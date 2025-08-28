"""Data router for market data endpoints."""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...data.database import get_db
from ...data.models import Candle, TimeFrame
from ...services.data_service import DataService
from ..schemas.data import (
    CandleResponse,
    SymbolInfo,
    MarketDataRequest,
    PriceHistoryResponse,
    RealtimeQuote
)
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/symbols", response_model=List[SymbolInfo])
async def get_available_symbols(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[SymbolInfo]:
    """
    Get list of available symbols with data coverage info.
    
    Returns symbols that have historical data in the database.
    """
    try:
        from ...data.models import Ticker
        
        # Query unique tickers that have candle data
        tickers_with_data = db.query(Ticker).join(Candle, Ticker.id == Candle.ticker_id).distinct().all()
        
        symbol_info = []
        for ticker in tickers_with_data:
            # Get data range for ticker
            first_candle = db.query(Candle).filter(
                Candle.ticker_id == ticker.id
            ).order_by(Candle.timestamp.asc()).first()
            
            last_candle = db.query(Candle).filter(
                Candle.ticker_id == ticker.id
            ).order_by(Candle.timestamp.desc()).first()
            
            if first_candle and last_candle:
                symbol_info.append(SymbolInfo(
                    symbol=ticker.symbol,
                    name=ticker.name or ticker.symbol,
                    data_start=first_candle.timestamp,
                    data_end=last_candle.timestamp,
                    candle_count=db.query(Candle).filter(Candle.ticker_id == ticker.id).count()
                ))
        
        return symbol_info
        
    except Exception as e:
        logger.error(f"Failed to get symbols: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve symbols"
        )


@router.get("/candles/{symbol}", response_model=List[CandleResponse])
async def get_candles(
    symbol: str,
    timeframe: TimeFrame = Query(TimeFrame.ONE_MIN),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(1000, le=10000),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[CandleResponse]:
    """
    Get historical candle data for a symbol.
    
    Parameters:
    - symbol: Stock symbol (e.g., AAPL)
    - timeframe: Candle timeframe (1min, 5min, etc.)
    - start_date: Start date for data (default: 7 days ago)
    - end_date: End date for data (default: now)
    - limit: Maximum number of candles to return
    """
    try:
        from ...data.models import Ticker
        
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=7)
        
        # Find ticker for symbol
        ticker = db.query(Ticker).filter(Ticker.symbol == symbol.upper()).first()
        if not ticker:
            logger.warning(f"Symbol {symbol} not found")
            return []
        
        # Query candles (note: timeframe is always 1min in database)
        query = db.query(Candle).filter(
            Candle.ticker_id == ticker.id,
            Candle.timestamp >= start_date,
            Candle.timestamp <= end_date
        ).order_by(Candle.timestamp.desc()).limit(limit)
        
        candles = query.all()
        
        if not candles:
            logger.warning(f"No candles found for {symbol} in date range")
            return []
        
        # Convert to response model
        return [
            CandleResponse(
                timestamp=candle.timestamp,
                open=float(candle.open),
                high=float(candle.high),
                low=float(candle.low),
                close=float(candle.close),
                volume=candle.volume
            )
            for candle in candles
        ]
        
    except Exception as e:
        logger.error(f"Failed to get candles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve candle data"
        )


@router.post("/fetch-historical")
async def fetch_historical_data(
    request: MarketDataRequest,
    data_service: DataService = Depends(),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Fetch historical data from Schwab API and store in database.
    
    This endpoint triggers a background task to fetch data.
    """
    try:
        # Validate request
        if request.end_date <= request.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date must be after start date"
            )
        
        # Calculate days
        days = (request.end_date - request.start_date).days
        if days > 60:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date range cannot exceed 60 days"
            )
        
        # Start data fetch task
        task_id = await data_service.fetch_historical_data_async(
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframe=request.timeframe
        )
        
        return {
            "task_id": task_id,
            "message": f"Started fetching data for {len(request.symbols)} symbols",
            "symbols": request.symbols,
            "date_range": f"{request.start_date} to {request.end_date}"
        }
        
    except Exception as e:
        logger.error(f"Failed to start historical data fetch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start data fetch"
        )


@router.get("/quote/{symbol}", response_model=RealtimeQuote)
async def get_realtime_quote(
    symbol: str,
    data_service: DataService = Depends(),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> RealtimeQuote:
    """
    Get real-time quote for a symbol.
    
    Fetches current market data from Schwab API.
    """
    try:
        quote = await data_service.get_quote(symbol.upper())
        
        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quote not found for symbol: {symbol}"
            )
        
        return RealtimeQuote(
            symbol=symbol.upper(),
            last_price=quote.get("lastPrice", 0),
            bid_price=quote.get("bidPrice", 0),
            ask_price=quote.get("askPrice", 0),
            bid_size=quote.get("bidSize", 0),
            ask_size=quote.get("askSize", 0),
            volume=quote.get("totalVolume", 0),
            open_price=quote.get("openPrice", 0),
            high_price=quote.get("highPrice", 0),
            low_price=quote.get("lowPrice", 0),
            close_price=quote.get("closePrice", 0),
            change=quote.get("netChange", 0),
            change_percent=quote.get("netPercentChangeInDouble", 0),
            timestamp=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get quote: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve quote"
        )


@router.get("/data-gaps")
async def identify_data_gaps(
    symbols: List[str] = Query(...),
    timeframe: TimeFrame = Query(TimeFrame.ONE_MIN),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Identify gaps in historical data for given symbols.
    
    Returns date ranges where data is missing.
    """
    try:
        gaps = {}
        
        from ...data.models import Ticker
        
        for symbol in symbols:
            # Find ticker for symbol
            ticker = db.query(Ticker).filter(Ticker.symbol == symbol.upper()).first()
            if not ticker:
                gaps[symbol] = [{"type": "no_ticker", "message": "Symbol not found"}]
                continue
                
            # Get all candles for ticker (note: timeframe is always 1min in database)
            candles = db.query(Candle.timestamp).filter(
                Candle.ticker_id == ticker.id
            ).order_by(Candle.timestamp.asc()).all()
            
            if not candles:
                gaps[symbol] = [{
                    "type": "no_data",
                    "message": "No data found for symbol"
                }]
                continue
            
            # Find gaps in data
            symbol_gaps = []
            timestamps = [c.timestamp for c in candles]
            
            for i in range(1, len(timestamps)):
                expected_next = timestamps[i-1] + timedelta(minutes=1)  # For 1min timeframe
                
                if timestamps[i] > expected_next + timedelta(minutes=5):  # Allow 5 min tolerance
                    symbol_gaps.append({
                        "start": timestamps[i-1],
                        "end": timestamps[i],
                        "duration_minutes": int((timestamps[i] - timestamps[i-1]).total_seconds() / 60)
                    })
            
            gaps[symbol] = symbol_gaps
        
        return {
            "symbols_checked": len(symbols),
            "gaps_found": sum(len(g) for g in gaps.values()),
            "gaps": gaps
        }
        
    except Exception as e:
        logger.error(f"Failed to identify data gaps: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to identify data gaps"
        )
"""DEPRECATED MODULE: src/api/routers.py

This monolithic routers module is retained for backward compatibility only.
The application uses the package 'src.api.routers' (directory with __init__.py)
as the source of FastAPI routers. Do not add new endpoints here.
Prefer adding routers under src/api/routers/ and export them from
src/api/routers/__init__.py.

This file can be removed once all external references to 'src.api.routers'
are eliminated and tests validate no regressions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime

from src.auth import get_authenticated_client
from src.utils.logger import logger
from .dependencies import require_auth, get_db, get_async_db, verify_api_key
from src.tasks import data_mining, backtesting

# Create routers
auth_router = APIRouter()
data_router = APIRouter()
strategy_router = APIRouter()
trading_router = APIRouter()


# Request/Response models
class AuthStatusResponse(BaseModel):
    """Authentication status response."""
    authenticated: bool
    username: str
    expires_at: Optional[datetime] = None
    

class StreamingRequest(BaseModel):
    """Streaming request parameters."""
    symbols: List[str]
    mode: str = "BOTH"  # QUOTES, CHARTS, or BOTH
    

class SubscriptionRequest(BaseModel):
    """Symbol subscription request."""
    symbols: List[str]
    

class DataMiningRequest(BaseModel):
    """Data mining request parameters."""
    symbols: List[str]
    start_date: datetime
    end_date: datetime
    

class StrategyCreateRequest(BaseModel):
    """Strategy creation request."""
    name: str
    strategy_class: str
    parameters: Dict[str, Any] = {}
    

class BacktestRequest(BaseModel):
    """Backtest request parameters."""
    strategy_id: str
    symbols: List[str]
    start_date: datetime
    end_date: datetime
    parameters: Optional[Dict[str, Any]] = None
    

class OptimizationRequest(BaseModel):
    """Strategy optimization request."""
    strategy_id: str
    symbols: List[str]
    start_date: datetime
    end_date: datetime
    parameter_ranges: Dict[str, Dict[str, Any]]
    

# Auth endpoints
@auth_router.get("/status", response_model=AuthStatusResponse)
async def auth_status(api_key_valid: bool = Depends(verify_api_key)):
    """Check authentication status."""
    try:
        return AuthStatusResponse(
            authenticated=True,
            username="api_user"
        )
    except Exception as e:
        logger.error(f"Auth status check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check authentication status"
        )


# Data endpoints
@data_router.get("/tickers")
async def get_tickers(
    user: dict = Depends(require_auth),
    db: Any = Depends(get_async_db)
):
    """Get list of available tickers."""
    try:
        from sqlalchemy import select
        from src.data.models import Ticker
        
        result = await db.execute(
            select(Ticker)
            .where(Ticker.active == True)
            .order_by(Ticker.tier, Ticker.symbol)
        )
        tickers = result.scalars().all()
        
        return {
            "tickers": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "name": t.name,
                    "tier": t.tier.value,
                    "last_mined": t.last_mined.isoformat() if t.last_mined else None,
                    "mining_status": t.mining_status.value if t.mining_status else None
                }
                for t in tickers
            ],
            "total": len(tickers)
        }
    except Exception as e:
        logger.error(f"Failed to get tickers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tickers: {str(e)}"
        )


@data_router.post("/mining/start")
async def start_data_mining(
    request: DataMiningRequest,
    user: dict = Depends(require_auth)
):
    """Start data mining job."""
    logger.info(f"User {user['username']} requested data mining for {len(request.symbols)} symbols")
    
    try:
        # Celery 태스크 호출
        result = data_mining.mine_date_range.delay(
            symbols=request.symbols,
            start_date=request.start_date.strftime("%Y-%m-%d"),
            end_date=request.end_date.strftime("%Y-%m-%d")
        )
        
        return {
            "job_id": result.id,
            "status": "submitted",
            "symbols": request.symbols,
            "date_range": {
                "start": request.start_date.isoformat(),
                "end": request.end_date.isoformat()
            },
            "message": f"Data mining job submitted for {len(request.symbols)} symbols"
        }
    except Exception as e:
        logger.error(f"Failed to start data mining: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start data mining: {str(e)}"
        )


@data_router.post("/mining/daily")
async def start_daily_mining(
    user: dict = Depends(require_auth)
):
    """Start the daily mining process."""
    logger.info(f"User {user['username']} started daily mining process")
    
    try:
        # Start daily mining task
        result = data_mining.start_daily_mining.delay()
        
        return {
            "task_id": result.id,
            "status": "submitted",
            "message": "Daily mining process started"
        }
    except Exception as e:
        logger.error(f"Failed to start daily mining: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start daily mining: {str(e)}"
        )


@data_router.post("/mining/check-gaps")
async def check_data_gaps(
    user: dict = Depends(require_auth)
):
    """Check and fill data gaps."""
    logger.info(f"User {user['username']} triggered gap check")
    
    try:
        # Start gap checking task
        result = data_mining.check_and_fill_gaps.delay()
        
        return {
            "task_id": result.id,
            "status": "submitted",
            "message": "Gap checking process started"
        }
    except Exception as e:
        logger.error(f"Failed to start gap check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start gap check: {str(e)}"
        )


@data_router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    limit: int = 100,
    user: dict = Depends(require_auth),
    db: Any = Depends(get_async_db)
):
    """Get candles for a specific symbol."""
    try:
        from sqlalchemy import select
        from src.data.models import Candle, Ticker
        
        # Get ticker ID
        result = await db.execute(
            select(Ticker).where(Ticker.symbol == symbol)
        )
        ticker = result.scalar_one_or_none()
        
        if not ticker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticker {symbol} not found"
            )
        
        # Get candles
        result = await db.execute(
            select(Candle)
            .where(Candle.ticker_id == ticker.id)
            .order_by(Candle.timestamp.desc())
            .limit(limit)
        )
        candles = result.scalars().all()
        
        return [
            {
                "timestamp": c.timestamp.isoformat(),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": c.volume
            }
            for c in candles
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get candles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candles: {str(e)}"
        )


# Streaming endpoints
@data_router.post("/streaming/start")
async def start_streaming_endpoint(
    request: StreamingRequest,
    api_key_valid: bool = Depends(verify_api_key)
):
    """Start real-time streaming for specified symbols."""
    try:
        from src.services.streaming_service import start_streaming, StreamingMode
        
        # Start streaming
        service = await start_streaming(
            request.symbols,
            StreamingMode[request.mode.upper()]
        )
        
        # Get status
        status = await service.get_status()
        
        return {
            "status": "started",
            "symbols": request.symbols,
            "mode": request.mode,
            "streaming_status": status
        }
        
    except Exception as e:
        logger.error(f"Failed to start streaming: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start streaming: {str(e)}"
        )


@data_router.post("/streaming/stop")
async def stop_streaming_endpoint(api_key_valid: bool = Depends(verify_api_key)):
    """Stop real-time streaming."""
    try:
        from src.services.streaming_service import stop_streaming
        
        await stop_streaming()
        
        return {
            "status": "stopped",
            "message": "Streaming service stopped successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to stop streaming: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop streaming: {str(e)}"
        )


@data_router.get("/streaming/status")
async def get_streaming_status(user: dict = Depends(require_auth)):
    """Get current streaming service status."""
    try:
        from src.services.streaming_service import get_streaming_service
        
        service = await get_streaming_service()
        status = await service.get_status()
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get streaming status: {e}")
        return {
            "active": False,
            "error": str(e)
        }


@data_router.post("/streaming/subscribe")
async def subscribe_symbols(
    request: SubscriptionRequest,
    user: dict = Depends(require_auth)
):
    """Subscribe to additional symbols for streaming."""
    try:
        from src.services.streaming_service import get_streaming_service
        
        service = await get_streaming_service()
        
        if not service.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Streaming service is not active"
            )
        
        await service.subscribe(request.symbols)
        
        return {
            "status": "subscribed",
            "symbols": request.symbols,
            "total_subscriptions": len(service.subscribed_symbols)
        }
        
    except Exception as e:
        logger.error(f"Failed to subscribe symbols: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to subscribe: {str(e)}"
        )


@data_router.post("/streaming/unsubscribe")
async def unsubscribe_symbols(
    request: SubscriptionRequest,
    user: dict = Depends(require_auth)
):
    """Unsubscribe from symbols."""
    try:
        from src.services.streaming_service import get_streaming_service
        
        service = await get_streaming_service()
        
        if not service.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Streaming service is not active"
            )
        
        await service.unsubscribe(request.symbols)
        
        return {
            "status": "unsubscribed",
            "symbols": request.symbols,
            "remaining_subscriptions": len(service.subscribed_symbols)
        }
        
    except Exception as e:
        logger.error(f"Failed to unsubscribe symbols: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unsubscribe: {str(e)}"
        )


@data_router.get("/streaming/candles")
async def get_current_candles(user: dict = Depends(require_auth)):
    """Get current in-progress candles from streaming service."""
    try:
        from src.services.streaming_service import get_streaming_service
        
        service = await get_streaming_service()
        candles = await service.get_current_candles()
        
        return {
            "count": len(candles),
            "candles": candles
        }
        
    except Exception as e:
        logger.error(f"Failed to get current candles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candles: {str(e)}"
        )


@data_router.get("/mining/summary")
async def get_mining_summary(
    user: dict = Depends(require_auth),
    db: Any = Depends(get_async_db)
):
    """Get overall mining status summary."""
    try:
        from src.services.data_mining_service import DataMiningService
        
        service = DataMiningService()
        await service.initialize()
        
        summary = await service.get_mining_status(db)
        
        return summary
    except Exception as e:
        logger.error(f"Failed to get mining summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mining summary: {str(e)}"
        )


@data_router.get("/mining/status/{job_id}")
async def get_mining_status(
    job_id: str,
    user: dict = Depends(require_auth)
):
    """Check data mining job status."""
    try:
        # Celery 태스크 진행 상황 조회
        result = data_mining.get_mining_progress.delay(job_id)
        progress_info = result.get(timeout=5)  # 5초 타임아웃
        
        return progress_info
    except Exception as e:
        logger.error(f"Failed to get mining status: {e}")
        return {
            "job_id": job_id,
            "status": "error",
            "error": str(e),
            "message": "Failed to get mining job status"
        }


# Strategy endpoints
@strategy_router.get("/")
async def list_strategies(user: dict = Depends(require_auth)):
    """List all available strategies."""
    # Placeholder - will be implemented in Phase 3
    return {"strategies": [], "message": "Strategy list placeholder"}


@strategy_router.post("/")
async def create_strategy(
    strategy: StrategyCreateRequest,
    user: dict = Depends(require_auth)
):
    """Create a new strategy."""
    # Placeholder - will be implemented in Phase 3
    logger.info(f"User {user['username']} creating strategy: {strategy.name}")
    return {
        "id": "placeholder",
        "name": strategy.name,
        "strategy_class": strategy.strategy_class,
        "parameters": strategy.parameters,
        "active": False,
        "message": "Strategy creation placeholder"
    }


@strategy_router.post("/{strategy_id}/activate")
async def activate_strategy(
    strategy_id: str,
    user: dict = Depends(require_auth)
):
    """Activate a strategy."""
    # Placeholder - will be implemented in Phase 3
    logger.info(f"User {user['username']} activating strategy: {strategy_id}")
    return {
        "id": strategy_id,
        "active": True,
        "message": "Strategy activation placeholder"
    }


# Trading endpoints
@trading_router.get("/positions")
async def get_positions(user: dict = Depends(require_auth)):
    """Get current positions."""
    # Placeholder - will be implemented in Phase 4
    return {"positions": [], "message": "Positions placeholder"}


@trading_router.get("/orders")
async def get_orders(
    status: Optional[str] = None,
    user: dict = Depends(require_auth)
):
    """Get orders with optional status filter."""
    # Placeholder - will be implemented in Phase 4
    return {
        "orders": [],
        "filter": {"status": status} if status else None,
        "message": "Orders placeholder"
    }


@trading_router.get("/signals")
async def get_signals(
    limit: int = 10,
    user: dict = Depends(require_auth)
):
    """Get recent trading signals."""
    # Placeholder - will be implemented in Phase 4
    return {
        "signals": [],
        "limit": limit,
        "message": "Signals placeholder"
    }


@trading_router.get("/pnl")
async def get_pnl(user: dict = Depends(require_auth)):
    """Get profit and loss summary."""
    # Placeholder - will be implemented in Phase 4
    return {
        "total_pnl": 0.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "message": "P&L placeholder"
    }


# Backtesting endpoints
@strategy_router.post("/backtest")
async def run_backtest(
    request: BacktestRequest,
    user: dict = Depends(require_auth)
):
    """Run backtest for a strategy."""
    logger.info(f"User {user['username']} requested backtest for strategy {request.strategy_id}")
    
    try:
        # Celery 태스크 호출
        result = backtesting.run_backtest_task.delay(
            strategy_id=request.strategy_id,
            symbols=request.symbols,
            start_date=request.start_date.strftime("%Y-%m-%d"),
            end_date=request.end_date.strftime("%Y-%m-%d"),
            parameters=request.parameters
        )
        
        return {
            "task_id": result.id,
            "status": "submitted",
            "strategy_id": request.strategy_id,
            "message": "Backtest task submitted"
        }
    except Exception as e:
        logger.error(f"Failed to start backtest: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start backtest: {str(e)}"
        )


@strategy_router.get("/backtest/{task_id}")
async def get_backtest_result(
    task_id: str,
    user: dict = Depends(require_auth)
):
    """Get backtest task result."""
    try:
        from celery.result import AsyncResult
        from src.tasks.celery_app import celery_app
        
        result = AsyncResult(task_id, app=celery_app)
        
        if result.ready():
            if result.successful():
                return result.get()
            else:
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(result.info)
                }
        else:
            return {
                "task_id": task_id,
                "status": result.state,
                "info": result.info if result.info else {}
            }
    except Exception as e:
        logger.error(f"Failed to get backtest result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backtest result: {str(e)}"
        )


@strategy_router.post("/optimize")
async def optimize_strategy(
    request: OptimizationRequest,
    user: dict = Depends(require_auth)
):
    """Optimize strategy parameters."""
    logger.info(f"User {user['username']} requested optimization for strategy {request.strategy_id}")
    
    try:
        # Celery 태스크 호출
        result = backtesting.optimize_strategy.delay(
            strategy_id=request.strategy_id,
            symbols=request.symbols,
            start_date=request.start_date.strftime("%Y-%m-%d"),
            end_date=request.end_date.strftime("%Y-%m-%d"),
            parameter_ranges=request.parameter_ranges
        )
        
        return {
            "task_id": result.id,
            "status": "submitted",
            "strategy_id": request.strategy_id,
            "message": "Optimization task submitted"
        }
    except Exception as e:
        logger.error(f"Failed to start optimization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start optimization: {str(e)}"
        )


@strategy_router.post("/batch-backtest")
async def batch_backtest(
    strategy_ids: List[str],
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    user: dict = Depends(require_auth)
):
    """Run batch backtest for multiple strategies."""
    logger.info(f"User {user['username']} requested batch backtest for {len(strategy_ids)} strategies")
    
    try:
        # Celery 태스크 호출
        result = backtesting.batch_backtest.delay(
            strategy_ids=strategy_ids,
            symbols=symbols,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        
        return result.get(timeout=5)  # 빠른 응답을 위해 5초 타임아웃
    except Exception as e:
        logger.error(f"Failed to start batch backtest: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start batch backtest: {str(e)}"
        )


@strategy_router.get("/batch-backtest/{job_id}/progress")
async def get_batch_backtest_progress(
    job_id: str,
    user: dict = Depends(require_auth)
):
    """Get batch backtest progress."""
    try:
        # Celery 태스크 진행 상황 조회
        result = backtesting.get_backtest_progress.delay(job_id)
        progress_info = result.get(timeout=5)  # 5초 타임아웃
        
        return progress_info
    except Exception as e:
        logger.error(f"Failed to get batch backtest progress: {e}")
        return {
            "job_id": job_id,
            "status": "error",
            "error": str(e),
            "message": "Failed to get batch backtest progress"
        }
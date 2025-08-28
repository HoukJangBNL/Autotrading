"""Portfolio router for portfolio management endpoints."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ...data.database import get_db
from ...trading.portfolio_service import get_portfolio_service
from ..schemas.portfolio import (
    PortfolioSummaryResponse,
    PortfolioHistoryResponse,
    PortfolioPosition,
    PortfolioPerformance,
    AssetAllocation,
    TransactionHistory
)
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    account_hash: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> PortfolioSummaryResponse:
    """
    Get portfolio summary with metrics and positions.
    
    Args:
        account_hash: Account hash (optional)
        
    Returns:
        Portfolio summary including metrics and positions
    """
    try:
        portfolio_service = get_portfolio_service()
        await portfolio_service.initialize()
        summary = await portfolio_service.get_portfolio_summary(account_hash)
        
        return PortfolioSummaryResponse(**summary)
        
    except Exception as e:
        logger.error(f"Failed to get portfolio summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/positions", response_model=List[PortfolioPosition])
async def get_portfolio_positions(
    account_hash: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[PortfolioPosition]:
    """
    Get all portfolio positions.
    
    Returns detailed information for each holding.
    """
    try:
        # Get portfolio service
        portfolio_service = get_portfolio_service()
        await portfolio_service.initialize()
        
        # Get portfolio summary which includes positions
        summary = await portfolio_service.get_portfolio_summary(account_hash)
        
        # Extract and return positions
        positions = []
        for pos_data in summary.get('positions', []):
            positions.append(PortfolioPosition(
                symbol=pos_data['symbol'],
                quantity=pos_data['quantity'],
                averageCost=pos_data['averageCost'],
                currentPrice=pos_data['currentPrice'],
                marketValue=pos_data['marketValue'],
                unrealizedPnl=pos_data['unrealizedPnl'],
                unrealizedPnlPercent=pos_data['unrealizedPnlPercent'],
                realizedPnl=pos_data['realizedPnl'],
                assetType=pos_data['assetType'],
                positionType=pos_data['positionType'],
                percentOfPortfolio=pos_data['percentOfPortfolio']
            ))
        
        # Sort by market value descending
        positions.sort(key=lambda x: x.marketValue, reverse=True)
        
        return positions
        
    except Exception as e:
        logger.error(f"Failed to get portfolio positions: {e}")
        return []


@router.get("/performance", response_model=PortfolioPerformance)
async def get_portfolio_performance(
    period: str = Query("1M", regex="^(1D|1W|1M|3M|6M|1Y|YTD|ALL)$"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> PortfolioPerformance:
    """
    Get portfolio performance metrics.
    
    Returns performance data for the specified period.
    """
    try:
        # Calculate period start date
        now = datetime.now()
        if period == "1D":
            start_date = now - timedelta(days=1)
        elif period == "1W":
            start_date = now - timedelta(weeks=1)
        elif period == "1M":
            start_date = now - timedelta(days=30)
        elif period == "3M":
            start_date = now - timedelta(days=90)
        elif period == "6M":
            start_date = now - timedelta(days=180)
        elif period == "1Y":
            start_date = now - timedelta(days=365)
        elif period == "YTD":
            start_date = datetime(now.year, 1, 1)
        else:  # ALL
            start_date = datetime(2020, 1, 1)  # Mock start date
        
        # Mock performance data
        # In production, this would query historical portfolio values
        total_return = 12.5  # Mock 12.5%
        annualized_return = total_return * (365 / (now - start_date).days)
        
        # Mock daily values for chart
        days = (now - start_date).days
        daily_values = []
        base_value = 100000  # Starting value
        
        for i in range(min(days, 365)):
            date = start_date + timedelta(days=i)
            # Add some randomness
            change = (i / days) * total_return / 100 + (i % 3 - 1) * 0.005
            value = base_value * (1 + change)
            daily_values.append({
                "date": date.isoformat(),
                "value": round(value, 2),
                "change": round(value - base_value, 2),
                "change_pct": round(change * 100, 2)
            })
        
        return PortfolioPerformance(
            period=period,
            start_date=start_date,
            end_date=now,
            starting_value=base_value,
            ending_value=daily_values[-1]["value"] if daily_values else base_value,
            total_return=total_return,
            total_return_pct=total_return,
            annualized_return=annualized_return,
            volatility=15.5,  # Mock
            sharpe_ratio=1.2,  # Mock
            max_drawdown=-8.5,  # Mock
            win_rate=0.65,  # Mock
            profit_factor=1.8,  # Mock
            daily_values=daily_values[-30:] if len(daily_values) > 30 else daily_values  # Last 30 days
        )
        
    except Exception as e:
        logger.error(f"Failed to get portfolio performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve portfolio performance"
        )


@router.get("/allocation", response_model=AssetAllocation)
async def get_asset_allocation(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AssetAllocation:
    """
    Get portfolio asset allocation.
    
    Returns breakdown by asset type, sector, and individual holdings.
    """
    try:
        # Get positions
        positions = await get_portfolio_positions(current_user)
        
        # Calculate total value
        total_value = sum(p.market_value for p in positions)
        
        if total_value == 0:
            return AssetAllocation(
                total_value=0,
                by_asset_type=[],
                by_sector=[],
                by_holding=[],
                cash_percentage=100
            )
        
        # Mock sector data (in production, would look up actual sectors)
        sector_map = {
            "AAPL": "Technology",
            "MSFT": "Technology", 
            "GOOGL": "Technology",
            "AMZN": "Consumer Discretionary",
            "JPM": "Financials",
            "JNJ": "Healthcare",
            "XOM": "Energy"
        }
        
        # Calculate allocations
        by_asset_type = {}
        by_sector = {}
        by_holding = []
        
        for position in positions:
            # Asset type allocation
            asset_type = position.position_type
            if asset_type not in by_asset_type:
                by_asset_type[asset_type] = {"value": 0, "percentage": 0, "count": 0}
            by_asset_type[asset_type]["value"] += position.market_value
            by_asset_type[asset_type]["count"] += 1
            
            # Sector allocation
            sector = sector_map.get(position.symbol, "Other")
            if sector not in by_sector:
                by_sector[sector] = {"value": 0, "percentage": 0, "count": 0}
            by_sector[sector]["value"] += position.market_value
            by_sector[sector]["count"] += 1
            
            # Individual holdings
            by_holding.append({
                "symbol": position.symbol,
                "name": position.name,
                "value": position.market_value,
                "percentage": (position.market_value / total_value) * 100,
                "shares": position.quantity
            })
        
        # Calculate percentages
        for asset_data in by_asset_type.values():
            asset_data["percentage"] = (asset_data["value"] / total_value) * 100
        
        for sector_data in by_sector.values():
            sector_data["percentage"] = (sector_data["value"] / total_value) * 100
        
        # Sort holdings by value
        by_holding.sort(key=lambda x: x["value"], reverse=True)
        
        # Get cash balance
        summary = await get_portfolio_summary(current_user)
        cash_percentage = (summary.cash_balance / summary.total_value * 100) if summary.total_value > 0 else 0
        
        return AssetAllocation(
            total_value=total_value,
            by_asset_type=[
                {"type": k, **v} for k, v in by_asset_type.items()
            ],
            by_sector=[
                {"sector": k, **v} for k, v in by_sector.items()
            ],
            by_holding=by_holding[:10],  # Top 10 holdings
            cash_percentage=cash_percentage
        )
        
    except Exception as e:
        logger.error(f"Failed to get asset allocation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve asset allocation"
        )


@router.get("/transactions", response_model=List[TransactionHistory])
async def get_transaction_history(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    symbol: Optional[str] = None,
    transaction_type: Optional[str] = None,
    limit: int = Query(100, le=1000),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[TransactionHistory]:
    """
    Get transaction history.
    
    Returns list of all portfolio transactions (trades, dividends, etc).
    """
    try:
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # TODO: Get actual transactions from broker
        # For now, return mock data
        transactions = []
        
        # Mock some trades
        mock_trades = [
            {
                "symbol": "AAPL",
                "type": "BUY",
                "quantity": 100,
                "price": 150.00,
                "date": datetime.now() - timedelta(days=5)
            },
            {
                "symbol": "MSFT",
                "type": "BUY", 
                "quantity": 50,
                "price": 380.00,
                "date": datetime.now() - timedelta(days=3)
            },
            {
                "symbol": "AAPL",
                "type": "SELL",
                "quantity": 50,
                "price": 155.00,
                "date": datetime.now() - timedelta(days=1)
            }
        ]
        
        for i, trade in enumerate(mock_trades):
            if trade["date"] < start_date or trade["date"] > end_date:
                continue
            if symbol and trade["symbol"] != symbol.upper():
                continue
            if transaction_type and trade["type"] != transaction_type:
                continue
            
            transactions.append(TransactionHistory(
                transaction_id=f"TXN{i+1:06d}",
                date=trade["date"],
                type=trade["type"],
                symbol=trade["symbol"],
                description=f"{trade['type']} {trade['quantity']} shares of {trade['symbol']}",
                quantity=trade["quantity"],
                price=trade["price"],
                amount=trade["quantity"] * trade["price"],
                fees=0.01 * trade["quantity"],  # $0.01 per share
                net_amount=trade["quantity"] * trade["price"] + (0.01 * trade["quantity"] if trade["type"] == "BUY" else -0.01 * trade["quantity"]),
                balance_after=100000 + (i * 1000)  # Mock balance
            ))
        
        # Sort by date descending
        transactions.sort(key=lambda x: x.date, reverse=True)
        
        return transactions[:limit]
        
    except Exception as e:
        logger.error(f"Failed to get transaction history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transaction history"
        )


@router.post("/rebalance")
async def rebalance_portfolio(
    target_allocation: Dict[str, float],
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Calculate rebalancing trades.
    
    Returns suggested trades to achieve target allocation.
    """
    try:
        # Validate allocations sum to 100%
        total_allocation = sum(target_allocation.values())
        if abs(total_allocation - 100) > 0.1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target allocations must sum to 100%, got {total_allocation}%"
            )
        
        # Get current positions
        positions = await get_portfolio_positions(current_user)
        summary = await get_portfolio_summary(current_user)
        
        total_value = summary.total_value
        if total_value == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot rebalance empty portfolio"
            )
        
        # Calculate current allocation
        current_allocation = {}
        for position in positions:
            current_allocation[position.symbol] = (position.market_value / total_value) * 100
        
        # Calculate required trades
        trades = []
        for symbol, target_pct in target_allocation.items():
            current_pct = current_allocation.get(symbol, 0)
            diff_pct = target_pct - current_pct
            
            if abs(diff_pct) > 0.5:  # Only rebalance if difference > 0.5%
                target_value = total_value * (target_pct / 100)
                current_value = total_value * (current_pct / 100)
                trade_value = target_value - current_value
                
                # Get current price (mock)
                current_price = 150.00  # Would get actual price
                shares = int(trade_value / current_price)
                
                if shares != 0:
                    trades.append({
                        "symbol": symbol,
                        "action": "BUY" if shares > 0 else "SELL",
                        "shares": abs(shares),
                        "estimated_value": abs(trade_value),
                        "current_allocation": current_pct,
                        "target_allocation": target_pct
                    })
        
        return {
            "total_portfolio_value": total_value,
            "trades_required": len(trades),
            "estimated_cost": sum(t["estimated_value"] for t in trades if t["action"] == "BUY"),
            "estimated_proceeds": sum(t["estimated_value"] for t in trades if t["action"] == "SELL"),
            "trades": trades
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to calculate rebalancing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate rebalancing"
        )


@router.get("/{account_hash}/summary", response_model=PortfolioSummaryResponse)
async def get_account_portfolio_summary(
    account_hash: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> PortfolioSummaryResponse:
    """
    Get portfolio summary for specific account.
    
    Args:
        account_hash: Account hash identifier
        
    Returns:
        Portfolio summary for the account
    """
    try:
        portfolio_service = get_portfolio_service()
        await portfolio_service.initialize()
        summary = await portfolio_service.get_portfolio_summary(account_hash)
        
        return PortfolioSummaryResponse(**summary)
        
    except Exception as e:
        logger.error(f"Failed to get portfolio summary for {account_hash}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/history", response_model=PortfolioHistoryResponse)
async def get_portfolio_history(
    account_hash: Optional[str] = None,
    days: int = 30,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> PortfolioHistoryResponse:
    """
    Get portfolio value history.
    
    Args:
        account_hash: Account hash (optional)
        days: Number of days of history (default 30)
        
    Returns:
        Historical portfolio data
    """
    try:
        portfolio_service = get_portfolio_service()
        await portfolio_service.initialize()
        history = await portfolio_service.get_portfolio_history(
            account_hash=account_hash,
            days=days
        )
        
        return PortfolioHistoryResponse(**history)
        
    except Exception as e:
        logger.error(f"Failed to get portfolio history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/refresh")
async def refresh_portfolio_data(
    account_hash: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Refresh portfolio data and broadcast updates.
    
    Args:
        account_hash: Account hash to refresh (optional, all if None)
        
    Returns:
        Updated portfolio summary
    """
    try:
        portfolio_service = get_portfolio_service()
        await portfolio_service.initialize()
        
        # Get fresh portfolio data
        summary = await portfolio_service.get_portfolio_summary(account_hash)
        
        # The portfolio service already publishes to Redis
        # WebSocket handlers will pick up and broadcast
        
        return {
            "status": "success",
            "message": "Portfolio data refreshed",
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Failed to refresh portfolio data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.websocket("/ws")
async def portfolio_websocket(
    websocket: WebSocket,
    account_hash: Optional[str] = None
):
    """
    WebSocket endpoint for real-time portfolio updates.
    
    Subscribes to portfolio update events and streams to client.
    """
    await websocket.accept()
    
    try:
        # Subscribe to portfolio updates via Redis
        from ...cache import get_redis_client
        redis = await get_redis_client()
        
        pubsub = redis.pubsub()
        await pubsub.subscribe('portfolio_updates')
        
        # Send initial portfolio data
        portfolio_service = get_portfolio_service()
        await portfolio_service.initialize()
        summary = await portfolio_service.get_portfolio_summary(account_hash)
        await websocket.send_json({
            'type': 'portfolio_snapshot',
            'data': summary
        })
        
        # Listen for updates
        async for message in pubsub.listen():
            if message['type'] == 'message':
                data = message['data']
                
                # Filter by account if specified
                if account_hash and data.get('accountHash') != account_hash:
                    continue
                    
                await websocket.send_json({
                    'type': 'portfolio_update',
                    'data': data
                })
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await pubsub.unsubscribe('portfolio_updates')
        await websocket.close()
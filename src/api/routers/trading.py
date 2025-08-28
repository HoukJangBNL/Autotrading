"""Trading router for live trading operations."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ...data.database import get_db
from ...broker import get_schwab_broker
from ...strategy.models import OrderSide, OrderType, OrderStatus
from ..schemas.trading import (
    OrderRequest,
    OrderResponse,
    PositionResponse,
    SignalResponse,
    TradingStatus,
    ExecutionReport
)
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for demo (replace with database in production)
orders_store: Dict[str, Dict[str, Any]] = {}
positions_store: Dict[str, Dict[str, Any]] = {}
signals_store: List[Dict[str, Any]] = []


@router.get("/status", response_model=TradingStatus)
async def get_trading_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> TradingStatus:
    """
    Get overall trading system status.
    
    Returns account info, active strategies, and system health.
    """
    try:
        # Get broker instance
        broker = await get_schwab_broker()
        
        # Get account info
        account_info = await broker.get_account_info()
        
        # Count active positions
        active_positions = len([p for p in positions_store.values() if p.get("quantity", 0) > 0])
        
        # Count open orders
        open_orders = len([o for o in orders_store.values() if o["status"] in ["PENDING", "PARTIAL"]])
        
        # Get today's trades
        today = datetime.now().date()
        today_trades = len([
            o for o in orders_store.values() 
            if o.get("filled_time") and o["filled_time"].date() == today
        ])
        
        return TradingStatus(
            is_connected=True,
            account_id=account_info.get("securitiesAccount", {}).get("accountId", ""),
            cash_balance=account_info.get("securitiesAccount", {}).get("currentBalances", {}).get("cashBalance", 0),
            buying_power=account_info.get("securitiesAccount", {}).get("currentBalances", {}).get("buyingPower", 0),
            total_value=account_info.get("securitiesAccount", {}).get("currentBalances", {}).get("liquidationValue", 0),
            active_positions=active_positions,
            open_orders=open_orders,
            today_trades=today_trades,
            active_strategies=0,  # TODO: Get from strategy service
            last_update=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to get trading status: {e}")
        return TradingStatus(
            is_connected=False,
            account_id="",
            cash_balance=0,
            buying_power=0,
            total_value=0,
            active_positions=0,
            open_orders=0,
            today_trades=0,
            active_strategies=0,
            last_update=datetime.now()
        )


@router.post("/orders", response_model=OrderResponse)
async def place_order(
    order: OrderRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> OrderResponse:
    """
    Place a new order.
    
    Submits order to broker for execution.
    """
    try:
        # Validate order
        if order.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order quantity must be positive"
            )
        
        if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and not order.limit_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit price required for limit orders"
            )
        
        if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and not order.stop_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stop price required for stop orders"
            )
        
        # Generate order ID
        order_id = str(uuid4())
        
        # Create order record
        order_data = {
            "order_id": order_id,
            "symbol": order.symbol.upper(),
            "side": order.side,
            "quantity": order.quantity,
            "order_type": order.order_type,
            "limit_price": order.limit_price,
            "stop_price": order.stop_price,
            "time_in_force": order.time_in_force,
            "status": OrderStatus.PENDING,
            "created_at": datetime.now(),
            "filled_quantity": 0,
            "average_fill_price": 0,
            "commission": 0,
            "strategy_name": order.strategy_name,
            "signal_id": order.signal_id
        }
        
        # Store order
        orders_store[order_id] = order_data
        
        # TODO: Actually submit to broker
        # broker = await get_schwab_broker()
        # broker_order_id = await broker.place_order(order_data)
        # order_data["broker_order_id"] = broker_order_id
        
        # For demo, simulate immediate fill
        order_data["status"] = OrderStatus.FILLED
        order_data["filled_quantity"] = order.quantity
        order_data["average_fill_price"] = order.limit_price or 150.00  # Mock price
        order_data["filled_time"] = datetime.now()
        order_data["commission"] = float(order.quantity) * 0.01  # $0.01 per share
        
        # Update position
        if order.symbol not in positions_store:
            positions_store[order.symbol] = {
                "symbol": order.symbol,
                "quantity": 0,
                "average_cost": 0,
                "current_price": 0,
                "market_value": 0,
                "unrealized_pnl": 0,
                "realized_pnl": 0
            }
        
        position = positions_store[order.symbol]
        if order.side == OrderSide.BUY:
            # Calculate new average cost
            total_cost = position["quantity"] * position["average_cost"] + order_data["filled_quantity"] * order_data["average_fill_price"]
            position["quantity"] += order_data["filled_quantity"]
            position["average_cost"] = total_cost / position["quantity"] if position["quantity"] > 0 else 0
        else:  # SELL
            # Calculate realized P&L
            if position["quantity"] > 0:
                realized_pnl = (order_data["average_fill_price"] - position["average_cost"]) * order_data["filled_quantity"]
                position["realized_pnl"] += realized_pnl
            position["quantity"] -= order_data["filled_quantity"]
        
        return OrderResponse(**order_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to place order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to place order"
        )


@router.get("/orders", response_model=List[OrderResponse])
async def get_orders(
    status: Optional[OrderStatus] = None,
    symbol: Optional[str] = None,
    limit: int = Query(100, le=500),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[OrderResponse]:
    """
    Get order history.
    
    Can filter by status or symbol.
    """
    try:
        orders = []
        
        for order_data in orders_store.values():
            # Apply filters
            if status and order_data["status"] != status:
                continue
            if symbol and order_data["symbol"] != symbol.upper():
                continue
            
            orders.append(OrderResponse(**order_data))
        
        # Sort by created_at descending
        orders.sort(key=lambda x: x.created_at, reverse=True)
        
        return orders[:limit]
        
    except Exception as e:
        logger.error(f"Failed to get orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve orders"
        )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> OrderResponse:
    """
    Get specific order details.
    """
    try:
        if order_id not in orders_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order not found: {order_id}"
            )
        
        return OrderResponse(**orders_store[order_id])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve order"
        )


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Cancel a pending order.
    """
    try:
        if order_id not in orders_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order not found: {order_id}"
            )
        
        order_data = orders_store[order_id]
        
        if order_data["status"] not in [OrderStatus.PENDING, OrderStatus.PARTIAL]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel order with status: {order_data['status']}"
            )
        
        # TODO: Cancel with broker
        # broker = await get_schwab_broker()
        # await broker.cancel_order(order_data["broker_order_id"])
        
        order_data["status"] = OrderStatus.CANCELLED
        order_data["cancelled_at"] = datetime.now()
        
        return {"message": f"Order {order_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel order"
        )


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[PositionResponse]:
    """
    Get current positions.
    
    Returns all open positions with current market values.
    """
    try:
        positions = []
        
        for position_data in positions_store.values():
            if position_data["quantity"] > 0:
                # Update current price (mock)
                position_data["current_price"] = position_data["average_cost"] * 1.05  # Mock 5% gain
                position_data["market_value"] = position_data["quantity"] * position_data["current_price"]
                position_data["unrealized_pnl"] = (position_data["current_price"] - position_data["average_cost"]) * position_data["quantity"]
                
                positions.append(PositionResponse(**position_data))
        
        return positions
        
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve positions"
        )


@router.get("/signals", response_model=List[SignalResponse])
async def get_signals(
    strategy_id: Optional[str] = None,
    limit: int = Query(50, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[SignalResponse]:
    """
    Get recent trading signals.
    
    Returns signals generated by strategies.
    """
    try:
        # Filter signals
        filtered_signals = signals_store
        if strategy_id:
            filtered_signals = [s for s in signals_store if s.get("strategy_id") == strategy_id]
        
        # Sort by timestamp descending
        filtered_signals.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Convert to response model
        return [SignalResponse(**signal) for signal in filtered_signals[:limit]]
        
    except Exception as e:
        logger.error(f"Failed to get signals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve signals"
        )


@router.post("/signals/{signal_id}/execute")
async def execute_signal(
    signal_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> OrderResponse:
    """
    Manually execute a trading signal.
    
    Creates an order based on the signal parameters.
    """
    try:
        # Find signal
        signal = next((s for s in signals_store if s["signal_id"] == signal_id), None)
        if not signal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signal not found: {signal_id}"
            )
        
        # Check if already executed
        if signal.get("executed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Signal already executed"
            )
        
        # Create order from signal
        order_request = OrderRequest(
            symbol=signal["symbol"],
            side=signal["direction"],
            quantity=signal.get("position_size", 100),
            order_type=OrderType.MARKET,
            strategy_name=signal.get("strategy_name"),
            signal_id=signal_id
        )
        
        # Place order
        order_response = await place_order(order_request, current_user)
        
        # Mark signal as executed
        signal["executed"] = True
        signal["order_id"] = order_response.order_id
        
        return order_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute signal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute signal"
        )


@router.get("/performance", response_model=Dict[str, Any])
async def get_performance_summary(
    period: str = Query("today", regex="^(today|week|month|year|all)$"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get trading performance summary.
    
    Returns P&L, win rate, and other metrics for the specified period.
    """
    try:
        # Calculate period start date
        now = datetime.now()
        if period == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        elif period == "year":
            start_date = now - timedelta(days=365)
        else:  # all
            start_date = datetime.min
        
        # Filter orders by period
        period_orders = [
            o for o in orders_store.values()
            if o.get("filled_time") and o["filled_time"] >= start_date
        ]
        
        # Calculate metrics
        total_trades = len(period_orders)
        total_pnl = sum(p.get("realized_pnl", 0) for p in positions_store.values())
        
        # Calculate win rate (mock)
        winning_trades = int(total_trades * 0.6)  # Mock 60% win rate
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        return {
            "period": period,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "average_pnl": total_pnl / total_trades if total_trades > 0 else 0,
            "best_trade": 500.00,  # Mock
            "worst_trade": -200.00,  # Mock
            "sharpe_ratio": 1.5,  # Mock
            "max_drawdown": -0.05,  # Mock -5%
            "last_update": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve performance summary"
        )
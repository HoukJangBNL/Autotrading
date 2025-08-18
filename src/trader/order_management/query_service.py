"""
CQRS Query Service for Order Management System.

This module implements the query (read) side of CQRS pattern, providing
optimized read operations and real-time projections for order data.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from uuid import UUID
from dataclasses import dataclass
from enum import Enum
import logging

from eventsourcing.application import Application

from .event_sourced_order import OrderAggregate
from .order import OrderState, OrderType, OrderSide
from ...utils.logger import get_logger

logger = get_logger(__name__)


class OrderSortBy(str, Enum):
    """Order sorting options."""
    CREATED_AT = "created_at"
    SUBMITTED_AT = "submitted_at"
    COMPLETED_AT = "completed_at"
    SYMBOL = "symbol"
    QUANTITY = "quantity"
    STATE = "state"


class OrderFilter:
    """Filter criteria for order queries."""
    
    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        states: Optional[List[OrderState]] = None,
        sides: Optional[List[OrderSide]] = None,
        order_types: Optional[List[OrderType]] = None,
        account_ids: Optional[List[str]] = None,
        strategy_ids: Optional[List[str]] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        submitted_after: Optional[datetime] = None,
        submitted_before: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        min_quantity: Optional[int] = None,
        max_quantity: Optional[int] = None,
        min_value: Optional[Decimal] = None,
        max_value: Optional[Decimal] = None,
        active_only: bool = False,
        completed_only: bool = False
    ):
        self.symbols = symbols or []
        self.states = states or []
        self.sides = sides or []
        self.order_types = order_types or []
        self.account_ids = account_ids or []
        self.strategy_ids = strategy_ids or []
        self.created_after = created_after
        self.created_before = created_before
        self.submitted_after = submitted_after
        self.submitted_before = submitted_before
        self.tags = tags or []
        self.min_quantity = min_quantity
        self.max_quantity = max_quantity
        self.min_value = min_value
        self.max_value = max_value
        self.active_only = active_only
        self.completed_only = completed_only


@dataclass
class OrderSummary:
    """Summary information for an order."""
    order_id: UUID
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    state: OrderState
    filled_quantity: int
    remaining_quantity: int
    average_fill_price: Decimal
    created_at: datetime
    submitted_at: Optional[datetime]
    completed_at: Optional[datetime]
    account_id: str
    strategy_id: str
    broker_order_id: Optional[str]
    executed_value: Decimal
    total_cost: Decimal
    is_active: bool


@dataclass
class OrderStatistics:
    """Aggregate statistics for orders."""
    total_orders: int
    active_orders: int
    completed_orders: int
    filled_orders: int
    cancelled_orders: int
    rejected_orders: int
    total_volume: Decimal
    total_commission: Decimal
    total_fees: Decimal
    average_fill_time: Optional[timedelta]
    success_rate: float
    
    # By symbol
    symbol_breakdown: Dict[str, int]
    
    # By strategy
    strategy_breakdown: Dict[str, int]
    
    # By time period
    orders_today: int
    orders_this_week: int
    orders_this_month: int


@dataclass
class PortfolioPosition:
    """Current position for a symbol."""
    symbol: str
    quantity: int  # Net position (positive = long, negative = short)
    average_cost: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    total_cost: Decimal
    total_commission: Decimal
    total_fees: Decimal
    first_trade_at: datetime
    last_trade_at: datetime
    trade_count: int


class OrderQueryService:
    """
    Query service for order management.
    
    Handles all read operations (queries) in the CQRS pattern.
    Provides optimized queries, projections, and analytics.
    """
    
    def __init__(self, application: Application):
        """
        Initialize query service.
        
        Args:
            application: Event sourcing application for data access
        """
        self.application = application
        
        # Cache for frequently accessed data
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, datetime] = {}
        self.cache_duration = timedelta(minutes=5)
        
        logger.info("Order query service initialized")
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get item from cache if not expired."""
        if key in self._cache:
            expiry = self._cache_ttl.get(key)
            if expiry and datetime.now(timezone.utc) < expiry:
                return self._cache[key]
            else:
                # Expired, remove from cache
                self._cache.pop(key, None)
                self._cache_ttl.pop(key, None)
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Set item in cache with TTL."""
        self._cache[key] = value
        self._cache_ttl[key] = datetime.now(timezone.utc) + self.cache_duration
    
    async def get_order(self, order_id: UUID) -> Optional[OrderAggregate]:
        """
        Get order by ID.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order aggregate or None if not found
        """
        try:
            # Check cache first
            cache_key = f"order:{order_id}"
            cached_order = self._get_from_cache(cache_key)
            if cached_order:
                return cached_order
            
            # Load from repository
            order = self.application.repository.get(order_id)
            
            # Cache if found
            if order:
                self._set_cache(cache_key, order)
            
            return order
            
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None
    
    async def get_order_summary(self, order_id: UUID) -> Optional[OrderSummary]:
        """
        Get order summary information.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order summary or None if not found
        """
        order = await self.get_order(order_id)
        if not order:
            return None
        
        return OrderSummary(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            state=order.state,
            filled_quantity=order.filled_quantity,
            remaining_quantity=order.remaining_quantity,
            average_fill_price=order.average_fill_price,
            created_at=order.created_at,
            submitted_at=order.submitted_at,
            completed_at=order.completed_at,
            account_id=order.account_id,
            strategy_id=order.strategy_id,
            broker_order_id=order.broker_order_id,
            executed_value=order.executed_value,
            total_cost=order.total_cost,
            is_active=order.is_active
        )
    
    async def list_orders(
        self,
        filter_criteria: Optional[OrderFilter] = None,
        sort_by: OrderSortBy = OrderSortBy.CREATED_AT,
        ascending: bool = False,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[OrderSummary]:
        """
        List orders with filtering and sorting.
        
        Args:
            filter_criteria: Filter criteria
            sort_by: Sort field
            ascending: Sort direction
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of order summaries
        """
        try:
            # For now, we'll load all orders and filter in memory
            # In a production system, this would be optimized with database queries
            # or materialized views
            
            # Get all order IDs (this would be optimized in production)
            # Since eventsourcing doesn't provide a direct way to list all aggregates,
            # we'll need to maintain an index or use a different approach
            
            # For demonstration, return empty list with logging
            logger.info(f"List orders called with filter: {filter_criteria}, sort: {sort_by}")
            
            # In production, this would:
            # 1. Query an optimized read model/projection
            # 2. Apply filters at the database level
            # 3. Sort and paginate efficiently
            # 4. Return OrderSummary objects
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to list orders: {e}")
            return []
    
    async def get_active_orders(self, account_id: Optional[str] = None) -> List[OrderSummary]:
        """
        Get all active orders.
        
        Args:
            account_id: Optional account filter
            
        Returns:
            List of active order summaries
        """
        filter_criteria = OrderFilter(active_only=True)
        if account_id:
            filter_criteria.account_ids = [account_id]
        
        return await self.list_orders(filter_criteria)
    
    async def get_orders_by_symbol(self, symbol: str) -> List[OrderSummary]:
        """
        Get all orders for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of order summaries for the symbol
        """
        filter_criteria = OrderFilter(symbols=[symbol])
        return await self.list_orders(filter_criteria)
    
    async def get_orders_by_strategy(self, strategy_id: str) -> List[OrderSummary]:
        """
        Get all orders for a strategy.
        
        Args:
            strategy_id: Strategy identifier
            
        Returns:
            List of order summaries for the strategy
        """
        filter_criteria = OrderFilter(strategy_ids=[strategy_id])
        return await self.list_orders(filter_criteria)
    
    async def get_order_statistics(
        self,
        account_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        time_period: Optional[timedelta] = None
    ) -> OrderStatistics:
        """
        Get order statistics.
        
        Args:
            account_id: Optional account filter
            strategy_id: Optional strategy filter
            time_period: Optional time period (from now backwards)
            
        Returns:
            Order statistics
        """
        try:
            # Check cache first
            cache_key = f"stats:{account_id}:{strategy_id}:{time_period}"
            cached_stats = self._get_from_cache(cache_key)
            if cached_stats:
                return cached_stats
            
            # In production, this would query optimized aggregation tables
            # For now, return default statistics
            stats = OrderStatistics(
                total_orders=0,
                active_orders=0,
                completed_orders=0,
                filled_orders=0,
                cancelled_orders=0,
                rejected_orders=0,
                total_volume=Decimal("0"),
                total_commission=Decimal("0"),
                total_fees=Decimal("0"),
                average_fill_time=None,
                success_rate=0.0,
                symbol_breakdown={},
                strategy_breakdown={},
                orders_today=0,
                orders_this_week=0,
                orders_this_month=0
            )
            
            # Cache the results
            self._set_cache(cache_key, stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get order statistics: {e}")
            return OrderStatistics(
                total_orders=0, active_orders=0, completed_orders=0,
                filled_orders=0, cancelled_orders=0, rejected_orders=0,
                total_volume=Decimal("0"), total_commission=Decimal("0"),
                total_fees=Decimal("0"), average_fill_time=None,
                success_rate=0.0, symbol_breakdown={}, strategy_breakdown={},
                orders_today=0, orders_this_week=0, orders_this_month=0
            )
    
    async def get_portfolio_positions(self, account_id: Optional[str] = None) -> List[PortfolioPosition]:
        """
        Get current portfolio positions.
        
        Args:
            account_id: Optional account filter
            
        Returns:
            List of portfolio positions
        """
        try:
            # Check cache first
            cache_key = f"positions:{account_id}"
            cached_positions = self._get_from_cache(cache_key)
            if cached_positions:
                return cached_positions
            
            # In production, this would:
            # 1. Query position projections built from OrderFilled events
            # 2. Calculate current market values
            # 3. Compute unrealized P&L
            
            # For now, return empty list
            positions = []
            
            # Cache the results
            self._set_cache(cache_key, positions)
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get portfolio positions: {e}")
            return []
    
    async def get_order_history(
        self,
        order_id: UUID,
        include_events: bool = False
    ) -> Dict[str, Any]:
        """
        Get complete order history including all events.
        
        Args:
            order_id: Order identifier
            include_events: Whether to include raw events
            
        Returns:
            Order history with events and state transitions
        """
        try:
            order = await self.get_order(order_id)
            if not order:
                return {}
            
            history = {
                "order": order.to_dict(),
                "state_transitions": [],
                "fills": [fill.to_dict() for fill in order.fills],
                "broker_messages": order.broker_messages,
                "total_events": order.version
            }
            
            if include_events:
                # Get all events for this order
                events = list(self.application.events.get(order_id))
                history["events"] = [
                    {
                        "event_type": type(event).__name__,
                        "version": event.originator_version,
                        "timestamp": event.timestamp.isoformat(),
                        "data": event.__dict__
                    }
                    for event in events
                ]
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get order history for {order_id}: {e}")
            return {}
    
    async def search_orders(
        self,
        query: str,
        search_fields: Optional[List[str]] = None
    ) -> List[OrderSummary]:
        """
        Search orders by text query.
        
        Args:
            query: Search query
            search_fields: Fields to search in (symbol, account_id, strategy_id, etc.)
            
        Returns:
            List of matching order summaries
        """
        try:
            # In production, this would use full-text search on optimized indices
            # For now, return empty list
            logger.info(f"Search orders: '{query}' in fields {search_fields}")
            return []
            
        except Exception as e:
            logger.error(f"Failed to search orders: {e}")
            return []
    
    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """
        Get real-time trading metrics for monitoring.
        
        Returns:
            Real-time metrics dictionary
        """
        try:
            stats = await self.get_order_statistics()
            
            return {
                "active_orders": stats.active_orders,
                "orders_today": stats.orders_today,
                "success_rate": stats.success_rate,
                "total_volume": str(stats.total_volume),
                "avg_fill_time_seconds": stats.average_fill_time.total_seconds() if stats.average_fill_time else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "top_symbols": dict(list(stats.symbol_breakdown.items())[:5]),
                "top_strategies": dict(list(stats.strategy_breakdown.items())[:5])
            }
            
        except Exception as e:
            logger.error(f"Failed to get real-time metrics: {e}")
            return {
                "active_orders": 0,
                "orders_today": 0,
                "success_rate": 0.0,
                "total_volume": "0",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        self._cache_ttl.clear()
        logger.info("Order query cache cleared")
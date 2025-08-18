"""
Order Management System Application with Event Sourcing and CQRS.

This module provides the main application service that coordinates
command and query operations, event persistence, and integration
with external services.
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from uuid import UUID
import logging

from eventsourcing.application import Application
from eventsourcing.persistence import EventStore
from eventsourcing.popo import POPOAggregateRecorder, POPOApplicationRecorder

from .event_sourced_order import OrderAggregate
from .command_service import (
    OrderCommandService, CreateOrderCommand, ValidateOrderCommand,
    SubmitOrderCommand, ProcessFillCommand, CancelOrderCommand, CommandResult
)
from .query_service import OrderQueryService, OrderFilter, OrderSummary, OrderStatistics
from .event_store import OrderEventStore, OrderEventStoreFactory
from .risk_validator import PreTradeRiskValidator
from ...utils.logger import get_logger

logger = get_logger(__name__)


class OrderEventBus:
    """
    Event bus for real-time order event distribution.
    
    Publishes order events to subscribers for side effects like
    GUI updates, position tracking, and notifications.
    """
    
    def __init__(self):
        self.subscribers: List[Callable] = []
        
    def subscribe(self, callback: Callable):
        """Subscribe to order events."""
        self.subscribers.append(callback)
        logger.debug(f"Added event subscriber: {callback.__name__ if hasattr(callback, '__name__') else str(callback)}")
    
    def unsubscribe(self, callback: Callable):
        """Unsubscribe from order events."""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            logger.debug(f"Removed event subscriber: {callback.__name__ if hasattr(callback, '__name__') else str(callback)}")
    
    async def publish(self, event: Any):
        """Publish event to all subscribers."""
        for subscriber in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(event)
                else:
                    subscriber(event)
            except Exception as e:
                logger.error(f"Event subscriber error: {e}")


class OrderManagementApplication(Application):
    """
    Main Order Management System application.
    
    Provides a unified interface for order operations, coordinates
    command and query services, and manages event distribution.
    """
    
    def __init__(
        self,
        risk_validator: PreTradeRiskValidator,
        broker_client: Optional[Any] = None,
        persist_events: bool = True,
        env: Optional[Dict[str, Any]] = None,
        event_store: Optional[OrderEventStore] = None,
        environment: str = None
    ):
        """
        Initialize OMS application.
        
        Args:
            risk_validator: Pre-trade risk validation service
            broker_client: Optional broker API client
            persist_events: Whether to persist events (False for testing)
            env: Environment configuration
            event_store: Optional pre-configured event store
            environment: Environment name for auto-configuration
        """
        # Configure event store if not provided
        if event_store is None:
            env_name = environment or os.getenv("ENVIRONMENT", "development")
            if not persist_events:
                env_name = "test"
            event_store = OrderEventStoreFactory.create_event_store(env_name)
        
        self.event_store = event_store
        
        # Configure environment for eventsourcing application
        app_env = env or {}
        if hasattr(event_store, 'infrastructure'):
            # Use the configured event store infrastructure
            app_env.update({
                'INFRASTRUCTURE_FACTORY': lambda: event_store.infrastructure,
                'AGGREGATE_RECORDER': event_store.aggregate_recorder,
                'APPLICATION_RECORDER': event_store.application_recorder
            })
        
        # Initialize event sourcing application
        super().__init__(env=app_env)
        
        # Initialize event bus
        self.event_bus = OrderEventBus()
        
        # Initialize command service
        self.command_service = OrderCommandService(
            application=self,
            risk_validator=risk_validator,
            broker_client=broker_client
        )
        
        # Initialize query service
        self.query_service = OrderQueryService(application=self)
        
        # Add event bus as listener to command service
        self.command_service.add_event_listener(self.event_bus.publish)
        
        # Configuration
        self.persist_events = persist_events
        self.risk_validator = risk_validator
        self.broker_client = broker_client
        
        # Statistics
        self._stats = {
            "orders_created": 0,
            "orders_validated": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_rejected": 0,
            "events_processed": 0
        }
        
        logger.info("Order Management Application initialized")
    
    # Command Operations (Write Side)
    
    async def create_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        **kwargs
    ) -> CommandResult:
        """
        Create a new order.
        
        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            quantity: Order quantity
            order_type: Order type (MARKET/LIMIT/etc.)
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            **kwargs: Additional order parameters
            
        Returns:
            Command result with order ID if successful
        """
        from .order import OrderSide, OrderType
        from decimal import Decimal
        
        command = CreateOrderCommand(
            symbol=symbol.upper(),
            side=OrderSide(side.upper()),
            quantity=quantity,
            order_type=OrderType(order_type.upper()),
            limit_price=Decimal(str(limit_price)) if limit_price else None,
            stop_price=Decimal(str(stop_price)) if stop_price else None,
            **kwargs
        )
        
        result = await self.command_service.create_order(command)
        
        if result.success:
            self._stats["orders_created"] += 1
            self._stats["events_processed"] += result.events_generated
        
        return result
    
    async def validate_order(self, order_id: UUID, force_validation: bool = False) -> CommandResult:
        """
        Validate an order with risk checks.
        
        Args:
            order_id: Order identifier
            force_validation: Force re-validation if already validated
            
        Returns:
            Command result indicating validation success/failure
        """
        command = ValidateOrderCommand(order_id=order_id, force_validation=force_validation)
        result = await self.command_service.validate_order(command)
        
        if result.success:
            self._stats["orders_validated"] += 1
        else:
            self._stats["orders_rejected"] += 1
        
        self._stats["events_processed"] += result.events_generated
        
        return result
    
    async def submit_order(self, order_id: UUID, broker_order_id: Optional[str] = None) -> CommandResult:
        """
        Submit order to broker.
        
        Args:
            order_id: Order identifier
            broker_order_id: Optional broker order ID
            
        Returns:
            Command result indicating submission success/failure
        """
        command = SubmitOrderCommand(order_id=order_id, broker_order_id=broker_order_id)
        result = await self.command_service.submit_order(command)
        
        if result.success:
            self._stats["orders_submitted"] += 1
        
        self._stats["events_processed"] += result.events_generated
        
        return result
    
    async def process_fill(
        self,
        order_id: UUID,
        fill_quantity: int,
        fill_price: float,
        **kwargs
    ) -> CommandResult:
        """
        Process an order fill.
        
        Args:
            order_id: Order identifier
            fill_quantity: Quantity filled
            fill_price: Fill price
            **kwargs: Additional fill parameters
            
        Returns:
            Command result indicating fill processing success/failure
        """
        from decimal import Decimal
        
        command = ProcessFillCommand(
            order_id=order_id,
            fill_quantity=fill_quantity,
            fill_price=Decimal(str(fill_price)),
            **kwargs
        )
        
        result = await self.command_service.process_fill(command)
        
        if result.success:
            self._stats["orders_filled"] += 1
        
        self._stats["events_processed"] += result.events_generated
        
        return result
    
    async def cancel_order(self, order_id: UUID, reason: str = "", requested_by: str = "") -> CommandResult:
        """
        Cancel an order.
        
        Args:
            order_id: Order identifier
            reason: Cancellation reason
            requested_by: Who requested the cancellation
            
        Returns:
            Command result indicating cancellation success/failure
        """
        command = CancelOrderCommand(order_id=order_id, reason=reason, requested_by=requested_by)
        result = await self.command_service.cancel_order(command)
        
        if result.success:
            self._stats["orders_cancelled"] += 1
        
        self._stats["events_processed"] += result.events_generated
        
        return result
    
    # Query Operations (Read Side)
    
    async def get_order(self, order_id: UUID) -> Optional[OrderAggregate]:
        """
        Get order by ID.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order aggregate or None if not found
        """
        return await self.query_service.get_order(order_id)
    
    async def get_order_summary(self, order_id: UUID) -> Optional[OrderSummary]:
        """
        Get order summary.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order summary or None if not found
        """
        return await self.query_service.get_order_summary(order_id)
    
    async def list_orders(
        self,
        filter_criteria: Optional[OrderFilter] = None,
        limit: Optional[int] = None
    ) -> List[OrderSummary]:
        """
        List orders with optional filtering.
        
        Args:
            filter_criteria: Optional filter criteria
            limit: Maximum number of results
            
        Returns:
            List of order summaries
        """
        return await self.query_service.list_orders(filter_criteria, limit=limit)
    
    async def get_active_orders(self, account_id: Optional[str] = None) -> List[OrderSummary]:
        """
        Get all active orders.
        
        Args:
            account_id: Optional account filter
            
        Returns:
            List of active order summaries
        """
        return await self.query_service.get_active_orders(account_id)
    
    async def get_orders_by_symbol(self, symbol: str) -> List[OrderSummary]:
        """
        Get orders for a specific symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of order summaries for the symbol
        """
        return await self.query_service.get_orders_by_symbol(symbol.upper())
    
    async def get_order_statistics(
        self,
        account_id: Optional[str] = None,
        strategy_id: Optional[str] = None
    ) -> OrderStatistics:
        """
        Get order statistics.
        
        Args:
            account_id: Optional account filter
            strategy_id: Optional strategy filter
            
        Returns:
            Order statistics
        """
        return await self.query_service.get_order_statistics(account_id, strategy_id)
    
    async def get_portfolio_positions(self, account_id: Optional[str] = None):
        """
        Get current portfolio positions.
        
        Args:
            account_id: Optional account filter
            
        Returns:
            List of portfolio positions
        """
        return await self.query_service.get_portfolio_positions(account_id)
    
    async def search_orders(self, query: str) -> List[OrderSummary]:
        """
        Search orders by text query.
        
        Args:
            query: Search query
            
        Returns:
            List of matching order summaries
        """
        return await self.query_service.search_orders(query)
    
    # Full Workflow Operations
    
    async def create_and_submit_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        auto_validate: bool = True,
        auto_submit: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create, validate, and submit order in one workflow.
        
        Args:
            symbol: Trading symbol
            side: Order side
            quantity: Order quantity
            order_type: Order type
            auto_validate: Automatically validate after creation
            auto_submit: Automatically submit after validation
            **kwargs: Additional order parameters
            
        Returns:
            Workflow result with all operation results
        """
        workflow_result = {
            "create_result": None,
            "validate_result": None,
            "submit_result": None,
            "order_id": None,
            "success": False,
            "message": ""
        }
        
        try:
            # Step 1: Create order
            create_result = await self.create_order(symbol, side, quantity, order_type, **kwargs)
            workflow_result["create_result"] = create_result
            
            if not create_result.success:
                workflow_result["message"] = f"Order creation failed: {create_result.message}"
                return workflow_result
            
            order_id = create_result.order_id
            workflow_result["order_id"] = order_id
            
            # Step 2: Validate order (if requested)
            if auto_validate:
                validate_result = await self.validate_order(order_id)
                workflow_result["validate_result"] = validate_result
                
                if not validate_result.success:
                    workflow_result["message"] = f"Order validation failed: {validate_result.message}"
                    return workflow_result
                
                # Step 3: Submit order (if requested)
                if auto_submit:
                    submit_result = await self.submit_order(order_id)
                    workflow_result["submit_result"] = submit_result
                    
                    if not submit_result.success:
                        workflow_result["message"] = f"Order submission failed: {submit_result.message}"
                        return workflow_result
                    
                    workflow_result["success"] = True
                    workflow_result["message"] = "Order created, validated, and submitted successfully"
                else:
                    workflow_result["success"] = True
                    workflow_result["message"] = "Order created and validated successfully"
            else:
                workflow_result["success"] = True
                workflow_result["message"] = "Order created successfully"
            
            return workflow_result
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            workflow_result["message"] = f"Workflow error: {str(e)}"
            return workflow_result
    
    # Event and Integration Management
    
    def subscribe_to_events(self, callback: Callable):
        """
        Subscribe to order events.
        
        Args:
            callback: Event callback function
        """
        self.event_bus.subscribe(callback)
    
    def unsubscribe_from_events(self, callback: Callable):
        """
        Unsubscribe from order events.
        
        Args:
            callback: Event callback function
        """
        self.event_bus.unsubscribe(callback)
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get system status and health information.
        
        Returns:
            System status dictionary
        """
        circuit_breaker_status = await self.command_service.get_circuit_breaker_status()
        
        return {
            "application": "Order Management System",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "statistics": self._stats,
            "circuit_breaker": circuit_breaker_status,
            "event_subscribers": len(self.event_bus.subscribers),
            "query_cache_size": len(self.query_service._cache),
            "risk_validator": {
                "available": self.risk_validator is not None,
                "type": type(self.risk_validator).__name__ if self.risk_validator else None
            },
            "broker_client": {
                "available": self.broker_client is not None,
                "type": type(self.broker_client).__name__ if self.broker_client else None
            }
        }
    
    async def clear_cache(self):
        """Clear all cached data."""
        self.query_service.clear_cache()
        logger.info("OMS cache cleared")
    
    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """
        Get real-time metrics for monitoring.
        
        Returns:
            Real-time metrics dictionary
        """
        query_metrics = await self.query_service.get_real_time_metrics()
        system_status = await self.get_system_status()
        event_store_stats = self.event_store.get_event_store_statistics()
        
        return {
            **query_metrics,
            "system_stats": system_status["statistics"],
            "circuit_breaker_state": system_status["circuit_breaker"]["state"],
            "event_subscribers": system_status["event_subscribers"],
            "event_store": event_store_stats
        }
    
    # Event Store Management
    
    async def get_order_event_history(self, order_id: UUID, include_snapshots: bool = False) -> Dict[str, Any]:
        """
        Get complete event history for an order.
        
        Args:
            order_id: Order identifier
            include_snapshots: Whether to include snapshot information
            
        Returns:
            Order event history with metadata
        """
        try:
            events = self.event_store.get_order_events(order_id)
            
            history = {
                "order_id": str(order_id),
                "total_events": len(events),
                "events": []
            }
            
            for event in events:
                event_data = {
                    "version": event.originator_version,
                    "event_type": event.__class__.__name__,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.__dict__
                }
                history["events"].append(event_data)
            
            if include_snapshots:
                # Add snapshot information if requested
                history["snapshots_available"] = len(events) // 10  # Snapshots every 10 events
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get event history for order {order_id}: {e}")
            return {
                "order_id": str(order_id),
                "error": str(e)
            }
    
    async def create_order_snapshot(self, order_id: UUID) -> bool:
        """
        Create a snapshot for an order to optimize loading.
        
        Args:
            order_id: Order identifier
            
        Returns:
            True if snapshot created successfully
        """
        try:
            order = await self.get_order(order_id)
            if order:
                return self.event_store.create_snapshot(order)
            return False
        except Exception as e:
            logger.error(f"Failed to create snapshot for order {order_id}: {e}")
            return False
    
    async def replay_order_events(self, order_id: UUID, from_version: int = 0) -> Optional[OrderAggregate]:
        """
        Replay order events from a specific version.
        
        Args:
            order_id: Order identifier
            from_version: Starting version for replay
            
        Returns:
            Replayed order aggregate or None if failed
        """
        try:
            if from_version == 0:
                # Full replay from beginning
                order = self.repository.get(order_id)
            else:
                # Replay from specific version
                events = self.event_store.get_order_events_after_version(order_id, from_version)
                if not events:
                    return None
                
                # Get base order and apply events
                order = self.repository.get(order_id)
                if order and order.version >= from_version:
                    # Apply events after the specified version
                    for event in events:
                        event.mutate(order)
            
            return order
            
        except Exception as e:
            logger.error(f"Failed to replay events for order {order_id}: {e}")
            return None
    
    async def get_event_store_health(self) -> Dict[str, Any]:
        """
        Get event store health information.
        
        Returns:
            Event store health status
        """
        try:
            stats = self.event_store.get_event_store_statistics()
            
            health = {
                "status": "healthy",
                "db_type": stats.get("db_type"),
                "total_events": stats.get("total_events", 0),
                "total_snapshots": stats.get("total_snapshots", 0),
                "unique_orders": stats.get("unique_aggregates", 0),
                "latest_event": stats.get("latest_event_timestamp"),
                "connection_status": "connected"
            }
            
            # Check for potential issues
            if stats.get("total_events", 0) > 100000:
                health["warnings"] = health.get("warnings", [])
                health["warnings"].append("High event count - consider archiving old events")
            
            if stats.get("error"):
                health["status"] = "degraded"
                health["error"] = stats["error"]
            
            return health
            
        except Exception as e:
            logger.error(f"Failed to get event store health: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "connection_status": "failed"
            }
    
    async def close(self):
        """Clean shutdown of OMS application."""
        try:
            # Clear caches
            await self.clear_cache()
            
            # Close event store connections
            if self.event_store:
                self.event_store.close()
            
            logger.info("OMS application closed successfully")
            
        except Exception as e:
            logger.error(f"Error during OMS shutdown: {e}")
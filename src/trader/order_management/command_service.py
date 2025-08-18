"""
CQRS Command Service for Order Management System.

This module implements the command (write) side of CQRS pattern, handling
all order creation, validation, submission, and lifecycle commands.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Any, Callable
from uuid import UUID, uuid4
from dataclasses import dataclass
import logging

from eventsourcing.persistence import EventStore
from eventsourcing.application import Application

from .event_sourced_order import OrderAggregate
from .order import OrderType, OrderSide, TimeInForce
from .risk_validator import PreTradeRiskValidator, ValidationResult
from ...utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CreateOrderCommand:
    """Command to create a new order."""
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    trailing_amount: Optional[Decimal] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    expire_time: Optional[datetime] = None
    account_id: str = ""
    strategy_id: str = ""
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ValidateOrderCommand:
    """Command to validate an order."""
    order_id: UUID
    force_validation: bool = False


@dataclass
class SubmitOrderCommand:
    """Command to submit an order to broker."""
    order_id: UUID
    broker_order_id: Optional[str] = None


@dataclass
class ProcessFillCommand:
    """Command to process an order fill."""
    order_id: UUID
    fill_quantity: int
    fill_price: Decimal
    fill_id: Optional[str] = None
    commission: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    venue: str = ""
    contra_party: str = ""


@dataclass
class CancelOrderCommand:
    """Command to cancel an order."""
    order_id: UUID
    reason: str = ""
    requested_by: str = ""


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    order_id: Optional[UUID] = None
    message: str = ""
    error_details: Optional[Dict[str, Any]] = None
    events_generated: int = 0


class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls.
    
    Prevents cascading failures when external services (broker API) are down.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    def is_open(self) -> bool:
        """Check if circuit breaker is open (blocking calls)."""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker moving to HALF_OPEN state")
                return False
            return True
        return False
        
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True
        time_since_failure = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
        return time_since_failure >= self.recovery_timeout
        
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.is_open():
            raise RuntimeError("Circuit breaker is OPEN - service unavailable")
            
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.expected_exception as e:
            await self._on_failure()
            raise
            
    async def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = "CLOSED"
        
    async def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")


class OrderCommandService:
    """
    Command service for order management.
    
    Handles all write operations (commands) in the CQRS pattern.
    Coordinates with risk validation, broker integration, and event persistence.
    """
    
    def __init__(
        self,
        application: Application,
        risk_validator: PreTradeRiskValidator,
        broker_client: Optional[Any] = None
    ):
        """
        Initialize command service.
        
        Args:
            application: Event sourcing application for persistence
            risk_validator: Pre-trade risk validation service
            broker_client: Broker API client (optional for testing)
        """
        self.application = application
        self.risk_validator = risk_validator
        self.broker_client = broker_client
        
        # Circuit breaker for broker API calls
        self.broker_circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            expected_exception=Exception
        )
        
        # Event listeners for side effects
        self.event_listeners: List[Callable] = []
        
        logger.info("Order command service initialized")
    
    def add_event_listener(self, listener: Callable):
        """Add event listener for side effects (e.g., GUI updates)."""
        self.event_listeners.append(listener)
    
    async def _publish_events(self, order: OrderAggregate):
        """Publish events to listeners."""
        events = order.collect_events()
        for event in events:
            for listener in self.event_listeners:
                try:
                    await listener(event)
                except Exception as e:
                    logger.error(f"Event listener error: {e}")
    
    async def create_order(self, command: CreateOrderCommand) -> CommandResult:
        """
        Create a new order.
        
        Args:
            command: Order creation command
            
        Returns:
            CommandResult with order ID if successful
        """
        try:
            # Create order aggregate
            order = OrderAggregate(
                symbol=command.symbol,
                side=command.side,
                quantity=command.quantity,
                order_type=command.order_type,
                limit_price=command.limit_price,
                stop_price=command.stop_price,
                trailing_amount=command.trailing_amount,
                time_in_force=command.time_in_force,
                expire_time=command.expire_time,
                account_id=command.account_id,
                strategy_id=command.strategy_id,
                tags=command.tags,
                metadata=command.metadata
            )
            
            # Save aggregate (persists OrderCreated event)
            self.application.save(order)
            
            # Publish events for side effects
            await self._publish_events(order)
            
            logger.info(f"Created order {order.id}: {command.side} {command.quantity} {command.symbol}")
            
            return CommandResult(
                success=True,
                order_id=order.id,
                message=f"Order created successfully",
                events_generated=1
            )
            
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to create order: {str(e)}",
                error_details={"exception": str(e), "command": command.__dict__}
            )
    
    async def validate_order(self, command: ValidateOrderCommand) -> CommandResult:
        """
        Validate order with pre-trade risk checks.
        
        Args:
            command: Order validation command
            
        Returns:
            CommandResult indicating validation success/failure
        """
        try:
            # Load order aggregate
            order: OrderAggregate = self.application.repository.get(command.order_id)
            if not order:
                return CommandResult(
                    success=False,
                    message=f"Order {command.order_id} not found"
                )
            
            # Check if already validated
            if order.state.value != "NEW" and not command.force_validation:
                return CommandResult(
                    success=False,
                    message=f"Order {command.order_id} already validated or in state {order.state}"
                )
            
            # Run risk validation
            validation_result = await self.risk_validator.validate_order(order)
            
            # Process validation result
            if validation_result.passed:
                # Validation passed - emit OrderValidated event
                order.validate(validation_result.to_dict())
                self.application.save(order)
                
                await self._publish_events(order)
                
                logger.info(f"Order {command.order_id} validated successfully")
                
                return CommandResult(
                    success=True,
                    order_id=order.id,
                    message="Order validated successfully",
                    events_generated=1
                )
            else:
                # Validation failed - emit OrderRejected event
                reasons = validation_result.get_failure_reasons()
                order.reject(
                    reason=f"Risk validation failed: {reasons}",
                    error_details=validation_result.to_dict()
                )
                self.application.save(order)
                
                await self._publish_events(order)
                
                logger.warning(f"Order {command.order_id} rejected: {reasons}")
                
                return CommandResult(
                    success=False,
                    order_id=order.id,
                    message=f"Order rejected: {reasons}",
                    error_details=validation_result.to_dict(),
                    events_generated=1
                )
                
        except Exception as e:
            logger.error(f"Failed to validate order {command.order_id}: {e}")
            return CommandResult(
                success=False,
                message=f"Validation error: {str(e)}",
                error_details={"exception": str(e)}
            )
    
    async def submit_order(self, command: SubmitOrderCommand) -> CommandResult:
        """
        Submit order to broker.
        
        Args:
            command: Order submission command
            
        Returns:
            CommandResult indicating submission success/failure
        """
        try:
            # Load order aggregate
            order: OrderAggregate = self.application.repository.get(command.order_id)
            if not order:
                return CommandResult(
                    success=False,
                    message=f"Order {command.order_id} not found"
                )
            
            # Check if order can be submitted
            if order.state.value != "VALIDATED":
                return CommandResult(
                    success=False,
                    message=f"Cannot submit order in state {order.state}"
                )
            
            # Submit to broker with circuit breaker protection
            broker_order_id = command.broker_order_id
            
            if self.broker_client and not broker_order_id:
                try:
                    broker_order_id = await self.broker_circuit_breaker.call(
                        self.broker_client.submit_order, order.to_dict()
                    )
                except RuntimeError as e:
                    # Circuit breaker is open
                    order.reject(
                        reason="Broker service unavailable (circuit breaker open)",
                        error_details={"circuit_breaker": str(e)}
                    )
                    self.application.save(order)
                    await self._publish_events(order)
                    
                    return CommandResult(
                        success=False,
                        order_id=order.id,
                        message="Broker service unavailable",
                        error_details={"circuit_breaker": str(e)},
                        events_generated=1
                    )
                except Exception as e:
                    # Broker submission failed
                    order.reject(
                        reason=f"Broker submission failed: {str(e)}",
                        error_details={"broker_error": str(e)}
                    )
                    self.application.save(order)
                    await self._publish_events(order)
                    
                    return CommandResult(
                        success=False,
                        order_id=order.id,
                        message=f"Broker submission failed: {str(e)}",
                        error_details={"broker_error": str(e)},
                        events_generated=1
                    )
            else:
                # Use provided broker order ID or generate placeholder
                broker_order_id = broker_order_id or f"BROKER-{order.id}"
            
            # Submit order (emit OrderSubmitted event)
            order.submit(broker_order_id, "SUBMITTED")
            self.application.save(order)
            
            # Simulate broker acknowledgment for testing
            # In production, this would come from broker API callback
            if not self.broker_client:
                order.acknowledge("PENDING")
                self.application.save(order)
            
            await self._publish_events(order)
            
            logger.info(f"Order {command.order_id} submitted to broker as {broker_order_id}")
            
            return CommandResult(
                success=True,
                order_id=order.id,
                message=f"Order submitted successfully (broker ID: {broker_order_id})",
                events_generated=2 if not self.broker_client else 1
            )
            
        except Exception as e:
            logger.error(f"Failed to submit order {command.order_id}: {e}")
            return CommandResult(
                success=False,
                message=f"Submission error: {str(e)}",
                error_details={"exception": str(e)}
            )
    
    async def process_fill(self, command: ProcessFillCommand) -> CommandResult:
        """
        Process an order fill.
        
        Args:
            command: Fill processing command
            
        Returns:
            CommandResult indicating fill processing success/failure
        """
        try:
            # Load order aggregate
            order: OrderAggregate = self.application.repository.get(command.order_id)
            if not order:
                return CommandResult(
                    success=False,
                    message=f"Order {command.order_id} not found"
                )
            
            # Validate fill can be processed
            if order.state.value not in ["PENDING", "PARTIALLY_FILLED"]:
                return CommandResult(
                    success=False,
                    message=f"Cannot process fill for order in state {order.state}"
                )
            
            if command.fill_quantity > order.remaining_quantity:
                return CommandResult(
                    success=False,
                    message=f"Fill quantity {command.fill_quantity} exceeds remaining {order.remaining_quantity}"
                )
            
            # Process fill (emit OrderFilled event)
            order.add_fill(
                fill_quantity=command.fill_quantity,
                fill_price=command.fill_price,
                fill_id=command.fill_id,
                commission=command.commission,
                fees=command.fees,
                venue=command.venue,
                contra_party=command.contra_party
            )
            
            self.application.save(order)
            await self._publish_events(order)
            
            fill_type = "Full" if order.remaining_quantity == 0 else "Partial"
            logger.info(f"{fill_type} fill processed for order {command.order_id}: {command.fill_quantity} @ {command.fill_price}")
            
            return CommandResult(
                success=True,
                order_id=order.id,
                message=f"{fill_type} fill processed successfully",
                events_generated=1
            )
            
        except Exception as e:
            logger.error(f"Failed to process fill for order {command.order_id}: {e}")
            return CommandResult(
                success=False,
                message=f"Fill processing error: {str(e)}",
                error_details={"exception": str(e)}
            )
    
    async def cancel_order(self, command: CancelOrderCommand) -> CommandResult:
        """
        Cancel an order.
        
        Args:
            command: Order cancellation command
            
        Returns:
            CommandResult indicating cancellation success/failure
        """
        try:
            # Load order aggregate
            order: OrderAggregate = self.application.repository.get(command.order_id)
            if not order:
                return CommandResult(
                    success=False,
                    message=f"Order {command.order_id} not found"
                )
            
            # Check if order can be cancelled
            if not order.is_active:
                return CommandResult(
                    success=False,
                    message=f"Cannot cancel order in state {order.state}"
                )
            
            # Cancel with broker if needed
            if self.broker_client and order.broker_order_id:
                try:
                    await self.broker_circuit_breaker.call(
                        self.broker_client.cancel_order, order.broker_order_id
                    )
                except Exception as e:
                    logger.warning(f"Broker cancellation failed for {order.broker_order_id}: {e}")
                    # Continue with local cancellation even if broker fails
            
            # Cancel order (emit OrderCancelled event)
            order.cancel(command.reason, command.requested_by)
            self.application.save(order)
            
            await self._publish_events(order)
            
            logger.info(f"Order {command.order_id} cancelled: {command.reason}")
            
            return CommandResult(
                success=True,
                order_id=order.id,
                message=f"Order cancelled successfully",
                events_generated=1
            )
            
        except Exception as e:
            logger.error(f"Failed to cancel order {command.order_id}: {e}")
            return CommandResult(
                success=False,
                message=f"Cancellation error: {str(e)}",
                error_details={"exception": str(e)}
            )
    
    async def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for monitoring."""
        return {
            "state": self.broker_circuit_breaker.state,
            "failure_count": self.broker_circuit_breaker.failure_count,
            "last_failure_time": self.broker_circuit_breaker.last_failure_time.isoformat() if self.broker_circuit_breaker.last_failure_time else None,
            "failure_threshold": self.broker_circuit_breaker.failure_threshold,
            "recovery_timeout": self.broker_circuit_breaker.recovery_timeout
        }
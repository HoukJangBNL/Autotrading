"""
Event-sourced Order aggregate implementation with CQRS pattern.

This module provides the event-sourced Order aggregate that captures all 
order lifecycle changes as immutable events for complete audit trail and replay capability.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from enum import Enum

from eventsourcing.domain import Aggregate, event

# Import existing enums and value objects
from .order import OrderState, OrderType, OrderSide, TimeInForce, Fill


class OrderAggregate(Aggregate):
    """
    Event-sourced Order aggregate with immutable state and complete audit trail.
    
    This aggregate captures all order lifecycle changes as events, enabling:
    - Complete audit trail of all order changes
    - Replay capability for debugging and testing  
    - Real-time event streaming for GUI and integrations
    - CQRS pattern for scalable order processing
    """

    @event('OrderCreated')
    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        trailing_amount: Optional[Decimal] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        expire_time: Optional[datetime] = None,
        account_id: str = "",
        strategy_id: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Create a new order aggregate.
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL')
            side: Order side (BUY, SELL, etc.)
            quantity: Number of shares/units
            order_type: Type of order (MARKET, LIMIT, etc.)
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            trailing_amount: Trailing amount for trailing stops
            time_in_force: Order duration (DAY, GTC, etc.)
            expire_time: Expiration time for GTD orders
            account_id: Trading account identifier
            strategy_id: Strategy that created this order
            tags: List of tags for categorization
            metadata: Additional metadata
        """
        # Validate required fields
        if not symbol:
            raise ValueError("Symbol is required")
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive: {quantity}")
        
        # Validate order type specific requirements
        if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and not limit_price:
            raise ValueError(f"Limit price required for {order_type} orders")
        
        if order_type in [OrderType.STOP, OrderType.STOP_LIMIT, OrderType.TRAILING_STOP] and not stop_price:
            if order_type != OrderType.TRAILING_STOP or not trailing_amount:
                raise ValueError(f"Stop price or trailing amount required for {order_type} orders")
        
        # Initialize immutable order properties
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.order_type = order_type
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.trailing_amount = trailing_amount
        self.time_in_force = time_in_force
        self.expire_time = expire_time
        self.account_id = account_id
        self.strategy_id = strategy_id
        self.tags = tags or []
        self.metadata = metadata or {}
        
        # Initialize mutable state
        self.state = OrderState.NEW
        self.fills: List[Fill] = []
        self.filled_quantity = 0
        self.remaining_quantity = quantity
        self.average_fill_price = Decimal("0")
        self.total_commission = Decimal("0")
        self.total_fees = Decimal("0")
        
        # Broker information
        self.broker_order_id: Optional[str] = None
        self.broker_status: Optional[str] = None
        self.broker_messages: List[str] = []
        
        # Risk check results
        self.risk_check_results: Dict[str, Any] = {}
        
        # Timestamps
        self.created_at = datetime.now(timezone.utc)
        self.submitted_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    class OrderCreated(Aggregate.Created):
        """Event emitted when an order is created."""
        symbol: str
        side: OrderSide
        quantity: int
        order_type: OrderType
        limit_price: Optional[Decimal]
        stop_price: Optional[Decimal]
        trailing_amount: Optional[Decimal]
        time_in_force: TimeInForce
        expire_time: Optional[datetime]
        account_id: str
        strategy_id: str
        tags: List[str]
        metadata: Dict[str, Any]

    @event('OrderValidated')
    def validate(self, risk_check_results: Dict[str, Any]) -> None:
        """
        Validate order with risk check results.
        
        Args:
            risk_check_results: Results from pre-trade risk validation
            
        Raises:
            ValueError: If order is not in NEW state
        """
        if self.state != OrderState.NEW:
            raise ValueError(f"Cannot validate order in state {self.state}")
        
        self.state = OrderState.VALIDATED
        self.risk_check_results = risk_check_results

    class OrderValidated(Aggregate.Event):
        """Event emitted when an order passes validation."""
        risk_check_results: Dict[str, Any]

        def apply(self, aggregate: 'OrderAggregate') -> None:
            aggregate.state = OrderState.VALIDATED
            aggregate.risk_check_results = self.risk_check_results

    @event('OrderRejected')
    def reject(self, reason: str, error_details: Optional[Dict[str, Any]] = None) -> None:
        """
        Reject order due to validation failure or other reasons.
        
        Args:
            reason: Rejection reason
            error_details: Additional error information
        """
        self.state = OrderState.REJECTED
        self.completed_at = datetime.now(timezone.utc)
        self.broker_messages.append(f"Rejected: {reason}")
        if error_details:
            self.metadata.update({"rejection_details": error_details})

    class OrderRejected(Aggregate.Event):
        """Event emitted when an order is rejected."""
        reason: str
        error_details: Optional[Dict[str, Any]]

        def apply(self, aggregate: 'OrderAggregate') -> None:
            aggregate.state = OrderState.REJECTED
            aggregate.completed_at = self.timestamp
            aggregate.broker_messages.append(f"Rejected: {self.reason}")
            if self.error_details:
                aggregate.metadata.update({"rejection_details": self.error_details})

    @event('OrderSubmitted')
    def submit(self, broker_order_id: str, broker_status: Optional[str] = None) -> None:
        """
        Submit order to broker.
        
        Args:
            broker_order_id: Broker's order identifier
            broker_status: Initial broker status
            
        Raises:
            ValueError: If order is not in VALIDATED state
        """
        if self.state != OrderState.VALIDATED:
            raise ValueError(f"Cannot submit order in state {self.state}")
        
        self.state = OrderState.SUBMITTED
        self.broker_order_id = broker_order_id
        self.broker_status = broker_status
        self.submitted_at = datetime.now(timezone.utc)

    class OrderSubmitted(Aggregate.Event):
        """Event emitted when an order is submitted to broker."""
        broker_order_id: str
        broker_status: Optional[str]

        def apply(self, aggregate: 'OrderAggregate') -> None:
            aggregate.state = OrderState.SUBMITTED
            aggregate.broker_order_id = self.broker_order_id
            aggregate.broker_status = self.broker_status
            aggregate.submitted_at = self.timestamp

    @event('OrderAcknowledged')
    def acknowledge(self, broker_status: Optional[str] = None) -> None:
        """
        Acknowledge order acceptance by broker.
        
        Args:
            broker_status: Updated broker status
            
        Raises:
            ValueError: If order is not in SUBMITTED state
        """
        if self.state != OrderState.SUBMITTED:
            raise ValueError(f"Cannot acknowledge order in state {self.state}")
        
        self.state = OrderState.PENDING
        if broker_status:
            self.broker_status = broker_status

    class OrderAcknowledged(Aggregate.Event):
        """Event emitted when broker acknowledges order."""
        broker_status: Optional[str]

        def apply(self, aggregate: 'OrderAggregate') -> None:
            aggregate.state = OrderState.PENDING
            if self.broker_status:
                aggregate.broker_status = self.broker_status

    @event('OrderFilled')
    def add_fill(
        self,
        fill_quantity: int,
        fill_price: Decimal,
        fill_id: Optional[str] = None,
        commission: Decimal = Decimal("0"),
        fees: Decimal = Decimal("0"),
        venue: str = "",
        contra_party: str = ""
    ) -> None:
        """
        Add a fill (partial or complete) to the order.
        
        Args:
            fill_quantity: Quantity filled
            fill_price: Price of fill
            fill_id: Unique fill identifier
            commission: Commission charged
            fees: Additional fees
            venue: Trading venue
            contra_party: Counterparty identifier
            
        Raises:
            ValueError: If fill quantity exceeds remaining quantity or invalid state
        """
        if self.state not in [OrderState.PENDING, OrderState.PARTIALLY_FILLED]:
            raise ValueError(f"Cannot add fill to order in state {self.state}")
        
        if fill_quantity > self.remaining_quantity:
            raise ValueError(f"Fill quantity {fill_quantity} exceeds remaining {self.remaining_quantity}")
        
        # Create fill object
        fill = Fill(
            fill_id=fill_id or f"FILL-{self.id}-{len(self.fills) + 1}",
            timestamp=datetime.now(timezone.utc),
            quantity=fill_quantity,
            price=fill_price,
            commission=commission,
            fees=fees,
            venue=venue,
            contra_party=contra_party
        )
        
        # Update fill tracking
        self.fills.append(fill)
        self.filled_quantity += fill_quantity
        self.remaining_quantity -= fill_quantity
        
        # Update average fill price (weighted average)
        total_value = sum(f.price * f.quantity for f in self.fills)
        self.average_fill_price = total_value / self.filled_quantity if self.filled_quantity > 0 else Decimal("0")
        
        # Update commission and fees
        self.total_commission += commission
        self.total_fees += fees
        
        # Update state based on remaining quantity
        if self.remaining_quantity == 0:
            self.state = OrderState.FILLED
            self.completed_at = datetime.now(timezone.utc)
        else:
            self.state = OrderState.PARTIALLY_FILLED

    class OrderFilled(Aggregate.Event):
        """Event emitted when an order receives a fill."""
        fill_quantity: int
        fill_price: Decimal
        fill_id: Optional[str]
        commission: Decimal
        fees: Decimal
        venue: str
        contra_party: str

        def apply(self, aggregate: 'OrderAggregate') -> None:
            # Create fill object
            fill = Fill(
                fill_id=self.fill_id or f"FILL-{aggregate.id}-{len(aggregate.fills) + 1}",
                timestamp=self.timestamp,
                quantity=self.fill_quantity,
                price=self.fill_price,
                commission=self.commission,
                fees=self.fees,
                venue=self.venue,
                contra_party=self.contra_party
            )
            
            # Update aggregate state
            aggregate.fills.append(fill)
            aggregate.filled_quantity += self.fill_quantity
            aggregate.remaining_quantity -= self.fill_quantity
            
            # Update average fill price
            total_value = sum(f.price * f.quantity for f in aggregate.fills)
            aggregate.average_fill_price = total_value / aggregate.filled_quantity if aggregate.filled_quantity > 0 else Decimal("0")
            
            # Update commission and fees
            aggregate.total_commission += self.commission
            aggregate.total_fees += self.fees
            
            # Update state
            if aggregate.remaining_quantity == 0:
                aggregate.state = OrderState.FILLED
                aggregate.completed_at = self.timestamp
            else:
                aggregate.state = OrderState.PARTIALLY_FILLED

    @event('OrderCancelled')
    def cancel(self, reason: str = "", requested_by: str = "") -> None:
        """
        Cancel order.
        
        Args:
            reason: Cancellation reason
            requested_by: Who requested the cancellation
            
        Raises:
            ValueError: If order cannot be cancelled in current state
        """
        if not self.is_active:
            raise ValueError(f"Cannot cancel order in state {self.state}")
        
        self.state = OrderState.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
        self.broker_messages.append(f"Cancelled: {reason}" if reason else "Cancelled")

    class OrderCancelled(Aggregate.Event):
        """Event emitted when an order is cancelled."""
        reason: str
        requested_by: str

        def apply(self, aggregate: 'OrderAggregate') -> None:
            aggregate.state = OrderState.CANCELLED
            aggregate.completed_at = self.timestamp
            message = f"Cancelled: {self.reason}" if self.reason else "Cancelled"
            aggregate.broker_messages.append(message)

    @event('OrderExpired')
    def expire(self, reason: str = "Time in force expired") -> None:
        """
        Mark order as expired.
        
        Args:
            reason: Expiration reason
        """
        if self.state not in [OrderState.PENDING, OrderState.PARTIALLY_FILLED]:
            raise ValueError(f"Cannot expire order in state {self.state}")
        
        self.state = OrderState.EXPIRED
        self.completed_at = datetime.now(timezone.utc)
        self.broker_messages.append(f"Expired: {reason}")

    class OrderExpired(Aggregate.Event):
        """Event emitted when an order expires."""
        reason: str

        def apply(self, aggregate: 'OrderAggregate') -> None:
            aggregate.state = OrderState.EXPIRED
            aggregate.completed_at = self.timestamp
            aggregate.broker_messages.append(f"Expired: {self.reason}")

    # Properties and utility methods
    
    @property
    def is_active(self) -> bool:
        """Check if order is in an active state."""
        return self.state in [
            OrderState.NEW,
            OrderState.VALIDATED,
            OrderState.SUBMITTED,
            OrderState.PENDING,
            OrderState.PARTIALLY_FILLED
        ]

    @property
    def is_complete(self) -> bool:
        """Check if order is in a terminal state."""
        return self.state in [
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.REJECTED,
            OrderState.EXPIRED
        ]

    @property
    def executed_value(self) -> Decimal:
        """Calculate total executed value (price * quantity)."""
        return sum(fill.price * fill.quantity for fill in self.fills)

    @property
    def total_cost(self) -> Decimal:
        """Calculate total cost including commission and fees."""
        return self.executed_value + self.total_commission + self.total_fees

    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary for serialization."""
        return {
            'order_id': str(self.id),
            'version': self.version,
            'account_id': self.account_id,
            'strategy_id': self.strategy_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'limit_price': str(self.limit_price) if self.limit_price else None,
            'stop_price': str(self.stop_price) if self.stop_price else None,
            'trailing_amount': str(self.trailing_amount) if self.trailing_amount else None,
            'time_in_force': self.time_in_force.value,
            'expire_time': self.expire_time.isoformat() if self.expire_time else None,
            'state': self.state.value,
            'fills': [f.to_dict() for f in self.fills],
            'filled_quantity': self.filled_quantity,
            'remaining_quantity': self.remaining_quantity,
            'average_fill_price': str(self.average_fill_price),
            'total_commission': str(self.total_commission),
            'total_fees': str(self.total_fees),
            'broker_order_id': self.broker_order_id,
            'broker_status': self.broker_status,
            'broker_messages': self.broker_messages,
            'risk_check_results': self.risk_check_results,
            'created_at': self.created_at.isoformat(),
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'tags': self.tags,
            'metadata': self.metadata,
            'is_active': self.is_active,
            'is_complete': self.is_complete,
            'executed_value': str(self.executed_value),
            'total_cost': str(self.total_cost)
        }
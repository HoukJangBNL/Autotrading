"""
Order data model with comprehensive tracking of order lifecycle.

This module defines the Order class and related enums for the OMS.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid
from copy import deepcopy


class OrderState(str, Enum):
    """Order lifecycle states."""
    NEW = "NEW"
    VALIDATED = "VALIDATED"
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderType(str, Enum):
    """Supported order types."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"
    MOC = "MOC"  # Market on Close
    LOC = "LOC"  # Limit on Close


class OrderSide(str, Enum):
    """Order side (direction)."""
    BUY = "BUY"
    SELL = "SELL"
    SELL_SHORT = "SELL_SHORT"
    BUY_TO_COVER = "BUY_TO_COVER"


class TimeInForce(str, Enum):
    """Order time in force."""
    DAY = "DAY"
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    GTD = "GTD"  # Good Till Date
    MOO = "MOO"  # Market on Open
    MOC = "MOC"  # Market on Close


@dataclass
class Fill:
    """Represents a partial or complete order fill."""
    fill_id: str
    timestamp: datetime
    quantity: int
    price: Decimal
    commission: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    venue: str = ""
    contra_party: str = ""
    
    @property
    def total_cost(self) -> Decimal:
        """Calculate total cost including commission and fees."""
        return (self.price * self.quantity) + self.commission + self.fees
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'fill_id': self.fill_id,
            'timestamp': self.timestamp.isoformat(),
            'quantity': self.quantity,
            'price': str(self.price),
            'commission': str(self.commission),
            'fees': str(self.fees),
            'venue': self.venue,
            'contra_party': self.contra_party
        }


@dataclass
class StateTransition:
    """Records a state transition with metadata."""
    from_state: OrderState
    to_state: OrderState
    timestamp: datetime
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'from_state': self.from_state.value,
            'to_state': self.to_state.value,
            'timestamp': self.timestamp.isoformat(),
            'reason': self.reason,
            'metadata': self.metadata
        }


@dataclass
class Order:
    """
    Comprehensive order representation with full lifecycle tracking.
    
    This class is designed to be mostly immutable with only specific
    fields that can change during the order lifecycle.
    """
    # Immutable identification fields
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    strategy_id: str = ""
    
    # Order details (immutable after creation)
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: int = 0
    
    # Price fields (immutable after creation)
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    trailing_amount: Optional[Decimal] = None  # For trailing stops
    
    # Time constraints (immutable after creation)
    time_in_force: TimeInForce = TimeInForce.DAY
    expire_time: Optional[datetime] = None
    
    # State tracking (mutable)
    state: OrderState = field(default=OrderState.NEW)
    state_history: List[StateTransition] = field(default_factory=list)
    
    # Execution tracking (mutable)
    fills: List[Fill] = field(default_factory=list)
    filled_quantity: int = 0
    remaining_quantity: int = 0
    average_fill_price: Decimal = Decimal("0")
    total_commission: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    
    # Broker information (mutable)
    broker_order_id: Optional[str] = None
    broker_status: Optional[str] = None
    broker_messages: List[str] = field(default_factory=list)
    
    # Risk checks (set during validation)
    risk_check_results: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize calculated fields."""
        self.remaining_quantity = self.quantity
        
        # Validate order parameters
        if self.quantity <= 0:
            raise ValueError(f"Order quantity must be positive: {self.quantity}")
        
        if self.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and not self.limit_price:
            raise ValueError(f"Limit price required for {self.order_type} orders")
        
        if self.order_type in [OrderType.STOP, OrderType.STOP_LIMIT, OrderType.TRAILING_STOP] and not self.stop_price:
            if self.order_type != OrderType.TRAILING_STOP or not self.trailing_amount:
                raise ValueError(f"Stop price or trailing amount required for {self.order_type} orders")
    
    def add_fill(self, fill: Fill) -> None:
        """
        Add a fill to the order and update tracking fields.
        
        Args:
            fill: Fill information
            
        Raises:
            ValueError: If fill would exceed order quantity
        """
        if self.state not in [OrderState.PENDING, OrderState.PARTIALLY_FILLED]:
            raise ValueError(f"Cannot add fill to order in state {self.state}")
        
        if fill.quantity > self.remaining_quantity:
            raise ValueError(
                f"Fill quantity {fill.quantity} exceeds remaining quantity {self.remaining_quantity}"
            )
        
        # Add fill
        self.fills.append(fill)
        
        # Update quantities
        self.filled_quantity += fill.quantity
        self.remaining_quantity -= fill.quantity
        
        # Update average price (weighted average)
        total_value = sum(f.price * f.quantity for f in self.fills)
        self.average_fill_price = total_value / self.filled_quantity if self.filled_quantity > 0 else Decimal("0")
        
        # Update commission and fees
        self.total_commission += fill.commission
        self.total_fees += fill.fees
        
        # Update state if fully filled
        if self.remaining_quantity == 0:
            self.state = OrderState.FILLED
            self.completed_at = datetime.now(timezone.utc)
        else:
            self.state = OrderState.PARTIALLY_FILLED
    
    def update_state(self, new_state: OrderState, reason: str = "", metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Update order state with history tracking.
        
        Args:
            new_state: New state
            reason: Reason for state change
            metadata: Additional metadata
        """
        if metadata is None:
            metadata = {}
        
        # Record transition
        transition = StateTransition(
            from_state=self.state,
            to_state=new_state,
            timestamp=datetime.now(timezone.utc),
            reason=reason,
            metadata=metadata
        )
        self.state_history.append(transition)
        
        # Update state
        self.state = new_state
        
        # Update timestamps
        if new_state == OrderState.SUBMITTED:
            self.submitted_at = datetime.now(timezone.utc)
        elif new_state in [OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED, OrderState.EXPIRED]:
            self.completed_at = datetime.now(timezone.utc)
    
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
    
    def _update_state(self, event=None):
        """Update state from transitions library string to OrderState enum."""
        # This is called after state transitions by the state machine
        if hasattr(self, 'state') and isinstance(self.state, str):
            old_state = None
            if self.state_history:
                old_state = self.state_history[-1].to_state
            
            self.state = OrderState(self.state)
            
            # Record state transition if it's actually different
            if old_state and old_state != self.state:
                transition = StateTransition(
                    from_state=old_state,
                    to_state=self.state,
                    timestamp=datetime.now(timezone.utc)
                )
                self.state_history.append(transition)
    
    # State machine callbacks
    def _on_enter_new(self, event):
        """Called when entering NEW state."""
        pass
    
    def _on_enter_validated(self, event):
        """Called when entering VALIDATED state."""
        pass
    
    def _on_enter_submitted(self, event):
        """Called when entering SUBMITTED state."""
        self.submitted_at = datetime.now(timezone.utc)
    
    def _on_enter_pending(self, event):
        """Called when entering PENDING state."""
        pass
    
    def _on_enter_partially_filled(self, event):
        """Called when entering PARTIALLY_FILLED state."""
        pass
    
    def _on_enter_filled(self, event):
        """Called when entering FILLED state."""
        self.completed_at = datetime.now(timezone.utc)
    
    def _on_enter_cancelled(self, event):
        """Called when entering CANCELLED state."""
        self.completed_at = datetime.now(timezone.utc)
    
    def _on_enter_rejected(self, event):
        """Called when entering REJECTED state."""
        self.completed_at = datetime.now(timezone.utc)
    
    def _on_enter_expired(self, event):
        """Called when entering EXPIRED state."""
        self.completed_at = datetime.now(timezone.utc)
    
    # Trigger callbacks for OrderService
    def _trigger_callback_new(self, event):
        """Trigger callback for NEW state."""
        if hasattr(self, '_callbacks') and 'on_new' in self._callbacks:
            self._callbacks['on_new'](self, event)
    
    def _trigger_callback_validated(self, event):
        """Trigger callback for VALIDATED state."""
        if hasattr(self, '_callbacks') and 'on_validated' in self._callbacks:
            self._callbacks['on_validated'](self, event)
    
    def _trigger_callback_submitted(self, event):
        """Trigger callback for SUBMITTED state."""
        if hasattr(self, '_callbacks') and 'on_submitted' in self._callbacks:
            self._callbacks['on_submitted'](self, event)
    
    def _trigger_callback_pending(self, event):
        """Trigger callback for PENDING state."""
        if hasattr(self, '_callbacks') and 'on_pending' in self._callbacks:
            self._callbacks['on_pending'](self, event)
    
    def _trigger_callback_partially_filled(self, event):
        """Trigger callback for PARTIALLY_FILLED state."""
        if hasattr(self, '_callbacks') and 'on_partially_filled' in self._callbacks:
            self._callbacks['on_partially_filled'](self, event)
    
    def _trigger_callback_filled(self, event):
        """Trigger callback for FILLED state."""
        if hasattr(self, '_callbacks') and 'on_filled' in self._callbacks:
            self._callbacks['on_filled'](self, event)
    
    def _trigger_callback_cancelled(self, event):
        """Trigger callback for CANCELLED state."""
        if hasattr(self, '_callbacks') and 'on_cancelled' in self._callbacks:
            self._callbacks['on_cancelled'](self, event)
    
    def _trigger_callback_rejected(self, event):
        """Trigger callback for REJECTED state."""
        if hasattr(self, '_callbacks') and 'on_rejected' in self._callbacks:
            self._callbacks['on_rejected'](self, event)
    
    def _trigger_callback_expired(self, event):
        """Trigger callback for EXPIRED state."""
        if hasattr(self, '_callbacks') and 'on_expired' in self._callbacks:
            self._callbacks['on_expired'](self, event)
    
    # Before transition callbacks
    def _before_validate(self, event):
        """Called before validation transition."""
        pass
    
    def _before_submit(self, event):
        """Called before submission transition."""
        pass
    
    def _before_acknowledge(self, event):
        """Called before acknowledgment transition."""
        if hasattr(self, '_machine'):
            broker_order_id = self._machine._transition_metadata.get('broker_order_id')
            if broker_order_id:
                self.broker_order_id = broker_order_id
    
    def _before_fill(self, event):
        """Called before fill transition."""
        if hasattr(self, '_machine'):
            fill = self._machine._transition_metadata.get('fill')
            if fill:
                self.add_fill(fill)
    
    def _before_partial_fill(self, event):
        """Called before partial fill transition."""
        if hasattr(self, '_machine'):
            fill = self._machine._transition_metadata.get('fill')
            if fill:
                self.add_fill(fill)
    
    def _before_cancel(self, event):
        """Called before cancellation transition."""
        pass
    
    def _before_reject(self, event):
        """Called before rejection transition."""
        if hasattr(self, '_machine'):
            reason = self._machine._transition_metadata.get('reason', 'Unknown')
            self.broker_messages.append(f"Rejected: {reason}")
    
    def _before_expire(self, event):
        """Called before expiration transition."""
        pass
    
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
            'order_id': self.order_id,
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
            'state_history': [t.to_dict() for t in self.state_history],
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
            'metadata': self.metadata
        }
    
    def clone(self) -> 'Order':
        """Create a deep copy of the order."""
        return deepcopy(self)
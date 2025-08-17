"""
Order Service with state machine implementation for order lifecycle management.

This module provides the main order management service with state transitions,
validation, and broker integration.
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone
from decimal import Decimal
import logging

from transitions import Machine
from transitions.extensions import AsyncMachine

from .order import Order, OrderState, OrderType, OrderSide, Fill
from .risk_validator import PreTradeRiskValidator, ValidationResult
from ...utils.logger import get_logger

logger = get_logger(__name__)


class OrderStateMachine:
    """
    State machine for order lifecycle management.
    
    Handles all state transitions with proper validation and callbacks.
    """
    
    states = [
        {'name': OrderState.NEW, 'on_enter': ['_on_enter_new', '_trigger_callback_new']},
        {'name': OrderState.VALIDATED, 'on_enter': ['_on_enter_validated', '_trigger_callback_validated']},
        {'name': OrderState.SUBMITTED, 'on_enter': ['_on_enter_submitted', '_trigger_callback_submitted']},
        {'name': OrderState.PENDING, 'on_enter': ['_on_enter_pending', '_trigger_callback_pending']},
        {'name': OrderState.PARTIALLY_FILLED, 'on_enter': ['_on_enter_partially_filled', '_trigger_callback_partially_filled']},
        {'name': OrderState.FILLED, 'on_enter': ['_on_enter_filled', '_trigger_callback_filled']},
        {'name': OrderState.CANCELLED, 'on_enter': ['_on_enter_cancelled', '_trigger_callback_cancelled']},
        {'name': OrderState.REJECTED, 'on_enter': ['_on_enter_rejected', '_trigger_callback_rejected']},
        {'name': OrderState.EXPIRED, 'on_enter': ['_on_enter_expired', '_trigger_callback_expired']}
    ]
    
    transitions = [
        # Validation flow
        {
            'trigger': 'validate',
            'source': OrderState.NEW,
            'dest': OrderState.VALIDATED,
            'before': '_before_validate'
        },
        
        # Submission flow
        {
            'trigger': 'submit',
            'source': OrderState.VALIDATED,
            'dest': OrderState.SUBMITTED,
            'before': '_before_submit'
        },
        
        # Broker acknowledgment
        {
            'trigger': 'acknowledge',
            'source': OrderState.SUBMITTED,
            'dest': OrderState.PENDING,
            'before': '_before_acknowledge'
        },
        
        # Fill transitions
        {
            'trigger': 'fill',
            'source': [OrderState.PENDING, OrderState.PARTIALLY_FILLED],
            'dest': OrderState.FILLED,
            'before': '_before_fill'
        },
        {
            'trigger': 'partial_fill',
            'source': OrderState.PENDING,
            'dest': OrderState.PARTIALLY_FILLED,
            'before': '_before_partial_fill'
        },
        
        # Cancellation flow
        {
            'trigger': 'cancel',
            'source': [OrderState.VALIDATED, OrderState.SUBMITTED, OrderState.PENDING, OrderState.PARTIALLY_FILLED],
            'dest': OrderState.CANCELLED,
            'before': '_before_cancel'
        },
        
        # Rejection flow
        {
            'trigger': 'reject',
            'source': '*',
            'dest': OrderState.REJECTED,
            'before': '_before_reject'
        },
        
        # Expiration flow
        {
            'trigger': 'expire',
            'source': [OrderState.PENDING, OrderState.PARTIALLY_FILLED],
            'dest': OrderState.EXPIRED,
            'before': '_before_expire'
        }
    ]
    
    def __init__(self, order: Order, callbacks: Optional[Dict[str, Callable]] = None):
        """
        Initialize state machine for an order.
        
        Args:
            order: Order instance
            callbacks: Optional callbacks for state transitions
        """
        self.order = order
        self.callbacks = callbacks or {}
        
        # Store reference in order for callbacks
        order._machine = self
        order._callbacks = self.callbacks  # Store callbacks on order for trigger methods
        
        # Initialize state machine
        self.machine = Machine(
            model=order,
            states=OrderStateMachine.states,
            transitions=OrderStateMachine.transitions,
            initial=order.state.value,
            send_event=True,
            queued=True,  # Process events sequentially
            auto_transitions=False,  # Don't create automatic to_* methods
            after_state_change='_update_state'
        )
        
        # Track transition metadata
        self._transition_metadata: Dict[str, Any] = {}
    
    
    def set_metadata(self, metadata: Dict[str, Any]):
        """Set metadata for the next transition."""
        self._transition_metadata = metadata
    
    def get_state(self) -> OrderState:
        """Get current order state."""
        return self.order.state
    
    # Trigger wrapper methods
    def validate(self):
        """Validate the order."""
        return self.order.validate()
    
    def submit(self):
        """Submit the order."""
        return self.order.submit()
    
    def acknowledge(self):
        """Acknowledge the order."""
        return self.order.acknowledge()
    
    def fill(self):
        """Mark order as filled."""
        return self.order.fill()
    
    def partial_fill(self):
        """Mark order as partially filled."""
        return self.order.partial_fill()
    
    def cancel(self):
        """Cancel the order."""
        return self.order.cancel()
    
    def reject(self):
        """Reject the order."""
        return self.order.reject()
    
    def expire(self):
        """Expire the order."""
        return self.order.expire()


class OrderService:
    """
    Main order management service.
    
    Coordinates order lifecycle, risk validation, and broker communication.
    """
    
    def __init__(
        self,
        risk_validator: PreTradeRiskValidator,
        broker_client: Any,  # Will be replaced with actual broker client
        position_tracker: Any = None  # Will be replaced with actual position tracker
    ):
        """
        Initialize order service.
        
        Args:
            risk_validator: Pre-trade risk validator
            broker_client: Broker client for order submission
            position_tracker: Optional position tracker
        """
        self.risk_validator = risk_validator
        self.broker_client = broker_client
        self.position_tracker = position_tracker
        
        # Order storage
        self._orders: Dict[str, Order] = {}
        self._order_machines: Dict[str, OrderStateMachine] = {}
        
        # Statistics
        self._order_stats = {
            'total': 0,
            'filled': 0,
            'cancelled': 0,
            'rejected': 0,
            'total_volume': Decimal("0"),
            'total_commission': Decimal("0")
        }
        
        logger.info("Order service initialized")
    
    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        account_id: str = "",
        strategy_id: str = "",
        **kwargs
    ) -> Order:
        """
        Create a new order.
        
        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            quantity: Order quantity
            order_type: Type of order
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            account_id: Trading account ID
            strategy_id: Strategy identifier
            **kwargs: Additional order parameters
            
        Returns:
            Created order
        """
        # Create order
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            account_id=account_id,
            strategy_id=strategy_id,
            **kwargs
        )
        
        # Create state machine
        callbacks = {
            'on_validated': self._on_order_validated,
            'on_submitted': self._on_order_submitted,
            'on_filled': self._on_order_filled,
            'on_cancelled': self._on_order_cancelled,
            'on_rejected': self._on_order_rejected
        }
        
        machine = OrderStateMachine(order, callbacks)
        
        # Store order and machine
        self._orders[order.order_id] = order
        self._order_machines[order.order_id] = machine
        
        # Update statistics
        self._order_stats['total'] += 1
        
        logger.info(f"Created order {order.order_id}: {side} {quantity} {symbol} @ {order_type}")
        
        return order
    
    async def validate_order(self, order_id: str) -> ValidationResult:
        """
        Validate order with pre-trade risk checks.
        
        Args:
            order_id: Order ID
            
        Returns:
            Validation result
        """
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        machine = self._order_machines[order_id]
        
        # Run risk validation
        result = await self.risk_validator.validate_order(order)
        
        # Store results
        order.risk_check_results = {
            'passed': result.passed,
            'checks': [check.to_dict() for check in result.checks],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Transition state if validation passed
        if result.passed:
            machine.validate()
        else:
            machine.set_metadata({'reason': result.get_failure_reasons()})
            machine.reject()
        
        return result
    
    async def submit_order(self, order_id: str) -> bool:
        """
        Submit order to broker.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if submission successful
        """
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        machine = self._order_machines[order_id]
        
        # Check if order can be submitted
        if order.state != OrderState.VALIDATED:
            logger.error(f"Cannot submit order {order_id} in state {order.state}")
            return False
        
        try:
            # Submit to broker (placeholder for actual implementation)
            # broker_order_id = await self.broker_client.submit_order(order)
            broker_order_id = f"BROKER-{order.order_id}"  # Placeholder
            
            # Update order and transition state
            machine.set_metadata({'broker_order_id': broker_order_id})
            machine.submit()
            
            # Simulate acknowledgment for now
            await asyncio.sleep(0.1)
            machine.acknowledge()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to submit order {order_id}: {e}")
            machine.set_metadata({'reason': str(e)})
            machine.reject()
            return False
    
    async def process_fill(
        self,
        order_id: str,
        fill_quantity: int,
        fill_price: Decimal,
        fill_id: Optional[str] = None,
        commission: Decimal = Decimal("0"),
        fees: Decimal = Decimal("0")
    ):
        """
        Process an order fill.
        
        Args:
            order_id: Order ID
            fill_quantity: Filled quantity
            fill_price: Fill price
            fill_id: Optional fill ID
            commission: Commission charged
            fees: Additional fees
        """
        order = self._orders.get(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for fill")
            return
        
        machine = self._order_machines[order_id]
        
        # Create fill
        fill = Fill(
            fill_id=fill_id or f"FILL-{order.order_id}-{len(order.fills)}",
            timestamp=datetime.now(timezone.utc),
            quantity=fill_quantity,
            price=fill_price,
            commission=commission,
            fees=fees
        )
        
        # Set metadata and trigger transition
        machine.set_metadata({'fill': fill})
        
        if fill_quantity == order.remaining_quantity:
            machine.fill()
        else:
            machine.partial_fill()
        
        # Update position tracker if available
        if self.position_tracker:
            await self.position_tracker.process_fill(order, fill)
        
        # Update statistics
        self._order_stats['total_volume'] += fill_price * fill_quantity
        self._order_stats['total_commission'] += commission + fees
    
    async def cancel_order(self, order_id: str, reason: str = "") -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            reason: Cancellation reason
            
        Returns:
            True if cancellation successful
        """
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        machine = self._order_machines[order_id]
        
        # Check if order can be cancelled
        if not order.is_active:
            logger.error(f"Cannot cancel order {order_id} in state {order.state}")
            return False
        
        try:
            # Cancel with broker (placeholder for actual implementation)
            if order.broker_order_id:
                # await self.broker_client.cancel_order(order.broker_order_id)
                pass
            
            # Update order and transition state
            machine.set_metadata({'reason': reason})
            machine.cancel()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self._orders.get(order_id)
    
    def get_active_orders(self) -> List[Order]:
        """Get all active orders."""
        return [order for order in self._orders.values() if order.is_active]
    
    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Get all orders for a symbol."""
        return [order for order in self._orders.values() if order.symbol == symbol]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get order statistics."""
        return self._order_stats.copy()
    
    # Callback methods
    
    def _on_order_validated(self, order: Order, event: Any):
        """Called when order is validated."""
        logger.debug(f"Order {order.order_id} validated callback")
    
    def _on_order_submitted(self, order: Order, event: Any):
        """Called when order is submitted."""
        logger.debug(f"Order {order.order_id} submitted callback")
    
    def _on_order_filled(self, order: Order, event: Any):
        """Called when order is filled."""
        self._order_stats['filled'] += 1
        logger.info(f"Order {order.order_id} filled callback")
    
    def _on_order_cancelled(self, order: Order, event: Any):
        """Called when order is cancelled."""
        self._order_stats['cancelled'] += 1
        logger.info(f"Order {order.order_id} cancelled callback")
    
    def _on_order_rejected(self, order: Order, event: Any):
        """Called when order is rejected."""
        self._order_stats['rejected'] += 1
        logger.warning(f"Order {order.order_id} rejected callback")
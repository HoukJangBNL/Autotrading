"""Trade simulator for realistic order execution in backtesting."""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
import random

from ..models import Order, OrderType, OrderStatus, OrderSide


logger = logging.getLogger(__name__)


class TradeSimulator:
    """
    Simulates realistic trade execution with slippage and commissions.
    
    Handles order fills, partial fills, and market impact simulation
    for accurate backtesting results.
    """
    
    def __init__(
        self,
        commission_rate: float = 0.001,  # 0.1%
        slippage_rate: float = 0.0005,  # 0.05%
        min_commission: float = 1.0,  # Minimum $1 commission
        maker_fee: float = 0.0008,  # 0.08% maker fee
        taker_fee: float = 0.001,  # 0.1% taker fee
        use_tiered_commission: bool = False,
        partial_fill_probability: float = 0.0  # Probability of partial fill
    ):
        """
        Initialize trade simulator.
        
        Args:
            commission_rate: Base commission rate
            slippage_rate: Base slippage rate
            min_commission: Minimum commission per trade
            maker_fee: Maker fee for limit orders
            taker_fee: Taker fee for market orders
            use_tiered_commission: Use maker/taker fee structure
            partial_fill_probability: Probability of partial fills
        """
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.min_commission = min_commission
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.use_tiered_commission = use_tiered_commission
        self.partial_fill_probability = partial_fill_probability
    
    async def execute_trade(
        self,
        order: Order,
        current_price: Decimal,
        current_candle: Optional[Dict[str, Any]] = None
    ) -> Order:
        """
        Simulate trade execution.
        
        Args:
            order: Order to execute
            current_price: Current market price
            current_candle: Current candle data (for limit order checks)
            
        Returns:
            Executed order with fill details
        """
        # Validate order
        if not self._validate_order(order):
            order.status = OrderStatus.REJECTED
            logger.warning(f"Order {order.order_id} rejected - validation failed")
            return order
        
        # Mark as submitted
        order.status = OrderStatus.SUBMITTED
        order.submitted_time = datetime.now()
        
        # Check if order should fill
        should_fill, fill_price = self._check_fill_condition(
            order, current_price, current_candle
        )
        
        if not should_fill:
            return order
        
        # Apply slippage
        slippage_amount = self.apply_slippage(
            order_type=order.order_type,
            side=order.side,
            price=fill_price,
            quantity=order.quantity
        )
        
        # Calculate actual fill price with slippage
        if order.side == OrderSide.BUY:
            actual_fill_price = fill_price + slippage_amount
        else:
            actual_fill_price = fill_price - slippage_amount
        
        # Ensure price is positive
        actual_fill_price = max(actual_fill_price, Decimal('0.01'))
        
        # Simulate partial fills
        fill_quantity = self._simulate_fill_quantity(order.quantity)
        
        # Calculate commission
        commission = self.calculate_commission(
            order_type=order.order_type,
            quantity=fill_quantity,
            price=actual_fill_price
        )
        
        # Update order with execution details
        order.filled_quantity = fill_quantity
        order.average_fill_price = actual_fill_price
        order.commission = commission
        order.filled_time = datetime.now()
        
        # Set order status
        if fill_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
            logger.info(
                f"Order {order.order_id} filled: "
                f"{order.side.value} {fill_quantity} @ {actual_fill_price} "
                f"(slippage: {slippage_amount}, commission: {commission})"
            )
        else:
            order.status = OrderStatus.PARTIAL
            logger.info(
                f"Order {order.order_id} partially filled: "
                f"{fill_quantity}/{order.quantity} @ {actual_fill_price}"
            )
        
        return order
    
    def apply_slippage(
        self,
        order_type: OrderType,
        side: OrderSide,
        price: Decimal,
        quantity: Decimal
    ) -> Decimal:
        """
        Calculate slippage amount.
        
        Args:
            order_type: Type of order
            side: Buy or sell
            price: Base price
            quantity: Order quantity
            
        Returns:
            Slippage amount to add/subtract from price
        """
        if order_type == OrderType.LIMIT:
            # Limit orders have minimal slippage
            base_slippage = self.slippage_rate * 0.1
        else:
            # Market orders have full slippage
            base_slippage = self.slippage_rate
        
        # Increase slippage for larger orders (market impact)
        size_factor = 1.0
        if quantity > 1000:
            size_factor = 1.2
        elif quantity > 5000:
            size_factor = 1.5
        elif quantity > 10000:
            size_factor = 2.0
        
        # Add some randomness (±20%)
        random_factor = 0.8 + (random.random() * 0.4)
        
        # Calculate total slippage
        total_slippage_rate = base_slippage * size_factor * random_factor
        slippage_amount = price * Decimal(str(total_slippage_rate))
        
        return slippage_amount
    
    def calculate_commission(
        self,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal
    ) -> Decimal:
        """
        Calculate trading commission.
        
        Args:
            order_type: Type of order
            quantity: Order quantity
            price: Fill price
            
        Returns:
            Commission amount
        """
        # Calculate trade value
        trade_value = quantity * price
        
        # Determine commission rate
        if self.use_tiered_commission:
            if order_type == OrderType.LIMIT:
                rate = self.maker_fee
            else:
                rate = self.taker_fee
        else:
            rate = self.commission_rate
        
        # Calculate commission
        commission = trade_value * Decimal(str(rate))
        
        # Apply minimum commission
        commission = max(commission, Decimal(str(self.min_commission)))
        
        return commission
    
    def _validate_order(self, order: Order) -> bool:
        """Validate order parameters."""
        # Check quantity
        if order.quantity <= 0:
            logger.error(f"Invalid quantity: {order.quantity}")
            return False
        
        # Check limit price for limit orders
        if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            if not order.price or order.price <= 0:
                logger.error(f"Invalid limit price: {order.price}")
                return False
        
        # Check stop price for stop orders
        if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
            if not order.stop_price or order.stop_price <= 0:
                logger.error(f"Invalid stop price: {order.stop_price}")
                return False
        
        return True
    
    def _check_fill_condition(
        self,
        order: Order,
        current_price: Decimal,
        current_candle: Optional[Dict[str, Any]]
    ) -> tuple[bool, Decimal]:
        """
        Check if order should fill at current price.
        
        Returns:
            Tuple of (should_fill, fill_price)
        """
        if order.order_type == OrderType.MARKET:
            # Market orders always fill at current price
            return True, current_price
        
        elif order.order_type == OrderType.LIMIT:
            # Limit orders fill when price is favorable
            if order.side == OrderSide.BUY:
                # Buy limit fills when price <= limit
                if current_price <= order.price:
                    return True, min(current_price, order.price)
            else:
                # Sell limit fills when price >= limit
                if current_price >= order.price:
                    return True, max(current_price, order.price)
            
            # Check if candle crossed limit price
            if current_candle:
                if order.side == OrderSide.BUY:
                    if current_candle['low'] <= order.price:
                        return True, order.price
                else:
                    if current_candle['high'] >= order.price:
                        return True, order.price
        
        elif order.order_type == OrderType.STOP:
            # Stop orders trigger when price crosses stop
            if order.side == OrderSide.BUY:
                # Buy stop triggers when price >= stop
                if current_price >= order.stop_price:
                    return True, current_price
            else:
                # Sell stop triggers when price <= stop
                if current_price <= order.stop_price:
                    return True, current_price
            
            # Check if candle crossed stop price
            if current_candle:
                if order.side == OrderSide.BUY:
                    if current_candle['high'] >= order.stop_price:
                        # Assume worst case fill
                        return True, order.stop_price + self.apply_slippage(
                            OrderType.STOP, order.side, order.stop_price, order.quantity
                        )
                else:
                    if current_candle['low'] <= order.stop_price:
                        # Assume worst case fill
                        return True, order.stop_price - self.apply_slippage(
                            OrderType.STOP, order.side, order.stop_price, order.quantity
                        )
        
        elif order.order_type == OrderType.STOP_LIMIT:
            # Stop limit orders need stop trigger then limit fill
            # This is simplified - in reality would need two-step process
            if order.side == OrderSide.BUY:
                if current_price >= order.stop_price and current_price <= order.price:
                    return True, current_price
            else:
                if current_price <= order.stop_price and current_price >= order.price:
                    return True, current_price
        
        return False, Decimal('0')
    
    def _simulate_fill_quantity(self, requested_quantity: Decimal) -> Decimal:
        """
        Simulate fill quantity (potentially partial).
        
        Args:
            requested_quantity: Requested order quantity
            
        Returns:
            Actual filled quantity
        """
        if self.partial_fill_probability > 0 and random.random() < self.partial_fill_probability:
            # Simulate partial fill (50-95% of requested)
            fill_percentage = 0.5 + (random.random() * 0.45)
            return requested_quantity * Decimal(str(fill_percentage))
        
        return requested_quantity
    
    def estimate_fill_price(
        self,
        order_type: OrderType,
        side: OrderSide,
        current_price: Decimal,
        quantity: Decimal,
        limit_price: Optional[Decimal] = None
    ) -> Decimal:
        """
        Estimate likely fill price for an order.
        
        Useful for position sizing and risk calculations.
        
        Args:
            order_type: Type of order
            side: Buy or sell
            current_price: Current market price
            quantity: Order quantity
            limit_price: Limit price (for limit orders)
            
        Returns:
            Estimated fill price including slippage
        """
        # Base price
        if order_type == OrderType.LIMIT and limit_price:
            base_price = limit_price
        else:
            base_price = current_price
        
        # Apply estimated slippage
        slippage = self.apply_slippage(order_type, side, base_price, quantity)
        
        if side == OrderSide.BUY:
            return base_price + slippage
        else:
            return base_price - slippage
    
    def estimate_total_cost(
        self,
        order_type: OrderType,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal
    ) -> Dict[str, Decimal]:
        """
        Estimate total cost of a trade including commission and slippage.
        
        Args:
            order_type: Type of order
            side: Buy or sell
            quantity: Order quantity
            price: Expected price
            
        Returns:
            Dictionary with cost breakdown
        """
        # Estimate fill price with slippage
        fill_price = self.estimate_fill_price(order_type, side, price, quantity, price)
        
        # Calculate commission
        commission = self.calculate_commission(order_type, quantity, fill_price)
        
        # Calculate slippage cost
        slippage_cost = abs(fill_price - price) * quantity
        
        # Total cost
        trade_value = quantity * fill_price
        total_cost = trade_value + commission
        
        return {
            'trade_value': trade_value,
            'commission': commission,
            'slippage_cost': slippage_cost,
            'total_cost': total_cost,
            'estimated_fill_price': fill_price
        }
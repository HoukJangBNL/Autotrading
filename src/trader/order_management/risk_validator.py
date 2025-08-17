"""
Pre-trade risk validation for order management.

This module provides comprehensive risk checks before order submission,
including position limits, daily loss limits, and regulatory compliance.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import pytz

from .order import Order, OrderSide, OrderType
from ...utils.logger import get_logger

logger = get_logger(__name__)


class RiskCheckType(str, Enum):
    """Types of risk checks."""
    POSITION_LIMIT = "POSITION_LIMIT"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    ORDER_SIZE_LIMIT = "ORDER_SIZE_LIMIT"
    PRICE_REASONABILITY = "PRICE_REASONABILITY"
    RESTRICTED_LIST = "RESTRICTED_LIST"
    MARKET_HOURS = "MARKET_HOURS"
    ACCOUNT_RESTRICTIONS = "ACCOUNT_RESTRICTIONS"
    BUYING_POWER = "BUYING_POWER"
    DUPLICATE_ORDER = "DUPLICATE_ORDER"
    RATE_LIMIT = "RATE_LIMIT"


@dataclass
class RiskCheckResult:
    """Result of a single risk check."""
    check_type: RiskCheckType
    passed: bool
    reason: str = ""
    severity: str = "ERROR"  # ERROR, WARNING, INFO
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'check_type': self.check_type.value,
            'passed': self.passed,
            'reason': self.reason,
            'severity': self.severity,
            'metadata': self.metadata
        }


@dataclass
class ValidationResult:
    """Overall validation result containing all check results."""
    passed: bool
    checks: List[RiskCheckResult]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def get_failures(self) -> List[RiskCheckResult]:
        """Get all failed checks."""
        return [check for check in self.checks if not check.passed]
    
    def get_failure_reasons(self) -> str:
        """Get concatenated failure reasons."""
        failures = self.get_failures()
        if not failures:
            return ""
        return "; ".join(f"{f.check_type.value}: {f.reason}" for f in failures)
    
    @classmethod
    def combine(cls, results: List['ValidationResult']) -> 'ValidationResult':
        """Combine multiple validation results."""
        all_checks = []
        for result in results:
            all_checks.extend(result.checks)
        
        passed = all(check.passed for check in all_checks)
        return cls(passed=passed, checks=all_checks)


@dataclass
class RiskConfig:
    """Risk management configuration."""
    # Position limits
    max_position_size: int = 10000  # Max shares per symbol
    max_position_value: Decimal = Decimal("100000")  # Max $ value per position
    max_total_positions: int = 20  # Max number of open positions
    
    # Loss limits
    max_daily_loss: Decimal = Decimal("5000")  # Max daily loss
    max_daily_loss_percent: Decimal = Decimal("0.05")  # 5% of account value
    
    # Order limits
    max_order_size: int = 5000  # Max shares per order
    max_order_value: Decimal = Decimal("50000")  # Max $ value per order
    min_order_size: int = 1  # Min shares per order
    
    # Price checks
    price_deviation_percent: Decimal = Decimal("0.05")  # 5% from market
    min_price: Decimal = Decimal("0.01")  # Penny stock threshold
    
    # Rate limiting
    max_orders_per_minute: int = 30
    max_orders_per_hour: int = 300
    max_orders_per_day: int = 1000
    
    # Market hours (EST)
    market_open: time = time(9, 30)
    market_close: time = time(16, 0)
    allow_premarket: bool = True
    allow_afterhours: bool = True
    premarket_start: time = time(4, 0)
    afterhours_end: time = time(20, 0)
    
    # Account restrictions
    pdt_equity_requirement: Decimal = Decimal("25000")  # PDT rule
    margin_requirement: Decimal = Decimal("0.25")  # 25% margin requirement
    
    # Restricted symbols
    restricted_symbols: Set[str] = field(default_factory=set)
    
    # Feature flags
    enable_position_limits: bool = True
    enable_loss_limits: bool = True
    enable_price_checks: bool = True
    enable_market_hours_check: bool = True
    enable_duplicate_check: bool = True
    enable_rate_limiting: bool = True


class PreTradeRiskValidator:
    """
    Comprehensive pre-trade risk validation.
    
    Performs all risk checks before order submission to ensure
    compliance with risk limits and regulatory requirements.
    """
    
    def __init__(
        self,
        config: RiskConfig,
        position_tracker: Optional[Any] = None,  # Will be replaced with actual tracker
        quote_service: Optional[Any] = None,  # Will be replaced with actual service
        account_service: Optional[Any] = None  # Will be replaced with actual service
    ):
        """
        Initialize risk validator.
        
        Args:
            config: Risk configuration
            position_tracker: Position tracking service
            quote_service: Real-time quote service
            account_service: Account information service
        """
        self.config = config
        self.position_tracker = position_tracker
        self.quote_service = quote_service
        self.account_service = account_service
        
        # Track order submissions for rate limiting
        self._order_timestamps: List[datetime] = []
        
        # Track daily metrics
        self._daily_metrics = {
            'loss': Decimal("0"),
            'order_count': 0,
            'last_reset': datetime.now(timezone.utc).date()
        }
        
        # Eastern timezone for market hours
        self.market_tz = pytz.timezone('US/Eastern')
        
        logger.info("Risk validator initialized with config")
    
    async def validate_order(self, order: Order) -> ValidationResult:
        """
        Perform all pre-trade risk checks on an order.
        
        Args:
            order: Order to validate
            
        Returns:
            Validation result with all check results
        """
        # Reset daily metrics if needed
        self._check_daily_reset()
        
        # Run all checks in parallel
        check_tasks = []
        
        if self.config.enable_position_limits:
            check_tasks.append(self.check_position_limits(order))
        
        if self.config.enable_loss_limits:
            check_tasks.append(self.check_daily_loss_limit(order))
        
        check_tasks.extend([
            self.check_order_size_limits(order),
            self.check_restricted_list(order),
            self.check_market_hours(order),
            self.check_buying_power(order)
        ])
        
        if self.config.enable_price_checks:
            check_tasks.append(self.check_price_reasonability(order))
        
        if self.config.enable_duplicate_check:
            check_tasks.append(self.check_duplicate_order(order))
        
        if self.config.enable_rate_limiting:
            check_tasks.append(self.check_rate_limits(order))
        
        # Wait for all checks to complete
        check_results = await asyncio.gather(*check_tasks, return_exceptions=True)
        
        # Process results
        all_checks = []
        for result in check_results:
            if isinstance(result, Exception):
                logger.error(f"Risk check failed with exception: {result}")
                all_checks.append(RiskCheckResult(
                    check_type=RiskCheckType.ACCOUNT_RESTRICTIONS,
                    passed=False,
                    reason=f"Check failed: {str(result)}",
                    severity="ERROR"
                ))
            else:
                all_checks.append(result)
        
        # Determine overall pass/fail
        passed = all(check.passed or check.severity == "WARNING" for check in all_checks)
        
        result = ValidationResult(passed=passed, checks=all_checks)
        
        # Log validation result
        if passed:
            logger.info(f"Order {order.order_id} passed all risk checks")
        else:
            logger.warning(f"Order {order.order_id} failed risk checks: {result.get_failure_reasons()}")
        
        return result
    
    async def check_position_limits(self, order: Order) -> RiskCheckResult:
        """Check position size limits."""
        if not self.position_tracker:
            return RiskCheckResult(
                check_type=RiskCheckType.POSITION_LIMIT,
                passed=True,
                reason="Position tracker not available",
                severity="WARNING"
            )
        
        try:
            # Get current position
            current_position = await self.position_tracker.get_position(order.symbol)
            current_quantity = current_position.quantity if current_position else 0
            
            # Calculate new position
            if order.side in [OrderSide.BUY, OrderSide.BUY_TO_COVER]:
                new_quantity = current_quantity + order.quantity
            else:  # SELL, SELL_SHORT
                new_quantity = current_quantity - order.quantity
            
            new_quantity_abs = abs(new_quantity)
            
            # Check quantity limit
            if new_quantity_abs > self.config.max_position_size:
                return RiskCheckResult(
                    check_type=RiskCheckType.POSITION_LIMIT,
                    passed=False,
                    reason=f"Position size {new_quantity_abs} exceeds limit {self.config.max_position_size}",
                    metadata={
                        'current_position': current_quantity,
                        'new_position': new_quantity,
                        'limit': self.config.max_position_size
                    }
                )
            
            # Check value limit (if we have price)
            if order.order_type == OrderType.LIMIT and order.limit_price:
                position_value = new_quantity_abs * order.limit_price
                if position_value > self.config.max_position_value:
                    return RiskCheckResult(
                        check_type=RiskCheckType.POSITION_LIMIT,
                        passed=False,
                        reason=f"Position value ${position_value} exceeds limit ${self.config.max_position_value}",
                        metadata={
                            'position_value': float(position_value),
                            'limit': float(self.config.max_position_value)
                        }
                    )
            
            # Check total positions limit
            total_positions = await self.position_tracker.get_position_count()
            if current_quantity == 0 and total_positions >= self.config.max_total_positions:
                return RiskCheckResult(
                    check_type=RiskCheckType.POSITION_LIMIT,
                    passed=False,
                    reason=f"Total positions {total_positions} at limit {self.config.max_total_positions}",
                    metadata={
                        'total_positions': total_positions,
                        'limit': self.config.max_total_positions
                    }
                )
            
            return RiskCheckResult(
                check_type=RiskCheckType.POSITION_LIMIT,
                passed=True,
                metadata={
                    'current_position': current_quantity,
                    'new_position': new_quantity
                }
            )
            
        except Exception as e:
            logger.error(f"Error checking position limits: {e}")
            return RiskCheckResult(
                check_type=RiskCheckType.POSITION_LIMIT,
                passed=False,
                reason=f"Position limit check error: {str(e)}"
            )
    
    async def check_daily_loss_limit(self, order: Order) -> RiskCheckResult:
        """Check daily loss limits."""
        if not self.position_tracker:
            return RiskCheckResult(
                check_type=RiskCheckType.DAILY_LOSS_LIMIT,
                passed=True,
                reason="Position tracker not available",
                severity="WARNING"
            )
        
        try:
            # Get daily P&L
            daily_pnl = await self.position_tracker.get_daily_pnl()
            current_loss = min(daily_pnl, Decimal("0"))  # Only consider losses
            
            # Check absolute loss limit
            if abs(current_loss) >= self.config.max_daily_loss:
                return RiskCheckResult(
                    check_type=RiskCheckType.DAILY_LOSS_LIMIT,
                    passed=False,
                    reason=f"Daily loss ${abs(current_loss)} exceeds limit ${self.config.max_daily_loss}",
                    metadata={
                        'daily_pnl': float(daily_pnl),
                        'daily_loss': float(current_loss),
                        'limit': float(self.config.max_daily_loss)
                    }
                )
            
            # Check percentage loss limit if account service available
            if self.account_service:
                account_value = await self.account_service.get_account_value()
                loss_percent = abs(current_loss) / account_value if account_value > 0 else Decimal("0")
                
                if loss_percent >= self.config.max_daily_loss_percent:
                    return RiskCheckResult(
                        check_type=RiskCheckType.DAILY_LOSS_LIMIT,
                        passed=False,
                        reason=f"Daily loss {loss_percent:.2%} exceeds limit {self.config.max_daily_loss_percent:.2%}",
                        metadata={
                            'daily_loss_percent': float(loss_percent),
                            'limit_percent': float(self.config.max_daily_loss_percent)
                        }
                    )
            
            return RiskCheckResult(
                check_type=RiskCheckType.DAILY_LOSS_LIMIT,
                passed=True,
                metadata={
                    'daily_pnl': float(daily_pnl),
                    'remaining_loss_capacity': float(self.config.max_daily_loss - abs(current_loss))
                }
            )
            
        except Exception as e:
            logger.error(f"Error checking daily loss limit: {e}")
            return RiskCheckResult(
                check_type=RiskCheckType.DAILY_LOSS_LIMIT,
                passed=False,
                reason=f"Daily loss check error: {str(e)}"
            )
    
    async def check_order_size_limits(self, order: Order) -> RiskCheckResult:
        """Check order size limits."""
        # Check minimum size
        if order.quantity < self.config.min_order_size:
            return RiskCheckResult(
                check_type=RiskCheckType.ORDER_SIZE_LIMIT,
                passed=False,
                reason=f"Order size {order.quantity} below minimum {self.config.min_order_size}",
                metadata={
                    'order_size': order.quantity,
                    'min_size': self.config.min_order_size
                }
            )
        
        # Check maximum size
        if order.quantity > self.config.max_order_size:
            return RiskCheckResult(
                check_type=RiskCheckType.ORDER_SIZE_LIMIT,
                passed=False,
                reason=f"Order size {order.quantity} exceeds limit {self.config.max_order_size}",
                metadata={
                    'order_size': order.quantity,
                    'max_size': self.config.max_order_size
                }
            )
        
        # Check order value if limit order
        if order.order_type == OrderType.LIMIT and order.limit_price:
            order_value = order.quantity * order.limit_price
            if order_value > self.config.max_order_value:
                return RiskCheckResult(
                    check_type=RiskCheckType.ORDER_SIZE_LIMIT,
                    passed=False,
                    reason=f"Order value ${order_value} exceeds limit ${self.config.max_order_value}",
                    metadata={
                        'order_value': float(order_value),
                        'max_value': float(self.config.max_order_value)
                    }
                )
        
        return RiskCheckResult(
            check_type=RiskCheckType.ORDER_SIZE_LIMIT,
            passed=True,
            metadata={'order_size': order.quantity}
        )
    
    async def check_price_reasonability(self, order: Order) -> RiskCheckResult:
        """Check if order price is reasonable compared to market."""
        # Skip for market orders
        if order.order_type == OrderType.MARKET:
            return RiskCheckResult(
                check_type=RiskCheckType.PRICE_REASONABILITY,
                passed=True,
                reason="Market order - no price check needed"
            )
        
        # Check minimum price
        if order.limit_price and order.limit_price < self.config.min_price:
            return RiskCheckResult(
                check_type=RiskCheckType.PRICE_REASONABILITY,
                passed=False,
                reason=f"Price ${order.limit_price} below minimum ${self.config.min_price}",
                severity="WARNING",
                metadata={
                    'order_price': float(order.limit_price),
                    'min_price': float(self.config.min_price)
                }
            )
        
        # Check against market price if quote service available
        if self.quote_service and order.limit_price:
            try:
                quote = await self.quote_service.get_quote(order.symbol)
                if quote:
                    mid_price = (quote.bid + quote.ask) / 2
                    price_deviation = abs(order.limit_price - mid_price) / mid_price
                    
                    if price_deviation > self.config.price_deviation_percent:
                        return RiskCheckResult(
                            check_type=RiskCheckType.PRICE_REASONABILITY,
                            passed=False,
                            reason=f"Price ${order.limit_price} deviates {price_deviation:.2%} from market ${mid_price}",
                            severity="WARNING",
                            metadata={
                                'order_price': float(order.limit_price),
                                'market_price': float(mid_price),
                                'deviation': float(price_deviation),
                                'max_deviation': float(self.config.price_deviation_percent)
                            }
                        )
            except Exception as e:
                logger.error(f"Error checking market price: {e}")
        
        return RiskCheckResult(
            check_type=RiskCheckType.PRICE_REASONABILITY,
            passed=True
        )
    
    async def check_restricted_list(self, order: Order) -> RiskCheckResult:
        """Check if symbol is on restricted list."""
        if order.symbol in self.config.restricted_symbols:
            return RiskCheckResult(
                check_type=RiskCheckType.RESTRICTED_LIST,
                passed=False,
                reason=f"Symbol {order.symbol} is on restricted list",
                metadata={'symbol': order.symbol}
            )
        
        return RiskCheckResult(
            check_type=RiskCheckType.RESTRICTED_LIST,
            passed=True
        )
    
    async def check_market_hours(self, order: Order) -> RiskCheckResult:
        """Check if order is being placed during valid market hours."""
        now = datetime.now(self.market_tz)
        current_time = now.time()
        
        # Regular market hours
        if self.config.market_open <= current_time <= self.config.market_close:
            return RiskCheckResult(
                check_type=RiskCheckType.MARKET_HOURS,
                passed=True,
                reason="Regular market hours"
            )
        
        # Pre-market
        if (self.config.allow_premarket and 
            self.config.premarket_start <= current_time < self.config.market_open):
            return RiskCheckResult(
                check_type=RiskCheckType.MARKET_HOURS,
                passed=True,
                reason="Pre-market trading allowed",
                severity="INFO"
            )
        
        # After-hours
        if (self.config.allow_afterhours and 
            self.config.market_close < current_time <= self.config.afterhours_end):
            return RiskCheckResult(
                check_type=RiskCheckType.MARKET_HOURS,
                passed=True,
                reason="After-hours trading allowed",
                severity="INFO"
            )
        
        # Outside trading hours
        return RiskCheckResult(
            check_type=RiskCheckType.MARKET_HOURS,
            passed=False,
            reason=f"Outside trading hours (current: {current_time.strftime('%H:%M')} ET)",
            metadata={
                'current_time': current_time.strftime('%H:%M'),
                'market_open': self.config.market_open.strftime('%H:%M'),
                'market_close': self.config.market_close.strftime('%H:%M')
            }
        )
    
    async def check_buying_power(self, order: Order) -> RiskCheckResult:
        """Check if account has sufficient buying power."""
        if not self.account_service:
            return RiskCheckResult(
                check_type=RiskCheckType.BUYING_POWER,
                passed=True,
                reason="Account service not available",
                severity="WARNING"
            )
        
        # Only check for buy orders
        if order.side not in [OrderSide.BUY, OrderSide.BUY_TO_COVER]:
            return RiskCheckResult(
                check_type=RiskCheckType.BUYING_POWER,
                passed=True,
                reason="Sell order - no buying power check needed"
            )
        
        try:
            # Get required buying power
            if order.order_type == OrderType.LIMIT and order.limit_price:
                required_amount = order.quantity * order.limit_price
            else:
                # For market orders, estimate using quote
                if self.quote_service:
                    quote = await self.quote_service.get_quote(order.symbol)
                    if quote:
                        required_amount = order.quantity * quote.ask
                    else:
                        # Can't determine required amount
                        return RiskCheckResult(
                            check_type=RiskCheckType.BUYING_POWER,
                            passed=True,
                            reason="Cannot determine required amount for market order",
                            severity="WARNING"
                        )
                else:
                    return RiskCheckResult(
                        check_type=RiskCheckType.BUYING_POWER,
                        passed=True,
                        reason="Quote service not available",
                        severity="WARNING"
                    )
            
            # Check buying power
            buying_power = await self.account_service.get_buying_power()
            if required_amount > buying_power:
                return RiskCheckResult(
                    check_type=RiskCheckType.BUYING_POWER,
                    passed=False,
                    reason=f"Insufficient buying power: required ${required_amount}, available ${buying_power}",
                    metadata={
                        'required': float(required_amount),
                        'available': float(buying_power)
                    }
                )
            
            return RiskCheckResult(
                check_type=RiskCheckType.BUYING_POWER,
                passed=True,
                metadata={
                    'required': float(required_amount),
                    'available': float(buying_power),
                    'remaining': float(buying_power - required_amount)
                }
            )
            
        except Exception as e:
            logger.error(f"Error checking buying power: {e}")
            return RiskCheckResult(
                check_type=RiskCheckType.BUYING_POWER,
                passed=False,
                reason=f"Buying power check error: {str(e)}"
            )
    
    async def check_duplicate_order(self, order: Order) -> RiskCheckResult:
        """Check for duplicate orders."""
        # This would typically check against recent orders
        # For now, always pass
        return RiskCheckResult(
            check_type=RiskCheckType.DUPLICATE_ORDER,
            passed=True
        )
    
    async def check_rate_limits(self, order: Order) -> RiskCheckResult:
        """Check order submission rate limits."""
        now = datetime.now(timezone.utc)
        
        # Clean up old timestamps
        cutoff_hour = now - timedelta(hours=1)
        self._order_timestamps = [ts for ts in self._order_timestamps if ts > cutoff_hour]
        
        # Count orders in different windows
        one_minute_ago = now - timedelta(minutes=1)
        one_hour_ago = now - timedelta(hours=1)
        
        orders_last_minute = sum(1 for ts in self._order_timestamps if ts > one_minute_ago)
        orders_last_hour = len(self._order_timestamps)
        
        # Check per-minute limit
        if orders_last_minute >= self.config.max_orders_per_minute:
            return RiskCheckResult(
                check_type=RiskCheckType.RATE_LIMIT,
                passed=False,
                reason=f"Rate limit exceeded: {orders_last_minute} orders/minute",
                metadata={
                    'orders_last_minute': orders_last_minute,
                    'limit_per_minute': self.config.max_orders_per_minute
                }
            )
        
        # Check per-hour limit
        if orders_last_hour >= self.config.max_orders_per_hour:
            return RiskCheckResult(
                check_type=RiskCheckType.RATE_LIMIT,
                passed=False,
                reason=f"Rate limit exceeded: {orders_last_hour} orders/hour",
                metadata={
                    'orders_last_hour': orders_last_hour,
                    'limit_per_hour': self.config.max_orders_per_hour
                }
            )
        
        # Check daily limit
        if self._daily_metrics['order_count'] >= self.config.max_orders_per_day:
            return RiskCheckResult(
                check_type=RiskCheckType.RATE_LIMIT,
                passed=False,
                reason=f"Daily order limit exceeded: {self._daily_metrics['order_count']} orders",
                metadata={
                    'orders_today': self._daily_metrics['order_count'],
                    'limit_per_day': self.config.max_orders_per_day
                }
            )
        
        # Record this order submission
        self._order_timestamps.append(now)
        self._daily_metrics['order_count'] += 1
        
        return RiskCheckResult(
            check_type=RiskCheckType.RATE_LIMIT,
            passed=True,
            metadata={
                'orders_last_minute': orders_last_minute,
                'orders_last_hour': orders_last_hour,
                'orders_today': self._daily_metrics['order_count']
            }
        )
    
    def _check_daily_reset(self):
        """Check if daily metrics need to be reset."""
        today = datetime.now(timezone.utc).date()
        if today > self._daily_metrics['last_reset']:
            self._daily_metrics = {
                'loss': Decimal("0"),
                'order_count': 0,
                'last_reset': today
            }
            logger.info("Daily risk metrics reset")
    
    def add_restricted_symbol(self, symbol: str):
        """Add symbol to restricted list."""
        self.config.restricted_symbols.add(symbol)
        logger.info(f"Added {symbol} to restricted list")
    
    def remove_restricted_symbol(self, symbol: str):
        """Remove symbol from restricted list."""
        self.config.restricted_symbols.discard(symbol)
        logger.info(f"Removed {symbol} from restricted list")
    
    def update_config(self, **kwargs):
        """Update risk configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Updated risk config: {key} = {value}")
            else:
                logger.warning(f"Unknown risk config parameter: {key}")
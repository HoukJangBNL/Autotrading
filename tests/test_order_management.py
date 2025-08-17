"""
Comprehensive tests for the Order Management System.
"""

import pytest
import asyncio
from datetime import datetime, timezone, time
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from src.trader.order_management import (
    Order, OrderState, OrderType, OrderSide, Fill,
    OrderService, OrderStateMachine,
    PreTradeRiskValidator, RiskConfig, ValidationResult,
    PositionTracker, Position, CostBasisMethod
)
from src.trader.order_management.risk_validator import RiskCheckType
from src.utils import setup_logging


class TestOrder:
    """Test Order data model."""
    
    def test_order_creation(self):
        """Test basic order creation."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("150.00")
        )
        
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100
        assert order.order_type == OrderType.LIMIT
        assert order.limit_price == Decimal("150.00")
        assert order.state == OrderState.NEW
        assert order.remaining_quantity == 100
        assert order.filled_quantity == 0
    
    def test_order_validation_errors(self):
        """Test order validation errors."""
        # Invalid quantity
        with pytest.raises(ValueError, match="quantity must be positive"):
            Order(symbol="AAPL", side=OrderSide.BUY, quantity=0)
        
        # Limit order without price
        with pytest.raises(ValueError, match="Limit price required"):
            Order(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=100,
                order_type=OrderType.LIMIT
            )
    
    def test_add_fill(self):
        """Test adding fills to order."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        order.state = OrderState.PENDING
        
        # Add partial fill
        fill1 = Fill(
            fill_id="F1",
            timestamp=datetime.now(timezone.utc),
            quantity=50,
            price=Decimal("150.00"),
            commission=Decimal("1.00")
        )
        
        order.add_fill(fill1)
        
        assert order.filled_quantity == 50
        assert order.remaining_quantity == 50
        assert order.average_fill_price == Decimal("150.00")
        assert order.total_commission == Decimal("1.00")
        assert order.state == OrderState.PARTIALLY_FILLED
        
        # Add remaining fill
        fill2 = Fill(
            fill_id="F2",
            timestamp=datetime.now(timezone.utc),
            quantity=50,
            price=Decimal("151.00"),
            commission=Decimal("1.00")
        )
        
        order.add_fill(fill2)
        
        assert order.filled_quantity == 100
        assert order.remaining_quantity == 0
        assert order.average_fill_price == Decimal("150.50")  # Weighted average
        assert order.total_commission == Decimal("2.00")
        assert order.state == OrderState.FILLED
        assert order.completed_at is not None


class TestOrderStateMachine:
    """Test Order State Machine."""
    
    def test_state_transitions(self):
        """Test valid state transitions."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("150.00")
        )
        
        machine = OrderStateMachine(order)
        
        # Initial state
        assert machine.get_state() == OrderState.NEW
        
        # Validate
        order.risk_check_results = {'passed': True}
        machine.validate()
        assert machine.get_state() == OrderState.VALIDATED
        
        # Submit
        machine.submit()
        assert machine.get_state() == OrderState.SUBMITTED
        
        # Acknowledge
        machine.set_metadata({'broker_order_id': 'BROKER123'})
        machine.acknowledge()
        assert machine.get_state() == OrderState.PENDING
        assert order.broker_order_id == 'BROKER123'
        
        # Partial fill
        fill = Fill(
            fill_id="F1",
            timestamp=datetime.now(timezone.utc),
            quantity=50,
            price=Decimal("150.00")
        )
        machine.set_metadata({'fill': fill})
        machine.partial_fill()
        assert machine.get_state() == OrderState.PARTIALLY_FILLED
        
        # Final fill
        fill2 = Fill(
            fill_id="F2",
            timestamp=datetime.now(timezone.utc),
            quantity=50,
            price=Decimal("150.00")
        )
        machine.set_metadata({'fill': fill2})
        machine.fill()
        assert machine.get_state() == OrderState.FILLED
    
    def test_rejection_flow(self):
        """Test order rejection."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        
        machine = OrderStateMachine(order)
        
        # Reject from NEW state
        machine.set_metadata({'reason': 'Invalid symbol'})
        machine.reject()
        assert machine.get_state() == OrderState.REJECTED
        assert 'Rejected: Invalid symbol' in order.broker_messages
    
    def test_cancellation_flow(self):
        """Test order cancellation."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("150.00")
        )
        order.risk_check_results = {'passed': True}
        
        machine = OrderStateMachine(order)
        
        # Move to PENDING state
        machine.validate()
        machine.submit()
        machine.acknowledge()
        
        # Cancel
        machine.cancel()
        assert machine.get_state() == OrderState.CANCELLED
        assert order.completed_at is not None


class TestOrderService:
    """Test Order Service."""
    
    @pytest.fixture
    def mock_risk_validator(self):
        validator = Mock(spec=PreTradeRiskValidator)
        validator.validate_order = AsyncMock(return_value=ValidationResult(
            passed=True,
            checks=[]
        ))
        return validator
    
    @pytest.fixture
    def mock_broker_client(self):
        broker = Mock()
        broker.submit_order = AsyncMock(return_value="BROKER123")
        broker.cancel_order = AsyncMock(return_value=True)
        return broker
    
    @pytest.fixture
    def order_service(self, mock_risk_validator, mock_broker_client):
        return OrderService(
            risk_validator=mock_risk_validator,
            broker_client=mock_broker_client
        )
    
    @pytest.mark.asyncio
    async def test_create_order(self, order_service):
        """Test order creation."""
        order = await order_service.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("150.00"),
            account_id="TEST123"
        )
        
        assert order.symbol == "AAPL"
        assert order.order_id in order_service._orders
        assert order_service._order_stats['total'] == 1
    
    @pytest.mark.asyncio
    async def test_validate_order(self, order_service):
        """Test order validation."""
        order = await order_service.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100
        )
        
        result = await order_service.validate_order(order.order_id)
        
        assert result.passed
        assert order.state == OrderState.VALIDATED
        assert order.risk_check_results['passed']
    
    @pytest.mark.asyncio
    async def test_submit_order(self, order_service):
        """Test order submission."""
        order = await order_service.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100
        )
        
        # Validate first
        await order_service.validate_order(order.order_id)
        
        # Submit
        success = await order_service.submit_order(order.order_id)
        
        assert success
        assert order.state == OrderState.PENDING  # After acknowledgment
        assert order.broker_order_id == f"BROKER-{order.order_id}"
    
    @pytest.mark.asyncio
    async def test_process_fill(self, order_service):
        """Test fill processing."""
        order = await order_service.create_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100
        )
        
        # Move to PENDING state
        await order_service.validate_order(order.order_id)
        await order_service.submit_order(order.order_id)
        
        # Process fill
        await order_service.process_fill(
            order_id=order.order_id,
            fill_quantity=100,
            fill_price=Decimal("150.00"),
            commission=Decimal("1.00")
        )
        
        assert order.state == OrderState.FILLED
        assert order.filled_quantity == 100
        assert order.average_fill_price == Decimal("150.00")
        assert order_service._order_stats['filled'] == 1


class TestRiskValidator:
    """Test Pre-Trade Risk Validator."""
    
    @pytest.fixture
    def risk_config(self):
        return RiskConfig(
            max_position_size=1000,
            max_order_size=500,
            max_daily_loss=Decimal("1000"),
            price_deviation_percent=Decimal("0.05"),
            restricted_symbols={"BANNED"}
        )
    
    @pytest.fixture
    def risk_validator(self, risk_config):
        return PreTradeRiskValidator(config=risk_config)
    
    @pytest.mark.asyncio
    async def test_order_size_limits(self, risk_validator):
        """Test order size limit checks."""
        # Order too large
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=600,  # Exceeds max_order_size of 500
            order_type=OrderType.MARKET
        )
        
        result = await risk_validator.validate_order(order)
        
        assert not result.passed
        failures = result.get_failures()
        assert any(f.check_type.value == "ORDER_SIZE_LIMIT" for f in failures)
    
    @pytest.mark.asyncio
    async def test_restricted_symbol(self, risk_validator):
        """Test restricted symbol check."""
        order = Order(
            symbol="BANNED",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        
        result = await risk_validator.validate_order(order)
        
        assert not result.passed
        failures = result.get_failures()
        assert any(f.check_type.value == "RESTRICTED_LIST" for f in failures)
    
    @pytest.mark.asyncio
    async def test_market_hours_check(self, risk_validator):
        """Test market hours validation."""
        # Enable market hours checking
        risk_validator.config.enable_market_hours_check = True
        
        # Mock current time to be outside market hours
        # Create a mock datetime object for 3 AM ET (outside all trading hours)
        from unittest.mock import MagicMock
        
        # Create a proper mock that returns expected values
        mock_now = MagicMock()
        mock_now.time.return_value = time(3, 0)  # 3 AM
        mock_now.date.return_value = datetime(2023, 1, 2).date()  # Monday
        mock_now.weekday.return_value = 0  # Monday
        
        with patch('src.trader.order_management.risk_validator.datetime') as mock_dt:
            # Configure datetime class methods
            mock_dt.now.return_value = mock_now
            mock_dt.utcnow.return_value = mock_now
            # Keep the real timezone attribute
            mock_dt.timezone = timezone
            
            order = Order(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=100,
                order_type=OrderType.MARKET
            )
            
            result = await risk_validator.validate_order(order)
            
            # Should fail since we're outside market hours
            assert not result.passed
            failures = result.get_failures()
            assert any(f.check_type == RiskCheckType.MARKET_HOURS for f in failures)


class TestPositionTracker:
    """Test Position Tracker."""
    
    @pytest.fixture
    def position_tracker(self):
        return PositionTracker(cost_basis_method=CostBasisMethod.FIFO)
    
    @pytest.mark.asyncio
    async def test_process_buy_fill(self, position_tracker):
        """Test processing buy fills."""
        order = Order(
            order_id="O1",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        
        fill = Fill(
            fill_id="F1",
            timestamp=datetime.now(timezone.utc),
            quantity=100,
            price=Decimal("150.00"),
            commission=Decimal("1.00")
        )
        
        await position_tracker.process_fill(order, fill)
        
        position = await position_tracker.get_position("AAPL")
        assert position is not None
        assert position.quantity == 100
        assert position.average_cost == Decimal("150.00")
        assert position.total_bought == 100
        assert position.total_commission == Decimal("1.00")
        assert len(position.lots) == 1
    
    @pytest.mark.asyncio
    async def test_process_sell_fill_with_pnl(self, position_tracker):
        """Test processing sell fills with P&L calculation."""
        # First buy 100 shares
        buy_order = Order(
            order_id="O1",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        
        buy_fill = Fill(
            fill_id="F1",
            timestamp=datetime.now(timezone.utc),
            quantity=100,
            price=Decimal("150.00")
        )
        
        await position_tracker.process_fill(buy_order, buy_fill)
        
        # Then sell 50 shares at higher price
        sell_order = Order(
            order_id="O2",
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=50,
            order_type=OrderType.MARKET
        )
        
        sell_fill = Fill(
            fill_id="F2",
            timestamp=datetime.now(timezone.utc),
            quantity=50,
            price=Decimal("155.00")
        )
        
        await position_tracker.process_fill(sell_order, sell_fill)
        
        position = await position_tracker.get_position("AAPL")
        assert position.quantity == 50
        assert position.realized_pnl == Decimal("250.00")  # (155-150) * 50
        assert position.total_sold == 50
        assert len(position.lots) == 1  # One lot remaining
    
    @pytest.mark.asyncio
    async def test_fifo_cost_basis(self, position_tracker):
        """Test FIFO cost basis calculation."""
        # Buy 100 @ $150
        order1 = Order(
            order_id="O1",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        fill1 = Fill(
            fill_id="F1",
            timestamp=datetime.now(timezone.utc),
            quantity=100,
            price=Decimal("150.00")
        )
        await position_tracker.process_fill(order1, fill1)
        
        # Buy 100 @ $160
        order2 = Order(
            order_id="O2",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        fill2 = Fill(
            fill_id="F2",
            timestamp=datetime.now(timezone.utc),
            quantity=100,
            price=Decimal("160.00")
        )
        await position_tracker.process_fill(order2, fill2)
        
        # Sell 150 @ $165 (should use FIFO)
        sell_order = Order(
            order_id="O3",
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=150,
            order_type=OrderType.MARKET
        )
        sell_fill = Fill(
            fill_id="F3",
            timestamp=datetime.now(timezone.utc),
            quantity=150,
            price=Decimal("165.00")
        )
        await position_tracker.process_fill(sell_order, sell_fill)
        
        position = await position_tracker.get_position("AAPL")
        assert position.quantity == 50
        # P&L: 100 * (165-150) + 50 * (165-160) = 1500 + 250 = 1750
        assert position.realized_pnl == Decimal("1750.00")
        assert position.average_cost == Decimal("160.00")  # Remaining lot
    
    @pytest.mark.asyncio
    async def test_position_metrics(self, position_tracker):
        """Test position metrics calculation."""
        # Create multiple positions
        orders_fills = [
            ("AAPL", OrderSide.BUY, 100, "150.00"),
            ("GOOGL", OrderSide.BUY, 50, "2500.00"),
            ("MSFT", OrderSide.SELL_SHORT, 75, "300.00")
        ]
        
        for i, (symbol, side, qty, price) in enumerate(orders_fills):
            order = Order(
                order_id=f"O{i}",
                symbol=symbol,
                side=side,
                quantity=qty,
                order_type=OrderType.MARKET
            )
            fill = Fill(
                fill_id=f"F{i}",
                timestamp=datetime.now(timezone.utc),
                quantity=qty,
                price=Decimal(price)
            )
            await position_tracker.process_fill(order, fill)
        
        # Test metrics
        assert await position_tracker.get_position_count() == 3
        
        total_value = await position_tracker.get_total_market_value()
        expected = (100 * Decimal("150")) + (50 * Decimal("2500")) - (75 * Decimal("300"))
        assert total_value == expected
    
    @pytest.mark.asyncio
    async def test_daily_pnl_tracking(self, position_tracker):
        """Test daily P&L tracking."""
        # Buy and sell for realized P&L
        buy_order = Order(
            order_id="O1",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        buy_fill = Fill(
            fill_id="F1",
            timestamp=datetime.now(timezone.utc),
            quantity=100,
            price=Decimal("150.00")
        )
        await position_tracker.process_fill(buy_order, buy_fill)
        
        sell_order = Order(
            order_id="O2",
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=50,
            order_type=OrderType.MARKET
        )
        sell_fill = Fill(
            fill_id="F2",
            timestamp=datetime.now(timezone.utc),
            quantity=50,
            price=Decimal("155.00"),
            commission=Decimal("1.00")
        )
        await position_tracker.process_fill(sell_order, sell_fill)
        
        # Update market price for unrealized P&L
        position = await position_tracker.get_position("AAPL")
        position.update_market_price(Decimal("160.00"))
        
        daily_pnl = await position_tracker.get_daily_pnl()
        # Realized: (155-150) * 50 = 250
        # Unrealized: (160-150) * 50 = 500
        # Commission: -1
        # Total before commission: 750
        assert daily_pnl == Decimal("750.00")  # Commission tracked separately


@pytest.mark.asyncio
async def test_oms_integration():
    """Test full OMS integration."""
    # Create components
    risk_config = RiskConfig(
        max_order_size=1000,
        max_position_size=5000
    )
    
    position_tracker = PositionTracker()
    risk_validator = PreTradeRiskValidator(
        config=risk_config,
        position_tracker=position_tracker
    )
    
    order_service = OrderService(
        risk_validator=risk_validator,
        broker_client=Mock(),
        position_tracker=position_tracker
    )
    
    # Create and process order
    order = await order_service.create_order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("150.00")
    )
    
    # Validate
    validation_result = await order_service.validate_order(order.order_id)
    assert validation_result.passed
    
    # Submit
    success = await order_service.submit_order(order.order_id)
    assert success
    
    # Process fill
    await order_service.process_fill(
        order_id=order.order_id,
        fill_quantity=100,
        fill_price=Decimal("150.00"),
        commission=Decimal("1.00")
    )
    
    # Check position
    position = await position_tracker.get_position("AAPL")
    assert position is not None
    assert position.quantity == 100
    assert position.average_cost == Decimal("150.00")
    
    # Check order state
    assert order.state == OrderState.FILLED
    assert order.filled_quantity == 100
    
    # Check statistics
    stats = order_service.get_statistics()
    assert stats['total'] == 1
    assert stats['filled'] == 1
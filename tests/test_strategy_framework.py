"""Comprehensive tests for the trading strategy framework."""

import asyncio
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any

from src.strategy import (
    BaseStrategy,
    Signal,
    Position,
    Trade,
    Order,
    OrderSide,
    OrderType,
    OrderStatus,
    SignalStrength
)
from src.strategy.backtesting import BacktestEngine, TradeSimulator
from src.data.models import TimeFrame


class MockStrategy(BaseStrategy):
    """Mock strategy for testing."""
    
    def __init__(self, **kwargs):
        super().__init__(
            name="MockStrategy",
            symbols=["AAPL", "MSFT"],
            timeframe=TimeFrame.ONE_MIN,
            **kwargs
        )
        self.candle_count = 0
        self.should_generate_signal = False
        self.signal_direction = OrderSide.BUY
    
    async def on_candle(self, symbol: str, candle: Dict[str, Any]) -> None:
        """Process new candle."""
        self.candle_count += 1
        self.update_candle_history(symbol, candle)
    
    async def generate_signals(self) -> List[Signal]:
        """Generate test signals."""
        signals = []
        
        if self.should_generate_signal and self.candle_count > 5:
            for symbol in self.symbols:
                signal = Signal(
                    symbol=symbol,
                    direction=self.signal_direction,
                    strength=0.8,
                    timestamp=datetime.now(),
                    strategy_name=self.name,
                    stop_loss=95.0 if self.signal_direction == OrderSide.BUY else 105.0,
                    take_profit=105.0 if self.signal_direction == OrderSide.BUY else 95.0,
                    reason="Test signal",
                    confidence=0.9
                )
                signals.append(signal)
        
        return signals
    
    def calculate_position_size(self, signal: Signal) -> float:
        """Calculate position size."""
        max_value = self.get_max_position_value()
        # Use 50% of max position value
        position_value = max_value * 0.5
        # Assume price is 100 for testing
        return position_value / 100.0


class TestBaseStrategy:
    """Test BaseStrategy functionality."""
    
    @pytest.mark.asyncio
    async def test_strategy_initialization(self):
        """Test strategy initialization."""
        strategy = MockStrategy(
            initial_capital=50000,
            max_position_size=0.2,
            stop_loss_pct=0.03,
            take_profit_pct=0.06
        )
        
        assert strategy.name == "MockStrategy"
        assert strategy.symbols == ["AAPL", "MSFT"]
        assert strategy.initial_capital == 50000
        assert strategy.current_capital == 50000
        assert strategy.max_position_size == 0.2
        assert strategy.stop_loss_pct == 0.03
        assert strategy.take_profit_pct == 0.06
        assert len(strategy.positions) == 0
        assert strategy.total_trades == 0
    
    @pytest.mark.asyncio
    async def test_candle_processing(self):
        """Test candle processing and history."""
        strategy = MockStrategy()
        
        # Process some candles
        for i in range(10):
            candle = {
                'timestamp': datetime.now(),
                'open': Decimal('100'),
                'high': Decimal('101'),
                'low': Decimal('99'),
                'close': Decimal('100.5'),
                'volume': 1000
            }
            await strategy.on_candle("AAPL", candle)
        
        assert strategy.candle_count == 10
        assert len(strategy.candle_history["AAPL"]) == 10
    
    @pytest.mark.asyncio
    async def test_signal_generation(self):
        """Test signal generation."""
        strategy = MockStrategy()
        strategy.should_generate_signal = True
        
        # Process enough candles to trigger signals
        for i in range(10):
            candle = {
                'timestamp': datetime.now(),
                'open': Decimal('100'),
                'high': Decimal('101'),
                'low': Decimal('99'),
                'close': Decimal('100.5'),
                'volume': 1000
            }
            await strategy.on_candle("AAPL", candle)
        
        # Generate signals
        signals = await strategy.generate_signals()
        
        assert len(signals) == 2  # One for each symbol
        assert all(s.direction == OrderSide.BUY for s in signals)
        assert all(s.strength == 0.8 for s in signals)
        assert all(s.confidence == 0.9 for s in signals)
        assert signals[0].stop_loss == 95.0
        assert signals[0].take_profit == 105.0
    
    @pytest.mark.asyncio
    async def test_position_management(self):
        """Test position tracking."""
        strategy = MockStrategy()
        
        # Simulate order fill
        order = {
            'symbol': 'AAPL',
            'side': 'BUY',
            'price': Decimal('100'),
            'quantity': Decimal('100'),
            'timestamp': datetime.now()
        }
        
        await strategy.on_order_filled(order)
        
        assert strategy.has_position('AAPL')
        assert not strategy.has_position('MSFT')
        
        position = strategy.get_position('AAPL')
        assert position is not None
        assert position['entry_price'] == Decimal('100')
        assert position['quantity'] == Decimal('100')
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self):
        """Test performance metric calculation."""
        strategy = MockStrategy()
        
        # Simulate some trades
        # Buy
        buy_order = {
            'symbol': 'AAPL',
            'side': 'BUY',
            'price': Decimal('100'),
            'quantity': Decimal('100'),
            'timestamp': datetime.now()
        }
        await strategy.on_order_filled(buy_order)
        
        # Sell with profit
        sell_order = {
            'symbol': 'AAPL',
            'side': 'SELL',
            'price': Decimal('105'),
            'quantity': Decimal('100'),
            'timestamp': datetime.now()
        }
        await strategy.on_order_filled(sell_order)
        
        metrics = strategy.get_performance_metrics()
        
        assert metrics['total_trades'] == 1
        assert metrics['winning_trades'] == 1
        assert metrics['losing_trades'] == 0
        assert metrics['win_rate'] == 1.0
        assert metrics['total_profit'] == 500  # (105-100) * 100
        assert metrics['current_capital'] == 100500  # 100000 + 500


class TestSignalModel:
    """Test Signal model."""
    
    def test_signal_creation(self):
        """Test signal creation and validation."""
        signal = Signal(
            symbol="AAPL",
            direction=OrderSide.BUY,
            strength=0.8,
            timestamp=datetime.now(),
            strategy_name="TestStrategy",
            stop_loss=95.0,
            take_profit=105.0,
            confidence=0.9
        )
        
        assert signal.symbol == "AAPL"
        assert signal.direction == OrderSide.BUY
        assert signal.strength == 0.8
        assert signal.confidence == 0.9
        assert not signal.is_expired()
    
    def test_signal_validation(self):
        """Test signal validation."""
        # Invalid strength
        with pytest.raises(ValueError):
            Signal(
                symbol="AAPL",
                direction=OrderSide.BUY,
                strength=1.5,  # > 1.0
                timestamp=datetime.now(),
                strategy_name="TestStrategy"
            )
        
        # Invalid confidence
        with pytest.raises(ValueError):
            Signal(
                symbol="AAPL",
                direction=OrderSide.BUY,
                strength=0.8,
                timestamp=datetime.now(),
                strategy_name="TestStrategy",
                confidence=2.0  # > 1.0
            )
    
    def test_signal_expiration(self):
        """Test signal expiration."""
        signal = Signal(
            symbol="AAPL",
            direction=OrderSide.BUY,
            strength=0.8,
            timestamp=datetime.now(),
            strategy_name="TestStrategy",
            expires_at=datetime.now() - timedelta(minutes=1)
        )
        
        assert signal.is_expired()


class TestPositionModel:
    """Test Position model."""
    
    def test_position_pnl_calculation(self):
        """Test P&L calculations."""
        # Long position
        position = Position(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=Decimal('100'),
            entry_price=Decimal('100'),
            entry_time=datetime.now(),
            current_price=Decimal('105'),
            entry_commission=Decimal('10')
        )
        
        assert position.market_value == Decimal('10500')  # 100 * 105
        assert position.entry_value == Decimal('10000')  # 100 * 100
        assert position.unrealized_pnl == Decimal('490')  # (105-100)*100 - 10
        assert position.is_profitable()
        
        # Short position
        short_position = Position(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=Decimal('100'),
            entry_price=Decimal('100'),
            entry_time=datetime.now(),
            current_price=Decimal('95'),
            entry_commission=Decimal('10')
        )
        
        assert short_position.unrealized_pnl == Decimal('490')  # (100-95)*100 - 10
        assert short_position.is_profitable()


class TestTradeModel:
    """Test Trade model."""
    
    def test_trade_pnl_calculation(self):
        """Test trade P&L calculations."""
        # Winning long trade
        trade = Trade(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=Decimal('100'),
            entry_price=Decimal('100'),
            entry_time=datetime.now() - timedelta(hours=1),
            entry_commission=Decimal('10'),
            exit_price=Decimal('110'),
            exit_time=datetime.now(),
            exit_commission=Decimal('11')
        )
        
        assert trade.gross_pnl == Decimal('1000')  # (110-100)*100
        assert trade.net_pnl == Decimal('979')  # 1000 - 10 - 11
        assert trade.total_commission == Decimal('21')
        assert trade.is_winner()
        assert trade.duration == 3600.0  # 1 hour in seconds
        
        # Losing short trade
        losing_trade = Trade(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=Decimal('100'),
            entry_price=Decimal('100'),
            entry_time=datetime.now() - timedelta(minutes=30),
            entry_commission=Decimal('10'),
            exit_price=Decimal('105'),
            exit_time=datetime.now(),
            exit_commission=Decimal('10.5')
        )
        
        assert losing_trade.gross_pnl == Decimal('-500')  # (100-105)*100
        assert losing_trade.net_pnl == Decimal('-520.5')  # -500 - 10 - 10.5
        assert not losing_trade.is_winner()


class TestTradeSimulator:
    """Test TradeSimulator."""
    
    @pytest.mark.asyncio
    async def test_market_order_execution(self):
        """Test market order execution."""
        simulator = TradeSimulator(
            commission_rate=0.001,
            slippage_rate=0.0005
        )
        
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=Decimal('100'),
            order_type=OrderType.MARKET
        )
        
        current_price = Decimal('100')
        executed = await simulator.execute_trade(order, current_price)
        
        assert executed.status == OrderStatus.FILLED
        assert executed.filled_quantity == Decimal('100')
        assert executed.average_fill_price > current_price  # Due to slippage
        assert executed.commission >= Decimal('1')  # Minimum commission
    
    @pytest.mark.asyncio
    async def test_limit_order_execution(self):
        """Test limit order execution."""
        simulator = TradeSimulator()
        
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=Decimal('100'),
            order_type=OrderType.LIMIT,
            price=Decimal('99')
        )
        
        # Price above limit - should not fill
        executed = await simulator.execute_trade(order, Decimal('100'))
        assert executed.status == OrderStatus.SUBMITTED
        
        # Price at limit - should fill
        executed = await simulator.execute_trade(order, Decimal('99'))
        assert executed.status == OrderStatus.FILLED
        assert executed.average_fill_price <= Decimal('99')
    
    def test_slippage_calculation(self):
        """Test slippage calculation."""
        simulator = TradeSimulator(slippage_rate=0.001)  # 0.1%
        
        # Small order
        slippage = simulator.apply_slippage(
            OrderType.MARKET,
            OrderSide.BUY,
            Decimal('100'),
            Decimal('100')
        )
        
        assert slippage > 0
        assert slippage < Decimal('0.2')  # Less than 0.2%
        
        # Large order should have more slippage
        large_slippage = simulator.apply_slippage(
            OrderType.MARKET,
            OrderSide.BUY,
            Decimal('100'),
            Decimal('10000')
        )
        
        assert large_slippage > slippage
    
    def test_commission_calculation(self):
        """Test commission calculation."""
        # Tiered commission
        simulator = TradeSimulator(
            use_tiered_commission=True,
            maker_fee=0.0008,
            taker_fee=0.001,
            min_commission=1.0
        )
        
        # Maker order
        maker_commission = simulator.calculate_commission(
            OrderType.LIMIT,
            Decimal('100'),
            Decimal('100')
        )
        
        # Taker order
        taker_commission = simulator.calculate_commission(
            OrderType.MARKET,
            Decimal('100'),
            Decimal('100')
        )
        
        assert taker_commission > maker_commission
        assert maker_commission == Decimal('8')  # 100 * 100 * 0.0008
        assert taker_commission == Decimal('10')  # 100 * 100 * 0.001
        
        # Test minimum commission
        small_commission = simulator.calculate_commission(
            OrderType.MARKET,
            Decimal('1'),
            Decimal('10')
        )
        assert small_commission == Decimal('1')  # Minimum


class TestBacktestEngine:
    """Test BacktestEngine."""
    
    @pytest.mark.asyncio
    async def test_empty_backtest(self):
        """Test backtest with no data."""
        engine = BacktestEngine()
        strategy = MockStrategy()
        
        result = await engine.run_backtest(
            strategy,
            datetime.now() - timedelta(days=30),
            datetime.now()
        )
        
        assert result.total_trades == 0
        assert result.final_capital == result.initial_capital
        assert result.total_return_pct == 0.0
    
    def test_performance_analysis(self):
        """Test performance metric calculations."""
        engine = BacktestEngine()
        strategy = MockStrategy()
        
        # Create some test trades
        trades = [
            Trade(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=Decimal('100'),
                entry_price=Decimal('100'),
                entry_time=datetime.now() - timedelta(days=5),
                exit_price=Decimal('110'),
                exit_time=datetime.now() - timedelta(days=4),
                entry_commission=Decimal('10'),
                exit_commission=Decimal('11')
            ),
            Trade(
                symbol="MSFT",
                side=OrderSide.BUY,
                quantity=Decimal('50'),
                entry_price=Decimal('200'),
                entry_time=datetime.now() - timedelta(days=3),
                exit_price=Decimal('195'),
                exit_time=datetime.now() - timedelta(days=2),
                entry_commission=Decimal('10'),
                exit_commission=Decimal('9.75')
            )
        ]
        
        # Update strategy state
        strategy.current_capital = 100479  # Initial 100000 + profit from trades
        
        result = engine.analyze_performance(
            strategy=strategy,
            trades=trades,
            equity_curve=[],
            daily_returns=[0.01, -0.005, 0.02, -0.01, 0.015],
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            initial_capital=100000
        )
        
        assert result.total_trades == 2
        assert result.winning_trades == 1
        assert result.losing_trades == 1
        assert result.win_rate == 0.5
        assert result.profit_factor > 1.0  # More profit than loss
    
    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation."""
        engine = BacktestEngine(risk_free_rate=0.02)
        
        # Test with positive returns
        daily_returns = [0.01, 0.02, -0.01, 0.015, 0.005]
        sharpe = engine._calculate_sharpe_ratio(daily_returns, 0.02)
        
        assert sharpe > 0  # Positive Sharpe ratio
        
        # Test with negative returns
        negative_returns = [-0.01, -0.02, -0.015, -0.005, -0.01]
        negative_sharpe = engine._calculate_sharpe_ratio(negative_returns, 0.02)
        
        assert negative_sharpe < 0  # Negative Sharpe ratio
    
    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation."""
        engine = BacktestEngine()
        
        equity_curve = [
            {'timestamp': datetime.now() - timedelta(days=10), 'capital': 100000},
            {'timestamp': datetime.now() - timedelta(days=9), 'capital': 105000},
            {'timestamp': datetime.now() - timedelta(days=8), 'capital': 110000},
            {'timestamp': datetime.now() - timedelta(days=7), 'capital': 108000},
            {'timestamp': datetime.now() - timedelta(days=6), 'capital': 102000},
            {'timestamp': datetime.now() - timedelta(days=5), 'capital': 98000},  # Lowest
            {'timestamp': datetime.now() - timedelta(days=4), 'capital': 103000},
            {'timestamp': datetime.now() - timedelta(days=3), 'capital': 107000},
            {'timestamp': datetime.now() - timedelta(days=2), 'capital': 112000},
            {'timestamp': datetime.now() - timedelta(days=1), 'capital': 115000},
        ]
        
        max_dd, duration = engine._calculate_max_drawdown(equity_curve)
        
        assert max_dd > 10  # Drawdown from 110000 to 98000
        assert max_dd < 11  # Should be around 10.91%
        assert duration >= 4  # Days from peak to recovery


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
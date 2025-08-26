"""Base strategy abstract class for trading strategies."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from decimal import Decimal
import logging
from enum import Enum

from ..data.models import TimeFrame


logger = logging.getLogger(__name__)


class StrategyState(Enum):
    """Strategy state enumeration."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    This class provides the framework for implementing trading strategies
    that can work with both live data and backtesting.
    """
    
    def __init__(
        self,
        name: str,
        symbols: List[str],
        timeframe: TimeFrame = TimeFrame.ONE_MIN,
        initial_capital: float = 100000.0,
        max_position_size: float = 0.1,  # 10% of capital per position
        stop_loss_pct: float = 0.02,  # 2% stop loss
        take_profit_pct: float = 0.05,  # 5% take profit
        **kwargs
    ):
        """
        Initialize base strategy.
        
        Args:
            name: Strategy name
            symbols: List of symbols to trade
            timeframe: Primary timeframe for the strategy
            initial_capital: Starting capital
            max_position_size: Maximum position size as percentage of capital
            stop_loss_pct: Default stop loss percentage
            take_profit_pct: Default take profit percentage
            **kwargs: Additional strategy-specific parameters
        """
        self.name = name
        self.symbols = symbols
        self.timeframe = timeframe
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_position_size = max_position_size
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        
        # Strategy state
        self.state = StrategyState.STOPPED
        self.positions = {}  # symbol -> Position
        self.pending_orders = {}  # order_id -> Order
        self.trade_history = []  # List of completed trades
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = Decimal('0')
        
        # Data storage
        self.candle_history = {}  # symbol -> List[candle]
        self.indicators = {}  # symbol -> {indicator_name: value}
        
        # Additional parameters
        self.params = kwargs
        
        logger.info(f"Strategy '{name}' initialized with symbols: {symbols}")
    
    @abstractmethod
    async def on_candle(self, symbol: str, candle: Dict[str, Any]) -> None:
        """
        Called when a new candle is received.
        
        Args:
            symbol: Trading symbol
            candle: Candle data with keys: timestamp, open, high, low, close, volume
        """
        pass
    
    @abstractmethod
    async def generate_signals(self) -> List[Dict[str, Any]]:
        """
        Generate trading signals based on current market data.
        
        Returns:
            List of Signal dictionaries
        """
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: Dict[str, Any]) -> float:
        """
        Calculate position size for a given signal.
        
        Args:
            signal: Trading signal
            
        Returns:
            Position size in units
        """
        pass
    
    async def on_tick(self, symbol: str, tick: Dict[str, Any]) -> None:
        """
        Called when a new tick is received (optional override).
        
        Args:
            symbol: Trading symbol
            tick: Tick data
        """
        pass
    
    async def on_order_filled(self, order: Dict[str, Any]) -> None:
        """
        Called when an order is filled.
        
        Args:
            order: Filled order details
        """
        symbol = order['symbol']
        
        if order['side'] == 'BUY':
            self.positions[symbol] = {
                'symbol': symbol,
                'entry_price': order['price'],
                'quantity': order['quantity'],
                'entry_time': order['timestamp'],
                'unrealized_pnl': Decimal('0')
            }
        elif order['side'] == 'SELL' and symbol in self.positions:
            position = self.positions.pop(symbol)
            pnl = (order['price'] - position['entry_price']) * position['quantity']
            
            self.total_trades += 1
            if pnl > 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1
            
            self.total_profit += pnl
            self.current_capital += float(pnl)
            
            self.trade_history.append({
                'symbol': symbol,
                'entry_price': position['entry_price'],
                'exit_price': order['price'],
                'quantity': position['quantity'],
                'pnl': pnl,
                'entry_time': position['entry_time'],
                'exit_time': order['timestamp']
            })
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current position for a symbol."""
        return self.positions.get(symbol)
    
    def has_position(self, symbol: str) -> bool:
        """Check if strategy has position in symbol."""
        return symbol in self.positions
    
    def calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """
        Calculate stop loss price.
        
        Args:
            entry_price: Entry price
            side: 'BUY' or 'SELL'
            
        Returns:
            Stop loss price
        """
        if side == 'BUY':
            return entry_price * (1 - self.stop_loss_pct)
        else:
            return entry_price * (1 + self.stop_loss_pct)
    
    def calculate_take_profit(self, entry_price: float, side: str) -> float:
        """
        Calculate take profit price.
        
        Args:
            entry_price: Entry price
            side: 'BUY' or 'SELL'
            
        Returns:
            Take profit price
        """
        if side == 'BUY':
            return entry_price * (1 + self.take_profit_pct)
        else:
            return entry_price * (1 - self.take_profit_pct)
    
    def get_max_position_value(self) -> float:
        """Get maximum position value based on current capital."""
        return self.current_capital * self.max_position_size
    
    def update_candle_history(self, symbol: str, candle: Dict[str, Any], max_candles: int = 1000):
        """
        Update candle history for a symbol.
        
        Args:
            symbol: Trading symbol
            candle: Candle data
            max_candles: Maximum candles to keep in history
        """
        if symbol not in self.candle_history:
            self.candle_history[symbol] = []
        
        self.candle_history[symbol].append(candle)
        
        # Keep only recent candles
        if len(self.candle_history[symbol]) > max_candles:
            self.candle_history[symbol] = self.candle_history[symbol][-max_candles:]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics.
        
        Returns:
            Dictionary of performance metrics
        """
        win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        avg_win = 0
        avg_loss = 0
        
        if self.trade_history:
            wins = [t['pnl'] for t in self.trade_history if t['pnl'] > 0]
            losses = [t['pnl'] for t in self.trade_history if t['pnl'] <= 0]
            
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
        
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'total_profit': float(self.total_profit),
            'current_capital': self.current_capital,
            'return_pct': ((self.current_capital - self.initial_capital) / self.initial_capital) * 100,
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        }
    
    async def start(self) -> None:
        """Start the strategy."""
        logger.info(f"Starting strategy '{self.name}'")
        self.state = StrategyState.RUNNING
    
    async def stop(self) -> None:
        """Stop the strategy."""
        logger.info(f"Stopping strategy '{self.name}'")
        self.state = StrategyState.STOPPED
    
    async def pause(self) -> None:
        """Pause the strategy."""
        logger.info(f"Pausing strategy '{self.name}'")
        self.state = StrategyState.PAUSED
    
    def is_running(self) -> bool:
        """Check if strategy is running."""
        return self.state == StrategyState.RUNNING
    
    def reset(self) -> None:
        """Reset strategy state."""
        self.current_capital = self.initial_capital
        self.positions.clear()
        self.pending_orders.clear()
        self.trade_history.clear()
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = Decimal('0')
        self.candle_history.clear()
        self.indicators.clear()
        self.state = StrategyState.STOPPED
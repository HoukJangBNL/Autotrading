"""Backtesting engine for strategy evaluation."""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd
from dataclasses import dataclass, field

from ..base import BaseStrategy
from ..models import Signal, Trade, Position, Order, OrderSide, OrderStatus
from ...data.models import Candle, TimeFrame
from ...data.database import get_db


logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Container for backtest results."""
    # Basic info
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    
    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # Returns
    total_return: float
    total_return_pct: float
    annualized_return: float
    
    # Risk metrics
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int  # days
    
    # Trade analysis
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_trade_duration: float  # hours
    profit_factor: float
    
    # Additional metrics
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'strategy_name': self.strategy_name,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'total_return': self.total_return,
            'total_return_pct': self.total_return_pct,
            'annualized_return': self.annualized_return,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_duration': self.max_drawdown_duration,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'avg_trade_duration': self.avg_trade_duration,
            'profit_factor': self.profit_factor,
            'total_trades_data': [t.to_dict() for t in self.trades],
            'equity_curve': self.equity_curve,
            'daily_returns': self.daily_returns
        }


class BacktestEngine:
    """
    Engine for running strategy backtests.
    
    Simulates strategy execution on historical data with realistic
    market conditions including slippage and commissions.
    """
    
    def __init__(
        self,
        commission_rate: float = 0.001,  # 0.1%
        slippage_rate: float = 0.0005,  # 0.05%
        starting_cash: float = 100000.0,
        risk_free_rate: float = 0.02  # 2% annual risk-free rate
    ):
        """
        Initialize backtest engine.
        
        Args:
            commission_rate: Commission rate per trade
            slippage_rate: Slippage rate per trade
            starting_cash: Starting capital
            risk_free_rate: Risk-free rate for Sharpe calculation
        """
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.starting_cash = starting_cash
        self.risk_free_rate = risk_free_rate
        
        # Trade simulator (will be initialized later)
        self.simulator = None
    
    async def run_backtest(
        self,
        strategy: BaseStrategy,
        start_date: datetime,
        end_date: datetime,
        symbols: Optional[List[str]] = None
    ) -> BacktestResult:
        """
        Run backtest for a strategy.
        
        Args:
            strategy: Strategy instance to test
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: Symbols to test (None uses strategy's symbols)
            
        Returns:
            BacktestResult with performance metrics
        """
        logger.info(f"Starting backtest for {strategy.name} from {start_date} to {end_date}")
        
        # Initialize strategy
        strategy.reset()
        strategy.current_capital = self.starting_cash
        await strategy.start()
        
        # Use strategy's symbols if not provided
        if symbols is None:
            symbols = strategy.symbols
        
        # Initialize trade simulator
        from .simulator import TradeSimulator
        self.simulator = TradeSimulator(
            commission_rate=self.commission_rate,
            slippage_rate=self.slippage_rate
        )
        
        # Track backtest state
        equity_curve = []
        daily_returns = []
        trades = []
        positions = {}  # symbol -> Position
        
        # Load historical data
        candles_data = await self._load_historical_data(
            symbols, start_date, end_date, strategy.timeframe
        )
        
        if not candles_data:
            logger.error("No historical data found for backtest")
            return self._create_empty_result(strategy, start_date, end_date)
        
        # Sort all candles by timestamp
        all_candles = []
        for symbol, candles in candles_data.items():
            for candle in candles:
                candle['symbol'] = symbol
                all_candles.append(candle)
        
        all_candles.sort(key=lambda x: x['timestamp'])
        
        # Process candles chronologically
        last_equity = self.starting_cash
        last_date = start_date.date()
        
        for candle in all_candles:
            current_date = candle['timestamp'].date()
            
            # Calculate daily returns
            if current_date != last_date:
                daily_return = (strategy.current_capital - last_equity) / last_equity
                daily_returns.append(daily_return)
                last_equity = strategy.current_capital
                last_date = current_date
            
            # Update strategy with new candle
            await strategy.on_candle(candle['symbol'], candle)
            
            # Update position prices
            if candle['symbol'] in positions:
                positions[candle['symbol']].update_price(candle['close'])
            
            # Generate signals
            if strategy.is_running():
                signals = await strategy.generate_signals()
                
                # Process signals
                for signal in signals:
                    order = await self._process_signal(
                        strategy, signal, candle, positions
                    )
                    
                    if order and order.is_filled():
                        # Update positions
                        if order.side == OrderSide.BUY:
                            positions[order.symbol] = Position(
                                symbol=order.symbol,
                                side=order.side,
                                quantity=order.filled_quantity,
                                entry_price=order.average_fill_price,
                                entry_time=candle['timestamp'],
                                strategy_name=strategy.name,
                                entry_commission=order.commission
                            )
                        elif order.side == OrderSide.SELL and order.symbol in positions:
                            position = positions.pop(order.symbol)
                            
                            # Create trade record
                            trade = Trade(
                                symbol=order.symbol,
                                side=position.side,
                                quantity=position.quantity,
                                entry_price=position.entry_price,
                                entry_time=position.entry_time,
                                entry_commission=position.entry_commission,
                                exit_price=order.average_fill_price,
                                exit_time=candle['timestamp'],
                                exit_commission=order.commission,
                                strategy_name=strategy.name
                            )
                            trades.append(trade)
                            
                            # Update strategy capital
                            strategy.current_capital += float(trade.net_pnl)
            
            # Check stop loss and take profit
            positions_to_close = []
            for symbol, position in positions.items():
                if self._should_close_position(position, candle):
                    positions_to_close.append(symbol)
            
            # Close positions that hit stop/target
            for symbol in positions_to_close:
                position = positions.pop(symbol)
                
                # Simulate exit order
                exit_order = await self.simulator.execute_trade(
                    Order(
                        symbol=symbol,
                        side=OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY,
                        quantity=position.quantity,
                        order_type=OrderType.MARKET,
                        strategy_name=strategy.name
                    ),
                    candle['close']
                )
                
                # Create trade record
                trade = Trade(
                    symbol=symbol,
                    side=position.side,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    entry_time=position.entry_time,
                    entry_commission=position.entry_commission,
                    exit_price=exit_order.average_fill_price,
                    exit_time=candle['timestamp'],
                    exit_commission=exit_order.commission,
                    strategy_name=strategy.name,
                    stop_loss_hit=position.stop_loss and candle['low'] <= position.stop_loss,
                    take_profit_hit=position.take_profit and candle['high'] >= position.take_profit
                )
                trades.append(trade)
                
                # Update strategy capital
                strategy.current_capital += float(trade.net_pnl)
            
            # Record equity curve
            equity_curve.append({
                'timestamp': candle['timestamp'],
                'capital': strategy.current_capital,
                'positions': len(positions),
                'trades': len(trades)
            })
        
        # Close any remaining positions at end
        for symbol, position in positions.items():
            last_candle = candles_data[symbol][-1]
            
            # Simulate exit order
            exit_order = await self.simulator.execute_trade(
                Order(
                    symbol=symbol,
                    side=OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY,
                    quantity=position.quantity,
                    order_type=OrderType.MARKET,
                    strategy_name=strategy.name
                ),
                last_candle['close']
            )
            
            # Create trade record
            trade = Trade(
                symbol=symbol,
                side=position.side,
                quantity=position.quantity,
                entry_price=position.entry_price,
                entry_time=position.entry_time,
                entry_commission=position.entry_commission,
                exit_price=exit_order.average_fill_price,
                exit_time=last_candle['timestamp'],
                exit_commission=exit_order.commission,
                strategy_name=strategy.name
            )
            trades.append(trade)
        
        # Stop strategy
        await strategy.stop()
        
        # Analyze performance
        result = self.analyze_performance(
            strategy=strategy,
            trades=trades,
            equity_curve=equity_curve,
            daily_returns=daily_returns,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.starting_cash
        )
        
        logger.info(f"Backtest complete. Total return: {result.total_return_pct:.2f}%")
        
        return result
    
    def analyze_performance(
        self,
        strategy: BaseStrategy,
        trades: List[Trade],
        equity_curve: List[Dict[str, Any]],
        daily_returns: List[float],
        start_date: datetime,
        end_date: datetime,
        initial_capital: float
    ) -> BacktestResult:
        """
        Analyze backtest performance.
        
        Args:
            strategy: Strategy instance
            trades: List of completed trades
            equity_curve: Equity curve data
            daily_returns: Daily return percentages
            start_date: Backtest start date
            end_date: Backtest end date
            initial_capital: Starting capital
            
        Returns:
            BacktestResult with calculated metrics
        """
        final_capital = strategy.current_capital
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100
        
        # Calculate basic statistics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.is_winner())
        losing_trades = total_trades - winning_trades
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # Calculate average win/loss
        wins = [float(t.net_pnl) for t in trades if t.is_winner()]
        losses = [float(t.net_pnl) for t in trades if not t.is_winner()]
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0
        
        # Calculate profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calculate average trade duration
        if trades:
            durations = [(t.exit_time - t.entry_time).total_seconds() / 3600 for t in trades]
            avg_trade_duration = np.mean(durations)
        else:
            avg_trade_duration = 0
        
        # Calculate annualized return
        days = (end_date - start_date).days
        years = days / 365.25
        annualized_return = ((final_capital / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0
        
        # Calculate risk metrics
        sharpe_ratio = self._calculate_sharpe_ratio(daily_returns, self.risk_free_rate)
        sortino_ratio = self._calculate_sortino_ratio(daily_returns, self.risk_free_rate)
        max_drawdown, max_dd_duration = self._calculate_max_drawdown(equity_curve)
        
        return BacktestResult(
            strategy_name=strategy.name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_dd_duration,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_trade_duration=avg_trade_duration,
            profit_factor=profit_factor,
            trades=trades,
            equity_curve=equity_curve,
            daily_returns=daily_returns
        )
    
    async def _load_historical_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        timeframe: TimeFrame
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Load historical candle data."""
        async with get_db() as session:
            candles_data = {}
            
            for symbol in symbols:
                # Query candles from database
                result = await session.execute(
                    """
                    SELECT timestamp, open, high, low, close, volume
                    FROM candles
                    WHERE symbol = :symbol
                    AND timeframe = :timeframe
                    AND timestamp >= :start
                    AND timestamp <= :end
                    ORDER BY timestamp
                    """,
                    {
                        'symbol': symbol,
                        'timeframe': timeframe.value,
                        'start': start_date,
                        'end': end_date
                    }
                )
                
                candles = []
                for row in result:
                    candles.append({
                        'timestamp': row.timestamp,
                        'open': Decimal(str(row.open)),
                        'high': Decimal(str(row.high)),
                        'low': Decimal(str(row.low)),
                        'close': Decimal(str(row.close)),
                        'volume': row.volume
                    })
                
                if candles:
                    candles_data[symbol] = candles
                    logger.info(f"Loaded {len(candles)} candles for {symbol}")
                else:
                    logger.warning(f"No candles found for {symbol}")
            
            return candles_data
    
    async def _process_signal(
        self,
        strategy: BaseStrategy,
        signal: Signal,
        current_candle: Dict[str, Any],
        positions: Dict[str, Position]
    ) -> Optional[Order]:
        """Process a trading signal."""
        # Skip if already have position
        if signal.symbol in positions:
            return None
        
        # Calculate position size
        position_size = strategy.calculate_position_size(signal)
        
        if position_size <= 0:
            return None
        
        # Create order
        order = Order(
            symbol=signal.symbol,
            side=signal.direction,
            quantity=Decimal(str(position_size)),
            order_type=OrderType.MARKET,
            strategy_name=strategy.name,
            signal_id=signal.signal_id,
            stop_loss=Decimal(str(signal.stop_loss)) if signal.stop_loss else None,
            take_profit=Decimal(str(signal.take_profit)) if signal.take_profit else None
        )
        
        # Simulate order execution
        filled_order = await self.simulator.execute_trade(
            order,
            current_candle['close']
        )
        
        # Update strategy on order fill
        if filled_order.is_filled():
            await strategy.on_order_filled(filled_order.to_dict())
        
        return filled_order
    
    def _should_close_position(
        self,
        position: Position,
        candle: Dict[str, Any]
    ) -> bool:
        """Check if position should be closed based on stop/target."""
        if position.stop_loss:
            if position.side == OrderSide.BUY and candle['low'] <= position.stop_loss:
                return True
            elif position.side == OrderSide.SELL and candle['high'] >= position.stop_loss:
                return True
        
        if position.take_profit:
            if position.side == OrderSide.BUY and candle['high'] >= position.take_profit:
                return True
            elif position.side == OrderSide.SELL and candle['low'] <= position.take_profit:
                return True
        
        return False
    
    def _calculate_sharpe_ratio(
        self,
        daily_returns: List[float],
        risk_free_rate: float
    ) -> float:
        """Calculate Sharpe ratio."""
        if not daily_returns:
            return 0.0
        
        returns_array = np.array(daily_returns)
        excess_returns = returns_array - (risk_free_rate / 252)  # Daily risk-free rate
        
        if len(excess_returns) < 2:
            return 0.0
        
        return_std = np.std(excess_returns, ddof=1)
        if return_std == 0:
            return 0.0
        
        sharpe = np.mean(excess_returns) / return_std * np.sqrt(252)  # Annualized
        return float(sharpe)
    
    def _calculate_sortino_ratio(
        self,
        daily_returns: List[float],
        risk_free_rate: float
    ) -> float:
        """Calculate Sortino ratio (downside risk adjusted)."""
        if not daily_returns:
            return 0.0
        
        returns_array = np.array(daily_returns)
        excess_returns = returns_array - (risk_free_rate / 252)
        
        # Calculate downside deviation
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) < 2:
            return 0.0
        
        downside_std = np.std(downside_returns, ddof=1)
        if downside_std == 0:
            return 0.0
        
        sortino = np.mean(excess_returns) / downside_std * np.sqrt(252)
        return float(sortino)
    
    def _calculate_max_drawdown(
        self,
        equity_curve: List[Dict[str, Any]]
    ) -> Tuple[float, int]:
        """Calculate maximum drawdown and duration."""
        if not equity_curve:
            return 0.0, 0
        
        # Extract capital values
        capitals = [point['capital'] for point in equity_curve]
        timestamps = [point['timestamp'] for point in equity_curve]
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(capitals)
        
        # Calculate drawdowns
        drawdowns = (capitals - running_max) / running_max * 100
        
        # Find maximum drawdown
        max_dd_idx = np.argmin(drawdowns)
        max_drawdown = abs(drawdowns[max_dd_idx])
        
        # Calculate drawdown duration
        if max_dd_idx > 0:
            # Find when drawdown started (last peak)
            start_idx = max_dd_idx
            while start_idx > 0 and capitals[start_idx] < running_max[start_idx]:
                start_idx -= 1
            
            # Find when drawdown ended (recovery)
            end_idx = max_dd_idx
            peak_value = running_max[max_dd_idx]
            while end_idx < len(capitals) - 1 and capitals[end_idx] < peak_value:
                end_idx += 1
            
            # Calculate duration in days
            duration = (timestamps[end_idx] - timestamps[start_idx]).days
        else:
            duration = 0
        
        return float(max_drawdown), duration
    
    def _create_empty_result(
        self,
        strategy: BaseStrategy,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """Create empty result when no data available."""
        return BacktestResult(
            strategy_name=strategy.name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.starting_cash,
            final_capital=self.starting_cash,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_return=0.0,
            total_return_pct=0.0,
            annualized_return=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            avg_win=0.0,
            avg_loss=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            avg_trade_duration=0.0,
            profit_factor=0.0
        )
"""Integration between Strategy Framework and API/WebSocket."""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import redis.asyncio as redis
from sqlalchemy.orm import Session

from ..strategy.base import BaseStrategy
from ..strategy.models import Signal, OrderSide
from ..data.models import TimeFrame
from ..data.database import get_db

logger = logging.getLogger(__name__)


class StrategyManager:
    """Manages strategy instances and their lifecycle."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.strategies: Dict[str, BaseStrategy] = {}
        self.strategy_tasks: Dict[str, asyncio.Task] = {}
        self.running = False
    
    async def start(self):
        """Start the strategy manager."""
        logger.info("Starting StrategyManager...")
        self.running = True
        
        # Subscribe to market data updates
        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe("market_data:*")
        
        # Start market data processing task
        self.market_data_task = asyncio.create_task(self._process_market_data())
        
        logger.info("StrategyManager started")
    
    async def stop(self):
        """Stop the strategy manager and all strategies."""
        logger.info("Stopping StrategyManager...")
        self.running = False
        
        # Stop all strategies
        for strategy_id in list(self.strategies.keys()):
            await self.stop_strategy(strategy_id)
        
        # Cancel market data task
        if hasattr(self, 'market_data_task'):
            self.market_data_task.cancel()
            try:
                await self.market_data_task
            except asyncio.CancelledError:
                pass
        
        # Unsubscribe from Redis
        if hasattr(self, 'pubsub'):
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        
        logger.info("StrategyManager stopped")
    
    async def add_strategy(
        self,
        strategy_id: str,
        strategy_instance: BaseStrategy
    ) -> None:
        """Add a strategy instance to be managed."""
        if strategy_id in self.strategies:
            raise ValueError(f"Strategy {strategy_id} already exists")
        
        self.strategies[strategy_id] = strategy_instance
        
        # Initialize strategy
        await strategy_instance.initialize()
        
        logger.info(f"Added strategy {strategy_id}")
    
    async def start_strategy(self, strategy_id: str) -> None:
        """Start a strategy."""
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")
        
        if strategy_id in self.strategy_tasks:
            raise ValueError(f"Strategy {strategy_id} is already running")
        
        strategy = self.strategies[strategy_id]
        
        # Start strategy task
        task = asyncio.create_task(self._run_strategy(strategy_id))
        self.strategy_tasks[strategy_id] = task
        
        logger.info(f"Started strategy {strategy_id}")
    
    async def stop_strategy(self, strategy_id: str) -> None:
        """Stop a strategy."""
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")
        
        # Cancel strategy task
        if strategy_id in self.strategy_tasks:
            task = self.strategy_tasks[strategy_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.strategy_tasks[strategy_id]
        
        logger.info(f"Stopped strategy {strategy_id}")
    
    async def remove_strategy(self, strategy_id: str) -> None:
        """Remove a strategy."""
        # Stop if running
        if strategy_id in self.strategy_tasks:
            await self.stop_strategy(strategy_id)
        
        # Remove from strategies
        if strategy_id in self.strategies:
            del self.strategies[strategy_id]
        
        logger.info(f"Removed strategy {strategy_id}")
    
    async def _run_strategy(self, strategy_id: str):
        """Run a strategy (background task)."""
        strategy = self.strategies[strategy_id]
        
        try:
            logger.info(f"Strategy {strategy_id} task started")
            
            # Strategy main loop
            while True:
                # Strategy processing is event-driven via market data
                # This loop just keeps the task alive
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info(f"Strategy {strategy_id} task cancelled")
            raise
        except Exception as e:
            logger.error(f"Strategy {strategy_id} error: {e}")
            raise
    
    async def _process_market_data(self):
        """Process market data and route to strategies."""
        logger.info("Started processing market data for strategies")
        
        while self.running:
            try:
                # Get message from Redis pubsub
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                
                if message is None:
                    continue
                
                # Parse channel
                channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                if not channel.startswith("market_data:"):
                    continue
                
                # Parse channel parts
                parts = channel.split(":")
                if len(parts) < 3:
                    continue
                
                symbol = parts[1]
                data_type = parts[2]  # 'quote' or timeframe
                
                # Parse data
                data = json.loads(message["data"])
                
                # Route to strategies
                for strategy_id, strategy in self.strategies.items():
                    # Check if strategy is interested in this symbol
                    if symbol not in strategy.symbols:
                        continue
                    
                    # Check if strategy is running
                    if strategy_id not in self.strategy_tasks:
                        continue
                    
                    try:
                        if data_type == "quote":
                            # Process quote update
                            # Strategy doesn't have on_quote method in base class
                            # Could be extended in future
                            pass
                        else:
                            # Process candle update
                            await strategy.on_candle(symbol, data)
                            
                            # Check for signals
                            signals = await strategy.generate_signals(symbol)
                            
                            # Broadcast signals
                            for signal in signals:
                                await self._broadcast_signal(strategy_id, signal)
                                
                    except Exception as e:
                        logger.error(f"Error processing data for strategy {strategy_id}: {e}")
                
            except Exception as e:
                logger.error(f"Error in market data processing: {e}")
                await asyncio.sleep(1)
    
    async def _broadcast_signal(self, strategy_id: str, signal: Signal):
        """Broadcast a trading signal."""
        try:
            # Convert signal to JSON
            signal_data = {
                'signal_id': str(uuid4()),
                'strategy_id': strategy_id,
                'strategy_name': self.strategies[strategy_id].__class__.__name__,
                'timestamp': datetime.now().isoformat(),
                'symbol': signal.symbol,
                'direction': signal.direction.value,
                'entry_price': float(signal.entry_price) if signal.entry_price else None,
                'stop_loss': float(signal.stop_loss) if signal.stop_loss else None,
                'take_profit': float(signal.take_profit) if signal.take_profit else None,
                'confidence': float(signal.confidence) if signal.confidence else None,
                'metadata': signal.metadata
            }
            
            # Publish to Redis
            await self.redis_client.publish(
                "strategy:signals",
                json.dumps(signal_data)
            )
            
            logger.info(f"Broadcasted signal from {strategy_id} for {signal.symbol}")
            
        except Exception as e:
            logger.error(f"Error broadcasting signal: {e}")
    
    def get_strategy_status(self, strategy_id: str) -> Dict[str, Any]:
        """Get status of a specific strategy."""
        if strategy_id not in self.strategies:
            return {'error': 'Strategy not found'}
        
        strategy = self.strategies[strategy_id]
        is_running = strategy_id in self.strategy_tasks
        
        return {
            'strategy_id': strategy_id,
            'class_name': strategy.__class__.__name__,
            'is_running': is_running,
            'symbols': strategy.symbols,
            'positions': {
                symbol: {
                    'quantity': pos.quantity,
                    'average_price': float(pos.average_price),
                    'current_price': float(pos.current_price) if pos.current_price else None,
                    'unrealized_pnl': float(pos.unrealized_pnl) if pos.unrealized_pnl else None
                }
                for symbol, pos in strategy.positions.items()
            },
            'performance': {
                'total_trades': strategy.performance_tracker.total_trades,
                'winning_trades': strategy.performance_tracker.winning_trades,
                'losing_trades': strategy.performance_tracker.losing_trades,
                'total_pnl': float(strategy.performance_tracker.total_pnl),
                'win_rate': strategy.performance_tracker.win_rate,
                'sharpe_ratio': strategy.performance_tracker.sharpe_ratio,
                'max_drawdown': strategy.performance_tracker.max_drawdown
            }
        }
    
    def get_all_strategies_status(self) -> List[Dict[str, Any]]:
        """Get status of all strategies."""
        return [
            self.get_strategy_status(strategy_id)
            for strategy_id in self.strategies.keys()
        ]
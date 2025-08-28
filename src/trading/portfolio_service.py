"""Portfolio service for managing positions and portfolio analytics."""

import logging
import json
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass
import pandas as pd

from .account_service import get_account_service, Position
from ..utils.logger import get_logger
from ..cache import get_redis_client

logger = get_logger(__name__)


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics."""
    total_value: Decimal
    total_cost: Decimal
    total_pnl: Decimal
    total_pnl_percent: Decimal
    daily_pnl: Decimal
    daily_pnl_percent: Decimal
    positions_count: int
    winning_positions: int
    losing_positions: int
    win_rate: Decimal
    best_performer: Optional[str] = None
    worst_performer: Optional[str] = None
    largest_position: Optional[str] = None
    
    
@dataclass
class AssetAllocation:
    """Asset allocation breakdown."""
    asset_type: str
    value: Decimal
    percentage: Decimal
    count: int
    

@dataclass
class SectorAllocation:
    """Sector allocation breakdown."""
    sector: str
    value: Decimal
    percentage: Decimal
    symbols: List[str]


class PortfolioService:
    """Service for portfolio management and analytics."""
    
    def __init__(self):
        """Initialize portfolio service."""
        self.account_service = get_account_service()
        self._metrics_cache = {}
        self._allocation_cache = {}
        self._history_cache = {}
        self._position_cache = {}
        self._last_update = None
        self.redis_client = None
        
    async def initialize(self):
        """Initialize redis connection."""
        if not self.redis_client:
            self.redis_client = await get_redis_client()
            
    async def get_portfolio_summary(self, account_hash: Optional[str] = None) -> Dict[str, Any]:
        """
        Get portfolio summary with positions and metrics.
        
        Args:
            account_hash: Account hash to get portfolio for
            
        Returns:
            Dictionary with portfolio summary
        """
        try:
            # Get account info
            account_info = await self.account_service.get_account_info(account_hash)
            
            # Get positions
            positions = await self.account_service.get_positions(account_hash or account_info.account_hash)
            
            # Calculate metrics
            metrics = await self.calculate_portfolio_metrics(positions)
            
            # Get asset allocation
            asset_allocation = await self.calculate_asset_allocation(positions)
            
            # Format positions for response
            positions_data = []
            for pos in positions:
                positions_data.append({
                    'symbol': pos.symbol,
                    'quantity': float(pos.quantity),
                    'averageCost': float(pos.average_cost),
                    'currentPrice': float(pos.current_price),
                    'marketValue': float(pos.market_value),
                    'unrealizedPnl': float(pos.unrealized_pnl),
                    'unrealizedPnlPercent': float(pos.unrealized_pnl_percent),
                    'realizedPnl': float(pos.realized_pnl),
                    'assetType': pos.asset_type,
                    'positionType': pos.position_type,
                    'percentOfPortfolio': float((pos.market_value / account_info.total_value * 100) if account_info.total_value > 0 else 0)
                })
                
            summary = {
                'accountInfo': {
                    'accountNumber': account_info.account_number,
                    'accountHash': account_info.account_hash,
                    'accountType': account_info.account_type,
                    'cashBalance': float(account_info.cash_balance),
                    'totalValue': float(account_info.total_value),
                    'buyingPower': float(account_info.buying_power),
                    'dayTradingBuyingPower': float(account_info.day_trading_buying_power) if account_info.day_trading_buying_power else None
                },
                'metrics': {
                    'totalValue': float(metrics.total_value),
                    'totalCost': float(metrics.total_cost),
                    'totalPnl': float(metrics.total_pnl),
                    'totalPnlPercent': float(metrics.total_pnl_percent),
                    'dailyPnl': float(metrics.daily_pnl),
                    'dailyPnlPercent': float(metrics.daily_pnl_percent),
                    'positionsCount': metrics.positions_count,
                    'winningPositions': metrics.winning_positions,
                    'losingPositions': metrics.losing_positions,
                    'winRate': float(metrics.win_rate),
                    'bestPerformer': metrics.best_performer,
                    'worstPerformer': metrics.worst_performer,
                    'largestPosition': metrics.largest_position
                },
                'positions': positions_data,
                'assetAllocation': [
                    {
                        'assetType': alloc.asset_type,
                        'value': float(alloc.value),
                        'percentage': float(alloc.percentage),
                        'count': alloc.count
                    }
                    for alloc in asset_allocation
                ],
                'lastUpdate': datetime.utcnow().isoformat()
            }
            
            # Cache in Redis for real-time updates
            if self.redis_client:
                cache_key = f"portfolio:{account_info.account_hash}"
                await self.redis_client.set(
                    cache_key,
                    json.dumps(summary),
                    ex=60  # Cache for 1 minute
                )
                
            logger.info(f"Generated portfolio summary for account {account_info.account_number}")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get portfolio summary: {e}")
            raise
            
    async def calculate_portfolio_metrics(self, positions: List[Position]) -> PortfolioMetrics:
        """
        Calculate portfolio performance metrics.
        
        Args:
            positions: List of positions
            
        Returns:
            PortfolioMetrics object
        """
        try:
            if not positions:
                return PortfolioMetrics(
                    total_value=Decimal('0'),
                    total_cost=Decimal('0'),
                    total_pnl=Decimal('0'),
                    total_pnl_percent=Decimal('0'),
                    daily_pnl=Decimal('0'),
                    daily_pnl_percent=Decimal('0'),
                    positions_count=0,
                    winning_positions=0,
                    losing_positions=0,
                    win_rate=Decimal('0')
                )
                
            total_value = sum(pos.market_value for pos in positions)
            total_cost = sum(pos.average_cost * abs(pos.quantity) for pos in positions)
            total_pnl = sum(pos.unrealized_pnl for pos in positions)
            total_pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else Decimal('0')
            
            # Count winning/losing positions
            winning_positions = sum(1 for pos in positions if pos.unrealized_pnl > 0)
            losing_positions = sum(1 for pos in positions if pos.unrealized_pnl < 0)
            positions_count = len(positions)
            win_rate = (Decimal(winning_positions) / Decimal(positions_count) * 100) if positions_count > 0 else Decimal('0')
            
            # Find best and worst performers
            best_performer = None
            worst_performer = None
            largest_position = None
            
            if positions:
                positions_sorted_by_pnl = sorted(positions, key=lambda p: p.unrealized_pnl_percent)
                best_performer = positions_sorted_by_pnl[-1].symbol if positions_sorted_by_pnl[-1].unrealized_pnl_percent > 0 else None
                worst_performer = positions_sorted_by_pnl[0].symbol if positions_sorted_by_pnl[0].unrealized_pnl_percent < 0 else None
                
                positions_sorted_by_value = sorted(positions, key=lambda p: p.market_value, reverse=True)
                largest_position = positions_sorted_by_value[0].symbol
                
            # TODO: Calculate daily P&L from historical data
            daily_pnl = Decimal('0')
            daily_pnl_percent = Decimal('0')
            
            metrics = PortfolioMetrics(
                total_value=total_value,
                total_cost=total_cost,
                total_pnl=total_pnl,
                total_pnl_percent=total_pnl_percent,
                daily_pnl=daily_pnl,
                daily_pnl_percent=daily_pnl_percent,
                positions_count=positions_count,
                winning_positions=winning_positions,
                losing_positions=losing_positions,
                win_rate=win_rate,
                best_performer=best_performer,
                worst_performer=worst_performer,
                largest_position=largest_position
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to calculate portfolio metrics: {e}")
            raise
            
    async def calculate_asset_allocation(self, positions: List[Position]) -> List[AssetAllocation]:
        """
        Calculate asset allocation breakdown.
        
        Args:
            positions: List of positions
            
        Returns:
            List of AssetAllocation objects
        """
        try:
            allocation_map = {}
            total_value = sum(pos.market_value for pos in positions)
            
            for pos in positions:
                asset_type = pos.asset_type
                if asset_type not in allocation_map:
                    allocation_map[asset_type] = {
                        'value': Decimal('0'),
                        'count': 0,
                        'symbols': []
                    }
                    
                allocation_map[asset_type]['value'] += pos.market_value
                allocation_map[asset_type]['count'] += 1
                allocation_map[asset_type]['symbols'].append(pos.symbol)
                
            allocations = []
            for asset_type, data in allocation_map.items():
                percentage = (data['value'] / total_value * 100) if total_value > 0 else Decimal('0')
                allocation = AssetAllocation(
                    asset_type=asset_type,
                    value=data['value'],
                    percentage=percentage,
                    count=data['count']
                )
                allocations.append(allocation)
                
            # Sort by value descending
            allocations.sort(key=lambda a: a.value, reverse=True)
            
            return allocations
            
        except Exception as e:
            logger.error(f"Failed to calculate asset allocation: {e}")
            raise
            
    async def get_portfolio_history(
        self,
        account_hash: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get portfolio value history.
        
        Args:
            account_hash: Account hash
            days: Number of days of history to retrieve
            
        Returns:
            Dictionary with historical portfolio data
        """
        try:
            # This would typically query historical data from database
            # For now, return empty history
            history = {
                'dates': [],
                'values': [],
                'returns': [],
                'cumulative_returns': []
            }
            
            logger.info(f"Retrieved portfolio history for {days} days")
            return history
            
        except Exception as e:
            logger.error(f"Failed to get portfolio history: {e}")
            raise
            
    async def update_portfolio_realtime(self, account_hash: str, quotes: Dict[str, Any]):
        """
        Update portfolio with real-time quotes.
        
        Args:
            account_hash: Account hash
            quotes: Real-time quote data
        """
        try:
            # Get current positions
            positions = await self.account_service.get_positions(account_hash)
            
            # Update positions with real-time prices
            for pos in positions:
                if pos.symbol in quotes:
                    quote = quotes[pos.symbol]
                    if 'quote' in quote:
                        quote_data = quote['quote']
                        pos.current_price = Decimal(str(quote_data.get('lastPrice', pos.current_price)))
                        pos.market_value = pos.current_price * pos.quantity
                        
                        # Recalculate P&L
                        total_cost = pos.average_cost * abs(pos.quantity)
                        pos.unrealized_pnl = pos.market_value - total_cost if pos.quantity > 0 else total_cost - pos.market_value
                        pos.unrealized_pnl_percent = (pos.unrealized_pnl / total_cost * 100) if total_cost != 0 else Decimal('0')
                        
            # Update cache
            self._position_cache[account_hash] = positions
            self._last_update = datetime.utcnow()
            
            # Recalculate metrics
            metrics = await self.calculate_portfolio_metrics(positions)
            self._metrics_cache[account_hash] = metrics
            
            # Publish update to Redis for WebSocket broadcast
            if self.redis_client:
                update_data = {
                    'accountHash': account_hash,
                    'positions': [
                        {
                            'symbol': pos.symbol,
                            'currentPrice': float(pos.current_price),
                            'marketValue': float(pos.market_value),
                            'unrealizedPnl': float(pos.unrealized_pnl),
                            'unrealizedPnlPercent': float(pos.unrealized_pnl_percent)
                        }
                        for pos in positions
                    ],
                    'metrics': {
                        'totalValue': float(metrics.total_value),
                        'totalPnl': float(metrics.total_pnl),
                        'totalPnlPercent': float(metrics.total_pnl_percent)
                    },
                    'timestamp': self._last_update.isoformat()
                }
                
                await self.redis_client.publish(
                    'portfolio_updates',
                    json.dumps(update_data)
                )
                
            logger.info(f"Updated portfolio with real-time quotes for account {account_hash}")
            
        except Exception as e:
            logger.error(f"Failed to update portfolio realtime: {e}")
            raise


# Singleton instance
_portfolio_service: Optional[PortfolioService] = None


def get_portfolio_service() -> PortfolioService:
    """Get the singleton portfolio service instance."""
    global _portfolio_service
    if _portfolio_service is None:
        _portfolio_service = PortfolioService()
    return _portfolio_service
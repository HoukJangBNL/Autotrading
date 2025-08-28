"""Portfolio integration with WebSocket and real-time updates."""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..trading.portfolio_service import get_portfolio_service
from ..trading.account_service import get_account_service
from ..cache import get_redis_client
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PortfolioIntegration:
    """Integrates portfolio updates with WebSocket broadcasting."""
    
    def __init__(self):
        """Initialize portfolio integration."""
        self.portfolio_service = get_portfolio_service()
        self.account_service = get_account_service()
        self.redis_client = None
        self.update_interval = 5  # seconds
        self._running = False
        self._update_task = None
        
    async def initialize(self):
        """Initialize Redis connection and services."""
        if not self.redis_client:
            self.redis_client = await get_redis_client()
        await self.portfolio_service.initialize()
        logger.info("Portfolio integration initialized")
        
    async def start_realtime_updates(self):
        """Start real-time portfolio update loop."""
        await self.initialize()
        
        if self._running:
            logger.warning("Portfolio updates already running")
            return
            
        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        logger.info("Started real-time portfolio updates")
        
    async def stop_realtime_updates(self):
        """Stop real-time portfolio update loop."""
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
                
        logger.info("Stopped real-time portfolio updates")
        
    async def _update_loop(self):
        """Main update loop for portfolio data."""
        while self._running:
            try:
                # Get all accounts
                accounts = await self.account_service.get_account_numbers()
                
                for account in accounts:
                    account_hash = account.get('hashValue')
                    if account_hash:
                        await self.update_portfolio_for_account(account_hash)
                        
                # Wait for next update interval
                await asyncio.sleep(self.update_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in portfolio update loop: {e}")
                await asyncio.sleep(self.update_interval)
                
    async def update_portfolio_for_account(self, account_hash: str):
        """
        Update portfolio data for a specific account and broadcast.
        
        Args:
            account_hash: Account hash to update
        """
        try:
            # Get current positions
            positions = await self.account_service.get_positions(account_hash)
            
            # Get symbols for quotes
            symbols = [pos.symbol for pos in positions]
            
            if symbols:
                # Get real-time quotes
                quotes = await self.account_service.get_quotes(symbols)
                
                # Update portfolio with real-time data
                await self.portfolio_service.update_portfolio_realtime(
                    account_hash=account_hash,
                    quotes=quotes
                )
                
                logger.info(f"Updated portfolio for account {account_hash} with {len(symbols)} symbols")
            
        except Exception as e:
            logger.error(f"Failed to update portfolio for account {account_hash}: {e}")
            
    async def handle_quote_update(self, symbol: str, quote_data: Dict[str, Any]):
        """
        Handle real-time quote update for portfolio positions.
        
        Args:
            symbol: Stock symbol
            quote_data: Real-time quote data
        """
        try:
            # Get all accounts with this symbol
            accounts = await self.account_service.get_account_numbers()
            
            for account in accounts:
                account_hash = account.get('hashValue')
                if not account_hash:
                    continue
                    
                # Check if this account has the symbol
                positions = await self.account_service.get_positions(account_hash)
                
                for position in positions:
                    if position.symbol == symbol:
                        # Update this specific position with new quote
                        await self.portfolio_service.update_portfolio_realtime(
                            account_hash=account_hash,
                            quotes={symbol: quote_data}
                        )
                        
                        logger.debug(f"Updated {symbol} for account {account_hash}")
                        break
                        
        except Exception as e:
            logger.error(f"Failed to handle quote update for {symbol}: {e}")
            
    async def refresh_all_portfolios(self) -> Dict[str, Any]:
        """
        Refresh all portfolio data and broadcast updates.
        
        Returns:
            Summary of refreshed portfolios
        """
        try:
            # Get all accounts
            accounts = await self.account_service.get_account_numbers()
            
            results = {
                'accounts_updated': 0,
                'positions_updated': 0,
                'errors': []
            }
            
            for account in accounts:
                account_hash = account.get('hashValue')
                if not account_hash:
                    continue
                    
                try:
                    # Get fresh portfolio data
                    summary = await self.portfolio_service.get_portfolio_summary(account_hash)
                    
                    # Count updates
                    results['accounts_updated'] += 1
                    results['positions_updated'] += len(summary.get('positions', []))
                    
                except Exception as e:
                    error_msg = f"Failed to refresh account {account_hash}: {e}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
                    
            logger.info(f"Refreshed {results['accounts_updated']} portfolios with {results['positions_updated']} positions")
            return results
            
        except Exception as e:
            logger.error(f"Failed to refresh all portfolios: {e}")
            raise
            
    async def get_aggregated_portfolio(self) -> Dict[str, Any]:
        """
        Get aggregated portfolio across all accounts.
        
        Returns:
            Aggregated portfolio data
        """
        try:
            # Get all accounts
            accounts = await self.account_service.get_all_accounts()
            
            # Aggregate data
            total_value = sum(acc.total_value for acc in accounts)
            total_cash = sum(acc.cash_balance for acc in accounts)
            total_buying_power = sum(acc.buying_power for acc in accounts)
            
            # Get all positions
            all_positions = []
            position_map = {}
            
            for account in accounts:
                positions = await self.account_service.get_positions(account.account_hash)
                
                for pos in positions:
                    # Aggregate by symbol
                    if pos.symbol not in position_map:
                        position_map[pos.symbol] = {
                            'symbol': pos.symbol,
                            'totalQuantity': 0,
                            'totalValue': 0,
                            'totalCost': 0,
                            'accounts': []
                        }
                        
                    position_map[pos.symbol]['totalQuantity'] += float(pos.quantity)
                    position_map[pos.symbol]['totalValue'] += float(pos.market_value)
                    position_map[pos.symbol]['totalCost'] += float(pos.average_cost * pos.quantity)
                    position_map[pos.symbol]['accounts'].append(account.account_number)
                    
                all_positions.extend(positions)
                
            # Calculate aggregated metrics
            aggregated_positions = []
            for symbol, data in position_map.items():
                avg_cost = data['totalCost'] / data['totalQuantity'] if data['totalQuantity'] > 0 else 0
                unrealized_pnl = data['totalValue'] - data['totalCost']
                unrealized_pnl_pct = (unrealized_pnl / data['totalCost'] * 100) if data['totalCost'] > 0 else 0
                
                aggregated_positions.append({
                    'symbol': symbol,
                    'quantity': data['totalQuantity'],
                    'averageCost': avg_cost,
                    'marketValue': data['totalValue'],
                    'unrealizedPnl': unrealized_pnl,
                    'unrealizedPnlPercent': unrealized_pnl_pct,
                    'accounts': data['accounts'],
                    'percentOfTotal': (data['totalValue'] / total_value * 100) if total_value > 0 else 0
                })
                
            # Sort by market value
            aggregated_positions.sort(key=lambda x: x['marketValue'], reverse=True)
            
            return {
                'totalValue': float(total_value),
                'totalCash': float(total_cash),
                'totalSecurities': float(total_value - total_cash),
                'totalBuyingPower': float(total_buying_power),
                'accountCount': len(accounts),
                'positionCount': len(aggregated_positions),
                'positions': aggregated_positions,
                'lastUpdate': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get aggregated portfolio: {e}")
            raise


# Singleton instance
_portfolio_integration: Optional[PortfolioIntegration] = None


def get_portfolio_integration() -> PortfolioIntegration:
    """Get the singleton portfolio integration instance."""
    global _portfolio_integration
    if _portfolio_integration is None:
        _portfolio_integration = PortfolioIntegration()
    return _portfolio_integration
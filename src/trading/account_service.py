"""Account service for managing Schwab account information."""

import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime
import asyncio
from dataclasses import dataclass

from ..auth import get_auth_service
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AccountBalance:
    """Account balance information."""
    account_number: str
    account_hash: str
    account_type: str
    cash_balance: Decimal
    total_value: Decimal
    buying_power: Decimal
    margin_balance: Optional[Decimal] = None
    short_balance: Optional[Decimal] = None
    cash_available_for_withdrawal: Optional[Decimal] = None
    cash_available_for_trading: Optional[Decimal] = None
    maintenance_requirement: Optional[Decimal] = None
    day_trading_buying_power: Optional[Decimal] = None
    
@dataclass
class Position:
    """Position information."""
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal
    realized_pnl: Decimal
    asset_type: str
    position_type: str  # LONG or SHORT


class AccountService:
    """Service for managing account information and positions."""
    
    def __init__(self):
        """Initialize account service."""
        self.auth_service = get_auth_service()
        self._account_cache = {}
        self._position_cache = {}
        self._last_update = None
        
    async def get_account_numbers(self) -> List[Dict[str, str]]:
        """
        Get all account numbers and their hashes.
        
        Returns:
            List of dictionaries containing accountNumber and hashValue
        """
        try:
            client = await self.auth_service.ensure_authenticated()
            response = await client.get_account_numbers()
            response.raise_for_status()
            
            accounts = response.json()
            logger.info(f"Retrieved {len(accounts)} accounts")
            
            return accounts
            
        except Exception as e:
            logger.error(f"Failed to get account numbers: {e}")
            raise
            
    async def get_account_info(self, account_hash: Optional[str] = None) -> AccountBalance:
        """
        Get detailed account information.
        
        Args:
            account_hash: Account hash to retrieve. If None, uses first available account.
            
        Returns:
            AccountBalance object with account details
        """
        try:
            client = await self.auth_service.ensure_authenticated()
            
            # Get account hash if not provided
            if not account_hash:
                accounts = await self.get_account_numbers()
                if not accounts:
                    raise ValueError("No accounts available")
                account_hash = accounts[0]['hashValue']
                
            # Get account details
            response = await client.get_account(account_hash, fields=['positions'])
            response.raise_for_status()
            
            account_data = response.json()
            account = account_data.get('securitiesAccount', {})
            
            # Extract balance information
            current_balances = account.get('currentBalances', {})
            initial_balances = account.get('initialBalances', {})
            
            balance = AccountBalance(
                account_number=account.get('accountNumber', ''),
                account_hash=account_hash,
                account_type=account.get('type', 'UNKNOWN'),
                cash_balance=Decimal(str(current_balances.get('cashBalance', 0))),
                total_value=Decimal(str(current_balances.get('liquidationValue', 0))),
                buying_power=Decimal(str(initial_balances.get('buyingPower', 0))),
                margin_balance=Decimal(str(current_balances.get('marginBalance', 0))) if 'marginBalance' in current_balances else None,
                short_balance=Decimal(str(current_balances.get('shortBalance', 0))) if 'shortBalance' in current_balances else None,
                cash_available_for_withdrawal=Decimal(str(current_balances.get('cashAvailableForWithdrawal', 0))) if 'cashAvailableForWithdrawal' in current_balances else None,
                cash_available_for_trading=Decimal(str(current_balances.get('cashAvailableForTrading', 0))) if 'cashAvailableForTrading' in current_balances else None,
                maintenance_requirement=Decimal(str(current_balances.get('maintenanceRequirement', 0))) if 'maintenanceRequirement' in current_balances else None,
                day_trading_buying_power=Decimal(str(initial_balances.get('dayTradingBuyingPower', 0))) if 'dayTradingBuyingPower' in initial_balances else None
            )
            
            # Cache the result
            self._account_cache[account_hash] = balance
            self._last_update = datetime.utcnow()
            
            logger.info(f"Retrieved account info for {balance.account_number}")
            return balance
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise
            
    async def get_all_accounts(self) -> List[AccountBalance]:
        """
        Get information for all linked accounts.
        
        Returns:
            List of AccountBalance objects
        """
        try:
            client = await self.auth_service.ensure_authenticated()
            
            # Get all accounts
            response = await client.get_accounts(fields=['positions'])
            response.raise_for_status()
            
            accounts_data = response.json()
            accounts = []
            
            for account_data in accounts_data:
                account = account_data.get('securitiesAccount', {})
                current_balances = account.get('currentBalances', {})
                initial_balances = account.get('initialBalances', {})
                
                # Get account hash
                account_number = account.get('accountNumber', '')
                accounts_list = await self.get_account_numbers()
                account_hash = next((a['hashValue'] for a in accounts_list if a['accountNumber'] == account_number), '')
                
                balance = AccountBalance(
                    account_number=account_number,
                    account_hash=account_hash,
                    account_type=account.get('type', 'UNKNOWN'),
                    cash_balance=Decimal(str(current_balances.get('cashBalance', 0))),
                    total_value=Decimal(str(current_balances.get('liquidationValue', 0))),
                    buying_power=Decimal(str(initial_balances.get('buyingPower', 0))),
                    margin_balance=Decimal(str(current_balances.get('marginBalance', 0))) if 'marginBalance' in current_balances else None,
                    short_balance=Decimal(str(current_balances.get('shortBalance', 0))) if 'shortBalance' in current_balances else None,
                    cash_available_for_withdrawal=Decimal(str(current_balances.get('cashAvailableForWithdrawal', 0))) if 'cashAvailableForWithdrawal' in current_balances else None,
                    cash_available_for_trading=Decimal(str(current_balances.get('cashAvailableForTrading', 0))) if 'cashAvailableForTrading' in current_balances else None,
                    maintenance_requirement=Decimal(str(current_balances.get('maintenanceRequirement', 0))) if 'maintenanceRequirement' in current_balances else None,
                    day_trading_buying_power=Decimal(str(initial_balances.get('dayTradingBuyingPower', 0))) if 'dayTradingBuyingPower' in initial_balances else None
                )
                
                accounts.append(balance)
                self._account_cache[account_hash] = balance
                
            self._last_update = datetime.utcnow()
            logger.info(f"Retrieved info for {len(accounts)} accounts")
            
            return accounts
            
        except Exception as e:
            logger.error(f"Failed to get all accounts: {e}")
            raise
            
    async def get_positions(self, account_hash: Optional[str] = None) -> List[Position]:
        """
        Get all positions for an account.
        
        Args:
            account_hash: Account hash to retrieve positions for
            
        Returns:
            List of Position objects
        """
        try:
            client = await self.auth_service.ensure_authenticated()
            
            # Get account hash if not provided
            if not account_hash:
                accounts = await self.get_account_numbers()
                if not accounts:
                    raise ValueError("No accounts available")
                account_hash = accounts[0]['hashValue']
                
            # Get account with positions
            response = await client.get_account(account_hash, fields=['positions'])
            response.raise_for_status()
            
            account_data = response.json()
            account = account_data.get('securitiesAccount', {})
            positions_data = account.get('positions', [])
            
            positions = []
            for pos_data in positions_data:
                instrument = pos_data.get('instrument', {})
                
                # Calculate unrealized P&L
                quantity = Decimal(str(pos_data.get('longQuantity', 0))) - Decimal(str(pos_data.get('shortQuantity', 0)))
                average_cost = Decimal(str(pos_data.get('averagePrice', 0)))
                market_value = Decimal(str(pos_data.get('marketValue', 0)))
                
                # Get current price from market value and quantity
                current_price = market_value / quantity if quantity != 0 else Decimal('0')
                
                # Calculate P&L
                total_cost = average_cost * abs(quantity)
                unrealized_pnl = market_value - total_cost if quantity > 0 else total_cost - market_value
                unrealized_pnl_percent = (unrealized_pnl / total_cost * 100) if total_cost != 0 else Decimal('0')
                
                position = Position(
                    symbol=instrument.get('symbol', ''),
                    quantity=quantity,
                    average_cost=average_cost,
                    current_price=current_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_percent=unrealized_pnl_percent,
                    realized_pnl=Decimal(str(pos_data.get('realizedPnl', 0))),
                    asset_type=instrument.get('assetType', 'UNKNOWN'),
                    position_type='LONG' if quantity > 0 else 'SHORT'
                )
                
                positions.append(position)
                
            # Cache the result
            self._position_cache[account_hash] = positions
            self._last_update = datetime.utcnow()
            
            logger.info(f"Retrieved {len(positions)} positions for account {account_hash}")
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise
            
    async def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Get real-time quotes for symbols.
        
        Args:
            symbols: List of symbols to get quotes for
            
        Returns:
            Dictionary of symbol -> quote data
        """
        try:
            client = await self.auth_service.ensure_authenticated()
            
            # Get quotes
            response = await client.get_quotes(symbols)
            response.raise_for_status()
            
            quotes = response.json()
            logger.info(f"Retrieved quotes for {len(quotes)} symbols")
            
            return quotes
            
        except Exception as e:
            logger.error(f"Failed to get quotes: {e}")
            raise
            
    async def refresh_all_data(self) -> Dict[str, Any]:
        """
        Refresh all account and position data.
        
        Returns:
            Dictionary with updated account and position information
        """
        try:
            # Get all accounts
            accounts = await self.get_all_accounts()
            
            # Get positions for each account
            all_positions = {}
            for account in accounts:
                positions = await self.get_positions(account.account_hash)
                all_positions[account.account_hash] = positions
                
            # Get unique symbols from all positions
            symbols = set()
            for positions in all_positions.values():
                for position in positions:
                    symbols.add(position.symbol)
                    
            # Get quotes for all symbols
            quotes = {}
            if symbols:
                quotes = await self.get_quotes(list(symbols))
                
            result = {
                'accounts': [
                    {
                        'accountNumber': acc.account_number,
                        'accountHash': acc.account_hash,
                        'accountType': acc.account_type,
                        'cashBalance': float(acc.cash_balance),
                        'totalValue': float(acc.total_value),
                        'buyingPower': float(acc.buying_power),
                        'marginBalance': float(acc.margin_balance) if acc.margin_balance else None,
                        'dayTradingBuyingPower': float(acc.day_trading_buying_power) if acc.day_trading_buying_power else None
                    }
                    for acc in accounts
                ],
                'positions': {
                    account_hash: [
                        {
                            'symbol': pos.symbol,
                            'quantity': float(pos.quantity),
                            'averageCost': float(pos.average_cost),
                            'currentPrice': float(pos.current_price),
                            'marketValue': float(pos.market_value),
                            'unrealizedPnl': float(pos.unrealized_pnl),
                            'unrealizedPnlPercent': float(pos.unrealized_pnl_percent),
                            'realizedPnl': float(pos.realized_pnl),
                            'assetType': pos.asset_type,
                            'positionType': pos.position_type
                        }
                        for pos in positions
                    ]
                    for account_hash, positions in all_positions.items()
                },
                'quotes': quotes,
                'lastUpdate': self._last_update.isoformat() if self._last_update else None
            }
            
            logger.info("Successfully refreshed all account data")
            return result
            
        except Exception as e:
            logger.error(f"Failed to refresh all data: {e}")
            raise


# Singleton instance
_account_service: Optional[AccountService] = None


def get_account_service() -> AccountService:
    """Get the singleton account service instance."""
    global _account_service
    if _account_service is None:
        _account_service = AccountService()
    return _account_service
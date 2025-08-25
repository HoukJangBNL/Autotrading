"""Schwab broker client with comprehensive API integration."""

import asyncio
import json
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple
from functools import wraps
import httpx
from httpx import Response

# from schwab.orders import EquityInstruction, OrderType, Duration, Session
# from schwab.orders.generic import OrderBuilder

# Avoid circular import - import get_auth_service only when needed
from ..auth.exceptions import AuthenticationError
from ..config.settings import get_settings
from ..utils.logger import get_logger
from .exceptions import (
    BrokerError,
    RateLimitError,
    InvalidOrderError,
    InsufficientFundsError,
    PositionNotFoundError,
    OrderNotFoundError,
    MarketDataError,
    BrokerConnectionError
)
from .rate_limiter import RateLimiter, CircuitBreaker, CircuitState

logger = get_logger(__name__)


class OrderStatus(str, Enum):
    """Order status enumeration."""
    AWAITING_PARENT_ORDER = "AWAITING_PARENT_ORDER"
    AWAITING_CONDITION = "AWAITING_CONDITION"
    AWAITING_MANUAL_REVIEW = "AWAITING_MANUAL_REVIEW"
    ACCEPTED = "ACCEPTED"
    AWAITING_UR_OUT = "AWAITING_UR_OUT"
    PENDING_ACTIVATION = "PENDING_ACTIVATION"
    QUEUED = "QUEUED"
    WORKING = "WORKING"
    REJECTED = "REJECTED"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELED = "CANCELED"
    PENDING_REPLACE = "PENDING_REPLACE"
    REPLACED = "REPLACED"
    FILLED = "FILLED"
    EXPIRED = "EXPIRED"


class SchwabBroker:
    """
    Unified Schwab broker client with comprehensive API integration.
    
    Features:
    - Singleton pattern with thread-safe initialization
    - Automatic OAuth token management
    - Request/response logging with sensitive data masking
    - Error standardization and retry logic
    - Rate limiting and circuit breaker protection
    """
    
    _instance: Optional['SchwabBroker'] = None
    _initialized: bool = False
    
    # API endpoints
    BASE_URL = "https://api.schwabapi.com/trader/v1"
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_STATUSES = {429, 502, 503, 504}
    NO_RETRY_STATUSES = {400, 401, 403, 404}
    
    def __new__(cls, *args, **kwargs) -> 'SchwabBroker':
        """Ensure singleton instance with test support."""
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        auth_service=None,
        rate_limiter=None,
        circuit_breaker=None,
        config=None
    ):
        """
        Initialize broker client with optional dependencies.
        
        Args:
            auth_service: Optional auth service instance
            rate_limiter: Optional rate limiter instance
            circuit_breaker: Optional circuit breaker instance
            config: Optional configuration override
        """
        # Prevent re-initialization
        if self._initialized and not auth_service:
            return
            
        self.auth_service = auth_service
        self.rate_limiter = rate_limiter
        self.circuit_breaker = circuit_breaker
        self.config = config or get_settings()
        self.client = None
        self._account_numbers = None
        self._account_hash_map = {}  # Map account numbers to hash values
        self._lock = None  # Will be created when needed
        
    async def initialize(self):
        """
        Lazy initialization of the broker client.
        
        Ensures thread-safe initialization of auth service and client.
        """
        # Create lock if not exists (bound to current event loop)
        if self._lock is None:
            self._lock = asyncio.Lock()
            
        async with self._lock:
            if self._initialized and self.client:
                return
                
            # Set initializing flag to prevent recursive init
            self._initializing = True
                
            try:
                # Initialize auth service if not provided
                if not self.auth_service:
                    # Import here to avoid circular import
                    from ..auth.auth_service import get_auth_service
                    self.auth_service = get_auth_service()
                    await self.auth_service.initialize()
                
                # Ensure auth service is authenticated
                await self.auth_service.ensure_authenticated()
                
                # Get authenticated client
                self.client = self.auth_service.get_client()
                
                # Initialize rate limiter if not provided
                if not self.rate_limiter:
                    self.rate_limiter = RateLimiter(
                        rate=120,  # 120 requests per minute
                        period=60,  # 60 seconds
                        burst=30    # Allow burst of 30 requests
                    )
                
                # Initialize circuit breaker if not provided
                if not self.circuit_breaker:
                    self.circuit_breaker = CircuitBreaker(
                        failure_threshold=5,
                        recovery_timeout=30,
                        expected_exception=BrokerError
                    )
                
                # Load account numbers
                await self._load_account_numbers()
                
                self._initialized = True
                logger.info("SchwabBroker initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize SchwabBroker: {e}")
                raise BrokerConnectionError(f"Failed to initialize broker: {e}")
            finally:
                # Clear initializing flag
                self._initializing = False
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton for testing."""
        cls._instance = None
        cls._initialized = False
        logger.debug("SchwabBroker singleton reset for testing")
    
    async def _load_account_numbers(self):
        """Load and cache account numbers with their hash values."""
        try:
            # Use the client's built-in method
            response = await self.client.get_account_numbers()
            accounts = response.json()
            
            self._account_numbers = []
            self._account_hash_map = {}
            
            for account in accounts:
                account_number = account.get('accountNumber')
                hash_value = account.get('hashValue')
                
                if account_number and hash_value:
                    self._account_numbers.append(account_number)
                    self._account_hash_map[account_number] = hash_value
                    
            logger.info(f"Loaded {len(self._account_numbers)} accounts")
            
        except Exception as e:
            logger.error(f"Failed to load account numbers: {e}")
            raise
    
    def _mask_sensitive_data(self, data: Any) -> Any:
        """
        Mask sensitive data for logging.
        
        Args:
            data: Data to mask (dict, list, or string)
            
        Returns:
            Masked data safe for logging
        """
        if isinstance(data, dict):
            masked = {}
            sensitive_keys = {
                'accountNumber', 'account_number', 'password', 'token',
                'authorization', 'api_key', 'secret', 'position',
                'quantity', 'price', 'cost', 'value', 'balance'
            }
            
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    if isinstance(value, str) and len(value) > 4:
                        masked[key] = f"{value[:2]}...{value[-2:]}"
                    else:
                        masked[key] = "***"
                else:
                    masked[key] = self._mask_sensitive_data(value)
            return masked
            
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
            
        elif isinstance(data, str):
            # Mask account numbers in URLs
            if '/accounts/' in data:
                parts = data.split('/')
                for i, part in enumerate(parts):
                    if part.isdigit() and len(part) > 6:
                        parts[i] = f"{part[:3]}...{part[-3:]}"
                return '/'.join(parts)
            return data
            
        return data
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        retry_count: int = 0
    ) -> Response:
        """
        Make an authenticated request to Schwab API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to base URL)
            params: Query parameters
            json_data: JSON request body
            retry_count: Current retry attempt
            
        Returns:
            Response object
            
        Raises:
            Various BrokerError subclasses based on response
        """
        # Ensure initialization - but only if we're not already initializing
        if not self._initialized and not hasattr(self, '_initializing'):
            await self.initialize()
        
        # Check circuit breaker
        if not self.circuit_breaker.can_request():
            raise BrokerConnectionError("Circuit breaker is open - API unavailable")
        
        # Apply rate limiting
        await self.rate_limiter.acquire()
        
        # Build full URL
        url = endpoint if endpoint.startswith('http') else f"{self.BASE_URL}{endpoint}"
        
        # Log request (with masked data)
        logger.info(
            f"API Request: {method} {self._mask_sensitive_data(url)} "
            f"params={self._mask_sensitive_data(params or {})} "
            f"retry={retry_count}"
        )
        
        try:
            # Make request using schwab-py client
            if method == "GET":
                response = await self.client.get(url, params=params)
            elif method == "POST":
                response = await self.client.post(url, json=json_data)
            elif method == "PUT":
                response = await self.client.put(url, json=json_data)
            elif method == "DELETE":
                response = await self.client.delete(url)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check response status
            if response.status_code < 400:
                # Success - reset circuit breaker
                self.circuit_breaker.record_success()
                
                # Log success
                logger.info(
                    f"API Response: {response.status_code} "
                    f"for {method} {self._mask_sensitive_data(url)}"
                )
                
                return response
            
            # Handle errors
            await self._handle_error_response(response, method, endpoint, retry_count)
            
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {e}")
            self.circuit_breaker.record_failure()
            
            if retry_count < self.MAX_RETRIES:
                await asyncio.sleep(2 ** retry_count)
                return await self._make_request(
                    method, endpoint, params, json_data, retry_count + 1
                )
            
            raise BrokerConnectionError(f"Request timeout after {retry_count} retries")
            
        except httpx.NetworkError as e:
            logger.error(f"Network error: {e}")
            self.circuit_breaker.record_failure()
            
            if retry_count < self.MAX_RETRIES:
                await asyncio.sleep(2 ** retry_count)
                return await self._make_request(
                    method, endpoint, params, json_data, retry_count + 1
                )
            
            raise BrokerConnectionError(f"Network error: {e}")
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.circuit_breaker.record_failure()
            raise BrokerError(f"Unexpected error: {e}")
    
    async def _handle_error_response(
        self,
        response: Response,
        method: str,
        endpoint: str,
        retry_count: int
    ):
        """Handle error responses from the API."""
        status_code = response.status_code
        
        try:
            error_data = response.json()
            error_message = error_data.get('message', 'Unknown error')
            error_code = error_data.get('code', 'UNKNOWN')
        except:
            error_message = response.text
            error_code = 'UNKNOWN'
        
        # Log error
        logger.error(
            f"API Error: {status_code} {error_code} - {error_message} "
            f"for {method} {self._mask_sensitive_data(endpoint)}"
        )
        
        # Record failure for circuit breaker
        self.circuit_breaker.record_failure()
        
        # Handle specific error codes
        if status_code == 401:
            raise AuthenticationError("Authentication failed - token may be expired")
            
        elif status_code == 403:
            raise BrokerError(f"Forbidden: {error_message}")
            
        elif status_code == 404:
            if 'order' in endpoint.lower():
                raise OrderNotFoundError(f"Order not found: {error_message}")
            elif 'position' in endpoint.lower():
                raise PositionNotFoundError(f"Position not found: {error_message}")
            else:
                raise BrokerError(f"Resource not found: {error_message}")
                
        elif status_code == 429:
            # Rate limited
            if retry_count < self.MAX_RETRIES:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited, retrying after {retry_after} seconds")
                await asyncio.sleep(retry_after)
                return await self._make_request(
                    method, endpoint, None, None, retry_count + 1
                )
            raise RateLimitError(f"Rate limit exceeded: {error_message}")
            
        elif status_code in self.RETRY_STATUSES and retry_count < self.MAX_RETRIES:
            # Retry on server errors
            wait_time = (2 ** retry_count) + (0.1 * time.time() % 1)
            logger.warning(f"Server error {status_code}, retrying in {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            return await self._make_request(
                method, endpoint, None, None, retry_count + 1
            )
            
        elif status_code >= 500:
            raise BrokerConnectionError(f"Server error {status_code}: {error_message}")
            
        else:
            raise BrokerError(f"API error {status_code}: {error_message}")
    
    # Account Information Methods
    
    async def get_account_numbers(self) -> List[str]:
        """
        Get list of account numbers.
        
        Returns:
            List of account numbers
        """
        if not self._account_numbers:
            await self._load_account_numbers()
        return self._account_numbers.copy()
    
    async def get_account_info(
        self,
        account_number: Optional[str] = None,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get detailed account information.
        
        Args:
            account_number: Account number (uses first account if not specified)
            fields: Optional list of fields to include
            
        Returns:
            Account information dict
        """
        # Use first account if not specified
        if not account_number:
            accounts = await self.get_account_numbers()
            if not accounts:
                raise BrokerError("No accounts found")
            account_number = accounts[0]
        
        # Get account hash
        account_hash = self._account_hash_map.get(account_number)
        if not account_hash:
            raise BrokerError(f"Account {account_number} not found")
        
        # Build endpoint
        endpoint = f"/accounts/{account_hash}"
        
        # Add fields if specified
        params = {}
        if fields:
            params['fields'] = ','.join(fields)
        
        response = await self._make_request("GET", endpoint, params=params)
        return response.json()
    
    async def get_positions(
        self,
        account_number: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all positions for an account.
        
        Args:
            account_number: Account number (uses first account if not specified)
            
        Returns:
            List of position dictionaries
        """
        # Get full account info with positions
        account_info = await self.get_account_info(
            account_number,
            fields=['positions']
        )
        
        # Extract positions
        securities_account = account_info.get('securitiesAccount', {})
        positions = securities_account.get('positions', [])
        
        return positions
    
    async def get_orders(
        self,
        account_number: Optional[str] = None,
        from_entered_time: Optional[datetime] = None,
        to_entered_time: Optional[datetime] = None,
        max_results: int = 100,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get orders for an account.
        
        Args:
            account_number: Account number (uses first account if not specified)
            from_entered_time: Start time for order query
            to_entered_time: End time for order query
            max_results: Maximum number of results
            status: Filter by order status
            
        Returns:
            List of order dictionaries
        """
        # Use first account if not specified
        if not account_number:
            accounts = await self.get_account_numbers()
            if not accounts:
                raise BrokerError("No accounts found")
            account_number = accounts[0]
        
        # Get account hash
        account_hash = self._account_hash_map.get(account_number)
        if not account_hash:
            raise BrokerError(f"Account {account_number} not found")
        
        # Build params
        params = {'maxResults': max_results}
        
        if from_entered_time:
            params['fromEnteredTime'] = from_entered_time.isoformat()
            
        if to_entered_time:
            params['toEnteredTime'] = to_entered_time.isoformat()
        else:
            # Default to current time
            params['toEnteredTime'] = datetime.now().isoformat()
            
        if status:
            params['status'] = status
        
        endpoint = f"/accounts/{account_hash}/orders"
        response = await self._make_request("GET", endpoint, params=params)
        
        return response.json()
    
    # Trading Methods
    
    async def place_order(
        self,
        account_number: str,
        order: Union[Dict[str, Any], Any]  # OrderBuilder when available
    ) -> Dict[str, Any]:
        """
        Place an order.
        
        Args:
            account_number: Account number
            order: Order dict or OrderBuilder object (when available)
            
        Returns:
            Order confirmation with order ID
        """
        # Get account hash
        account_hash = self._account_hash_map.get(account_number)
        if not account_hash:
            raise BrokerError(f"Account {account_number} not found")
        
        # Convert OrderBuilder to dict if needed
        if hasattr(order, 'build'):
            order_dict = order.build()
        else:
            order_dict = order
        
        # Validate order
        self._validate_order(order_dict)
        
        # Place order
        endpoint = f"/accounts/{account_hash}/orders"
        response = await self._make_request("POST", endpoint, json_data=order_dict)
        
        # Extract order ID from location header
        location = response.headers.get('Location', '')
        order_id = location.split('/')[-1] if location else None
        
        return {
            'order_id': order_id,
            'status': 'SUBMITTED',
            'message': 'Order submitted successfully'
        }
    
    async def cancel_order(
        self,
        account_number: str,
        order_id: str
    ) -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            account_number: Account number
            order_id: Order ID to cancel
            
        Returns:
            Cancellation confirmation
        """
        # Get account hash
        account_hash = self._account_hash_map.get(account_number)
        if not account_hash:
            raise BrokerError(f"Account {account_number} not found")
        
        # Cancel order
        endpoint = f"/accounts/{account_hash}/orders/{order_id}"
        await self._make_request("DELETE", endpoint)
        
        return {
            'order_id': order_id,
            'status': 'CANCELLED',
            'message': 'Order cancelled successfully'
        }
    
    def _validate_order(self, order: Dict[str, Any]):
        """Validate order structure."""
        required_fields = ['orderType', 'session', 'duration', 'orderStrategyType']
        
        for field in required_fields:
            if field not in order:
                raise InvalidOrderError(f"Missing required field: {field}")
        
        # Validate order legs
        if 'orderLegCollection' not in order or not order['orderLegCollection']:
            raise InvalidOrderError("Order must have at least one leg")
    
    # Market Data Methods
    
    async def get_quotes(
        self,
        symbols: Union[str, List[str]],
        fields: Optional[List[str]] = None,
        indicative: bool = False
    ) -> Dict[str, Any]:
        """
        Get real-time quotes for symbols.
        
        Args:
            symbols: Single symbol or list of symbols
            fields: Optional fields to include
            indicative: Whether to include indicative quotes
            
        Returns:
            Dict mapping symbols to quote data
        """
        # Convert single symbol to list
        if isinstance(symbols, str):
            symbols = [symbols]
        
        # Validate symbols
        if not symbols:
            raise MarketDataError("No symbols provided")
            
        if len(symbols) > 500:
            raise MarketDataError("Maximum 500 symbols allowed per request")
        
        # Build params
        params = {
            'symbols': ','.join(symbols),
            'indicative': str(indicative).lower()
        }
        
        if fields:
            params['fields'] = ','.join(fields)
        
        response = await self._make_request("GET", "/marketdata/v1/quotes", params=params)
        return response.json()
    
    async def get_price_history(
        self,
        symbol: str,
        period_type: str = "day",
        period: int = 10,
        frequency_type: str = "minute",
        frequency: int = 1,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        need_extended_hours: bool = True,
        need_previous_close: bool = True
    ) -> Dict[str, Any]:
        """
        Get price history for a symbol.
        
        Args:
            symbol: Symbol to get history for
            period_type: Type of period (day, month, year, ytd)
            period: Number of periods
            frequency_type: Type of frequency (minute, daily, weekly, monthly)
            frequency: Frequency value
            start_date: Start date (optional)
            end_date: End date (optional)
            need_extended_hours: Include extended hours data
            need_previous_close: Include previous close
            
        Returns:
            Price history data with candles
        """
        # Build params
        params = {
            'periodType': period_type,
            'period': period,
            'frequencyType': frequency_type,
            'frequency': frequency,
            'needExtendedHoursData': str(need_extended_hours).lower(),
            'needPreviousClose': str(need_previous_close).lower()
        }
        
        # Add dates if provided
        if start_date:
            params['startDate'] = int(start_date.timestamp() * 1000)
            
        if end_date:
            params['endDate'] = int(end_date.timestamp() * 1000)
        
        # Use the appropriate client method based on frequency
        if frequency_type == "minute" and frequency == 1:
            # Only pass dates if they are provided
            kwargs = {
                'symbol': symbol,
                'need_extended_hours_data': need_extended_hours,
                'need_previous_close': need_previous_close
            }
            if start_date is not None:
                kwargs['start_datetime'] = start_date
            if end_date is not None:
                kwargs['end_datetime'] = end_date
                
            response = await self.client.get_price_history_every_minute(**kwargs)
        elif frequency_type == "minute" and frequency == 5:
            kwargs = {
                'symbol': symbol,
                'need_extended_hours_data': need_extended_hours,
                'need_previous_close': need_previous_close
            }
            if start_date is not None:
                kwargs['start_datetime'] = start_date
            if end_date is not None:
                kwargs['end_datetime'] = end_date
                
            response = await self.client.get_price_history_every_five_minutes(**kwargs)
        elif frequency_type == "daily":
            kwargs = {
                'symbol': symbol,
                'need_previous_close': need_previous_close
            }
            if start_date is not None:
                kwargs['start_datetime'] = start_date
            if end_date is not None:
                kwargs['end_datetime'] = end_date
                
            response = await self.client.get_price_history_every_day(**kwargs)
        else:
            # Fallback to generic method
            # This requires the schwab-py enums
            import schwab
            
            period_type_enum = getattr(schwab.client.Client.PriceHistory.PeriodType, period_type.upper(), None)
            frequency_type_enum = getattr(schwab.client.Client.PriceHistory.FrequencyType, frequency_type.upper(), None)
            
            response = await self.client.get_price_history(
                symbol=symbol,
                period_type=period_type_enum,
                period=period,
                frequency_type=frequency_type_enum,
                frequency=frequency,
                start_datetime=start_date,
                end_datetime=end_date,
                extended_hours_data=need_extended_hours,
                need_previous_close=need_previous_close
            )
        
        return response.json()
    
    # Utility Methods
    
    async def get_market_hours(
        self,
        markets: Union[str, List[str]],
        date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get market hours for specified markets.
        
        Args:
            markets: Market or list of markets (EQUITY, OPTION, BOND, FUTURE, FOREX)
            date: Date to check (defaults to today)
            
        Returns:
            Market hours information
        """
        # Convert single market to list
        if isinstance(markets, str):
            markets = [markets]
        
        # Build params
        params = {'markets': ','.join(markets)}
        
        if date:
            params['date'] = date.strftime('%Y-%m-%d')
        
        response = await self._make_request("GET", "/marketdata/v1/markets", params=params)
        return response.json()
    
    async def search_instruments(
        self,
        symbol: str,
        projection: str = "symbol-search"
    ) -> Dict[str, Any]:
        """
        Search for instruments.
        
        This wraps the schwab-py get_instruments method.
        
        Args:
            symbol: Symbol pattern to search
            projection: Search type (symbol-search, symbol-regex, desc-search, desc-regex, search, fundamental)
            
        Returns:
            Search results
        """
        if not self._initialized:
            await self.initialize()
            
        logger.debug(f"Searching instruments: symbol={symbol}, projection={projection}")
        
        try:
            # Map our projection values to schwab-py's Projection enum
            from schwab.client import Client
            
            projection_map = {
                'symbol-search': Client.Instrument.Projection.SYMBOL_SEARCH,
                'symbol-regex': Client.Instrument.Projection.SYMBOL_REGEX,
                'desc-search': Client.Instrument.Projection.DESCRIPTION_SEARCH,
                'desc-regex': Client.Instrument.Projection.DESCRIPTION_REGEX,
                'fundamental': Client.Instrument.Projection.FUNDAMENTAL,
                'search': Client.Instrument.Projection.SEARCH
            }
            
            # Get the enum value for projection
            if projection not in projection_map:
                logger.warning(f"Unknown projection: {projection}, defaulting to symbol-search")
                projection_enum = Client.Instrument.Projection.SYMBOL_SEARCH
            else:
                projection_enum = projection_map[projection]
            
            # Call schwab-py's get_instruments
            response = await self.client.get_instruments(symbol, projection_enum)
            
            # Check response status
            if hasattr(response, 'raise_for_status'):
                response.raise_for_status()
            
            # Extract JSON data
            if hasattr(response, 'json'):
                result = response.json()
            else:
                result = response
                
            logger.debug(f"search_instruments raw response: type={type(result)}, size={len(str(result))} chars")
            
            # Log structure without full data
            if isinstance(result, dict):
                logger.debug(f"Response is dict with keys: {list(result.keys())}")
                # Log structure of first value if it exists
                for key in list(result.keys())[:1]:
                    value = result[key]
                    if isinstance(value, dict):
                        logger.debug(f"Value for key '{key}' is dict with keys: {list(value.keys())[:10]}")
                    else:
                        logger.debug(f"Value for key '{key}' is type: {type(value)}")
            elif isinstance(result, list):
                logger.debug(f"Response is list with {len(result)} items")
                if result:
                    logger.debug(f"First item type: {type(result[0])}")
                    if isinstance(result[0], dict):
                        logger.debug(f"First item keys: {list(result[0].keys())[:10]}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error searching instruments for {symbol}: {e}", exc_info=True)
            return {}
    
    async def get_instruments(
        self,
        symbol: str,
        projection: str = "fundamental"
    ) -> Dict[str, Any]:
        """
        Get instruments data for a specific symbol.
        
        This is a wrapper around search_instruments for compatibility
        with the discovery service that expects get_instruments.
        
        Args:
            symbol: The symbol to get data for
            projection: Type of data to return (fundamental, quote, etc.)
            
        Returns:
            Dictionary with instruments data
        """
        try:
            # Use search_instruments with symbol-search projection
            result = await self.search_instruments(symbol, projection="symbol-search")
            
            logger.debug(f"search_instruments result for {symbol}: type={type(result)}, keys={list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
            
            # Log first few items if it's a list
            if isinstance(result, list) and result:
                logger.debug(f"First item in result list: {result[0]}")
            
            # The schwab-py API might return different formats
            # Check if it's already in the expected format
            if isinstance(result, dict) and "instruments" in result:
                logger.debug(f"Result already has 'instruments' key, returning as-is")
                return result
            
            # If result is a dict with symbol as key
            if isinstance(result, dict) and symbol.upper() in result:
                logger.debug(f"Found symbol {symbol.upper()} in result, wrapping in instruments list")
                return {"instruments": [result[symbol.upper()]]}
            
            # If result is a dict with lowercase symbol as key
            if isinstance(result, dict) and symbol.lower() in result:
                logger.debug(f"Found symbol {symbol.lower()} in result, wrapping in instruments list")
                return {"instruments": [result[symbol.lower()]]}
            
            # If result is a list, assume it's a list of instruments
            if isinstance(result, list):
                logger.debug(f"Result is a list with {len(result)} items, wrapping in instruments dict")
                return {"instruments": result}
            
            # If we have any result but couldn't match format, log it
            if result:
                logger.warning(f"Unexpected search_instruments format for {symbol}: {result}")
            
            return {"instruments": []}
            
        except Exception as e:
            logger.error(f"Error in get_instruments for {symbol}: {e}", exc_info=True)
            return {"instruments": []}
    
    async def get_movers(
        self,
        index: str,
        direction: str = "up",
        change: str = "percent"
    ) -> List[Dict[str, Any]]:
        """
        Get market movers for an index.
        
        Args:
            index: The index symbol (e.g., '$DJI', '$COMPX', '$SPX')
            direction: Direction of movement ('up' or 'down') - NOT USED by schwab-py
            change: Type of change ('percent' or 'volume') - NOT USED by schwab-py
            
        Returns:
            List of mover dictionaries
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            # Map index symbols to schwab-py's Index enum values
            from schwab.client import Client
            
            index_map = {
                '$DJI': Client.Movers.Index.DJI,
                '$COMPX': Client.Movers.Index.COMPX,  # or NASDAQ
                '$SPX': Client.Movers.Index.SPX,
                'DJI': Client.Movers.Index.DJI,
                'NASDAQ': Client.Movers.Index.NASDAQ,
                'COMPX': Client.Movers.Index.COMPX,
                'SPX': Client.Movers.Index.SPX,
                'NYSE': Client.Movers.Index.NYSE,
                'OTCBB': Client.Movers.Index.OTCBB
            }
            
            # Get the enum value for the index
            if index not in index_map:
                logger.warning(f"Unknown index: {index}, defaulting to SP_500")
                index_enum = Client.Movers.Index.SP_500
            else:
                index_enum = index_map[index]
            
            # Call the schwab-py client's get_movers with correct signature
            # Note: schwab-py doesn't take direction/change parameters
            response = await self.client.get_movers(index_enum)
            
            # Check if response has status code
            if hasattr(response, 'raise_for_status'):
                response.raise_for_status()
            
            # Extract the movers data
            if hasattr(response, 'json'):
                data = response.json()
            else:
                data = response
            
            logger.debug(f"Movers response type: {type(data)}")
            
            # The API might return different formats
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Check various possible keys
                for key in ['movers', 'screeners', 'items']:
                    if key in data:
                        return data[key]
                # If no known key, return the dict values as list
                return list(data.values())
            else:
                logger.warning(f"Unexpected movers response format: {type(data)}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get movers for {index}: {e}", exc_info=True)
            return []
    
    async def close(self):
        """Close the client and cleanup resources."""
        if self.client and hasattr(self.client, 'close'):
            await self.client.close()
        
        if self.auth_service:
            await self.auth_service.shutdown()
        
        logger.info("SchwabBroker closed")
    
    def get_price_history_sync(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Synchronous version of get_price_history for use in Celery tasks.
        
        Args:
            Same as get_price_history
            
        Returns:
            Price history data
        """
        import asyncio
        
        # Use the existing event loop if available, or create a new one
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, just await
            return asyncio.create_task(self.get_price_history(**kwargs))
        except RuntimeError:
            # No running loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.get_price_history(**kwargs))
            finally:
                loop.close()
    
    # Context manager support
    
    async def __aenter__(self):
        """Enter async context."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self.close()


# Convenience function
async def get_schwab_broker() -> SchwabBroker:
    """
    Get initialized SchwabBroker instance.
    
    Returns:
        Initialized SchwabBroker
    """
    broker = SchwabBroker()
    await broker.initialize()
    return broker


def get_schwab_broker_sync() -> SchwabBroker:
    """
    Get initialized SchwabBroker instance synchronously.
    
    This is useful for Celery tasks that need to run in sync context.
    
    Returns:
        Initialized SchwabBroker
    """
    import asyncio
    
    broker = SchwabBroker()
    
    # Create a new event loop for sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(broker.initialize())
        return broker
    except Exception:
        loop.close()
        raise
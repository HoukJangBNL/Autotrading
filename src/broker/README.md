# Broker Module

This module provides a comprehensive integration with the Schwab API for automated trading operations.

## Components

### SchwabBroker
The main broker client that handles all interactions with the Schwab API.

**Features:**
- Singleton pattern for single instance management
- Automatic OAuth token management
- Built-in rate limiting and circuit breaker
- Comprehensive error handling and retry logic
- Request/response logging with sensitive data masking

### RateLimiter
Implements multiple rate limiting strategies to prevent API throttling.

**Strategies:**
- **Token Bucket**: Allows burst traffic while maintaining average rate
- **Sliding Window**: Strict rate enforcement over time windows
- **Adaptive**: Automatically adjusts rate based on response times

### CircuitBreaker
Prevents cascading failures by failing fast when the API is experiencing issues.

**States:**
- **CLOSED**: Normal operation
- **OPEN**: Failing, reject requests
- **HALF_OPEN**: Testing recovery

## Usage

### Basic Setup

```python
from src.broker import SchwabBroker, get_schwab_broker

# Using convenience function (recommended)
broker = await get_schwab_broker()

# Or manual initialization
broker = SchwabBroker()
await broker.initialize()
```

### Account Operations

```python
# Get account numbers
accounts = await broker.get_account_numbers()

# Get account information
account_info = await broker.get_account_info(
    account_number="12345678",
    fields=["positions", "orders"]
)

# Get positions
positions = await broker.get_positions("12345678")

# Get orders
orders = await broker.get_orders(
    account_number="12345678",
    from_entered_time=datetime.now() - timedelta(days=7),
    status="WORKING"
)
```

### Trading Operations

```python
# Place an order
from schwab.orders.equities import equity_buy_limit

order = equity_buy_limit("AAPL", 10, 150.00)
result = await broker.place_order("12345678", order)
print(f"Order ID: {result['order_id']}")

# Or using a dict
order_dict = {
    'orderType': 'LIMIT',
    'session': 'NORMAL',
    'duration': 'DAY',
    'orderStrategyType': 'SINGLE',
    'price': 150.00,
    'orderLegCollection': [{
        'instruction': 'BUY',
        'quantity': 10,
        'instrument': {'symbol': 'AAPL', 'assetType': 'EQUITY'}
    }]
}
result = await broker.place_order("12345678", order_dict)

# Cancel an order
await broker.cancel_order("12345678", order_id)
```

### Market Data

```python
# Get quotes
quotes = await broker.get_quotes(["AAPL", "GOOGL", "MSFT"])
print(f"AAPL Last: ${quotes['AAPL']['last']}")

# Get price history
history = await broker.get_price_history(
    symbol="AAPL",
    period_type="day",
    period=5,
    frequency_type="minute",
    frequency=5
)

# Get market hours
hours = await broker.get_market_hours(["EQUITY", "OPTION"])
```

### Using Context Manager

```python
async with SchwabBroker() as broker:
    # Broker is automatically initialized
    accounts = await broker.get_account_numbers()
    # ... perform operations
# Automatically cleaned up on exit
```

## Error Handling

The broker provides specific exceptions for different error scenarios:

```python
from src.broker.exceptions import (
    BrokerError,
    RateLimitError,
    InvalidOrderError,
    OrderNotFoundError,
    InsufficientFundsError,
    MarketDataError
)

try:
    await broker.place_order(account, order)
except InvalidOrderError as e:
    print(f"Order validation failed: {e}")
except InsufficientFundsError as e:
    print(f"Not enough funds: {e}")
except RateLimitError as e:
    print(f"Rate limited, try again later: {e}")
except BrokerError as e:
    print(f"General broker error: {e}")
```

## Rate Limiting

The broker includes automatic rate limiting, but you can also use the rate limiter directly:

```python
from src.broker import RateLimiter

# Create custom rate limiter
limiter = RateLimiter(
    rate=60,           # 60 requests
    period=60.0,       # per 60 seconds
    burst=15,          # allow burst of 15
    strategy="token_bucket"
)

# Use in custom code
await limiter.acquire()  # Wait if needed
# ... make request

# Or check without waiting
if limiter.try_acquire():
    # ... make request
else:
    # Rate limited, handle accordingly
    pass
```

## Circuit Breaker

The circuit breaker helps prevent cascading failures:

```python
from src.broker import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,    # Open after 5 failures
    recovery_timeout=30.0,  # Try recovery after 30s
    success_threshold=2     # Need 2 successes to close
)

# Check circuit state
if breaker.can_request():
    try:
        result = await make_request()
        breaker.record_success()
    except Exception as e:
        breaker.record_failure()
        raise
```

## Configuration

The broker uses settings from the configuration module, but you can override:

```python
# Custom rate limiter
custom_limiter = RateLimiter(rate=30, period=60)

# Custom circuit breaker
custom_breaker = CircuitBreaker(failure_threshold=10)

# Initialize with custom components
broker = SchwabBroker(
    rate_limiter=custom_limiter,
    circuit_breaker=custom_breaker
)
```

## Monitoring

Get statistics from rate limiter and circuit breaker:

```python
# Rate limiter stats
limiter_stats = broker.rate_limiter.get_stats()
print(f"Total requests: {limiter_stats['total_requests']}")
print(f"Average wait time: {limiter_stats['average_wait_time']:.2f}s")

# Circuit breaker stats
breaker_stats = broker.circuit_breaker.get_stats()
print(f"State: {breaker_stats['state']}")
print(f"Success rate: {breaker_stats['success_rate']:.2%}")
```

## Best Practices

1. **Always use context manager or ensure proper cleanup**
   ```python
   async with SchwabBroker() as broker:
       # Your code here
   ```

2. **Handle specific exceptions**
   ```python
   try:
       await broker.place_order(account, order)
   except InvalidOrderError:
       # Handle validation errors
   except InsufficientFundsError:
       # Handle funding issues
   ```

3. **Use appropriate field filters**
   ```python
   # Only request needed fields to reduce response size
   account_info = await broker.get_account_info(
       account_number,
       fields=["positions"]  # Don't request orders if not needed
   )
   ```

4. **Batch operations when possible**
   ```python
   # Get quotes for multiple symbols in one request
   quotes = await broker.get_quotes(["AAPL", "GOOGL", "MSFT"])
   ```

5. **Monitor rate limits**
   ```python
   stats = broker.rate_limiter.get_stats()
   if stats['rejected_requests'] > 0:
       # Consider reducing request rate
       pass
   ```

## Testing

The module includes comprehensive tests:

```bash
# Run unit tests
pytest tests/test_schwab_broker.py -v

# Run rate limiter tests
pytest tests/test_rate_limiter.py -v

# Run integration tests
pytest tests/test_schwab_integration.py -v

# Run all broker tests
pytest tests/test_schwab*.py tests/test_rate*.py -v
```

## Troubleshooting

### Authentication Issues
- Ensure OAuth tokens are valid (7-day expiration)
- Check auth setup with `python scripts/auth_setup.py`
- Verify API credentials in `.env` file

### Rate Limiting
- Default limit is 120 requests/minute
- Use batch operations to reduce request count
- Monitor rate limiter statistics
- Consider implementing caching for frequently accessed data

### Connection Issues
- Check circuit breaker state
- Verify network connectivity
- Review error logs for specific failure reasons
- Ensure Schwab API is operational

### Order Failures
- Validate order structure before submission
- Check account buying power
- Ensure market hours for session type
- Verify symbol validity
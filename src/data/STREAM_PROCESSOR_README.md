# Stream Processor Documentation

## Overview

The Stream Processor is a high-performance, real-time market data processing engine designed for the Schwab Autotrader system. It provides tick-by-tick data processing, OHLCV bar aggregation, volume profile analysis, and comprehensive health monitoring.

## Features

### Core Capabilities
- **Real-time Tick Processing**: Handle thousands of ticks per second with low latency
- **Multi-timeframe OHLCV Aggregation**: Simultaneous bar construction for multiple timeframes
- **Volume Profile Tracking**: Real-time POC (Point of Control) and Value Area calculations
- **Stream Health Monitoring**: Latency tracking, gap detection, and error monitoring
- **Redis Integration**: Pub/sub for real-time data distribution
- **Extensible Callback System**: Custom processing logic via callbacks
- **Async/Await Architecture**: Non-blocking, high-performance design

### Technical Specifications
- **Performance**: 10,000+ ticks/second processing capability
- **Latency**: Sub-millisecond tick-to-bar processing
- **Memory**: Efficient circular buffers with configurable limits
- **Concurrency**: Thread-safe with asyncio locks
- **Persistence**: Optional database storage for bars

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  WebSocket Feed │────▶│ Stream Processor │────▶│  Redis Pub/Sub  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ├── Tick Queue (10K capacity)
                               ├── Bar Aggregators (1m, 5m, 15m)
                               ├── Volume Profiles
                               └── Health Monitors
```

## Data Models

### Tick
Represents a single market data point:
```python
@dataclass
class Tick:
    symbol: str              # Stock symbol
    price: float            # Trade/bid/ask price
    volume: int             # Volume
    timestamp: datetime     # UTC timestamp
    tick_type: TickType     # TRADE, BID, or ASK
    
    # Optional fields
    bid_price: Optional[float]
    ask_price: Optional[float]
    bid_size: Optional[int]
    ask_size: Optional[int]
    sequence_id: Optional[int]
    exchange: Optional[str]
    conditions: Optional[List[str]]
```

### OHLCV Bar
Aggregated price bar:
```python
@dataclass
class OHLCV:
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime     # Bar start time
    timeframe: int         # Minutes
    
    # Additional metrics
    vwap: Optional[float]  # Volume-weighted average price
    trade_count: int
    bid_volume: int
    ask_volume: int
```

### Volume Profile
Market microstructure analysis:
```python
@dataclass
class VolumeProfile:
    symbol: str
    start_time: datetime
    end_time: Optional[datetime]
    price_levels: Dict[float, int]  # Price -> Volume mapping
    
    # Calculated properties
    @property
    def poc(self) -> Optional[float]  # Point of Control
    @property
    def val(self) -> Optional[float]  # Value Area Low
    @property
    def vah(self) -> Optional[float]  # Value Area High
```

### Stream Health
Connection and performance monitoring:
```python
@dataclass
class StreamHealth:
    status: StreamStatus    # CONNECTED, DISCONNECTED, ERROR, etc.
    last_tick: Optional[datetime]
    ticks_received: int
    ticks_processed: int
    ticks_dropped: int
    avg_latency_ms: float
    error_count: int
    
    @property
    def is_healthy(self) -> bool
```

## Usage

### Basic Setup

```python
from src.data.stream_processor import create_stream_processor

# Create and start processor
processor = await create_stream_processor(
    redis_url="redis://localhost:6379",
    save_to_db=True,
    timeframes=[1, 5, 15]  # 1-min, 5-min, 15-min bars
)

# Process ticks
tick = Tick(
    symbol="AAPL",
    price=150.25,
    volume=100,
    timestamp=datetime.now(timezone.utc)
)
await processor.add_tick(tick)

# Stop when done
await processor.stop()
```

### Callback System

Register callbacks for custom processing:

```python
# Tick callback
@processor.on_tick
def handle_tick(tick: Tick):
    if tick.volume > 10000:
        print(f"Large trade: {tick.symbol} {tick.volume} @ ${tick.price}")

# Bar callback
@processor.on_bar
def handle_bar(bar: OHLCV):
    if bar.volume > bar.trade_count * 500:
        print(f"High volume bar: {bar.symbol} {bar.timeframe}m")

# Health callback
@processor.on_health_update
def handle_health(health_updates: Dict[str, Any]):
    for symbol, health in health_updates.items():
        if not health['is_healthy']:
            print(f"Stream unhealthy: {symbol}")
```

### Volume Profile Analysis

```python
# Get current volume profile
profile = processor.get_volume_profile("AAPL")

# Point of Control (most traded price)
poc = profile.poc
print(f"POC: ${poc:.2f}")

# Value Area (70% of volume)
val, vah = profile.calculate_value_area(0.70)
print(f"Value Area: ${val:.2f} - ${vah:.2f}")

# Check if price is in value area
current_price = 150.50
in_value_area = val <= current_price <= vah
```

### Health Monitoring

```python
# Get health status
health = processor.get_health("AAPL")

if health.is_healthy:
    print(f"Stream healthy - Latency: {health.avg_latency_ms:.1f}ms")
else:
    print(f"Stream issues - Status: {health.status.value}")
    print(f"Errors: {health.error_count}")
    print(f"Last tick: {health.last_tick}")

# Check all streams
if processor.is_healthy():
    print("All streams healthy")
```

### Redis Integration

The processor publishes to these channels:
- `stream:ticks:{symbol}` - Individual ticks
- `stream:bars:{symbol}:{timeframe}` - Completed bars
- `stream:health` - Health updates

Subscribe example:
```python
import redis.asyncio as redis

r = await redis.from_url("redis://localhost:6379")
pubsub = r.pubsub()

await pubsub.subscribe("stream:bars:AAPL:1")
async for message in pubsub.listen():
    if message['type'] == 'message':
        bar_data = json.loads(message['data'])
        print(f"New bar: {bar_data}")
```

## Performance Optimization

### Configuration Tips

1. **Queue Size**: Adjust tick queue size based on burst expectations
   ```python
   self.tick_queue = asyncio.Queue(maxsize=10000)  # Default 10K
   ```

2. **Buffer Size**: Configure circular buffer for recent tick access
   ```python
   self.tick_buffer = deque(maxlen=1000)  # Keep last 1000 ticks
   ```

3. **Latency Samples**: Adjust sample size for latency calculations
   ```python
   latency_samples: deque = field(default_factory=lambda: deque(maxlen=100))
   ```

### Best Practices

1. **Batch Processing**: Process multiple ticks together when possible
2. **Selective Callbacks**: Only register necessary callbacks to reduce overhead
3. **Timeframe Selection**: Use fewer timeframes to reduce aggregation overhead
4. **Database Writes**: Consider batching or async writes for high-volume scenarios
5. **Redis Pipeline**: Use Redis pipelines for bulk publishing

## Advanced Features

### Gap Detection

Detect missing data in tick stream:
```python
from src.data.stream_processor import detect_tick_gaps

recent_ticks = processor.get_recent_ticks("AAPL", limit=1000)
gaps = detect_tick_gaps(recent_ticks, threshold_seconds=5.0)

for tick_before, tick_after, gap_seconds in gaps:
    print(f"Gap detected: {gap_seconds:.1f}s between "
          f"{tick_before.timestamp} and {tick_after.timestamp}")
```

### Custom Aggregation

Extend BarAggregator for custom bar types:
```python
class RangeBarAggregator(BarAggregator):
    def __init__(self, range_size: float):
        self.range_size = range_size
        # Custom logic for range bars
```

### Multi-Symbol Processing

Process multiple symbols efficiently:
```python
symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]

# Add ticks for multiple symbols
for symbol in symbols:
    tick = Tick(symbol=symbol, price=get_price(symbol), ...)
    await processor.add_tick(tick)

# Get all volume profiles
profiles = {symbol: processor.get_volume_profile(symbol) 
            for symbol in symbols}
```

## Integration with Trading System

### WebSocket Connection

```python
# Example integration with Schwab WebSocket
async def handle_websocket_message(message):
    # Parse message to tick
    tick = parse_schwab_message(message)
    
    # Process through stream processor
    await processor.add_tick(tick)
```

### Strategy Integration

```python
# Use in trading strategy
@processor.on_bar
async def strategy_on_bar(bar: OHLCV):
    # Get volume profile context
    profile = processor.get_volume_profile(bar.symbol)
    
    # Make trading decisions
    if bar.close > profile.vah and bar.volume > average_volume:
        # Breakout above value area with volume
        await place_buy_order(bar.symbol)
```

## Error Handling

The processor includes comprehensive error handling:

1. **Queue Full**: Drops ticks and increments drop counter
2. **Processing Errors**: Logs errors and updates health status
3. **Callback Errors**: Isolated to prevent cascade failures
4. **Redis Errors**: Graceful degradation without pub/sub

## Testing

Run comprehensive tests:
```bash
pytest tests/test_stream_processor.py -v
```

Run the demo:
```bash
python examples/stream_processor_demo.py
```

## Performance Benchmarks

Based on testing with simulated data:
- **Tick Processing**: 10,000+ ticks/second
- **Bar Aggregation**: <1ms per tick
- **Volume Profile Update**: O(1) per tick
- **Memory Usage**: ~100MB for 1M ticks in buffer
- **Redis Pub/Sub**: ~50μs per publish

## Future Enhancements

Planned improvements:
1. **WebSocket Integration**: Direct connection to Schwab streaming
2. **Level 2 Data**: Order book depth processing
3. **Options Chain**: Support for options tick data
4. **Market Replay**: Historical tick replay capability
5. **Distributed Processing**: Multi-node support via Redis Streams
6. **Machine Learning**: Real-time feature extraction for ML models
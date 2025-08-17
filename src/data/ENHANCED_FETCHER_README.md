# Enhanced Historical Data Fetcher

## Overview

The Enhanced Historical Data Fetcher provides advanced capabilities for fetching and managing historical market data from the Schwab API. It includes batch processing, parallel fetching, progress tracking, data validation, duplicate detection, and gap analysis.

## Key Features

### 1. Batch Symbol Processing
- Process multiple symbols concurrently with configurable batch sizes
- Efficient work distribution using asyncio queues
- Configurable worker pool for parallel processing

### 2. Parallel Data Fetching
- Multiple concurrent workers (default: 10)
- Automatic rate limiting with exponential backoff
- Semaphore-based concurrency control
- Worker pool pattern for optimal resource utilization

### 3. Progress Tracking
- Real-time progress updates with callbacks
- Multiple callback implementations:
  - `LoggingProgressCallback`: Periodic logging updates
  - `DetailedProgressCallback`: Detailed progress with ETA
  - Custom callbacks via `ProgressCallback` protocol
- Progress statistics including completion rate, ETA, and throughput

### 4. Data Validation Pipeline
- Pluggable validator system
- Built-in validators:
  - `OHLCValidator`: Validates price relationships
  - `VolumeValidator`: Checks volume bounds
  - `TimestampValidator`: Validates timestamp ranges
- Support for custom validators
- Validation warnings vs errors

### 5. Duplicate Detection
- Automatic detection of existing data in database
- Prevents redundant API calls and storage
- Configurable duplicate handling strategies

### 6. Missing Data Detection
- Gap analysis using SQL window functions
- Configurable gap thresholds
- Market hours awareness
- Automatic gap filling capabilities

## Usage

### Basic Usage

```python
from src.data.historical_data_enhanced import (
    EnhancedHistoricalDataFetcher,
    TimeFrame,
    LoggingProgressCallback
)

# Initialize fetcher
fetcher = EnhancedHistoricalDataFetcher(
    max_workers=10,
    batch_size=10
)
await fetcher.initialize()

# Add progress tracking
fetcher.add_progress_callback(LoggingProgressCallback())

# Fetch data for multiple symbols
result = await fetcher.fetch_symbols_batch(
    symbols=['AAPL', 'GOOGL', 'MSFT'],
    timeframe=TimeFrame.DAILY,
    start_date=datetime.now() - timedelta(days=30),
    save_to_db=True,
    detect_duplicates=True,
    fill_gaps=True
)

# Check results
print(f"Fetched {result['statistics']['total_records']} records")
print(f"Found {result['statistics']['duplicates_found']} duplicates")
print(f"Filled {result['statistics']['gaps_filled']} gaps")
```

### Custom Validation

```python
from src.data.historical_data_enhanced import (
    DataValidator,
    ValidationResult,
    ValidationPipeline
)

class CustomValidator(DataValidator):
    async def validate(self, data: dict) -> ValidationResult:
        # Your validation logic
        if data['volume'] > 1000000000:
            return ValidationResult(
                is_valid=True,
                warnings=["Unusually high volume"]
            )
        return ValidationResult(is_valid=True)

# Use custom pipeline
pipeline = ValidationPipeline(validators=[
    OHLCValidator(),
    CustomValidator()
])

fetcher.validation_pipeline = pipeline
```

### Progress Monitoring

```python
# Custom progress callback
async def my_progress_callback(progress: FetchProgress, message: str):
    print(f"Progress: {progress.progress_percentage:.1f}% - {message}")
    print(f"ETA: {progress.estimated_time_remaining:.0f} seconds")

fetcher.add_progress_callback(my_progress_callback)
```

### Gap Detection and Filling

```python
# Detect missing data
gaps = await fetcher.detect_missing_data(
    symbol='AAPL',
    timeframe=TimeFrame.MINUTE_5,
    start_date=start_date,
    end_date=end_date,
    market_hours_only=True
)

print(f"Found {len(gaps)} data gaps")

# Fill gaps automatically during fetch
result = await fetcher.fetch_symbols_batch(
    symbols=['AAPL'],
    timeframe=TimeFrame.MINUTE_5,
    fill_gaps=True
)
```

## Configuration

### Environment Variables
- `BATCH_INSERT_SIZE`: Database batch size (default: 1000)
- `MAX_WORKERS`: Maximum concurrent workers (default: 10)

### Fetcher Parameters
- `max_workers`: Number of concurrent workers (1-20)
- `batch_size`: Symbols per batch (1-50)
- `validation_pipeline`: Custom validation pipeline
- `broker`: Custom SchwabBroker instance

## Performance Considerations

1. **Worker Count**: More workers = faster fetching but higher API load
2. **Batch Size**: Larger batches reduce overhead but may hit memory limits
3. **Validation**: Disable validation for faster processing if data quality is guaranteed
4. **Database Operations**: Batch inserts are optimized for PostgreSQL

## Error Handling

The fetcher includes comprehensive error handling:
- Automatic retry with exponential backoff
- Rate limit detection and adaptation
- Worker isolation (one symbol failure doesn't affect others)
- Detailed error reporting in results

## Migration from Original Fetcher

To migrate from the original `HistoricalDataFetcher`:

1. Replace import:
   ```python
   # Old
   from src.data.historical_data import HistoricalDataFetcher
   
   # New
   from src.data.historical_data_enhanced import EnhancedHistoricalDataFetcher
   ```

2. Update initialization:
   ```python
   # Old
   fetcher = HistoricalDataFetcher()
   
   # New
   fetcher = EnhancedHistoricalDataFetcher(max_workers=10)
   ```

3. Use batch methods:
   ```python
   # Old
   data = await fetcher.fetch_multiple_symbols(symbols, ...)
   
   # New
   result = await fetcher.fetch_symbols_batch(symbols, ...)
   data = result['results']
   ```

## Testing

Run the comprehensive test suite:

```bash
pytest tests/test_historical_data_enhanced.py -v
```

Run the demo script:

```bash
python examples/historical_data_demo.py
```

## Future Enhancements

1. **Streaming Integration**: Real-time data updates
2. **Caching Layer**: Redis-based caching for frequently accessed data
3. **Data Compression**: Store compressed data for older periods
4. **Advanced Gap Strategies**: Different strategies for different timeframes
5. **Market Calendar**: Holiday awareness for gap detection
# Data Mining Mode Implementation Guide

## Overview

Data Mining Mode는 매일 Pre-market 시간(오전 4:00-9:30 EST)에 실행되어 거래할 종목들의 최근 2달치 1분봉 데이터를 수집합니다. 핵심 종목부터 시작하여 점진적으로 확장하는 전략을 사용합니다.

## Core Architecture

### 1. Ticker Management Strategy

#### Phase 1: Core Tickers (MVP)
```json
{
    "core_tickers": [
        // Mega caps (시총 상위)
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
        
        // Blue chips (안정적 대형주)
        "BRK.B", "JPM", "JNJ", "V", "PG", "UNH", "HD", "MA",
        
        // Major ETFs (시장 지표)
        "SPY", "QQQ", "IWM", "DIA", "VTI", "ARKK", "XLF", "XLK",
        
        // High volume traders (고거래량)
        "AMD", "BAC", "F", "PLTR", "SOFI", "NIO", "AAL", "T"
    ]
}
```

#### Progressive Expansion Plan
1. **Week 1-2**: 30-50개 핵심 종목
2. **Week 3-4**: S&P 100 구성 종목 추가 (~100개)
3. **Month 2**: NASDAQ 100 추가 (~200개)
4. **Month 3+**: 고거래량/변동성 종목 동적 추가

### 2. Data Collection Strategy

#### Pre-market Schedule (EST)
```
04:00 AM - 시스템 시작, 데이터베이스 체크
04:15 AM - Core tickers 데이터 수집 시작 (우선순위: 높음)
05:00 AM - Core 완료 확인, expansion tickers 시작
06:30 AM - 데이터 검증 및 gap filling
07:00 AM - Backtesting mode 준비
09:00 AM - 수집 종료, 리포트 생성
```

#### Data Requirements
- **기간**: 최근 60일 (약 2달)
- **간격**: 1분봉 (1-minute candles)
- **데이터**: OHLCV (Open, High, Low, Close, Volume)
- **예상 크기**: 종목당 ~20,000 candles (60일 × 390분/일 × 0.85)

### 3. Implementation Components

#### 3.1 Ticker Manager
```python
# src/data/ticker_manager.py
class TickerManager:
    """Manages ticker lists and expansion strategy."""
    
    def __init__(self):
        self.core_tickers = self._load_core_tickers()
        self.expanded_tickers = set()
        self.blacklist = set()  # 거래 중지, 상폐 등
        
    def get_daily_targets(self) -> List[str]:
        """Get today's mining targets based on priority."""
        targets = []
        
        # 1. Always include core tickers
        targets.extend(self.core_tickers)
        
        # 2. Add expanded tickers if enabled
        if self._should_expand():
            targets.extend(self._get_expansion_candidates())
            
        # 3. Remove blacklisted
        targets = [t for t in targets if t not in self.blacklist]
        
        return targets[:MAX_DAILY_TICKERS]  # Limit to avoid overload
```

#### 3.2 Mining Service
```python
# src/services/data_mining_service.py
class DataMiningService:
    """Orchestrates data collection process."""
    
    async def run_daily_mining(self):
        """Main entry point for daily mining."""
        logger.info("Starting daily data mining...")
        
        # Get today's targets
        tickers = self.ticker_manager.get_daily_targets()
        
        # Group by priority
        priority_groups = self._prioritize_tickers(tickers)
        
        # Mine each group
        for priority, group in priority_groups.items():
            await self._mine_group(group, priority)
            
        # Verify and report
        report = await self._generate_mining_report()
        await self._send_notification(report)
```

#### 3.3 Rate Limit Management
```python
# src/utils/rate_limiter.py
class SchwabRateLimiter:
    """Manages API rate limits for Schwab."""
    
    def __init__(self):
        self.limit = 60  # requests per minute
        self.window = 60  # seconds
        self.requests = deque()
        
    async def acquire(self):
        """Wait if necessary to respect rate limits."""
        now = time.time()
        
        # Remove old requests
        while self.requests and self.requests[0] < now - self.window:
            self.requests.popleft()
            
        # Wait if at limit
        if len(self.requests) >= self.limit:
            sleep_time = self.window - (now - self.requests[0]) + 0.1
            await asyncio.sleep(sleep_time)
            
        self.requests.append(now)
```

### 4. Database Schema

#### Tickers Table
```sql
CREATE TABLE tickers (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255),
    tier VARCHAR(20) DEFAULT 'expanded',  -- 'core', 'expanded', 'dynamic'
    active BOOLEAN DEFAULT true,
    last_mined TIMESTAMP,
    mining_status VARCHAR(20),  -- 'pending', 'mining', 'completed', 'failed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tickers_symbol ON tickers(symbol);
CREATE INDEX idx_tickers_tier ON tickers(tier);
CREATE INDEX idx_tickers_active ON tickers(active);
```

#### Mining Status Table
```sql
CREATE TABLE mining_status (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    date DATE NOT NULL,
    candles_expected INTEGER,
    candles_received INTEGER,
    gaps_detected INTEGER DEFAULT 0,
    status VARCHAR(20),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    UNIQUE(ticker_id, date)
);
```

### 5. Celery Tasks

#### Main Mining Task
```python
# src/tasks/data_mining.py
@celery_app.task(bind=True, max_retries=3)
def mine_ticker_data(self, ticker_id: int, symbol: str):
    """Mine 2 months of data for a single ticker."""
    
    try:
        # Update status
        update_mining_status(ticker_id, 'mining')
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        # Fetch from Schwab API
        with rate_limiter:
            candles = schwab_client.get_price_history(
                symbol=symbol,
                period_type='month',
                period=2,
                frequency_type='minute',
                frequency=1
            )
        
        # Process and store
        processed = process_candles(candles)
        bulk_insert_candles(ticker_id, processed)
        
        # Update status
        update_mining_status(ticker_id, 'completed', 
                           candles_received=len(processed))
        
        return f"Successfully mined {len(processed)} candles for {symbol}"
        
    except Exception as e:
        update_mining_status(ticker_id, 'failed', error=str(e))
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

#### Scheduled Tasks
```python
# Celery Beat Schedule
beat_schedule = {
    # Daily mining at 4:00 AM EST
    'daily-mining': {
        'task': 'src.tasks.data_mining.start_daily_mining',
        'schedule': crontab(hour=4, minute=0),
        'kwargs': {'mode': 'auto'}
    },
    
    # Hourly progress check during mining window
    'mining-progress': {
        'task': 'src.tasks.data_mining.check_mining_progress',
        'schedule': crontab(minute=0),
        'kwargs': {'alert_on_delays': True}
    },
    
    # Weekly expansion check
    'ticker-expansion': {
        'task': 'src.tasks.data_mining.evaluate_expansion',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),
    }
}
```

### 6. API Endpoints

```python
# src/api/routers/data_mining.py

@router.get("/mining/status")
async def get_mining_status():
    """Get current mining status and statistics."""
    return {
        "active_jobs": get_active_mining_jobs(),
        "completed_today": get_completed_count(),
        "pending": get_pending_count(),
        "failed": get_failed_tickers(),
        "next_run": get_next_scheduled_run()
    }

@router.post("/mining/start")
async def start_mining(
    tickers: Optional[List[str]] = None,
    priority: str = "normal"
):
    """Manually start mining for specific tickers."""
    if not tickers:
        tickers = ticker_manager.get_daily_targets()
    
    job_id = start_mining_job(tickers, priority)
    return {"job_id": job_id, "tickers": len(tickers)}

@router.get("/mining/report/{date}")
async def get_mining_report(date: str):
    """Get detailed mining report for a specific date."""
    return generate_mining_report(date)
```

### 7. Monitoring and Alerts

#### Health Checks
```python
# src/monitoring/health_checks.py
class MiningHealthCheck:
    """Monitors mining system health."""
    
    async def check_mining_health(self) -> Dict:
        checks = {
            "database": await self._check_database(),
            "redis": await self._check_redis(),
            "schwab_api": await self._check_schwab_connection(),
            "disk_space": await self._check_disk_space(),
            "mining_progress": await self._check_mining_progress()
        }
        
        return {
            "status": "healthy" if all(checks.values()) else "unhealthy",
            "checks": checks,
            "timestamp": datetime.now()
        }
```

#### Alert System
```python
# src/monitoring/alerts.py
class MiningAlerts:
    """Sends alerts for mining issues."""
    
    async def check_and_alert(self):
        # Check for stalled jobs
        stalled = await get_stalled_mining_jobs()
        if stalled:
            await self.send_alert(
                level="warning",
                message=f"{len(stalled)} mining jobs stalled",
                details=stalled
            )
        
        # Check for high failure rate
        failure_rate = await get_failure_rate()
        if failure_rate > 0.1:  # 10%
            await self.send_alert(
                level="error",
                message=f"High failure rate: {failure_rate:.1%}",
                action="Check API limits and network"
            )
```

### 8. Progressive Expansion Strategy

#### Automatic Expansion
```python
# src/data/expansion_manager.py
class ExpansionManager:
    """Manages progressive ticker expansion."""
    
    async def evaluate_expansion(self):
        """Weekly evaluation for expansion."""
        
        metrics = await self._get_system_metrics()
        
        # Check if ready for expansion
        if self._should_expand(metrics):
            # Get next batch of tickers
            new_tickers = await self._get_next_expansion_batch()
            
            # Add to database
            for ticker in new_tickers:
                await self._add_ticker(ticker, tier='expanded')
                
            logger.info(f"Expanded ticker list by {len(new_tickers)} symbols")
    
    def _should_expand(self, metrics: Dict) -> bool:
        """Determine if system is ready for expansion."""
        return (
            metrics['completion_rate'] > 0.95 and  # 95% success rate
            metrics['avg_mining_time'] < 300 and   # Under 5 min per ticker
            metrics['disk_usage'] < 0.7 and        # 70% disk usage
            metrics['api_errors'] < 5              # Low error rate
        )
```

### 9. Error Recovery

#### Gap Detection and Filling
```python
# src/data/gap_detector.py
class GapDetector:
    """Detects and fills data gaps."""
    
    async def check_and_fill_gaps(self, ticker_id: int):
        """Check for missing candles and fill gaps."""
        
        # Get expected vs actual candle count
        expected = self._calculate_expected_candles(ticker_id)
        actual = await self._get_actual_candle_count(ticker_id)
        
        if actual < expected * 0.95:  # More than 5% missing
            gaps = await self._identify_gaps(ticker_id)
            
            for gap in gaps:
                # Schedule gap filling task
                fill_data_gap.apply_async(
                    args=[ticker_id, gap['start'], gap['end']],
                    priority=5  # Lower priority than daily mining
                )
```

### 10. Performance Optimization

#### Batch Processing
```python
# src/utils/batch_processor.py
class BatchProcessor:
    """Optimizes bulk data operations."""
    
    async def bulk_insert_candles(self, candles: List[Dict]):
        """Efficient bulk insert with chunking."""
        
        chunk_size = 1000  # PostgreSQL optimal chunk size
        
        for i in range(0, len(candles), chunk_size):
            chunk = candles[i:i + chunk_size]
            
            # Use COPY command for fastest insert
            await self._copy_from_csv(chunk)
            
        # Update indexes after bulk insert
        await self._refresh_indexes()
```

## Testing Strategy

### Unit Tests
```python
# tests/test_data_mining.py
def test_ticker_prioritization():
    """Test that core tickers are prioritized."""
    
def test_rate_limiting():
    """Test rate limiter respects limits."""
    
def test_gap_detection():
    """Test gap detection algorithm."""
```

### Integration Tests
```python
# tests/integration/test_mining_flow.py
async def test_full_mining_cycle():
    """Test complete mining workflow."""
    
async def test_error_recovery():
    """Test recovery from API errors."""
```

## Deployment Checklist

### Pre-deployment
- [ ] Configure core ticker list
- [ ] Set up PostgreSQL with TimescaleDB
- [ ] Configure Celery Beat schedule
- [ ] Test Schwab API connection
- [ ] Set rate limits appropriately

### Monitoring Setup
- [ ] Configure health check endpoints
- [ ] Set up alert notifications
- [ ] Create Grafana dashboards
- [ ] Configure log aggregation

### Performance Targets
- **Mining Speed**: < 5 minutes per ticker
- **Success Rate**: > 95%
- **Data Completeness**: > 98%
- **API Error Rate**: < 1%
- **System Uptime**: > 99%

## Next Steps

1. **Week 1**: Implement core ticker mining
2. **Week 2**: Add monitoring and alerts
3. **Week 3**: Implement expansion logic
4. **Week 4**: Optimize performance
5. **Month 2**: Scale to 200+ tickers
6. **Month 3**: Full automation with 500+ tickers
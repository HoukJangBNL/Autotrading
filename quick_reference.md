# Quick Reference - Schwab Autotrading Development

## 🚀 Daily Development Commands

### Start Development Environment
```bash
# 1. Start Docker services
docker compose up -d postgres redis

# 2. Activate Python environment
source venv/bin/activate

# 3. Check service status
docker compose ps
redis-cli ping
```

### Common Development Tasks
```bash
# Run tests
pytest tests/ -v

# Run specific test file
pytest tests/test_auth/test_oauth_manager.py -v

# Check code quality
black src tests
isort src tests
flake8 src tests
mypy src

# Database operations
alembic upgrade head      # Apply migrations
alembic revision --autogenerate -m "Description"  # Create migration

# View logs
tail -f logs/trading_*.log
```

## 📁 Project Structure Reference

```
Autotrading/
├── src/
│   ├── auth/           # OAuth2 & authentication
│   ├── broker/         # Schwab API integration
│   ├── data/           # Data fetching & storage
│   ├── strategy/       # Trading strategies
│   ├── trader/         # Order execution
│   ├── gui/            # PyQt6 interface
│   ├── config/         # Settings & constants
│   └── utils/          # Logging & helpers
├── tests/              # Test files
├── scripts/            # Utility scripts
├── alembic/            # Database migrations
└── logs/               # Application logs
```

## 🔑 Key Classes & Methods

### Authentication
```python
from src.auth.auth_service import AuthService

# Initialize
auth_service = AuthService()
await auth_service.initialize()

# Get client
client = auth_service.get_client()
```

### Schwab API Calls
```python
# Account info
client.get_account_numbers()
client.get_account(account_hash)

# Market data
client.get_quotes(['AAPL', 'GOOGL'])
client.get_price_history_every_minute('AAPL')
client.get_movers(index='$DJI', direction='up')

# Orders
client.place_order(account_hash, order_spec)
client.get_orders_for_account(account_hash)

# Streaming
stream_client = StreamClient(client)
await stream_client.login()
await stream_client.chart_equity_subs(['AAPL'])
```

## 🗄️ Database Models

```python
# Price data
PriceData(
    symbol='AAPL',
    timestamp=datetime.now(),
    open=150.0,
    high=151.0,
    low=149.0,
    close=150.5,
    volume=1000000
)

# Trade
Trade(
    symbol='AAPL',
    action='BUY',
    quantity=100,
    price=150.5,
    strategy_id=1,
    status='FILLED'
)

# Position
Position(
    symbol='AAPL',
    quantity=100,
    entry_price=150.5,
    current_price=151.0,
    unrealized_pnl=50.0
)
```

## ⚙️ Configuration (.env)

```bash
# Schwab API
SCHWAB_API_KEY=your_api_key
SCHWAB_APP_SECRET=your_app_secret
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182
SCHWAB_ACCOUNT_NUMBER=your_account_number

# Database
DATABASE_URL=postgresql://trading:trading123@localhost:5432/trading_db
REDIS_URL=redis://localhost:6379/0

# Trading
INITIAL_CAPITAL=10000
MAX_POSITION_SIZE=1000
MAX_DAILY_LOSS=200
RISK_PER_TRADE=0.01

# System
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
```

## 🚨 Important Reminders

### Security
- **NEVER** commit .env file
- **NEVER** log sensitive data (tokens, passwords)
- Use keyring for token storage
- Encrypt sensitive database fields

### Trading Safety
- Schwab has **NO paper trading** - all trades are real
- Start with minimal capital for testing
- Implement stop-loss on every trade
- Set daily loss limits
- Monitor all trades manually during development

### API Limits
- Schwab tokens expire in 7 days
- Rate limits apply (check documentation)
- Use caching to minimize API calls
- Implement exponential backoff

### Common Issues & Solutions

**OAuth Callback Issues**
```bash
# Generate SSL certificate for callback
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

**Database Connection Issues**
```bash
# Check PostgreSQL
docker exec trading-postgres psql -U trading -d trading_db -c "SELECT 1;"

# Reset database
alembic downgrade base
alembic upgrade head
```

**Import Issues**
```python
# Always use absolute imports
from src.auth.oauth_manager import OAuthManager  # ✓
from auth.oauth_manager import OAuthManager      # ✗
```

## 📊 Testing Strategy

### Unit Tests
- Mock all external API calls
- Test each component in isolation
- Aim for >90% coverage on critical paths

### Integration Tests
- Use test database
- Mock Schwab API responses
- Test full workflows

### Manual Testing Checklist
- [ ] Authentication flow works
- [ ] Can fetch account data
- [ ] Can get real-time quotes
- [ ] Can retrieve historical data
- [ ] Database operations work
- [ ] Error handling works
- [ ] Logging provides useful info

## 🎯 Current Phase Goals

### Phase 1: API Integration (Current)
- [x] Environment setup
- [x] Database schema
- [ ] OAuth2 authentication
- [ ] Historical data fetching
- [ ] WebSocket streaming
- [ ] Basic order placement

### Next Phases
- Phase 2: Trading engine core
- Phase 3: GUI development
- Phase 4: Backtesting
- Phase 5: Production readiness

## 📞 Help & Resources

### Documentation
- [schwab-py docs](https://github.com/alexgolec/schwab-py)
- [Schwab API docs](https://developer.schwab.com)
- [PyQt6 docs](https://doc.qt.io/qtforpython-6/)
- [SQLAlchemy docs](https://docs.sqlalchemy.org/)

### Debugging
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check current settings
from src.config.settings import get_settings
settings = get_settings()
print(settings.model_dump())

# Interactive debugging
import ipdb; ipdb.set_trace()
```

### Emergency Stops
```python
# Stop all trading
await trading_engine.emergency_stop()

# Close all positions
await trader.close_all_positions()

# Disable automated trading
settings.system.enable_real_trading = False
```

Remember: **Move Fast, Test Thoroughly, Trade Carefully!** 🚀
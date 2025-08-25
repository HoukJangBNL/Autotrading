# Schwab Automated Trading System

A comprehensive automated stock trading system using the Charles Schwab API with historical data collection, backtesting, and real-time trading capabilities.

## Current Status

- ✅ **Phase 1**: Backend Foundation (OAuth2, API Client, Database) - COMPLETED
- ✅ **Phase 2**: Data Mining Mode - COMPLETED (Aug 2025)
- 🚧 **Phase 3**: Real-time Streaming - In Progress
- 📅 **Phase 4**: Strategy Framework - Planned
- 📅 **Phase 5**: Trading Engine - Planned

## System Overview

This trading system operates in three distinct modes:

1. **Data Mining Mode**: Pre-market collection of historical 1-minute candle data ✅
2. **Backtesting Mode**: Strategy validation using historical data 🚧
3. **Trading Mode**: Real-time automated trading with risk management 📅

## Features

- **OAuth2 Authentication**: Secure token management with automatic refresh
- **Progressive Data Collection**: Start with core tickers, expand gradually to 500+ symbols
- **FastAPI Backend**: RESTful API with WebSocket support for real-time updates
- **Celery Task Queue**: Distributed processing for data mining and backtesting
- **Rate Limiting**: Intelligent API rate management with retry logic
- **TimescaleDB**: Optimized time-series data storage for millions of candles
- **Real-time Monitoring**: Health checks, progress tracking, and alerts
- **Risk Management**: Position limits, stop-loss, and circuit breakers

## Core Architecture

### Data Mining Strategy

The system uses a progressive approach to data collection:

1. **Phase 1 (Week 1-2)**: 30-50 core tickers (mega-caps, major ETFs)
2. **Phase 2 (Week 3-4)**: Expand to S&P 100 components (~100 tickers)
3. **Phase 3 (Month 2)**: Add NASDAQ 100 components (~200 tickers)
4. **Phase 4 (Month 3+)**: Dynamic expansion based on volume and volatility

Each ticker gets 2 months of 1-minute candle data, updated daily during pre-market hours.

## Requirements

- Python 3.10 or higher
- Charles Schwab developer account
- Schwab API credentials (API key and app secret)
- PostgreSQL with TimescaleDB extension
- Redis (for Celery message broker)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/schwab-api-client.git
cd schwab-api-client
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Initialize the database (if using PostgreSQL):
```bash
alembic upgrade head
```

## Configuration

### Schwab API Setup

1. Create an app at https://developer.schwab.com
2. Set callback URL to `https://127.0.0.1:8182`
3. Note your API key and app secret
4. Update `.env` with your credentials

### Environment Variables

```env
# Schwab API Credentials
SCHWAB_APP_KEY=your_app_key
SCHWAB_APP_SECRET=your_app_secret
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182

# Database (optional)
DATABASE_URL=postgresql://user:password@localhost/schwab_api

# Security
ENCRYPTION_KEY=your_encryption_key
```

## Quick Start

### 1. First-time Authentication

```bash
python scripts/auth_setup.py
```

### 2. Start the API Server

```bash
python scripts/run_server.py
```

### 3. Start Celery Worker

```bash
celery -A src.tasks.celery_app worker --loglevel=info
```

### 4. Access the System

- API Documentation: http://localhost:8000/api/docs
- Health Check: http://localhost:8000/health

## Data Mining Mode

The Data Mining Mode runs daily at 4:00 AM EST to collect historical data:

### Core Ticker List (Phase 1)
```json
{
    "core_tickers": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
        "SPY", "QQQ", "IWM", "DIA", "VTI", "ARKK", "XLF", "XLK"
    ]
}
```

### API Endpoints

- `GET /api/mining/status` - Current mining status
- `POST /api/mining/start` - Manually start mining
- `GET /api/mining/report/{date}` - Mining report for specific date

### Monitoring

The system provides real-time monitoring of:
- Active mining jobs
- Completion rates
- Failed tickers
- API rate limit usage

## Project Structure

```
autotrading/
├── src/
│   ├── api/            # FastAPI server and routers
│   ├── auth/           # OAuth2 authentication
│   ├── broker/         # Schwab API client
│   ├── data/           # Database models and mining logic
│   ├── services/       # Business logic services
│   ├── strategies/     # Trading strategy implementations
│   ├── tasks/          # Celery background tasks
│   └── utils/          # Utilities and logging
├── config/             # Configuration files
│   ├── core_tickers.json  # Core ticker list
│   └── schwab_token.json  # OAuth tokens (gitignored)
├── scripts/            # Utility scripts
├── tests/              # Test suite
└── docs/               # Documentation
```

## Development

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_auth/

# With coverage
pytest --cov=src --cov-report=html
```

### Code Style

We use Black for formatting and flake8 for linting:

```bash
black src tests
flake8 src tests
mypy src
```

## Performance Targets

- **Data Mining**: < 5 minutes per ticker
- **Success Rate**: > 95% completion rate
- **Data Coverage**: > 98% candle completeness
- **API Efficiency**: < 1% error rate
- **System Uptime**: > 99% availability

## Roadmap

### Phase 1 (Current) - Foundation
- ✅ OAuth2 authentication
- ✅ FastAPI server setup
- ✅ Celery task queue
- 🔄 Core ticker data mining

### Phase 2 - Expansion
- [ ] S&P 100 coverage
- [ ] Real-time monitoring dashboard
- [ ] Automated gap detection and filling
- [ ] Performance optimization

### Phase 3 - Trading
- [ ] Backtesting engine
- [ ] Strategy framework
- [ ] Risk management
- [ ] Live trading mode

## Security Notes

- Store API credentials in environment variables
- Never commit `.env` or credentials to version control
- Use encrypted token storage
- Implement rate limiting and circuit breakers
- Regular security audits

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

- Documentation: See `/docs` folder
- Issues: GitHub Issues
- Wiki: Implementation guides and strategies
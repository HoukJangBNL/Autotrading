# Schwab Automated Trading System

A comprehensive automated stock trading system using the Charles Schwab API with real-time streaming, multiple trading strategies, and risk management.

## Features

- **OAuth2 Authentication**: Secure token management with automatic refresh
- **Real-time Streaming**: WebSocket-based 1-minute OHLCV data streaming
- **Three Operational Modes**:
  - Discovery Mode: Pre-market stock scanning
  - Selection Mode: Strategy optimization and stock selection
  - Trading Mode: Real-time automated trading
- **Modular Strategy Framework**: Pluggable trading strategies
- **Risk Management**: Position limits, stop-loss, circuit breakers
- **Desktop GUI**: Real-time monitoring with PyQt6
- **Backtesting**: Historical data analysis and strategy validation
- **AI Optimization**: Bayesian optimization for strategy parameters

## Requirements

- Python 3.10 or higher
- Charles Schwab brokerage account
- Schwab API credentials (API key and app secret)
- PostgreSQL (for production) or SQLite (for development)
- Redis (for caching and pub/sub)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/schwab-autotrader.git
cd schwab-autotrader
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

5. Initialize the database:
```bash
alembic upgrade head
```

## Configuration

### Schwab API Setup

1. Create an app at https://developer.schwab.com
2. Set callback URL to `https://127.0.0.1:8182`
3. Note your API key and app secret
4. Update `.env` with your credentials

### First-time Authentication

Run the authentication CLI to obtain initial tokens:
```bash
python -m src.auth.cli
```

## Usage

### Running the Trading System

```bash
python -m src.main
```

### Running Individual Modes

```bash
# Discovery mode only
python -m src.main --mode discovery

# Selection mode only
python -m src.main --mode selection

# Trading mode only
python -m src.main --mode trading
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_broker.py
```

## Project Structure

```
autotrading/
├── src/
│   ├── auth/           # OAuth2 management
│   ├── broker/         # Schwab API integration
│   ├── data/           # Data fetching and storage
│   ├── strategy/       # Trading strategies
│   ├── trader/         # Trade execution engine
│   ├── utils/          # Shared utilities
│   ├── gui/            # Desktop GUI
│   └── config/         # Configuration management
├── tests/              # Test suite
├── docs/               # Documentation
├── scripts/            # Utility scripts
└── docker/             # Docker configuration
```

## Development

### Setting up Development Environment

```bash
pip install -r requirements-dev.txt
pre-commit install
```

### Code Style

We use Black for formatting and flake8 for linting:
```bash
black src tests
flake8 src tests
mypy src
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## Risk Warning

**IMPORTANT**: This software is for educational purposes. Trading stocks involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results. Always test thoroughly with paper trading before using real money.

## License

MIT License - see LICENSE file for details

## Support

- Documentation: https://schwab-autotrader.readthedocs.io
- Issues: https://github.com/yourusername/schwab-autotrader/issues
- Discord: https://discord.gg/yourdiscord
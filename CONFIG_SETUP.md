# Configuration Setup for Real Trading Mode

## 📋 Overview

The GUI supports two modes:
- **Mock Mode** (default): Simulated data for testing and development
- **Real Mode**: Live Schwab API integration with actual market data

## 🔧 Setting Up Real Mode

### 1. Environment Configuration

Create a `.env` file in the project root with your Schwab API credentials:

```bash
# Schwab API Configuration
SCHWAB_API_KEY=your_api_key_here
SCHWAB_APP_SECRET=your_app_secret_here
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182
SCHWAB_ACCOUNT_NUMBER=your_account_number

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost/trading
REDIS_URL=redis://localhost:6379/0

# Trading Configuration  
TRADING_INITIAL_CAPITAL=100000.0
TRADING_MAX_POSITION_SIZE=10000.0
```

### 2. Schwab API Setup

1. Register at https://developer.schwab.com
2. Create a new application
3. Set callback URL to `https://127.0.0.1:8182`
4. Note your API key and app secret
5. Add them to your `.env` file

### 3. Database Setup (Optional)

For full functionality, set up PostgreSQL and Redis:

```bash
# Install PostgreSQL and Redis
brew install postgresql redis

# Start services
brew services start postgresql
brew services start redis

# Create database
createdb trading
```

### 4. Authentication

First time setup requires authentication:

```bash
# Run authentication CLI
python -m src.auth.cli
```

This will:
- Open a browser for Schwab OAuth
- Save refresh tokens for future use
- Validate your account access

## 🎮 Using the GUI

### Switching Modes

1. **Start in Mock Mode** (default)
   - Checkbox unchecked: "Real Trading Mode"
   - Safe for testing and development

2. **Switch to Real Mode**
   - Check "Real Trading Mode" checkbox
   - Requires proper configuration
   - Connects to actual Schwab API

### Mode Indicators

- **Mock Mode**: 🟡 Mock Mode
- **Real Mode**: 🟢 Connected 
- **Error State**: ❌ Failed connection → Auto-fallback to Mock

### Discovery Mode Features

#### Mock Mode
- Simulated market data for popular stocks
- Random volume spikes and price movements
- Realistic but fake discovery alerts

#### Real Mode  
- Live Schwab streaming data
- Real volume and price analysis
- Actual market opportunity detection
- 15 popular stocks monitored: AAPL, GOOGL, MSFT, TSLA, etc.

### Discovery Criteria

Both modes use the same criteria:
- **Volume Spike**: 2x average volume threshold
- **Price Breakout**: 5% price change threshold  
- **Minimum Volume**: 100K shares filter

## 🔍 Troubleshooting

### Real Mode Connection Issues

1. **"Backend services not available"**
   - Normal when running standalone imports
   - GUI should still work in Mock mode

2. **Authentication errors**
   - Run `python -m src.auth.cli` again
   - Check API credentials in `.env`
   - Verify account permissions

3. **Database connection errors**
   - Real mode will work without database
   - Only affects data persistence
   - Check PostgreSQL/Redis if needed

### Performance Tips

1. **Mock Mode**: Instant startup, no external dependencies
2. **Real Mode**: 5-10 second connection time, requires internet
3. **Auto-Fallback**: Real mode errors → automatic Mock mode

## 🚀 Next Steps

1. **Test Mock Mode**: Verify Discovery alerts and market data
2. **Configure Real Mode**: Set up `.env` and authentication  
3. **Compare Results**: Switch between modes to see differences
4. **Extend Discovery**: Add custom criteria and more symbols

## 📊 Integration Architecture

```
GUI Layer (PySide6)
    ↓
GUIService (Mock/Real Mode)
    ↓
Backend Services:
├── AuthService (OAuth tokens)
├── StreamingService (WebSocket)
└── StreamProcessor (Real-time analysis)
    ↓
Schwab API (Live market data)
```

The integration provides:
- Seamless mode switching
- Automatic error recovery
- Real-time data processing
- Discovery alert generation
- Full GUI compatibility
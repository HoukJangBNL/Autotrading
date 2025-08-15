"""System-wide constants."""

from enum import Enum, auto


class TradingMode(str, Enum):
    """Trading operation modes."""
    DISCOVERY = "discovery"
    SELECTION = "selection"
    TRADING = "trading"


class OrderAction(str, Enum):
    """Order actions."""
    BUY = "BUY"
    SELL = "SELL"
    BUY_TO_COVER = "BUY_TO_COVER"
    SELL_SHORT = "SELL_SHORT"


class OrderType(str, Enum):
    """Order types."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PositionStatus(str, Enum):
    """Position status."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PARTIAL = "PARTIAL"


class TimeInForce(str, Enum):
    """Order time in force."""
    DAY = "DAY"
    GTC = "GTC"  # Good Till Cancelled
    GTD = "GTD"  # Good Till Date
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill


class MarketSession(str, Enum):
    """Market sessions."""
    PRE_MARKET = "PRE_MARKET"
    REGULAR = "REGULAR"
    POST_MARKET = "POST_MARKET"
    SEAMLESS = "SEAMLESS"


class AssetType(str, Enum):
    """Asset types."""
    EQUITY = "EQUITY"
    OPTION = "OPTION"
    MUTUAL_FUND = "MUTUAL_FUND"
    FIXED_INCOME = "FIXED_INCOME"
    INDEX = "INDEX"


# Time constants
MARKET_OPEN_TIME = "09:30:00"
MARKET_CLOSE_TIME = "16:00:00"
PRE_MARKET_OPEN = "04:00:00"
POST_MARKET_CLOSE = "20:00:00"

# Trading hours (Eastern Time)
REGULAR_HOURS = {
    "start": "09:30",
    "end": "16:00"
}

PRE_MARKET_HOURS = {
    "start": "04:00",
    "end": "09:30"
}

POST_MARKET_HOURS = {
    "start": "16:00",
    "end": "20:00"
}

# API Rate limits
SCHWAB_API_RATE_LIMIT = 120  # requests per minute
STREAM_RECONNECT_DELAY = 5  # seconds
MAX_RECONNECT_ATTEMPTS = 5

# Data constants
OHLCV_FIELDS = ["open", "high", "low", "close", "volume"]
CANDLE_INTERVAL = 60  # seconds (1 minute)

# Risk management constants
DEFAULT_STOP_LOSS = 0.02  # 2%
DEFAULT_TAKE_PROFIT = 0.05  # 5%
DEFAULT_POSITION_SIZE = 0.1  # 10% of capital
MAX_CORRELATION = 0.7  # Maximum allowed correlation between positions

# Performance thresholds
MIN_SHARPE_RATIO = 1.0
MIN_WIN_RATE = 0.5
MAX_DRAWDOWN = 0.15  # 15%

# Database
BATCH_INSERT_SIZE = 1000
DATA_RETENTION_DAYS = 365

# GUI Update intervals (milliseconds)
PRICE_UPDATE_INTERVAL = 1000
CHART_UPDATE_INTERVAL = 5000
POSITION_UPDATE_INTERVAL = 2000

# Logging
LOG_ROTATION_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5
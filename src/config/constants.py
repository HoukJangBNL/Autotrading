"""System-wide constants and enums for config and API."""

from enum import Enum

# API Rate limits
SCHWAB_API_RATE_LIMIT = 120  # requests per minute
STREAM_RECONNECT_DELAY = 5  # seconds
MAX_RECONNECT_ATTEMPTS = 5

# Auth constants
TOKEN_REFRESH_BUFFER = 300  # 5 minutes before expiration
OAUTH_TIMEOUT = 30  # seconds

# Logging
LOG_ROTATION_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5


# ===== Enums expected by tests and API contracts =====
class TradingMode(str, Enum):
    """System trading modes."""
    DISCOVERY = "discovery"
    SELECTION = "selection"
    TRADING = "trading"


class OrderAction(str, Enum):
    """Order actions/instructions."""
    BUY = "BUY"
    SELL = "SELL"
    BUY_TO_COVER = "BUY_TO_COVER"
    SELL_SHORT = "SELL_SHORT"


class OrderStatus(str, Enum):
    """Simplified order status for high-level flows."""
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderType(str, Enum):
    """Common order types."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class TimeInForce(str, Enum):
    """Time-in-force policies."""
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class AssetType(str, Enum):
    """Supported asset classes for requests."""
    EQUITY = "EQUITY"
    OPTION = "OPTION"
    INDEX = "INDEX"
    ETF = "ETF"
    MUTUAL_FUND = "MUTUAL_FUND"
    CASH_EQUIVALENT = "CASH_EQUIVALENT"


class MarketSession(str, Enum):
    """Market sessions for trading hours."""
    PRE_MARKET = "PRE_MARKET"
    NORMAL = "NORMAL"
    AFTER_MARKET = "AFTER_MARKET"


class PositionStatus(str, Enum):
    """Position lifecycle states."""
    OPEN = "OPEN"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    CLOSED = "CLOSED"
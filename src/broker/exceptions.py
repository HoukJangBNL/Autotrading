"""Broker-specific exception classes."""


class BrokerError(Exception):
    """Base exception for all broker-related errors."""
    pass


class BrokerConnectionError(BrokerError):
    """Raised when connection to broker fails."""
    pass


class RateLimitError(BrokerError):
    """Raised when API rate limit is exceeded."""
    pass


class InvalidOrderError(BrokerError):
    """Raised when order validation fails."""
    pass


class InsufficientFundsError(BrokerError):
    """Raised when account has insufficient funds for order."""
    pass


class PositionNotFoundError(BrokerError):
    """Raised when requested position is not found."""
    pass


class OrderNotFoundError(BrokerError):
    """Raised when requested order is not found."""
    pass


class MarketDataError(BrokerError):
    """Raised when market data request fails."""
    pass


class InvalidSymbolError(MarketDataError):
    """Raised when an invalid symbol is provided."""
    pass


class DataUnavailableError(MarketDataError):
    """Raised when requested data is not available."""
    pass


class StreamingError(BrokerError):
    """Base exception for streaming-related errors."""
    pass


class StreamConnectionError(StreamingError):
    """Raised when streaming connection fails."""
    pass


class StreamSubscriptionError(StreamingError):
    """Raised when stream subscription fails."""
    pass
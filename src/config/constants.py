"""System-wide constants for auth and API."""

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
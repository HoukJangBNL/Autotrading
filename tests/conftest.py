"""Pytest configuration and fixtures."""

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.database import DatabaseService
from src.data.models import Base
from src.utils.logger import setup_logging


# Configure logging for tests
setup_logging()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_database_url():
    """Get test database URL based on environment."""
    # Check if we should use PostgreSQL (for integration tests)
    if os.getenv("TEST_USE_POSTGRES", "false").lower() == "true":
        return "postgresql://test:test@localhost:5433/test_autotrading"
    # Default to SQLite for unit tests (in-memory)
    return "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine(test_database_url):
    """Create a test database engine."""
    engine = create_engine(test_database_url)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a test database session."""
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_engine
    )
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def db_service(test_database_url):
    """Create a test database service."""
    service = DatabaseService()
    service.initialize(test_database_url)
    service.create_tables()
    yield service
    service.drop_tables()
    service.close()


@pytest.fixture
def mock_schwab_client():
    """Mock Schwab API client."""
    from unittest.mock import Mock
    
    client = Mock()
    client.get_quote.return_value = Mock(
        status_code=200,
        json=lambda: {"AAPL": {"lastPrice": 150.00}}
    )
    client.get_account_numbers.return_value = Mock(
        status_code=200,
        json=lambda: [{"accountNumber": "123456789", "hashValue": "ABC123XYZ"}]
    )
    return client


@pytest.fixture
def sample_candle():
    """Sample OHLCV candle data."""
    return {
        "symbol": "AAPL",
        "timestamp": "2024-01-15T09:30:00Z",
        "open": 149.50,
        "high": 151.00,
        "low": 149.00,
        "close": 150.50,
        "volume": 1000000
    }


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    # Reset auth service singleton
    import src.auth.auth_service
    src.auth.auth_service._auth_instance = None
    
    # Reset historical fetcher singleton
    import src.data.historical_data
    src.data.historical_data._fetcher_instance = None
    
    # Reset SchwabBroker singleton
    from src.broker import SchwabBroker
    SchwabBroker.reset_instance()
    
    yield
    
    # Cleanup after test
    src.auth.auth_service._auth_instance = None
    src.data.historical_data._fetcher_instance = None
    SchwabBroker.reset_instance()


@pytest.fixture
def sample_order():
    """Sample order data."""
    return {
        "symbol": "AAPL",
        "action": "BUY",
        "orderType": "LIMIT",
        "quantity": 100,
        "price": 150.00,
        "timeInForce": "DAY"
    }


# Temporary directory fixtures
@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_log_dir(temp_dir):
    """Create temporary log directory."""
    log_dir = temp_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir


# Enhanced mock fixtures
@pytest.fixture
def mock_auth_service():
    """Create standard mock auth service."""
    auth = AsyncMock()
    auth.initialize = AsyncMock()
    auth.ensure_authenticated = AsyncMock()
    auth.get_client = Mock()
    auth.is_initialized = Mock(return_value=True)
    auth.has_valid_client = Mock(return_value=True)
    return auth


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    redis.publish = AsyncMock(return_value=1)
    redis.subscribe = AsyncMock()
    redis.unsubscribe = AsyncMock()
    redis.close = AsyncMock()
    return redis


# Docker services for integration tests
@pytest.fixture(scope="session")
def docker_services():
    """Ensure docker services are running for integration tests."""
    if os.getenv("TEST_USE_POSTGRES", "false").lower() == "true":
        # Check if PostgreSQL is already running
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                port=5433,
                database="test_autotrading",
                user="test",
                password="test"
            )
            conn.close()
            yield  # Already running
            return
        except:
            pass
        
        # Start PostgreSQL container
        os.system("docker-compose -f docker-compose.test.yml up -d test-db")
        time.sleep(5)  # Wait for PostgreSQL to start
        
        yield
        
        # Stop container if we started it
        if os.getenv("TEST_KEEP_DOCKER", "false").lower() != "true":
            os.system("docker-compose -f docker-compose.test.yml down")
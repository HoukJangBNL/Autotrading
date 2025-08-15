"""Pytest configuration and fixtures."""

import asyncio
import os
import sys
from pathlib import Path

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
    """Get test database URL."""
    return os.environ.get(
        "TEST_DATABASE_URL",
        "sqlite:///test_trading.db"
    )


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
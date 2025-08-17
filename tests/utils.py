"""Test utilities and helpers for consistent testing."""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Callable
from unittest.mock import Mock

import pytest


class AsyncContextManagerMock:
    """Mock for async context managers."""
    
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.enter_called = False
        self.exit_called = False
        self.exception = None
    
    async def __aenter__(self):
        self.enter_called = True
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exit_called = True
        self.exception = exc_val
        return False


def async_return(value: Any):
    """Create an async function that returns a value."""
    async def _return():
        return value
    return _return()


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 1.0,
    interval: float = 0.01
) -> bool:
    """Wait for a condition to become true."""
    start = time.time()
    while time.time() - start < timeout:
        if condition():
            return True
        await asyncio.sleep(interval)
    return False


def assert_called_with_retry(
    mock: Mock,
    *args,
    timeout: float = 1.0,
    **kwargs
):
    """Assert mock was called with args, with retry."""
    async def check():
        return await wait_for_condition(
            lambda: mock.called and mock.call_args == ((args), kwargs),
            timeout=timeout
        )
    
    loop = asyncio.get_event_loop()
    assert loop.run_until_complete(check()), \
        f"Mock not called with expected args within {timeout}s"


class TimeAdvancer:
    """Helper to advance time in tests."""
    
    def __init__(self):
        self.current_time = datetime.now(timezone.utc)
        self.original_datetime = datetime
    
    def __enter__(self):
        """Replace datetime.now with mock."""
        mock_datetime = Mock(wraps=datetime)
        mock_datetime.now = Mock(return_value=self.current_time)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore original datetime."""
        pass
    
    def advance(self, seconds: float):
        """Advance time by specified seconds."""
        self.current_time += timedelta(seconds=seconds)


def create_test_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create test configuration with defaults."""
    config = {
        "broker": {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "account_number": "12345678"
        },
        "redis": {
            "url": "redis://localhost:6380",
            "enabled": False  # Disabled by default for tests
        },
        "database": {
            "url": "sqlite:///:memory:",
            "echo": False
        },
        "system": {
            "batch_insert_size": 100,
            "max_workers": 2,
            "rate_limit": 120
        },
        "logging": {
            "level": "INFO",
            "log_dir": "/tmp/test_logs"
        }
    }
    
    if overrides:
        deep_update(config, overrides)
    
    return config


def deep_update(base: Dict, update: Dict) -> Dict:
    """Deep update dictionary."""
    for key, value in update.items():
        if isinstance(value, dict) and key in base:
            base[key] = deep_update(base[key], value)
        else:
            base[key] = value
    return base


async def create_test_websocket_server(
    handler: Callable,
    host: str = "localhost",
    port: int = 8765
):
    """Create test WebSocket server."""
    import websockets
    
    async with websockets.serve(handler, host, port):
        yield f"ws://{host}:{port}"


class MockWebSocketServer:
    """Mock WebSocket server for testing."""
    
    def __init__(self, responses: Optional[List[str]] = None):
        self.responses = responses or []
        self.received_messages = []
        self.connected = False
        self.current_response = 0
    
    async def handler(self, websocket, path):
        """WebSocket handler."""
        self.connected = True
        
        try:
            async for message in websocket:
                self.received_messages.append(message)
                
                # Send next response if available
                if self.current_response < len(self.responses):
                    await websocket.send(self.responses[self.current_response])
                    self.current_response += 1
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            self.connected = False


def compare_floats(a: float, b: float, tolerance: float = 0.0001) -> bool:
    """Compare floats with tolerance."""
    return abs(a - b) < tolerance


def assert_recent_timestamp(
    timestamp: datetime,
    max_age_seconds: float = 1.0
):
    """Assert timestamp is recent."""
    age = (datetime.now(timezone.utc) - timestamp).total_seconds()
    assert age <= max_age_seconds, \
        f"Timestamp {timestamp} is {age}s old, max allowed is {max_age_seconds}s"


class PerformanceTimer:
    """Context manager for timing operations."""
    
    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.duration = self.end_time - self.start_time
        print(f"{self.name} took {self.duration:.4f} seconds")
    
    def assert_faster_than(self, max_seconds: float):
        """Assert operation completed within time limit."""
        assert self.duration is not None, "Timer not used in context"
        assert self.duration < max_seconds, \
            f"{self.name} took {self.duration:.4f}s, max allowed is {max_seconds}s"


def create_async_generator(items: List[Any]):
    """Create async generator from list."""
    async def gen():
        for item in items:
            yield item
    return gen()


async def exhaust_async_generator(gen):
    """Exhaust async generator and return list."""
    items = []
    async for item in gen:
        items.append(item)
    return items


# Test decorators
def async_timeout(seconds: float):
    """Decorator to add timeout to async tests."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
        return wrapper
    return decorator


def retry_async(retries: int = 3, delay: float = 0.1):
    """Decorator to retry async tests."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_error = None
            for i in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if i < retries - 1:
                        await asyncio.sleep(delay)
            raise last_error
        return wrapper
    return decorator


# Pytest fixtures using utilities
@pytest.fixture
def time_advancer():
    """Provide time advancer for tests."""
    with TimeAdvancer() as advancer:
        yield advancer


@pytest.fixture
def performance_timer():
    """Provide performance timer for tests."""
    return PerformanceTimer


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return create_test_config()
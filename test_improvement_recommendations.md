# Test Suite Improvement Recommendations

## Priority 0 - Critical Fixes (Block Testing)

### 1. Fix SchwabBroker Singleton for Testing

**Issue**: The `__new__` method doesn't accept constructor arguments
```python
# Current problematic code in schwab_client.py
def __new__(cls) -> 'SchwabBroker':
    """Ensure singleton instance."""
    if not cls._instance:
        cls._instance = super().__new__(cls)
    return cls._instance
```

**Solution**: Add testing support to singleton pattern
```python
# Recommended fix in schwab_client.py
def __new__(cls, *args, **kwargs) -> 'SchwabBroker':
    """Ensure singleton instance with test support."""
    # Allow reset for testing
    if kwargs.get('_test_mode', False):
        cls._instance = None
        cls._initialized = False
    
    if not cls._instance:
        cls._instance = super().__new__(cls)
    return cls._instance

# Add class method for test cleanup
@classmethod
def reset_instance(cls):
    """Reset singleton for testing."""
    cls._instance = None
    cls._initialized = False
```

**Test fixture update**:
```python
@pytest.fixture
async def schwab_broker(mock_auth_service, mock_client):
    """Create SchwabBroker instance with mocks."""
    # Reset singleton before each test
    SchwabBroker.reset_instance()
    
    mock_auth_service.get_authenticated_client.return_value = mock_client
    
    # Create instance with test mode
    broker = SchwabBroker(
        auth_service=mock_auth_service,
        _test_mode=True
    )
    
    # Rest of fixture...
```

### 2. Database Test Infrastructure

**Issue**: Tests failing due to missing database connection
```
sqlalchemy.exc.OperationalError: connection to server on socket "/tmp/.s.PGSQL.5432" failed
```

**Solution A**: Use SQLite for tests
```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.data.models import Base

@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine

@pytest.fixture
def test_db_session(test_db_engine):
    """Create test database session."""
    Session = sessionmaker(bind=test_db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()
```

**Solution B**: Docker-based PostgreSQL
```yaml
# docker-compose.test.yml
version: '3.8'
services:
  test-db:
    image: postgres:15
    environment:
      POSTGRES_DB: test_autotrading
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports:
      - "5433:5432"
    tmpfs:
      - /var/lib/postgresql/data
```

```python
# tests/conftest.py
@pytest.fixture(scope="session")
def docker_services():
    """Ensure docker services are running."""
    os.system("docker-compose -f docker-compose.test.yml up -d")
    time.sleep(2)  # Wait for db to start
    yield
    os.system("docker-compose -f docker-compose.test.yml down")
```

### 3. Fix Logger Test Permissions

**Issue**: Tests trying to write to protected directories
```python
PermissionError: [Errno 1] Operation not permitted: '/var'
```

**Solution**: Use temporary directories
```python
# tests/test_logger.py
import tempfile
from pathlib import Path

@pytest.fixture
def temp_log_dir():
    """Create temporary log directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

def test_setup_logging_custom_config(temp_log_dir):
    """Test custom logging configuration."""
    config = LogConfig(
        log_dir=str(temp_log_dir),
        log_file="test.log",
        level="DEBUG"
    )
    setup_logging(config)
    # Test assertions...
```

## Priority 1 - Test Reliability

### 1. Async Test Configuration

**Issue**: pytest-asyncio deprecation warning
```
The configuration option "asyncio_default_fixture_loop_scope" is unset
```

**Solution**: Update pyproject.toml
```toml
[tool.pytest.ini_options]
asyncio_default_fixture_loop_scope = "function"
```

### 2. WebSocket Deprecation

**Issue**: Using deprecated websocket imports
```python
DeprecationWarning: websockets.client.WebSocketClientProtocol is deprecated
```

**Solution**: Update imports
```python
# Old
from websockets.client import WebSocketClientProtocol

# New
from websockets import WebSocketClientProtocol
```

### 3. Mock Consistency

**Issue**: Inconsistent mocking patterns causing failures

**Solution**: Create standard mock factories
```python
# tests/mocks.py
from unittest.mock import Mock, AsyncMock

def create_mock_auth_service():
    """Create standard mock auth service."""
    auth = AsyncMock()
    auth.initialize = AsyncMock()
    auth.ensure_authenticated = AsyncMock()
    auth.get_client = Mock()
    return auth

def create_mock_schwab_client():
    """Create standard mock Schwab client."""
    client = AsyncMock()
    
    # Standard response
    response = Mock()
    response.status_code = 200
    response.json.return_value = {}
    response.headers = {}
    
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    # ... other methods
    
    return client
```

## Priority 2 - Test Organization

### 1. Test Markers

**Add more granular test markers**:
```toml
[tool.pytest.ini_options]
markers = [
    "unit: marks unit tests",
    "integration: marks integration tests",
    "db: marks tests requiring database",
    "websocket: marks websocket tests",
    "slow: marks slow tests",
    "performance: marks performance tests",
]
```

### 2. Test Structure

**Organize tests by type**:
```
tests/
├── unit/           # Pure unit tests (no external deps)
├── integration/    # Integration tests (db, redis, etc)
├── e2e/           # End-to-end tests
├── performance/   # Performance tests
├── fixtures/      # Shared fixtures
└── mocks/         # Shared mocks
```

### 3. Fixture Scoping

**Optimize fixture performance**:
```python
# Expensive fixtures at session scope
@pytest.fixture(scope="session")
async def auth_service():
    """Share auth service across tests."""
    service = await create_test_auth_service()
    yield service
    await service.cleanup()

# Cheap fixtures at function scope
@pytest.fixture
def mock_response():
    """Create fresh mock for each test."""
    return create_mock_response()
```

## Test Execution Strategy

### 1. Staged Testing
```bash
# Stage 1: Fast unit tests
pytest tests/unit -v

# Stage 2: Integration tests
pytest tests/integration -v -m "not slow"

# Stage 3: Full suite
pytest tests/ -v

# Stage 4: Performance tests
pytest tests/performance -v
```

### 2. Parallel Execution
```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel
pytest -n auto tests/unit
```

### 3. Coverage Goals
- Unit tests: 90%+ coverage
- Integration tests: 80%+ coverage
- E2E tests: Critical paths only
- Overall: 85%+ coverage

## Immediate Action Items

1. **Fix SchwabBroker singleton** (2 hours)
   - Update `__new__` method
   - Add reset_instance method
   - Update all broker tests

2. **Setup test database** (1 hour)
   - Add SQLite option for unit tests
   - Docker setup for integration tests
   - Update conftest.py

3. **Fix logger tests** (30 minutes)
   - Use temp directories
   - Mock file operations

4. **Update async configuration** (15 minutes)
   - Update pyproject.toml
   - Fix deprecation warnings

5. **Create test utilities** (1 hour)
   - Standard mock factories
   - Common fixtures
   - Test helpers

Total estimated time: ~5 hours to fix critical test infrastructure
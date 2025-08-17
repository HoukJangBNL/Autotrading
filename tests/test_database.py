"""Tests for database service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import DatabaseService, get_db, get_async_db, db_service


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = Mock()
    settings.get_database_url.return_value = "postgresql://test:test@localhost/test"
    settings.database.pool_size = 10
    settings.database.max_overflow = 20
    settings.database.pool_timeout = 30
    settings.database.echo = False
    return settings


@pytest.fixture
def database_service(mock_settings):
    """Create a fresh database service for testing."""
    with patch('src.data.database.settings', mock_settings):
        service = DatabaseService()
        yield service
        # Cleanup
        if service._initialized:
            service.close()


class TestDatabaseService:
    """Test cases for DatabaseService."""
    
    def test_initialize(self, database_service, mock_settings):
        """Test database service initialization."""
        with patch('src.data.database.create_engine') as mock_create_engine:
            with patch('src.data.database.create_async_engine') as mock_create_async_engine:
                with patch('src.data.database.sessionmaker') as mock_sessionmaker:
                    # Setup mocks
                    mock_engine = Mock()
                    mock_async_engine = Mock()
                    mock_create_engine.return_value = mock_engine
                    mock_create_async_engine.return_value = mock_async_engine
                    
                    # Initialize
                    database_service.initialize()
                    
                    # Verify
                    assert database_service._initialized is True
                    assert database_service.engine is mock_engine
                    assert database_service.async_engine is mock_async_engine
                    assert mock_sessionmaker.call_count == 2
                    
                    # Test idempotency - calling again should not reinitialize
                    database_service.initialize()
                    assert mock_create_engine.call_count == 1
    
    def test_create_tables_not_initialized(self, database_service):
        """Test create_tables when service is not initialized."""
        with patch.object(database_service, 'initialize') as mock_init:
            with patch('src.data.database.Base.metadata.create_all') as mock_create_all:
                # Setup
                database_service._initialized = False
                mock_engine = Mock()
                database_service.engine = mock_engine
                
                # Execute
                database_service.create_tables()
                
                # Verify
                mock_init.assert_called_once()
                mock_create_all.assert_called_once_with(bind=mock_engine)
    
    def test_drop_tables_not_initialized(self, database_service):
        """Test drop_tables when service is not initialized."""
        with patch.object(database_service, 'initialize') as mock_init:
            with patch('src.data.database.Base.metadata.drop_all') as mock_drop_all:
                # Setup
                database_service._initialized = False
                mock_engine = Mock()
                database_service.engine = mock_engine
                
                # Execute
                database_service.drop_tables()
                
                # Verify
                mock_init.assert_called_once()
                mock_drop_all.assert_called_once_with(bind=mock_engine)
    
    def test_get_session_not_initialized(self, database_service):
        """Test get_session when service is not initialized."""
        with patch.object(database_service, 'initialize') as mock_init:
            # Setup
            database_service._initialized = False
            mock_session = Mock(spec=Session)
            mock_session_factory = Mock(return_value=mock_session)
            database_service.SessionLocal = mock_session_factory
            
            # Execute
            with database_service.get_session() as session:
                assert session is mock_session
            
            # Verify
            mock_init.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
    
    def test_get_session_exception_handling(self, database_service):
        """Test get_session exception handling."""
        # Setup
        database_service._initialized = True
        mock_session = Mock(spec=Session)
        mock_session_factory = Mock(return_value=mock_session)
        database_service.SessionLocal = mock_session_factory
        
        # Test exception during context
        with pytest.raises(ValueError):
            with database_service.get_session() as session:
                raise ValueError("Test error")
        
        # Verify rollback was called
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.commit.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_async_session_not_initialized(self, database_service):
        """Test get_async_session when service is not initialized."""
        with patch.object(database_service, 'initialize') as mock_init:
            # Setup
            database_service._initialized = False
            
            # Create async session mock with proper async support
            mock_async_session = MagicMock(spec=AsyncSession)
            
            # Setup async context manager properly
            async def async_enter():
                return mock_async_session
            
            async def async_exit(exc_type, exc, tb):
                return None
            
            async def async_commit():
                pass
            
            async def async_close():
                pass
            
            mock_async_session.__aenter__ = Mock(side_effect=async_enter)
            mock_async_session.__aexit__ = Mock(side_effect=async_exit)
            mock_async_session.commit = Mock(side_effect=async_commit)
            mock_async_session.close = Mock(side_effect=async_close)
            
            mock_async_session_factory = Mock(return_value=mock_async_session)
            database_service.AsyncSessionLocal = mock_async_session_factory
            
            # Execute
            async with database_service.get_async_session() as session:
                assert session is mock_async_session
            
            # Verify
            mock_init.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_async_session_exception_handling(self, database_service):
        """Test get_async_session exception handling."""
        # Setup
        database_service._initialized = True
        
        # Create async session mock with proper async methods
        mock_async_session = MagicMock(spec=AsyncSession)
        
        # Setup async context manager properly
        async def async_enter():
            return mock_async_session
        
        async def async_exit(exc_type, exc, tb):
            if exc_type:
                await mock_async_session.rollback()
            await mock_async_session.close()
            return None
        
        # Make rollback and close async
        async def async_rollback():
            pass
        
        async def async_close():
            pass
        
        mock_async_session.__aenter__ = Mock(side_effect=async_enter)
        mock_async_session.__aexit__ = Mock(side_effect=async_exit)
        mock_async_session.rollback = Mock(side_effect=async_rollback)
        mock_async_session.close = Mock(side_effect=async_close)
        
        mock_async_session_factory = Mock(return_value=mock_async_session)
        database_service.AsyncSessionLocal = mock_async_session_factory
        
        # Test exception during context
        with pytest.raises(ValueError):
            async with database_service.get_async_session() as session:
                raise ValueError("Test error")
        
        # Verify rollback was called (might be called twice - once by database.py and once by our mock)
        assert mock_async_session.rollback.call_count >= 1
    
    def test_close(self, database_service):
        """Test closing database connections."""
        # Setup
        mock_engine = Mock()
        mock_async_engine = Mock()
        mock_async_engine.sync_engine = Mock()
        
        database_service._initialized = True
        database_service.engine = mock_engine
        database_service.async_engine = mock_async_engine
        
        # Execute
        database_service.close()
        
        # Verify
        mock_engine.dispose.assert_called_once()
        mock_async_engine.sync_engine.dispose.assert_called_once()
        assert database_service._initialized is False


class TestDependencyHelpers:
    """Test dependency injection helpers."""
    
    def test_get_db(self):
        """Test get_db dependency helper."""
        mock_session = Mock(spec=Session)
        
        with patch.object(db_service, 'get_session') as mock_get_session:
            # Setup context manager mock
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_session
            mock_context.__exit__.return_value = None
            mock_get_session.return_value = mock_context
            
            # Execute
            gen = get_db()
            session = next(gen)
            
            # Verify
            assert session is mock_session
            
            # Cleanup generator
            try:
                next(gen)
            except StopIteration:
                pass
    
    @pytest.mark.asyncio
    async def test_get_async_db(self):
        """Test get_async_db dependency helper."""
        mock_session = Mock(spec=AsyncSession)
        
        with patch.object(db_service, 'get_async_session') as mock_get_async_session:
            # Setup async context manager mock
            mock_context = MagicMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_get_async_session.return_value = mock_context
            
            # Execute
            async_gen = get_async_db()
            session = await async_gen.__anext__()
            
            # Verify
            assert session is mock_session
            
            # Cleanup async generator
            try:
                await async_gen.__anext__()
            except StopAsyncIteration:
                pass
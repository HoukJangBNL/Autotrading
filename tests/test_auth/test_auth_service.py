"""Tests for authentication service."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
from datetime import datetime, timedelta

from src.auth.auth_service import AuthService, get_auth_service, get_authenticated_client
from src.auth.exceptions import ClientInitializationError


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = Mock()
    settings.schwab.api_key = "test_api_key"
    settings.schwab.app_secret = "test_app_secret"
    settings.schwab.callback_url = "https://127.0.0.1:8182"
    return settings


@pytest.fixture
def mock_oauth_manager():
    """Mock OAuth manager for testing."""
    manager = AsyncMock()
    manager.authenticate = AsyncMock()
    manager.refresh_token = AsyncMock()
    manager.get_client = Mock()
    manager.close = AsyncMock()
    return manager


@pytest.fixture
def mock_client():
    """Mock Schwab client for testing."""
    client = AsyncMock()
    response = Mock()
    response.json.return_value = [{'accountNumber': '12345678', 'hashValue': 'abc123'}]
    response.raise_for_status = Mock()
    client.get_account_numbers.return_value = response
    return client


@pytest.fixture
async def auth_service(mock_settings, mock_oauth_manager):
    """Auth service instance for testing."""
    with patch('src.auth.auth_service.get_settings', return_value=mock_settings):
        with patch('src.auth.auth_service.OAuthManager', return_value=mock_oauth_manager):
            service = AuthService()
            yield service
            # Cleanup
            if service._refresh_task and not service._refresh_task.done():
                service._refresh_task.cancel()
                try:
                    await service._refresh_task
                except asyncio.CancelledError:
                    pass


class TestAuthService:
    """Test cases for AuthService."""
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, auth_service, mock_oauth_manager, mock_client):
        """Test successful initialization."""
        # Setup
        mock_oauth_manager.authenticate.return_value = mock_client
        
        # Execute
        await auth_service.initialize()
        
        # Verify
        assert auth_service._initialized is True
        assert auth_service.client == mock_client
        mock_oauth_manager.authenticate.assert_called_once()
        assert auth_service._refresh_task is not None
        assert not auth_service._refresh_task.done()
        
    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, auth_service, mock_oauth_manager, mock_client):
        """Test initialization when already initialized."""
        # Setup
        auth_service._initialized = True
        
        # Execute
        await auth_service.initialize()
        
        # Verify - should not reinitialize
        mock_oauth_manager.authenticate.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_initialize_failure(self, auth_service, mock_oauth_manager):
        """Test initialization failure."""
        # Setup
        mock_oauth_manager.authenticate.side_effect = Exception("Auth failed")
        
        # Execute & Verify
        with pytest.raises(RuntimeError, match="Authentication initialization failed"):
            await auth_service.initialize()
            
        assert auth_service._initialized is False
        
    @pytest.mark.asyncio
    async def test_token_refresh_loop(self, auth_service, mock_oauth_manager, mock_client):
        """Test token refresh loop behavior."""
        # Setup
        refresh_count = 0
        
        async def mock_refresh():
            nonlocal refresh_count
            refresh_count += 1
            if refresh_count > 1:
                raise asyncio.CancelledError()
                
        mock_oauth_manager.refresh_token.side_effect = mock_refresh
        mock_oauth_manager.get_client.return_value = mock_client
        
        # Execute
        task = asyncio.create_task(auth_service._token_refresh_loop())
        
        # Let it run briefly
        await asyncio.sleep(0.1)
        
        # Cancel and wait
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
            
        # Since we're testing with a short sleep, refresh shouldn't have been called
        assert refresh_count == 0
        
    @pytest.mark.asyncio
    async def test_shutdown(self, auth_service, mock_oauth_manager, mock_client):
        """Test shutdown process."""
        # Setup - initialize first
        mock_oauth_manager.authenticate.return_value = mock_client
        await auth_service.initialize()
        
        # Execute
        await auth_service.shutdown()
        
        # Verify
        assert auth_service._initialized is False
        assert auth_service.client is None
        mock_oauth_manager.close.assert_called_once()
        assert auth_service._refresh_task.done()
        
    def test_get_client_success(self, auth_service, mock_client):
        """Test getting client when initialized."""
        # Setup
        auth_service._initialized = True
        auth_service.client = mock_client
        
        # Execute
        client = auth_service.get_client()
        
        # Verify
        assert client == mock_client
        
    def test_get_client_not_initialized(self, auth_service):
        """Test getting client when not initialized."""
        with pytest.raises(RuntimeError, match="Authentication service not initialized"):
            auth_service.get_client()
            
    def test_get_client_no_client(self, auth_service):
        """Test getting client when no client available."""
        auth_service._initialized = True
        auth_service.client = None
        
        with pytest.raises(RuntimeError, match="No authenticated client available"):
            auth_service.get_client()
            
    @pytest.mark.asyncio
    async def test_ensure_authenticated_not_initialized(self, auth_service, mock_oauth_manager, mock_client):
        """Test ensure_authenticated initializes if needed."""
        # Setup
        mock_oauth_manager.authenticate.return_value = mock_client
        
        # Execute
        client = await auth_service.ensure_authenticated()
        
        # Verify
        assert client == mock_client
        assert auth_service._initialized is True
        
    @pytest.mark.asyncio
    async def test_ensure_authenticated_valid_client(self, auth_service, mock_client):
        """Test ensure_authenticated with valid client."""
        # Setup
        auth_service._initialized = True
        auth_service.client = mock_client
        
        # Execute
        client = await auth_service.ensure_authenticated()
        
        # Verify
        assert client == mock_client
        mock_client.get_account_numbers.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_ensure_authenticated_reauthenticate(self, auth_service, mock_oauth_manager, mock_client):
        """Test ensure_authenticated re-authenticates on failure."""
        # Setup
        bad_client = AsyncMock()
        bad_client.get_account_numbers.side_effect = Exception("Auth error")
        
        auth_service._initialized = True
        auth_service.client = bad_client
        
        mock_oauth_manager.authenticate.return_value = mock_client
        
        # Execute
        client = await auth_service.ensure_authenticated()
        
        # Verify
        assert client == mock_client
        mock_oauth_manager.authenticate.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_get_authenticated_client_context(self, auth_service, mock_oauth_manager, mock_client):
        """Test context manager for authenticated client."""
        # Setup
        mock_oauth_manager.authenticate.return_value = mock_client
        
        # Execute
        async with auth_service.get_authenticated_client() as client:
            assert client == mock_client
            assert auth_service._initialized is True
            
    @pytest.mark.asyncio
    async def test_test_authentication_success(self, auth_service, mock_oauth_manager, mock_client):
        """Test authentication testing success."""
        # Setup
        mock_oauth_manager.authenticate.return_value = mock_client
        response = Mock()
        response.json.return_value = [
            {'accountNumber': '12345678', 'hashValue': 'abc123'},
            {'accountNumber': '87654321', 'hashValue': 'xyz789'}
        ]
        response.raise_for_status = Mock()
        mock_client.get_account_numbers.return_value = response
        
        # Execute
        results = await auth_service.test_authentication()
        
        # Verify
        assert results['authenticated'] is True
        assert len(results['accounts']) == 2
        assert results['error'] is None
        
    @pytest.mark.asyncio
    async def test_test_authentication_failure(self, auth_service, mock_oauth_manager):
        """Test authentication testing failure."""
        # Setup
        mock_oauth_manager.authenticate.side_effect = Exception("Auth failed")
        
        # Execute
        results = await auth_service.test_authentication()
        
        # Verify
        assert results['authenticated'] is False
        assert results['accounts'] == []
        assert 'Auth failed' in results['error']
        
    def test_is_initialized(self, auth_service):
        """Test initialization check."""
        assert auth_service.is_initialized() is False
        
        auth_service._initialized = True
        assert auth_service.is_initialized() is True
        
    def test_has_valid_client(self, auth_service, mock_client):
        """Test valid client check."""
        assert auth_service.has_valid_client() is False
        
        auth_service._initialized = True
        assert auth_service.has_valid_client() is False
        
        auth_service.client = mock_client
        assert auth_service.has_valid_client() is True
        

class TestModuleFunctions:
    """Test module-level functions."""
    
    def test_get_auth_service_singleton(self):
        """Test auth service singleton behavior."""
        with patch('src.auth.auth_service._auth_service', None):
            service1 = get_auth_service()
            service2 = get_auth_service()
            
            assert service1 is service2
            
    @pytest.mark.asyncio
    async def test_get_authenticated_client_function(self):
        """Test convenience function for getting client."""
        mock_service = AsyncMock()
        mock_client = Mock()
        mock_service.ensure_authenticated.return_value = mock_client
        
        with patch('src.auth.auth_service.get_auth_service', return_value=mock_service):
            client = await get_authenticated_client()
            
            assert client == mock_client
            mock_service.ensure_authenticated.assert_called_once()
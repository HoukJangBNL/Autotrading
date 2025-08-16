"""Tests for OAuth manager."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

from src.auth.oauth_manager import OAuthManager
from src.auth.exceptions import OAuthFlowError


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = Mock()
    settings.schwab.api_key = "test_api_key"
    settings.schwab.app_secret = "test_app_secret"  
    settings.schwab.callback_url = "https://127.0.0.1:8182"
    settings.schwab.account_number = "12345678"
    settings.config_dir = "/tmp/test_config"
    return settings


@pytest.fixture
def mock_token_store():
    """Mock token store for testing."""
    token_store = Mock()
    token_store.load_token = Mock(return_value=None)
    token_store.is_token_valid = Mock(return_value=False)
    token_store.save_token = Mock()
    token_store.save_to_file = Mock()
    token_store.get_token_file_path = Mock(return_value="/tmp/test_token.json")
    return token_store


@pytest.fixture
def valid_token_data():
    """Valid token data for testing."""
    return {
        'access_token': 'test_access_token',
        'refresh_token': 'test_refresh_token',
        'expires_at': (datetime.now() + timedelta(days=6)).isoformat(),
        'token_type': 'Bearer',
        'expires_in': 518400  # 6 days
    }


@pytest.fixture
def expired_token_data():
    """Expired token data for testing."""
    return {
        'access_token': 'expired_access_token',
        'refresh_token': 'expired_refresh_token', 
        'expires_at': (datetime.now() - timedelta(days=1)).isoformat(),
        'token_type': 'Bearer',
        'expires_in': 0
    }


@pytest.fixture
async def oauth_manager(mock_settings, mock_token_store):
    """OAuth manager instance for testing."""
    with patch('src.auth.oauth_manager.get_settings', return_value=mock_settings):
        with patch('src.auth.oauth_manager.TokenStore', return_value=mock_token_store):
            manager = OAuthManager()
            return manager


class TestOAuthManager:
    """Test cases for OAuthManager."""
    
    @pytest.mark.asyncio
    async def test_authenticate_with_valid_token(self, oauth_manager, mock_token_store, valid_token_data):
        """Test authentication with valid existing token."""
        # Setup
        mock_token_store.load_token.return_value = valid_token_data
        mock_token_store.is_token_valid.return_value = True
        
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = [{'accountNumber': '12345678', 'hashValue': 'abc123'}]
        mock_response.raise_for_status = Mock()
        mock_client.get_account_numbers.return_value = mock_response
        
        with patch.object(oauth_manager, '_create_client_from_token', return_value=mock_client) as mock_create:
            # Execute
            client = await oauth_manager.authenticate()
            
            # Verify
            assert client == mock_client
            mock_token_store.load_token.assert_called_once()
            mock_token_store.is_token_valid.assert_called_once_with(valid_token_data)
            mock_create.assert_called_once_with(valid_token_data)
            mock_client.get_account_numbers.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_authenticate_with_expired_token(self, oauth_manager, mock_token_store, expired_token_data):
        """Test authentication with expired token triggers new OAuth flow."""
        # Setup
        mock_token_store.load_token.return_value = expired_token_data
        mock_token_store.is_token_valid.return_value = False
        
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = [{'accountNumber': '12345678', 'hashValue': 'abc123'}]
        mock_response.raise_for_status = Mock()
        mock_client.get_account_numbers.return_value = mock_response
        
        with patch.object(oauth_manager, '_perform_oauth_flow', return_value=mock_client) as mock_oauth:
            # Execute
            client = await oauth_manager.authenticate()
            
            # Verify
            assert client == mock_client
            mock_token_store.load_token.assert_called_once()
            mock_token_store.is_token_valid.assert_called_once_with(expired_token_data)
            mock_oauth.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_authenticate_no_existing_token(self, oauth_manager, mock_token_store):
        """Test authentication with no existing token."""
        # Setup
        mock_token_store.load_token.return_value = None
        mock_token_store.is_token_valid.return_value = False
        
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = [{'accountNumber': '12345678'}]
        mock_response.raise_for_status = Mock()
        mock_client.get_account_numbers.return_value = mock_response
        
        with patch.object(oauth_manager, '_perform_oauth_flow', return_value=mock_client) as mock_oauth:
            # Execute
            client = await oauth_manager.authenticate()
            
            # Verify
            assert client == mock_client
            mock_oauth.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_perform_oauth_flow_success(self, oauth_manager, mock_settings, mock_token_store):
        """Test successful OAuth flow."""
        # Setup
        mock_client = AsyncMock()
        mock_client._token = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 518400,
            'token_type': 'Bearer'
        }
        
        with patch('src.auth.oauth_manager.auth.easy_client', return_value=mock_client) as mock_easy_client:
            with patch.object(oauth_manager, '_save_client_token') as mock_save:
                # Execute
                client = await oauth_manager._perform_oauth_flow()
                
                # Verify
                assert client == mock_client
                mock_easy_client.assert_called_once_with(
                    api_key=mock_settings.schwab.api_key,
                    redirect_uri=mock_settings.schwab.callback_url,
                    token_path=str(mock_token_store.get_token_file_path()),
                    asyncio=True,
                    app_secret=mock_settings.schwab.app_secret
                )
                mock_save.assert_called_once_with(mock_client)
                
    @pytest.mark.asyncio
    async def test_perform_oauth_flow_failure(self, oauth_manager):
        """Test OAuth flow failure."""
        # Setup
        with patch('src.auth.oauth_manager.auth.easy_client', side_effect=Exception("OAuth failed")):
            # Execute & Verify
            with pytest.raises(RuntimeError, match="OAuth authentication failed"):
                await oauth_manager._perform_oauth_flow()
                
    @pytest.mark.asyncio
    async def test_create_client_from_token(self, oauth_manager, mock_settings, mock_token_store, valid_token_data):
        """Test creating client from saved token."""
        # Setup
        mock_client = AsyncMock()
        
        with patch('src.auth.oauth_manager.auth.client_from_token_file', return_value=mock_client) as mock_from_file:
            # Execute
            client = await oauth_manager._create_client_from_token(valid_token_data)
            
            # Verify
            assert client == mock_client
            mock_token_store.save_to_file.assert_called_once_with(valid_token_data)
            mock_from_file.assert_called_once_with(
                token_path=str(mock_token_store.get_token_file_path()),
                api_key=mock_settings.schwab.api_key,
                app_secret=mock_settings.schwab.app_secret,
                asyncio=True
            )
            
    @pytest.mark.asyncio
    async def test_save_client_token(self, oauth_manager, mock_token_store):
        """Test saving token from client."""
        # Setup
        mock_client = Mock()
        mock_client._token = {
            'access_token': 'test_token',
            'refresh_token': 'refresh_token',
            'expires_in': 518400,
            'token_type': 'Bearer'
        }
        
        # Execute
        await oauth_manager._save_client_token(mock_client)
        
        # Verify
        mock_token_store.save_token.assert_called_once()
        saved_token = mock_token_store.save_token.call_args[0][0]
        assert saved_token['access_token'] == 'test_token'
        assert 'expires_at' in saved_token
        mock_token_store.save_to_file.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_test_client_success(self, oauth_manager):
        """Test successful client validation."""
        # Setup
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = [
            {'accountNumber': '12345678', 'hashValue': 'abc123'},
            {'accountNumber': '87654321', 'hashValue': 'xyz789'}
        ]
        mock_response.raise_for_status = Mock()
        mock_client.get_account_numbers.return_value = mock_response
        
        oauth_manager.client = mock_client
        
        # Execute - should not raise
        await oauth_manager._test_client()
        
        # Verify
        mock_client.get_account_numbers.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_test_client_failure(self, oauth_manager):
        """Test client validation failure."""
        # Setup
        mock_client = AsyncMock()
        mock_client.get_account_numbers.side_effect = Exception("API error")
        
        oauth_manager.client = mock_client
        
        # Execute & Verify
        with pytest.raises(RuntimeError, match="Client authentication test failed"):
            await oauth_manager._test_client()
            
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, oauth_manager, mock_token_store):
        """Test successful token refresh."""
        # Setup
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = [{'accountNumber': '12345678'}]
        mock_response.raise_for_status = Mock()
        mock_client.get_account_numbers.return_value = mock_response
        
        oauth_manager.client = mock_client
        
        with patch.object(oauth_manager, '_save_client_token') as mock_save:
            # Execute
            await oauth_manager.refresh_token()
            
            # Verify
            mock_client.get_account_numbers.assert_called_once()
            mock_save.assert_called_once_with(mock_client)
            
    @pytest.mark.asyncio
    async def test_refresh_token_no_client(self, oauth_manager):
        """Test token refresh with no client."""
        # Execute & Verify
        with pytest.raises(RuntimeError, match="No client initialized"):
            await oauth_manager.refresh_token()
            
    def test_get_client(self, oauth_manager):
        """Test getting client instance."""
        # Setup
        mock_client = Mock()
        oauth_manager.client = mock_client
        
        # Execute
        client = oauth_manager.get_client()
        
        # Verify
        assert client == mock_client
        
    @pytest.mark.asyncio
    async def test_close(self, oauth_manager):
        """Test closing client session."""
        # Setup
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        oauth_manager.client = mock_client
        
        # Execute
        await oauth_manager.close()
        
        # Verify
        mock_client.close.assert_called_once()
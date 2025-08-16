"""Tests for OAuth Manager."""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import json
import httpx

from src.auth.oauth_manager import OAuthManager
from src.auth.exceptions import AuthenticationError, TokenRefreshError


@pytest.fixture
def oauth_manager():
    """Create OAuthManager instance."""
    with patch('src.auth.oauth_manager.TokenStore') as mock_token_store:
        # Create a mock token store instance
        mock_store = Mock()
        mock_token_store.return_value = mock_store
        
        # Create OAuth manager
        manager = OAuthManager()
        
        # Attach the mock store for test access
        manager.token_store = mock_store
        
        return manager


@pytest.fixture
def mock_token_data():
    """Mock token data."""
    return {
        'access_token': 'test_access_token',
        'refresh_token': 'test_refresh_token',
        'expires_in': 1800,
        'token_type': 'Bearer',
        'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
    }


@pytest.fixture
def expired_token_data():
    """Mock expired token data."""
    return {
        'access_token': 'expired_access_token',
        'refresh_token': 'expired_refresh_token',
        'expires_in': 1800,
        'token_type': 'Bearer',
        'expires_at': (datetime.now() - timedelta(hours=1)).isoformat()
    }


class TestOAuthManager:
    """Test OAuth Manager functionality."""
    
    def test_get_authorization_url(self, oauth_manager):
        """Test authorization URL generation."""
        # Generate URL
        auth_url = oauth_manager.get_authorization_url()
        
        # Verify URL structure
        assert auth_url.startswith(oauth_manager.AUTHORIZATION_URL)
        assert 'client_id=' in auth_url
        assert 'redirect_uri=' in auth_url
        assert 'state=' in auth_url
        assert 'code_challenge=' in auth_url
        assert 'code_challenge_method=S256' in auth_url
        
        # Verify state and code verifier are set
        assert oauth_manager._state is not None
        assert oauth_manager._code_verifier is not None
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token_success(self, oauth_manager, mock_token_data):
        """Test successful code exchange."""
        # Setup
        oauth_manager._state = 'test_state'
        oauth_manager._code_verifier = 'test_verifier'
        
        mock_response = Mock()
        mock_response.json.return_value = mock_token_data
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            with patch.object(oauth_manager.token_store, 'save_token') as mock_save:
                # Execute
                result = await oauth_manager.exchange_code_for_token(
                    'https://127.0.0.1:8182?code=test_code&state=test_state'
                )
                
                # Verify
                assert result['access_token'] == 'test_access_token'
                assert 'expires_at' in result
                mock_save.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token_state_mismatch(self, oauth_manager):
        """Test code exchange with state mismatch."""
        oauth_manager._state = 'expected_state'
        
        with pytest.raises(AuthenticationError, match="State mismatch"):
            await oauth_manager.exchange_code_for_token(
                'https://127.0.0.1:8182?code=test_code&state=wrong_state'
            )
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token_error_response(self, oauth_manager):
        """Test code exchange with error response."""
        oauth_manager._state = 'test_state'
        
        with pytest.raises(AuthenticationError, match="Authorization failed"):
            await oauth_manager.exchange_code_for_token(
                'https://127.0.0.1:8182?error=access_denied&error_description=User%20denied&state=test_state'
            )
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_success(self, oauth_manager, mock_token_data):
        """Test successful token refresh."""
        # Setup existing token
        existing_token = {
            'refresh_token': 'existing_refresh_token',
            'access_token': 'old_access_token'
        }
        
        with patch.object(oauth_manager.token_store, 'load_token', return_value=existing_token):
            mock_response = Mock()
            mock_response.json.return_value = mock_token_data
            mock_response.raise_for_status = Mock()
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
                with patch.object(oauth_manager.token_store, 'save_token') as mock_save:
                    # Execute
                    result = await oauth_manager.refresh_access_token()
                    
                    # Verify
                    assert result['access_token'] == 'test_access_token'
                    assert 'expires_at' in result
                    mock_save.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_no_refresh_token(self, oauth_manager):
        """Test refresh with no refresh token."""
        with patch.object(oauth_manager.token_store, 'load_token', return_value={}):
            with pytest.raises(TokenRefreshError, match="No refresh token"):
                await oauth_manager.refresh_access_token()
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_401_error(self, oauth_manager):
        """Test refresh with 401 error (invalid refresh token)."""
        existing_token = {'refresh_token': 'invalid_refresh_token'}
        
        with patch.object(oauth_manager.token_store, 'load_token', return_value=existing_token):
            mock_response = Mock()
            mock_response.status_code = 401
            mock_error = httpx.HTTPStatusError(
                message="401 Unauthorized",
                request=Mock(),
                response=mock_response
            )
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=mock_error)
                
                with pytest.raises(TokenRefreshError, match="Refresh token invalid"):
                    await oauth_manager.refresh_access_token(retry_count=1)
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_with_retry(self, oauth_manager, mock_token_data):
        """Test refresh with retry logic."""
        existing_token = {'refresh_token': 'test_refresh_token'}
        
        with patch.object(oauth_manager.token_store, 'load_token', return_value=existing_token):
            # First two calls fail, third succeeds
            mock_response = Mock()
            mock_response.json.return_value = mock_token_data
            mock_response.raise_for_status = Mock()
            
            mock_error = httpx.HTTPStatusError(
                message="500 Server Error",
                request=Mock(),
                response=Mock(status_code=500)
            )
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_post = AsyncMock()
                mock_post.side_effect = [mock_error, mock_error, mock_response]
                mock_client.return_value.__aenter__.return_value.post = mock_post
                
                with patch.object(oauth_manager.token_store, 'save_token'):
                    with patch('asyncio.sleep', new_callable=AsyncMock):  # Speed up test
                        # Execute
                        result = await oauth_manager.refresh_access_token(retry_count=3)
                        
                        # Verify
                        assert result['access_token'] == 'test_access_token'
                        assert mock_post.call_count == 3
    
    def test_is_token_expiring_soon_true(self, oauth_manager):
        """Test token expiring soon detection."""
        # Token expires in 12 hours (less than buffer)
        token_data = {
            'expires_at': (datetime.now() + timedelta(hours=12)).isoformat()
        }
        
        assert oauth_manager.is_token_expiring_soon(token_data) is True
    
    def test_is_token_expiring_soon_false(self, oauth_manager):
        """Test token not expiring soon."""
        # Token expires in 3 days
        token_data = {
            'expires_at': (datetime.now() + timedelta(days=3)).isoformat()
        }
        
        assert oauth_manager.is_token_expiring_soon(token_data) is False
    
    def test_is_token_expiring_soon_no_expiry(self, oauth_manager):
        """Test token with no expiry date."""
        token_data = {'access_token': 'test'}
        assert oauth_manager.is_token_expiring_soon(token_data) is True
    
    @pytest.mark.asyncio
    async def test_ensure_valid_token_success(self, oauth_manager, mock_token_data):
        """Test ensure valid token with valid token."""
        with patch.object(oauth_manager.token_store, 'load_token', return_value=mock_token_data):
            with patch.object(oauth_manager.token_store, 'is_token_valid', return_value=True):
                with patch.object(oauth_manager, 'is_token_expiring_soon', return_value=False):
                    result = await oauth_manager.ensure_valid_token()
                    assert result == mock_token_data
    
    @pytest.mark.asyncio
    async def test_ensure_valid_token_refresh_needed(self, oauth_manager, mock_token_data):
        """Test ensure valid token when refresh is needed."""
        old_token = mock_token_data.copy()
        old_token['expires_at'] = (datetime.now() + timedelta(hours=12)).isoformat()
        
        new_token = mock_token_data.copy()
        new_token['access_token'] = 'new_access_token'
        
        with patch.object(oauth_manager.token_store, 'load_token', return_value=old_token):
            with patch.object(oauth_manager.token_store, 'is_token_valid', return_value=True):
                with patch.object(oauth_manager, 'refresh_access_token', return_value=new_token):
                    result = await oauth_manager.ensure_valid_token()
                    assert result['access_token'] == 'new_access_token'
    
    @pytest.mark.asyncio
    async def test_ensure_valid_token_no_token(self, oauth_manager):
        """Test ensure valid token with no token."""
        with patch.object(oauth_manager.token_store, 'load_token', return_value=None):
            with pytest.raises(AuthenticationError, match="No valid token"):
                await oauth_manager.ensure_valid_token()
    
    def test_get_token_info(self, oauth_manager, mock_token_data):
        """Test get token info."""
        with patch.object(oauth_manager.token_store, 'load_token', return_value=mock_token_data):
            with patch.object(oauth_manager.token_store, 'is_token_valid', return_value=True):
                with patch.object(oauth_manager, 'is_token_expiring_soon', return_value=False):
                    info = oauth_manager.get_token_info()
                    
                    assert info['has_access_token'] is True
                    assert info['has_refresh_token'] is True
                    assert info['is_valid'] is True
                    assert info['is_expiring_soon'] is False
                    assert 'time_until_expiry' in info
    
    def test_get_token_info_no_token(self, oauth_manager):
        """Test get token info with no token."""
        with patch.object(oauth_manager.token_store, 'load_token', return_value=None):
            assert oauth_manager.get_token_info() is None
    
    @pytest.mark.asyncio
    async def test_authenticate_with_valid_token(self, oauth_manager, mock_token_data):
        """Test authenticate with existing valid token."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [{'accountNumber': '123', 'hashValue': 'abc'}]
        mock_client.get_account_numbers = AsyncMock(return_value=mock_response)
        
        with patch.object(oauth_manager.token_store, 'load_token', return_value=mock_token_data):
            with patch.object(oauth_manager.token_store, 'is_token_valid', return_value=True):
                with patch.object(oauth_manager, '_create_client_from_token', return_value=mock_client):
                    oauth_manager.client = mock_client
                    
                    result = await oauth_manager.authenticate()
                    assert result == mock_client
    
    @pytest.mark.asyncio
    async def test_authenticate_perform_oauth_flow(self, oauth_manager):
        """Test authenticate with OAuth flow."""
        mock_client = Mock()
        
        with patch.object(oauth_manager.token_store, 'load_token', return_value=None):
            with patch.object(oauth_manager, '_perform_oauth_flow', return_value=mock_client):
                with patch.object(oauth_manager, '_test_client', new_callable=AsyncMock):
                    result = await oauth_manager.authenticate()
                    assert result == mock_client
    
    @pytest.mark.asyncio
    async def test_update_client_token(self, oauth_manager, mock_token_data):
        """Test updating client token."""
        mock_client = Mock()
        mock_client._token = {'old': 'token'}
        mock_session = Mock()
        mock_session.headers = {}
        mock_client._session = mock_session
        
        oauth_manager.client = mock_client
        
        await oauth_manager._update_client_token(mock_token_data)
        
        assert mock_client._token == mock_token_data
        assert mock_session.headers['Authorization'] == f"Bearer {mock_token_data['access_token']}"
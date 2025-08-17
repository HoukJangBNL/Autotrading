"""Extended tests for authentication service to improve coverage."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
import asyncio
from datetime import datetime, timedelta

from src.auth.auth_service import AuthService, get_auth_service, get_authenticated_client, _auth_service


class TestAuthServiceInit:
    """Test cases for AuthService initialization."""
    
    def test_init_direct(self):
        """Test direct initialization of AuthService."""
        with patch('src.auth.auth_service.get_settings') as mock_get_settings:
            with patch('src.auth.auth_service.OAuthManager') as mock_oauth_manager:
                # Setup
                mock_settings = Mock()
                mock_get_settings.return_value = mock_settings
                
                # Execute
                service = AuthService()
                
                # Verify
                assert service.settings == mock_settings
                assert service.oauth_manager is not None
                assert service.client is None
                assert service._refresh_task is None
                assert service._initialized is False
                mock_oauth_manager.assert_called_once()


class TestTokenRefreshLoop:
    """Test cases for token refresh loop."""
    
    @pytest.mark.asyncio
    async def test_token_refresh_loop_successful(self):
        """Test successful token refresh loop execution."""
        # Setup
        service = AuthService()
        mock_oauth_manager = AsyncMock()
        mock_client = Mock()
        
        # Track calls
        refresh_count = 0
        sleep_count = 0
        
        async def mock_refresh():
            nonlocal refresh_count
            refresh_count += 1
            # After first refresh, we'll cancel the loop
            
        mock_oauth_manager.refresh_token = AsyncMock(side_effect=mock_refresh)
        mock_oauth_manager.get_client.return_value = mock_client
        
        service.oauth_manager = mock_oauth_manager
        
        # Execute with mocked sleep to speed up test
        with patch('src.auth.auth_service.asyncio.sleep') as mock_sleep:
            async def controlled_sleep(seconds):
                nonlocal sleep_count
                sleep_count += 1
                
                if sleep_count == 1:
                    # First sleep is the refresh interval, return to trigger refresh
                    assert seconds == 5 * 24 * 60 * 60
                    return
                else:
                    # This would be the next iteration, cancel the loop
                    raise asyncio.CancelledError()
                
            mock_sleep.side_effect = controlled_sleep
            
            # Run the loop
            task = asyncio.create_task(service._token_refresh_loop())
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
        # Verify
        assert refresh_count == 1
        assert sleep_count >= 1
        mock_oauth_manager.get_client.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_token_refresh_loop_with_error_retry(self):
        """Test token refresh loop with error and retry."""
        # Setup
        service = AuthService()
        mock_oauth_manager = AsyncMock()
        
        refresh_attempts = 0
        
        async def mock_refresh():
            nonlocal refresh_attempts
            refresh_attempts += 1
            raise Exception("Refresh failed")
        
        mock_oauth_manager.refresh_token = AsyncMock(side_effect=mock_refresh)
        service.oauth_manager = mock_oauth_manager
        
        # Execute with mocked sleep
        with patch('src.auth.auth_service.asyncio.sleep') as mock_sleep:
            sleep_calls = []
            
            async def track_sleep(seconds):
                sleep_calls.append(seconds)
                if len(sleep_calls) == 1:
                    # First sleep is the initial wait, return to trigger refresh
                    return
                elif len(sleep_calls) == 2:
                    # Second sleep is the retry interval, cancel after this
                    raise asyncio.CancelledError()
                
            mock_sleep.side_effect = track_sleep
            
            # Run the loop
            task = asyncio.create_task(service._token_refresh_loop())
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
        # Verify
        assert refresh_attempts == 1  # Should have tried to refresh once
        assert len(sleep_calls) == 2
        # First sleep should be 5 days, second should be retry interval (1 hour)
        assert sleep_calls[0] == 5 * 24 * 60 * 60
        assert sleep_calls[1] == 3600


class TestShutdownEdgeCases:
    """Test shutdown edge cases."""
    
    @pytest.mark.asyncio
    async def test_shutdown_no_refresh_task(self):
        """Test shutdown when refresh task doesn't exist."""
        # Setup
        service = AuthService()
        mock_oauth_manager = AsyncMock()
        service.oauth_manager = mock_oauth_manager
        service._initialized = True
        service.client = Mock()
        service._refresh_task = None
        
        # Execute
        await service.shutdown()
        
        # Verify
        assert service._initialized is False
        assert service.client is None
        mock_oauth_manager.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_with_done_refresh_task(self):
        """Test shutdown when refresh task is already done."""
        # Setup
        service = AuthService()
        mock_oauth_manager = AsyncMock()
        service.oauth_manager = mock_oauth_manager
        service._initialized = True
        
        # Create a completed task
        async def completed_task():
            return None
        
        service._refresh_task = asyncio.create_task(completed_task())
        await service._refresh_task  # Let it complete
        
        # Execute
        await service.shutdown()
        
        # Verify
        assert service._initialized is False
        mock_oauth_manager.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_no_oauth_manager(self):
        """Test shutdown when oauth_manager is None."""
        # Setup
        service = AuthService()
        service.oauth_manager = None
        service._initialized = True
        service._refresh_task = None
        
        # Execute - should not raise
        await service.shutdown()
        
        # Verify
        assert service._initialized is False


class TestGetAuthenticatedClientContext:
    """Test context manager edge cases."""
    
    @pytest.mark.asyncio
    async def test_context_manager_initializes_if_needed(self):
        """Test context manager initializes service if not initialized."""
        # Setup
        service = AuthService()
        mock_oauth_manager = AsyncMock()
        mock_client = Mock()
        
        mock_oauth_manager.authenticate.return_value = mock_client
        service.oauth_manager = mock_oauth_manager
        
        # Execute
        async with service.get_authenticated_client() as client:
            assert client == mock_client
            assert service._initialized is True
        
        # Cleanup
        if service._refresh_task:
            service._refresh_task.cancel()
            try:
                await service._refresh_task
            except asyncio.CancelledError:
                pass
    
    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self):
        """Test context manager handles exceptions properly."""
        # Setup
        service = AuthService()
        service._initialized = True
        service.client = Mock()
        
        # Execute
        with pytest.raises(ValueError):
            async with service.get_authenticated_client() as client:
                assert client is not None
                raise ValueError("Test error")
        
        # Context manager should still exit cleanly


class TestSingletonBehavior:
    """Test singleton behavior without mocking."""
    
    def test_get_auth_service_creates_instance(self):
        """Test get_auth_service creates new instance when None."""
        # Reset global
        import src.auth.auth_service
        original = src.auth.auth_service._auth_service
        src.auth.auth_service._auth_service = None
        
        try:
            with patch('src.auth.auth_service.get_settings') as mock_settings:
                with patch('src.auth.auth_service.OAuthManager'):
                    # Execute
                    service = get_auth_service()
                    
                    # Verify
                    assert service is not None
                    assert isinstance(service, AuthService)
                    
                    # Second call should return same instance
                    service2 = get_auth_service()
                    assert service is service2
        finally:
            # Restore original
            src.auth.auth_service._auth_service = original


class TestEnsureAuthenticatedEdgeCases:
    """Test ensure_authenticated edge cases."""
    
    @pytest.mark.asyncio
    async def test_ensure_authenticated_handles_response_error(self):
        """Test ensure_authenticated when response.raise_for_status fails."""
        # Setup
        service = AuthService()
        mock_oauth_manager = AsyncMock()
        mock_client = AsyncMock()
        
        # Mock response that fails raise_for_status
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("HTTP Error")
        mock_client.get_account_numbers.return_value = mock_response
        
        service._initialized = True
        service.client = mock_client
        service.oauth_manager = mock_oauth_manager
        
        # New client after re-auth
        new_client = AsyncMock()
        mock_oauth_manager.authenticate.return_value = new_client
        
        # Execute
        result = await service.ensure_authenticated()
        
        # Verify
        assert result == new_client
        mock_oauth_manager.authenticate.assert_called_once()


class TestTestAuthenticationEdgeCases:
    """Test test_authentication edge cases."""
    
    @pytest.mark.asyncio
    async def test_test_authentication_missing_account_fields(self):
        """Test test_authentication with missing account fields."""
        # Setup
        service = AuthService()
        mock_oauth_manager = AsyncMock()
        mock_client = AsyncMock()
        
        mock_oauth_manager.authenticate.return_value = mock_client
        service.oauth_manager = mock_oauth_manager
        
        # Mock response with missing fields
        mock_response = Mock()
        mock_response.json.return_value = [
            {},  # Empty account
            {'accountNumber': '12345'},  # Missing hashValue
            {'hashValue': 'abc123'}  # Missing accountNumber
        ]
        mock_response.raise_for_status = Mock()
        mock_client.get_account_numbers.return_value = mock_response
        
        # Execute
        results = await service.test_authentication()
        
        # Verify
        assert results['authenticated'] is True
        assert len(results['accounts']) == 3
        # Check that missing fields are handled with 'Unknown'
        assert results['accounts'][0]['accountNumber'] == 'Unknown'
        assert results['accounts'][0]['hashValue'] == 'Unknown'
        assert results['accounts'][1]['hashValue'] == 'Unknown'
        assert results['accounts'][2]['accountNumber'] == 'Unknown'
        
        # Cleanup
        if service._refresh_task:
            service._refresh_task.cancel()
            try:
                await service._refresh_task
            except asyncio.CancelledError:
                pass
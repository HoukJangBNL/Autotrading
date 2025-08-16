"""High-level authentication service for managing OAuth lifecycle."""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from schwab.client import Client

from .oauth_manager import OAuthManager
from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AuthService:
    """
    Manages authentication lifecycle and token refresh.
    
    Provides a high-level interface for authentication with automatic
    token refresh and error recovery.
    """
    
    def __init__(self):
        """Initialize authentication service."""
        self.settings = get_settings()
        self.oauth_manager = OAuthManager()
        self.client: Optional[Client] = None
        self._refresh_task: Optional[asyncio.Task] = None
        self._initialized = False
        
    async def initialize(self) -> None:
        """
        Initialize authentication and start refresh cycle.
        
        Raises:
            RuntimeError: If initialization fails
        """
        if self._initialized:
            logger.warning("Authentication service already initialized")
            return
            
        logger.info("Initializing authentication service")
        
        try:
            # Perform initial authentication
            self.client = await self.oauth_manager.authenticate()
            
            # Start background refresh task
            self._refresh_task = asyncio.create_task(
                self._token_refresh_loop(),
                name="token_refresh"
            )
            
            self._initialized = True
            logger.info("Authentication service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize authentication service: {e}")
            raise RuntimeError(f"Authentication initialization failed: {e}")
            
    async def _token_refresh_loop(self) -> None:
        """
        Background task to refresh token before expiration.
        
        Schwab tokens expire in 7 days. We refresh after 5 days to be safe.
        """
        refresh_interval = 5 * 24 * 60 * 60  # 5 days in seconds
        retry_interval = 60 * 60  # 1 hour retry on failure
        
        while True:
            try:
                # Wait for refresh interval
                await asyncio.sleep(refresh_interval)
                
                logger.info("Starting proactive token refresh")
                await self.oauth_manager.refresh_token()
                
                # Update our client reference
                self.client = self.oauth_manager.get_client()
                
                logger.info("Token refreshed successfully")
                
            except asyncio.CancelledError:
                logger.info("Token refresh loop cancelled")
                break
                
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                logger.warning(f"Retrying token refresh in {retry_interval/3600} hours")
                
                # Retry after shorter interval
                try:
                    await asyncio.sleep(retry_interval)
                except asyncio.CancelledError:
                    break
                    
    async def shutdown(self) -> None:
        """Cleanup authentication service."""
        logger.info("Shutting down authentication service")
        
        # Cancel refresh task
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
                
        # Close OAuth manager
        if self.oauth_manager:
            await self.oauth_manager.close()
            
        self._initialized = False
        self.client = None
        
        logger.info("Authentication service shut down")
        
    def get_client(self) -> Client:
        """
        Get authenticated Schwab client.
        
        Returns:
            Authenticated Client instance
            
        Raises:
            RuntimeError: If not authenticated
        """
        if not self._initialized:
            raise RuntimeError("Authentication service not initialized")
            
        if not self.client:
            raise RuntimeError("No authenticated client available")
            
        return self.client
        
    async def ensure_authenticated(self) -> Client:
        """
        Ensure authentication is valid and return client.
        
        This method can be called to verify authentication
        and re-authenticate if necessary.
        
        Returns:
            Authenticated Client instance
            
        Raises:
            RuntimeError: If authentication fails
        """
        if not self._initialized:
            await self.initialize()
            
        # Test current client
        try:
            response = await self.client.get_account_numbers()
            response.raise_for_status()
            return self.client
            
        except Exception as e:
            logger.warning(f"Current authentication invalid: {e}")
            
            # Re-authenticate
            logger.info("Re-authenticating...")
            self.client = await self.oauth_manager.authenticate()
            
            return self.client
            
    @asynccontextmanager
    async def get_authenticated_client(self):
        """
        Context manager for getting authenticated client.
        
        Ensures proper initialization and cleanup.
        
        Yields:
            Authenticated Client instance
            
        Example:
            async with auth_service.get_authenticated_client() as client:
                response = client.get_quotes(['AAPL'])
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            yield self.get_client()
        finally:
            # Could add cleanup here if needed
            pass
            
    async def test_authentication(self) -> Dict[str, Any]:
        """
        Test authentication and return account info.
        
        Returns:
            Dictionary with test results
        """
        results = {
            'authenticated': False,
            'accounts': [],
            'error': None
        }
        
        try:
            client = await self.ensure_authenticated()
            
            # Get account numbers
            response = await client.get_account_numbers()
            response.raise_for_status()
            
            accounts = response.json()
            results['authenticated'] = True
            results['accounts'] = [
                {
                    'accountNumber': acc.get('accountNumber', 'Unknown'),
                    'hashValue': acc.get('hashValue', 'Unknown')
                }
                for acc in accounts
            ]
            
            logger.info(f"Authentication test successful: {len(accounts)} accounts found")
            
        except Exception as e:
            results['error'] = str(e)
            logger.error(f"Authentication test failed: {e}")
            
        return results
        
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
        
    def has_valid_client(self) -> bool:
        """Check if we have a valid client."""
        return self._initialized and self.client is not None


# Singleton instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """
    Get the singleton authentication service instance.
    
    Returns:
        AuthService instance
    """
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


async def get_authenticated_client() -> Client:
    """
    Convenience function to get authenticated client.
    
    Returns:
        Authenticated Client instance
        
    Raises:
        RuntimeError: If authentication fails
    """
    auth_service = get_auth_service()
    return await auth_service.ensure_authenticated()
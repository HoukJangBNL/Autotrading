"""OAuth2 authentication manager for Schwab API."""

import asyncio
import webbrowser
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from pathlib import Path
import httpx

from schwab import auth
from schwab.client import Client
from schwab.auth import TokenMetadata

from .token_store import TokenStore
from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class OAuthManager:
    """
    Manages OAuth2 authentication flow with Schwab.
    
    Handles initial authentication, token storage, and client creation.
    Integrates with schwab-py library for OAuth flow.
    """
    
    def __init__(self):
        """Initialize OAuth manager with settings and token store."""
        self.settings = get_settings()
        self.token_store = TokenStore()
        self.client: Optional[Client] = None
        self._token_metadata: Optional[TokenMetadata] = None
        
    async def authenticate(self) -> Client:
        """
        Authenticate and return Schwab client.
        
        Returns:
            Authenticated Client instance
            
        Raises:
            RuntimeError: If authentication fails
        """
        # Try to load existing token
        token_data = self.token_store.load_token()
        
        if self.token_store.is_token_valid(token_data):
            logger.info("Using existing valid token")
            try:
                self.client = await self._create_client_from_token(token_data)
                # Test the client
                await self._test_client()
                return self.client
            except Exception as e:
                logger.warning(f"Failed to use existing token: {e}")
                # Fall through to new auth flow
                
        logger.info("Token expired or not found, starting OAuth flow")
        self.client = await self._perform_oauth_flow()
        
        # Test the client
        await self._test_client()
        
        return self.client
        
    async def _perform_oauth_flow(self) -> Client:
        """
        Perform OAuth2 flow to get new token.
        
        Returns:
            Authenticated Client instance
            
        Raises:
            RuntimeError: If OAuth flow fails
        """
        try:
            callback_url = self.settings.schwab.callback_url
            token_path = self.token_store.get_token_file_path()
            
            # schwab-py uses sync mode by default for OAuth flow
            # We'll use the easy_client method
            logger.info(f"Starting OAuth flow with callback URL: {callback_url}")
            
            # Use schwab-py's easy_client with correct parameters
            # Note: easy_client is synchronous even when asyncio=True
            # Add interactive=False to prevent input prompts
            client = auth.easy_client(
                api_key=self.settings.schwab.api_key,
                app_secret=self.settings.schwab.app_secret,
                callback_url=callback_url,  # Fixed parameter name
                token_path=str(token_path),
                asyncio=True,
                enforce_enums=True,
                interactive=False  # Prevent input prompts in automated scripts
            )
            
            # Save token to our secure storage
            await self._save_client_token(client)
            
            logger.info("OAuth flow completed successfully")
            return client
            
        except Exception as e:
            logger.error(f"OAuth flow failed: {e}")
            raise RuntimeError(f"OAuth authentication failed: {e}")
            
    async def _create_client_from_token(self, token_data: Dict[str, Any]) -> Client:
        """
        Create client from saved token.
        
        Args:
            token_data: Saved token data
            
        Returns:
            Client instance
        """
        # Save token to file for schwab-py
        self.token_store.save_to_file(token_data)
        token_path = self.token_store.get_token_file_path()
        
        # Create client from token file
        # Note: client_from_token_file is synchronous
        client = auth.client_from_token_file(
            token_path=str(token_path),
            api_key=self.settings.schwab.api_key,
            app_secret=self.settings.schwab.app_secret,
            asyncio=True,
            enforce_enums=True
        )
        
        # Update our secure storage if token was refreshed
        if hasattr(client, '_token') and client._token != token_data:
            await self._save_client_token(client)
            
        return client
        
    async def _save_client_token(self, client: Client) -> None:
        """
        Extract and save token from client.
        
        Args:
            client: Authenticated client instance
        """
        try:
            # Get token from client's internal state
            # schwab-py stores token in client._token
            if hasattr(client, '_token'):
                token_data = dict(client._token)
                
                # Ensure we have all required fields
                if 'expires_at' not in token_data and 'expires_in' in token_data:
                    expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'])
                    token_data['expires_at'] = expires_at.isoformat()
                    
                # Save to our secure storage
                self.token_store.save_token(token_data)
                
                # Also save to file for schwab-py compatibility
                self.token_store.save_to_file(token_data)
                
                logger.debug("Token saved successfully")
            else:
                logger.warning("Client does not have accessible token data")
                
        except Exception as e:
            logger.error(f"Failed to save client token: {e}")
            # Don't raise - this is not critical if client works
            
    async def _test_client(self) -> None:
        """
        Test the client with a simple API call.
        
        Raises:
            RuntimeError: If client test fails
        """
        if not self.client:
            raise RuntimeError("No client to test")
            
        try:
            # Make a simple API call to verify authentication
            response = await self.client.get_account_numbers()
            response.raise_for_status()
            
            accounts = response.json()
            logger.info(f"Authentication successful, found {len(accounts)} accounts")
            
            # Log account numbers (masked for security)
            for account in accounts:
                account_num = account.get('accountNumber', 'Unknown')
                masked = f"{account_num[:3]}...{account_num[-3:]}" if len(account_num) > 6 else "***"
                logger.debug(f"Account: {masked}")
                
        except Exception as e:
            logger.error(f"Authentication test failed: {e}")
            raise RuntimeError(f"Client authentication test failed: {e}")
            
    async def refresh_token(self) -> None:
        """
        Manually refresh the token if needed.
        
        Note: schwab-py handles token refresh automatically,
        but this method allows manual refresh if needed.
        
        Raises:
            RuntimeError: If refresh fails
        """
        if not self.client:
            raise RuntimeError("No client initialized")
            
        try:
            # schwab-py should handle refresh automatically
            # Force a refresh by making an API call
            response = await self.client.get_account_numbers()
            response.raise_for_status()
            
            # Save updated token if it was refreshed
            await self._save_client_token(self.client)
            
            logger.info("Token refreshed successfully")
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise RuntimeError(f"Token refresh failed: {e}")
            
    def get_client(self) -> Optional[Client]:
        """
        Get the authenticated client instance.
        
        Returns:
            Client instance or None if not authenticated
        """
        return self.client
        
    async def close(self) -> None:
        """Close the client session if open."""
        if self.client and hasattr(self.client, 'close'):
            await self.client.close()
            logger.debug("Client session closed")
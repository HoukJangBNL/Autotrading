"""
Schwab OAuth flow using schwab-py's built-in authentication.
This replaces our custom OAuth implementation to avoid token format issues.
"""

import asyncio
import logging
import json
import time
import collections
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from urllib.parse import urlparse, parse_qs

from schwab import auth
from schwab.client import Client

from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SchwabAuthFlow:
    """
    Handles OAuth flow using schwab-py's client_from_access_functions.
    
    This approach allows us to manage tokens programmatically without
    requiring interactive terminal input.
    """
    
    def __init__(self):
        """Initialize with settings."""
        self.settings = get_settings()
        self.token_path = Path(self.settings.config_dir) / "schwab_token.json"
        self.client: Optional[Client] = None
        self.token_data: Optional[Dict[str, Any]] = None
        
        # OAuth flow state
        self._auth_url: Optional[str] = None
        self._auth_state: Optional[str] = None
        self._redirect_uri = self.settings.schwab.callback_url
        
        # Load existing token if available
        self._load_token_data()
        
    def _load_token_data(self) -> None:
        """Load token data from file if it exists."""
        if self.token_path.exists():
            try:
                with open(self.token_path, 'r') as f:
                    self.token_data = json.load(f)
                logger.info("Loaded existing token data")
            except Exception as e:
                logger.warning(f"Failed to load token data: {e}")
                self.token_data = None
        else:
            self.token_data = None
    
    def _save_token_data(self, token: Dict[str, Any]) -> None:
        """Save token data to file."""
        try:
            self.token_data = token
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, 'w') as f:
                json.dump(token, f, indent=2)
            logger.info("Saved token data to file")
        except Exception as e:
            logger.error(f"Failed to save token data: {e}")
    
    def _token_read_func(self) -> Optional[Dict[str, Any]]:
        """Function for schwab-py to read token."""
        return self.token_data
    
    def _token_write_func(self, token: Dict[str, Any]) -> None:
        """Function for schwab-py to write token."""
        self._save_token_data(token)
    
    def get_auth_url(self) -> str:
        """
        Get OAuth authorization URL using schwab-py's method.
        
        Returns:
            Authorization URL for user to visit
        """
        # Use schwab-py's get_auth_context to properly generate auth URL with state
        auth_context = auth.get_auth_context(
            api_key=self.settings.schwab.api_key,
            callback_url=self._redirect_uri
        )
        
        self._auth_url = auth_context.authorization_url
        self._auth_state = auth_context.state
        
        logger.info(f"Generated authorization URL: {self._auth_url[:50]}...")
        return self._auth_url
        
    async def complete_auth(self, callback_url: str) -> Client:
        """
        Complete OAuth flow using schwab-py's internal methods.
        
        Args:
            callback_url: The full callback URL with authorization code
            
        Returns:
            Authenticated Client instance
            
        Raises:
            Exception: If authentication fails
        """
        try:
            # Parse the callback URL to check for errors
            parsed = urlparse(callback_url)
            params = parse_qs(parsed.query)
            
            if 'error' in params:
                error = params['error'][0]
                error_desc = params.get('error_description', [''])[0]
                raise ValueError(f"OAuth error: {error} - {error_desc}")
            
            if 'code' not in params:
                raise ValueError("No authorization code in callback URL")
                
            auth_code = params['code'][0]
            logger.info(f"Received authorization code: {auth_code[:10]}...")
            
            # Create AuthContext (schwab-py internal structure)
            AuthContext = collections.namedtuple(
                'AuthContext', ['callback_url', 'authorization_url', 'state']
            )
            
            # Get state from URL if present, otherwise use the one we generated
            state = params.get('state', [None])[0] or self._auth_state
            
            auth_context = AuthContext(
                callback_url=self._redirect_uri,
                authorization_url=self._auth_url,
                state=state
            )
            
            # Use schwab-py's internal function to create client from callback URL
            # This properly handles token format and metadata that schwab-py expects
            self.client = auth.client_from_received_url(
                api_key=self.settings.schwab.api_key,
                app_secret=self.settings.schwab.app_secret,
                auth_context=auth_context,
                received_url=callback_url,
                token_write_func=self._token_write_func,
                asyncio=True
            )
            
            logger.info("Successfully created client with schwab-py")
            return self.client
            
        except Exception as e:
            logger.error(f"Failed to complete OAuth flow: {e}")
            raise
            
    def load_existing_client(self) -> Optional[Client]:
        """
        Load client from existing token file if it exists.
        
        Returns:
            Client instance or None if no valid token
        """
        if not self.token_data:
            logger.info("No existing token data found")
            return None
            
        try:
            # Check if token is expired
            if 'expires_at' in self.token_data:
                if time.time() > self.token_data['expires_at']:
                    logger.info("Access token expired, client will refresh it")
            
            # Create client using access functions
            self.client = auth.client_from_access_functions(
                api_key=self.settings.schwab.api_key,
                app_secret=self.settings.schwab.app_secret,
                token_read_func=self._token_read_func,
                token_write_func=self._token_write_func,
                asyncio=True
            )
            logger.info("Successfully loaded client from token data")
            return self.client
            
        except Exception as e:
            logger.warning(f"Failed to load client from token: {e}")
            # Clear invalid token data
            self.token_data = None
            if self.token_path.exists():
                logger.info("Deleting invalid token file")
                self.token_path.unlink()
            return None
            
    async def ensure_authenticated(self) -> Client:
        """
        Ensure we have a valid authenticated client.
        
        Returns:
            Authenticated Client instance
            
        Raises:
            RuntimeError: If not authenticated
        """
        # Try to load existing client
        if not self.client:
            self.client = self.load_existing_client()
            
        if not self.client:
            raise RuntimeError("No authenticated client. Please complete OAuth flow.")
            
        # Test if client is still valid
        try:
            # Make a simple API call to test authentication
            resp = await self.client.get_account_numbers()
            resp.raise_for_status()
            return self.client
        except Exception as e:
            logger.warning(f"Client authentication test failed: {e}")
            # Token might be expired, try to refresh
            # schwab-py handles token refresh automatically on API calls
            # If it fails, user needs to re-authenticate
            raise RuntimeError(f"Authentication invalid: {e}. Please re-authenticate.")
            
    def get_client(self) -> Optional[Client]:
        """Get current client if available."""
        return self.client
        
    def clear_token(self):
        """Clear stored token file."""
        self.token_data = None
        if self.token_path.exists():
            self.token_path.unlink()
            logger.info("Token file deleted")
        self.client = None
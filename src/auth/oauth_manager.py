"""OAuth2 authentication manager for Schwab API."""

import asyncio
import webbrowser
import secrets
import base64
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, Tuple
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
import httpx
import time

from schwab import auth
from schwab.client import Client
from schwab.auth import TokenMetadata

from .token_store import TokenStore
from .exceptions import AuthenticationError, TokenRefreshError
from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class OAuthManager:
    """
    Manages OAuth2 authentication flow with Schwab.
    
    Handles initial authentication, token storage, and client creation.
    Integrates with schwab-py library for OAuth flow.
    """
    
    # OAuth2 endpoints
    AUTHORIZATION_URL = "https://api.schwabapi.com/v1/oauth/authorize"
    TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
    
    # Token expiration settings
    TOKEN_EXPIRATION_DAYS = 7  # Schwab tokens expire after 7 days
    TOKEN_REFRESH_BUFFER_HOURS = 24  # Refresh 1 day before expiration
    
    def __init__(self):
        """Initialize OAuth manager with settings and token store."""
        self.settings = get_settings()
        self.token_store = TokenStore()
        self.client: Optional[Client] = None
        self._token_metadata: Optional[TokenMetadata] = None
        self._state: Optional[str] = None  # OAuth state for CSRF protection
        self._code_verifier: Optional[str] = None  # PKCE code verifier
    
    def get_authorization_url(self) -> str:
        """
        Generate OAuth2 authorization URL with PKCE.
        
        Returns:
            Authorization URL for user to visit
        """
        # Generate state for CSRF protection
        self._state = secrets.token_urlsafe(32)
        
        # Generate PKCE code verifier and challenge
        self._code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(self._code_verifier.encode()).digest()
        ).decode('utf-8').rstrip('=')
        
        # Build authorization URL
        params = {
            'response_type': 'code',
            'client_id': self.settings.schwab.api_key,
            'redirect_uri': self.settings.schwab.callback_url,
            'state': self._state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        
        auth_url = f"{self.AUTHORIZATION_URL}?{urlencode(params)}"
        logger.info(f"Generated authorization URL: {auth_url[:50]}...")
        
        return auth_url
    
    async def exchange_code_for_token(self, authorization_response: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            authorization_response: Full callback URL with authorization code
            
        Returns:
            Token data dictionary
            
        Raises:
            AuthenticationError: If code exchange fails
        """
        # Parse authorization response
        parsed = urlparse(authorization_response)
        params = parse_qs(parsed.query)
        
        # Verify state
        if not params.get('state') or params['state'][0] != self._state:
            raise AuthenticationError("State mismatch - possible CSRF attack")
        
        # Check for errors
        if 'error' in params:
            error = params['error'][0]
            error_desc = params.get('error_description', ['Unknown error'])[0]
            raise AuthenticationError(f"Authorization failed: {error} - {error_desc}")
        
        # Get authorization code
        if 'code' not in params:
            raise AuthenticationError("No authorization code in response")
        
        auth_code = params['code'][0]
        
        # Exchange code for token
        token_data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'client_id': self.settings.schwab.api_key,
            'client_secret': self.settings.schwab.app_secret,
            'redirect_uri': self.settings.schwab.callback_url,
            'code_verifier': self._code_verifier
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.TOKEN_URL,
                    data=token_data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                response.raise_for_status()
                
                token_response = response.json()
                
                # Add expiration timestamp
                if 'expires_in' in token_response:
                    expires_at = datetime.now() + timedelta(seconds=token_response['expires_in'])
                    token_response['expires_at'] = expires_at.isoformat()
                
                # Save token
                self.token_store.save_token(token_response)
                
                logger.info("Successfully exchanged code for token")
                return token_response
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Token exchange failed: {e.response.text}")
                raise AuthenticationError(f"Token exchange failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error during token exchange: {e}")
                raise AuthenticationError(f"Token exchange error: {e}")
    
    async def refresh_access_token(self, retry_count: int = 3) -> Dict[str, Any]:
        """
        Refresh access token with retry logic and exponential backoff.
        
        Args:
            retry_count: Number of retry attempts (default: 3)
            
        Returns:
            New token data
            
        Raises:
            TokenRefreshError: If refresh fails after all retries
        """
        # Load current token
        token_data = self.token_store.load_token()
        if not token_data or 'refresh_token' not in token_data:
            raise TokenRefreshError("No refresh token available")
        
        refresh_token = token_data['refresh_token']
        
        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(retry_count):
            try:
                # Prepare refresh request
                refresh_data = {
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': self.settings.schwab.api_key,
                    'client_secret': self.settings.schwab.app_secret
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.TOKEN_URL,
                        data=refresh_data,
                        headers={'Content-Type': 'application/x-www-form-urlencoded'},
                        timeout=30.0
                    )
                    response.raise_for_status()
                    
                    new_token_data = response.json()
                    
                    # Add expiration timestamp
                    if 'expires_in' in new_token_data:
                        expires_at = datetime.now() + timedelta(seconds=new_token_data['expires_in'])
                        new_token_data['expires_at'] = expires_at.isoformat()
                    
                    # Preserve refresh token if not included in response
                    if 'refresh_token' not in new_token_data and refresh_token:
                        new_token_data['refresh_token'] = refresh_token
                    
                    # Save new token
                    self.token_store.save_token(new_token_data)
                    
                    # Update client if exists
                    if self.client:
                        await self._update_client_token(new_token_data)
                    
                    logger.info("Token refreshed successfully")
                    return new_token_data
                    
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 401:
                    # Refresh token is invalid - need full re-authentication
                    logger.error("Refresh token is invalid - full re-authentication required")
                    raise TokenRefreshError("Refresh token invalid - please re-authenticate")
                    
                logger.warning(f"Token refresh attempt {attempt + 1} failed: {e}")
                
            except Exception as e:
                last_error = e
                logger.warning(f"Token refresh attempt {attempt + 1} failed: {e}")
            
            # Exponential backoff
            if attempt < retry_count - 1:
                wait_time = (2 ** attempt) + (0.1 * secrets.randbelow(10))
                logger.info(f"Waiting {wait_time:.1f} seconds before retry...")
                await asyncio.sleep(wait_time)
        
        # All retries failed
        raise TokenRefreshError(f"Token refresh failed after {retry_count} attempts: {last_error}")
    
    def is_token_expiring_soon(self, token_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if token is expiring soon (within refresh buffer).
        
        Args:
            token_data: Token data to check (loads from store if not provided)
            
        Returns:
            True if token needs refresh, False otherwise
        """
        if token_data is None:
            token_data = self.token_store.load_token()
        
        if not token_data or 'expires_at' not in token_data:
            return True
        
        try:
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            time_until_expiry = expires_at - datetime.now()
            
            # Check if within refresh buffer
            if time_until_expiry <= timedelta(hours=self.TOKEN_REFRESH_BUFFER_HOURS):
                logger.info(f"Token expiring in {time_until_expiry} - refresh needed")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking token expiration: {e}")
            return True
    
    async def ensure_valid_token(self) -> Dict[str, Any]:
        """
        Ensure we have a valid, non-expiring token.
        
        Returns:
            Valid token data
            
        Raises:
            AuthenticationError: If unable to get valid token
        """
        token_data = self.token_store.load_token()
        
        # Check if token exists and is valid
        if not token_data or not self.token_store.is_token_valid(token_data):
            raise AuthenticationError("No valid token - authentication required")
        
        # Check if token needs refresh
        if self.is_token_expiring_soon(token_data):
            try:
                logger.info("Token expiring soon - refreshing...")
                token_data = await self.refresh_access_token()
            except TokenRefreshError:
                raise AuthenticationError("Token refresh failed - re-authentication required")
        
        return token_data
    
    async def _update_client_token(self, token_data: Dict[str, Any]) -> None:
        """
        Update the client with new token data.
        
        Args:
            token_data: New token data
        """
        if self.client and hasattr(self.client, '_token'):
            # Update internal token
            self.client._token = token_data
            # Also update session headers if using httpx
            if hasattr(self.client, '_session') and self.client._session:
                self.client._session.headers['Authorization'] = f"Bearer {token_data['access_token']}"
        
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
            client = auth.easy_client(
                api_key=self.settings.schwab.api_key,
                app_secret=self.settings.schwab.app_secret,
                callback_url=callback_url,  # Fixed parameter name
                token_path=str(token_path),
                asyncio=True,
                enforce_enums=True
                # Note: interactive parameter removed - not supported in newer versions
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
        
        This method wraps refresh_access_token for backward compatibility.
        
        Raises:
            RuntimeError: If refresh fails
        """
        try:
            await self.refresh_access_token()
        except TokenRefreshError as e:
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
    
    def get_token_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current token information including expiration.
        
        Returns:
            Token info or None if no token
        """
        token_data = self.token_store.load_token()
        if not token_data:
            return None
        
        info = {
            'has_access_token': 'access_token' in token_data,
            'has_refresh_token': 'refresh_token' in token_data,
            'expires_at': token_data.get('expires_at'),
            'is_valid': self.token_store.is_token_valid(token_data),
            'is_expiring_soon': self.is_token_expiring_soon(token_data)
        }
        
        if info['expires_at']:
            try:
                expires_at = datetime.fromisoformat(info['expires_at'])
                info['time_until_expiry'] = str(expires_at - datetime.now())
            except Exception:
                pass
        
        return info
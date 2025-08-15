# Immediate Next Steps - Schwab API Integration

## 🎯 Current Focus: OAuth2 Authentication Implementation

### Prerequisites Check
- [x] Python 3.11.7 environment active
- [x] schwab-py 1.5.0 installed
- [x] PostgreSQL and Redis running
- [x] .env file configured with Schwab credentials
- [ ] Schwab Developer Portal access confirmed

### Step 1: Create Authentication Module Structure (30 minutes)

```bash
# Create directory structure
mkdir -p src/auth
mkdir -p tests/test_auth
mkdir -p config/certs  # For SSL certificates if needed
```

Create these files:
1. `src/auth/__init__.py`
2. `src/auth/oauth_manager.py`
3. `src/auth/token_store.py`
4. `src/auth/auth_service.py`
5. `tests/test_auth/test_oauth_manager.py`

### Step 2: Implement Token Storage (1 hour)

```python
# src/auth/token_store.py
"""Secure token storage using keyring and database backup."""

import json
import keyring
from datetime import datetime, timedelta
from typing import Optional, Dict
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet

from ..config.settings import get_settings
from ..data.database import get_db
from ..utils.logger import get_logger

logger = get_logger(__name__)

class TokenStore:
    """Manages secure storage and retrieval of OAuth tokens."""
    
    def __init__(self):
        self.settings = get_settings()
        self.service_name = "schwab_autotrader"
        self.username = "oauth_token"
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize encryption for database storage."""
        # Generate or load encryption key
        key = keyring.get_password(self.service_name, "encryption_key")
        if not key:
            key = Fernet.generate_key().decode()
            keyring.set_password(self.service_name, "encryption_key", key)
        self.cipher = Fernet(key.encode())
    
    def save_token(self, token_data: Dict) -> None:
        """Save token to both keyring and database."""
        try:
            # Save to keyring (primary)
            keyring.set_password(
                self.service_name,
                self.username,
                json.dumps(token_data)
            )
            
            # Save encrypted to database (backup)
            encrypted = self.cipher.encrypt(json.dumps(token_data).encode())
            # TODO: Implement database save
            
            logger.info("Token saved successfully")
        except Exception as e:
            logger.error(f"Failed to save token: {e}")
            raise
    
    def load_token(self) -> Optional[Dict]:
        """Load token from storage."""
        try:
            # Try keyring first
            token_json = keyring.get_password(self.service_name, self.username)
            if token_json:
                return json.loads(token_json)
            
            # Fallback to database
            # TODO: Implement database load
            
            return None
        except Exception as e:
            logger.error(f"Failed to load token: {e}")
            return None
    
    def is_token_valid(self, token_data: Optional[Dict]) -> bool:
        """Check if token is still valid."""
        if not token_data:
            return False
        
        # Check expiration (schwab tokens expire in 7 days)
        if 'expires_at' in token_data:
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            # Refresh if less than 1 day remaining
            return datetime.now() < expires_at - timedelta(days=1)
        
        return False
```

### Step 3: Implement OAuth Manager (2 hours)

```python
# src/auth/oauth_manager.py
"""OAuth2 authentication manager for Schwab API."""

import asyncio
import webbrowser
from datetime import datetime, timedelta
from typing import Optional, Dict
from urllib.parse import urlparse, parse_qs

import httpx
from schwab import auth, Client
from schwab.auth import TokenMetadata

from .token_store import TokenStore
from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

class OAuthManager:
    """Manages OAuth2 authentication flow with Schwab."""
    
    def __init__(self):
        self.settings = get_settings()
        self.token_store = TokenStore()
        self.client: Optional[Client] = None
        self._token_metadata: Optional[TokenMetadata] = None
    
    async def authenticate(self) -> Client:
        """Authenticate and return Schwab client."""
        # Try to load existing token
        token_data = self.token_store.load_token()
        
        if self.token_store.is_token_valid(token_data):
            logger.info("Using existing valid token")
            self.client = self._create_client_from_token(token_data)
        else:
            logger.info("Token expired or not found, starting OAuth flow")
            self.client = await self._perform_oauth_flow()
        
        # Test the client
        try:
            # Make a simple API call to verify authentication
            response = self.client.get_account_numbers()
            logger.info(f"Authentication successful, found {len(response.json())} accounts")
        except Exception as e:
            logger.error(f"Authentication test failed: {e}")
            raise
        
        return self.client
    
    async def _perform_oauth_flow(self) -> Client:
        """Perform OAuth2 flow to get new token."""
        try:
            # Create callback server
            callback_url = self.settings.schwab.callback_url
            
            # Use schwab-py's built-in OAuth flow
            client = await auth.client_from_manual_flow(
                api_key=self.settings.schwab.api_key,
                app_secret=self.settings.schwab.app_secret,
                callback_url=callback_url,
                asyncio=True
            )
            
            # Save token for future use
            self._save_client_token(client)
            
            return client
            
        except Exception as e:
            logger.error(f"OAuth flow failed: {e}")
            raise
    
    def _create_client_from_token(self, token_data: Dict) -> Client:
        """Create client from saved token."""
        # Reconstruct client with saved token
        # This is a simplified version - actual implementation depends on schwab-py internals
        return Client(
            api_key=self.settings.schwab.api_key,
            token_data=token_data,
            asyncio=True
        )
    
    def _save_client_token(self, client: Client) -> None:
        """Extract and save token from client."""
        # Extract token data from client
        # This depends on schwab-py implementation details
        token_data = {
            'access_token': client.token['access_token'],
            'refresh_token': client.token['refresh_token'],
            'expires_at': (datetime.now() + timedelta(seconds=client.token['expires_in'])).isoformat(),
            'token_type': client.token['token_type'],
        }
        
        self.token_store.save_token(token_data)
    
    async def refresh_token(self) -> None:
        """Manually refresh the token if needed."""
        if not self.client:
            raise RuntimeError("No client initialized")
        
        try:
            # Use schwab-py's refresh mechanism
            # This is handled internally by the library
            logger.info("Token refreshed successfully")
            self._save_client_token(self.client)
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise
```

### Step 4: Create Authentication Service (1 hour)

```python
# src/auth/auth_service.py
"""High-level authentication service."""

import asyncio
from typing import Optional
from datetime import datetime, timedelta

from .oauth_manager import OAuthManager
from ..utils.logger import get_logger

logger = get_logger(__name__)

class AuthService:
    """Manages authentication lifecycle and token refresh."""
    
    def __init__(self):
        self.oauth_manager = OAuthManager()
        self.client = None
        self._refresh_task = None
    
    async def initialize(self):
        """Initialize authentication and start refresh cycle."""
        logger.info("Initializing authentication service")
        
        # Perform initial authentication
        self.client = await self.oauth_manager.authenticate()
        
        # Start background refresh task
        self._refresh_task = asyncio.create_task(self._token_refresh_loop())
        
        logger.info("Authentication service initialized")
    
    async def _token_refresh_loop(self):
        """Background task to refresh token before expiration."""
        while True:
            try:
                # Wait for 6 days (refresh 1 day before expiration)
                await asyncio.sleep(6 * 24 * 60 * 60)
                
                logger.info("Refreshing token proactively")
                await self.oauth_manager.refresh_token()
                
            except asyncio.CancelledError:
                logger.info("Token refresh loop cancelled")
                break
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                # Retry after 1 hour
                await asyncio.sleep(3600)
    
    async def shutdown(self):
        """Cleanup authentication service."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Authentication service shut down")
    
    def get_client(self):
        """Get authenticated Schwab client."""
        if not self.client:
            raise RuntimeError("Authentication not initialized")
        return self.client
```

### Step 5: Create Test Script (30 minutes)

```python
# scripts/test_auth.py
"""Test authentication with Schwab API."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.auth.auth_service import AuthService
from src.utils.logger import setup_logging

async def main():
    """Test authentication flow."""
    setup_logging()
    
    auth_service = AuthService()
    
    try:
        # Initialize authentication
        await auth_service.initialize()
        
        # Get client and test API call
        client = auth_service.get_client()
        
        # Test: Get account numbers
        response = client.get_account_numbers()
        print(f"Account numbers: {response.json()}")
        
        # Test: Get a quote
        response = client.get_quotes(['AAPL'])
        print(f"AAPL quote: {response.json()}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await auth_service.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 6: Run Initial Test (15 minutes)

```bash
# Activate virtual environment
source venv/bin/activate

# Run the test script
python scripts/test_auth.py
```

**Expected Flow:**
1. Browser opens with Schwab login page
2. Log in with your Schwab credentials
3. Authorize the application
4. Callback captures the authorization code
5. Token is exchanged and saved
6. API calls are tested

### Step 7: Handle Common Issues

#### Issue 1: SSL Certificate Error
```python
# If you get SSL errors with the callback URL, create a self-signed certificate:
openssl req -x509 -newkey rsa:4096 -keyout config/certs/key.pem -out config/certs/cert.pem -days 365 -nodes
```

#### Issue 2: Callback URL Mismatch
- Ensure callback URL in .env matches exactly with Schwab app settings
- Default is `https://127.0.0.1:8182`

#### Issue 3: Token Storage Issues
```bash
# Test keyring access
python -c "import keyring; print(keyring.get_keyring())"
```

### Next: After Authentication Works

Once authentication is confirmed working:

1. **Implement Rate Limiting** (1 hour)
   - Add rate limit tracking
   - Implement exponential backoff
   - Monitor API usage

2. **Create Broker Interface** (2 hours)
   - Abstract Schwab-specific calls
   - Unified error handling
   - Response normalization

3. **Start Data Pipeline** (4 hours)
   - Historical data fetcher
   - Real-time quote service
   - Database integration

## Quick Validation Checklist

Before moving to the next phase, ensure:
- [ ] Can authenticate successfully
- [ ] Token is saved and retrieved
- [ ] Token refresh works
- [ ] Can make API calls (get accounts, get quotes)
- [ ] Error handling works properly
- [ ] Logging provides useful debugging info
- [ ] Tests pass for auth module

## Troubleshooting Commands

```bash
# Check if Redis is running (for later caching)
redis-cli ping

# Check PostgreSQL connection
psql -U trading -d trading_db -c "SELECT current_timestamp;"

# View logs
tail -f logs/trading_*.log

# Run specific auth tests
pytest tests/test_auth/ -v

# Check environment variables
python -c "from src.config.settings import get_settings; s = get_settings(); print(s.schwab.api_key[:10] + '...')"
```

## Emergency Fallback

If schwab-py has issues:
1. Document the exact error
2. Check schwab-py GitHub issues
3. Consider using httpx directly with Schwab API
4. Implement minimal OAuth2 flow manually

Remember: This is real money - test thoroughly before proceeding!
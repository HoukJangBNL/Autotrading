# Authentication Module

This module handles OAuth2 authentication with the Schwab API using the schwab-py library.

## Components

### TokenStore
Manages secure storage of OAuth tokens using keyring (primary) and encrypted database (backup).

**Features:**
- Secure token storage with keyring
- Encrypted database backup using Fernet
- Token validation and expiration checking
- File storage compatibility for schwab-py

### OAuthManager
Handles the OAuth2 flow and client creation with enhanced security features.

**Features:**
- OAuth2 authentication flow with PKCE (Proof Key for Code Exchange)
- State parameter for CSRF protection
- Manual authorization URL generation (`get_authorization_url()`)
- Authorization code exchange (`exchange_code_for_token()`)
- Token refresh with retry logic (`refresh_access_token()`)
- Token expiration monitoring (`is_token_expiring_soon()`)
- Token status information (`get_token_info()`)

### AuthService
High-level service managing the authentication lifecycle.

**Features:**
- Singleton pattern for single auth instance
- Automatic token refresh every 5 days
- Context manager support
- Comprehensive error handling

## Initial Setup

Run the interactive authentication setup:
```bash
python scripts/auth_setup.py
```

This will:
1. Verify your Schwab API credentials
2. Start a local HTTPS server for OAuth callback
3. Open your browser for Schwab login
4. Save tokens securely in system keychain

## Usage

### Basic Usage
```python
from src.auth import get_auth_service

# Get auth service instance
auth_service = get_auth_service()

# Initialize authentication
await auth_service.initialize()

# Get authenticated client
client = auth_service.get_client()

# Make API calls
response = await client.get_account_numbers()

# Shutdown when done
await auth_service.shutdown()
```

### Using Context Manager
```python
from src.auth import get_auth_service

auth_service = get_auth_service()

async with auth_service.get_authenticated_client() as client:
    # Client is automatically initialized
    response = client.get_quotes(['AAPL'])
```

### Convenience Function
```python
from src.auth import get_authenticated_client

# Automatically initializes if needed
client = await get_authenticated_client()
response = await client.get_account_numbers()
```

### Direct OAuth Manager Usage
```python
from src.auth.oauth_manager import OAuthManager

oauth_manager = OAuthManager()

# Generate authorization URL
auth_url = oauth_manager.get_authorization_url()
print(f"Visit: {auth_url}")

# After user authorizes, exchange code for token
token_data = await oauth_manager.exchange_code_for_token(callback_url)

# Check token status
token_info = oauth_manager.get_token_info()
print(f"Token valid: {token_info['is_valid']}")
print(f"Expires: {token_info['expires_at']}")

# Manual token refresh
await oauth_manager.refresh_access_token()
```

## Token Storage

Tokens are stored in three locations:
1. **Keyring** (primary) - Most secure, OS-managed
2. **Database** (backup) - Encrypted with Fernet
3. **File** (compatibility) - For schwab-py internal use

The token is automatically refreshed 1 day before expiration (Schwab tokens expire in 7 days).

## Error Handling

The module provides custom exceptions:
- `AuthenticationError` - Base exception
- `TokenExpiredError` - Token has expired
- `TokenRefreshError` - Refresh failed
- `OAuthFlowError` - OAuth flow failed
- `ClientInitializationError` - Client init failed
- `TokenStorageError` - Storage operation failed
- `APITestError` - API test failed

## Token Lifecycle

1. **Initial Token**: Valid for 30 minutes (access) and 7 days (refresh)
2. **Automatic Refresh**: Triggers 24 hours before expiration
3. **Manual Refresh**: Available via `refresh_access_token()`
4. **Re-authentication**: Required after 7 days or on refresh failure

## Testing

Run the authentication setup:
```bash
python scripts/auth_setup.py
```

Run unit tests:
```bash
pytest tests/test_oauth_manager.py -v
```

The test suite covers:
- OAuth flow generation and validation
- Token exchange and refresh
- Error scenarios and retry logic
- Token expiration checking
- Client token updates

## Security Features

1. **PKCE Implementation**: Protects against authorization code interception
2. **State Parameter**: CSRF protection for OAuth flow
3. **Keychain Storage**: Tokens stored in OS-level secure storage
4. **Encryption**: Database backup uses Fernet encryption
5. **Token Rotation**: Automatic refresh before expiration
6. **No Token in Logs**: Sensitive data never logged
7. **Retry Logic**: Exponential backoff for transient failures

## Troubleshooting

### OAuth Callback Issues
If you get SSL errors:
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

### Token Not Found
Check keyring access:
```python
import keyring
print(keyring.get_keyring())
```

### Authentication Fails
1. Verify Schwab app credentials in .env
2. Check callback URL matches app settings (https://127.0.0.1:8182)
3. Ensure your app is in "Ready for Use" status
4. Try deleting existing token and re-authenticating
5. Check if refresh token has expired (7 days)

### SSL Certificate Warning
This is normal for the local callback server. The auth setup script uses a self-signed certificate. Click "Advanced" and "Proceed to 127.0.0.1" in your browser.

## Environment Variables

Required in `.env`:
```
SCHWAB_API_KEY=your_api_key
SCHWAB_APP_SECRET=your_app_secret
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182
```
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
Handles the OAuth2 flow and client creation.

**Features:**
- OAuth2 authentication flow
- Client creation from saved tokens
- Automatic token refresh
- API connection testing

### AuthService
High-level service managing the authentication lifecycle.

**Features:**
- Singleton pattern for single auth instance
- Automatic token refresh every 5 days
- Context manager support
- Comprehensive error handling

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
response = client.get_account_numbers()

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
response = client.get_account_numbers()
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

## Testing

Run the test script to verify authentication:
```bash
python scripts/test_auth.py
```

Run unit tests:
```bash
pytest tests/test_auth/ -v
```

## Security Notes

1. **Never commit tokens** - The module ensures tokens are never logged
2. **Keyring security** - Primary storage uses OS keyring
3. **Database encryption** - Backup tokens are encrypted
4. **Token expiration** - Automatic refresh before expiration
5. **API key safety** - Store in .env file, never in code

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
2. Check callback URL matches app settings
3. Ensure you're logged into Schwab account
4. Try deleting existing token and re-authenticating

## Environment Variables

Required in `.env`:
```
SCHWAB_API_KEY=your_api_key
SCHWAB_APP_SECRET=your_app_secret
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182
```
# Schwab-py Integration Notes

## Important: Import Patterns

The correct import pattern for schwab-py is:
```python
from schwab import auth
from schwab.client import Client  # NOT "from schwab import Client"
```

## Authentication Functions

schwab-py provides several authentication methods:

### 1. easy_client() [Recommended]
```python
client = auth.easy_client(
    api_key=api_key,
    app_secret=app_secret,
    callback_url=callback_url,  # NOT redirect_uri
    token_path=token_path,
    asyncio=True,  # For async client
    enforce_enums=True
)
```

### 2. client_from_token_file()
```python
client = auth.client_from_token_file(
    token_path=token_path,
    api_key=api_key,
    app_secret=app_secret,
    asyncio=True,
    enforce_enums=True
)
```

## Key Points

1. **Synchronous vs Asynchronous**:
   - OAuth functions (`easy_client`, `client_from_token_file`) are synchronous
   - When `asyncio=True`, the returned client methods need `await`
   - Don't use `await` on the auth functions themselves

2. **Token Storage**:
   - schwab-py expects a file path for token storage
   - Tokens expire in 7 days (Schwab limitation)
   - The library handles refresh automatically on API calls

3. **Callback URL**:
   - Must match EXACTLY what's registered in Schwab Developer Portal
   - Default port is 8182: `https://127.0.0.1:8182`
   - Include the port in your .env file

4. **Common Errors**:
   - `ImportError: cannot import name 'Client'` → Use `from schwab.client import Client`
   - `TypeError: got an unexpected keyword argument 'redirect_uri'` → Use `callback_url`
   - `SSL Error` → The callback URL uses HTTPS, browser will show warning

## OAuth Flow

1. `easy_client()` opens browser automatically
2. Log into Schwab account
3. Authorize the application
4. Browser redirects to callback URL (will show error page)
5. Copy the ENTIRE URL from browser
6. Paste when prompted in terminal
7. Token is saved to file

## Testing Authentication

Use the simple test script first:
```bash
python scripts/test_oauth_simple.py
```

This tests schwab-py directly without our wrapper code.

## Environment Variables

Required in `.env`:
```
SCHWAB_API_KEY=your_api_key_here
SCHWAB_APP_SECRET=your_app_secret_here
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182
```

## Troubleshooting

1. **Browser doesn't open**: 
   - Run on a system with GUI
   - Or use `client_from_manual_flow()` instead

2. **Callback URL error**:
   - This is normal - copy the URL with the authorization code
   - URL will look like: `https://127.0.0.1:8182/?code=...&session=...`

3. **Token not saving**:
   - Check file permissions
   - Ensure token_path directory exists

4. **API calls fail after auth**:
   - Token might be expired (7 days)
   - Delete token file and re-authenticate
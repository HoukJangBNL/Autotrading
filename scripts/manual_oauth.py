#!/usr/bin/env python3
"""Manual OAuth flow test."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from schwab import auth
import os
from dotenv import load_dotenv

load_dotenv()

# Get credentials
api_key = os.getenv('SCHWAB_API_KEY')
app_secret = os.getenv('SCHWAB_APP_SECRET')
callback_url = os.getenv('SCHWAB_CALLBACK_URL')
token_path = str(Path.home() / '.schwab_token.json')

print("Manual OAuth Flow")
print("=" * 60)
print(f"Callback URL: {callback_url}")
print()

try:
    # Use client_from_manual_flow which handles input better
    print("Starting manual OAuth flow...")
    print("1. A browser will open")
    print("2. Log in and approve permissions")
    print("3. Copy the ENTIRE redirect URL")
    print("4. Paste it below when prompted")
    print()
    
    client = auth.client_from_manual_flow(
        api_key=api_key,
        app_secret=app_secret,
        callback_url=callback_url,
        token_path=token_path
    )
    
    print("\n✅ OAuth successful!")
    
    # Test it
    response = client.get_account_numbers()
    response.raise_for_status()
    accounts = response.json()
    
    print(f"\n✅ Found {len(accounts)} accounts:")
    for acc in accounts:
        print(f"  Account: {acc.get('accountNumber')}")
        print(f"  Hash: {acc.get('hashValue')}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
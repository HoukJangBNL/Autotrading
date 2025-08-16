#!/usr/bin/env python3
"""Quick test after OAuth completion."""

import sys
from pathlib import Path
import json

sys.path.append(str(Path(__file__).parent.parent))

from schwab import auth
from schwab.client import Client
import os
from dotenv import load_dotenv

load_dotenv()

# Check if token was created
token_path = Path.home() / '.schwab_token.json'

if token_path.exists():
    print("✅ Token file exists!")
    
    with open(token_path, 'r') as f:
        token_data = json.load(f)
    
    print("\nToken Details:")
    if 'token' in token_data:
        token = token_data['token']
        print(f"  Scope: {token.get('scope', 'N/A')}")
        print(f"  Type: {token.get('token_type', 'N/A')}")
    
    # Quick API test
    api_key = os.getenv('SCHWAB_API_KEY')
    app_secret = os.getenv('SCHWAB_APP_SECRET')
    
    client = auth.client_from_token_file(
        token_path=str(token_path),
        api_key=api_key,
        app_secret=app_secret
    )
    
    print("\nTesting APIs:")
    
    # Test accounts
    try:
        response = client.get_account_numbers()
        response.raise_for_status()
        accounts = response.json()
        print(f"✅ Accounts API: Found {len(accounts)} accounts")
        for acc in accounts:
            print(f"   - Number: {acc.get('accountNumber')}")
            print(f"     Hash: {acc.get('hashValue')}")
    except Exception as e:
        print(f"❌ Accounts API: {e}")
        
else:
    print("❌ No token file found")
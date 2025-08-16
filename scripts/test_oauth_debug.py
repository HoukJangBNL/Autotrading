#!/usr/bin/env python3
"""OAuth test with detailed debugging information."""

import sys
from pathlib import Path
import os
import json
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from schwab import auth
from schwab.client import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_oauth_with_debug():
    """Test OAuth with detailed debugging."""
    print("Schwab OAuth Debug Test")
    print("=" * 60)
    
    # Get credentials
    api_key = os.getenv('SCHWAB_API_KEY')
    app_secret = os.getenv('SCHWAB_APP_SECRET')
    callback_url = os.getenv('SCHWAB_CALLBACK_URL')
    
    print(f"API Key: {api_key[:10]}...")
    print(f"Callback URL: {callback_url}")
    print()
    
    # Token file path
    token_path = Path.home() / '.schwab_token.json'
    
    try:
        print("Starting OAuth flow...")
        print("-" * 40)
        print("IMPORTANT: When the browser opens:")
        print("1. Log into your Schwab account")
        print("2. ⚠️  CAREFULLY CHECK the permissions being requested")
        print("3. ✅ APPROVE ALL permissions (especially account access)")
        print("4. Copy the ENTIRE redirect URL")
        print("-" * 40)
        print()
        
        # Perform OAuth
        client = auth.easy_client(
            api_key=api_key,
            app_secret=app_secret,
            callback_url=callback_url,
            token_path=str(token_path)
        )
        
        print("\n✅ OAuth completed!")
        
        # Check the token file
        if token_path.exists():
            with open(token_path, 'r') as f:
                token_data = json.load(f)
                
            print("\nToken Information:")
            print("-" * 40)
            
            # Display token details
            if 'token' in token_data:
                token = token_data['token']
                print(f"Token Type: {token.get('token_type', 'N/A')}")
                print(f"Expires In: {token.get('expires_in', 'N/A')} seconds")
                print(f"Scope: {token.get('scope', 'N/A')}")  # This is important!
                
                # Check scope
                scope = token.get('scope', '')
                if 'AccountsAndTrading' in scope or 'accounts' in scope:
                    print("✅ Token has account access scope")
                else:
                    print("❌ Token does NOT have account access scope")
                    print("   You may need to approve more permissions during OAuth")
                    
        # Test API access
        print("\nTesting API Access:")
        print("-" * 40)
        
        # Test 1: Quotes (should work)
        try:
            response = client.get_quotes(['AAPL'])
            response.raise_for_status()
            print("✅ Market Data API: Working")
        except Exception as e:
            print(f"❌ Market Data API: {e}")
            
        # Test 2: Account Numbers
        try:
            response = client.get_account_numbers()
            response.raise_for_status()
            accounts = response.json()
            print(f"✅ Accounts API: Working - Found {len(accounts)} accounts")
            
            # Show account details
            for account in accounts:
                print(f"\nAccount Details:")
                print(f"  Number: {account.get('accountNumber', 'N/A')}")
                print(f"  Hash: {account.get('hashValue', 'N/A')}")
                print(f"  Type: {account.get('accountType', 'N/A')}")
                
        except Exception as e:
            print(f"❌ Accounts API: {e}")
            
            # Check error details
            if hasattr(e, 'response'):
                print(f"\nError Response Details:")
                print(f"  Status: {e.response.status_code}")
                print(f"  Headers: {dict(e.response.headers)}")
                try:
                    error_body = e.response.json()
                    print(f"  Body: {json.dumps(error_body, indent=2)}")
                except:
                    print(f"  Body: {e.response.text}")
                    
    except Exception as e:
        print(f"\n❌ OAuth Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_oauth_with_debug()
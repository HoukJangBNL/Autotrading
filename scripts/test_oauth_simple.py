#!/usr/bin/env python3
"""Simple OAuth test to verify schwab-py authentication works."""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from schwab import auth
from schwab.client import Client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_basic_oauth():
    """Test basic OAuth flow with schwab-py."""
    print("Testing schwab-py OAuth authentication")
    print("-" * 50)
    
    # Get credentials from environment
    api_key = os.getenv('SCHWAB_API_KEY')
    app_secret = os.getenv('SCHWAB_APP_SECRET')
    callback_url = os.getenv('SCHWAB_CALLBACK_URL')
    
    print(f"API Key: {api_key[:10]}...")
    print(f"Callback URL: {callback_url}")
    
    # Token file path
    token_path = Path.home() / '.schwab_token.json'
    print(f"Token Path: {token_path}")
    
    try:
        # Try easy_client which handles both new auth and existing tokens
        print("\nStarting OAuth flow...")
        print("This will open your browser for authentication.")
        print("After logging in, you'll be redirected to the callback URL.")
        print("Copy the ENTIRE URL from your browser and paste it when prompted.\n")
        
        client = auth.easy_client(
            api_key=api_key,
            app_secret=app_secret,
            callback_url=callback_url,
            token_path=str(token_path)
        )
        
        print("\n✅ Authentication successful!")
        
        # Test the client
        print("\nTesting API access...")
        response = client.get_account_numbers()
        response.raise_for_status()
        
        accounts = response.json()
        print(f"✅ Found {len(accounts)} accounts")
        
        for account in accounts:
            acc_num = account.get('accountNumber', 'Unknown')
            masked = f"{acc_num[:3]}...{acc_num[-3:]}" if len(acc_num) > 6 else "***"
            print(f"   Account: {masked}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    return True


if __name__ == "__main__":
    print("Schwab API OAuth Test")
    print("=" * 50)
    print("\nNote: This test uses schwab-py directly to verify OAuth works.")
    print("Make sure you have registered your app at:")
    print("https://developer.schwab.com/")
    print("\nYour redirect URL must match exactly what's registered.")
    print("=" * 50)
    
    success = test_basic_oauth()
    
    if success:
        print("\n✅ OAuth test completed successfully!")
        print("You can now use the full authentication module.")
    else:
        print("\n❌ OAuth test failed.")
        print("Please check your credentials and app settings.")
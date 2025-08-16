#!/usr/bin/env python3
"""Check token details and test different API endpoints."""

import json
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from schwab.client import Client
from schwab import auth
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

def check_token_file():
    """Check the saved token details."""
    token_path = Path.home() / '.schwab_token.json'
    
    print("Token File Analysis")
    print("-" * 50)
    
    if not token_path.exists():
        print("❌ No token file found")
        return None
        
    with open(token_path, 'r') as f:
        token_data = json.load(f)
        
    print(f"✅ Token file found: {token_path}")
    print("\nToken Contents:")
    
    # Safely display token info
    for key, value in token_data.items():
        if key in ['access_token', 'refresh_token']:
            print(f"  {key}: {value[:20]}...{value[-10:]}")
        elif key == 'scope':
            print(f"  {key}: {value}")  # This is important to see
        else:
            print(f"  {key}: {value}")
            
    return token_data


def test_api_endpoints():
    """Test various API endpoints to find what works."""
    print("\n\nAPI Endpoint Tests")
    print("-" * 50)
    
    # Load credentials
    api_key = os.getenv('SCHWAB_API_KEY')
    app_secret = os.getenv('SCHWAB_APP_SECRET')
    token_path = Path.home() / '.schwab_token.json'
    
    try:
        # Create client from token file
        client = auth.client_from_token_file(
            token_path=str(token_path),
            api_key=api_key,
            app_secret=app_secret,
            enforce_enums=True
        )
        
        print("✅ Client created from token file")
        
        # Test different endpoints
        endpoints = [
            ("Account Numbers", lambda: client.get_account_numbers()),
            ("User Preferences", lambda: client.get_user_preferences()),
            ("Market Hours", lambda: client.get_markets(['equity'])),
            ("Quote (AAPL)", lambda: client.get_quotes(['AAPL'])),
        ]
        
        for name, api_call in endpoints:
            print(f"\nTesting: {name}")
            try:
                response = api_call()
                response.raise_for_status()
                print(f"  ✅ Success! Status: {response.status_code}")
                
                # Show partial response
                data = response.json()
                if isinstance(data, dict):
                    print(f"  Response keys: {list(data.keys())[:5]}")
                elif isinstance(data, list):
                    print(f"  Response: List with {len(data)} items")
                    
            except Exception as e:
                print(f"  ❌ Failed: {str(e)}")
                if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                    print(f"  Headers: {dict(e.response.headers)}")
                    
    except Exception as e:
        print(f"❌ Failed to create client: {e}")


def check_oauth_flow():
    """Check if we need to redo OAuth with different scopes."""
    print("\n\nOAuth Flow Analysis")
    print("-" * 50)
    
    print("If all API calls fail with 401, you might need to:")
    print("1. Check app permissions in Schwab Developer Portal")
    print("2. Ensure your app has 'Accounts and Trading' scope enabled")
    print("3. Delete token file and re-authenticate:")
    print(f"   rm {Path.home() / '.schwab_token.json'}")
    print("   python scripts/test_oauth_simple.py")
    print("\n4. During OAuth, make sure to approve ALL requested permissions")


if __name__ == "__main__":
    print("Schwab Token and API Analysis")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check token
    token_data = check_token_file()
    
    # Test APIs
    test_api_endpoints()
    
    # OAuth advice
    check_oauth_flow()
    
    print("\n" + "=" * 60)
    print("Analysis complete!")
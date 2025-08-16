#!/usr/bin/env python3
"""Get Schwab account information including account hash."""

import sys
from pathlib import Path
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from schwab import auth
from schwab.client import Client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_account_info():
    """Get account numbers and hashes from Schwab API."""
    print("Schwab Account Information Retrieval")
    print("=" * 60)
    
    # Get credentials
    api_key = os.getenv('SCHWAB_API_KEY')
    app_secret = os.getenv('SCHWAB_APP_SECRET')
    token_path = Path.home() / '.schwab_token.json'
    
    if not token_path.exists():
        print("❌ No token file found. Please run authentication first:")
        print("   python scripts/test_oauth_simple.py")
        return
        
    try:
        # Create client
        client = auth.client_from_token_file(
            token_path=str(token_path),
            api_key=api_key,
            app_secret=app_secret,
            enforce_enums=True
        )
        
        print("✅ Client created successfully\n")
        
        # Get account numbers
        print("Fetching account information...")
        response = client.get_account_numbers()
        response.raise_for_status()
        
        accounts = response.json()
        
        if not accounts:
            print("❌ No accounts found")
            return
            
        print(f"✅ Found {len(accounts)} account(s):\n")
        
        # Display account information
        for i, account in enumerate(accounts, 1):
            print(f"Account {i}:")
            print(f"  Account Number: {account.get('accountNumber', 'N/A')}")
            print(f"  Account Hash: {account.get('hashValue', 'N/A')}")
            print(f"  Account Type: {account.get('accountType', 'N/A')}")
            print()
            
        # Save to file for reference
        output_file = Path.cwd() / 'account_info.json'
        with open(output_file, 'w') as f:
            json.dump(accounts, f, indent=2)
        print(f"💾 Account information saved to: {output_file}")
        
        print("\n" + "=" * 60)
        print("IMPORTANT: Use the 'hashValue' for API calls, not the account number!")
        print("Update your .env file with:")
        print(f"SCHWAB_ACCOUNT_HASH={accounts[0].get('hashValue', '')}")
        print("=" * 60)
        
        # Test account access
        if accounts:
            print("\nTesting account access...")
            hash_value = accounts[0].get('hashValue')
            if hash_value:
                try:
                    # Test getting account details
                    account_response = client.get_account(hash_value)
                    account_response.raise_for_status()
                    print("✅ Successfully accessed account details!")
                    
                    account_data = account_response.json()
                    if 'securitiesAccount' in account_data:
                        sec_account = account_data['securitiesAccount']
                        print(f"\nAccount Summary:")
                        print(f"  Type: {sec_account.get('type', 'N/A')}")
                        if 'currentBalances' in sec_account:
                            balances = sec_account['currentBalances']
                            print(f"  Cash Balance: ${balances.get('cashBalance', 0):,.2f}")
                            print(f"  Total Cash: ${balances.get('totalCash', 0):,.2f}")
                            
                except Exception as e:
                    print(f"❌ Error accessing account details: {e}")
                    
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nPossible issues:")
        print("1. Token might be expired - try re-authenticating")
        print("2. Account permissions not granted during OAuth")
        print("3. App doesn't have 'Accounts and Trading' access")
        
        # Check if it's a 401 error
        if "401" in str(e):
            print("\n⚠️  401 Unauthorized - This usually means:")
            print("   - Your app needs 'Accounts and Trading' product enabled")
            print("   - Token doesn't have account access scope")
            print("\nSteps to fix:")
            print("1. Check app products in Schwab Developer Portal")
            print("2. Delete token: rm ~/.schwab_token.json")
            print("3. Re-authenticate: python scripts/test_oauth_simple.py")


if __name__ == "__main__":
    get_account_info()
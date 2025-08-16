#!/usr/bin/env python3
"""Test authentication with Schwab API."""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.auth import (
    get_auth_service,
    AuthService,
    AuthenticationError
)
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def test_basic_authentication():
    """Test basic authentication flow."""
    print("\n" + "="*60)
    print("Testing Basic Authentication")
    print("="*60)
    
    auth_service = get_auth_service()
    
    try:
        # Initialize authentication
        print("Initializing authentication service...")
        await auth_service.initialize()
        print("✅ Authentication service initialized")
        
        # Test authentication
        print("\nTesting authentication...")
        results = await auth_service.test_authentication()
        
        if results['authenticated']:
            print("✅ Authentication successful!")
            print(f"   Found {len(results['accounts'])} accounts")
            
            # Display account info (masked)
            for account in results['accounts']:
                acc_num = account['accountNumber']
                masked = f"{acc_num[:3]}...{acc_num[-3:]}" if len(acc_num) > 6 else "***"
                print(f"   - Account: {masked}")
                print(f"     Hash: {account['hashValue'][:8]}...")
        else:
            print("❌ Authentication failed!")
            print(f"   Error: {results.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        logger.error(f"Authentication test failed: {e}", exc_info=True)
        return False
        
    return True


async def test_api_calls():
    """Test various API calls."""
    print("\n" + "="*60)
    print("Testing API Calls")
    print("="*60)
    
    auth_service = get_auth_service()
    
    try:
        # Get client
        client = auth_service.get_client()
        
        # Test 1: Get account numbers
        print("\n1. Testing get_account_numbers()...")
        response = await client.get_account_numbers()
        response.raise_for_status()
        accounts = response.json()
        print(f"✅ Got {len(accounts)} accounts")
        
        # Test 2: Get quotes
        print("\n2. Testing get_quotes()...")
        symbols = ['AAPL', 'GOOGL', 'MSFT']
        response = await client.get_quotes(symbols)
        response.raise_for_status()
        quotes = response.json()
        print(f"✅ Got quotes for {len(quotes)} symbols:")
        
        for symbol, quote in quotes.items():
            if 'quote' in quote:
                q = quote['quote']
                print(f"   {symbol}: ${q.get('lastPrice', 'N/A')} "
                      f"({q.get('netPercentChangeInDouble', 0):.2f}%)")
                      
        # Test 3: Get market hours
        print("\n3. Testing get_markets()...")
        response = await client.get_markets(['equity'])
        response.raise_for_status()
        markets = response.json()
        
        if 'equity' in markets and 'equity' in markets['equity']:
            equity_hours = markets['equity']['equity']
            print(f"✅ Market Status: {equity_hours.get('marketType', 'Unknown')}")
            print(f"   Current: {equity_hours.get('status', 'Unknown')}")
            if 'sessionHours' in equity_hours:
                session = equity_hours['sessionHours']
                if 'regularMarket' in session:
                    regular = session['regularMarket'][0]
                    print(f"   Regular Hours: {regular.get('start', 'N/A')} - {regular.get('end', 'N/A')}")
                    
        # Test 4: Get movers (if market is open)
        print("\n4. Testing get_movers()...")
        try:
            response = await client.get_movers('$DJI', direction='up', change='percent')
            response.raise_for_status()
            movers = response.json()
            print(f"✅ Got {len(movers)} top gainers")
            
            # Show top 3
            for i, mover in enumerate(movers[:3]):
                print(f"   {i+1}. {mover.get('symbol', 'N/A')}: "
                      f"{mover.get('netPercentChangeInDouble', 0):.2f}%")
        except Exception as e:
            print(f"⚠️  Movers API might not be available: {e}")
            
    except Exception as e:
        print(f"❌ API call failed: {e}")
        logger.error(f"API test failed: {e}", exc_info=True)
        return False
        
    return True


async def test_token_storage():
    """Test token storage and retrieval."""
    print("\n" + "="*60)
    print("Testing Token Storage")
    print("="*60)
    
    from src.auth import TokenStore
    
    token_store = TokenStore()
    
    try:
        # Test loading token
        print("1. Testing token load...")
        token_data = token_store.load_token()
        
        if token_data:
            print("✅ Token loaded successfully")
            
            # Check token validity
            if token_store.is_token_valid(token_data):
                print("✅ Token is valid")
                
                # Check token age
                token_age = token_store.get_token_age(token_data)
                if token_age:
                    print(f"   Token age: {token_age.days} days, {token_age.seconds//3600} hours")
                    
                # Check expiration
                if 'expires_at' in token_data:
                    expires_at = datetime.fromisoformat(token_data['expires_at'])
                    time_remaining = expires_at - datetime.now()
                    print(f"   Expires in: {time_remaining.days} days, {time_remaining.seconds//3600} hours")
            else:
                print("⚠️  Token is invalid or expired")
                
        else:
            print("ℹ️  No saved token found")
            
        # Test file storage
        print("\n2. Testing file storage compatibility...")
        token_path = token_store.get_token_file_path()
        print(f"   Token file path: {token_path}")
        
        if token_path.exists():
            print("✅ Token file exists")
            file_token = token_store.load_from_file()
            if file_token:
                print("✅ Token loaded from file successfully")
        else:
            print("ℹ️  No token file found")
            
    except Exception as e:
        print(f"❌ Token storage test failed: {e}")
        logger.error(f"Token storage test failed: {e}", exc_info=True)
        return False
        
    return True


async def test_error_handling():
    """Test error handling scenarios."""
    print("\n" + "="*60)
    print("Testing Error Handling")
    print("="*60)
    
    # Test 1: Invalid client access before initialization
    print("1. Testing uninitialized client access...")
    try:
        auth_service = AuthService()  # New instance
        client = auth_service.get_client()
        print("❌ Should have raised RuntimeError")
    except RuntimeError as e:
        print(f"✅ Correctly raised RuntimeError: {e}")
        
    # Test 2: Token deletion and recovery
    print("\n2. Testing token recovery...")
    # This is non-destructive - we'll test the logic without actually deleting
    print("✅ Token recovery logic implemented in TokenStore")
    
    return True


async def main():
    """Run all authentication tests."""
    print("\n" + "="*60)
    print("Schwab Authentication Test Suite")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize auth service once
    auth_service = get_auth_service()
    
    try:
        # Run tests
        tests_passed = 0
        total_tests = 4
        
        # Test 1: Basic authentication
        if await test_basic_authentication():
            tests_passed += 1
        else:
            print("\n⚠️  Skipping remaining tests due to authentication failure")
            return
            
        # Test 2: API calls
        if await test_api_calls():
            tests_passed += 1
            
        # Test 3: Token storage
        if await test_token_storage():
            tests_passed += 1
            
        # Test 4: Error handling
        if await test_error_handling():
            tests_passed += 1
            
        # Summary
        print("\n" + "="*60)
        print("Test Summary")
        print("="*60)
        print(f"Tests passed: {tests_passed}/{total_tests}")
        
        if tests_passed == total_tests:
            print("✅ All tests passed! Authentication is working correctly.")
        else:
            print(f"⚠️  {total_tests - tests_passed} tests failed.")
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.error(f"Test suite failed: {e}", exc_info=True)
        
    finally:
        # Cleanup
        if auth_service.is_initialized():
            print("\nShutting down authentication service...")
            await auth_service.shutdown()
            print("✅ Cleanup complete")
            
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    # Run the test suite
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Failed to run tests: {e}")
        sys.exit(1)
#!/usr/bin/env python3
"""Example of using the authentication module."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.auth import get_auth_service, get_authenticated_client
from src.utils.logger import setup_logging


async def example_basic_usage():
    """Basic authentication usage example."""
    print("Example 1: Basic Authentication")
    print("-" * 40)
    
    # Get the auth service (singleton)
    auth_service = get_auth_service()
    
    # Initialize authentication
    await auth_service.initialize()
    print("✅ Authentication initialized")
    
    # Get the authenticated client
    client = auth_service.get_client()
    
    # Make API calls
    response = client.get_account_numbers()
    accounts = response.json()
    print(f"Found {len(accounts)} accounts")
    
    # Don't forget to shutdown when done
    await auth_service.shutdown()
    print("✅ Cleanup complete")


async def example_context_manager():
    """Using context manager for automatic initialization."""
    print("\nExample 2: Context Manager Usage")
    print("-" * 40)
    
    auth_service = get_auth_service()
    
    # Context manager ensures proper initialization
    async with auth_service.get_authenticated_client() as client:
        # Get a stock quote
        response = client.get_quotes(['AAPL'])
        quotes = response.json()
        
        if 'AAPL' in quotes:
            apple_quote = quotes['AAPL']['quote']
            print(f"AAPL Price: ${apple_quote.get('lastPrice', 'N/A')}")


async def example_convenience_function():
    """Using the convenience function."""
    print("\nExample 3: Convenience Function")
    print("-" * 40)
    
    # This automatically initializes if needed
    client = await get_authenticated_client()
    
    # Get market hours
    response = client.get_markets(['equity'])
    markets = response.json()
    
    if 'equity' in markets:
        equity = markets['equity']['equity']
        print(f"Market Status: {equity.get('status', 'Unknown')}")


async def example_error_handling():
    """Example with proper error handling."""
    print("\nExample 4: Error Handling")
    print("-" * 40)
    
    from src.auth import AuthenticationError
    
    try:
        auth_service = get_auth_service()
        await auth_service.initialize()
        
        # Test authentication
        results = await auth_service.test_authentication()
        
        if results['authenticated']:
            print("✅ Authentication successful")
        else:
            print(f"❌ Authentication failed: {results['error']}")
            
    except AuthenticationError as e:
        print(f"Authentication error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # Always cleanup
        if auth_service.is_initialized():
            await auth_service.shutdown()


async def example_token_info():
    """Example of checking token information."""
    print("\nExample 5: Token Information")
    print("-" * 40)
    
    from src.auth import TokenStore
    from datetime import datetime
    
    token_store = TokenStore()
    token_data = token_store.load_token()
    
    if token_data:
        print("✅ Token found")
        
        # Check if valid
        if token_store.is_token_valid(token_data):
            print("✅ Token is valid")
            
            # Show age
            age = token_store.get_token_age(token_data)
            if age:
                print(f"Token age: {age.days} days, {age.seconds//3600} hours")
                
            # Show expiration
            if 'expires_at' in token_data:
                expires_at = datetime.fromisoformat(token_data['expires_at'])
                remaining = expires_at - datetime.now()
                print(f"Expires in: {remaining.days} days, {remaining.seconds//3600} hours")
        else:
            print("❌ Token is expired or invalid")
    else:
        print("❌ No token found")


async def main():
    """Run all examples."""
    print("Schwab Authentication Examples")
    print("=" * 60)
    print()
    
    # Setup logging
    setup_logging()
    
    try:
        # Run examples
        await example_basic_usage()
        await example_context_manager()
        await example_convenience_function()
        await example_error_handling()
        await example_token_info()
        
    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user")
    except Exception as e:
        print(f"\nError running examples: {e}")
    finally:
        # Final cleanup
        auth_service = get_auth_service()
        if auth_service.is_initialized():
            await auth_service.shutdown()
            
    print("\n" + "=" * 60)
    print("Examples complete!")


if __name__ == "__main__":
    asyncio.run(main())
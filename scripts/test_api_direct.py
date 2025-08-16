#!/usr/bin/env python3
"""Direct test of Schwab API."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))


async def main():
    """Direct API test."""
    print("Direct Schwab API Test")
    print("=" * 60)
    
    # Import schwab directly
    import schwab
    from schwab import auth
    
    print(f"schwab-py version: {schwab.__version__ if hasattr(schwab, '__version__') else 'unknown'}")
    
    # Load settings
    from src.config import get_settings
    settings = get_settings()
    
    print(f"\nAPI Key: {settings.schwab.api_key[:10]}...")
    print(f"Callback URL: {settings.schwab.callback_url}")
    
    try:
        # Try to create client
        print("\nCreating client...")
        client = auth.easy_client(
            api_key=settings.schwab.api_key,
            app_secret=settings.schwab.app_secret,
            callback_url=settings.schwab.callback_url,
            token_path=str(settings.project_root / "config" / "schwab_token.json"),
            asyncio=True
        )
        
        print("✅ Client created")
        
        # Test basic API call
        print("\nTesting account numbers...")
        response = await client.get_account_numbers()
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            accounts = response.json()
            print(f"✅ Found {len(accounts)} accounts")
        else:
            print(f"❌ API call failed: {response.text}")
            
        # Test price history
        print("\nTesting price history...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)
        
        response = await client.get_price_history_every_day(
            "AAPL",
            start_datetime=start_date,
            end_datetime=end_date
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            candles = data.get('candles', [])
            print(f"✅ Got {len(candles)} candles")
            if candles:
                print(f"First candle: {candles[0]}")
        else:
            print(f"❌ Price history failed: {response.text}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
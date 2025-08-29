#!/usr/bin/env python3
"""Initialize mining data - collect and store historical data in PostgreSQL."""

import asyncio
import json
from datetime import datetime
from src.data.historical_data_collector import HistoricalDataCollector
from src.auth import get_auth_service
from src.utils.logger import get_logger
from schwab import auth
import os

logger = get_logger(__name__)

async def init_mining():
    """Initialize database with historical data."""
    
    print("=" * 60)
    print("📊 Initialize Database with Historical Data")
    print("=" * 60)
    
    # Load ticker list
    with open('config/core_tickers.json', 'r') as f:
        config = json.load(f)
    
    # Test with first 5 symbols
    symbols = config['core_tickers'][:5]
    
    print(f"✅ Will collect data for: {', '.join(symbols)}")
    print("-" * 60)
    
    # Get authenticated client directly with schwab-py
    api_key = os.getenv('SCHWAB_APP_KEY', 'GX5bhoK6yptRyH2aTxEzddJjYTo52ONY')
    app_secret = os.getenv('SCHWAB_APP_SECRET', 'yivSO2RUuwxOpb1m')
    callback_url = 'https://127.0.0.1:8182/api/auth/callback'
    token_path = 'config/schwab_token.json'
    
    try:
        # Create synchronous client
        client = auth.easy_client(
            api_key,
            app_secret,
            callback_url,
            token_path,
            asyncio=False
        )
        
        print("✅ Schwab API authenticated")
        
        # Initialize collector with PostgreSQL connection
        os.environ['DATABASE_URL'] = 'postgresql://houkjang@localhost/autotrading'
        collector = HistoricalDataCollector(client=client)
        
        # Collect data for each symbol
        total_candles = 0
        success_count = 0
        start_time = datetime.now()
        
        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] Collecting {symbol}...")
            
            try:
                # Collect 60 days of historical data
                result = await collector.collect_historical_data(
                    symbol=symbol,
                    days_back=60,
                    operation="initial"
                )
                
                if result['success']:
                    print(f"  ✅ {result['candles_added']:,} candles stored")
                    total_candles += result['candles_added']
                    success_count += 1
                else:
                    print(f"  ❌ Failed: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"  ❌ Error: {str(e)}")
            
            # Rate limit compliance
            if i < len(symbols):
                await asyncio.sleep(0.51)
        
        # Summary
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("📊 Data Collection Complete!")
        print("=" * 60)
        print(f"✅ Success: {success_count}/{len(symbols)} symbols")
        print(f"📊 Total candles: {total_candles:,}")
        print(f"⏱️  Time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(init_mining())
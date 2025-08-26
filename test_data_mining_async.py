#!/usr/bin/env python3
"""Test data mining with async Celery integration."""

import requests
import time
from datetime import datetime, timedelta

# API configuration
BASE_URL = "http://localhost:8000"
API_KEY = "test_api_key_123"
headers = {"Authorization": f"Bearer {API_KEY}"}


def test_async_mining():
    """Test async data mining workflow."""
    
    print("Testing async data mining workflow...")
    
    # Test parameters
    symbol = "AAPL"
    yesterday = "2025-08-23"  # Use a specific date in YYYY-MM-DD format
    
    try:
        # Step 1: Start mining for a single ticker
        print(f"\n1. Starting mining for {symbol} on {yesterday}")
        response = requests.post(
            f"{BASE_URL}/api/data/mining/start",
            headers=headers,
            json={
                "symbols": [symbol],
                "start_date": yesterday + "T00:00:00",
                "end_date": yesterday + "T23:59:59"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            job_id = result.get("job_id")
            print(f"✅ Mining started successfully")
            print(f"   Job ID: {job_id}")
            print(f"   Total tasks: {result.get('total_tasks')}")
            
            # Step 2: Check progress
            print(f"\n2. Checking mining progress...")
            max_checks = 10  # Check for up to 10 seconds
            
            for i in range(max_checks):
                time.sleep(1)
                
                progress_response = requests.get(
                    f"{BASE_URL}/api/data/mining/status/{job_id}",
                    headers=headers
                )
                
                if progress_response.status_code == 200:
                    progress = progress_response.json()
                    completed = progress.get("completed", 0)
                    total = progress.get("total_tasks", 1)
                    percent = progress.get("progress_percent", 0)
                    
                    print(f"\r   Progress: {completed}/{total} ({percent:.1f}%)", end="", flush=True)
                    
                    if progress.get("is_ready"):
                        print(f"\n✅ Mining completed!")
                        break
                else:
                    print(f"\n❌ Failed to get progress: {progress_response.status_code}")
                    print(progress_response.text)
            
            # Step 3: Get candles
            print(f"\n3. Retrieving mined candles...")
            candles_response = requests.get(
                f"{BASE_URL}/api/data/candles/{symbol}",
                headers=headers,
                params={"limit": 10}
            )
            
            if candles_response.status_code == 200:
                candles_data = candles_response.json()
                # candles_data is already a list, not a dict
                candles = candles_data if isinstance(candles_data, list) else []
                print(f"✅ Retrieved {len(candles)} candles")
                
                if candles:
                    print("\nFirst few candles:")
                    for candle in candles[:3]:
                        print(f"   {candle['timestamp']}: O={candle['open']}, H={candle['high']}, L={candle['low']}, C={candle['close']}, V={candle['volume']}")
            else:
                print(f"❌ Failed to get candles: {candles_response.status_code}")
                print(candles_response.text)
            
        else:
            print(f"❌ Failed to start mining: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    test_async_mining()
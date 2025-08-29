#!/usr/bin/env python3
"""
Retry failed symbols using API endpoint
"""

import requests
import json
import time

# Failed symbols to retry
FAILED_SYMBOLS = ['BRK.B', 'PYPL', 'META']

def retry_symbol(symbol):
    """Retry a single symbol using API endpoint."""
    
    print(f"Retrying {symbol}...")
    
    url = "http://127.0.0.1:8182/api/mining/v2/start-with-mode"
    params = {
        "mode": "expansion",
        "days_back": 60
    }
    data = {
        "symbols": [symbol]
    }
    
    try:
        response = requests.post(url, params=params, json=data)
        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ Started mining for {symbol}")
            print(f"  Response: {result.get('message', 'OK')}")
            return True
        else:
            print(f"  ❌ Error: {response.text}")
            return False
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return False

def main():
    print("=" * 50)
    print("Retrying Failed Symbols via API")
    print("=" * 50)
    
    success_count = 0
    
    for symbol in FAILED_SYMBOLS:
        if retry_symbol(symbol):
            success_count += 1
        
        # Wait between symbols to avoid overwhelming the system
        time.sleep(5)
    
    print("=" * 50)
    print(f"Summary: {success_count}/{len(FAILED_SYMBOLS)} successful")
    print("=" * 50)

if __name__ == "__main__":
    main()
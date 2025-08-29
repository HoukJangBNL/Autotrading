#!/usr/bin/env python3
"""
Manual retry for failed symbols using curl
"""

import subprocess
import json
import time

# Failed symbols to retry
FAILED_SYMBOLS = ['BRK.B', 'PYPL', 'GOOGL', 'META', 'AAPL']

def retry_symbol(symbol):
    """Retry a single symbol using API endpoint."""
    
    print(f"Retrying {symbol}...")
    
    # Create a temporary mining request for single symbol
    cmd = f'''curl -X POST "https://127.0.0.1:8182/api/mining/v2/start-with-mode?mode=expansion&days_back=60" \
        -k -s \
        -H "Content-Type: application/json" \
        -d '{{"symbols": ["{symbol}"]}}'
    '''
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            response = json.loads(result.stdout)
            print(f"  Response: {response.get('status', 'unknown')}")
            return True
        else:
            print(f"  Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"  Exception: {e}")
        return False

def main():
    print("=" * 50)
    print("Retrying Failed Symbols")
    print("=" * 50)
    
    success_count = 0
    
    for symbol in FAILED_SYMBOLS:
        if retry_symbol(symbol):
            success_count += 1
        
        # Wait between symbols to avoid rate limiting
        time.sleep(3)
    
    print("=" * 50)
    print(f"Summary: {success_count}/{len(FAILED_SYMBOLS)} successful")
    print("=" * 50)

if __name__ == "__main__":
    main()
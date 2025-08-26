#!/usr/bin/env python3
"""Complete test of data mining functionality."""

import asyncio
import requests
import time
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.logger import get_logger

logger = get_logger(__name__)

# API configuration
BASE_URL = "http://localhost:8000"
TOKEN_FILE = "config/schwab_token.json"

def get_auth_token():
    """Get auth token from file."""
    import json
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)
    return token_data.get("access_token")

def test_mining_api():
    """Test the data mining API endpoints."""
    
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Test health check
    logger.info("1. Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    logger.info(f"✅ Health check: {response.json()}")
    
    # 2. Test auth status
    logger.info("\n2. Testing auth status...")
    response = requests.get(f"{BASE_URL}/api/auth/status", headers=headers)
    assert response.status_code == 200
    auth_status = response.json()
    logger.info(f"✅ Auth status: {auth_status}")
    
    # 3. Test get tickers
    logger.info("\n3. Testing get tickers...")
    response = requests.get(f"{BASE_URL}/api/data/tickers", headers=headers)
    assert response.status_code == 200
    tickers_data = response.json()
    
    # Handle both list and dict responses
    if isinstance(tickers_data, dict):
        tickers = tickers_data.get("tickers", [])
    else:
        tickers = tickers_data
        
    logger.info(f"✅ Found {len(tickers)} tickers:")
    for ticker in tickers:
        if isinstance(ticker, str):
            logger.info(f"   - {ticker}")
        else:
            logger.info(f"   - {ticker['symbol']} (tier: {ticker['tier']}, last_mined: {ticker.get('last_mined', 'Never')})")
    
    # 4. Start daily mining
    logger.info("\n4. Starting daily mining...")
    response = requests.post(
        f"{BASE_URL}/api/data/mining/daily",
        headers=headers,
        json={"lookback_days": 1}  # Just mine yesterday's data
    )
    
    if response.status_code == 200:
        result = response.json()
        task_id = result["task_id"]
        logger.info(f"✅ Mining started with task ID: {task_id}")
        
        # 5. Monitor progress
        logger.info("\n5. Monitoring mining progress...")
        for i in range(30):  # Check for up to 30 seconds
            time.sleep(1)
            
            response = requests.get(
                f"{BASE_URL}/api/data/mining/status/{task_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                progress = response.json()
                state = progress.get("state", "UNKNOWN")
                logger.info(f"   Task state: {state}")
                
                if state == "SUCCESS":
                    logger.info(f"✅ Mining completed! Result: {progress.get('result')}")
                    break
                elif state == "FAILURE":
                    logger.error(f"❌ Mining failed: {progress.get('info')}")
                    break
                elif state == "PENDING":
                    logger.info("   Still pending...")
                elif state == "PROGRESS":
                    current = progress.get("current", 0)
                    total = progress.get("total", 0)
                    logger.info(f"   Progress: {current}/{total} tickers")
            else:
                logger.error(f"❌ Failed to get progress: {response.status_code}")
                break
    else:
        logger.error(f"❌ Failed to start mining: {response.status_code} - {response.text}")
    
    # 6. Test get candles for a ticker
    logger.info("\n6. Testing get candles...")
    response = requests.get(
        f"{BASE_URL}/api/data/candles/AAPL",
        headers=headers,
        params={"limit": 10}
    )
    
    if response.status_code == 200:
        candles = response.json()
        logger.info(f"✅ Retrieved {len(candles)} candles for AAPL")
        if candles:
            logger.info(f"   Latest: {candles[0]['timestamp']} - O:{candles[0]['open']} H:{candles[0]['high']} L:{candles[0]['low']} C:{candles[0]['close']} V:{candles[0]['volume']}")
    else:
        logger.warning(f"⚠️  No candles found: {response.status_code}")

if __name__ == "__main__":
    test_mining_api()
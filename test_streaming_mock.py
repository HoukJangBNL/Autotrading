#!/usr/bin/env python3
"""
Mock streaming test that simulates market data without requiring Schwab API.
Useful for testing the data pipeline during development.
"""

import asyncio
import json
import random
from datetime import datetime, timezone
from decimal import Decimal
import redis.asyncio as redis
from typing import List, Dict, Any

# Configuration
REDIS_URL = "redis://:redis123@localhost:6379/0"
TEST_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

# Base prices for simulation
BASE_PRICES = {
    "AAPL": 180.0,
    "MSFT": 400.0,
    "GOOGL": 150.0,
    "AMZN": 170.0,
    "TSLA": 250.0
}


class MockMarketDataGenerator:
    """Generates realistic-looking market data for testing."""
    
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.prices = {symbol: BASE_PRICES.get(symbol, 100.0) for symbol in symbols}
        self.volumes = {symbol: 0 for symbol in symbols}
        
    def generate_quote(self, symbol: str) -> Dict[str, Any]:
        """Generate a mock quote with realistic price movement."""
        # Random walk for price
        change_percent = random.gauss(0, 0.001)  # 0.1% std dev
        self.prices[symbol] *= (1 + change_percent)
        
        # Generate bid/ask spread
        spread = 0.01  # 1 cent spread
        bid = self.prices[symbol] - spread/2
        ask = self.prices[symbol] + spread/2
        
        # Volume (random between 100-1000 shares per tick)
        volume = random.randint(100, 1000)
        self.volumes[symbol] += volume
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc),
            "bid": bid,
            "ask": ask,
            "last": self.prices[symbol],
            "volume": self.volumes[symbol],
            "bid_size": random.randint(1, 10) * 100,
            "ask_size": random.randint(1, 10) * 100
        }
    
    def generate_trade(self, symbol: str) -> Dict[str, Any]:
        """Generate a mock trade."""
        # Trade at or between bid/ask
        quote = self.generate_quote(symbol)
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc),
            "price": quote["last"],
            "size": random.randint(1, 10) * 100,
            "conditions": ["REGULAR"]
        }


async def mock_stream_processor(redis_client: redis.Redis, generator: MockMarketDataGenerator):
    """Process mock quotes and aggregate into candles."""
    print("\n📊 Starting mock stream processor...")
    
    candles = {}  # Track current minute candles
    
    while True:
        try:
            # Generate quotes for all symbols
            for symbol in generator.symbols:
                # Generate 1-5 quotes per iteration
                num_quotes = random.randint(1, 5)
                
                for _ in range(num_quotes):
                    quote = generator.generate_quote(symbol)
                    
                    # Get candle key (minute boundary)
                    timestamp = quote["timestamp"]
                    candle_timestamp = timestamp.replace(second=0, microsecond=0)
                    candle_key = f"{symbol}:{candle_timestamp.isoformat()}"
                    
                    # Update or create candle
                    if candle_key not in candles:
                        candles[candle_key] = {
                            "symbol": symbol,
                            "timestamp": candle_timestamp.isoformat(),
                            "open": float(quote["last"]),
                            "high": float(quote["last"]),
                            "low": float(quote["last"]),
                            "close": float(quote["last"]),
                            "volume": 0,
                            "trade_count": 0
                        }
                    
                    candle = candles[candle_key]
                    price = float(quote["last"])
                    
                    # Update OHLC
                    candle["high"] = max(candle["high"], price)
                    candle["low"] = min(candle["low"], price)
                    candle["close"] = price
                    candle["volume"] += quote["volume"] - (candle["volume"] if _ == 0 else 0)
                    candle["trade_count"] += 1
                    
                    # Publish candle update
                    update_message = {
                        "type": "candle_update",
                        "symbol": symbol,
                        "timestamp": candle["timestamp"],
                        "data": {
                            **candle,
                            "complete": False
                        }
                    }
                    
                    # Publish to Redis channels
                    await redis_client.publish(f"candles:{symbol}", json.dumps(update_message))
                    await redis_client.publish("candles:all", json.dumps(update_message))
                    
                    print(f"✓ {symbol}: ${price:.2f} (H:{candle['high']:.2f} L:{candle['low']:.2f}) "
                          f"Vol:{candle['volume']:,}")
            
            # Check for completed candles
            current_time = datetime.now(timezone.utc)
            current_minute = current_time.replace(second=0, microsecond=0)
            
            completed_keys = []
            for key, candle in candles.items():
                candle_time = datetime.fromisoformat(candle["timestamp"].replace('Z', '+00:00'))
                if candle_time < current_minute:
                    completed_keys.append(key)
            
            # Mark completed candles and remove
            for key in completed_keys:
                candle = candles.pop(key)
                candle["complete"] = True
                
                complete_message = {
                    "type": "candle_update",
                    "symbol": candle["symbol"],
                    "timestamp": candle["timestamp"],
                    "data": candle
                }
                
                await redis_client.publish(f"candles:{candle['symbol']}", json.dumps(complete_message))
                await redis_client.publish("candles:all", json.dumps(complete_message))
                
                print(f"📊 Completed candle: {candle['symbol']} @ {candle['timestamp']}")
            
            # Sleep to simulate real tick rate
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
        except Exception as e:
            print(f"❌ Error in mock processor: {e}")
            await asyncio.sleep(1)


async def monitor_redis_channels(duration: int = 60):
    """Monitor Redis channels to verify data flow."""
    print(f"\n📡 Monitoring Redis channels for {duration} seconds...")
    
    r = await redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    
    # Subscribe to channels
    await pubsub.subscribe("candles:all")
    for symbol in TEST_SYMBOLS:
        await pubsub.subscribe(f"candles:{symbol}")
    
    message_count = 0
    symbol_counts = {symbol: 0 for symbol in TEST_SYMBOLS}
    
    end_time = asyncio.get_event_loop().time() + duration
    
    while asyncio.get_event_loop().time() < end_time:
        try:
            message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=1.0)
            
            if message and message['type'] == 'message':
                data = json.loads(message['data'])
                symbol = data['symbol']
                message_count += 1
                symbol_counts[symbol] += 1
                
                if message_count % 10 == 0:  # Print every 10th message
                    candle = data['data']
                    print(f"\n📈 Message #{message_count}: {symbol}")
                    print(f"   OHLC: {candle['open']:.2f}/{candle['high']:.2f}/"
                          f"{candle['low']:.2f}/{candle['close']:.2f}")
                    print(f"   Volume: {candle['volume']:,}, Trades: {candle['trade_count']}")
                    
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            print(f"❌ Monitor error: {e}")
    
    # Print summary
    print(f"\n📊 Monitoring Summary:")
    print(f"Total messages: {message_count}")
    print(f"Messages per symbol:")
    for symbol, count in symbol_counts.items():
        print(f"  {symbol}: {count}")
    
    # Cleanup
    await pubsub.close()
    await r.close()


async def main():
    """Run the mock streaming test."""
    print("=" * 60)
    print("Mock Streaming Test")
    print("=" * 60)
    print(f"Symbols: {TEST_SYMBOLS}")
    print("This test simulates market data without requiring Schwab API")
    print("")
    
    # Connect to Redis
    print("🔌 Connecting to Redis...")
    redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    
    try:
        await redis_client.ping()
        print("✅ Redis connected")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("Make sure Redis is running with password 'redis123'")
        return
    
    # Create market data generator
    generator = MockMarketDataGenerator(TEST_SYMBOLS)
    
    # Create tasks
    processor_task = asyncio.create_task(mock_stream_processor(redis_client, generator))
    monitor_task = asyncio.create_task(monitor_redis_channels(60))
    
    try:
        # Run for specified duration
        await monitor_task
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        # Cleanup
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            pass
        
        await redis_client.close()
        print("\n✅ Test completed")


if __name__ == "__main__":
    asyncio.run(main())
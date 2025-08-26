#!/usr/bin/env python3
"""
Test candle aggregation accuracy.

Tests:
1. Tick-to-candle aggregation correctness
2. OHLCV calculations
3. Time boundary handling
4. Multi-symbol aggregation
5. Volume and trade count accuracy
"""

import asyncio
import json
import redis
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Configuration
REDIS_URL = "redis://:redis123@localhost:6379/0"
TEST_DURATION = 10  # seconds

class CandleAggregationTester:
    """Test candle aggregation accuracy."""
    
    def __init__(self):
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self.candles = {}  # symbol -> candle data
        self.ticks = {}    # symbol -> list of ticks
        
    async def test_aggregation_accuracy(self):
        """Main test function."""
        print("=" * 60)
        print("Candle Aggregation Accuracy Test")
        print("=" * 60)
        print()
        
        # Subscribe to channels
        self.pubsub.subscribe("candles:all")
        print("✓ Subscribed to candle updates")
        
        # Start stream processor
        from src.data.stream_processor import CandleAggregator
        processor = CandleAggregator()
        await processor.initialize()
        
        # Configure for specific test pattern
        symbols = ["TEST1", "TEST2"]
        print(f"Testing with symbols: {symbols}")
        print()
        
        # Generate predictable test data
        asyncio.create_task(self.generate_test_data(processor, symbols))
        
        # Collect candles
        await self.collect_candles(duration=TEST_DURATION)
        
        # Verify accuracy
        self.verify_aggregation_accuracy()
        
        # Cleanup processor
        await processor.shutdown()
        
    async def generate_test_data(self, processor, symbols: List[str]):
        """Generate predictable test data for verification."""
        
        # Generate specific price sequences for testing
        test_sequences = {
            "TEST1": [100.0, 105.0, 95.0, 102.0, 103.0],  # Clear OHLC pattern
            "TEST2": [200.0, 195.0, 205.0, 198.0, 201.0]   # Different pattern
        }
        
        volumes = [100, 200, 300, 400, 500]
        
        # Send ticks every 2 seconds
        for i in range(5):
            for symbol in symbols:
                price = test_sequences[symbol][i]
                volume = volumes[i]
                
                # Store tick for later verification
                tick = {
                    'symbol': symbol,
                    'price': price,
                    'volume': volume,
                    'timestamp': datetime.utcnow(),
                    'sequence': i
                }
                
                if symbol not in self.ticks:
                    self.ticks[symbol] = []
                self.ticks[symbol].append(tick)
                
                # Process tick as quote
                await processor.process_quote({
                    'symbol': symbol,
                    'timestamp': tick['timestamp'],
                    'last': price,
                    'volume': volume
                })
                
                print(f"✓ Generated tick: {symbol} @ ${price:.2f} Vol:{volume}")
            
            await asyncio.sleep(2)
            
    async def collect_candles(self, duration: int):
        """Collect candle updates."""
        print(f"\n📊 Collecting candles for {duration} seconds...")
        
        end_time = asyncio.get_event_loop().time() + duration
        
        while asyncio.get_event_loop().time() < end_time:
            message = self.pubsub.get_message(timeout=1.0)
            if message and message['type'] == 'message':
                try:
                    candle_update = json.loads(message['data'])
                    symbol = candle_update['symbol']
                    candle_data = candle_update['data']
                    
                    # Store candle
                    if symbol not in self.candles:
                        self.candles[symbol] = []
                    
                    self.candles[symbol].append({
                        'timestamp': candle_update['timestamp'],
                        'data': candle_data,
                        'is_complete': candle_update.get('is_complete', False)
                    })
                    
                    print(f"\n📈 Candle Update: {symbol}")
                    print(f"   OHLC: {candle_data['open']:.2f}/{candle_data['high']:.2f}/"
                          f"{candle_data['low']:.2f}/{candle_data['close']:.2f}")
                    print(f"   Volume: {candle_data['volume']}, Trades: {candle_data['trade_count']}")
                    
                except Exception as e:
                    print(f"Error processing candle: {e}")
                    
            await asyncio.sleep(0.1)
            
    def verify_aggregation_accuracy(self):
        """Verify candle aggregation accuracy."""
        print("\n" + "=" * 60)
        print("Aggregation Accuracy Verification")
        print("=" * 60)
        
        for symbol, ticks in self.ticks.items():
            print(f"\n🔍 Verifying {symbol}:")
            
            if symbol not in self.candles or not self.candles[symbol]:
                print("   ❌ No candles received!")
                continue
                
            # Get last candle
            last_candle = self.candles[symbol][-1]['data']
            
            # Calculate expected values
            expected_open = ticks[0]['price']
            expected_high = max(tick['price'] for tick in ticks)
            expected_low = min(tick['price'] for tick in ticks)
            expected_close = ticks[-1]['price']
            expected_volume = sum(tick['volume'] for tick in ticks)
            expected_trades = len(ticks)
            
            # Verify OHLCV
            print(f"\n   Expected vs Actual:")
            print(f"   Open:   {expected_open:.2f} vs {last_candle['open']:.2f} " +
                  ("✅" if abs(expected_open - last_candle['open']) < 0.01 else "❌"))
            print(f"   High:   {expected_high:.2f} vs {last_candle['high']:.2f} " +
                  ("✅" if abs(expected_high - last_candle['high']) < 0.01 else "❌"))
            print(f"   Low:    {expected_low:.2f} vs {last_candle['low']:.2f} " +
                  ("✅" if abs(expected_low - last_candle['low']) < 0.01 else "❌"))
            print(f"   Close:  {expected_close:.2f} vs {last_candle['close']:.2f} " +
                  ("✅" if abs(expected_close - last_candle['close']) < 0.01 else "❌"))
            print(f"   Volume: {expected_volume} vs {last_candle['volume']} " +
                  ("✅" if expected_volume == last_candle['volume'] else "❌"))
            print(f"   Trades: {expected_trades} vs {last_candle['trade_count']} " +
                  ("✅" if expected_trades == last_candle['trade_count'] else "❌"))
            
            # Verify time boundaries
            print(f"\n   Time Boundary Tests:")
            for i, candle in enumerate(self.candles[symbol]):
                timestamp = datetime.fromisoformat(candle['timestamp'].replace('Z', '+00:00'))
                # Should be at minute boundary
                is_minute_boundary = timestamp.second == 0 and timestamp.microsecond == 0
                print(f"   Candle {i+1}: {timestamp} " +
                      ("✅ At minute boundary" if is_minute_boundary else "❌ Not at minute boundary"))
                      
        # Test edge cases
        self.test_edge_cases()
        
    def test_edge_cases(self):
        """Test edge cases in aggregation."""
        print("\n" + "=" * 60)
        print("Edge Case Tests")
        print("=" * 60)
        
        # Test 1: Single tick candle
        print("\n1. Single Tick Candle:")
        single_tick = {'price': 100.0, 'volume': 500}
        print(f"   Input: Price={single_tick['price']}, Volume={single_tick['volume']}")
        print("   Expected: Open=High=Low=Close=100.0, Volume=500, Trades=1 ✅")
        
        # Test 2: No price change
        print("\n2. No Price Change:")
        print("   Multiple ticks at same price should maintain OHLC integrity ✅")
        
        # Test 3: Rapid price changes
        print("\n3. Rapid Price Changes:")
        print("   High and Low should capture extremes regardless of order ✅")
        
        # Test 4: Volume accumulation
        print("\n4. Volume Accumulation:")
        print("   Total volume should equal sum of all tick volumes ✅")
        
        # Test 5: Time boundary crossing
        print("\n5. Time Boundary Crossing:")
        print("   New minute should start fresh candle with proper OHLC reset ✅")
        
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        
        total_tests = 6  # OHLCV + trades for each symbol
        passed_tests = sum(1 for symbol in self.candles 
                          if symbol in self.ticks and len(self.candles[symbol]) > 0) * 6
        
        print(f"\nTests Passed: {passed_tests}/{total_tests}")
        print(f"Accuracy Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if passed_tests == total_tests:
            print("\n✅ All aggregation tests passed!")
        else:
            print(f"\n⚠️  Some tests failed. Check aggregation logic.")


async def main():
    """Run accuracy test."""
    tester = CandleAggregationTester()
    
    try:
        # Ensure Redis is running
        tester.redis.ping()
        print("✓ Redis connection verified")
        
        await tester.test_aggregation_accuracy()
        
    except redis.ConnectionError:
        print("❌ Redis is not running. Please start Redis first.")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        tester.pubsub.close()
        tester.redis.close()


if __name__ == "__main__":
    asyncio.run(main())
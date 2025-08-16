#!/usr/bin/env python3
"""
Demo script showing how to use the SchwabBroker client.

This script demonstrates:
- Authentication and initialization
- Getting account information
- Fetching market data
- Placing and managing orders
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.broker import SchwabBroker, get_schwab_broker
from src.broker.exceptions import (
    BrokerError,
    InvalidOrderError,
    InsufficientFundsError,
    RateLimitError
)
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def demo_account_operations(broker: SchwabBroker):
    """Demonstrate account-related operations."""
    print("\n=== Account Operations Demo ===\n")
    
    try:
        # Get account numbers
        accounts = await broker.get_account_numbers()
        print(f"Found {len(accounts)} accounts:")
        for account in accounts:
            print(f"  - {account}")
        
        if not accounts:
            print("No accounts found!")
            return
        
        # Use first account for demo
        account_number = accounts[0]
        print(f"\nUsing account: {account_number}")
        
        # Get account information
        print("\nFetching account information...")
        account_info = await broker.get_account_info(
            account_number,
            fields=['positions']
        )
        
        # Display account balances
        balances = account_info.get('securitiesAccount', {}).get('currentBalances', {})
        if balances:
            print(f"\nAccount Balances:")
            print(f"  Cash Balance: ${balances.get('cashBalance', 0):,.2f}")
            print(f"  Account Value: ${balances.get('accountValue', 0):,.2f}")
            print(f"  Buying Power: ${balances.get('buyingPower', 0):,.2f}")
        
        # Get positions
        print("\nFetching positions...")
        positions = await broker.get_positions(account_number)
        
        if positions:
            print(f"\nCurrent Positions ({len(positions)}):")
            for position in positions:
                instrument = position.get('instrument', {})
                symbol = instrument.get('symbol', 'Unknown')
                quantity = position.get('longQuantity', 0)
                avg_price = position.get('averagePrice', 0)
                market_value = position.get('marketValue', 0)
                
                print(f"  {symbol}: {quantity} shares @ ${avg_price:.2f} = ${market_value:,.2f}")
        else:
            print("\nNo positions found.")
        
        # Get recent orders
        print("\nFetching recent orders...")
        orders = await broker.get_orders(
            account_number,
            from_entered_time=datetime.now() - timedelta(days=7),
            max_results=5
        )
        
        if orders:
            print(f"\nRecent Orders ({len(orders)}):")
            for order in orders[:5]:  # Show max 5 orders
                order_id = order.get('orderId', 'Unknown')
                status = order.get('status', 'Unknown')
                
                # Get order details
                legs = order.get('orderLegCollection', [])
                if legs:
                    leg = legs[0]
                    symbol = leg.get('instrument', {}).get('symbol', 'Unknown')
                    instruction = leg.get('instruction', 'Unknown')
                    quantity = leg.get('quantity', 0)
                    
                    print(f"  Order {order_id}: {instruction} {quantity} {symbol} - Status: {status}")
        else:
            print("\nNo recent orders found.")
            
    except Exception as e:
        logger.error(f"Account operations error: {e}")
        print(f"\nError during account operations: {e}")


async def demo_market_data(broker: SchwabBroker):
    """Demonstrate market data operations."""
    print("\n=== Market Data Demo ===\n")
    
    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
    
    try:
        # Get quotes
        print(f"Fetching quotes for: {', '.join(symbols)}")
        quotes = await broker.get_quotes(symbols)
        
        print("\nCurrent Quotes:")
        for symbol in symbols:
            if symbol in quotes:
                quote = quotes[symbol]
                last = quote.get('lastPrice', quote.get('last', 0))
                bid = quote.get('bidPrice', quote.get('bid', 0))
                ask = quote.get('askPrice', quote.get('ask', 0))
                volume = quote.get('totalVolume', quote.get('volume', 0))
                
                print(f"  {symbol}: Last=${last:.2f}, Bid=${bid:.2f}, Ask=${ask:.2f}, Volume={volume:,}")
        
        # Get price history for one symbol
        print(f"\nFetching price history for AAPL (last 5 days)...")
        history = await broker.get_price_history(
            symbol="AAPL",
            period_type="day",
            period=5,
            frequency_type="daily",
            frequency=1
        )
        
        candles = history.get('candles', [])
        if candles:
            print(f"\nPrice History (last {len(candles)} days):")
            for candle in candles[-5:]:  # Show last 5 candles
                date = datetime.fromtimestamp(candle['datetime'] / 1000).strftime('%Y-%m-%d')
                open_price = candle['open']
                close_price = candle['close']
                high = candle['high']
                low = candle['low']
                volume = candle['volume']
                
                print(f"  {date}: O=${open_price:.2f}, H=${high:.2f}, L=${low:.2f}, C=${close_price:.2f}, V={volume:,}")
        
        # Get market hours
        print("\nChecking market hours...")
        market_hours = await broker.get_market_hours("EQUITY")
        
        for market, hours_data in market_hours.items():
            for key, hours in hours_data.items():
                is_open = hours.get('isOpen', False)
                market_type = hours.get('marketType', 'Unknown')
                
                print(f"\n{market_type} Market: {'OPEN' if is_open else 'CLOSED'}")
                
                if 'sessionHours' in hours:
                    session_hours = hours['sessionHours']
                    if 'regularMarket' in session_hours:
                        for session in session_hours['regularMarket']:
                            start = session.get('start', 'Unknown')
                            end = session.get('end', 'Unknown')
                            print(f"  Regular Hours: {start} - {end}")
                
    except RateLimitError:
        print("\n⚠️  Rate limited! Please wait before making more requests.")
    except Exception as e:
        logger.error(f"Market data error: {e}")
        print(f"\nError fetching market data: {e}")


async def demo_order_placement(broker: SchwabBroker):
    """Demonstrate order placement (with safety checks)."""
    print("\n=== Order Placement Demo ===\n")
    print("⚠️  This is a demo - no real orders will be placed without confirmation\n")
    
    try:
        # Get first account
        accounts = await broker.get_account_numbers()
        if not accounts:
            print("No accounts available for order placement.")
            return
        
        account_number = accounts[0]
        
        # Example order (small, safe amount)
        symbol = "AAPL"
        quantity = 1
        
        # Get current quote
        quotes = await broker.get_quotes(symbol)
        if symbol not in quotes:
            print(f"Could not get quote for {symbol}")
            return
        
        current_price = quotes[symbol].get('last', 0)
        if current_price <= 0:
            print(f"Invalid price for {symbol}")
            return
        
        # Set limit price slightly below current (more likely to fill)
        limit_price = round(current_price * 0.99, 2)
        
        print(f"Example Order:")
        print(f"  Symbol: {symbol}")
        print(f"  Type: BUY LIMIT")
        print(f"  Quantity: {quantity}")
        print(f"  Current Price: ${current_price:.2f}")
        print(f"  Limit Price: ${limit_price:.2f}")
        print(f"  Estimated Cost: ${limit_price * quantity:.2f}")
        
        # Create order object
        order = {
            'orderType': 'LIMIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': limit_price,
            'orderLegCollection': [{
                'instruction': 'BUY',
                'quantity': quantity,
                'instrument': {
                    'symbol': symbol,
                    'assetType': 'EQUITY'
                }
            }]
        }
        
        # Safety check - require confirmation
        response = input("\nDo you want to place this order? (yes/no): ")
        if response.lower() != 'yes':
            print("Order cancelled by user.")
            return
        
        # Place order
        print("\nPlacing order...")
        result = await broker.place_order(account_number, order)
        
        print(f"\n✅ Order placed successfully!")
        print(f"   Order ID: {result['order_id']}")
        print(f"   Status: {result['status']}")
        
        # Demonstrate order cancellation
        response = input("\nDo you want to cancel this order? (yes/no): ")
        if response.lower() == 'yes':
            print("\nCancelling order...")
            cancel_result = await broker.cancel_order(account_number, result['order_id'])
            print(f"✅ Order cancelled: {cancel_result['status']}")
        
    except InvalidOrderError as e:
        print(f"\n❌ Invalid order: {e}")
    except InsufficientFundsError as e:
        print(f"\n❌ Insufficient funds: {e}")
    except Exception as e:
        logger.error(f"Order placement error: {e}")
        print(f"\n❌ Error placing order: {e}")


async def demo_monitoring(broker: SchwabBroker):
    """Demonstrate monitoring capabilities."""
    print("\n=== System Monitoring Demo ===\n")
    
    # Get rate limiter stats
    rate_stats = broker.rate_limiter.get_stats()
    print("Rate Limiter Statistics:")
    print(f"  Total Requests: {rate_stats['total_requests']}")
    print(f"  Rejected Requests: {rate_stats['rejected_requests']}")
    print(f"  Average Wait Time: {rate_stats['average_wait_time']:.3f}s")
    
    # Get circuit breaker stats
    breaker_stats = broker.circuit_breaker.get_stats()
    print("\nCircuit Breaker Statistics:")
    print(f"  State: {breaker_stats['state'].upper()}")
    print(f"  Total Requests: {breaker_stats['total_requests']}")
    print(f"  Total Failures: {breaker_stats['total_failures']}")
    print(f"  Success Rate: {breaker_stats['success_rate']:.1%}")


async def main():
    """Main demo function."""
    print("=" * 60)
    print("Schwab Broker Demo")
    print("=" * 60)
    
    try:
        # Initialize broker
        print("\nInitializing broker connection...")
        
        async with SchwabBroker() as broker:
            print("✅ Broker initialized successfully!\n")
            
            # Run demos
            await demo_account_operations(broker)
            await demo_market_data(broker)
            
            # Optional order placement demo
            response = input("\nDo you want to see the order placement demo? (yes/no): ")
            if response.lower() == 'yes':
                await demo_order_placement(broker)
            
            # Show monitoring stats
            await demo_monitoring(broker)
            
        print("\n✅ Demo completed successfully!")
        
    except BrokerError as e:
        print(f"\n❌ Broker error: {e}")
        logger.error(f"Broker error: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.exception("Unexpected error in demo")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
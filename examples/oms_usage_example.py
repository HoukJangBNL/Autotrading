#!/usr/bin/env python3
"""
Example usage of the Order Management System with Event Sourcing and CQRS.

This example demonstrates how to use the OMS components including:
- Event-sourced order lifecycle management
- Risk validation
- Command and query operations
- Event bus integration
- Event store persistence

Run this example to see the OMS in action with sample orders.
"""

import asyncio
import sys
import os
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trader.order_management.oms_application import OrderManagementApplication
from trader.order_management.event_store import OrderEventStoreFactory
from trader.order_management.risk_validator import PreTradeRiskValidator, RiskConfig
from trader.order_management.order import OrderSide, OrderType
from utils.logger import get_logger

logger = get_logger(__name__)


async def demo_oms_lifecycle():
    """Demonstrate complete OMS order lifecycle."""
    
    print("🚀 Starting OMS Event Sourcing Demo")
    print("=" * 50)
    
    # Step 1: Create risk configuration
    print("\n📋 Step 1: Setting up risk configuration...")
    risk_config = RiskConfig(
        max_position_size=1000,
        max_order_size=500,
        max_daily_loss=Decimal("1000"),
        enable_market_hours_check=False,  # Disable for demo
        restricted_symbols={"RESTRICTED_STOCK"}
    )
    
    # Step 2: Initialize components
    print("\n🔧 Step 2: Initializing OMS components...")
    
    # Create risk validator
    risk_validator = PreTradeRiskValidator(risk_config)
    
    # Create event store for testing
    event_store = OrderEventStoreFactory.create_test_store()
    
    # Create OMS application
    oms = OrderManagementApplication(
        risk_validator=risk_validator,
        event_store=event_store,
        environment="test"
    )
    
    # Step 3: Set up event listeners
    print("\n📡 Step 3: Setting up event listeners...")
    
    async def on_order_event(event):
        """Handle order events for demo purposes."""
        event_type = type(event).__name__
        print(f"   📢 Event: {event_type} for order {getattr(event, 'originator_id', 'unknown')}")
    
    oms.subscribe_to_events(on_order_event)
    
    print("✅ OMS initialization complete!")
    
    # Step 4: Create and process orders
    print("\n📝 Step 4: Creating and processing orders...")
    
    # Example 1: Successful order workflow
    print("\n🟢 Example 1: Successful order workflow")
    print("-" * 40)
    
    try:
        # Create order
        result = await oms.create_order(
            symbol="AAPL",
            side="BUY",
            quantity=100,
            order_type="LIMIT",
            limit_price=150.50,
            account_id="DEMO_ACCOUNT",
            strategy_id="DEMO_STRATEGY"
        )
        
        if result.success:
            order_id = result.order_id
            print(f"✅ Order created successfully: {order_id}")
            
            # Validate order
            validation_result = await oms.validate_order(order_id)
            print(f"🔍 Validation result: {'✅ PASSED' if validation_result.success else '❌ FAILED'}")
            
            if validation_result.success:
                # Submit order
                submit_result = await oms.submit_order(order_id)
                print(f"📤 Submission result: {'✅ SUBMITTED' if submit_result.success else '❌ FAILED'}")
                
                if submit_result.success:
                    # Simulate partial fill
                    fill_result = await oms.process_fill(
                        order_id=order_id,
                        fill_quantity=50,
                        fill_price=150.25,
                        commission=Decimal("1.00")
                    )
                    print(f"📊 Partial fill: {'✅ PROCESSED' if fill_result.success else '❌ FAILED'}")
                    
                    # Complete the fill
                    complete_fill_result = await oms.process_fill(
                        order_id=order_id,
                        fill_quantity=50,
                        fill_price=150.30,
                        commission=Decimal("1.00")
                    )
                    print(f"📊 Complete fill: {'✅ PROCESSED' if complete_fill_result.success else '❌ FAILED'}")
                    
                    # Get final order state
                    final_order = await oms.get_order(order_id)
                    if final_order:
                        print(f"📈 Final order state: {final_order.state}")
                        print(f"💰 Average fill price: ${final_order.average_fill_price}")
                        print(f"📊 Total cost: ${final_order.total_cost}")
        
        else:
            print(f"❌ Order creation failed: {result.message}")
    
    except Exception as e:
        print(f"❌ Error in successful workflow: {e}")
    
    # Example 2: Risk validation failure
    print("\n🟡 Example 2: Risk validation failure")
    print("-" * 40)
    
    try:
        # Create order that will fail risk checks (too large)
        result = await oms.create_order(
            symbol="TSLA",
            side="BUY",
            quantity=1000,  # Exceeds max_order_size of 500
            order_type="MARKET",
            account_id="DEMO_ACCOUNT",
            strategy_id="DEMO_STRATEGY"
        )
        
        if result.success:
            order_id = result.order_id
            print(f"✅ Order created: {order_id}")
            
            # This should fail validation
            validation_result = await oms.validate_order(order_id)
            print(f"🔍 Validation result: {'✅ PASSED' if validation_result.success else '❌ FAILED'}")
            print(f"📝 Reason: {validation_result.message}")
    
    except Exception as e:
        print(f"❌ Error in risk failure example: {e}")
    
    # Example 3: Restricted symbol
    print("\n🔴 Example 3: Restricted symbol")
    print("-" * 40)
    
    try:
        result = await oms.create_order(
            symbol="RESTRICTED_STOCK",
            side="BUY", 
            quantity=100,
            order_type="MARKET",
            account_id="DEMO_ACCOUNT",
            strategy_id="DEMO_STRATEGY"
        )
        
        if result.success:
            order_id = result.order_id
            validation_result = await oms.validate_order(order_id)
            print(f"🔍 Validation result: {'✅ PASSED' if validation_result.success else '❌ FAILED'}")
            print(f"📝 Reason: {validation_result.message}")
    
    except Exception as e:
        print(f"❌ Error in restricted symbol example: {e}")
    
    # Example 4: Order cancellation
    print("\n🟠 Example 4: Order cancellation")
    print("-" * 40)
    
    try:
        # Create and submit order
        result = await oms.create_order(
            symbol="MSFT",
            side="SELL",
            quantity=200,
            order_type="LIMIT",
            limit_price=300.00,
            account_id="DEMO_ACCOUNT",
            strategy_id="DEMO_STRATEGY"
        )
        
        if result.success:
            order_id = result.order_id
            print(f"✅ Order created: {order_id}")
            
            # Validate and submit
            validation_result = await oms.validate_order(order_id)
            if validation_result.success:
                submit_result = await oms.submit_order(order_id)
                if submit_result.success:
                    print("📤 Order submitted successfully")
                    
                    # Cancel the order
                    cancel_result = await oms.cancel_order(
                        order_id=order_id,
                        reason="User requested cancellation",
                        requested_by="demo_user"
                    )
                    print(f"🚫 Cancellation: {'✅ CANCELLED' if cancel_result.success else '❌ FAILED'}")
    
    except Exception as e:
        print(f"❌ Error in cancellation example: {e}")
    
    # Step 5: Query operations
    print("\n📊 Step 5: Query operations and statistics")
    print("-" * 40)
    
    try:
        # Get statistics
        stats = await oms.get_order_statistics()
        print(f"📈 Total orders: {stats.total_orders}")
        print(f"✅ Completed orders: {stats.completed_orders}")
        print(f"🚫 Cancelled orders: {stats.cancelled_orders}")
        print(f"❌ Rejected orders: {stats.rejected_orders}")
        
        # Get system status
        system_status = await oms.get_system_status()
        print(f"🏥 System status: {system_status['status']}")
        print(f"📊 Event subscribers: {system_status['event_subscribers']}")
        
        # Get real-time metrics
        metrics = await oms.get_real_time_metrics()
        print(f"📊 Active orders: {metrics.get('active_orders', 0)}")
        print(f"📅 Orders today: {metrics.get('orders_today', 0)}")
        
        # Get event store health
        event_store_health = await oms.get_event_store_health()
        print(f"💾 Event store status: {event_store_health['status']}")
        print(f"📚 Total events: {event_store_health.get('total_events', 0)}")
        
    except Exception as e:
        print(f"❌ Error getting statistics: {e}")
    
    # Step 6: Event history demonstration
    print("\n📜 Step 6: Event history")
    print("-" * 40)
    
    try:
        # Get all orders to find one with events
        active_orders = await oms.get_active_orders()
        completed_orders = await oms.list_orders()
        
        all_orders = active_orders + completed_orders
        if all_orders:
            sample_order = all_orders[0]
            print(f"📖 Getting event history for order: {sample_order.order_id}")
            
            event_history = await oms.get_order_event_history(sample_order.order_id)
            print(f"📚 Total events: {event_history.get('total_events', 0)}")
            
            for i, event in enumerate(event_history.get('events', [])[:3]):  # Show first 3 events
                print(f"   {i+1}. {event['event_type']} (v{event['version']})")
        else:
            print("📭 No orders found to show event history")
    
    except Exception as e:
        print(f"❌ Error getting event history: {e}")
    
    # Cleanup
    print("\n🧹 Cleanup")
    print("-" * 40)
    
    try:
        await oms.close()
        print("✅ OMS closed successfully")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
    
    print("\n🎉 Demo completed!")
    print("=" * 50)


async def demo_batch_operations():
    """Demonstrate batch order operations."""
    
    print("\n🔄 Batch Operations Demo")
    print("=" * 30)
    
    # Initialize OMS
    risk_config = RiskConfig(enable_market_hours_check=False)
    risk_validator = PreTradeRiskValidator(risk_config)
    event_store = OrderEventStoreFactory.create_test_store()
    
    oms = OrderManagementApplication(
        risk_validator=risk_validator,
        event_store=event_store,
        environment="test"
    )
    
    # Track events
    event_count = 0
    
    async def count_events(event):
        nonlocal event_count
        event_count += 1
    
    oms.subscribe_to_events(count_events)
    
    # Create multiple orders
    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
    order_ids = []
    
    print(f"📝 Creating {len(symbols)} orders...")
    
    for symbol in symbols:
        result = await oms.create_and_submit_order(
            symbol=symbol,
            side="BUY",
            quantity=100,
            order_type="LIMIT",
            limit_price=100.00,
            auto_validate=True,
            auto_submit=True,
            account_id="BATCH_ACCOUNT",
            strategy_id="BATCH_STRATEGY"
        )
        
        if result["success"]:
            order_ids.append(result["order_id"])
            print(f"✅ {symbol}: {result['message']}")
        else:
            print(f"❌ {symbol}: {result['message']}")
    
    print(f"\n📊 Created {len(order_ids)} orders successfully")
    print(f"📢 Generated {event_count} events")
    
    # Get statistics
    stats = await oms.get_order_statistics()
    print(f"📈 Total orders in system: {stats.total_orders}")
    
    await oms.close()
    print("✅ Batch demo completed")


async def main():
    """Run all demo scenarios."""
    print("🎯 Order Management System - Event Sourcing Demo")
    print("=" * 60)
    print("This demo showcases the OMS with event sourcing and CQRS patterns.")
    print("Features demonstrated:")
    print("  • Event-sourced order aggregates")
    print("  • CQRS command and query separation")
    print("  • Risk validation engine")
    print("  • Circuit breaker patterns")
    print("  • Event bus for real-time updates")
    print("  • Persistent event store")
    print("=" * 60)
    
    try:
        # Run main lifecycle demo
        await demo_oms_lifecycle()
        
        # Run batch operations demo
        await demo_batch_operations()
        
        print("\n🏆 All demos completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⚠️  Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\n❌ Demo failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    # Run the demo
    exit_code = asyncio.run(main())
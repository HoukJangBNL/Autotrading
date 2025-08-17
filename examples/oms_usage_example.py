"""
Example usage of the Order Management System.

This demonstrates how to use the OMS components together for order lifecycle management.
"""

import asyncio
from decimal import Decimal
from datetime import datetime, timezone

from src.trader.order_management import (
    Order, OrderState, OrderType, OrderSide, Fill,
    OrderService, OrderStateMachine,
    PreTradeRiskValidator, RiskConfig,
    PositionTracker, CostBasisMethod
)
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def basic_order_example():
    """Basic example of creating and processing an order."""
    print("\n=== Basic Order Example ===")
    
    # Create OMS components
    risk_config = RiskConfig(
        max_order_size=1000,
        max_position_size=5000,
        max_daily_loss=Decimal("10000"),
        restricted_symbols={"BANNED", "RESTRICTED"}
    )
    
    position_tracker = PositionTracker(
        cost_basis_method=CostBasisMethod.FIFO
    )
    
    risk_validator = PreTradeRiskValidator(
        config=risk_config,
        position_tracker=position_tracker
    )
    
    order_service = OrderService(
        risk_validator=risk_validator,
        broker_client=None,  # Would be actual broker client
        position_tracker=position_tracker
    )
    
    # Create an order
    order = await order_service.create_order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("150.00"),
        account_id="DEMO123",
        strategy_id="MOMENTUM_01"
    )
    
    print(f"Created order: {order.order_id}")
    print(f"  Symbol: {order.symbol}")
    print(f"  Side: {order.side}")
    print(f"  Quantity: {order.quantity}")
    print(f"  Type: {order.order_type}")
    print(f"  Limit Price: ${order.limit_price}")
    print(f"  State: {order.state}")
    
    # Validate the order
    validation_result = await order_service.validate_order(order.order_id)
    print(f"\nValidation result: {'PASSED' if validation_result.passed else 'FAILED'}")
    
    if validation_result.passed:
        print("  All risk checks passed")
    else:
        print(f"  Failed checks: {validation_result.get_failure_reasons()}")
    
    # Submit the order
    if validation_result.passed:
        success = await order_service.submit_order(order.order_id)
        print(f"\nOrder submission: {'SUCCESS' if success else 'FAILED'}")
        print(f"  State: {order.state}")
        print(f"  Broker Order ID: {order.broker_order_id}")
    
    # Simulate a fill
    print("\nSimulating order fill...")
    await order_service.process_fill(
        order_id=order.order_id,
        fill_quantity=100,
        fill_price=Decimal("149.95"),
        commission=Decimal("0.65"),
        fees=Decimal("0.01")
    )
    
    print(f"  State: {order.state}")
    print(f"  Filled Quantity: {order.filled_quantity}")
    print(f"  Average Fill Price: ${order.average_fill_price}")
    print(f"  Total Commission: ${order.total_commission}")
    print(f"  Total Fees: ${order.total_fees}")
    
    # Check position
    position = await position_tracker.get_position("AAPL")
    if position:
        print(f"\nPosition Update:")
        print(f"  Symbol: {position.symbol}")
        print(f"  Quantity: {position.quantity}")
        print(f"  Average Cost: ${position.average_cost}")
        print(f"  Total Commission: ${position.total_commission}")


async def pnl_calculation_example():
    """Example of P&L calculation with multiple trades."""
    print("\n=== P&L Calculation Example ===")
    
    position_tracker = PositionTracker(
        cost_basis_method=CostBasisMethod.FIFO
    )
    
    # Trade 1: Buy 100 shares @ $150
    buy_order1 = Order(
        order_id="BUY1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET
    )
    
    fill1 = Fill(
        fill_id="F1",
        timestamp=datetime.now(timezone.utc),
        quantity=100,
        price=Decimal("150.00"),
        commission=Decimal("1.00")
    )
    
    await position_tracker.process_fill(buy_order1, fill1)
    print("Trade 1: Bought 100 shares @ $150.00")
    
    # Trade 2: Buy 50 more shares @ $155
    buy_order2 = Order(
        order_id="BUY2",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=50,
        order_type=OrderType.MARKET
    )
    
    fill2 = Fill(
        fill_id="F2",
        timestamp=datetime.now(timezone.utc),
        quantity=50,
        price=Decimal("155.00"),
        commission=Decimal("0.50")
    )
    
    await position_tracker.process_fill(buy_order2, fill2)
    print("Trade 2: Bought 50 shares @ $155.00")
    
    # Update market price for unrealized P&L
    position = await position_tracker.get_position("AAPL")
    position.update_market_price(Decimal("160.00"))
    
    print(f"\nPosition before sale:")
    print(f"  Quantity: {position.quantity}")
    print(f"  Average Cost: ${position.average_cost:.2f}")
    print(f"  Market Value: ${position.market_value:.2f}")
    print(f"  Unrealized P&L: ${position.unrealized_pnl:.2f}")
    
    # Trade 3: Sell 75 shares @ $160 (FIFO will sell 75 from first lot)
    sell_order = Order(
        order_id="SELL1",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=75,
        order_type=OrderType.MARKET
    )
    
    fill3 = Fill(
        fill_id="F3",
        timestamp=datetime.now(timezone.utc),
        quantity=75,
        price=Decimal("160.00"),
        commission=Decimal("0.75")
    )
    
    await position_tracker.process_fill(sell_order, fill3)
    print("\nTrade 3: Sold 75 shares @ $160.00")
    
    # Final position
    position = await position_tracker.get_position("AAPL")
    print(f"\nFinal Position:")
    print(f"  Quantity: {position.quantity}")
    print(f"  Average Cost: ${position.average_cost:.2f}")
    print(f"  Realized P&L: ${position.realized_pnl:.2f}")
    print(f"  Unrealized P&L: ${position.unrealized_pnl:.2f}")
    print(f"  Total P&L: ${position.total_pnl:.2f}")
    print(f"  Net P&L (after commission): ${position.net_pnl:.2f}")
    
    # Show remaining lots
    print(f"\nRemaining Lots (FIFO):")
    for i, lot in enumerate(position.lots):
        print(f"  Lot {i+1}: {lot.quantity} shares @ ${lot.cost_basis:.2f}")


async def risk_validation_example():
    """Example of risk validation scenarios."""
    print("\n=== Risk Validation Example ===")
    
    # Create strict risk configuration
    risk_config = RiskConfig(
        max_order_size=500,
        max_position_size=1000,
        max_order_value=Decimal("50000"),
        price_deviation_percent=Decimal("0.02"),  # 2% max deviation
        restricted_symbols={"TSLA", "GME", "AMC"}
    )
    
    risk_validator = PreTradeRiskValidator(config=risk_config)
    
    # Test various orders
    test_orders = [
        # Order 1: Valid order
        Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("150.00")
        ),
        
        # Order 2: Exceeds max order size
        Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=600,  # Exceeds 500
            order_type=OrderType.MARKET
        ),
        
        # Order 3: Restricted symbol
        Order(
            symbol="GME",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        ),
        
        # Order 4: Exceeds order value
        Order(
            symbol="GOOGL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("2500.00")  # $250,000 exceeds $50,000 limit
        ),
    ]
    
    for i, order in enumerate(test_orders, 1):
        print(f"\nOrder {i}: {order.side} {order.quantity} {order.symbol}")
        if order.order_type == OrderType.LIMIT:
            print(f"  Limit Price: ${order.limit_price}")
        
        result = await risk_validator.validate_order(order)
        print(f"  Result: {'PASSED' if result.passed else 'FAILED'}")
        
        if not result.passed:
            for check in result.get_failures():
                print(f"    - {check.check_type.value}: {check.reason}")


async def order_state_tracking_example():
    """Example of tracking order state changes."""
    print("\n=== Order State Tracking Example ===")
    
    order = Order(
        symbol="MSFT",
        side=OrderSide.BUY,
        quantity=50,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("300.00")
    )
    
    # Track state changes
    def on_state_change(order, event):
        transition = order.state_history[-1] if order.state_history else None
        if transition:
            print(f"State changed: {transition.from_state} -> {transition.to_state}")
            if transition.reason:
                print(f"  Reason: {transition.reason}")
    
    # Create state machine with callback
    machine = OrderStateMachine(order, callbacks={'on_validated': on_state_change})
    
    # Simulate order lifecycle
    print(f"Initial state: {order.state}")
    
    # Validate
    order.risk_check_results = {'passed': True}
    machine.validate()
    
    # Submit
    machine.submit()
    
    # Acknowledge
    machine.set_metadata({'broker_order_id': 'BROKER-12345'})
    machine.acknowledge()
    
    # Partial fill
    fill1 = Fill(
        fill_id="PF1",
        timestamp=datetime.now(timezone.utc),
        quantity=30,
        price=Decimal("299.95")
    )
    machine.set_metadata({'fill': fill1})
    machine.partial_fill()
    
    # Final fill
    fill2 = Fill(
        fill_id="PF2",
        timestamp=datetime.now(timezone.utc),
        quantity=20,
        price=Decimal("299.90")
    )
    machine.set_metadata({'fill': fill2})
    machine.fill()
    
    print(f"\nFinal state: {order.state}")
    print(f"State history ({len(order.state_history)} transitions):")
    for transition in order.state_history:
        print(f"  {transition.from_state} -> {transition.to_state} at {transition.timestamp.strftime('%H:%M:%S')}")


async def main():
    """Run all examples."""
    print("Order Management System Examples")
    print("================================")
    
    await basic_order_example()
    await pnl_calculation_example()
    await risk_validation_example()
    await order_state_tracking_example()
    
    print("\n\nAll examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
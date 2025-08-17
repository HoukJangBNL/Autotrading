"""
Real-time position tracking with P&L calculation.

This module provides comprehensive position tracking, P&L calculation,
and integration with the order management system.
"""

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any, Deque
from enum import Enum
import json

from .order import Order, OrderSide, Fill
from ...data.stream_processor import OHLCV
from ...data.quote_service import Quote
from ...utils.logger import get_logger

logger = get_logger(__name__)


class CostBasisMethod(str, Enum):
    """Cost basis calculation methods."""
    FIFO = "FIFO"  # First In First Out
    LIFO = "LIFO"  # Last In First Out
    AVERAGE = "AVERAGE"  # Average cost


@dataclass
class PositionLot:
    """Represents a tax lot for a position."""
    lot_id: str
    quantity: int
    cost_basis: Decimal
    entry_time: datetime
    entry_order_id: str
    commission: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    
    @property
    def total_cost(self) -> Decimal:
        """Total cost including commission and fees."""
        return (self.cost_basis * self.quantity) + self.commission + self.fees
    
    @property
    def average_cost(self) -> Decimal:
        """Average cost per share."""
        return self.total_cost / self.quantity if self.quantity > 0 else Decimal("0")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'lot_id': self.lot_id,
            'quantity': self.quantity,
            'cost_basis': str(self.cost_basis),
            'entry_time': self.entry_time.isoformat(),
            'entry_order_id': self.entry_order_id,
            'commission': str(self.commission),
            'fees': str(self.fees)
        }


@dataclass
class PositionUpdate:
    """Represents an update to a position."""
    timestamp: datetime
    update_type: str  # 'FILL', 'ADJUSTMENT', 'SPLIT', etc.
    quantity_change: int
    price: Decimal
    order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'update_type': self.update_type,
            'quantity_change': self.quantity_change,
            'price': str(self.price),
            'order_id': self.order_id,
            'metadata': self.metadata
        }


@dataclass
class Position:
    """
    Comprehensive position representation with P&L tracking.
    """
    symbol: str
    quantity: int = 0
    average_cost: Decimal = Decimal("0")
    
    # P&L tracking
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    total_commission: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    
    # Market data
    last_price: Decimal = Decimal("0")
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Tax lots for detailed tracking
    lots: List[PositionLot] = field(default_factory=list)
    
    # Position history
    updates: Deque[PositionUpdate] = field(default_factory=lambda: deque(maxlen=1000))
    
    # Statistics
    total_bought: int = 0
    total_sold: int = 0
    total_buy_value: Decimal = Decimal("0")
    total_sell_value: Decimal = Decimal("0")
    
    # Timestamps
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    @property
    def is_open(self) -> bool:
        """Check if position is open."""
        return self.quantity != 0
    
    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.quantity < 0
    
    @property
    def market_value(self) -> Decimal:
        """Current market value of position."""
        return self.quantity * self.last_price
    
    @property
    def cost_basis(self) -> Decimal:
        """Total cost basis of position."""
        return self.quantity * self.average_cost
    
    @property
    def total_pnl(self) -> Decimal:
        """Total P&L (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl
    
    @property
    def net_pnl(self) -> Decimal:
        """Net P&L after commission and fees."""
        return self.total_pnl - self.total_commission - self.total_fees
    
    @property
    def return_percent(self) -> Decimal:
        """Return percentage on position."""
        if self.cost_basis == 0:
            return Decimal("0")
        return (self.unrealized_pnl / abs(self.cost_basis)) * 100
    
    def update_market_price(self, price: Decimal):
        """Update market price and unrealized P&L."""
        self.last_price = price
        self.last_update = datetime.now(timezone.utc)
        
        # Calculate unrealized P&L
        if self.quantity != 0:
            market_value = self.quantity * price
            cost_basis = self.quantity * self.average_cost
            self.unrealized_pnl = market_value - cost_basis
        else:
            self.unrealized_pnl = Decimal("0")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'average_cost': str(self.average_cost),
            'realized_pnl': str(self.realized_pnl),
            'unrealized_pnl': str(self.unrealized_pnl),
            'total_pnl': str(self.total_pnl),
            'net_pnl': str(self.net_pnl),
            'total_commission': str(self.total_commission),
            'total_fees': str(self.total_fees),
            'last_price': str(self.last_price),
            'last_update': self.last_update.isoformat(),
            'market_value': str(self.market_value),
            'cost_basis': str(self.cost_basis),
            'return_percent': str(self.return_percent),
            'is_open': self.is_open,
            'is_long': self.is_long,
            'is_short': self.is_short,
            'total_bought': self.total_bought,
            'total_sold': self.total_sold,
            'total_buy_value': str(self.total_buy_value),
            'total_sell_value': str(self.total_sell_value),
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'lots': [lot.to_dict() for lot in self.lots],
            'recent_updates': [update.to_dict() for update in list(self.updates)[-10:]]
        }


class PnLCalculator:
    """Calculates P&L using different cost basis methods."""
    
    @staticmethod
    def calculate_fifo(
        lots: List[PositionLot],
        sell_quantity: int,
        sell_price: Decimal
    ) -> Tuple[Decimal, List[PositionLot], List[PositionLot]]:
        """
        Calculate realized P&L using FIFO method.
        
        Args:
            lots: Current position lots
            sell_quantity: Quantity to sell
            sell_price: Sale price per share
            
        Returns:
            Tuple of (realized_pnl, remaining_lots, sold_lots)
        """
        remaining_quantity = sell_quantity
        realized_pnl = Decimal("0")
        remaining_lots = []
        sold_lots = []
        
        for lot in lots:
            if remaining_quantity <= 0:
                remaining_lots.append(lot)
                continue
            
            if lot.quantity <= remaining_quantity:
                # Sell entire lot
                pnl = (sell_price - lot.average_cost) * lot.quantity
                realized_pnl += pnl
                remaining_quantity -= lot.quantity
                sold_lots.append(lot)
            else:
                # Sell partial lot
                sold_quantity = remaining_quantity
                pnl = (sell_price - lot.average_cost) * sold_quantity
                realized_pnl += pnl
                
                # Create remaining lot
                remaining_lot = PositionLot(
                    lot_id=lot.lot_id,
                    quantity=lot.quantity - sold_quantity,
                    cost_basis=lot.cost_basis,
                    entry_time=lot.entry_time,
                    entry_order_id=lot.entry_order_id,
                    commission=lot.commission * (lot.quantity - sold_quantity) / lot.quantity,
                    fees=lot.fees * (lot.quantity - sold_quantity) / lot.quantity
                )
                remaining_lots.append(remaining_lot)
                
                # Create sold lot
                sold_lot = PositionLot(
                    lot_id=lot.lot_id + "_sold",
                    quantity=sold_quantity,
                    cost_basis=lot.cost_basis,
                    entry_time=lot.entry_time,
                    entry_order_id=lot.entry_order_id,
                    commission=lot.commission * sold_quantity / lot.quantity,
                    fees=lot.fees * sold_quantity / lot.quantity
                )
                sold_lots.append(sold_lot)
                
                remaining_quantity = 0
        
        return realized_pnl, remaining_lots, sold_lots
    
    @staticmethod
    def calculate_lifo(
        lots: List[PositionLot],
        sell_quantity: int,
        sell_price: Decimal
    ) -> Tuple[Decimal, List[PositionLot], List[PositionLot]]:
        """
        Calculate realized P&L using LIFO method.
        
        Args:
            lots: Current position lots
            sell_quantity: Quantity to sell
            sell_price: Sale price per share
            
        Returns:
            Tuple of (realized_pnl, remaining_lots, sold_lots)
        """
        # Process lots in reverse order (last in first out)
        reversed_lots = list(reversed(lots))
        realized_pnl, remaining_lots_reversed, sold_lots = PnLCalculator.calculate_fifo(
            reversed_lots, sell_quantity, sell_price
        )
        
        # Reverse remaining lots back to original order
        remaining_lots = list(reversed(remaining_lots_reversed))
        
        return realized_pnl, remaining_lots, sold_lots
    
    @staticmethod
    def calculate_average(
        position: Position,
        sell_quantity: int,
        sell_price: Decimal
    ) -> Decimal:
        """
        Calculate realized P&L using average cost method.
        
        Args:
            position: Current position
            sell_quantity: Quantity to sell
            sell_price: Sale price per share
            
        Returns:
            Realized P&L
        """
        return (sell_price - position.average_cost) * sell_quantity


class PositionTracker:
    """
    Tracks all positions with real-time updates and P&L calculation.
    """
    
    def __init__(
        self,
        cost_basis_method: CostBasisMethod = CostBasisMethod.FIFO,
        quote_service: Optional[Any] = None,
        database: Optional[Any] = None
    ):
        """
        Initialize position tracker.
        
        Args:
            cost_basis_method: Method for calculating cost basis
            quote_service: Quote service for real-time prices
            database: Database for persistence
        """
        self.cost_basis_method = cost_basis_method
        self.quote_service = quote_service
        self.database = database
        
        # Position storage
        self._positions: Dict[str, Position] = {}
        
        # Daily metrics
        self._daily_pnl = Decimal("0")
        self._daily_realized_pnl = Decimal("0")
        self._daily_commission = Decimal("0")
        self._daily_reset_time = datetime.now(timezone.utc).date()
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.info(f"Position tracker initialized with {cost_basis_method} method")
    
    async def process_fill(self, order: Order, fill: Fill):
        """
        Process a fill and update positions.
        
        Args:
            order: Order that was filled
            fill: Fill information
        """
        async with self._lock:
            # Get or create position
            position = self._positions.get(order.symbol)
            if not position:
                position = Position(symbol=order.symbol)
                self._positions[order.symbol] = position
                position.opened_at = datetime.now(timezone.utc)
            
            # Process based on order side
            if order.side in [OrderSide.BUY, OrderSide.BUY_TO_COVER]:
                await self._process_buy_fill(position, order, fill)
            else:  # SELL, SELL_SHORT
                await self._process_sell_fill(position, order, fill)
            
            # Update position statistics
            position.total_commission += fill.commission
            position.total_fees += fill.fees
            self._daily_commission += fill.commission + fill.fees
            
            # Record update
            update = PositionUpdate(
                timestamp=fill.timestamp,
                update_type='FILL',
                quantity_change=fill.quantity if order.side in [OrderSide.BUY, OrderSide.BUY_TO_COVER] else -fill.quantity,
                price=fill.price,
                order_id=order.order_id,
                metadata={'fill_id': fill.fill_id}
            )
            position.updates.append(update)
            
            # Update market price
            position.update_market_price(fill.price)
            
            # Check if position is closed
            if position.quantity == 0:
                position.closed_at = datetime.now(timezone.utc)
            
            # Persist to database if available
            if self.database:
                await self._persist_position(position)
            
            logger.info(
                f"Processed fill for {order.symbol}: "
                f"{fill.quantity} @ ${fill.price}, "
                f"position now {position.quantity} @ ${position.average_cost}"
            )
    
    async def _process_buy_fill(self, position: Position, order: Order, fill: Fill):
        """Process a buy fill."""
        # Update position quantity and statistics
        old_quantity = position.quantity
        position.quantity += fill.quantity
        position.total_bought += fill.quantity
        position.total_buy_value += fill.price * fill.quantity
        
        # Update average cost
        if old_quantity >= 0:
            # Adding to long position or opening new long
            total_cost = (position.average_cost * old_quantity) + (fill.price * fill.quantity)
            position.average_cost = total_cost / position.quantity if position.quantity > 0 else Decimal("0")
            
            # Add lot for tracking
            lot = PositionLot(
                lot_id=f"{fill.fill_id}_lot",
                quantity=fill.quantity,
                cost_basis=fill.price,
                entry_time=fill.timestamp,
                entry_order_id=order.order_id,
                commission=fill.commission,
                fees=fill.fees
            )
            position.lots.append(lot)
        else:
            # Covering short position
            if fill.quantity <= abs(old_quantity):
                # Partial or full cover
                realized_pnl = (position.average_cost - fill.price) * fill.quantity
                position.realized_pnl += realized_pnl
                self._daily_realized_pnl += realized_pnl
                
                # Remove lots (FIFO for covering shorts)
                covered_quantity = fill.quantity
                remaining_lots = []
                for lot in position.lots:
                    if covered_quantity <= 0:
                        remaining_lots.append(lot)
                    elif lot.quantity <= covered_quantity:
                        covered_quantity -= lot.quantity
                    else:
                        # Partial lot remains
                        lot.quantity -= covered_quantity
                        remaining_lots.append(lot)
                        covered_quantity = 0
                position.lots = remaining_lots
            else:
                # Over-cover: close short and open long
                cover_quantity = abs(old_quantity)
                realized_pnl = (position.average_cost - fill.price) * cover_quantity
                position.realized_pnl += realized_pnl
                self._daily_realized_pnl += realized_pnl
                
                # Clear lots and create new long position
                position.lots.clear()
                new_long_quantity = fill.quantity - cover_quantity
                position.average_cost = fill.price
                
                lot = PositionLot(
                    lot_id=f"{fill.fill_id}_lot",
                    quantity=new_long_quantity,
                    cost_basis=fill.price,
                    entry_time=fill.timestamp,
                    entry_order_id=order.order_id,
                    commission=fill.commission * new_long_quantity / fill.quantity,
                    fees=fill.fees * new_long_quantity / fill.quantity
                )
                position.lots.append(lot)
    
    async def _process_sell_fill(self, position: Position, order: Order, fill: Fill):
        """Process a sell fill."""
        # Update position statistics
        position.total_sold += fill.quantity
        position.total_sell_value += fill.price * fill.quantity
        
        old_quantity = position.quantity
        
        if old_quantity > 0:
            # Selling long position
            if fill.quantity <= old_quantity:
                # Partial or full sell
                if self.cost_basis_method == CostBasisMethod.FIFO:
                    realized_pnl, remaining_lots, _ = PnLCalculator.calculate_fifo(
                        position.lots, fill.quantity, fill.price
                    )
                    position.lots = remaining_lots
                    # Recalculate average cost from remaining lots
                    if remaining_lots:
                        total_cost = sum(lot.average_cost * lot.quantity for lot in remaining_lots)
                        total_quantity = sum(lot.quantity for lot in remaining_lots)
                        position.average_cost = total_cost / total_quantity if total_quantity > 0 else Decimal("0")
                elif self.cost_basis_method == CostBasisMethod.LIFO:
                    realized_pnl, remaining_lots, _ = PnLCalculator.calculate_lifo(
                        position.lots, fill.quantity, fill.price
                    )
                    position.lots = remaining_lots
                    # Recalculate average cost from remaining lots
                    if remaining_lots:
                        total_cost = sum(lot.average_cost * lot.quantity for lot in remaining_lots)
                        total_quantity = sum(lot.quantity for lot in remaining_lots)
                        position.average_cost = total_cost / total_quantity if total_quantity > 0 else Decimal("0")
                else:  # AVERAGE
                    realized_pnl = PnLCalculator.calculate_average(
                        position, fill.quantity, fill.price
                    )
                
                position.realized_pnl += realized_pnl
                self._daily_realized_pnl += realized_pnl
                position.quantity -= fill.quantity
            else:
                # Over-sell: close long and open short
                # First, realize P&L on entire long position
                if self.cost_basis_method == CostBasisMethod.AVERAGE:
                    realized_pnl = PnLCalculator.calculate_average(
                        position, old_quantity, fill.price
                    )
                else:
                    realized_pnl, _, _ = PnLCalculator.calculate_fifo(
                        position.lots, old_quantity, fill.price
                    )
                
                position.realized_pnl += realized_pnl
                self._daily_realized_pnl += realized_pnl
                
                # Clear lots and create short position
                position.lots.clear()
                short_quantity = fill.quantity - old_quantity
                position.quantity = -short_quantity
                position.average_cost = fill.price
                
                lot = PositionLot(
                    lot_id=f"{fill.fill_id}_lot",
                    quantity=short_quantity,
                    cost_basis=fill.price,
                    entry_time=fill.timestamp,
                    entry_order_id=order.order_id,
                    commission=fill.commission * short_quantity / fill.quantity,
                    fees=fill.fees * short_quantity / fill.quantity
                )
                position.lots.append(lot)
        else:
            # Adding to short position or opening new short
            position.quantity -= fill.quantity
            
            # Update average cost for short position
            total_cost = (position.average_cost * abs(old_quantity)) + (fill.price * fill.quantity)
            position.average_cost = total_cost / abs(position.quantity) if position.quantity != 0 else Decimal("0")
            
            # Add lot for tracking
            lot = PositionLot(
                lot_id=f"{fill.fill_id}_lot",
                quantity=fill.quantity,
                cost_basis=fill.price,
                entry_time=fill.timestamp,
                entry_order_id=order.order_id,
                commission=fill.commission,
                fees=fill.fees
            )
            position.lots.append(lot)
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self._positions.get(symbol)
    
    async def get_all_positions(self) -> Dict[str, Position]:
        """Get all positions."""
        return self._positions.copy()
    
    async def get_open_positions(self) -> Dict[str, Position]:
        """Get all open positions."""
        return {symbol: pos for symbol, pos in self._positions.items() if pos.is_open}
    
    async def get_position_count(self) -> int:
        """Get count of open positions."""
        return sum(1 for pos in self._positions.values() if pos.is_open)
    
    async def get_total_market_value(self) -> Decimal:
        """Get total market value of all positions."""
        return sum(pos.market_value for pos in self._positions.values() if pos.is_open)
    
    async def get_total_unrealized_pnl(self) -> Decimal:
        """Get total unrealized P&L."""
        return sum(pos.unrealized_pnl for pos in self._positions.values() if pos.is_open)
    
    async def get_total_realized_pnl(self) -> Decimal:
        """Get total realized P&L."""
        return sum(pos.realized_pnl for pos in self._positions.values())
    
    async def get_daily_pnl(self) -> Decimal:
        """Get daily P&L (realized + unrealized changes)."""
        await self._check_daily_reset()
        
        # Calculate current unrealized P&L
        current_unrealized = await self.get_total_unrealized_pnl()
        
        # Daily P&L = daily realized + change in unrealized
        return self._daily_realized_pnl + current_unrealized
    
    async def update_market_prices(self, quotes: Dict[str, Quote]):
        """
        Update market prices for all positions.
        
        Args:
            quotes: Dictionary of symbol to quote
        """
        async with self._lock:
            for symbol, quote in quotes.items():
                if symbol in self._positions:
                    position = self._positions[symbol]
                    # Use mid price for mark-to-market
                    mid_price = (quote.bid + quote.ask) / 2
                    position.update_market_price(mid_price)
    
    async def reconcile_with_broker(self, broker_positions: Dict[str, Dict[str, Any]]):
        """
        Reconcile positions with broker.
        
        Args:
            broker_positions: Broker's view of positions
        """
        discrepancies = []
        
        async with self._lock:
            # Check our positions against broker
            for symbol, position in self._positions.items():
                if position.is_open:
                    broker_pos = broker_positions.get(symbol, {})
                    broker_quantity = broker_pos.get('quantity', 0)
                    
                    if position.quantity != broker_quantity:
                        discrepancies.append({
                            'symbol': symbol,
                            'our_quantity': position.quantity,
                            'broker_quantity': broker_quantity,
                            'difference': position.quantity - broker_quantity
                        })
            
            # Check for positions at broker we don't have
            for symbol, broker_pos in broker_positions.items():
                if symbol not in self._positions or not self._positions[symbol].is_open:
                    discrepancies.append({
                        'symbol': symbol,
                        'our_quantity': 0,
                        'broker_quantity': broker_pos.get('quantity', 0),
                        'difference': -broker_pos.get('quantity', 0)
                    })
        
        if discrepancies:
            logger.warning(f"Position discrepancies found: {discrepancies}")
        
        return discrepancies
    
    async def process_corporate_action(
        self,
        symbol: str,
        action_type: str,
        ratio: Decimal,
        ex_date: datetime
    ):
        """
        Process corporate action (split, dividend, etc).
        
        Args:
            symbol: Symbol affected
            action_type: Type of action ('SPLIT', 'DIVIDEND', etc)
            ratio: Action ratio (e.g., 2 for 2:1 split)
            ex_date: Ex-dividend/split date
        """
        async with self._lock:
            position = self._positions.get(symbol)
            if not position or not position.is_open:
                return
            
            if action_type == 'SPLIT':
                # Adjust quantity and average cost for split
                old_quantity = position.quantity
                old_avg_cost = position.average_cost
                
                position.quantity = int(position.quantity * ratio)
                position.average_cost = old_avg_cost / ratio
                
                # Adjust all lots
                for lot in position.lots:
                    lot.quantity = int(lot.quantity * ratio)
                    lot.cost_basis = lot.cost_basis / ratio
                
                # Record update
                update = PositionUpdate(
                    timestamp=ex_date,
                    update_type='SPLIT',
                    quantity_change=position.quantity - old_quantity,
                    price=position.average_cost,
                    metadata={'ratio': float(ratio), 'action_type': action_type}
                )
                position.updates.append(update)
                
                logger.info(
                    f"Processed {action_type} for {symbol}: "
                    f"{old_quantity} @ ${old_avg_cost} -> "
                    f"{position.quantity} @ ${position.average_cost}"
                )
    
    async def export_positions(self) -> str:
        """Export all positions to JSON."""
        positions_data = {
            symbol: pos.to_dict() 
            for symbol, pos in self._positions.items()
        }
        
        return json.dumps({
            'positions': positions_data,
            'daily_metrics': {
                'daily_pnl': str(await self.get_daily_pnl()),
                'daily_realized_pnl': str(self._daily_realized_pnl),
                'daily_commission': str(self._daily_commission),
                'reset_date': self._daily_reset_time.isoformat()
            },
            'export_time': datetime.now(timezone.utc).isoformat()
        }, indent=2)
    
    async def _persist_position(self, position: Position):
        """Persist position to database."""
        if self.database:
            try:
                # Implementation would depend on database interface
                pass
            except Exception as e:
                logger.error(f"Failed to persist position {position.symbol}: {e}")
    
    async def _check_daily_reset(self):
        """Check if daily metrics need reset."""
        today = datetime.now(timezone.utc).date()
        if today > self._daily_reset_time:
            self._daily_realized_pnl = Decimal("0")
            self._daily_commission = Decimal("0")
            self._daily_reset_time = today
            logger.info("Daily position metrics reset")
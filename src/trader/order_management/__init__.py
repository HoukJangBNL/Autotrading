"""
Order Management System (OMS) for Charles Schwab Automated Trading System.

This module provides a comprehensive order management solution with:
- State machine-based order lifecycle management
- Pre-trade risk validation
- Real-time position tracking
- Smart order routing
- Complete audit trail
"""

from .order import Order, OrderState, OrderType, OrderSide, Fill
from .order_service import OrderService, OrderStateMachine
from .risk_validator import (
    PreTradeRiskValidator,
    RiskCheckResult,
    ValidationResult,
    RiskConfig
)
from .position_tracker import (
    PositionTracker,
    Position,
    PositionUpdate,
    PnLCalculator,
    CostBasisMethod
)

__all__ = [
    # Order types
    'Order',
    'OrderState',
    'OrderType',
    'OrderSide',
    'Fill',
    
    # Order service
    'OrderService',
    'OrderStateMachine',
    
    # Risk validation
    'PreTradeRiskValidator',
    'RiskCheckResult',
    'ValidationResult',
    'RiskConfig',
    
    # Position tracking
    'PositionTracker',
    'Position',
    'PositionUpdate',
    'PnLCalculator',
    'CostBasisMethod',
]

__version__ = '1.0.0'
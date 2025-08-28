"""Strategies router for strategy management endpoints."""

import logging
from typing import List, Dict, Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session

from ...data.database import get_db
from ...strategy.base import BaseStrategy
from ...strategy.example_strategies import (
    MovingAverageCrossStrategy,
    RSIMeanReversionStrategy,
    BollingerBandStrategy
)
from ..schemas.strategy import (
    StrategyCreate,
    StrategyUpdate,
    StrategyResponse,
    StrategyListResponse,
    StrategyPerformance
)
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Strategy registry - maps strategy types to classes
STRATEGY_REGISTRY = {
    "moving_average_cross": MovingAverageCrossStrategy,
    "rsi_mean_reversion": RSIMeanReversionStrategy,
    "bollinger_band": BollingerBandStrategy,
}


# In-memory strategy storage (replace with database in production)
strategies_store: Dict[str, Dict[str, Any]] = {}


@router.get("/", response_model=List[StrategyListResponse])
async def list_strategies(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[StrategyListResponse]:
    """
    List all available strategies.
    
    Returns both user-created and example strategies.
    """
    try:
        strategies = []
        
        # Add registered strategy types
        for strategy_type, strategy_class in STRATEGY_REGISTRY.items():
            strategies.append(StrategyListResponse(
                id=strategy_type,
                name=strategy_class.__name__,
                type=strategy_type,
                description=strategy_class.__doc__ or "No description available",
                is_active=False,
                is_example=True
            ))
        
        # Add user strategies from store
        for strategy_id, strategy_data in strategies_store.items():
            strategies.append(StrategyListResponse(
                id=strategy_id,
                name=strategy_data["name"],
                type=strategy_data["type"],
                description=strategy_data.get("description", ""),
                is_active=strategy_data.get("is_active", False),
                is_example=False
            ))
        
        return strategies
        
    except Exception as e:
        logger.error(f"Failed to list strategies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve strategies"
        )


@router.post("/", response_model=StrategyResponse)
async def create_strategy(
    strategy: StrategyCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> StrategyResponse:
    """
    Create a new strategy configuration.
    
    Creates an instance of a strategy with custom parameters.
    """
    try:
        # Validate strategy type
        if strategy.type not in STRATEGY_REGISTRY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown strategy type: {strategy.type}"
            )
        
        # Generate unique ID
        strategy_id = str(uuid4())
        
        # Create strategy instance to validate parameters
        strategy_class = STRATEGY_REGISTRY[strategy.type]
        try:
            strategy_instance = strategy_class(
                symbols=strategy.symbols,
                **strategy.parameters
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid strategy parameters: {str(e)}"
            )
        
        # Store strategy configuration
        strategy_data = {
            "id": strategy_id,
            "name": strategy.name,
            "type": strategy.type,
            "description": strategy.description,
            "symbols": strategy.symbols,
            "parameters": strategy.parameters,
            "is_active": False,
            "created_at": datetime.now(),
            "performance": {
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0
            }
        }
        
        strategies_store[strategy_id] = strategy_data
        
        return StrategyResponse(**strategy_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create strategy"
        )


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> StrategyResponse:
    """
    Get strategy details by ID.
    
    Returns full strategy configuration and performance metrics.
    """
    try:
        if strategy_id not in strategies_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy not found: {strategy_id}"
            )
        
        return StrategyResponse(**strategies_store[strategy_id])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve strategy"
        )


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: str,
    update: StrategyUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> StrategyResponse:
    """
    Update strategy configuration.
    
    Can update name, description, symbols, or parameters.
    """
    try:
        if strategy_id not in strategies_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy not found: {strategy_id}"
            )
        
        strategy_data = strategies_store[strategy_id]
        
        # Don't allow updating active strategies
        if strategy_data.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update an active strategy. Please stop it first."
            )
        
        # Update fields
        if update.name is not None:
            strategy_data["name"] = update.name
        if update.description is not None:
            strategy_data["description"] = update.description
        if update.symbols is not None:
            strategy_data["symbols"] = update.symbols
        if update.parameters is not None:
            # Validate new parameters
            strategy_class = STRATEGY_REGISTRY[strategy_data["type"]]
            try:
                strategy_instance = strategy_class(
                    symbols=strategy_data["symbols"],
                    **update.parameters
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid strategy parameters: {str(e)}"
                )
            strategy_data["parameters"] = update.parameters
        
        strategy_data["updated_at"] = datetime.now()
        
        return StrategyResponse(**strategy_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update strategy"
        )


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Delete a strategy.
    
    Cannot delete active strategies.
    """
    try:
        if strategy_id not in strategies_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy not found: {strategy_id}"
            )
        
        strategy_data = strategies_store[strategy_id]
        
        # Don't allow deleting active strategies
        if strategy_data.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete an active strategy. Please stop it first."
            )
        
        del strategies_store[strategy_id]
        
        return {"message": f"Strategy {strategy_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete strategy"
        )


@router.post("/{strategy_id}/start")
async def start_strategy(
    strategy_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Start running a strategy.
    
    Activates the strategy for live trading or paper trading.
    """
    try:
        if strategy_id not in strategies_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy not found: {strategy_id}"
            )
        
        strategy_data = strategies_store[strategy_id]
        
        if strategy_data.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Strategy is already active"
            )
        
        # TODO: Actually start the strategy instance
        # This would involve:
        # 1. Creating strategy instance
        # 2. Connecting to streaming data
        # 3. Starting signal generation
        
        strategy_data["is_active"] = True
        strategy_data["started_at"] = datetime.now()
        
        return {"message": f"Strategy {strategy_id} started successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start strategy"
        )


@router.post("/{strategy_id}/stop")
async def stop_strategy(
    strategy_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Stop a running strategy.
    
    Deactivates the strategy and closes any open positions.
    """
    try:
        if strategy_id not in strategies_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy not found: {strategy_id}"
            )
        
        strategy_data = strategies_store[strategy_id]
        
        if not strategy_data.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Strategy is not active"
            )
        
        # TODO: Actually stop the strategy instance
        # This would involve:
        # 1. Stopping signal generation
        # 2. Closing open positions (optional)
        # 3. Disconnecting from streaming data
        
        strategy_data["is_active"] = False
        strategy_data["stopped_at"] = datetime.now()
        
        return {"message": f"Strategy {strategy_id} stopped successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop strategy"
        )


@router.get("/{strategy_id}/performance", response_model=StrategyPerformance)
async def get_strategy_performance(
    strategy_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> StrategyPerformance:
    """
    Get strategy performance metrics.
    
    Returns detailed performance statistics and trade history.
    """
    try:
        if strategy_id not in strategies_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy not found: {strategy_id}"
            )
        
        strategy_data = strategies_store[strategy_id]
        
        # TODO: Get actual performance from database
        # For now, return mock data
        return StrategyPerformance(
            strategy_id=strategy_id,
            total_trades=strategy_data["performance"]["total_trades"],
            winning_trades=0,
            losing_trades=0,
            win_rate=strategy_data["performance"]["win_rate"],
            total_pnl=strategy_data["performance"]["total_pnl"],
            average_win=0,
            average_loss=0,
            largest_win=0,
            largest_loss=0,
            sharpe_ratio=strategy_data["performance"]["sharpe_ratio"],
            sortino_ratio=0,
            max_drawdown=strategy_data["performance"]["max_drawdown"],
            profit_factor=0,
            average_trade_duration=0,
            trades=[]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get strategy performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve performance"
        )


# Import datetime at the top of the file
from datetime import datetime
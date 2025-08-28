"""Account API endpoints."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from ...trading.account_service import get_account_service
from ...auth import get_auth_service
from ..dependencies import get_current_user
from ..schemas.account import (
    AccountInfoResponse,
    AccountBalanceResponse,
    AccountListResponse,
    PositionResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=AccountListResponse)
async def get_accounts(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AccountListResponse:
    """
    Get all linked accounts.
    
    Returns list of account numbers and hashes.
    """
    try:
        account_service = get_account_service()
        accounts = await account_service.get_account_numbers()
        
        return AccountListResponse(
            accounts=accounts,
            count=len(accounts)
        )
        
    except Exception as e:
        logger.error(f"Failed to get accounts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{account_hash}", response_model=AccountBalanceResponse)
async def get_account_info(
    account_hash: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AccountBalanceResponse:
    """
    Get detailed account information.
    
    Args:
        account_hash: Account hash identifier
        
    Returns:
        Account balance and details
    """
    try:
        account_service = get_account_service()
        account_info = await account_service.get_account_info(account_hash)
        
        return AccountBalanceResponse(
            accountNumber=account_info.account_number,
            accountHash=account_info.account_hash,
            accountType=account_info.account_type,
            cashBalance=float(account_info.cash_balance),
            totalValue=float(account_info.total_value),
            buyingPower=float(account_info.buying_power),
            marginBalance=float(account_info.margin_balance) if account_info.margin_balance else None,
            shortBalance=float(account_info.short_balance) if account_info.short_balance else None,
            cashAvailableForWithdrawal=float(account_info.cash_available_for_withdrawal) if account_info.cash_available_for_withdrawal else None,
            cashAvailableForTrading=float(account_info.cash_available_for_trading) if account_info.cash_available_for_trading else None,
            maintenanceRequirement=float(account_info.maintenance_requirement) if account_info.maintenance_requirement else None,
            dayTradingBuyingPower=float(account_info.day_trading_buying_power) if account_info.day_trading_buying_power else None,
            lastUpdate=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/all/details", response_model=List[AccountBalanceResponse])
async def get_all_accounts_details(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[AccountBalanceResponse]:
    """
    Get detailed information for all linked accounts.
    
    Returns:
        List of account details with balances
    """
    try:
        account_service = get_account_service()
        accounts = await account_service.get_all_accounts()
        
        response = []
        for account in accounts:
            response.append(AccountBalanceResponse(
                accountNumber=account.account_number,
                accountHash=account.account_hash,
                accountType=account.account_type,
                cashBalance=float(account.cash_balance),
                totalValue=float(account.total_value),
                buyingPower=float(account.buying_power),
                marginBalance=float(account.margin_balance) if account.margin_balance else None,
                shortBalance=float(account.short_balance) if account.short_balance else None,
                cashAvailableForWithdrawal=float(account.cash_available_for_withdrawal) if account.cash_available_for_withdrawal else None,
                cashAvailableForTrading=float(account.cash_available_for_trading) if account.cash_available_for_trading else None,
                maintenanceRequirement=float(account.maintenance_requirement) if account.maintenance_requirement else None,
                dayTradingBuyingPower=float(account.day_trading_buying_power) if account.day_trading_buying_power else None,
                lastUpdate=datetime.utcnow().isoformat()
            ))
            
        return response
        
    except Exception as e:
        logger.error(f"Failed to get all accounts details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{account_hash}/positions", response_model=List[PositionResponse])
async def get_account_positions(
    account_hash: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[PositionResponse]:
    """
    Get all positions for an account.
    
    Args:
        account_hash: Account hash identifier
        
    Returns:
        List of positions
    """
    try:
        account_service = get_account_service()
        positions = await account_service.get_positions(account_hash)
        
        response = []
        for pos in positions:
            response.append(PositionResponse(
                symbol=pos.symbol,
                quantity=float(pos.quantity),
                averageCost=float(pos.average_cost),
                currentPrice=float(pos.current_price),
                marketValue=float(pos.market_value),
                unrealizedPnl=float(pos.unrealized_pnl),
                unrealizedPnlPercent=float(pos.unrealized_pnl_percent),
                realizedPnl=float(pos.realized_pnl),
                assetType=pos.asset_type,
                positionType=pos.position_type
            ))
            
        return response
        
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/refresh")
async def refresh_account_data(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Refresh all account and position data.
    
    Returns:
        Updated account and position information
    """
    try:
        account_service = get_account_service()
        result = await account_service.refresh_all_data()
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to refresh account data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
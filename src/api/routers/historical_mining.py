"""Historical Data Mining API Router."""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Optional, Dict
from datetime import datetime
import asyncio
from src.utils.logger import get_logger
from src.auth import get_auth_service
from src.services.mining_orchestrator import MiningOrchestrator
from src.data.historical_data_collector import HistoricalDataCollector

logger = get_logger(__name__)

router = APIRouter(prefix="/api/historical-mining", tags=["historical-mining"])

# Global orchestrator instance
orchestrator: Optional[MiningOrchestrator] = None


@router.post("/start")
async def start_historical_mining(
    background_tasks: BackgroundTasks,
    phase: int = Query(1, ge=1, le=4, description="Mining phase (1-4)"),
    symbols: Optional[List[str]] = None
):
    """Start historical data mining."""
    global orchestrator
    
    try:
        # Check if already running
        if orchestrator and orchestrator.is_running:
            return {
                "status": "already_running",
                "message": "Mining is already in progress",
                "current_status": orchestrator.get_status()
            }
        
        # Get authenticated client
        auth_service = get_auth_service()
        client = await auth_service.get_authenticated_client()
        if not client:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Create new orchestrator
        orchestrator = MiningOrchestrator(client)
        orchestrator.current_phase = phase
        
        # If specific symbols provided, override phase symbols
        if symbols:
            orchestrator.symbols_queue = symbols
            logger.info(f"Starting mining for {len(symbols)} specified symbols")
        
        # Start mining in background
        background_tasks.add_task(orchestrator.execute_mining)
        
        return {
            "status": "started",
            "phase": phase,
            "message": f"Started historical data mining for phase {phase}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to start historical mining: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_historical_mining():
    """Stop historical data mining."""
    global orchestrator
    
    if not orchestrator:
        return {
            "status": "not_running",
            "message": "No mining operation is running"
        }
    
    await orchestrator.stop_mining()
    final_status = orchestrator.get_status()
    
    return {
        "status": "stopped",
        "message": "Mining operation stopped",
        "final_status": final_status,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/status")
async def get_mining_status():
    """Get current mining status."""
    global orchestrator
    
    if not orchestrator:
        return {
            "status": "idle",
            "message": "No mining operation has been started",
            "is_running": False
        }
    
    return orchestrator.get_status()


@router.get("/collection-status")
async def get_collection_status():
    """Get overall data collection status."""
    try:
        auth_service = get_auth_service()
        client = await auth_service.get_authenticated_client()
        if not client:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        collector = HistoricalDataCollector(client)
        status = await collector.get_collection_status()
        
        return {
            "status": "success",
            "data": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get collection status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collect-symbol")
async def collect_single_symbol(
    symbol: str,
    days_back: int = Query(60, ge=1, le=365, description="Days of history to collect")
):
    """Collect historical data for a single symbol."""
    try:
        auth_service = get_auth_service()
        client = await auth_service.get_authenticated_client()
        if not client:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        collector = HistoricalDataCollector(client)
        result = await collector.collect_historical_data(
            symbol=symbol.upper(),
            days_back=days_back,
            operation="manual"
        )
        
        return {
            "status": "success" if result['success'] else "failed",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to collect data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fill-gaps/{symbol}")
async def fill_symbol_gaps(symbol: str):
    """Fill data gaps for a specific symbol."""
    try:
        auth_service = get_auth_service()
        client = await auth_service.get_authenticated_client()
        if not client:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        collector = HistoricalDataCollector(client)
        
        # Detect gaps
        gaps = await collector.detect_gaps(symbol.upper())
        
        if not gaps:
            return {
                "status": "no_gaps",
                "message": f"No gaps detected for {symbol}",
                "symbol": symbol.upper()
            }
        
        # Fill gaps
        filled_count = await collector.fill_gaps(symbol.upper())
        
        return {
            "status": "success",
            "symbol": symbol.upper(),
            "gaps_detected": len(gaps),
            "candles_filled": filled_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to fill gaps for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry-failed")
async def retry_failed_symbols(background_tasks: BackgroundTasks):
    """Retry collection for failed symbols."""
    global orchestrator
    
    if not orchestrator:
        return {
            "status": "error",
            "message": "No previous mining operation found"
        }
    
    if orchestrator.is_running:
        return {
            "status": "error",
            "message": "Mining is currently running"
        }
    
    if not orchestrator.failed_symbols:
        return {
            "status": "no_failures",
            "message": "No failed symbols to retry"
        }
    
    # Retry in background
    background_tasks.add_task(orchestrator.retry_failed)
    
    return {
        "status": "started",
        "message": f"Retrying {len(orchestrator.failed_symbols)} failed symbols",
        "symbols": list(orchestrator.failed_symbols),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/phases")
async def get_mining_phases():
    """Get information about mining phases."""
    return {
        "phases": [
            {
                "phase": 1,
                "name": "Core Tickers",
                "description": "30-50 high liquidity stocks and major ETFs",
                "estimated_symbols": 15,
                "status": "active"
            },
            {
                "phase": 2,
                "name": "S&P 100",
                "description": "Expand to S&P 100 components",
                "estimated_symbols": 100,
                "status": "planned"
            },
            {
                "phase": 3,
                "name": "NASDAQ 100",
                "description": "Add NASDAQ 100 components",
                "estimated_symbols": 100,
                "status": "planned"
            },
            {
                "phase": 4,
                "name": "Dynamic Expansion",
                "description": "Expand based on volume and volatility",
                "estimated_symbols": "500+",
                "status": "future"
            }
        ],
        "current_phase": orchestrator.current_phase if orchestrator else 1
    }
"""Data Mining API Router for real-time market data collection."""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
from src.utils.logger import get_logger
from src.auth import get_auth_service
from src.data.market_data_collector import MarketDataCollector
import json

logger = get_logger(__name__)

router = APIRouter(prefix="/api/data-mining", tags=["data-mining"])

# Global collector instance
data_collector: Optional[MarketDataCollector] = None


class DataMiningService:
    """Service for managing data mining operations."""
    
    def __init__(self):
        self.is_running = False
        self.symbols = []
        self.collection_stats = {
            "total_points": 0,
            "api_calls": 0,
            "errors": 0,
            "last_update": None
        }
        self.collector = None
        
    async def start_mining(self, symbols: List[str], interval: int = 5):
        """Start data mining for specified symbols."""
        if self.is_running:
            return {"status": "already_running", "symbols": self.symbols}
            
        try:
            auth_service = get_auth_service()
            client = await auth_service.get_authenticated_client()
            if not client:
                raise HTTPException(status_code=401, detail="Authentication required")
                
            self.collector = MarketDataCollector(client)
            self.symbols = symbols
            self.is_running = True
            
            # Start background collection
            asyncio.create_task(self._collect_loop(interval))
            
            logger.info(f"Started data mining for {len(symbols)} symbols")
            return {
                "status": "started",
                "symbols": symbols,
                "interval": interval,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to start data mining: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _collect_loop(self, interval: int):
        """Background loop for data collection."""
        while self.is_running:
            try:
                # Collect data for all symbols
                for symbol in self.symbols:
                    try:
                        data = await self.collector.collect_quote(symbol)
                        self.collection_stats["total_points"] += 1
                        self.collection_stats["api_calls"] += 1
                        self.collection_stats["last_update"] = datetime.now().isoformat()
                    except Exception as e:
                        logger.error(f"Error collecting data for {symbol}: {e}")
                        self.collection_stats["errors"] += 1
                        
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Collection loop error: {e}")
                await asyncio.sleep(interval)
    
    async def stop_mining(self):
        """Stop data mining operations."""
        self.is_running = False
        result = {
            "status": "stopped",
            "stats": self.collection_stats,
            "timestamp": datetime.now().isoformat()
        }
        logger.info("Stopped data mining")
        return result
    
    def get_status(self):
        """Get current mining status."""
        return {
            "is_running": self.is_running,
            "symbols": self.symbols,
            "stats": self.collection_stats,
            "timestamp": datetime.now().isoformat()
        }

# Initialize service
mining_service = DataMiningService()


@router.post("/start")
async def start_data_mining(
    symbols: List[str],
    interval: int = Query(5, ge=1, le=60, description="Collection interval in seconds")
):
    """Start data mining for specified symbols."""
    if not symbols:
        # Default to current portfolio symbols
        try:
            auth_service = get_auth_service()
            client = await auth_service.get_authenticated_client()
            if client:
                # Get account positions
                accounts = await auth_service.get_account_numbers()
                if accounts:
                    account_hash = accounts[0]
                    from schwab.client import Client
                    response = client.get_account(account_hash, fields=[Client.Account.Fields.POSITIONS])
                
                if response.status_code == 200:
                    account_data = response.json()
                    positions = account_data.get('securitiesAccount', {}).get('positions', [])
                    symbols = [pos['instrument']['symbol'] for pos in positions]
                    logger.info(f"Using {len(symbols)} portfolio symbols for data mining")
        except Exception as e:
            logger.error(f"Failed to get portfolio symbols: {e}")
            symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']  # Default symbols
    
    result = await mining_service.start_mining(symbols, interval)
    return result


@router.post("/stop")
async def stop_data_mining():
    """Stop data mining operations."""
    result = await mining_service.stop_mining()
    return result


@router.get("/status")
async def get_mining_status():
    """Get current data mining status."""
    return mining_service.get_status()


@router.get("/symbols")
async def get_mining_symbols():
    """Get list of symbols being mined."""
    return {
        "symbols": mining_service.symbols,
        "count": len(mining_service.symbols),
        "is_running": mining_service.is_running
    }


@router.post("/symbols/add")
async def add_mining_symbols(symbols: List[str]):
    """Add symbols to mining list."""
    if not mining_service.is_running:
        raise HTTPException(status_code=400, detail="Data mining is not running")
    
    new_symbols = list(set(symbols) - set(mining_service.symbols))
    mining_service.symbols.extend(new_symbols)
    
    return {
        "added": new_symbols,
        "total_symbols": len(mining_service.symbols),
        "all_symbols": mining_service.symbols
    }


@router.post("/symbols/remove")
async def remove_mining_symbols(symbols: List[str]):
    """Remove symbols from mining list."""
    if not mining_service.is_running:
        raise HTTPException(status_code=400, detail="Data mining is not running")
    
    mining_service.symbols = [s for s in mining_service.symbols if s not in symbols]
    
    return {
        "removed": symbols,
        "total_symbols": len(mining_service.symbols),
        "remaining_symbols": mining_service.symbols
    }


@router.get("/stats")
async def get_mining_stats():
    """Get detailed mining statistics."""
    stats = mining_service.collection_stats.copy()
    
    # Add more detailed stats
    if mining_service.is_running and mining_service.collection_stats["last_update"]:
        last_update = datetime.fromisoformat(mining_service.collection_stats["last_update"])
        stats["uptime_seconds"] = (datetime.now() - last_update).total_seconds()
        stats["points_per_minute"] = (
            stats["total_points"] / (stats["uptime_seconds"] / 60)
            if stats["uptime_seconds"] > 0 else 0
        )
        stats["error_rate"] = (
            stats["errors"] / stats["api_calls"] * 100
            if stats["api_calls"] > 0 else 0
        )
    
    return stats


@router.get("/data/{symbol}")
async def get_symbol_data(
    symbol: str,
    period: str = Query("1d", description="Time period: 1d, 5d, 1m, 3m, 6m, 1y")
):
    """Get collected data for a specific symbol."""
    try:
        client = await auth_service.get_authenticated_client()
        if not client:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get price history
        end_date = datetime.now()
        
        period_map = {
            "1d": 1,
            "5d": 5,
            "1m": 30,
            "3m": 90,
            "6m": 180,
            "1y": 365
        }
        
        days = period_map.get(period, 1)
        start_date = end_date - timedelta(days=days)
        
        # For now, just get current quote
        response = client.get_quote(symbol)
        
        if response.status_code == 200:
            quote_data = response.json()
            return {
                "symbol": symbol,
                "period": period,
                "current_data": quote_data,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to get data")
            
    except Exception as e:
        logger.error(f"Failed to get data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
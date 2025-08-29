"""Enhanced Historical Data Mining API Router with multi-phase support."""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Optional, Dict
from datetime import datetime
import asyncio
from src.utils.logger import get_logger
from src.auth import get_auth_service
from src.api.routers.auth import get_schwab_auth
from src.services.mining_orchestrator_v2 import EnhancedMiningOrchestrator, PhaseManager
from src.data.historical_data_collector_v2 import EnhancedHistoricalDataCollector
from src.models.mining_mode import MiningMode, MiningModeConfig

logger = get_logger(__name__)

router = APIRouter(prefix="/api/mining/v2", tags=["mining-v2"])

# Global orchestrator instance
orchestrator: Optional[EnhancedMiningOrchestrator] = None


@router.post("/start-with-mode")
async def start_mining_with_mode(
    background_tasks: BackgroundTasks,
    mode: str = Query("auto", description="Mining mode: gap_filling, expansion, or auto"),
    days_back: int = Query(60, ge=1, le=365, description="Days of history"),
    gap_filling_first: bool = Query(True, description="In auto mode, start with gap filling"),
    switch_on_completion: bool = Query(True, description="In auto mode, switch modes on completion"),
):
    """Start mining with specific mode configuration."""
    global orchestrator
    
    try:
        # Validate mode
        try:
            mining_mode = MiningMode(mode)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}. Must be gap_filling, expansion, or auto")
        
        # Check if already running
        if orchestrator and orchestrator.is_running:
            return {
                "status": "already_running",
                "message": "Mining is already in progress",
                "current_status": orchestrator.get_detailed_status()
            }
        
        # Get authenticated client from schwab_auth_flow directly
        try:
            schwab_auth = get_schwab_auth()
            client = schwab_auth.get_client()
            if not client:
                # Try auth_service as fallback
                auth_service = get_auth_service()
                client = await auth_service.ensure_authenticated()
                if not client:
                    raise HTTPException(status_code=401, detail="Authentication required")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
        
        # Create mode configuration
        mode_config = MiningModeConfig(
            mode=mining_mode,
            lookback_days=days_back,
            gap_filling_first=gap_filling_first,
            switch_on_completion=switch_on_completion
        )
        
        # Create new orchestrator with mode config
        orchestrator = EnhancedMiningOrchestrator(client, mode_config)
        
        # Get symbols from phase manager (use phase 1 for now)
        phase_manager = PhaseManager()
        symbols = phase_manager.get_symbols_for_phase(1, cumulative=True)
        
        # Start mining in background
        background_tasks.add_task(
            orchestrator.execute_mining_with_modes,
            symbols,
            days_back
        )
        
        return {
            "status": "started",
            "message": f"Started mining in {mode} mode",
            "mode_config": {
                "mode": mining_mode.value,
                "gap_filling_first": gap_filling_first,
                "switch_on_completion": switch_on_completion,
                    "lookback_days": days_back
                },
                "symbols_count": len(symbols),
                "timestamp": datetime.now().isoformat()
            }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Failed to start mining with mode: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switch-mode")
async def switch_mining_mode():
    """Manually switch mining mode during operation."""
    global orchestrator
    
    if not orchestrator:
        raise HTTPException(status_code=400, detail="No mining operation is running")
    
    if not orchestrator.is_running:
        raise HTTPException(status_code=400, detail="Mining is not currently running")
    
    if orchestrator.mining_session.config.mode != MiningMode.AUTO:
        raise HTTPException(status_code=400, detail="Mode switching is only available in AUTO mode")
    
    # Switch the mode
    old_mode = orchestrator.mining_session.current_mode.value
    orchestrator.mining_session.switch_mode()
    new_mode = orchestrator.mining_session.current_mode.value
    
    return {
        "status": "switched",
        "previous_mode": old_mode,
        "current_mode": new_mode,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/mode-status")
async def get_mining_mode_status():
    """Get current mining mode and configuration."""
    global orchestrator
    
    if not orchestrator:
        return {
            "status": "idle",
            "message": "No mining operation has been started"
        }
    
    session_stats = orchestrator.mining_session.get_session_stats()
    
    return {
        "is_running": orchestrator.is_running,
        "current_mode": orchestrator.mining_session.current_mode.value,
        "configuration": {
            "mode": orchestrator.mode_config.mode.value,
            "gap_filling_first": orchestrator.mode_config.gap_filling_first,
            "switch_on_completion": orchestrator.mode_config.switch_on_completion,
            "lookback_days": orchestrator.mode_config.lookback_days
        },
        "session": session_stats
    }


@router.post("/start-multi-phase")
async def start_multi_phase_mining(
    background_tasks: BackgroundTasks,
    start_phase: int = Query(1, ge=1, le=3, description="Starting phase"),
    end_phase: int = Query(3, ge=1, le=3, description="Ending phase"),
    days_back: int = Query(60, ge=1, le=365, description="Days of history"),
):
    """Start multi-phase historical data mining."""
    global orchestrator
    
    try:
        # Validate phase range
        if start_phase > end_phase:
            raise HTTPException(status_code=400, detail="Start phase must be <= end phase")
        
        # Check if already running
        if orchestrator and orchestrator.is_running:
            return {
                "status": "already_running",
                "message": "Mining is already in progress",
                "current_status": orchestrator.get_detailed_status()
            }
        
        # Get authenticated client from schwab_auth_flow directly
        try:
            schwab_auth = get_schwab_auth()
            client = schwab_auth.get_client()
            if not client:
                # Try auth_service as fallback
                auth_service = get_auth_service()
                client = await auth_service.ensure_authenticated()
                if not client:
                    raise HTTPException(status_code=401, detail="Authentication required")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
        
        # Create new orchestrator
        orchestrator = EnhancedMiningOrchestrator(client)
        
        # Start mining in background
        background_tasks.add_task(
            orchestrator.execute_multi_phase_mining,
            start_phase,
            end_phase,
            days_back
        )
        
        # Get phase information
        phase_manager = PhaseManager()
        phase_stats = phase_manager.get_phase_stats()
        
        total_symbols = 0
        for phase in range(start_phase, end_phase + 1):
            total_symbols += phase_stats[phase]['cumulative_symbols']
        
        return {
            "status": "started",
            "message": f"Started mining phases {start_phase} to {end_phase}",
            "phases": phase_stats,
            "estimated_symbols": total_symbols,
            "days_back": days_back,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to start multi-phase mining: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/detailed")
async def get_detailed_mining_status():
    """Get detailed mining status with progress and quality metrics."""
    global orchestrator
    
    if not orchestrator:
        return {
            "status": "idle",
            "message": "No mining operation has been started",
            "is_running": False
        }
    
    status = orchestrator.get_detailed_status()
    
    # Add additional context
    status['api_health'] = {
        'authenticated': True,  # Would check actual auth status
        'rate_limit_remaining': 100,  # Would get from rate limiter
        'database_connected': True  # Would check DB connection
    }
    
    return status


@router.get("/phases/info")
async def get_phase_information():
    """Get detailed information about all mining phases."""
    phase_manager = PhaseManager()
    
    phase_info = phase_manager.get_phase_stats()
    
    # Add symbol lists for each phase
    detailed_info = {}
    for phase in [1, 2, 3]:
        symbols = phase_manager.get_symbols_for_phase(phase, cumulative=False)
        detailed_info[phase] = {
            **phase_info[phase],
            "symbols": sorted(symbols)[:10],  # Show first 10 symbols
            "total_symbols": len(symbols)
        }
    
    return {
        "phases": detailed_info,
        "total_unique_symbols": len(
            phase_manager.get_symbols_for_phase(3, cumulative=True)
        ),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/stop")
async def stop_mining():
    """Stop mining operations gracefully."""
    global orchestrator
    
    if not orchestrator:
        return {
            "status": "not_running",
            "message": "No mining operation is running"
        }
    
    if not orchestrator.is_running:
        return {
            "status": "already_stopped",
            "message": "Mining operation is not running"
        }
    
    await orchestrator.stop_mining()
    final_status = orchestrator.get_detailed_status()
    
    return {
        "status": "stopped",
        "message": "Mining operation stopped gracefully",
        "final_status": final_status,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/quality/report")
async def get_quality_report():
    """Get data quality report for mined symbols."""
    from sqlalchemy import create_engine, select, func
    from sqlalchemy.orm import Session
    from src.models.market_data import MiningStatus, Candle1Min
    import os
    
    try:
        db_url = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_pass@localhost/trading_dev")
        engine = create_engine(db_url)
        
        with Session(engine) as session:
            # Get quality statistics
            quality_stats = session.execute(
                select(
                    func.count(MiningStatus.id).label('total_symbols'),
                    func.avg(MiningStatus.data_quality_score).label('avg_quality'),
                    func.min(MiningStatus.data_quality_score).label('min_quality'),
                    func.max(MiningStatus.data_quality_score).label('max_quality'),
                    func.sum(MiningStatus.gaps_detected).label('total_gaps'),
                    func.sum(MiningStatus.total_candles).label('total_candles')
                )
            ).one()
            
            # Get low quality symbols
            low_quality = session.execute(
                select(MiningStatus.symbol, MiningStatus.data_quality_score)
                .where(MiningStatus.data_quality_score < 80)
                .order_by(MiningStatus.data_quality_score)
                .limit(10)
            ).all()
            
            # Get symbols with most gaps
            gap_symbols = session.execute(
                select(MiningStatus.symbol, MiningStatus.gaps_detected)
                .where(MiningStatus.gaps_detected > 0)
                .order_by(MiningStatus.gaps_detected.desc())
                .limit(10)
            ).all()
            
            # Get phase distribution
            phase_dist = session.execute(
                select(
                    MiningStatus.phase,
                    func.count(MiningStatus.id).label('count')
                )
                .group_by(MiningStatus.phase)
            ).all()
        
        return {
            "summary": {
                "total_symbols": quality_stats.total_symbols or 0,
                "average_quality": float(quality_stats.avg_quality or 0),
                "min_quality": float(quality_stats.min_quality or 0),
                "max_quality": float(quality_stats.max_quality or 0),
                "total_gaps": quality_stats.total_gaps or 0,
                "total_candles": quality_stats.total_candles or 0
            },
            "low_quality_symbols": [
                {"symbol": s.symbol, "score": float(s.data_quality_score)}
                for s in low_quality
            ],
            "symbols_with_gaps": [
                {"symbol": s.symbol, "gaps": s.gaps_detected}
                for s in gap_symbols
            ],
            "phase_distribution": {
                p.phase: p.count for p in phase_dist
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to generate quality report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-symbol")
async def validate_symbol_data(symbol: str):
    """Validate data quality for a specific symbol."""
    try:
        # Get authenticated client from schwab_auth_flow directly
        try:
            schwab_auth = get_schwab_auth()
            client = schwab_auth.get_client()
            if not client:
                # Try auth_service as fallback
                auth_service = get_auth_service()
                client = await auth_service.ensure_authenticated()
                if not client:
                    raise HTTPException(status_code=401, detail="Authentication required")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
        
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import Session
        from src.models.market_data import Candle1Min
        from src.data.historical_data_collector_v2 import DataValidator
        import os
        
        db_url = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_pass@localhost/trading_dev")
        engine = create_engine(db_url)
        
        with Session(engine) as session:
            # Get candles for symbol
            candles = session.execute(
                select(Candle1Min)
                .where(Candle1Min.symbol == symbol.upper())
                .order_by(Candle1Min.timestamp)
                .limit(1000)  # Validate last 1000 candles
            ).scalars().all()
            
            if not candles:
                return {
                    "symbol": symbol.upper(),
                    "status": "no_data",
                    "message": "No data found for symbol"
                }
            
            # Convert to dict format for validator
            candle_dicts = [
                {
                    'datetime': int(c.timestamp.timestamp() * 1000),
                    'open': c.open,
                    'high': c.high,
                    'low': c.low,
                    'close': c.close,
                    'volume': c.volume
                }
                for c in candles
            ]
            
            # Validate
            validator = DataValidator()
            quality_score = validator.calculate_quality_score(candle_dicts)
            gaps = validator.detect_market_gaps(candle_dicts)
            
            # Check individual candles
            invalid_candles = []
            for i, candle_dict in enumerate(candle_dicts[:10]):  # Check first 10
                is_valid, reason = validator.validate_candle(candle_dict)
                if not is_valid:
                    invalid_candles.append({
                        'index': i,
                        'reason': reason,
                        'timestamp': candles[i].timestamp.isoformat()
                    })
        
        return {
            "symbol": symbol.upper(),
            "status": "validated",
            "quality_score": quality_score,
            "total_candles": len(candles),
            "gaps_detected": len(gaps),
            "invalid_candles": invalid_candles,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to validate {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/metrics")
async def get_performance_metrics():
    """Get mining performance metrics."""
    from sqlalchemy import create_engine, select, func, and_
    from sqlalchemy.orm import Session
    from src.models.market_data import MiningLog
    from datetime import datetime, timedelta
    import pytz
    import os
    
    try:
        db_url = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_pass@localhost/trading_dev")
        engine = create_engine(db_url)
        
        with Session(engine) as session:
            # Last 24 hours metrics
            yesterday = datetime.now(pytz.UTC) - timedelta(days=1)
            
            recent_stats = session.execute(
                select(
                    func.count(MiningLog.id).label('total_operations'),
                    func.sum(MiningLog.candles_added).label('total_candles'),
                    func.sum(MiningLog.api_calls).label('total_api_calls'),
                    func.avg(
                        func.extract('epoch', MiningLog.end_time - MiningLog.start_time)
                    ).label('avg_duration')
                )
                .where(MiningLog.created_at > yesterday)
            ).one()
            
            # Success rate
            success_count = session.execute(
                select(func.count(MiningLog.id))
                .where(
                    and_(
                        MiningLog.created_at > yesterday,
                        MiningLog.success == True
                    )
                )
            ).scalar()
            
            # Hourly distribution
            hourly_dist = session.execute(
                select(
                    func.date_trunc('hour', MiningLog.created_at).label('hour'),
                    func.count(MiningLog.id).label('count'),
                    func.sum(MiningLog.candles_added).label('candles')
                )
                .where(MiningLog.created_at > yesterday)
                .group_by('hour')
                .order_by('hour')
            ).all()
        
        success_rate = (success_count / recent_stats.total_operations * 100) if recent_stats.total_operations > 0 else 0
        
        return {
            "last_24_hours": {
                "total_operations": recent_stats.total_operations or 0,
                "total_candles": recent_stats.total_candles or 0,
                "total_api_calls": recent_stats.total_api_calls or 0,
                "avg_duration_seconds": float(recent_stats.avg_duration or 0),
                "success_rate": round(success_rate, 2)
            },
            "hourly_distribution": [
                {
                    "hour": h.hour.isoformat() if h.hour else None,
                    "operations": h.count,
                    "candles": h.candles or 0
                }
                for h in hourly_dist
            ],
            "current_status": {
                "is_running": orchestrator.is_running if orchestrator else False,
                "current_phase": orchestrator.current_phase if orchestrator else None
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
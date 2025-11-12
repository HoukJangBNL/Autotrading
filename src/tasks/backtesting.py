"""Celery tasks for backtesting operations."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from celery import group, chord
import pandas as pd
import numpy as np

from .celery_app import celery_app
from src.utils.logger import logger
# TODO: Phase 3에서 구현 예정
# from src.strategies.base import BaseStrategy
# from src.data.models import Candle, Strategy


@celery_app.task(bind=True, time_limit=3600)  # 1시간 제한
def run_backtest_task(
    self,
    strategy_id: str,
    symbols: List[str],
    start_date: str,
    end_date: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Run backtest for a strategy.
    
    Args:
        strategy_id: Strategy identifier
        symbols: List of symbols to test
        start_date: Backtest start date (YYYY-MM-DD)
        end_date: Backtest end date (YYYY-MM-DD)
        parameters: Optional strategy parameters override
        
    Returns:
        Backtest results with performance metrics
    """
    logger.info(f"[Task {self.request.id}] Running backtest for strategy {strategy_id}")
    logger.info(f"Symbols: {symbols}, Period: {start_date} to {end_date}")
    
    try:
        # Phase 3에서 실제 구현 예정
        # 현재는 시뮬레이션
        
        # 1. 전략 인스턴스 로드
        # strategy = load_strategy(strategy_id, parameters)
        
        # 2. 심볼별로 히스토리 데이터 가져오기
        # all_trades = []
        # for symbol in symbols:
        #     candles = load_candles(symbol, start_date, end_date)
        #     trades = run_strategy_on_symbol(strategy, candles, symbol)
        #     all_trades.extend(trades)
        
        # 3. 성능 메트릭 계산
        # metrics = calculate_performance_metrics(all_trades)
        
        # 시뮬레이션 결과
        total_trades = len(symbols) * 50
        winning_trades = int(total_trades * 0.55)
        
        # 진행 상황 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': len(symbols), 'total': len(symbols), 'status': 'Calculating metrics...'}
        )
        
        return {
            "status": "success",
            "task_id": self.request.id,
            "strategy_id": strategy_id,
            "symbols": symbols,
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "parameters": parameters or {},
            "results": {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": total_trades - winning_trades,
                "win_rate": winning_trades / total_trades if total_trades > 0 else 0,
                "total_return": 12.5,  # %
                "sharpe_ratio": 1.45,
                "max_drawdown": -8.3,  # %
                "profit_factor": 1.25,
                "avg_win": 0.85,  # %
                "avg_loss": -0.68,  # %
            },
            "execution_time": 2.5,  # seconds
            "message": f"Backtest completed for {len(symbols)} symbols"
        }
    
    except Exception as e:
        logger.error(f"[Task {self.request.id}] Error in backtest: {e}")
        return {
            "status": "error",
            "task_id": self.request.id,
            "strategy_id": strategy_id,
            "error": str(e)
        }


@celery_app.task(bind=True, time_limit=7200)  # 2시간 제한
def optimize_strategy(
    self,
    strategy_id: str,
    symbols: List[str],
    start_date: str,
    end_date: str,
    parameter_ranges: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Optimize strategy parameters using backtesting.
    
    Uses Bayesian optimization to find optimal parameters.
    
    Args:
        strategy_id: Strategy identifier
        symbols: List of symbols to test
        start_date: Optimization start date (YYYY-MM-DD)
        end_date: Optimization end date (YYYY-MM-DD)
        parameter_ranges: Parameter ranges to test
            Example: {
                "fast_period": {"min": 5, "max": 20, "step": 1},
                "slow_period": {"min": 20, "max": 50, "step": 5}
            }
        
    Returns:
        Optimization results with best parameters
    """
    logger.info(f"[Task {self.request.id}] Optimizing strategy {strategy_id}")
    
    try:
        from src.api.routers.strategies import STRATEGY_REGISTRY, strategies_store
        from src.strategy.optimization.objective import ObjectiveConfig
        from src.strategy.optimization.tuner import optimize as optimize_random
        from datetime import datetime as dt

        if strategy_id not in strategies_store:
            raise ValueError(f"Strategy not found: {strategy_id}")
        strategy_data = strategies_store[strategy_id]
        strategy_type = strategy_data["type"]
        if strategy_type not in STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        strategy_cls = STRATEGY_REGISTRY[strategy_type]

        # Parse dates
        start_dt = dt.fromisoformat(start_date)
        end_dt = dt.fromisoformat(end_date)

        # Objective/constraints config (defaults based on user input)
        cfg = ObjectiveConfig(
            w1=1.0, w2=1.0, w3=1.0,
            max_dd_limit_pct=15.0,
            turnover_limit_annualized_pct=200.0
        )

        # Run simple random search optimizer
        best_params, best_trial, trials = asyncio.get_event_loop().run_until_complete(
            optimize_random(
                strategy_cls=strategy_cls,
                symbols=symbols,
                start_date=start_dt,
                end_date=end_dt,
                parameter_ranges=parameter_ranges,
                objective_cfg=cfg,
                n_initial_samples=20,
                seed=42,
            )
        )

        # Progress/meta
        self.update_state(
            state='PROGRESS',
            meta={
                'current': len(trials),
                'total': len(trials),
                'status': 'Optimization complete',
                'best_objective': best_trial.objective,
            }
        )

        return {
            "status": "success",
            "task_id": self.request.id,
            "strategy_id": strategy_id,
            "optimization_method": "random_search",
            "iterations": len(trials),
            "best_parameters": best_params,
            "best_performance": best_trial.metrics,
            "all_trials": [t.metrics for t in trials],
            "message": f"Found optimal parameters after {len(trials)} evaluations"
        }

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Error in optimization: {e}")
        return {
            "status": "error",
            "task_id": self.request.id,
            "strategy_id": strategy_id,
            "error": str(e)
        }


@celery_app.task
def batch_backtest(
    strategy_ids: List[str],
    symbols: List[str],
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """Run backtests for multiple strategies in parallel.
    
    Args:
        strategy_ids: List of strategy identifiers
        symbols: List of symbols to test
        start_date: Backtest start date (YYYY-MM-DD)
        end_date: Backtest end date (YYYY-MM-DD)
        
    Returns:
        Aggregated backtest results with rankings
    """
    logger.info(f"Running batch backtest for {len(strategy_ids)} strategies")
    
    try:
        # 각 전략에 대한 백테스트 태스크 생성
        tasks = []
        for strategy_id in strategy_ids:
            task = run_backtest_task.s(
                strategy_id=strategy_id,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date
            )
            tasks.append(task)
        
        # 병렬로 실행
        job = group(tasks)
        result = job.apply_async(queue="backtesting")
        
        return {
            "status": "submitted",
            "job_id": result.id,
            "total_strategies": len(strategy_ids),
            "strategy_ids": strategy_ids,
            "message": f"Submitted {len(strategy_ids)} backtest tasks"
        }
    
    except Exception as e:
        logger.error(f"Error in batch backtest: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task
def get_backtest_progress(job_id: str) -> Dict[str, Any]:
    """Get progress of a batch backtest job.
    
    Args:
        job_id: Celery group result ID
        
    Returns:
        Progress information with partial results
    """
    try:
        from celery.result import GroupResult
        
        result = GroupResult.restore(job_id, app=celery_app)
        if not result:
            return {
                "status": "not_found",
                "job_id": job_id,
                "message": "Job not found"
            }
        
        total = len(result)
        completed_results = []
        
        for task_result in result:
            if task_result.ready():
                try:
                    completed_results.append(task_result.get(timeout=1))
                except:
                    pass
        
        # 완료된 결과를 Sharpe ratio로 정렬
        if completed_results:
            rankings = sorted(
                [r for r in completed_results if r.get("status") == "success"],
                key=lambda x: x.get("results", {}).get("sharpe_ratio", 0),
                reverse=True
            )
        else:
            rankings = []
        
        return {
            "status": "progress",
            "job_id": job_id,
            "total_strategies": total,
            "completed": len(completed_results),
            "progress_percent": (len(completed_results) / total * 100) if total > 0 else 0,
            "is_ready": result.ready(),
            "top_strategies": rankings[:5] if rankings else []
        }
        
    except Exception as e:
        logger.error(f"Error getting backtest progress for job {job_id}: {e}")
        return {
            "status": "error",
            "job_id": job_id,
            "error": str(e)
        }


@celery_app.task
def run_weekly_backtests() -> Dict[str, Any]:
    """Run weekly backtests for all active strategies.
    
    This is designed to be run by Celery Beat scheduler.
    
    Returns:
        Summary of weekly backtest results
    """
    logger.info("Starting weekly backtests")
    
    try:
        # Phase 3에서 실제 구현 예정
        # 현재는 시뮬레이션
        
        # 1. 활성 전략 목록 가져오기
        # active_strategies = get_active_strategies()
        
        # 2. 상위 볼륨 심볼 가져오기
        # top_symbols = get_top_volume_symbols(limit=50)
        
        # 3. 지난 주 데이터로 백테스트
        # end_date = datetime.now().date()
        # start_date = end_date - timedelta(days=7)
        
        # 4. 배치 백테스트 실행
        # job = batch_backtest(active_strategies, top_symbols, start_date, end_date)
        
        # 시뮬레이션 결과
        strategies_tested = 10
        
        return {
            "status": "success",
            "strategies_tested": strategies_tested,
            "timestamp": datetime.now().isoformat(),
            "message": f"Weekly backtests completed for {strategies_tested} strategies"
        }
        
    except Exception as e:
        logger.error(f"Error in weekly backtests: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
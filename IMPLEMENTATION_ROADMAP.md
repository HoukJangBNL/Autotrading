# Implementation Roadmap (Priority & Phases)

This plan bridges the current system to the target 3‑mode state‑machine platform. Priorities are chosen to unlock end‑to‑end control first, then data correctness, then optimization and trading.

## Milestone A: Control Plane & State Machine (P0)
1. ModeManager service (backend)
   - States: DataMining, Backtesting, Trading
   - Transitions: set_mode(new_mode), get_state(), with persisted state
   - Publishes state over WS/SSE; exposes metrics
2. Control API (/control)
   - POST /control/mode {mode}
   - GET /control/state
3. Wire ModeManager to orchestrators/tasks
   - DataMining: enforce GapFill→Expansion policy, report progress
   - Backtesting: enqueue batch runs, persist results skeleton
   - Trading: placeholder start/stop hooks
4. FE minimal control panel (reuse existing mode slice; wire to /control/*)

## Milestone B: Data Pipeline Guarantees (P0)
1. Explicit GapFill→Expansion policy in DataMining
2. Data endpoints alignment
   - POST /data/gapfill, POST /data/expand, GET /data/bars
3. Instrumentation (structured logs + Prometheus counters/gauges)

## Milestone C: Backtesting & Optimization (P1)
1. Batch backtest runner (Celery) + persistence (Backtests)
2. OptimRuns + Weights persistence and orchestration
3. APIs: POST /backtest/run, POST /optimize/run, GET status
4. Select top 10 symbols pipeline; expose via /control/state

## Milestone D: Strategy Plugins (P1)
1. StrategyRegistry + PluginLoader (pkg discovery, hot reload)
2. APIs: GET /strategy/list, POST /strategy/reload

## Milestone E: Trading Execution (P1)
1. ExchangeAdapter interface (paper/live)
2. Trading service: subscribe to top 10; TP/SL immediate on signals
3. APIs: GET /trading/portfolio, POST /trading/start, POST /order/submit

## Milestone F: DB Schema Migrations (P0/P1)
- P0: Jobs (mode runs), Backtests (skeleton), Config
- P1: Strategies, OptimRuns, Weights, Signals, Orders, Positions, Trades

## Milestone G: Tests & Quality (P0→)
- Unit tests for ModeManager, Control API, Data policy
- Integration tests for acceptance criteria (DataMining order, Backtest selection, Trading TP/SL)

---

## Initial Task Breakdown (Sprint 1)
- Backend
  - Implement ModeManager (src/services/mode_manager.py)
  - Add Control router (src/api/routers/control.py)
  - Add Jobs table (alembic migration) and simple persistence
  - Wire DataMining start/stop hooks to ModeManager
- FE (minimal)
  - Connect existing mode UI to /control endpoints
- Observability
  - Basic metrics placeholders (Prometheus client usage wiring points)
- Tests
  - Unit: ModeManager transitions; Control API handlers

## Risks / Notes
- Ensure backward compatibility with existing /api/* routes (add new /control/* without breaking)
- DB migrations gated to non-destructive initial schemas
- Keep Celery queues as-is, add new tasks incrementally


# Implementation Gap Analysis: Autotrading (Current vs Target Architecture)

This document analyzes differences between the current codebase and the target 3‑mode state‑machine architecture, and highlights concrete gaps by area.

## Scope
- Current: FastAPI backend + Celery + PostgreSQL/TimescaleDB + Redis + React frontend
- Target: 3-mode (DataMining → Backtesting → Trading) state machine, exchange adapter, strategy plugin hot‑reload, strict GapFill→Expansion, Prometheus metrics, structured logs, error hooks, required DB schema, control/data/strategy/backtest/trading API, SSE/WebSocket FE updates

---

## 1) Mode State Machine (DataMining/Backtesting/Trading)
- Current
  - Mining orchestrators exist (mining_orchestrator.py / mining_orchestrator_v2.py) with phases and a notion of gap vs expansion.
  - Frontend keeps a local Redux mode (data-mining, auto-trading, backtesting) but backend lacks a unified mode manager.
  - No centralized control endpoints (/control/mode, /control/state) to command modes.
- Target
  - Single backend “ModeManager” coordinating 3 modes as a state machine, controlling background jobs and transitions.
- Gap
  - Missing centralized ModeManager service and control API to drive modes and persist/report state.

## 2) Data Pipeline (GapFill → Expansion order)
- Current
  - Orchestrators prioritize filling gaps then update/initial load; v2 has phased mining and can handle gap vs expansion flows.
  - Endpoints under /api/mining and /api/data-mining exist, but not a strict global sequencing contract.
- Target
  - DataMining mode must guarantee GapFill first, then continuous Expansion thereafter.
- Gap
  - Need explicit DataMining mode policy that enforces ordering at mode level and reports compliance.

## 3) Backtest/Optimization Engine
- Current
  - Strategy framework and backtesting engine present under src/strategy/backtesting (engine/simulator).
  - Celery backtesting tasks are placeholders/TODOs (e.g., src/tasks/backtesting.py comments).
  - No parameter/weight optimization orchestration; no top‑10 symbol selection flow.
- Target
  - Batch evaluation across strategies → select top 10 symbols → parameter/weight optimization (OptimRuns, Weights tracked).
- Gap
  - Implement batch runner, optim scheduler, results persistence, and APIs (/backtest/run, /optimize/run). Missing persistence schema.

## 4) Strategy Framework + Plugin System
- Current
  - Solid framework (BaseStrategy, models, backtesting, examples). No plugin hot‑load/unload.
- Target
  - Plugin loader with dynamic discovery/reload, runtime registration.
- Gap
  - Implement StrategyRegistry + PluginLoader (filesystem packages, entry points), and admin API (/strategy/list, /strategy/reload).

## 5) API Endpoint Structure
- Current
  - Many endpoints under /api/* (auth, data, mining, strategies, trading), plus WebSocket.
  - No /control/mode, /control/state; data/control names differ from target spec.
- Target
  - Control: /control/mode, /control/state
  - Data: /data/gapfill, /data/expand, /data/bars
  - Strategy: /strategy/list, /strategy/reload
  - Backtest: /backtest/run, /optimize/run
  - Trading: /trading/portfolio, /trading/start, /order/submit
- Gap
  - Add Control router, align Data/Backtest/Strategy/Trading endpoints with target names (compat layer for existing /api/* routes recommended).

## 6) Frontend Dashboard
- Current
  - React app with mode slice, mining controls, some trading UI; WebSocket infra present.
- Target
  - Control panel for mode/Job creation, progress/log stream; Data panel for GapFill/Expansion status; Backtest board; Trading board with real‑time charts/signals/PNL; SSE/WS realtime.
- Gap
  - Control/Data/Backtest/Trading boards need alignment to target UX; SSE/WS channels standardized for mode/state, job progress, and metrics.

## 7) DB Schema Differences
- Target required tables:
  - Symbols, MinuteBars, Trades, Positions, Orders, Strategies, Backtests, OptimRuns, Weights, Jobs, Signals, Config
- Current schema highlights (src/data/models.py):
  - Ticker (≈ Symbols), Candle (≈ MinuteBars), MiningHistory, AuthToken
  - Missing or partial: Trades, Positions, Orders, Strategies (DB), Backtests, OptimRuns, Weights, Jobs, Signals, Config
- Gap
  - Alembic migrations to add missing tables; decide mapping (Ticker→Symbols, Candle→MinuteBars) and naming; establish Jobs (mode/phase runs), Backtests/OptimRuns/Weights/Signals, and Config.

## 8) Exchange Adapter (paper/live), Timezone/Holidays
- Current
  - Trading services exist but no explicit ExchangeAdapter abstraction for paper vs live.
  - Trading calendar util exists; ensure full timezone/holiday coverage for minute bars.
- Gap
  - Add ExchangeAdapter interface and paper/live implementations; verify calendar & extended hours handling across pipeline.

## 9) Observability
- Current
  - Structured logger; no Prometheus metrics wired across core paths.
- Target
  - Prometheus metrics, structured logs everywhere, error hooks.
- Gap
  - Add metrics middleware, task metrics, mode/state gauges; standardize error hooks.

## 10) Testing (Acceptance Criteria)
- Current
  - Good unit tests in places; limited e2e around the 3‑mode lifecycle.
- Target
  - Tests ensuring: DataMining enforces GapFill→Expansion; Backtesting produces 10 symbols + tuned params/weights; Trading sets TP/SL on signal.
- Gap
  - Add integration tests for mode machine transitions and acceptance criteria.


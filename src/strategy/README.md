# Strategy Framework Quickstart

The strategy framework lives under `src/strategy` and provides:
- BaseStrategy (abstract)
- Data models (Order, Signal, Position)
- Backtesting engine and simulator
- Example strategies

## Create a strategy
```python
from src.strategy import BaseStrategy, Signal, OrderSide

class MyStrategy(BaseStrategy):
    async def on_candle(self, symbol, candle):
        # update indicators and state
        pass

    async def generate_signals(self):
        # yield buy/sell signals
        return [Signal(symbol="AAPL", side=OrderSide.BUY, strength=0.8)]
```

## Run a simple backtest (example)
```python
from datetime import datetime, timedelta
from src.strategy.backtesting import BacktestEngine

engine = BacktestEngine(initial_capital=100_000)
results = engine.run_backtest(
    strategy_cls=MyStrategy,
    symbols=["AAPL"],
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
)
print(results.summary())
```

## Tests
- See `tests/test_strategy_framework.py`


# Phase 4: Trading Strategy Framework & Backtesting Engine

## Phase 4 개요

Phase 4는 자동화된 트레이딩 전략을 개발, 테스트, 실행할 수 있는 포괄적인 프레임워크를 구축합니다. 이 단계에서는 전략 개발자가 쉽게 새로운 전략을 만들고, 과거 데이터로 검증하며, 실시간으로 실행할 수 있는 시스템을 만듭니다.

## 주요 목표

### 1. **Strategy Framework (전략 프레임워크)**
- 모든 전략이 상속받을 BaseStrategy 추상 클래스
- 표준화된 신호 생성 인터페이스
- 상태 관리 및 포지션 추적
- 리스크 관리 통합

### 2. **Backtesting Engine (백테스팅 엔진)**
- 과거 데이터를 사용한 전략 성능 검증
- 현실적인 거래 시뮬레이션 (슬리피지, 수수료 포함)
- 상세한 성과 분석 및 리포팅
- 최적화 도구

### 3. **Performance Analytics (성과 분석)**
- Sharpe Ratio, Sortino Ratio 등 주요 지표
- 최대 낙폭(Maximum Drawdown) 분석
- 승률 및 손익비 계산
- 거래별 상세 분석

### 4. **Signal Generation (신호 생성)**
- 기술적 지표 라이브러리 (TA-Lib 통합)
- 실시간 신호 생성 및 알림
- 다중 타임프레임 분석
- 신호 필터링 및 확인

### 5. **Example Strategies (예제 전략)**
- Moving Average Crossover
- RSI Mean Reversion
- Bollinger Band Breakout
- MACD Momentum

## 구현할 주요 컴포넌트

### 1. BaseStrategy 클래스
```python
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    """모든 전략의 기본 클래스"""
    
    @abstractmethod
    async def on_candle(self, symbol: str, candle: Dict):
        """새 캔들 생성 시 호출"""
        pass
    
    @abstractmethod
    async def generate_signals(self) -> List[Signal]:
        """거래 신호 생성"""
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: Signal) -> float:
        """포지션 크기 계산"""
        pass
```

### 2. Backtesting Engine
```python
class BacktestEngine:
    """과거 데이터로 전략 테스트"""
    
    async def run_backtest(
        self,
        strategy: BaseStrategy,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float
    ) -> BacktestResult:
        """백테스트 실행"""
        pass
    
    def analyze_performance(self, trades: List[Trade]) -> PerformanceMetrics:
        """성과 분석"""
        pass
```

### 3. Signal System
```python
@dataclass
class Signal:
    symbol: str
    direction: Literal['BUY', 'SELL']
    strength: float  # 0.0 ~ 1.0
    stop_loss: float
    take_profit: float
    timestamp: datetime
```

## Phase 4 구현 로드맵

### Step 1: Core Framework (핵심 프레임워크)
1. BaseStrategy 추상 클래스
2. Signal 및 Trade 데이터 모델
3. Position 관리 시스템
4. Event 기반 아키텍처

### Step 2: Backtesting Engine (백테스팅 엔진)
1. Historical data loader
2. Trade simulator
3. Performance calculator
4. Report generator

### Step 3: Technical Indicators (기술적 지표)
1. TA-Lib 통합
2. Custom indicators
3. Multi-timeframe support
4. Indicator caching

### Step 4: Example Strategies (예제 전략)
1. Simple MA crossover
2. RSI oversold/overbought
3. Bollinger Band strategy
4. Combined strategies

### Step 5: Live Trading Integration (실거래 통합)
1. Real-time data connection
2. Order execution bridge
3. Position monitoring
4. Risk management

## Phase 4 시작 프롬프트

### 옵션 1: 전체 프레임워크 구현
```
/sc:implement --think --validate "Phase 4 Trading Strategy Framework 구현: 
1) src/strategy/base.py에 BaseStrategy 추상 클래스 생성 (on_candle, generate_signals, calculate_position_size 추상 메서드)
2) src/strategy/models.py에 Signal, Trade, Position 데이터클래스 정의
3) src/strategy/backtesting/engine.py에 BacktestEngine 클래스 구현 (run_backtest, analyze_performance)
4) src/strategy/backtesting/simulator.py에 TradeSimulator 구현 (execute_trade, apply_slippage, calculate_commission)
5) tests/test_strategy_framework.py로 기본 동작 검증"
```

### 옵션 2: 단계별 구현 - BaseStrategy 먼저
```
/sc:implement --think "Phase 4 Step 1 - BaseStrategy 프레임워크:
1) src/strategy/base.py에 BaseStrategy ABC 생성
2) src/strategy/models.py에 Signal, Trade, Position 모델 정의  
3) src/strategy/events.py에 StrategyEvent 시스템 구현
4) 간단한 MockStrategy로 테스트"
```

### 옵션 3: 백테스팅 엔진 중심
```
/sc:build --think "Phase 4 백테스팅 엔진:
1) Historical data loader 구현 (Phase 2 데이터 활용)
2) BacktestEngine 클래스 with trade simulation
3) Performance metrics 계산 (Sharpe, drawdown, win rate)
4) 결과 리포팅 시스템"
```

### 옵션 4: 기술적 지표 라이브러리
```
/sc:implement "Phase 4 기술적 지표 시스템:
1) TA-Lib 래퍼 구현
2) SMA, EMA, RSI, MACD, Bollinger Bands 지표
3) 지표 결과 캐싱 시스템
4) Multi-timeframe 지원"
```

### 옵션 5: 예제 전략 구현
```
/sc:implement --validate "Phase 4 예제 전략:
1) MovingAverageCrossStrategy (SMA 20/50 크로스)
2) RSIMeanReversionStrategy (RSI 30/70)
3) BollingerBandStrategy (Band breakout)
4) 각 전략에 대한 백테스트 실행"
```

## 예상 결과물

### 1. 전략 개발 워크플로우
```python
# 1. 전략 정의
class MyStrategy(BaseStrategy):
    def __init__(self):
        self.sma_short = SMA(period=20)
        self.sma_long = SMA(period=50)
    
    async def on_candle(self, symbol, candle):
        self.sma_short.update(candle['close'])
        self.sma_long.update(candle['close'])
    
    async def generate_signals(self):
        if self.sma_short.value > self.sma_long.value:
            return [Signal(
                symbol=self.symbol,
                direction='BUY',
                strength=0.8
            )]

# 2. 백테스트 실행
engine = BacktestEngine()
result = await engine.run_backtest(
    strategy=MyStrategy(),
    start_date='2024-01-01',
    end_date='2024-12-31',
    initial_capital=100000
)

# 3. 성과 분석
print(f"Total Return: {result.total_return:.2%}")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.2%}")
print(f"Win Rate: {result.win_rate:.2%}")
```

### 2. 실시간 실행
```python
# Phase 3 스트리밍과 통합
strategy = MyStrategy()
streaming_service.register_strategy(strategy)

# 자동으로 신호 생성 및 실행
async for signal in strategy.signal_stream():
    if signal.strength > 0.7:
        await execute_trade(signal)
```

## Phase 4 완료 기준

1. ✅ BaseStrategy 프레임워크 구현 및 테스트
2. ✅ 백테스팅 엔진 완성 (시뮬레이션, 성과 분석)
3. ✅ 최소 3개 이상의 예제 전략 구현
4. ✅ 기술적 지표 라이브러리 통합
5. ✅ Phase 3 실시간 데이터와 연동
6. ✅ 상세한 백테스트 리포트 생성

## 다음 단계 (Phase 5 미리보기)

Phase 4 완료 후, Phase 5에서는:
- GUI 대시보드 개발 (전략 모니터링, 백테스트 시각화)
- 실시간 포지션 및 P&L 추적
- 전략 파라미터 최적화 도구
- 멀티 전략 포트폴리오 관리

---

## 추천 시작 방법

**가장 추천하는 프롬프트** (전체 프레임워크 구현):

```
/sc:implement --think --validate "Phase 4 Trading Strategy Framework 구현: 
1) src/strategy/base.py에 BaseStrategy 추상 클래스 생성 (on_candle, generate_signals, calculate_position_size 추상 메서드)
2) src/strategy/models.py에 Signal, Trade, Position 데이터클래스 정의
3) src/strategy/backtesting/engine.py에 BacktestEngine 클래스 구현 (run_backtest, analyze_performance)
4) src/strategy/backtesting/simulator.py에 TradeSimulator 구현 (execute_trade, apply_slippage, calculate_commission)
5) tests/test_strategy_framework.py로 기본 동작 검증"
```

이 프롬프트는 Phase 4의 핵심 구조를 한 번에 구현하여 빠르게 전략 개발을 시작할 수 있게 합니다.
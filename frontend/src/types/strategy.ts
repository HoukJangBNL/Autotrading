export enum StrategyStatus {
  ACTIVE = 'ACTIVE',
  INACTIVE = 'INACTIVE',
  TESTING = 'TESTING',
  ERROR = 'ERROR',
}

export enum StrategyType {
  MOMENTUM = 'MOMENTUM',
  MEAN_REVERSION = 'MEAN_REVERSION',
  BREAKOUT = 'BREAKOUT',
  ARBITRAGE = 'ARBITRAGE',
  MARKET_MAKING = 'MARKET_MAKING',
  CUSTOM = 'CUSTOM',
}

export interface StrategyParameter {
  name: string;
  type: 'number' | 'string' | 'boolean' | 'select';
  value: any;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  description?: string;
}

export interface RiskManagement {
  stopLoss: number;
  takeProfit: number;
  positionSize: number;
  maxDrawdown: number;
  maxPositions: number;
}

export interface TradingSchedule {
  startTime: string;
  endTime: string;
  tradingDays: string[];
  timezone: string;
}

export interface PerformanceMetrics {
  totalReturn: number;
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
  avgWin: number;
  avgLoss: number;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  type: StrategyType;
  status: StrategyStatus;
  symbols: string[];
  parameters: StrategyParameter[];
  riskManagement: RiskManagement;
  schedule: TradingSchedule;
  performance?: PerformanceMetrics;
  createdAt: string;
  updatedAt: string;
  lastExecuted?: string;
}

export interface BacktestConfig {
  strategyId: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  commission: number;
  slippage: number;
}

export interface BacktestResult {
  id: string;
  strategyId: string;
  config: BacktestConfig;
  performance: PerformanceMetrics;
  equityCurve: { date: string; value: number }[];
  trades: Trade[];
  monthlyReturns: { [key: string]: number };
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  error?: string;
  completedAt?: string;
}

export interface Trade {
  id: string;
  strategyId: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  entryPrice: number;
  exitPrice?: number;
  entryTime: string;
  exitTime?: string;
  pnl?: number;
  pnlPercent?: number;
  commission: number;
  status: 'OPEN' | 'CLOSED' | 'CANCELLED';
}

export interface StrategySignal {
  strategyId: string;
  symbol: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  strength: number;
  price: number;
  quantity: number;
  timestamp: string;
  reason?: string;
}
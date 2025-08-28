// Mock data for development

export const mockPortfolioSummary = {
  total_value: 150000,
  cash_balance: 25000,
  buying_power: 50000,
  securities_value: 125000,
  day_change: 2500,
  day_change_pct: 1.69,
  total_change: 15000,
  total_change_pct: 11.11,
  position_count: 8,
  open_pnl: 3500,
  open_pnl_pct: 2.8,
  last_update: new Date().toISOString(),
};

export const mockPositions = [
  {
    symbol: 'AAPL',
    name: 'Apple Inc.',
    quantity: 100,
    avg_cost: 175.50,
    current_price: 182.30,
    market_value: 18230,
    cost_basis: 17550,
    unrealized_pnl: 680,
    unrealized_pnl_pct: 3.87,
    day_change: 230,
    day_change_pct: 1.28,
    side: 'long' as const,
  },
  {
    symbol: 'MSFT',
    name: 'Microsoft Corp.',
    quantity: 50,
    avg_cost: 380.20,
    current_price: 395.50,
    market_value: 19775,
    cost_basis: 19010,
    unrealized_pnl: 765,
    unrealized_pnl_pct: 4.02,
    day_change: -125,
    day_change_pct: -0.63,
    side: 'long' as const,
  },
  {
    symbol: 'GOOGL',
    name: 'Alphabet Inc.',
    quantity: 75,
    avg_cost: 140.80,
    current_price: 142.15,
    market_value: 10661.25,
    cost_basis: 10560,
    unrealized_pnl: 101.25,
    unrealized_pnl_pct: 0.96,
    day_change: 187.5,
    day_change_pct: 1.79,
    side: 'long' as const,
  },
];

export const mockStrategies = [
  {
    id: 'strat-1',
    name: 'Mean Reversion Strategy',
    type: 'mean_reversion',
    description: 'Trades based on price deviations from moving averages',
    symbols: ['AAPL', 'MSFT', 'GOOGL'],
    parameters: { lookback: 20, threshold: 2.0 },
    is_active: true,
    is_example: false,
    created_at: '2024-01-15T10:00:00Z',
    status: 'running' as const,
    metrics: {
      total_return: 12.5,
      sharpe_ratio: 1.8,
      win_rate: 0.65,
      total_trades: 42,
    },
    positions: ['AAPL', 'MSFT'],
  },
  {
    id: 'strat-2',
    name: 'Momentum Strategy',
    type: 'momentum',
    description: 'Follows strong price trends',
    symbols: ['TSLA', 'NVDA', 'AMD'],
    parameters: { period: 50, min_volume: 1000000 },
    is_active: true,
    is_example: false,
    created_at: '2024-01-20T14:30:00Z',
    status: 'running' as const,
    metrics: {
      total_return: 18.3,
      sharpe_ratio: 2.1,
      win_rate: 0.58,
      total_trades: 28,
    },
    positions: ['TSLA'],
  },
  {
    id: 'strat-3',
    name: 'Pairs Trading',
    type: 'pairs',
    description: 'Statistical arbitrage between correlated stocks',
    symbols: ['XOM', 'CVX'],
    parameters: { correlation_threshold: 0.8, z_score: 2.5 },
    is_active: false,
    is_example: false,
    created_at: '2024-02-01T09:15:00Z',
    status: 'paused' as const,
    metrics: {
      total_return: -2.1,
      sharpe_ratio: 0.9,
      win_rate: 0.48,
      total_trades: 15,
    },
    positions: [],
  },
];

export const mockTrades = [
  {
    id: 'trade-1',
    order_id: 'order-123',
    symbol: 'AAPL',
    side: 'buy' as const,
    quantity: 10,
    price: 182.50,
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
  },
  {
    id: 'trade-2',
    order_id: 'order-124',
    symbol: 'MSFT',
    side: 'sell' as const,
    quantity: 5,
    price: 396.20,
    timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(), // 3 hours ago
  },
  {
    id: 'trade-3',
    order_id: 'order-125',
    symbol: 'GOOGL',
    side: 'buy' as const,
    quantity: 15,
    price: 141.80,
    timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(), // 5 hours ago
  },
  {
    id: 'trade-4',
    order_id: 'order-126',
    symbol: 'TSLA',
    side: 'buy' as const,
    quantity: 20,
    price: 245.30,
    timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(), // 6 hours ago
  },
  {
    id: 'trade-5',
    order_id: 'order-127',
    symbol: 'NVDA',
    side: 'sell' as const,
    quantity: 8,
    price: 882.50,
    timestamp: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString(), // 7 hours ago
  },
];

export const mockMarketData = {
  symbols: [
    { symbol: 'AAPL', name: 'Apple Inc.', data_start: '2020-01-01', data_end: '2024-12-31', candle_count: 1000 },
    { symbol: 'MSFT', name: 'Microsoft Corp.', data_start: '2020-01-01', data_end: '2024-12-31', candle_count: 1000 },
    { symbol: 'GOOGL', name: 'Alphabet Inc.', data_start: '2020-01-01', data_end: '2024-12-31', candle_count: 1000 },
    { symbol: 'TSLA', name: 'Tesla Inc.', data_start: '2020-01-01', data_end: '2024-12-31', candle_count: 1000 },
    { symbol: 'NVDA', name: 'NVIDIA Corp.', data_start: '2020-01-01', data_end: '2024-12-31', candle_count: 1000 },
  ],
  candles: generateMockCandles('AAPL', 100),
};

function generateMockCandles(symbol: string, count: number) {
  const candles = [];
  const now = Date.now();
  let price = 180;
  
  for (let i = count - 1; i >= 0; i--) {
    const time = new Date(now - i * 60 * 1000); // 1 minute intervals
    const change = (Math.random() - 0.5) * 2; // Random walk
    price += change;
    
    const open = price;
    const close = price + (Math.random() - 0.5) * 1;
    const high = Math.max(open, close) + Math.random() * 0.5;
    const low = Math.min(open, close) - Math.random() * 0.5;
    const volume = Math.floor(Math.random() * 1000000) + 100000;
    
    candles.push({
      timestamp: time.toISOString(),
      open,
      high,
      low,
      close,
      volume,
    });
  }
  
  return candles;
}
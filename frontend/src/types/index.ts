// Re-export all types from individual modules
export * from './strategy';

// Common trading types
export enum OrderSide {
  BUY = 'BUY',
  SELL = 'SELL',
}

export enum OrderType {
  MARKET = 'MARKET',
  LIMIT = 'LIMIT',
  STOP = 'STOP',
  STOP_LIMIT = 'STOP_LIMIT',
}

export enum OrderStatus {
  PENDING = 'PENDING',
  PARTIALLY_FILLED = 'PARTIALLY_FILLED',
  FILLED = 'FILLED',
  CANCELLED = 'CANCELLED',
  REJECTED = 'REJECTED',
}

export enum TimeInForce {
  DAY = 'DAY',
  GTC = 'GTC',
  IOC = 'IOC',
  FOK = 'FOK',
}

export interface Position {
  id: string;
  symbol: string;
  quantity: number;
  avgCost: number;
  currentPrice: number;
  marketValue: number;
  unrealizedPnL: number;
  pnlPercent: number;
  side: 'LONG' | 'SHORT';
}

export interface Order {
  id: string;
  symbol: string;
  side: OrderSide;
  orderType: OrderType;
  quantity: number;
  limitPrice?: number;
  stopPrice?: number;
  filledQuantity: number;
  status: OrderStatus;
  createdAt: string;
  updatedAt: string;
  timeInForce: string;
}

export interface Trade {
  id: string;
  orderId: string;
  symbol: string;
  side: OrderSide;
  quantity: number;
  price: number;
  commission: number;
  executedAt: string;
  pnl?: number;
  notes?: string;
}

export interface MarketData {
  symbol: string;
  bid: number;
  ask: number;
  last: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  timestamp: string;
  change: number;
  changePercent: number;
}

export interface AccountSummary {
  totalValue: number;
  cashBalance: number;
  positionsValue: number;
  buyingPower: number;
  dayPnL: number;
  dayPnLPercent: number;
  totalPnL: number;
  totalPnLPercent: number;
}
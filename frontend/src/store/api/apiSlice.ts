import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { RootState } from '../store';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://127.0.0.1:8182';
const API_PREFIX = '/api';

// Define types
export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

export interface MarketData {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  high: number;
  low: number;
  open: number;
  close: number;
  timestamp: string;
}

export interface Order {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  type: 'MARKET' | 'LIMIT' | 'STOP';
  quantity: number;
  price?: number;
  stopPrice?: number;
  status: 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED';
  filledQuantity: number;
  averagePrice?: number;
  createdAt: string;
  updatedAt: string;
}

export interface Position {
  id: string;
  symbol: string;
  quantity: number;
  averagePrice: number;
  currentPrice: number;
  unrealizedPnL: number;
  realizedPnL: number;
  totalPnL: number;
  costBasis: number;
  marketValue: number;
}

export interface Strategy {
  id: string;
  name: string;
  type: string;
  status: 'ACTIVE' | 'INACTIVE' | 'PAUSED';
  parameters: Record<string, any>;
  performance: {
    totalReturn: number;
    winRate: number;
    sharpeRatio: number;
    maxDrawdown: number;
  };
  createdAt: string;
  updatedAt: string;
}

export interface BacktestConfig {
  strategyId: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  symbols: string[];
  parameters?: Record<string, any>;
}

export interface BacktestResult {
  id: string;
  strategyId: string;
  status: 'RUNNING' | 'COMPLETED' | 'FAILED';
  progress: number;
  results?: {
    totalReturn: number;
    annualizedReturn: number;
    sharpeRatio: number;
    maxDrawdown: number;
    winRate: number;
    totalTrades: number;
    profitableTrades: number;
    equity: number[];
    trades: any[];
  };
  error?: string;
  createdAt: string;
  completedAt?: string;
}

// Create the API slice
export const apiSlice = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: `${API_BASE_URL}${API_PREFIX}`,
    prepareHeaders: (headers, { getState }) => {
      const token = localStorage.getItem('accessToken');
      if (token) {
        headers.set('authorization', `Bearer ${token}`);
      }
      return headers;
    },
    credentials: 'include',
  }),
  tagTypes: [
    'User', 
    'MarketData', 
    'Order', 
    'Position', 
    'Strategy', 
    'Backtest',
    'Portfolio',
    'Trade'
  ],
  endpoints: (builder) => ({
    // Auth endpoints
    login: builder.mutation<LoginResponse, LoginRequest>({
      query: (credentials) => ({
        url: '/auth/login',
        method: 'POST',
        body: credentials,
      }),
      invalidatesTags: ['User'],
    }),

    logout: builder.mutation<void, void>({
      query: () => ({
        url: '/auth/logout',
        method: 'POST',
      }),
      invalidatesTags: ['User'],
    }),

    getCurrentUser: builder.query<User, void>({
      query: () => '/auth/me',
      providesTags: ['User'],
    }),

    refreshToken: builder.mutation<LoginResponse, void>({
      query: () => ({
        url: '/auth/refresh',
        method: 'POST',
      }),
    }),

    // Market Data endpoints
    getMarketData: builder.query<MarketData, { symbol: string; interval?: string }>({
      query: ({ symbol, interval }) => ({
        url: '/market/data',
        params: { symbol, interval },
      }),
      providesTags: (result, error, arg) => [
        { type: 'MarketData', id: arg.symbol },
      ],
      // Poll every 5 seconds for real-time data
      pollingInterval: 5000,
    }),

    getQuote: builder.query<MarketData, string>({
      query: (symbol) => `/market/quote/${symbol}`,
      providesTags: (result, error, symbol) => [
        { type: 'MarketData', id: symbol },
      ],
    }),

    searchSymbols: builder.query<string[], string>({
      query: (query) => ({
        url: '/market/search',
        params: { q: query },
      }),
    }),

    // Trading endpoints
    getOrders: builder.query<Order[], { status?: string }>({
      query: ({ status }) => ({
        url: '/trading/orders',
        params: status ? { status } : {},
      }),
      providesTags: ['Order'],
    }),

    placeOrder: builder.mutation<Order, Partial<Order>>({
      query: (order) => ({
        url: '/trading/orders',
        method: 'POST',
        body: order,
      }),
      invalidatesTags: ['Order', 'Position', 'Portfolio'],
    }),

    cancelOrder: builder.mutation<void, string>({
      query: (orderId) => ({
        url: `/trading/orders/${orderId}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Order'],
    }),

    getPositions: builder.query<Position[], void>({
      query: () => '/trading/positions',
      providesTags: ['Position'],
      // Poll every 10 seconds for position updates
      pollingInterval: 10000,
    }),

    // Strategy endpoints
    getStrategies: builder.query<Strategy[], void>({
      query: () => '/strategies',
      providesTags: ['Strategy'],
    }),

    getStrategy: builder.query<Strategy, string>({
      query: (id) => `/strategies/${id}`,
      providesTags: (result, error, id) => [
        { type: 'Strategy', id },
      ],
    }),

    createStrategy: builder.mutation<Strategy, Partial<Strategy>>({
      query: (strategy) => ({
        url: '/strategies',
        method: 'POST',
        body: strategy,
      }),
      invalidatesTags: ['Strategy'],
    }),

    updateStrategy: builder.mutation<Strategy, { id: string; updates: Partial<Strategy> }>({
      query: ({ id, updates }) => ({
        url: `/strategies/${id}`,
        method: 'PATCH',
        body: updates,
      }),
      invalidatesTags: (result, error, arg) => [
        { type: 'Strategy', id: arg.id },
      ],
    }),

    deleteStrategy: builder.mutation<void, string>({
      query: (id) => ({
        url: `/strategies/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Strategy'],
    }),

    startStrategy: builder.mutation<void, string>({
      query: (id) => ({
        url: `/strategies/${id}/start`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, id) => [
        { type: 'Strategy', id },
      ],
    }),

    stopStrategy: builder.mutation<void, string>({
      query: (id) => ({
        url: `/strategies/${id}/stop`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, id) => [
        { type: 'Strategy', id },
      ],
    }),

    // Backtest endpoints
    runBacktest: builder.mutation<BacktestResult, BacktestConfig>({
      query: (config) => ({
        url: '/backtest/run',
        method: 'POST',
        body: config,
      }),
      invalidatesTags: ['Backtest'],
    }),

    getBacktestResults: builder.query<BacktestResult, string>({
      query: (backtestId) => `/backtest/results/${backtestId}`,
      providesTags: (result, error, id) => [
        { type: 'Backtest', id },
      ],
      // Poll while backtest is running
      pollingInterval: (result) => {
        if (result?.status === 'RUNNING') {
          return 2000; // Poll every 2 seconds
        }
        return 0; // Stop polling
      },
    }),

    getBacktestHistory: builder.query<BacktestResult[], void>({
      query: () => '/backtest/history',
      providesTags: ['Backtest'],
    }),

    // Portfolio endpoints
    getPortfolio: builder.query<any, void>({
      query: () => '/portfolio',
      providesTags: ['Portfolio'],
      pollingInterval: 30000, // Update every 30 seconds
    }),

    getAccountBalance: builder.query<any, void>({
      query: () => '/portfolio/balance',
      providesTags: ['Portfolio'],
    }),

    getPerformance: builder.query<any, string>({
      query: (period) => ({
        url: '/portfolio/performance',
        params: { period },
      }),
      providesTags: ['Portfolio'],
    }),

    getTrades: builder.query<any[], { startDate?: string; endDate?: string }>({
      query: ({ startDate, endDate }) => ({
        url: '/trading/trades',
        params: { start_date: startDate, end_date: endDate },
      }),
      providesTags: ['Trade'],
    }),
  }),
});

// Export hooks for usage in components
export const {
  useLoginMutation,
  useLogoutMutation,
  useGetCurrentUserQuery,
  useRefreshTokenMutation,
  useGetMarketDataQuery,
  useGetQuoteQuery,
  useSearchSymbolsQuery,
  useGetOrdersQuery,
  usePlaceOrderMutation,
  useCancelOrderMutation,
  useGetPositionsQuery,
  useGetStrategiesQuery,
  useGetStrategyQuery,
  useCreateStrategyMutation,
  useUpdateStrategyMutation,
  useDeleteStrategyMutation,
  useStartStrategyMutation,
  useStopStrategyMutation,
  useRunBacktestMutation,
  useGetBacktestResultsQuery,
  useGetBacktestHistoryQuery,
  useGetPortfolioQuery,
  useGetAccountBalanceQuery,
  useGetPerformanceQuery,
  useGetTradesQuery,
} = apiSlice;
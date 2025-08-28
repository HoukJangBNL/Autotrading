// Portfolio state management slice

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { portfolioApi } from '../../services/api';

export interface PortfolioSummary {
  total_value?: number;
  cash_balance?: number;
  securities_value?: number;
  buying_power?: number;
  day_change?: number;
  day_change_pct?: number;
  total_change?: number;
  total_change_pct?: number;
  position_count?: number;
  open_pnl?: number;
  open_pnl_pct?: number;
  last_update?: string;
}

export interface Position {
  symbol: string;
  name?: string;
  quantity: number;
  avg_cost: number;
  current_price?: number;
  market_value?: number;
  cost_basis?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  realized_pnl?: number;
  day_change?: number;
  day_change_pct?: number;
  side?: 'long' | 'short';
}

export interface PortfolioPosition extends Position {
  average_cost: number;
}

interface PortfolioPerformance {
  period: string;
  total_return: number;
  total_return_pct: number;
  annualized_return: number;
  volatility: number;
  sharpe_ratio: number;
  max_drawdown: number;
  daily_values: any[];
}

interface AssetAllocation {
  total_value: number;
  by_asset_type: any[];
  by_sector: any[];
  by_holding: any[];
  cash_percentage: number;
}

interface PortfolioState {
  summary: PortfolioSummary | null;
  positions: Position[];
  performance: PortfolioPerformance | null;
  allocation: AssetAllocation | null;
  transactions: any[];
  loading: boolean;
  error: string | null;
}

const initialState: PortfolioState = {
  summary: null,
  positions: [],
  performance: null,
  allocation: null,
  transactions: [],
  loading: false,
  error: null,
};

// Async thunks
export const fetchPortfolioSummary = createAsyncThunk(
  'portfolio/fetchSummary',
  async () => {
    const response = await portfolioApi.getSummary();
    return response.data;
  }
);

export const fetchPortfolioPositions = createAsyncThunk(
  'portfolio/fetchPositions',
  async () => {
    const response = await portfolioApi.getPositions();
    return response.data;
  }
);

export const fetchPortfolioPerformance = createAsyncThunk(
  'portfolio/fetchPerformance',
  async (period: string) => {
    const response = await portfolioApi.getPerformance(period);
    return response.data;
  }
);

export const fetchAssetAllocation = createAsyncThunk(
  'portfolio/fetchAllocation',
  async () => {
    const response = await portfolioApi.getAllocation();
    return response.data;
  }
);

export const fetchTransactionHistory = createAsyncThunk(
  'portfolio/fetchTransactions',
  async (params?: any) => {
    const response = await portfolioApi.getTransactions(params);
    return response.data;
  }
);

export const rebalancePortfolio = createAsyncThunk(
  'portfolio/rebalance',
  async (targetAllocation: any) => {
    const response = await portfolioApi.rebalance(targetAllocation);
    return response.data;
  }
);

const portfolioSlice = createSlice({
  name: 'portfolio',
  initialState,
  reducers: {
    updateSummary: (state, action) => {
      state.summary = { ...state.summary, ...action.payload };
    },
    updatePosition: (state, action) => {
      const position = action.payload;
      const index = state.positions.findIndex(p => p.symbol === position.symbol);
      if (index >= 0) {
        state.positions[index] = position;
      }
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch summary
      .addCase(fetchPortfolioSummary.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchPortfolioSummary.fulfilled, (state, action) => {
        state.loading = false;
        state.summary = action.payload;
      })
      .addCase(fetchPortfolioSummary.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch portfolio summary';
      })
      // Fetch positions
      .addCase(fetchPortfolioPositions.fulfilled, (state, action) => {
        state.positions = action.payload;
      })
      // Fetch performance
      .addCase(fetchPortfolioPerformance.fulfilled, (state, action) => {
        state.performance = action.payload;
      })
      // Fetch allocation
      .addCase(fetchAssetAllocation.fulfilled, (state, action) => {
        state.allocation = action.payload;
      })
      // Fetch transactions
      .addCase(fetchTransactionHistory.fulfilled, (state, action) => {
        state.transactions = action.payload;
      });
  },
});

export const { updateSummary, updatePosition } = portfolioSlice.actions;
export const updatePortfolioSummary = updateSummary;
export default portfolioSlice.reducer;
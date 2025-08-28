// Backtest state management slice

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { backtestApi } from '../../services/api';

interface BacktestStatus {
  backtest_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  strategy_name: string;
  symbols: string[];
  start_date: string;
  end_date: string;
  created_at: string;
  error?: string;
}

interface BacktestResult {
  backtest_id: string;
  strategy_id: string;
  strategy_name: string;
  total_return: number;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  profit_factor: number;
  equity_curve: any[];
  trades: any[];
}

interface BacktestState {
  backtests: BacktestStatus[];
  results: { [key: string]: BacktestResult };
  activeBacktest: string | null;
  loading: boolean;
  error: string | null;
}

const initialState: BacktestState = {
  backtests: [],
  results: {},
  activeBacktest: null,
  loading: false,
  error: null,
};

// Async thunks
export const startBacktest = createAsyncThunk(
  'backtest/start',
  async (data: any) => {
    const response = await backtestApi.start(data);
    return response.data;
  }
);

export const fetchBacktestStatus = createAsyncThunk(
  'backtest/fetchStatus',
  async (id: string) => {
    const response = await backtestApi.getStatus(id);
    return response.data;
  }
);

export const fetchBacktestResult = createAsyncThunk(
  'backtest/fetchResult',
  async (id: string) => {
    const response = await backtestApi.getResult(id);
    return response.data;
  }
);

export const fetchBacktests = createAsyncThunk(
  'backtest/fetchAll',
  async (params?: any) => {
    const response = await backtestApi.list(params);
    return response.data;
  }
);

export const compareBacktests = createAsyncThunk(
  'backtest/compare',
  async (ids: string[]) => {
    const response = await backtestApi.compare(ids);
    return response.data;
  }
);

const backtestSlice = createSlice({
  name: 'backtest',
  initialState,
  reducers: {
    setActiveBacktest: (state, action) => {
      state.activeBacktest = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      // Start backtest
      .addCase(startBacktest.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(startBacktest.fulfilled, (state, action) => {
        state.loading = false;
        state.activeBacktest = action.payload.backtest_id;
      })
      .addCase(startBacktest.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to start backtest';
      })
      // Fetch status
      .addCase(fetchBacktestStatus.fulfilled, (state, action) => {
        const index = state.backtests.findIndex(
          b => b.backtest_id === action.payload.backtest_id
        );
        if (index >= 0) {
          state.backtests[index] = action.payload;
        } else {
          state.backtests.push(action.payload);
        }
      })
      // Fetch result
      .addCase(fetchBacktestResult.fulfilled, (state, action) => {
        state.results[action.payload.backtest_id] = action.payload;
      })
      // Fetch all
      .addCase(fetchBacktests.fulfilled, (state, action) => {
        state.backtests = action.payload;
      });
  },
});

export const { setActiveBacktest } = backtestSlice.actions;
export default backtestSlice.reducer;
// Strategies state management slice

import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { strategiesApi } from '../../services/api';

export type StrategyStatus = 'running' | 'paused' | 'stopped' | 'error';

export interface StrategyMetrics {
  total_return?: number;
  sharpe_ratio?: number;
  win_rate?: number;
  total_trades?: number;
}

export interface Strategy {
  id: string;
  name: string;
  type: string;
  description: string;
  symbols: string[];
  parameters: { [key: string]: any };
  is_active: boolean;
  is_example: boolean;
  created_at?: string;
  performance?: {
    total_trades: number;
    win_rate: number;
    total_pnl: number;
    sharpe_ratio: number;
    max_drawdown: number;
  };
  status: StrategyStatus;
  metrics?: StrategyMetrics;
  positions?: any[];
}

interface StrategiesState {
  strategies: Strategy[];
  activeStrategies: Strategy[];
  selectedStrategy: Strategy | null;
  loading: boolean;
  error: string | null;
}

const initialState: StrategiesState = {
  strategies: [],
  activeStrategies: [],
  selectedStrategy: null,
  loading: false,
  error: null,
};

// Async thunks
export const fetchStrategies = createAsyncThunk(
  'strategies/fetchAll',
  async () => {
    const response = await strategiesApi.list();
    return response.data;
  }
);

export const createStrategy = createAsyncThunk(
  'strategies/create',
  async (data: any) => {
    const response = await strategiesApi.create(data);
    return response.data;
  }
);

export const updateStrategy = createAsyncThunk(
  'strategies/update',
  async ({ id, data }: { id: string; data: any }) => {
    const response = await strategiesApi.update(id, data);
    return response.data;
  }
);

export const deleteStrategy = createAsyncThunk(
  'strategies/delete',
  async (id: string) => {
    await strategiesApi.delete(id);
    return id;
  }
);

export const startStrategy = createAsyncThunk(
  'strategies/start',
  async (id: string) => {
    await strategiesApi.start(id);
    return id;
  }
);

export const stopStrategy = createAsyncThunk(
  'strategies/stop',
  async (id: string) => {
    await strategiesApi.stop(id);
    return id;
  }
);

export const fetchStrategyPerformance = createAsyncThunk(
  'strategies/fetchPerformance',
  async (id: string) => {
    const response = await strategiesApi.getPerformance(id);
    return { id, performance: response.data };
  }
);

const strategiesSlice = createSlice({
  name: 'strategies',
  initialState,
  reducers: {
    selectStrategy: (state, action: PayloadAction<string>) => {
      state.selectedStrategy = 
        state.strategies.find(s => s.id === action.payload) || null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch all strategies
      .addCase(fetchStrategies.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchStrategies.fulfilled, (state, action) => {
        state.loading = false;
        state.strategies = action.payload;
        state.activeStrategies = action.payload.filter((s: Strategy) => s.is_active);
      })
      .addCase(fetchStrategies.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch strategies';
      })
      // Create strategy
      .addCase(createStrategy.fulfilled, (state, action) => {
        state.strategies.push(action.payload);
      })
      // Update strategy
      .addCase(updateStrategy.fulfilled, (state, action) => {
        const index = state.strategies.findIndex(s => s.id === action.payload.id);
        if (index >= 0) {
          state.strategies[index] = action.payload;
        }
      })
      // Delete strategy
      .addCase(deleteStrategy.fulfilled, (state, action) => {
        state.strategies = state.strategies.filter(s => s.id !== action.payload);
        if (state.selectedStrategy?.id === action.payload) {
          state.selectedStrategy = null;
        }
      })
      // Start strategy
      .addCase(startStrategy.fulfilled, (state, action) => {
        const strategy = state.strategies.find(s => s.id === action.payload);
        if (strategy) {
          strategy.is_active = true;
        }
      })
      // Stop strategy
      .addCase(stopStrategy.fulfilled, (state, action) => {
        const strategy = state.strategies.find(s => s.id === action.payload);
        if (strategy) {
          strategy.is_active = false;
        }
      })
      // Fetch performance
      .addCase(fetchStrategyPerformance.fulfilled, (state, action) => {
        const strategy = state.strategies.find(s => s.id === action.payload.id);
        if (strategy) {
          strategy.performance = action.payload.performance;
        }
      });
  },
});

export const { selectStrategy } = strategiesSlice.actions;

// Additional strategy-related actions
export const fetchActiveStrategies = fetchStrategies; // Alias for active strategies
export const updateStrategySignal = (state: any, action: any) => {
  const { strategyId, signal } = action.payload;
  const strategy = state.strategies.find((s: any) => s.id === strategyId);
  if (strategy) {
    strategy.lastSignal = signal;
  }
};
export const updateStrategyMetrics = (state: any, action: any) => {
  const { strategyId, metrics } = action.payload;
  const strategy = state.strategies.find((s: any) => s.id === strategyId);
  if (strategy) {
    strategy.performance = metrics;
  }
};

export default strategiesSlice.reducer;
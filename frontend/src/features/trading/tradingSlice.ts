// Trading operations state management slice

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { tradingApi } from '../../services/api';

interface Order {
  order_id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  order_type: string;
  status: string;
  created_at: string;
  average_fill_price?: number;
  filled_quantity?: number;
  commission?: number;
}

export interface Trade {
  id: string;
  order_id: string;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  timestamp: string;
}

export interface Position {
  symbol: string;
  quantity: number;
  average_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
}

interface Signal {
  signal_id: string;
  timestamp: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  strength: number;
  confidence: number;
  strategy_name: string;
  reason: string;
  executed: boolean;
}

interface TradingStatus {
  is_connected: boolean;
  account_id: string;
  cash_balance: number;
  buying_power: number;
  total_value: number;
  active_positions: number;
  open_orders: number;
  today_trades: number;
}

interface TradingState {
  status: TradingStatus | null;
  orders: Order[];
  positions: Position[];
  signals: Signal[];
  recentTrades: Trade[];
  performance: any | null;
  loading: boolean;
  error: string | null;
}

const initialState: TradingState = {
  status: null,
  orders: [],
  positions: [],
  signals: [],
  recentTrades: [],
  performance: null,
  loading: false,
  error: null,
};

// Async thunks
export const fetchTradingStatus = createAsyncThunk(
  'trading/fetchStatus',
  async () => {
    const response = await tradingApi.getStatus();
    return response.data;
  }
);

export const placeOrder = createAsyncThunk(
  'trading/placeOrder',
  async (data: any) => {
    const response = await tradingApi.placeOrder(data);
    return response.data;
  }
);

export const fetchOrders = createAsyncThunk(
  'trading/fetchOrders',
  async (params?: any) => {
    const response = await tradingApi.getOrders(params);
    return response.data;
  }
);

export const cancelOrder = createAsyncThunk(
  'trading/cancelOrder',
  async (id: string) => {
    await tradingApi.cancelOrder(id);
    return id;
  }
);

export const fetchPositions = createAsyncThunk(
  'trading/fetchPositions',
  async () => {
    const response = await tradingApi.getPositions();
    return response.data;
  }
);

export const fetchSignals = createAsyncThunk(
  'trading/fetchSignals',
  async (params?: any) => {
    const response = await tradingApi.getSignals(params);
    return response.data;
  }
);

export const executeSignal = createAsyncThunk(
  'trading/executeSignal',
  async (id: string) => {
    const response = await tradingApi.executeSignal(id);
    return { signalId: id, order: response.data };
  }
);

export const fetchPerformance = createAsyncThunk(
  'trading/fetchPerformance',
  async (period: string) => {
    const response = await tradingApi.getPerformance(period);
    return response.data;
  }
);

const tradingSlice = createSlice({
  name: 'trading',
  initialState,
  reducers: {
    updateOrderStatus: (state, action) => {
      const { orderId, status } = action.payload;
      const order = state.orders.find(o => o.order_id === orderId);
      if (order) {
        order.status = status;
      }
    },
    addSignal: (state, action) => {
      state.signals.unshift(action.payload);
      // Keep only last 100 signals
      if (state.signals.length > 100) {
        state.signals = state.signals.slice(0, 100);
      }
    },
    setRecentTrades: (state, action) => {
      state.recentTrades = action.payload;
    },
    updatePosition: (state, action) => {
      const position = action.payload;
      const index = state.positions.findIndex(p => p.symbol === position.symbol);
      if (index >= 0) {
        state.positions[index] = position;
      } else {
        state.positions.push(position);
      }
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch trading status
      .addCase(fetchTradingStatus.fulfilled, (state, action) => {
        state.status = action.payload;
      })
      // Place order
      .addCase(placeOrder.fulfilled, (state, action) => {
        state.orders.unshift(action.payload);
      })
      // Fetch orders
      .addCase(fetchOrders.fulfilled, (state, action) => {
        state.orders = action.payload;
      })
      // Cancel order
      .addCase(cancelOrder.fulfilled, (state, action) => {
        const order = state.orders.find(o => o.order_id === action.payload);
        if (order) {
          order.status = 'CANCELLED';
        }
      })
      // Fetch positions
      .addCase(fetchPositions.fulfilled, (state, action) => {
        state.positions = action.payload;
      })
      // Fetch signals
      .addCase(fetchSignals.fulfilled, (state, action) => {
        state.signals = action.payload;
      })
      // Execute signal
      .addCase(executeSignal.fulfilled, (state, action) => {
        const signal = state.signals.find(s => s.signal_id === action.payload.signalId);
        if (signal) {
          signal.executed = true;
        }
        state.orders.unshift(action.payload.order);
      })
      // Fetch performance
      .addCase(fetchPerformance.fulfilled, (state, action) => {
        state.performance = action.payload;
      });
  },
});

export const { updateOrderStatus, addSignal, updatePosition, setRecentTrades } = tradingSlice.actions;

// Additional trade-related actions
export const addTrade = tradingSlice.actions.addSignal; // Alias for trades
export const fetchRecentTrades = fetchOrders; // Alias for recent trades

export default tradingSlice.reducer;
// Market data state management slice

import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { dataApi } from '../../services/api';

interface Candle {
  timestamp: string;
  time?: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Symbol {
  symbol: string;
  name: string;
  exchange?: string;
  type?: string;
  data_start: string;
  data_end: string;
  candle_count: number;
}

interface Quote {
  symbol: string;
  last_price: number;
  bid_price: number;
  ask_price: number;
  bid_size: number;
  ask_size: number;
  volume: number;
  change: number;
  change_percent: number;
  timestamp: string;
}

export interface OrderBookEntry {
  price: number;
  quantity: number;
  total: number;
}

export interface Trade {
  id: string;
  price: number;
  quantity: number;
  timestamp: Date;
  side: 'buy' | 'sell';
}

export interface MarketStats {
  currentPrice: number;
  previousClose: number;
  dayChange: number;
  dayChangePercent: number;
  dayHigh: number;
  dayLow: number;
  volume: number;
  avgVolume: number;
  marketCap: number;
  week52High: number;
  week52Low: number;
  pe: number;
  eps: number;
  beta: number;
  dividend: number;
  dividendYield: number;
}

interface MarketDataState {
  symbols: Symbol[];
  selectedSymbol: string | null;
  selectedTimeframe: string;
  candles: { [key: string]: Candle[] };
  quotes: { [key: string]: Quote };
  orderbook: { [symbol: string]: { bids: OrderBookEntry[]; asks: OrderBookEntry[] } };
  trades: { [symbol: string]: Trade[] };
  stats: { [symbol: string]: MarketStats };
  recentSearches: string[];
  loading: boolean;
  error: string | null;
  wsConnected: boolean;
}

const initialState: MarketDataState = {
  symbols: [],
  selectedSymbol: null,
  selectedTimeframe: '5',
  candles: {},
  quotes: {},
  orderbook: {},
  trades: {},
  stats: {},
  recentSearches: [],
  loading: false,
  error: null,
  wsConnected: false,
};

// Async thunks
export const fetchSymbols = createAsyncThunk(
  'marketData/fetchSymbols',
  async () => {
    const response = await dataApi.getSymbols();
    return response.data;
  }
);

export const fetchCandles = createAsyncThunk(
  'marketData/fetchCandles',
  async ({ symbol, params }: { symbol: string; params: any }) => {
    const response = await dataApi.getCandles(symbol, params);
    return { symbol, candles: response.data };
  }
);

export const fetchQuote = createAsyncThunk(
  'marketData/fetchQuote',
  async (symbol: string) => {
    const response = await dataApi.getQuote(symbol);
    return response.data;
  }
);

const marketDataSlice = createSlice({
  name: 'marketData',
  initialState,
  reducers: {
    selectSymbol: (state, action: PayloadAction<string>) => {
      state.selectedSymbol = action.payload;
    },
    setTimeframe: (state, action: PayloadAction<string>) => {
      state.selectedTimeframe = action.payload;
    },
    updateCandle: (state, action: PayloadAction<{ symbol: string; candle: Candle }>) => {
      const { symbol, candle } = action.payload;
      if (!state.candles[symbol]) {
        state.candles[symbol] = [];
      }
      // Add or update candle
      const index = state.candles[symbol].findIndex(
        c => c.timestamp === candle.timestamp
      );
      if (index >= 0) {
        state.candles[symbol][index] = candle;
      } else {
        state.candles[symbol].push(candle);
        // Keep only last 1000 candles
        if (state.candles[symbol].length > 1000) {
          state.candles[symbol].shift();
        }
      }
    },
    updateQuote: (state, action: PayloadAction<Quote>) => {
      const quote = action.payload;
      state.quotes[quote.symbol] = quote;
    },
    updateOrderBook: (state, action: PayloadAction<{ 
      symbol: string; 
      bids: OrderBookEntry[]; 
      asks: OrderBookEntry[] 
    }>) => {
      const { symbol, bids, asks } = action.payload;
      state.orderbook[symbol] = { bids, asks };
    },
    addTrade: (state, action: PayloadAction<{ symbol: string; trade: Trade }>) => {
      const { symbol, trade } = action.payload;
      if (!state.trades[symbol]) {
        state.trades[symbol] = [];
      }
      state.trades[symbol].unshift(trade);
      // Keep only last 100 trades
      if (state.trades[symbol].length > 100) {
        state.trades[symbol] = state.trades[symbol].slice(0, 100);
      }
    },
    updateStats: (state, action: PayloadAction<{ symbol: string; stats: MarketStats }>) => {
      const { symbol, stats } = action.payload;
      state.stats[symbol] = stats;
    },
    addRecentSearch: (state, action: PayloadAction<string>) => {
      const symbol = action.payload;
      state.recentSearches = [symbol, ...state.recentSearches.filter(s => s !== symbol)].slice(0, 5);
    },
    setWsConnected: (state, action: PayloadAction<boolean>) => {
      state.wsConnected = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch symbols
      .addCase(fetchSymbols.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchSymbols.fulfilled, (state, action) => {
        state.loading = false;
        state.symbols = action.payload;
      })
      .addCase(fetchSymbols.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch symbols';
      })
      // Fetch candles
      .addCase(fetchCandles.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchCandles.fulfilled, (state, action) => {
        state.loading = false;
        state.candles[action.payload.symbol] = action.payload.candles;
      })
      .addCase(fetchCandles.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch candles';
      })
      // Fetch quote
      .addCase(fetchQuote.fulfilled, (state, action) => {
        state.quotes[action.payload.symbol] = action.payload;
      });
  },
});

export const { 
  selectSymbol, 
  setTimeframe,
  updateCandle, 
  updateQuote,
  updateOrderBook,
  addTrade,
  updateStats,
  addRecentSearch,
  setWsConnected,
} = marketDataSlice.actions;

// Additional action for updating full market data
export const updateMarketData = (state: any, action: any) => {
  const { symbol, bar } = action.payload;
  if (!state.candles[symbol]) {
    state.candles[symbol] = [];
  }
  state.candles[symbol].push(bar);
};

export default marketDataSlice.reducer;
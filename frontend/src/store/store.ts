// Redux store configuration

import { configureStore } from '@reduxjs/toolkit';
import { setupListeners } from '@reduxjs/toolkit/query';
import { apiSlice } from './api/apiSlice';
import { errorHandlerMiddleware } from '../services/errorHandler';

import authReducer from '../features/auth/authSlice';
import marketDataReducer from '../features/marketData/marketDataSlice';
import strategiesReducer from '../features/strategies/strategiesSlice';
import backtestReducer from '../features/backtest/backtestSlice';
import tradingReducer from '../features/trading/tradingSlice';
import portfolioReducer from '../features/portfolio/portfolioSlice';
import websocketReducer from '../features/websocket/websocketSlice';

export const store = configureStore({
  reducer: {
    [apiSlice.reducerPath]: apiSlice.reducer,
    auth: authReducer,
    marketData: marketDataReducer,
    strategies: strategiesReducer,
    backtest: backtestReducer,
    trading: tradingReducer,
    portfolio: portfolioReducer,
    websocket: websocketReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types
        ignoredActions: ['websocket/connect', 'websocket/disconnect'],
        // Ignore these field paths in all actions
        ignoredActionPaths: ['meta.arg', 'payload.timestamp'],
        // Ignore these paths in the state
        ignoredPaths: ['websocket.socket'],
      },
    })
      .concat(apiSlice.middleware)
      .concat(errorHandlerMiddleware),
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

// Enable refetchOnFocus/refetchOnReconnect behaviors
setupListeners(store.dispatch);
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { store } from '../store/store';

// In development, use relative URLs to work with proxy
// In production, use the full URL
const API_BASE_URL = process.env.NODE_ENV === 'development' 
  ? '' // Empty string for relative URLs in development
  : (process.env.REACT_APP_API_URL || 'https://127.0.0.1:8182');
const API_PREFIX = '/api';

// Create axios instance with default config
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear token and redirect to login
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// API endpoints
export const authApi = {
  getLoginUrl: () => api.get('/api/auth/login'),
  refreshToken: () => api.post('/api/auth/refresh'),
  getStatus: () => api.get('/api/auth/status'),
  logout: () => api.post('/api/auth/logout'),
};

export const dataApi = {
  getSymbols: () => api.get('/api/data/symbols'),
  getCandles: (symbol: string, params: any) => 
    api.get(`/api/data/candles/${symbol}`, { params }),
  fetchHistorical: (data: any) => api.post('/api/data/fetch-historical', data),
  getQuote: (symbol: string) => api.get(`/api/data/quote/${symbol}`),
  getDataGaps: (symbols: string[]) => 
    api.get('/api/data/data-gaps', { params: { symbols } }),
};

export const strategiesApi = {
  list: () => api.get('/api/strategies'),
  create: (data: any) => api.post('/api/strategies', data),
  get: (id: string) => api.get(`/api/strategies/${id}`),
  update: (id: string, data: any) => api.put(`/api/strategies/${id}`, data),
  delete: (id: string) => api.delete(`/api/strategies/${id}`),
  start: (id: string) => api.post(`/api/strategies/${id}/start`),
  stop: (id: string) => api.post(`/api/strategies/${id}/stop`),
  getPerformance: (id: string) => api.get(`/api/strategies/${id}/performance`),
};

export const backtestApi = {
  start: (data: any) => api.post('/api/backtest', data),
  getStatus: (id: string) => api.get(`/api/backtest/${id}/status`),
  getResult: (id: string) => api.get(`/api/backtest/${id}/result`),
  list: (params?: any) => api.get('/api/backtest', { params }),
  delete: (id: string) => api.delete(`/api/backtest/${id}`),
  compare: (ids: string[]) => api.post('/api/backtest/compare', { backtest_ids: ids }),
};

export const tradingApi = {
  getStatus: () => api.get('/api/trading/status'),
  placeOrder: (data: any) => api.post('/api/trading/orders', data),
  getOrders: (params?: any) => api.get('/api/trading/orders', { params }),
  getOrder: (id: string) => api.get(`/api/trading/orders/${id}`),
  cancelOrder: (id: string) => api.post(`/api/trading/orders/${id}/cancel`),
  getPositions: () => api.get('/api/trading/positions'),
  getSignals: (params?: any) => api.get('/api/trading/signals', { params }),
  executeSignal: (id: string) => api.post(`/api/trading/signals/${id}/execute`),
  getPerformance: (period: string) => 
    api.get('/api/trading/performance', { params: { period } }),
};

export const portfolioApi = {
  getSummary: () => api.get('/api/portfolio/summary'),
  getPositions: () => api.get('/api/portfolio/positions'),
  getPerformance: (period: string) => 
    api.get('/api/portfolio/performance', { params: { period } }),
  getAllocation: () => api.get('/api/portfolio/allocation'),
  getTransactions: (params?: any) => 
    api.get('/api/portfolio/transactions', { params }),
  rebalance: (targetAllocation: any) => 
    api.post('/api/portfolio/rebalance', { target_allocation: targetAllocation }),
};

export default api;
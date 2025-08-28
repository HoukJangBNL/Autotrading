import React, { useEffect, useState } from 'react';
import { 
  Box, 
  Grid, 
  Typography, 
  Paper,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { 
  selectSymbol, 
  setTimeframe, 
  fetchSymbols,
  addRecentSearch,
} from '../features/marketData/marketDataSlice';
import { SymbolSearch } from '../components/marketdata/SymbolSearch';
import { TradingChart } from '../components/marketdata/TradingChart';
import { OrderBook } from '../components/marketdata/OrderBook';
import { RecentTrades } from '../components/marketdata/RecentTrades';
import { MarketStatistics } from '../components/marketdata/MarketStatistics';
import { useWebSocket } from '../hooks/useWebSocket';

export const MarketData: React.FC = () => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  const { 
    selectedSymbol, 
    selectedTimeframe,
    candles,
    orderbook,
    trades,
    stats,
  } = useAppSelector((state) => state.marketData);
  
  // Initialize WebSocket for real-time data
  useWebSocket({
    onMarketData: (data) => {
      // Handle real-time market data updates
      console.log('Market data update:', data);
    },
  });
  
  useEffect(() => {
    // Load symbols on mount
    dispatch(fetchSymbols());
  }, [dispatch]);
  
  const handleSymbolSelect = (symbol: string) => {
    dispatch(selectSymbol(symbol));
    dispatch(addRecentSearch(symbol));
    // Subscribe to real-time data for the selected symbol
    // This would normally send a WebSocket message to subscribe
  };
  
  const handleTimeframeChange = (timeframe: string) => {
    dispatch(setTimeframe(timeframe));
    // Fetch new candle data for the selected timeframe
  };

  return (
    <Box sx={{ height: '100%', overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h4" gutterBottom>
          Market Data
        </Typography>
        <SymbolSearch 
          onSymbolSelect={handleSymbolSelect}
          currentSymbol={selectedSymbol || undefined}
        />
      </Box>
      
      {selectedSymbol ? (
        <Grid container spacing={2} sx={{ height: 'calc(100% - 60px)' }}>
          {/* Main Content Area */}
          <Grid item xs={12} md={8}>
            <Grid container spacing={2} sx={{ height: '100%' }}>
              {/* Chart */}
              <Grid item xs={12} sx={{ height: isMobile ? 400 : 600 }}>
                <TradingChart
                  symbol={selectedSymbol}
                  data={candles[selectedSymbol]}
                  onTimeframeChange={handleTimeframeChange}
                />
              </Grid>
              
              {/* Market Statistics */}
              {!isMobile && (
                <Grid item xs={12}>
                  <MarketStatistics
                    symbol={selectedSymbol}
                    stats={stats[selectedSymbol]}
                  />
                </Grid>
              )}
            </Grid>
          </Grid>
          
          {/* Right Sidebar */}
          <Grid item xs={12} md={4}>
            <Grid container spacing={2}>
              {/* Order Book */}
              <Grid item xs={12} sm={6} md={12}>
                <Box sx={{ height: isMobile ? 400 : 500 }}>
                  <OrderBook
                    symbol={selectedSymbol}
                    bids={orderbook[selectedSymbol]?.bids}
                    asks={orderbook[selectedSymbol]?.asks}
                  />
                </Box>
              </Grid>
              
              {/* Recent Trades */}
              <Grid item xs={12} sm={6} md={12}>
                <Box sx={{ height: isMobile ? 400 : 500 }}>
                  <RecentTrades
                    symbol={selectedSymbol}
                    trades={trades[selectedSymbol]}
                  />
                </Box>
              </Grid>
              
              {/* Market Statistics (Mobile) */}
              {isMobile && (
                <Grid item xs={12}>
                  <MarketStatistics
                    symbol={selectedSymbol}
                    stats={stats[selectedSymbol]}
                  />
                </Grid>
              )}
            </Grid>
          </Grid>
        </Grid>
      ) : (
        <Paper sx={{ p: 4, textAlign: 'center', mt: 8 }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            Select a symbol to view market data
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Use the search bar above to find and select a stock symbol
          </Typography>
        </Paper>
      )}
    </Box>
  );
};
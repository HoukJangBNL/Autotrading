import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Chip,
  Divider,
  LinearProgress,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  ShowChart as ChartIcon,
  AccessTime as TimeIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';

interface MarketStats {
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

interface MarketStatisticsProps {
  symbol: string;
  stats?: MarketStats;
}

export const MarketStatistics: React.FC<MarketStatisticsProps> = ({ symbol, stats }) => {
  const theme = useTheme();
  
  // Use provided stats or generate mock data
  const marketStats = stats || generateMockStats();
  
  const getPriceChangeColor = () => {
    return marketStats.dayChange >= 0 ? theme.palette.success.main : theme.palette.error.main;
  };
  
  const getPriceChangeIcon = () => {
    return marketStats.dayChange >= 0 ? <TrendingUpIcon /> : <TrendingDownIcon />;
  };
  
  const formatNumber = (num: number, decimals: number = 2) => {
    if (num >= 1e12) return `${(num / 1e12).toFixed(decimals)}T`;
    if (num >= 1e9) return `${(num / 1e9).toFixed(decimals)}B`;
    if (num >= 1e6) return `${(num / 1e6).toFixed(decimals)}M`;
    if (num >= 1e3) return `${(num / 1e3).toFixed(decimals)}K`;
    return num.toFixed(decimals);
  };
  
  const getDayRangePercent = () => {
    const range = marketStats.dayHigh - marketStats.dayLow;
    const position = marketStats.currentPrice - marketStats.dayLow;
    return range > 0 ? (position / range) * 100 : 50;
  };
  
  const get52WeekRangePercent = () => {
    const range = marketStats.week52High - marketStats.week52Low;
    const position = marketStats.currentPrice - marketStats.week52Low;
    return range > 0 ? (position / range) * 100 : 50;
  };

  return (
    <Paper sx={{ p: 2, height: '100%' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Market Statistics</Typography>
        <Chip 
          icon={<TimeIcon />} 
          label="Real-time" 
          size="small" 
          color="primary" 
          variant="outlined" 
        />
      </Box>
      
      {/* Price Section */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 2 }}>
          <Typography variant="h4" fontWeight="bold">
            ${marketStats.currentPrice.toFixed(2)}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', color: getPriceChangeColor() }}>
            {getPriceChangeIcon()}
            <Typography variant="h6" sx={{ ml: 0.5 }}>
              {marketStats.dayChange > 0 ? '+' : ''}{marketStats.dayChange.toFixed(2)} 
              ({marketStats.dayChangePercent > 0 ? '+' : ''}{marketStats.dayChangePercent.toFixed(2)}%)
            </Typography>
          </Box>
        </Box>
        <Typography variant="caption" color="text.secondary">
          {symbol} • Previous Close: ${marketStats.previousClose.toFixed(2)}
        </Typography>
      </Box>
      
      <Divider sx={{ my: 2 }} />
      
      {/* Key Stats Grid */}
      <Grid container spacing={2}>
        {/* Day Range */}
        <Grid item xs={12}>
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Day Range
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="body2">${marketStats.dayLow.toFixed(2)}</Typography>
              <Box sx={{ flex: 1, mx: 2 }}>
                <LinearProgress 
                  variant="determinate" 
                  value={getDayRangePercent()} 
                  sx={{ height: 6, borderRadius: 1 }}
                />
              </Box>
              <Typography variant="body2">${marketStats.dayHigh.toFixed(2)}</Typography>
            </Box>
          </Box>
        </Grid>
        
        {/* 52 Week Range */}
        <Grid item xs={12}>
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              52 Week Range
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="body2">${marketStats.week52Low.toFixed(2)}</Typography>
              <Box sx={{ flex: 1, mx: 2 }}>
                <LinearProgress 
                  variant="determinate" 
                  value={get52WeekRangePercent()} 
                  sx={{ height: 6, borderRadius: 1 }}
                  color="secondary"
                />
              </Box>
              <Typography variant="body2">${marketStats.week52High.toFixed(2)}</Typography>
            </Box>
          </Box>
        </Grid>
        
        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">Volume</Typography>
          <Typography variant="body1" fontWeight="medium">
            {formatNumber(marketStats.volume)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Avg: {formatNumber(marketStats.avgVolume)}
          </Typography>
        </Grid>
        
        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">Market Cap</Typography>
          <Typography variant="body1" fontWeight="medium">
            ${formatNumber(marketStats.marketCap)}
          </Typography>
        </Grid>
        
        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">P/E Ratio</Typography>
          <Typography variant="body1" fontWeight="medium">
            {marketStats.pe.toFixed(2)}
          </Typography>
        </Grid>
        
        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">EPS</Typography>
          <Typography variant="body1" fontWeight="medium">
            ${marketStats.eps.toFixed(2)}
          </Typography>
        </Grid>
        
        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">Beta</Typography>
          <Typography variant="body1" fontWeight="medium">
            {marketStats.beta.toFixed(2)}
          </Typography>
        </Grid>
        
        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">Div Yield</Typography>
          <Typography variant="body1" fontWeight="medium">
            {marketStats.dividendYield.toFixed(2)}%
          </Typography>
          <Typography variant="caption" color="text.secondary">
            ${marketStats.dividend.toFixed(2)}/share
          </Typography>
        </Grid>
      </Grid>
      
      <Divider sx={{ my: 2 }} />
      
      {/* Technical Indicators Preview */}
      <Box>
        <Typography variant="subtitle2" gutterBottom>
          Technical Indicators
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Chip 
            label="RSI: 58.3" 
            size="small" 
            color={58.3 > 70 ? 'error' : 58.3 < 30 ? 'success' : 'default'}
          />
          <Chip 
            label="MACD: Bullish" 
            size="small" 
            color="success"
          />
          <Chip 
            label="MA50 > MA200" 
            size="small" 
            color="success"
          />
          <Chip 
            label="Volume: Normal" 
            size="small" 
          />
        </Box>
      </Box>
    </Paper>
  );
};

// Helper function to generate mock stats
function generateMockStats(): MarketStats {
  const currentPrice = 182.45;
  const previousClose = 180.20;
  const dayChange = currentPrice - previousClose;
  const dayChangePercent = (dayChange / previousClose) * 100;
  
  return {
    currentPrice,
    previousClose,
    dayChange,
    dayChangePercent,
    dayHigh: 183.50,
    dayLow: 179.80,
    volume: 45678900,
    avgVolume: 52340000,
    marketCap: 2.85e12,
    week52High: 199.62,
    week52Low: 164.08,
    pe: 28.45,
    eps: 6.42,
    beta: 1.18,
    dividend: 0.96,
    dividendYield: 0.53,
  };
}
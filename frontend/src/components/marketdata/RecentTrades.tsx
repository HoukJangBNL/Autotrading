import React, { useEffect, useState, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Fade,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { format } from 'date-fns';

interface Trade {
  id: string;
  price: number;
  quantity: number;
  timestamp: Date;
  side: 'buy' | 'sell';
  isNew?: boolean;
}

interface RecentTradesProps {
  symbol: string;
  trades?: Trade[];
  maxTrades?: number;
}

export const RecentTrades: React.FC<RecentTradesProps> = ({ 
  symbol, 
  trades, 
  maxTrades = 50 
}) => {
  const theme = useTheme();
  const [recentTrades, setRecentTrades] = useState<Trade[]>([]);
  const [previousPrice, setPreviousPrice] = useState<number | null>(null);
  const tradesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (trades) {
      setRecentTrades(trades.slice(0, maxTrades));
    } else {
      // Generate mock trades if no data provided
      const mockTrades = generateMockTrades();
      setRecentTrades(mockTrades);
      
      // Simulate real-time trades
      const interval = setInterval(() => {
        const newTrade = generateSingleTrade(recentTrades.length);
        setRecentTrades((prev) => {
          const updated = [{ ...newTrade, isNew: true }, ...prev].slice(0, maxTrades);
          // Remove isNew flag after animation
          setTimeout(() => {
            setRecentTrades((trades) => 
              trades.map((t) => ({ ...t, isNew: false }))
            );
          }, 1000);
          return updated;
        });
      }, Math.random() * 3000 + 2000); // Random interval between 2-5 seconds
      
      return () => clearInterval(interval);
    }
  }, [trades, maxTrades]);

  const getPriceColor = (trade: Trade) => {
    if (trade.side === 'buy') return theme.palette.success.main;
    return theme.palette.error.main;
  };

  const getPriceIcon = (trade: Trade) => {
    if (trade.side === 'buy') {
      return <TrendingUpIcon sx={{ fontSize: 16, ml: 0.5 }} />;
    }
    return <TrendingDownIcon sx={{ fontSize: 16, ml: 0.5 }} />;
  };

  const formatTime = (timestamp: Date) => {
    return format(timestamp, 'HH:mm:ss');
  };

  return (
    <Paper sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Recent Trades</Typography>
        <Typography variant="body2" color="text.secondary">
          {symbol}
        </Typography>
      </Box>
      
      <TableContainer sx={{ flexGrow: 1, overflow: 'auto' }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold' }}>Time</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold' }}>Price</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold' }}>Quantity</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold' }}>Total</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {recentTrades.map((trade) => (
              <Fade in key={trade.id} timeout={500}>
                <TableRow
                  sx={{
                    backgroundColor: trade.isNew 
                      ? trade.side === 'buy' 
                        ? `${theme.palette.success.main}20`
                        : `${theme.palette.error.main}20`
                      : 'transparent',
                    transition: 'background-color 1s ease-out',
                  }}
                >
                  <TableCell sx={{ py: 0.5 }}>
                    <Typography variant="body2" color="text.secondary">
                      {formatTime(trade.timestamp)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right" sx={{ py: 0.5 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                      <Typography 
                        variant="body2" 
                        sx={{ 
                          color: getPriceColor(trade),
                          fontWeight: trade.isNew ? 'bold' : 'normal',
                        }}
                      >
                        ${trade.price.toFixed(2)}
                      </Typography>
                      {getPriceIcon(trade)}
                    </Box>
                  </TableCell>
                  <TableCell align="right" sx={{ py: 0.5 }}>
                    <Typography variant="body2">
                      {trade.quantity.toLocaleString()}
                    </Typography>
                  </TableCell>
                  <TableCell align="right" sx={{ py: 0.5 }}>
                    <Typography variant="body2" color="text.secondary">
                      ${(trade.price * trade.quantity).toFixed(2)}
                    </Typography>
                  </TableCell>
                </TableRow>
              </Fade>
            ))}
          </TableBody>
        </Table>
        <div ref={tradesEndRef} />
      </TableContainer>
      
      {/* Summary Stats */}
      <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="caption" color="text.secondary">
            Total Trades: {recentTrades.length}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Avg Size: {
              recentTrades.length > 0
                ? Math.round(
                    recentTrades.reduce((sum, t) => sum + t.quantity, 0) / 
                    recentTrades.length
                  ).toLocaleString()
                : 0
            }
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
          <Typography variant="caption" color="success.main">
            Buys: {recentTrades.filter((t) => t.side === 'buy').length}
          </Typography>
          <Typography variant="caption" color="error.main">
            Sells: {recentTrades.filter((t) => t.side === 'sell').length}
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
};

// Helper functions to generate mock data
function generateMockTrades(): Trade[] {
  const trades: Trade[] = [];
  const now = new Date();
  let basePrice = 180;
  
  for (let i = 0; i < 20; i++) {
    const trade = generateSingleTrade(i, basePrice);
    trades.push(trade);
    basePrice = trade.price; // Update base price for next trade
  }
  
  return trades;
}

function generateSingleTrade(index: number, basePrice: number = 180): Trade {
  const now = new Date();
  const priceChange = (Math.random() - 0.5) * 0.5;
  const price = basePrice + priceChange;
  const side = Math.random() > 0.5 ? 'buy' : 'sell';
  
  return {
    id: `trade-${Date.now()}-${index}`,
    price: parseFloat(price.toFixed(2)),
    quantity: Math.floor(Math.random() * 500) + 50,
    timestamp: new Date(now.getTime() - index * 5000), // 5 seconds apart
    side,
  };
}
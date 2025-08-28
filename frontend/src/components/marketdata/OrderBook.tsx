import React, { useEffect, useState } from 'react';
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
  Chip,
  LinearProgress,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';

interface OrderBookEntry {
  price: number;
  quantity: number;
  total: number;
}

interface OrderBookProps {
  symbol: string;
  bids?: OrderBookEntry[];
  asks?: OrderBookEntry[];
}

export const OrderBook: React.FC<OrderBookProps> = ({ symbol, bids, asks }) => {
  const theme = useTheme();
  const [orderBook, setOrderBook] = useState<{
    bids: OrderBookEntry[];
    asks: OrderBookEntry[];
    spread: number;
    spreadPercent: number;
  }>({
    bids: [],
    asks: [],
    spread: 0,
    spreadPercent: 0,
  });

  useEffect(() => {
    // Use provided data or generate mock data
    const mockBids = bids || generateMockOrderBook('bid');
    const mockAsks = asks || generateMockOrderBook('ask');
    
    const bestBid = mockBids[0]?.price || 0;
    const bestAsk = mockAsks[0]?.price || 0;
    const spread = bestAsk - bestBid;
    const spreadPercent = bestBid > 0 ? (spread / bestBid) * 100 : 0;
    
    setOrderBook({
      bids: mockBids,
      asks: mockAsks,
      spread,
      spreadPercent,
    });
  }, [bids, asks]);

  const getMaxQuantity = () => {
    const allQuantities = [...orderBook.bids, ...orderBook.asks].map((o) => o.quantity);
    return Math.max(...allQuantities, 1);
  };

  const maxQuantity = getMaxQuantity();

  return (
    <Paper sx={{ p: 2, height: '100%' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Order Book</Typography>
        <Typography variant="body2" color="text.secondary">
          {symbol}
        </Typography>
      </Box>
      
      {/* Spread Display */}
      <Box sx={{ mb: 2, textAlign: 'center' }}>
        <Chip
          label={`Spread: $${orderBook.spread.toFixed(2)} (${orderBook.spreadPercent.toFixed(2)}%)`}
          size="small"
          color="primary"
          variant="outlined"
        />
      </Box>
      
      <TableContainer sx={{ maxHeight: 500 }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell align="right" sx={{ fontWeight: 'bold' }}>Price</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold' }}>Quantity</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold' }}>Total</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {/* Asks (Sell Orders) - Reversed to show best ask at bottom */}
            {orderBook.asks.slice().reverse().map((ask, index) => (
              <TableRow key={`ask-${index}`}>
                <TableCell 
                  align="right" 
                  sx={{ 
                    color: theme.palette.error.main,
                    fontWeight: index === orderBook.asks.length - 1 ? 'bold' : 'normal',
                    position: 'relative',
                  }}
                >
                  <Box sx={{ position: 'relative' }}>
                    <Box
                      sx={{
                        position: 'absolute',
                        right: 0,
                        top: 0,
                        bottom: 0,
                        left: 0,
                        backgroundColor: theme.palette.error.main,
                        opacity: 0.1,
                        transform: `scaleX(${ask.quantity / maxQuantity})`,
                        transformOrigin: 'right',
                      }}
                    />
                    <Box sx={{ position: 'relative', zIndex: 1 }}>
                      ${ask.price.toFixed(2)}
                    </Box>
                  </Box>
                </TableCell>
                <TableCell align="right">{ask.quantity.toLocaleString()}</TableCell>
                <TableCell align="right">${ask.total.toLocaleString()}</TableCell>
              </TableRow>
            ))}
            
            {/* Spread Row */}
            <TableRow>
              <TableCell 
                colSpan={3} 
                align="center" 
                sx={{ 
                  py: 1,
                  backgroundColor: theme.palette.action.hover,
                  borderTop: `2px solid ${theme.palette.divider}`,
                  borderBottom: `2px solid ${theme.palette.divider}`,
                }}
              >
                <Typography variant="caption" fontWeight="bold">
                  SPREAD
                </Typography>
              </TableCell>
            </TableRow>
            
            {/* Bids (Buy Orders) */}
            {orderBook.bids.map((bid, index) => (
              <TableRow key={`bid-${index}`}>
                <TableCell 
                  align="right" 
                  sx={{ 
                    color: theme.palette.success.main,
                    fontWeight: index === 0 ? 'bold' : 'normal',
                    position: 'relative',
                  }}
                >
                  <Box sx={{ position: 'relative' }}>
                    <Box
                      sx={{
                        position: 'absolute',
                        right: 0,
                        top: 0,
                        bottom: 0,
                        left: 0,
                        backgroundColor: theme.palette.success.main,
                        opacity: 0.1,
                        transform: `scaleX(${bid.quantity / maxQuantity})`,
                        transformOrigin: 'right',
                      }}
                    />
                    <Box sx={{ position: 'relative', zIndex: 1 }}>
                      ${bid.price.toFixed(2)}
                    </Box>
                  </Box>
                </TableCell>
                <TableCell align="right">{bid.quantity.toLocaleString()}</TableCell>
                <TableCell align="right">${bid.total.toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      
      {/* Depth Indicator */}
      <Box sx={{ mt: 2 }}>
        <Typography variant="caption" color="text.secondary">
          Order Depth
        </Typography>
        <Box sx={{ display: 'flex', mt: 0.5 }}>
          <Box sx={{ flex: 1, mr: 0.5 }}>
            <LinearProgress
              variant="determinate"
              value={75}
              sx={{
                backgroundColor: theme.palette.error.light,
                '& .MuiLinearProgress-bar': {
                  backgroundColor: theme.palette.error.main,
                },
              }}
            />
            <Typography variant="caption" color="text.secondary">
              Asks: ${orderBook.asks.reduce((sum, a) => sum + a.total, 0).toLocaleString()}
            </Typography>
          </Box>
          <Box sx={{ flex: 1, ml: 0.5 }}>
            <LinearProgress
              variant="determinate"
              value={65}
              sx={{
                backgroundColor: theme.palette.success.light,
                '& .MuiLinearProgress-bar': {
                  backgroundColor: theme.palette.success.main,
                },
              }}
            />
            <Typography variant="caption" color="text.secondary">
              Bids: ${orderBook.bids.reduce((sum, b) => sum + b.total, 0).toLocaleString()}
            </Typography>
          </Box>
        </Box>
      </Box>
    </Paper>
  );
};

// Helper function to generate mock order book data
function generateMockOrderBook(side: 'bid' | 'ask'): OrderBookEntry[] {
  const orders: OrderBookEntry[] = [];
  const basePrice = 180;
  
  for (let i = 0; i < 10; i++) {
    const priceOffset = (i + 1) * 0.05;
    const price = side === 'bid' 
      ? basePrice - priceOffset 
      : basePrice + priceOffset;
    
    const quantity = Math.floor(Math.random() * 1000) + 100;
    const total = price * quantity;
    
    orders.push({
      price: parseFloat(price.toFixed(2)),
      quantity,
      total: parseFloat(total.toFixed(2)),
    });
  }
  
  return orders;
}
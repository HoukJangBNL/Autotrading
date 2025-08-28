import React from 'react';
import {
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Box,
  Chip,
  LinearProgress,
  useTheme,
} from '@mui/material';
import { format } from 'date-fns';
import { Trade } from '../../features/trading/tradingSlice';

interface RecentTradesWidgetProps {
  trades: Trade[];
  loading?: boolean;
  onTradeClick?: (trade: Trade) => void;
}

export const RecentTradesWidget: React.FC<RecentTradesWidgetProps> = ({
  trades,
  loading = false,
  onTradeClick,
}) => {
  const theme = useTheme();

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatTime = (timestamp: string) => {
    return format(new Date(timestamp), 'HH:mm:ss');
  };

  const formatDate = (timestamp: string) => {
    return format(new Date(timestamp), 'MMM dd');
  };

  const getSideColor = (side: 'buy' | 'sell') => {
    return side === 'buy' ? theme.palette.success.main : theme.palette.error.main;
  };

  const getSideChipColor = (side: 'buy' | 'sell') => {
    return side === 'buy' ? 'success' : 'error';
  };

  return (
    <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">Recent Trades</Typography>
        <Typography variant="body2" color="text.secondary">
          Today
        </Typography>
      </Box>

      {loading ? (
        <LinearProgress />
      ) : trades.length === 0 ? (
        <Box
          display="flex"
          alignItems="center"
          justifyContent="center"
          flexGrow={1}
          color="text.secondary"
        >
          <Typography>No trades today</Typography>
        </Box>
      ) : (
        <TableContainer sx={{ flexGrow: 1 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Time</TableCell>
                <TableCell>Symbol</TableCell>
                <TableCell>Side</TableCell>
                <TableCell align="right">Qty</TableCell>
                <TableCell align="right">Price</TableCell>
                <TableCell align="right">Total</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {trades.slice(0, 10).map((trade) => (
                <TableRow
                  key={trade.id}
                  hover
                  onClick={() => onTradeClick?.(trade)}
                  sx={{ cursor: onTradeClick ? 'pointer' : 'default' }}
                >
                  <TableCell>
                    <Box>
                      <Typography variant="body2">
                        {formatTime(trade.timestamp)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(trade.timestamp)}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {trade.symbol}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={trade.side.toUpperCase()}
                      size="small"
                      color={getSideChipColor(trade.side)}
                    />
                  </TableCell>
                  <TableCell align="right">{trade.quantity}</TableCell>
                  <TableCell align="right">
                    {formatCurrency(trade.price)}
                  </TableCell>
                  <TableCell align="right">
                    <Typography
                      variant="body2"
                      fontWeight="medium"
                      color={getSideColor(trade.side)}
                    >
                      {formatCurrency(trade.quantity * trade.price)}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      
      {trades.length > 10 && (
        <Box mt={2} display="flex" justifyContent="center">
          <Typography variant="caption" color="text.secondary">
            Showing latest 10 trades
          </Typography>
        </Box>
      )}
    </Paper>
  );
};
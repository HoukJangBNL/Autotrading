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
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { Position } from '../../features/portfolio/portfolioSlice';

interface PositionsWidgetProps {
  positions: Position[];
  loading?: boolean;
  onPositionClick?: (position: Position) => void;
}

export const PositionsWidget: React.FC<PositionsWidgetProps> = ({
  positions,
  loading = false,
  onPositionClick,
}) => {
  const theme = useTheme();

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const getProfitLossColor = (value: number) => {
    return value >= 0 ? theme.palette.success.main : theme.palette.error.main;
  };

  return (
    <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">Active Positions</Typography>
        <Chip 
          label={`${positions.length} positions`} 
          size="small" 
          variant="outlined"
        />
      </Box>

      {loading ? (
        <LinearProgress />
      ) : positions.length === 0 ? (
        <Box
          display="flex"
          alignItems="center"
          justifyContent="center"
          flexGrow={1}
          color="text.secondary"
        >
          <Typography>No active positions</Typography>
        </Box>
      ) : (
        <TableContainer sx={{ flexGrow: 1 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Symbol</TableCell>
                <TableCell align="right">Qty</TableCell>
                <TableCell align="right">Avg Cost</TableCell>
                <TableCell align="right">Current</TableCell>
                <TableCell align="right">P&L</TableCell>
                <TableCell align="right">Value</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {positions.map((position) => (
                <TableRow
                  key={position.symbol}
                  hover
                  onClick={() => onPositionClick?.(position)}
                  sx={{ cursor: onPositionClick ? 'pointer' : 'default' }}
                >
                  <TableCell>
                    <Box display="flex" alignItems="center" gap={1}>
                      <Typography variant="body2" fontWeight="medium">
                        {position.symbol}
                      </Typography>
                      {position.side === 'short' && (
                        <Chip label="SHORT" size="small" color="error" />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell align="right">{position.quantity}</TableCell>
                  <TableCell align="right">
                    {formatCurrency(position.avg_cost)}
                  </TableCell>
                  <TableCell align="right">
                    {formatCurrency(position.current_price || 0)}
                  </TableCell>
                  <TableCell align="right">
                    <Box display="flex" alignItems="center" justifyContent="flex-end" gap={0.5}>
                      {position.unrealized_pnl !== undefined && position.unrealized_pnl >= 0 ? (
                        <TrendingUpIcon fontSize="small" color="success" />
                      ) : (
                        <TrendingDownIcon fontSize="small" color="error" />
                      )}
                      <Box>
                        <Typography
                          variant="body2"
                          color={getProfitLossColor(position.unrealized_pnl || 0)}
                        >
                          {formatCurrency(position.unrealized_pnl || 0)}
                        </Typography>
                        <Typography
                          variant="caption"
                          color={getProfitLossColor(position.unrealized_pnl_pct || 0)}
                        >
                          {formatPercent(position.unrealized_pnl_pct || 0)}
                        </Typography>
                      </Box>
                    </Box>
                  </TableCell>
                  <TableCell align="right">
                    {formatCurrency(position.market_value || 0)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Paper>
  );
};
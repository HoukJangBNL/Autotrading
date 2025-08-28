import React, { useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  CircularProgress,
} from '@mui/material';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import {
  fetchPortfolioSummary,
  fetchPortfolioPositions,
  fetchAssetAllocation,
} from '../features/portfolio/portfolioSlice';
import { usePortfolioUpdates } from '../hooks/useWebSocket';

export const Portfolio: React.FC = () => {
  const dispatch = useAppDispatch();
  const { summary, positions, allocation, loading } = useAppSelector((state) => state.portfolio);
  
  // Subscribe to real-time portfolio updates
  usePortfolioUpdates();

  useEffect(() => {
    dispatch(fetchPortfolioSummary());
    dispatch(fetchPortfolioPositions());
    dispatch(fetchAssetAllocation());
  }, [dispatch]);

  const formatCurrency = (value: number | undefined) => {
    if (value === undefined) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };

  const formatPercent = (value: number | undefined) => {
    if (value === undefined) return '0%';
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const getColorForChange = (value: number | undefined) => {
    if (!value) return 'text.secondary';
    return value >= 0 ? 'success.main' : 'error.main';
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Portfolio
      </Typography>

      <Grid container spacing={3}>
        {/* Summary Cards */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Total Value
              </Typography>
              <Typography variant="h5">
                {formatCurrency(summary?.total_value)}
              </Typography>
              <Typography variant="body2" color="success.main">
                {formatPercent(summary?.total_change_pct)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Day Change
              </Typography>
              <Typography variant="h5">
                {formatCurrency(summary?.day_change)}
              </Typography>
              <Typography variant="body2" color={summary?.day_change_pct && summary.day_change_pct >= 0 ? 'success.main' : 'error.main'}>
                {formatPercent(summary?.day_change_pct)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Cash Balance
              </Typography>
              <Typography variant="h5">
                {formatCurrency(summary?.cash_balance)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {((summary?.cash_balance || 0) / (summary?.total_value || 1) * 100).toFixed(1)}% of total
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Positions
              </Typography>
              <Typography variant="h5">
                {positions.length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active holdings
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Asset Allocation */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Asset Allocation
            </Typography>
            <Box
              display="flex"
              justifyContent="center"
              alignItems="center"
              height="calc(100% - 40px)"
              color="text.secondary"
            >
              {loading ? 'Loading allocation...' : 'Allocation chart will be implemented here'}
            </Box>
          </Paper>
        </Grid>

        {/* Performance Chart */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Performance
            </Typography>
            <Box
              display="flex"
              justifyContent="center"
              alignItems="center"
              height="calc(100% - 40px)"
              color="text.secondary"
            >
              Performance chart will be implemented here
            </Box>
          </Paper>
        </Grid>

        {/* Holdings Table */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Holdings
            </Typography>
            {loading ? (
              <Box display="flex" justifyContent="center" alignItems="center" height={300}>
                <CircularProgress />
              </Box>
            ) : positions.length === 0 ? (
              <Box
                display="flex"
                justifyContent="center"
                alignItems="center"
                height={300}
                color="text.secondary"
              >
                No positions found
              </Box>
            ) : (
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Symbol</TableCell>
                      <TableCell align="right">Quantity</TableCell>
                      <TableCell align="right">Avg Cost</TableCell>
                      <TableCell align="right">Current Price</TableCell>
                      <TableCell align="right">Market Value</TableCell>
                      <TableCell align="right">Unrealized P&L</TableCell>
                      <TableCell align="right">% Change</TableCell>
                      <TableCell align="center">Type</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {positions.map((position: any) => (
                      <TableRow key={position.symbol}>
                        <TableCell>
                          <Typography variant="body1" fontWeight="medium">
                            {position.symbol}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">{position.quantity?.toFixed(2)}</TableCell>
                        <TableCell align="right">
                          {formatCurrency(position.averageCost || position.average_cost)}
                        </TableCell>
                        <TableCell align="right">
                          {formatCurrency(position.currentPrice || position.current_price)}
                        </TableCell>
                        <TableCell align="right">
                          {formatCurrency(position.marketValue || position.market_value)}
                        </TableCell>
                        <TableCell align="right">
                          <Typography
                            color={getColorForChange(position.unrealizedPnl || position.unrealized_pnl)}
                          >
                            {formatCurrency(position.unrealizedPnl || position.unrealized_pnl)}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Chip
                            label={formatPercent(position.unrealizedPnlPercent || position.unrealized_pnl_pct)}
                            size="small"
                            color={(position.unrealizedPnlPercent || position.unrealized_pnl_pct || 0) >= 0 ? 'success' : 'error'}
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            label={position.assetType || position.position_type || 'EQUITY'}
                            size="small"
                            variant="outlined"
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};
import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Card,
  CardContent,
  Alert,
} from '@mui/material';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useTheme } from '@mui/material/styles';
import { BacktestResult, Trade } from '../../types/strategy';
import { format } from 'date-fns';

interface BacktestResultsProps {
  result: BacktestResult;
}

export const BacktestResults: React.FC<BacktestResultsProps> = ({ result }) => {
  const theme = useTheme();

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };

  const formatPercent = (value: number) => {
    const formatted = value.toFixed(2);
    return value >= 0 ? `+${formatted}%` : `${formatted}%`;
  };

  const tradeColumns: GridColDef[] = [
    {
      field: 'entryTime',
      headerName: 'Entry Time',
      width: 150,
      valueFormatter: (params) => format(new Date(params.value), 'MM/dd/yyyy HH:mm'),
    },
    {
      field: 'symbol',
      headerName: 'Symbol',
      width: 100,
    },
    {
      field: 'side',
      headerName: 'Side',
      width: 80,
      renderCell: (params) => (
        <Chip
          label={params.value}
          size="small"
          color={params.value === 'BUY' ? 'success' : 'error'}
        />
      ),
    },
    {
      field: 'quantity',
      headerName: 'Qty',
      width: 80,
      type: 'number',
    },
    {
      field: 'entryPrice',
      headerName: 'Entry',
      width: 100,
      type: 'number',
      valueFormatter: (params) => `$${params.value.toFixed(2)}`,
    },
    {
      field: 'exitPrice',
      headerName: 'Exit',
      width: 100,
      type: 'number',
      valueFormatter: (params) => params.value ? `$${params.value.toFixed(2)}` : '-',
    },
    {
      field: 'pnl',
      headerName: 'P&L',
      width: 120,
      type: 'number',
      renderCell: (params) => {
        const value = params.value || 0;
        return (
          <Typography
            color={value >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {formatCurrency(value)}
          </Typography>
        );
      },
    },
    {
      field: 'pnlPercent',
      headerName: 'P&L %',
      width: 100,
      type: 'number',
      renderCell: (params) => {
        const value = params.value || 0;
        return (
          <Typography
            color={value >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {formatPercent(value)}
          </Typography>
        );
      },
    },
  ];

  const getMonthlyReturnsData = () => {
    const months = Object.keys(result.monthlyReturns || {});
    return months.map((month) => ({
      month,
      return: result.monthlyReturns[month],
    }));
  };

  if (!result.performance) {
    return (
      <Alert severity="warning">
        No backtest results available. Run a backtest to see performance metrics.
      </Alert>
    );
  }

  return (
    <Box>
      {/* Performance Metrics Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Total Return
              </Typography>
              <Typography
                variant="h5"
                color={result.performance.totalReturn >= 0 ? 'success.main' : 'error.main'}
              >
                {formatPercent(result.performance.totalReturn)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Sharpe Ratio
              </Typography>
              <Typography variant="h5">
                {result.performance.sharpeRatio.toFixed(2)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Max Drawdown
              </Typography>
              <Typography variant="h5" color="error.main">
                {formatPercent(result.performance.maxDrawdown)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Win Rate
              </Typography>
              <Typography variant="h5">
                {(result.performance.winRate * 100).toFixed(1)}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Equity Curve */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Equity Curve
        </Typography>
        <ResponsiveContainer width="100%" height={400}>
          <AreaChart data={result.equityCurve}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey="date" 
              tickFormatter={(value) => format(new Date(value), 'MM/dd')}
            />
            <YAxis 
              tickFormatter={(value) => `$${(value / 1000).toFixed(0)}K`}
            />
            <Tooltip
              formatter={(value: number) => formatCurrency(value)}
              labelFormatter={(label) => format(new Date(label), 'MMM dd, yyyy')}
            />
            <ReferenceLine 
              y={result.config.initialCapital} 
              stroke={theme.palette.divider}
              strokeDasharray="3 3"
              label="Initial"
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={theme.palette.primary.main}
              fill={theme.palette.primary.light}
              fillOpacity={0.3}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Paper>

      {/* Monthly Returns */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Monthly Returns
        </Typography>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={getMonthlyReturnsData()}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" />
            <YAxis tickFormatter={(value) => `${value}%`} />
            <Tooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
            <ReferenceLine y={0} stroke={theme.palette.divider} />
            <Line
              type="monotone"
              dataKey="return"
              stroke={theme.palette.primary.main}
              strokeWidth={2}
              dot={{ fill: theme.palette.primary.main }}
            />
          </LineChart>
        </ResponsiveContainer>
      </Paper>

      {/* Detailed Metrics Table */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Performance Metrics
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableBody>
                  <TableRow>
                    <TableCell>Annualized Return</TableCell>
                    <TableCell align="right">
                      <strong>{formatPercent(result.performance.annualizedReturn)}</strong>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Total Trades</TableCell>
                    <TableCell align="right">
                      <strong>{result.performance.totalTrades}</strong>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Profit Factor</TableCell>
                    <TableCell align="right">
                      <strong>{result.performance.profitFactor.toFixed(2)}</strong>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Average Win</TableCell>
                    <TableCell align="right">
                      <strong>{formatCurrency(result.performance.avgWin)}</strong>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Average Loss</TableCell>
                    <TableCell align="right">
                      <strong>{formatCurrency(result.performance.avgLoss)}</strong>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Backtest Configuration
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableBody>
                  <TableRow>
                    <TableCell>Period</TableCell>
                    <TableCell align="right">
                      <strong>
                        {format(new Date(result.config.startDate), 'MM/dd/yyyy')} - 
                        {format(new Date(result.config.endDate), 'MM/dd/yyyy')}
                      </strong>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Initial Capital</TableCell>
                    <TableCell align="right">
                      <strong>{formatCurrency(result.config.initialCapital)}</strong>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Commission</TableCell>
                    <TableCell align="right">
                      <strong>{result.config.commission}%</strong>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Slippage</TableCell>
                    <TableCell align="right">
                      <strong>{result.config.slippage}%</strong>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">
                      <Chip
                        label={result.status}
                        size="small"
                        color={result.status === 'completed' ? 'success' : 'warning'}
                      />
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>
      </Grid>

      {/* Trade History */}
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Trade History
        </Typography>
        <DataGrid
          rows={result.trades}
          columns={tradeColumns}
          initialState={{
            pagination: {
              paginationModel: { pageSize: 10 },
            },
          }}
          pageSizeOptions={[10, 25, 50]}
          autoHeight
          disableRowSelectionOnClick
        />
      </Paper>
    </Box>
  );
};
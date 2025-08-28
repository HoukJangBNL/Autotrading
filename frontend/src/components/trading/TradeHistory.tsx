import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Grid,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import DownloadIcon from '@mui/icons-material/Download';
import FilterListIcon from '@mui/icons-material/FilterList';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useTheme } from '@mui/material/styles';
import { format } from 'date-fns';
import { OrderSide } from '../../types/index';

interface Trade {
  id: string;
  orderId: string;
  symbol: string;
  side: OrderSide;
  quantity: number;
  price: number;
  commission: number;
  executedAt: string;
  pnl?: number;
  notes?: string;
}

interface TradeHistoryProps {
  trades?: Trade[];
  onExport?: () => void;
}

export const TradeHistory: React.FC<TradeHistoryProps> = ({ trades = [], onExport }) => {
  const theme = useTheme();
  const [filterSymbol, setFilterSymbol] = useState('');
  const [filterSide, setFilterSide] = useState('ALL');
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  // Mock data for demonstration
  const mockTrades: Trade[] = [
    {
      id: '1',
      orderId: 'ord1',
      symbol: 'AAPL',
      side: OrderSide.BUY,
      quantity: 100,
      price: 175.25,
      commission: 0.65,
      executedAt: new Date().toISOString(),
      pnl: undefined,
    },
    {
      id: '2',
      orderId: 'ord2',
      symbol: 'MSFT',
      side: OrderSide.SELL,
      quantity: 50,
      price: 425.50,
      commission: 0.65,
      executedAt: new Date(Date.now() - 3600000).toISOString(),
      pnl: 250.00,
    },
    {
      id: '3',
      orderId: 'ord3',
      symbol: 'GOOGL',
      side: OrderSide.BUY,
      quantity: 25,
      price: 142.75,
      commission: 0.65,
      executedAt: new Date(Date.now() - 7200000).toISOString(),
      pnl: undefined,
    },
    {
      id: '4',
      orderId: 'ord4',
      symbol: 'AAPL',
      side: OrderSide.SELL,
      quantity: 100,
      price: 176.50,
      commission: 0.65,
      executedAt: new Date(Date.now() - 10800000).toISOString(),
      pnl: 125.00,
    },
  ];

  const displayTrades = trades.length > 0 ? trades : mockTrades;

  // Apply filters
  const filteredTrades = displayTrades.filter(trade => {
    if (filterSymbol && !trade.symbol.toLowerCase().includes(filterSymbol.toLowerCase())) {
      return false;
    }
    if (filterSide !== 'ALL' && trade.side !== filterSide) {
      return false;
    }
    if (startDate && new Date(trade.executedAt) < startDate) {
      return false;
    }
    if (endDate && new Date(trade.executedAt) > endDate) {
      return false;
    }
    return true;
  });

  const columns: GridColDef[] = [
    {
      field: 'executedAt',
      headerName: 'Time',
      width: 150,
      valueFormatter: (params) => format(new Date(params.value), 'MM/dd HH:mm:ss'),
    },
    {
      field: 'symbol',
      headerName: 'Symbol',
      width: 80,
      renderCell: (params: GridRenderCellParams) => (
        <Typography fontWeight="bold">{params.value}</Typography>
      ),
    },
    {
      field: 'side',
      headerName: 'Side',
      width: 70,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={params.value}
          size="small"
          sx={{
            bgcolor: params.value === OrderSide.BUY 
              ? theme.palette.success.light 
              : theme.palette.error.light,
            color: params.value === OrderSide.BUY 
              ? theme.palette.success.contrastText 
              : theme.palette.error.contrastText,
          }}
        />
      ),
    },
    {
      field: 'quantity',
      headerName: 'Qty',
      width: 70,
      type: 'number',
    },
    {
      field: 'price',
      headerName: 'Price',
      width: 90,
      type: 'number',
      valueFormatter: (params) => `$${params.value.toFixed(2)}`,
    },
    {
      field: 'value',
      headerName: 'Value',
      width: 110,
      type: 'number',
      valueGetter: (params) => params.row.quantity * params.row.price,
      valueFormatter: (params) => `$${params.value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
    },
    {
      field: 'commission',
      headerName: 'Comm',
      width: 70,
      type: 'number',
      valueFormatter: (params) => `$${params.value.toFixed(2)}`,
    },
    {
      field: 'pnl',
      headerName: 'P&L',
      width: 100,
      type: 'number',
      renderCell: (params: GridRenderCellParams) => {
        if (params.value === undefined || params.value === null) {
          return <Typography color="text.secondary">-</Typography>;
        }
        return (
          <Typography
            color={params.value >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {params.value >= 0 ? '+' : ''}${Math.abs(params.value).toFixed(2)}
          </Typography>
        );
      },
    },
    {
      field: 'orderId',
      headerName: 'Order ID',
      width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Typography variant="caption" color="text.secondary">
          {params.value}
        </Typography>
      ),
    },
  ];

  // Calculate summary statistics
  const totalTrades = filteredTrades.length;
  const totalVolume = filteredTrades.reduce((sum, trade) => sum + (trade.quantity * trade.price), 0);
  const totalCommission = filteredTrades.reduce((sum, trade) => sum + trade.commission, 0);
  const totalPnL = filteredTrades.reduce((sum, trade) => sum + (trade.pnl || 0), 0);
  const winningTrades = filteredTrades.filter(t => t.pnl && t.pnl > 0).length;
  const losingTrades = filteredTrades.filter(t => t.pnl && t.pnl < 0).length;

  return (
    <Paper sx={{ p: 2 }}>
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">
          Trade History
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <IconButton
            onClick={() => setShowFilters(!showFilters)}
            size="small"
            color={showFilters ? 'primary' : 'default'}
            title="Toggle Filters"
          >
            <FilterListIcon />
          </IconButton>
          <IconButton onClick={onExport} size="small" title="Export Trades">
            <DownloadIcon />
          </IconButton>
        </Box>
      </Box>

      {showFilters && (
        <LocalizationProvider dateAdapter={AdapterDateFns}>
          <Box sx={{ mb: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 3 }}>
                <TextField
                  fullWidth
                  size="small"
                  label="Symbol"
                  value={filterSymbol}
                  onChange={(e) => setFilterSymbol(e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 3 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Side</InputLabel>
                  <Select
                    value={filterSide}
                    onChange={(e) => setFilterSide(e.target.value)}
                    label="Side"
                  >
                    <MenuItem value="ALL">All</MenuItem>
                    <MenuItem value={OrderSide.BUY}>Buy</MenuItem>
                    <MenuItem value={OrderSide.SELL}>Sell</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 3 }}>
                <DatePicker
                  label="Start Date"
                  value={startDate}
                  onChange={(newValue) => setStartDate(newValue)}
                  slotProps={{ textField: { fullWidth: true, size: 'small' } }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 3 }}>
                <DatePicker
                  label="End Date"
                  value={endDate}
                  onChange={(newValue) => setEndDate(newValue)}
                  slotProps={{ textField: { fullWidth: true, size: 'small' } }}
                />
              </Grid>
            </Grid>
          </Box>
        </LocalizationProvider>
      )}

      {/* Summary Statistics */}
      <Box sx={{ mb: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
        <Grid container spacing={3}>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="caption" color="text.secondary">
              Total Trades
            </Typography>
            <Typography variant="h6">
              {totalTrades}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="caption" color="text.secondary">
              Total Volume
            </Typography>
            <Typography variant="h6">
              ${totalVolume.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="caption" color="text.secondary">
              Total P&L
            </Typography>
            <Typography
              variant="h6"
              color={totalPnL >= 0 ? 'success.main' : 'error.main'}
            >
              {totalPnL >= 0 ? '+' : ''}${Math.abs(totalPnL).toFixed(2)}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="caption" color="text.secondary">
              Win Rate
            </Typography>
            <Typography variant="h6">
              {winningTrades + losingTrades > 0
                ? `${((winningTrades / (winningTrades + losingTrades)) * 100).toFixed(1)}%`
                : 'N/A'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              ({winningTrades}W / {losingTrades}L)
            </Typography>
          </Grid>
        </Grid>
      </Box>

      <DataGrid
        rows={filteredTrades}
        columns={columns}
        initialState={{
          pagination: {
            paginationModel: { pageSize: 10 },
          },
          sorting: {
            sortModel: [{ field: 'executedAt', sort: 'desc' }],
          },
        }}
        pageSizeOptions={[10, 25, 50, 100]}
        autoHeight
        disableRowSelectionOnClick
        sx={{
          '& .MuiDataGrid-row:hover': {
            backgroundColor: theme.palette.action.hover,
          },
        }}
      />
    </Paper>
  );
};
import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import CloseIcon from '@mui/icons-material/Close';
import EditIcon from '@mui/icons-material/Edit';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { useTheme } from '@mui/material/styles';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { Position } from '../../types/index';

interface PositionsTableProps {
  onClose?: (position: Position) => void;
  onModify?: (position: Position, quantity: number) => void;
}

export const PositionsTable: React.FC<PositionsTableProps> = ({ onClose, onModify }) => {
  const theme = useTheme();
  const { positions } = useAppSelector((state) => state.portfolio);
  const [selectedPosition, setSelectedPosition] = useState<Position | null>(null);
  const [closeDialogOpen, setCloseDialogOpen] = useState(false);
  const [modifyDialogOpen, setModifyDialogOpen] = useState(false);
  const [closeQuantity, setCloseQuantity] = useState('');
  const [modifyQuantity, setModifyQuantity] = useState('');
  const [error, setError] = useState('');

  const handleClosePosition = (position: Position) => {
    setSelectedPosition(position);
    setCloseQuantity(position.quantity.toString());
    setCloseDialogOpen(true);
  };

  const handleModifyPosition = (position: Position) => {
    setSelectedPosition(position);
    setModifyQuantity(position.quantity.toString());
    setModifyDialogOpen(true);
  };

  const confirmClosePosition = () => {
    if (!selectedPosition) return;

    const qty = parseFloat(closeQuantity);
    if (isNaN(qty) || qty <= 0 || qty > selectedPosition.quantity) {
      setError('Invalid quantity');
      return;
    }

    if (onClose) {
      onClose({ ...selectedPosition, quantity: qty });
    }

    setCloseDialogOpen(false);
    setSelectedPosition(null);
    setCloseQuantity('');
    setError('');
  };

  const confirmModifyPosition = () => {
    if (!selectedPosition) return;

    const qty = parseFloat(modifyQuantity);
    if (isNaN(qty) || qty <= 0) {
      setError('Invalid quantity');
      return;
    }

    if (onModify) {
      onModify(selectedPosition, qty);
    }

    setModifyDialogOpen(false);
    setSelectedPosition(null);
    setModifyQuantity('');
    setError('');
  };

  const columns: GridColDef[] = [
    {
      field: 'symbol',
      headerName: 'Symbol',
      width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Typography fontWeight="bold">{params.value}</Typography>
      ),
    },
    {
      field: 'quantity',
      headerName: 'Quantity',
      width: 100,
      type: 'number',
    },
    {
      field: 'avgCost',
      headerName: 'Avg Cost',
      width: 100,
      type: 'number',
      valueFormatter: (params) => `$${params.value.toFixed(2)}`,
    },
    {
      field: 'currentPrice',
      headerName: 'Current',
      width: 100,
      type: 'number',
      valueFormatter: (params) => `$${params.value.toFixed(2)}`,
    },
    {
      field: 'marketValue',
      headerName: 'Market Value',
      width: 120,
      type: 'number',
      valueGetter: (params) => params.row.quantity * params.row.currentPrice,
      valueFormatter: (params) => `$${params.value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
    },
    {
      field: 'unrealizedPnL',
      headerName: 'P&L',
      width: 120,
      type: 'number',
      renderCell: (params: GridRenderCellParams) => {
        const value = params.value || 0;
        const percent = params.row.pnlPercent || 0;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            {value >= 0 ? (
              <TrendingUpIcon fontSize="small" color="success" />
            ) : (
              <TrendingDownIcon fontSize="small" color="error" />
            )}
            <Box>
              <Typography
                variant="body2"
                color={value >= 0 ? 'success.main' : 'error.main'}
                fontWeight="bold"
              >
                ${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </Typography>
              <Typography
                variant="caption"
                color={value >= 0 ? 'success.main' : 'error.main'}
              >
                {percent >= 0 ? '+' : ''}{percent.toFixed(2)}%
              </Typography>
            </Box>
          </Box>
        );
      },
    },
    {
      field: 'side',
      headerName: 'Side',
      width: 80,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={params.value}
          size="small"
          color={params.value === 'LONG' ? 'success' : 'error'}
        />
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => (
        <Box>
          <IconButton
            size="small"
            onClick={() => handleModifyPosition(params.row)}
            title="Modify Position"
          >
            <EditIcon fontSize="small" />
          </IconButton>
          <IconButton
            size="small"
            onClick={() => handleClosePosition(params.row)}
            color="error"
            title="Close Position"
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      ),
    },
  ];

  // Calculate totals
  const totalMarketValue = positions.reduce((sum, pos) => sum + (pos.quantity * pos.currentPrice), 0);
  const totalUnrealizedPnL = positions.reduce((sum, pos) => sum + (pos.unrealizedPnL || 0), 0);
  const totalCost = positions.reduce((sum, pos) => sum + (pos.quantity * pos.avgCost), 0);
  const totalPnLPercent = totalCost > 0 ? (totalUnrealizedPnL / totalCost) * 100 : 0;

  return (
    <Paper sx={{ p: 2 }}>
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">
          Open Positions ({positions.length})
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Total Value
            </Typography>
            <Typography variant="h6">
              ${totalMarketValue.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Unrealized P&L
            </Typography>
            <Typography
              variant="h6"
              color={totalUnrealizedPnL >= 0 ? 'success.main' : 'error.main'}
            >
              ${Math.abs(totalUnrealizedPnL).toLocaleString('en-US', { minimumFractionDigits: 2 })}
              <Typography
                component="span"
                variant="body2"
                color={totalUnrealizedPnL >= 0 ? 'success.main' : 'error.main'}
                sx={{ ml: 0.5 }}
              >
                ({totalPnLPercent >= 0 ? '+' : ''}{totalPnLPercent.toFixed(2)}%)
              </Typography>
            </Typography>
          </Box>
        </Box>
      </Box>

      <DataGrid
        rows={positions}
        columns={columns}
        initialState={{
          pagination: {
            paginationModel: { pageSize: 10 },
          },
        }}
        pageSizeOptions={[10, 25, 50]}
        autoHeight
        disableRowSelectionOnClick
        sx={{
          '& .MuiDataGrid-row:hover': {
            backgroundColor: theme.palette.action.hover,
          },
        }}
      />

      {/* Close Position Dialog */}
      <Dialog open={closeDialogOpen} onClose={() => setCloseDialogOpen(false)}>
        <DialogTitle>Close Position</DialogTitle>
        <DialogContent>
          {selectedPosition && (
            <Box sx={{ pt: 1 }}>
              <Typography variant="body1" gutterBottom>
                Symbol: <strong>{selectedPosition.symbol}</strong>
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Current Position: {selectedPosition.quantity} shares @ ${selectedPosition.avgCost.toFixed(2)}
              </Typography>
              <TextField
                fullWidth
                label="Quantity to Close"
                value={closeQuantity}
                onChange={(e) => setCloseQuantity(e.target.value)}
                type="number"
                margin="normal"
                InputProps={{
                  inputProps: { min: 1, max: selectedPosition.quantity },
                }}
                helperText={`Max: ${selectedPosition.quantity} shares`}
              />
              {error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {error}
                </Alert>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCloseDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmClosePosition} color="error" variant="contained">
            Close Position
          </Button>
        </DialogActions>
      </Dialog>

      {/* Modify Position Dialog */}
      <Dialog open={modifyDialogOpen} onClose={() => setModifyDialogOpen(false)}>
        <DialogTitle>Modify Position</DialogTitle>
        <DialogContent>
          {selectedPosition && (
            <Box sx={{ pt: 1 }}>
              <Typography variant="body1" gutterBottom>
                Symbol: <strong>{selectedPosition.symbol}</strong>
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Current Position: {selectedPosition.quantity} shares @ ${selectedPosition.avgCost.toFixed(2)}
              </Typography>
              <TextField
                fullWidth
                label="New Quantity"
                value={modifyQuantity}
                onChange={(e) => setModifyQuantity(e.target.value)}
                type="number"
                margin="normal"
                InputProps={{
                  inputProps: { min: 1 },
                }}
                helperText="Enter the new total quantity for this position"
              />
              {error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {error}
                </Alert>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setModifyDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmModifyPosition} variant="contained">
            Modify Position
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
};
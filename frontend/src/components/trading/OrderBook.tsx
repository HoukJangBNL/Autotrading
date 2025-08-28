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
  Alert,
  Tab,
  Tabs,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import CancelIcon from '@mui/icons-material/Cancel';
import EditIcon from '@mui/icons-material/Edit';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useTheme } from '@mui/material/styles';
import { format } from 'date-fns';
import { OrderSide, OrderType, OrderStatus } from '../../types/index';

interface Order {
  id: string;
  symbol: string;
  side: OrderSide;
  orderType: OrderType;
  quantity: number;
  limitPrice?: number;
  stopPrice?: number;
  filledQuantity: number;
  status: OrderStatus;
  createdAt: string;
  updatedAt: string;
  timeInForce: string;
}

interface OrderBookProps {
  orders?: Order[];
  onCancel?: (orderId: string) => void;
  onModify?: (order: Order) => void;
  onRefresh?: () => void;
}

export const OrderBook: React.FC<OrderBookProps> = ({ 
  orders = [], 
  onCancel, 
  onModify, 
  onRefresh 
}) => {
  const theme = useTheme();
  const [activeTab, setActiveTab] = useState(0);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);

  // Mock data for demonstration
  const mockOrders: Order[] = [
    {
      id: '1',
      symbol: 'AAPL',
      side: OrderSide.BUY,
      orderType: OrderType.LIMIT,
      quantity: 100,
      limitPrice: 175.50,
      filledQuantity: 0,
      status: OrderStatus.PENDING,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      timeInForce: 'DAY',
    },
    {
      id: '2',
      symbol: 'MSFT',
      side: OrderSide.SELL,
      orderType: OrderType.STOP,
      quantity: 50,
      stopPrice: 420.00,
      filledQuantity: 0,
      status: OrderStatus.PENDING,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      timeInForce: 'GTC',
    },
    {
      id: '3',
      symbol: 'GOOGL',
      side: OrderSide.BUY,
      orderType: OrderType.LIMIT,
      quantity: 25,
      limitPrice: 140.00,
      filledQuantity: 10,
      status: OrderStatus.PARTIALLY_FILLED,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      timeInForce: 'DAY',
    },
  ];

  const displayOrders = orders.length > 0 ? orders : mockOrders;

  const getStatusColor = (status: OrderStatus) => {
    switch (status) {
      case OrderStatus.PENDING:
        return 'warning';
      case OrderStatus.PARTIALLY_FILLED:
        return 'info';
      case OrderStatus.FILLED:
        return 'success';
      case OrderStatus.CANCELLED:
        return 'default';
      case OrderStatus.REJECTED:
        return 'error';
      default:
        return 'default';
    }
  };

  const handleCancelOrder = (order: Order) => {
    setSelectedOrder(order);
    setCancelDialogOpen(true);
  };

  const confirmCancelOrder = () => {
    if (selectedOrder && onCancel) {
      onCancel(selectedOrder.id);
    }
    setCancelDialogOpen(false);
    setSelectedOrder(null);
  };

  const columns: GridColDef[] = [
    {
      field: 'createdAt',
      headerName: 'Time',
      width: 100,
      valueFormatter: (params) => format(new Date(params.value), 'HH:mm:ss'),
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
      field: 'orderType',
      headerName: 'Type',
      width: 80,
    },
    {
      field: 'quantity',
      headerName: 'Qty',
      width: 70,
      type: 'number',
      renderCell: (params: GridRenderCellParams) => {
        const filled = params.row.filledQuantity || 0;
        if (filled > 0) {
          return (
            <Typography variant="body2">
              {filled}/{params.value}
            </Typography>
          );
        }
        return params.value;
      },
    },
    {
      field: 'price',
      headerName: 'Price',
      width: 90,
      type: 'number',
      valueGetter: (params) => {
        if (params.row.orderType === OrderType.LIMIT || params.row.orderType === OrderType.STOP_LIMIT) {
          return params.row.limitPrice;
        }
        if (params.row.orderType === OrderType.STOP) {
          return params.row.stopPrice;
        }
        return 'Market';
      },
      valueFormatter: (params) => {
        if (typeof params.value === 'number') {
          return `$${params.value.toFixed(2)}`;
        }
        return params.value;
      },
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={params.value.replace('_', ' ')}
          size="small"
          color={getStatusColor(params.value)}
        />
      ),
    },
    {
      field: 'timeInForce',
      headerName: 'TIF',
      width: 60,
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => {
        const canModify = params.row.status === OrderStatus.PENDING;
        const canCancel = params.row.status === OrderStatus.PENDING || 
                         params.row.status === OrderStatus.PARTIALLY_FILLED;
        return (
          <Box>
            {canModify && (
              <IconButton
                size="small"
                onClick={() => onModify && onModify(params.row)}
                title="Modify Order"
              >
                <EditIcon fontSize="small" />
              </IconButton>
            )}
            {canCancel && (
              <IconButton
                size="small"
                onClick={() => handleCancelOrder(params.row)}
                color="error"
                title="Cancel Order"
              >
                <CancelIcon fontSize="small" />
              </IconButton>
            )}
          </Box>
        );
      },
    },
  ];

  // Filter orders by status
  const openOrders = displayOrders.filter(
    o => o.status === OrderStatus.PENDING || o.status === OrderStatus.PARTIALLY_FILLED
  );
  const filledOrders = displayOrders.filter(o => o.status === OrderStatus.FILLED);
  const cancelledOrders = displayOrders.filter(
    o => o.status === OrderStatus.CANCELLED || o.status === OrderStatus.REJECTED
  );

  const getFilteredOrders = () => {
    switch (activeTab) {
      case 0:
        return openOrders;
      case 1:
        return filledOrders;
      case 2:
        return cancelledOrders;
      default:
        return displayOrders;
    }
  };

  return (
    <Paper sx={{ p: 2 }}>
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">
          Order Book
        </Typography>
        <IconButton onClick={onRefresh} size="small" title="Refresh Orders">
          <RefreshIcon />
        </IconButton>
      </Box>

      <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)} sx={{ mb: 2 }}>
        <Tab label={`Open (${openOrders.length})`} />
        <Tab label={`Filled (${filledOrders.length})`} />
        <Tab label={`Cancelled (${cancelledOrders.length})`} />
      </Tabs>

      <DataGrid
        rows={getFilteredOrders()}
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

      {/* Cancel Order Dialog */}
      <Dialog open={cancelDialogOpen} onClose={() => setCancelDialogOpen(false)}>
        <DialogTitle>Cancel Order</DialogTitle>
        <DialogContent>
          {selectedOrder && (
            <Box sx={{ pt: 1 }}>
              <Alert severity="warning" sx={{ mb: 2 }}>
                Are you sure you want to cancel this order?
              </Alert>
              <Typography variant="body1" gutterBottom>
                Symbol: <strong>{selectedOrder.symbol}</strong>
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {selectedOrder.side} {selectedOrder.quantity} shares
              </Typography>
              {selectedOrder.limitPrice && (
                <Typography variant="body2" color="text.secondary">
                  Limit Price: ${selectedOrder.limitPrice.toFixed(2)}
                </Typography>
              )}
              {selectedOrder.stopPrice && (
                <Typography variant="body2" color="text.secondary">
                  Stop Price: ${selectedOrder.stopPrice.toFixed(2)}
                </Typography>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCancelDialogOpen(false)}>Keep Order</Button>
          <Button onClick={confirmCancelOrder} color="error" variant="contained">
            Cancel Order
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
};
import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Tabs,
  Tab,
  CircularProgress,
} from '@mui/material';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { fetchTradingStatus, fetchPositions, fetchOrders } from '../features/trading/tradingSlice';
import { OrderForm } from '../components/trading/OrderForm';
import { PositionsTable } from '../components/trading/PositionsTable';
import { OrderBook } from '../components/trading/OrderBook';
import { TradeHistory } from '../components/trading/TradeHistory';
import { QuickTrade } from '../components/trading/QuickTrade';
import { RiskMonitor } from '../components/trading/RiskMonitor';
import { useWebSocket } from '../hooks/useWebSocket';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`trading-tabpanel-${index}`}
      aria-labelledby={`trading-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
    </div>
  );
};

export const Trading: React.FC = () => {
  const dispatch = useAppDispatch();
  const { status, positions, orders, loading } = useAppSelector((state) => state.trading);
  const { connected } = useWebSocket();
  const [activeTab, setActiveTab] = useState(0);
  const [selectedSymbol, setSelectedSymbol] = useState('');

  useEffect(() => {
    // Initial data fetch
    dispatch(fetchTradingStatus());
    dispatch(fetchPositions());
    dispatch(fetchOrders({ limit: 50 }));

    // Set up polling for real-time data
    const interval = setInterval(() => {
      dispatch(fetchPositions());
      dispatch(fetchOrders({ limit: 50 }));
    }, 5000);

    return () => clearInterval(interval);
  }, [dispatch]);

  const handleOrderSubmit = (order: any) => {
    console.log('Order submitted:', order);
    // TODO: Dispatch order to backend
  };

  const handleQuickTrade = (order: any) => {
    console.log('Quick trade:', order);
    // TODO: Dispatch quick trade to backend
  };

  const handleClosePosition = (position: any) => {
    console.log('Close position:', position);
    // TODO: Dispatch close position to backend
  };

  const handleCancelOrder = (orderId: string) => {
    console.log('Cancel order:', orderId);
    // TODO: Dispatch cancel order to backend
  };

  const handleExportTrades = () => {
    console.log('Export trades');
    // TODO: Implement export functionality
  };

  if (loading && !positions.length && !orders.length) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4">
          Live Trading
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Connection:
          </Typography>
          <Typography
            variant="body2"
            color={connected ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {connected ? 'Connected' : 'Disconnected'}
          </Typography>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* Left Column - Order Entry and Quick Trade */}
        <Grid size={{ xs: 12, lg: 3 }}>
          <Grid container spacing={2}>
            <Grid size={12}>
              <QuickTrade
                symbol={selectedSymbol}
                onTrade={handleQuickTrade}
              />
            </Grid>
            <Grid size={12}>
              <OrderForm
                symbol={selectedSymbol}
                onSubmit={handleOrderSubmit}
              />
            </Grid>
          </Grid>
        </Grid>

        {/* Center Column - Positions and Orders */}
        <Grid size={{ xs: 12, lg: 6 }}>
          <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)} sx={{ mb: 2 }}>
            <Tab label="Positions" />
            <Tab label="Orders" />
            <Tab label="Trade History" />
          </Tabs>

          <TabPanel value={activeTab} index={0}>
            <PositionsTable
              onClose={handleClosePosition}
              onModify={(position, quantity) => {
                console.log('Modify position:', position, quantity);
              }}
            />
          </TabPanel>

          <TabPanel value={activeTab} index={1}>
            <OrderBook
              orders={[]}
              onCancel={handleCancelOrder}
              onModify={(order) => {
                console.log('Modify order:', order);
              }}
              onRefresh={() => dispatch(fetchOrders({ limit: 50 }))}
            />
          </TabPanel>

          <TabPanel value={activeTab} index={2}>
            <TradeHistory
              trades={[]}
              onExport={handleExportTrades}
            />
          </TabPanel>
        </Grid>

        {/* Right Column - Risk Monitor */}
        <Grid size={{ xs: 12, lg: 3 }}>
          <RiskMonitor />
        </Grid>
      </Grid>
    </Box>
  );
};
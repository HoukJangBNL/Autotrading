import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Grid,
  Container,
  Fade,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { 
  fetchPortfolioSummary, 
  fetchPortfolioPositions 
} from '../features/portfolio/portfolioSlice';
import { fetchActiveStrategies } from '../features/strategies/strategiesSlice';
import { fetchRecentTrades } from '../features/trading/tradingSlice';
import { DashboardCard } from '../components/dashboard/DashboardCard';
import { PositionsWidget } from '../components/dashboard/PositionsWidget';
import { StrategiesWidget } from '../components/dashboard/StrategiesWidget';
import { RecentTradesWidget } from '../components/dashboard/RecentTradesWidget';
import { MiniChart } from '../components/dashboard/MiniChart';
import { usePortfolioUpdates, useStrategyUpdates } from '../hooks/useWebSocket';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import AttachMoneyIcon from '@mui/icons-material/AttachMoney';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { summary, positions, loading: portfolioLoading } = useAppSelector((state) => state.portfolio);
  const { activeStrategies, loading: strategiesLoading } = useAppSelector((state) => state.strategies);
  const { recentTrades, loading: tradesLoading } = useAppSelector((state) => state.trading);
  const [portfolioHistory, setPortfolioHistory] = useState<Array<{ time: string; value: number }>>([]);

  // Enable real-time updates
  usePortfolioUpdates();
  useStrategyUpdates(activeStrategies.map(s => s.id));

  // Fetch initial data
  useEffect(() => {
    dispatch(fetchPortfolioSummary());
    dispatch(fetchPortfolioPositions());
    dispatch(fetchActiveStrategies());
    dispatch(fetchRecentTrades());
  }, [dispatch]);

  // Generate mock portfolio history for demo
  useEffect(() => {
    if (summary?.total_value) {
      const now = new Date();
      const data = [];
      const baseValue = summary.total_value * 0.98;
      
      for (let i = 30; i >= 0; i--) {
        const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
        const randomChange = (Math.random() - 0.5) * 0.02;
        const value = baseValue * (1 + randomChange + (30 - i) * 0.001);
        data.push({
          time: date.toISOString(),
          value: value,
        });
      }
      setPortfolioHistory(data);
    }
  }, [summary]);

  const formatCurrency = (value: number | undefined) => {
    if (value === undefined) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };

  const formatLargeCurrency = (value: number | undefined) => {
    if (value === undefined) return '$0';
    if (value >= 1000000) {
      return `$${(value / 1000000).toFixed(2)}M`;
    } else if (value >= 1000) {
      return `$${(value / 1000).toFixed(1)}K`;
    }
    return formatCurrency(value);
  };

  const handlePositionClick = useCallback((position: any) => {
    navigate(`/trading?symbol=${position.symbol}`);
  }, [navigate]);

  const handleStrategyClick = useCallback((strategy: any) => {
    navigate(`/strategies?id=${strategy.id}`);
  }, [navigate]);

  const handleTradeClick = useCallback((trade: any) => {
    navigate(`/trading?symbol=${trade.symbol}`);
  }, [navigate]);

  return (
    <Container maxWidth="xl">
      <Fade in timeout={800}>
        <Box>
          <Box mb={4}>
            <Typography variant="h4" fontWeight="bold">
              Dashboard
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Real-time portfolio overview and trading activity
            </Typography>
          </Box>

          <Grid container spacing={3}>
            {/* Portfolio Summary Cards - First Row */}
            <Grid size={12} sm={6} md={3}>
              <DashboardCard
                title="Total Portfolio Value"
                value={formatLargeCurrency(summary?.total_value)}
                change={summary?.total_change_pct}
                changeLabel="all time"
                loading={portfolioLoading}
                icon={<AccountBalanceIcon />}
                color="primary"
                tooltip="Total value of all holdings and cash"
              />
            </Grid>

            <Grid size={12} sm={6} md={3}>
              <DashboardCard
                title="Day Change"
                value={formatCurrency(summary?.day_change)}
                change={summary?.day_change_pct}
                changeLabel="today"
                loading={portfolioLoading}
                icon={<TrendingUpIcon />}
                color={summary?.day_change_pct && summary.day_change_pct >= 0 ? 'success' : 'error'}
                tooltip="Today's profit/loss"
              />
            </Grid>

            <Grid size={12} sm={6} md={3}>
              <DashboardCard
                title="Cash Balance"
                value={formatCurrency(summary?.cash_balance)}
                subtitle="Settled funds"
                loading={portfolioLoading}
                icon={<AttachMoneyIcon />}
                color="info"
                tooltip="Settled cash available"
              />
            </Grid>

            <Grid size={12} sm={6} md={3}>
              <DashboardCard
                title="Buying Power"
                value={formatCurrency(summary?.buying_power)}
                subtitle="Available for trading"
                loading={portfolioLoading}
                icon={<AccountBalanceWalletIcon />}
                color="secondary"
                tooltip="Total buying power including margin"
                onClick={() => navigate('/trading')}
              />
            </Grid>

            {/* Portfolio Summary Cards - Second Row */}
            <Grid size={12} sm={6} md={3}>
              <DashboardCard
                title="Open P&L"
                value={formatCurrency(summary?.open_pnl)}
                change={summary?.open_pnl_pct}
                loading={portfolioLoading}
                icon={<ShowChartIcon />}
                color={summary?.open_pnl && summary.open_pnl >= 0 ? 'success' : 'error'}
                tooltip="Unrealized profit/loss on open positions"
              />
            </Grid>

            {/* Portfolio Performance Chart */}
            <Grid size={12} md={8}>
              <Box sx={{ p: 3, height: 400, bgcolor: 'background.paper', borderRadius: 1 }}>
                <Typography variant="h6" gutterBottom>
                  Portfolio Performance
                </Typography>
                <Typography variant="body2" color="text.secondary" mb={2}>
                  30-day performance
                </Typography>
                {portfolioHistory.length > 0 ? (
                  <MiniChart
                    data={portfolioHistory}
                    height={320}
                    type="area"
                    showGrid
                    showAxis
                  />
                ) : (
                  <Box
                    display="flex"
                    justifyContent="center"
                    alignItems="center"
                    height="calc(100% - 60px)"
                    color="text.secondary"
                  >
                    {portfolioLoading ? 'Loading performance data...' : 'No data available'}
                  </Box>
                )}
              </Box>
            </Grid>

            {/* Active Strategies */}
            <Grid size={12} md={4}>
              <Box height={400}>
                <StrategiesWidget
                  strategies={activeStrategies}
                  loading={strategiesLoading}
                  onStrategyClick={handleStrategyClick}
                  onConfigureStrategy={(id) => navigate(`/strategies?id=${id}&action=configure`)}
                />
              </Box>
            </Grid>

            {/* Active Positions */}
            <Grid size={12} md={7}>
              <Box height={400}>
                <PositionsWidget
                  positions={positions}
                  loading={portfolioLoading}
                  onPositionClick={handlePositionClick}
                />
              </Box>
            </Grid>

            {/* Recent Trades */}
            <Grid size={12} md={5}>
              <Box height={400}>
                <RecentTradesWidget
                  trades={recentTrades}
                  loading={tradesLoading}
                  onTradeClick={handleTradeClick}
                />
              </Box>
            </Grid>
          </Grid>
        </Box>
      </Fade>
    </Container>
  );
};
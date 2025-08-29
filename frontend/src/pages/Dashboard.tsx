import React, { useEffect, useState } from 'react';
import { 
  Container, 
  Box, 
  Grid, 
  Typography, 
  Paper, 
  Card,
  CardContent,
  Stack,
  Chip,
  LinearProgress,
  IconButton,
  Tooltip,
  alpha,
  useTheme,
  Fade,
  Collapse,
  Skeleton,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  AccountBalance as AccountBalanceIcon,
  ShowChart as ChartIcon,
  Speed as SpeedIcon,
  Security as SecurityIcon,
  Refresh as RefreshIcon,
  MoreVert as MoreVertIcon,
} from '@mui/icons-material';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { fetchPortfolioSummary } from '../features/portfolio/portfolioSlice';
import { ModeSelector } from '../components/dashboard/ModeSelector';
import { TradingMode } from '../features/mode/modeSlice';
import { PositionsTable } from '../components/trading/PositionsTable';
import { ActiveStrategies } from '../components/strategies/ActiveStrategies';
import { TradeHistory } from '../components/trading/TradeHistory';
import { MiningMonitor } from '../components/mining/MiningMonitor';

interface DashboardCardProps {
  title: string;
  value: string | number;
  change?: number;
  subtitle?: string;
  icon?: React.ReactNode;
  color?: string;
  loading?: boolean;
  action?: React.ReactNode;
}

const DashboardCard: React.FC<DashboardCardProps> = ({ 
  title, 
  value, 
  change, 
  subtitle, 
  icon, 
  color = 'primary.main',
  loading = false,
  action,
}) => {
  const theme = useTheme();
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card 
        sx={{ 
          height: '100%',
          position: 'relative',
          overflow: 'hidden',
          '&::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: 4,
            background: `linear-gradient(90deg, ${color} 0%, ${alpha(color, 0.5)} 100%)`,
          },
        }}
      >
        <CardContent>
          {loading ? (
            <>
              <Skeleton variant="text" width="60%" />
              <Skeleton variant="text" width="40%" height={32} />
              <Skeleton variant="text" width="80%" />
            </>
          ) : (
            <>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2" color="text.secondary" fontWeight="medium">
                  {title}
                </Typography>
                {action || (icon && (
                  <Box sx={{ color: color }}>
                    {icon}
                  </Box>
                ))}
              </Box>
              
              <Typography variant="h4" fontWeight="bold" sx={{ color: color, mb: 1 }}>
                {value}
              </Typography>
              
              {(change !== undefined || subtitle) && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {change !== undefined && (
                    <Chip
                      size="small"
                      icon={change >= 0 ? <TrendingUpIcon /> : <TrendingDownIcon />}
                      label={`${change >= 0 ? '+' : ''}${change.toFixed(2)}%`}
                      sx={{
                        bgcolor: alpha(change >= 0 ? theme.palette.success.main : theme.palette.error.main, 0.1),
                        color: change >= 0 ? 'success.main' : 'error.main',
                        fontWeight: 'bold',
                        '& .MuiChip-icon': {
                          color: 'inherit',
                        },
                      }}
                    />
                  )}
                  {subtitle && (
                    <Typography variant="caption" color="text.secondary">
                      {subtitle}
                    </Typography>
                  )}
                </Box>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
};

const Dashboard: React.FC = () => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const { summary, loading } = useAppSelector((state) => state.portfolio);
  const { activeMode, modeStatus } = useAppSelector((state) => state.mode);
  const [portfolioHistory, setPortfolioHistory] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    dispatch(fetchPortfolioSummary());
    const interval = setInterval(() => {
      dispatch(fetchPortfolioSummary());
    }, 30000);
    return () => clearInterval(interval);
  }, [dispatch]);

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
          time: date.toISOString().split('T')[0],
          value: value,
        });
      }
      setPortfolioHistory(data);
    }
  }, [summary]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await dispatch(fetchPortfolioSummary());
    setTimeout(() => setRefreshing(false), 1000);
  };

  const formatCurrency = (value: number | undefined) => {
    if (value === undefined) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatPercentage = (value: number | undefined) => {
    if (value === undefined) return '0%';
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  // Mode-specific content
  const renderModeContent = () => {
    switch (activeMode) {
      case 'data-mining':
        return <MiningMonitor />;
        
      case 'auto-trading':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12} md={8}>
              <ActiveStrategies />
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 3, height: 400 }}>
                <Typography variant="h6" fontWeight="bold" gutterBottom>
                  Auto Trading Stats
                </Typography>
                <Stack spacing={3} sx={{ mt: 2 }}>
                  <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Today's Performance
                    </Typography>
                    <Typography variant="h4" color="success.main" fontWeight="bold">
                      +$1,245.00
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      12 trades executed
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Win Rate
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
                      <Typography variant="h5" fontWeight="bold">
                        67%
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        (8W / 4L)
                      </Typography>
                    </Box>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Risk Level
                    </Typography>
                    <Chip 
                      label="Conservative" 
                      color="success" 
                      size="small"
                      sx={{ fontWeight: 'bold' }}
                    />
                  </Box>
                </Stack>
              </Paper>
            </Grid>
            <Grid item xs={12}>
              <TradeHistory limit={10} />
            </Grid>
          </Grid>
        );
        
      case 'backtesting':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" fontWeight="bold" gutterBottom>
                  Backtesting Results
                </Typography>
                <Box sx={{ mt: 3, textAlign: 'center', py: 8 }}>
                  <Typography variant="h6" color="text.secondary">
                    No active backtest running
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Configure and start a backtest to see results here
                  </Typography>
                </Box>
              </Paper>
            </Grid>
          </Grid>
        );
        
      default:
        return null;
    }
  };

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* Mode Selector */}
      <ModeSelector />
      
      {/* Portfolio Summary Cards */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6" fontWeight="bold">
            Portfolio Overview
          </Typography>
          <Tooltip title="Refresh">
            <IconButton size="small" onClick={handleRefresh} disabled={refreshing}>
              <RefreshIcon sx={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
            </IconButton>
          </Tooltip>
        </Box>
        
        <Grid container spacing={3}>
          <Grid item xs={12} sm={6} md={3}>
            <DashboardCard
              title="Total Value"
              value={formatCurrency(summary?.total_value)}
              change={summary?.daily_pnl_percent}
              subtitle="Portfolio value"
              icon={<AccountBalanceIcon />}
              color={theme.palette.primary.main}
              loading={loading}
            />
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <DashboardCard
              title="Today's P&L"
              value={formatCurrency(summary?.daily_pnl)}
              change={summary?.daily_pnl_percent}
              icon={summary?.daily_pnl >= 0 ? <TrendingUpIcon /> : <TrendingDownIcon />}
              color={summary?.daily_pnl >= 0 ? theme.palette.success.main : theme.palette.error.main}
              loading={loading}
            />
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <DashboardCard
              title="Total P&L"
              value={formatCurrency(summary?.total_pnl)}
              change={summary?.total_pnl_percent}
              subtitle="All time"
              icon={<ChartIcon />}
              color={summary?.total_pnl >= 0 ? theme.palette.success.main : theme.palette.error.main}
              loading={loading}
            />
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <DashboardCard
              title="Win Rate"
              value={`${summary?.win_rate?.toFixed(1) || 0}%`}
              subtitle={`${summary?.winning_positions || 0}W / ${summary?.losing_positions || 0}L`}
              icon={<SpeedIcon />}
              color={theme.palette.info.main}
              loading={loading}
            />
          </Grid>
        </Grid>
      </Box>
      
      {/* Mode-specific Content with Animation */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeMode}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.3 }}
        >
          {renderModeContent()}
        </motion.div>
      </AnimatePresence>
      
      {/* Portfolio Chart - Always visible */}
      <Box sx={{ mt: 4 }}>
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6" fontWeight="bold">
              Portfolio Value History
            </Typography>
            <Stack direction="row" spacing={1}>
              <Chip label="1D" size="small" />
              <Chip label="1W" size="small" />
              <Chip label="1M" size="small" clickable color="primary" />
              <Chip label="3M" size="small" />
              <Chip label="1Y" size="small" />
              <Chip label="ALL" size="small" />
            </Stack>
          </Box>
          
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={portfolioHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke={alpha(theme.palette.divider, 0.5)} />
              <XAxis dataKey="time" stroke={theme.palette.text.secondary} />
              <YAxis stroke={theme.palette.text.secondary} />
              <ChartTooltip />
              <Line 
                type="monotone" 
                dataKey="value" 
                stroke={theme.palette.primary.main} 
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </Paper>
      </Box>
      
      {/* Positions Table - Always visible */}
      {activeMode !== 'backtesting' && (
        <Box sx={{ mt: 4 }}>
          <PositionsTable />
        </Box>
      )}
    </Container>
  );
};

export default Dashboard;
export { Dashboard };
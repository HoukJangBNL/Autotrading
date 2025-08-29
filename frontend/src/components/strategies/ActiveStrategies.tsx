import React from 'react';
import {
  Paper,
  Typography,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Switch,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Pause as PauseIcon,
  PlayArrow as PlayIcon,
} from '@mui/icons-material';
import { useAppSelector } from '../../store/hooks';

export const ActiveStrategies: React.FC = () => {
  const { strategies } = useAppSelector((state) => state.strategies);
  
  // Mock data for demo
  const mockStrategies = strategies?.length > 0 ? strategies : [
    {
      id: '1',
      name: 'Mean Reversion',
      is_active: true,
      performance: 12.5,
      trades_today: 5,
      win_rate: 68,
      status: 'running',
    },
    {
      id: '2',
      name: 'Momentum Trading',
      is_active: true,
      performance: -2.3,
      trades_today: 3,
      win_rate: 45,
      status: 'paused',
    },
    {
      id: '3',
      name: 'Volatility Arbitrage',
      is_active: false,
      performance: 8.7,
      trades_today: 0,
      win_rate: 72,
      status: 'stopped',
    },
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'success';
      case 'paused':
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <Paper sx={{ p: 3, height: '100%' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6" fontWeight="bold">
          Active Trading Strategies
        </Typography>
        <Chip 
          label={`${mockStrategies.filter(s => s.is_active).length} Active`}
          color="primary"
          size="small"
        />
      </Box>
      
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Strategy</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="center">Trades</TableCell>
              <TableCell align="right">Performance</TableCell>
              <TableCell align="center">Win Rate</TableCell>
              <TableCell align="center">Active</TableCell>
              <TableCell align="center">Action</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {mockStrategies.map((strategy) => (
              <TableRow key={strategy.id}>
                <TableCell>
                  <Typography variant="body2" fontWeight="medium">
                    {strategy.name}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={strategy.status}
                    size="small"
                    color={getStatusColor(strategy.status)}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="center">
                  {strategy.trades_today}
                </TableCell>
                <TableCell align="right">
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
                    {strategy.performance >= 0 ? (
                      <TrendingUpIcon fontSize="small" color="success" />
                    ) : (
                      <TrendingDownIcon fontSize="small" color="error" />
                    )}
                    <Typography
                      variant="body2"
                      color={strategy.performance >= 0 ? 'success.main' : 'error.main'}
                      fontWeight="medium"
                    >
                      {strategy.performance >= 0 ? '+' : ''}{strategy.performance}%
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell align="center">
                  <Typography variant="body2">
                    {strategy.win_rate}%
                  </Typography>
                </TableCell>
                <TableCell align="center">
                  <Switch
                    checked={strategy.is_active}
                    size="small"
                    color="primary"
                  />
                </TableCell>
                <TableCell align="center">
                  <Tooltip title={strategy.status === 'running' ? 'Pause' : 'Start'}>
                    <IconButton size="small">
                      {strategy.status === 'running' ? <PauseIcon /> : <PlayIcon />}
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Settings">
                    <IconButton size="small">
                      <SettingsIcon />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
};
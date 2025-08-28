import React from 'react';
import {
  Paper,
  Typography,
  Box,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  LinearProgress,
  IconButton,
  Tooltip,
  Switch,
  Divider,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import SettingsIcon from '@mui/icons-material/Settings';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { Strategy, StrategyStatus } from '../../features/strategies/strategiesSlice';

interface StrategiesWidgetProps {
  strategies: Strategy[];
  loading?: boolean;
  onStrategyClick?: (strategy: Strategy) => void;
  onToggleStrategy?: (strategyId: string, enabled: boolean) => void;
  onConfigureStrategy?: (strategyId: string) => void;
}

export const StrategiesWidget: React.FC<StrategiesWidgetProps> = ({
  strategies,
  loading = false,
  onStrategyClick,
  onToggleStrategy,
  onConfigureStrategy,
}) => {
  const getStatusColor = (status: StrategyStatus) => {
    switch (status) {
      case 'running':
        return 'success';
      case 'paused':
        return 'warning';
      case 'error':
        return 'error';
      case 'stopped':
      default:
        return 'default';
    }
  };

  const formatPercent = (value: number | undefined) => {
    if (value === undefined) return '0.00%';
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const getPerformanceColor = (value: number | undefined) => {
    if (value === undefined || value === 0) return 'text.secondary';
    return value > 0 ? 'success.main' : 'error.main';
  };

  return (
    <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">Active Strategies</Typography>
        <Box display="flex" gap={1}>
          <Chip 
            label={`${strategies.filter(s => s.status === 'running').length} running`} 
            size="small" 
            color="success"
            variant="outlined"
          />
          <Chip 
            label={`${strategies.length} total`} 
            size="small" 
            variant="outlined"
          />
        </Box>
      </Box>

      {loading ? (
        <LinearProgress />
      ) : strategies.length === 0 ? (
        <Box
          display="flex"
          alignItems="center"
          justifyContent="center"
          flexGrow={1}
          color="text.secondary"
        >
          <Typography>No strategies configured</Typography>
        </Box>
      ) : (
        <List sx={{ flexGrow: 1, overflow: 'auto' }}>
          {strategies.map((strategy, index) => (
            <React.Fragment key={strategy.id}>
              {index > 0 && <Divider />}
              <ListItem
                onClick={() => onStrategyClick?.(strategy)}
                sx={{
                  cursor: onStrategyClick ? 'pointer' : 'default',
                  py: 2,
                  '&:hover': {
                    backgroundColor: 'action.hover',
                  },
                }}
              >
                <Box sx={{ mr: 2 }}>
                  <Switch
                    edge="start"
                    checked={strategy.status === 'running'}
                    onChange={(e) => onToggleStrategy?.(strategy.id, e.target.checked)}
                    onClick={(e) => e.stopPropagation()}
                    color="success"
                  />
                </Box>
                
                <ListItemText
                  primary={
                    <Box display="flex" alignItems="center" gap={1}>
                      <Typography variant="subtitle1" fontWeight="medium">
                        {strategy.name}
                      </Typography>
                      <Chip 
                        label={strategy.status} 
                        size="small" 
                        color={getStatusColor(strategy.status)}
                      />
                    </Box>
                  }
                  secondary={
                    <Box mt={1}>
                      <Box display="flex" alignItems="center" gap={2}>
                        <Typography variant="body2" color="text.secondary">
                          {strategy.type}
                        </Typography>
                        {strategy.metrics && (
                          <>
                            <Box display="flex" alignItems="center" gap={0.5}>
                              {strategy.metrics.total_return !== undefined && strategy.metrics.total_return >= 0 ? (
                                <TrendingUpIcon fontSize="small" color="success" />
                              ) : (
                                <TrendingDownIcon fontSize="small" color="error" />
                              )}
                              <Typography 
                                variant="body2" 
                                color={getPerformanceColor(strategy.metrics.total_return)}
                                fontWeight="medium"
                              >
                                {formatPercent(strategy.metrics.total_return)}
                              </Typography>
                            </Box>
                            {strategy.metrics.sharpe_ratio !== undefined && (
                              <Typography variant="body2" color="text.secondary">
                                Sharpe: {strategy.metrics.sharpe_ratio.toFixed(2)}
                              </Typography>
                            )}
                            {strategy.metrics.win_rate !== undefined && (
                              <Typography variant="body2" color="text.secondary">
                                Win: {(strategy.metrics.win_rate * 100).toFixed(0)}%
                              </Typography>
                            )}
                          </>
                        )}
                      </Box>
                      {strategy.positions && strategy.positions.length > 0 && (
                        <Typography variant="caption" color="text.secondary">
                          {strategy.positions.length} active position{strategy.positions.length > 1 ? 's' : ''}
                        </Typography>
                      )}
                    </Box>
                  }
                />
                
                <ListItemSecondaryAction>
                  <Tooltip title="Configure">
                    <IconButton
                      edge="end"
                      onClick={(e) => {
                        e.stopPropagation();
                        onConfigureStrategy?.(strategy.id);
                      }}
                    >
                      <SettingsIcon />
                    </IconButton>
                  </Tooltip>
                </ListItemSecondaryAction>
              </ListItem>
            </React.Fragment>
          ))}
        </List>
      )}
    </Paper>
  );
};
import React from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Box,
  Chip,
  IconButton,
  Switch,
  Tooltip,
  Grid,
  LinearProgress,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Edit as EditIcon,
  ContentCopy as CopyIcon,
  Delete as DeleteIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Assessment as AssessmentIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { Strategy, StrategyStatus } from '../../types/strategy';
import { useNavigate } from 'react-router-dom';

interface StrategyCardProps {
  strategy: Strategy;
  onToggle: (id: string, active: boolean) => void;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  onClone: (id: string) => void;
  onBacktest: (id: string) => void;
}

export const StrategyCard: React.FC<StrategyCardProps> = ({
  strategy,
  onToggle,
  onEdit,
  onDelete,
  onClone,
  onBacktest,
}) => {
  const theme = useTheme();
  const navigate = useNavigate();

  const getStatusColor = (status: StrategyStatus) => {
    switch (status) {
      case StrategyStatus.ACTIVE:
        return 'success';
      case StrategyStatus.INACTIVE:
        return 'default';
      case StrategyStatus.TESTING:
        return 'warning';
      case StrategyStatus.ERROR:
        return 'error';
      default:
        return 'default';
    }
  };

  const getTypeLabel = (type: string) => {
    return type.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const formatPercent = (value: number) => {
    const formatted = value.toFixed(2);
    return value >= 0 ? `+${formatted}%` : `${formatted}%`;
  };

  const handleToggle = (event: React.ChangeEvent<HTMLInputElement>) => {
    event.stopPropagation();
    onToggle(strategy.id, event.target.checked);
  };

  const handleCardClick = () => {
    navigate(`/strategies/${strategy.id}`);
  };

  const performance = strategy.performance;

  return (
    <Card 
      sx={{ 
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        cursor: 'pointer',
        transition: 'all 0.3s',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: theme.shadows[8],
        },
      }}
      onClick={handleCardClick}
    >
      <CardContent sx={{ flexGrow: 1 }}>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Box>
            <Typography variant="h6" gutterBottom>
              {strategy.name}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Chip 
                label={getStatusColor(strategy.status) === 'success' ? 'Active' : strategy.status}
                color={getStatusColor(strategy.status) as any}
                size="small"
              />
              <Chip 
                label={getTypeLabel(strategy.type)}
                variant="outlined"
                size="small"
              />
            </Box>
          </Box>
          <Switch
            checked={strategy.status === StrategyStatus.ACTIVE}
            onChange={handleToggle}
            onClick={(e) => e.stopPropagation()}
            color="primary"
            size="small"
          />
        </Box>

        {/* Description */}
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2, minHeight: 40 }}>
          {strategy.description}
        </Typography>

        {/* Symbols */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Symbols
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
            {strategy.symbols.slice(0, 3).map((symbol) => (
              <Chip key={symbol} label={symbol} size="small" variant="outlined" />
            ))}
            {strategy.symbols.length > 3 && (
              <Chip label={`+${strategy.symbols.length - 3}`} size="small" variant="outlined" />
            )}
          </Box>
        </Box>

        {/* Performance Metrics */}
        {performance && (
          <Box>
            <Typography variant="caption" color="text.secondary">
              Performance
            </Typography>
            <Grid container spacing={2} sx={{ mt: 0.5 }}>
              <Grid item xs={6}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Total Return
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {performance.totalReturn >= 0 ? (
                      <TrendingUpIcon sx={{ fontSize: 16, color: theme.palette.success.main, mr: 0.5 }} />
                    ) : (
                      <TrendingDownIcon sx={{ fontSize: 16, color: theme.palette.error.main, mr: 0.5 }} />
                    )}
                    <Typography 
                      variant="body2" 
                      fontWeight="bold"
                      color={performance.totalReturn >= 0 ? 'success.main' : 'error.main'}
                    >
                      {formatPercent(performance.totalReturn)}
                    </Typography>
                  </Box>
                </Box>
              </Grid>
              <Grid item xs={6}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Sharpe Ratio
                  </Typography>
                  <Typography variant="body2" fontWeight="bold">
                    {performance.sharpeRatio.toFixed(2)}
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Win Rate
                  </Typography>
                  <Typography variant="body2" fontWeight="bold">
                    {(performance.winRate * 100).toFixed(1)}%
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Max Drawdown
                  </Typography>
                  <Typography variant="body2" fontWeight="bold" color="error.main">
                    {formatPercent(performance.maxDrawdown)}
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Box>
        )}

        {/* Progress Bar for Testing Status */}
        {strategy.status === StrategyStatus.TESTING && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Testing Progress
            </Typography>
            <LinearProgress variant="determinate" value={65} sx={{ mt: 0.5 }} />
          </Box>
        )}
      </CardContent>

      <CardActions sx={{ justifyContent: 'space-between', px: 2, pb: 2 }}>
        <Box>
          {strategy.lastExecuted && (
            <Typography variant="caption" color="text.secondary">
              Last run: {new Date(strategy.lastExecuted).toLocaleDateString()}
            </Typography>
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="Backtest">
            <IconButton 
              size="small" 
              onClick={(e) => {
                e.stopPropagation();
                onBacktest(strategy.id);
              }}
            >
              <AssessmentIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit">
            <IconButton 
              size="small" 
              onClick={(e) => {
                e.stopPropagation();
                onEdit(strategy.id);
              }}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Clone">
            <IconButton 
              size="small" 
              onClick={(e) => {
                e.stopPropagation();
                onClone(strategy.id);
              }}
            >
              <CopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton 
              size="small" 
              color="error"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(strategy.id);
              }}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </CardActions>
    </Card>
  );
};
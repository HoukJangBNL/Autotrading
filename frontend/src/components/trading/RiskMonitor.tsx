import React from 'react';
import {
  Box,
  Paper,
  Typography,
  LinearProgress,
  Grid,
  Alert,
  Chip,
  List,
  ListItem,
  ListItemText,
  Divider,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import WarningIcon from '@mui/icons-material/Warning';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import InfoIcon from '@mui/icons-material/Info';
import { format } from 'date-fns';
import { useAppSelector } from '../../store/hooks';

interface RiskMetrics {
  dailyPnL: number;
  dailyPnLPercent: number;
  maxDailyLoss: number;
  currentExposure: number;
  maxExposure: number;
  marginUsed: number;
  marginAvailable: number;
  buyingPower: number;
  openPositions: number;
  maxPositions: number;
  largestPosition: {
    symbol: string;
    value: number;
    percent: number;
  };
  sectorConcentration: Array<{
    sector: string;
    percent: number;
  }>;
  alerts: Array<{
    level: 'error' | 'warning' | 'info';
    message: string;
    timestamp: string;
  }>;
}

interface RiskMonitorProps {
  metrics?: RiskMetrics;
}

export const RiskMonitor: React.FC<RiskMonitorProps> = ({ metrics }) => {
  const theme = useTheme();
  const { summary, positions } = useAppSelector((state) => state.portfolio);

  // Mock data for demonstration
  const mockMetrics: RiskMetrics = {
    dailyPnL: -450.25,
    dailyPnLPercent: -0.45,
    maxDailyLoss: 10000,
    currentExposure: 85250,
    maxExposure: 100000,
    marginUsed: 42625,
    marginAvailable: 57375,
    buyingPower: 114750,
    openPositions: positions.length || 5,
    maxPositions: 10,
    largestPosition: {
      symbol: 'AAPL',
      value: 35250,
      percent: 35.25,
    },
    sectorConcentration: [
      { sector: 'Technology', percent: 65 },
      { sector: 'Healthcare', percent: 20 },
      { sector: 'Finance', percent: 15 },
    ],
    alerts: [
      { 
        level: 'warning', 
        message: 'Portfolio concentrated in Technology sector (65%)', 
        timestamp: new Date().toISOString() 
      },
      { 
        level: 'info', 
        message: 'Margin utilization at 42.6%', 
        timestamp: new Date().toISOString() 
      },
      { 
        level: 'warning', 
        message: 'Approaching max daily loss limit', 
        timestamp: new Date().toISOString() 
      },
    ],
  };

  const displayMetrics = metrics || mockMetrics;

  const getRiskLevel = (value: number, max: number): 'low' | 'medium' | 'high' => {
    const ratio = value / max;
    if (ratio < 0.5) return 'low';
    if (ratio < 0.8) return 'medium';
    return 'high';
  };

  const getRiskColor = (level: 'low' | 'medium' | 'high') => {
    switch (level) {
      case 'low':
        return theme.palette.success.main;
      case 'medium':
        return theme.palette.warning.main;
      case 'high':
        return theme.palette.error.main;
    }
  };

  const exposureRiskLevel = getRiskLevel(displayMetrics.currentExposure, displayMetrics.maxExposure);
  const marginRiskLevel = getRiskLevel(displayMetrics.marginUsed, displayMetrics.marginUsed + displayMetrics.marginAvailable);
  const positionRiskLevel = getRiskLevel(displayMetrics.openPositions, displayMetrics.maxPositions);
  const dailyLossRiskLevel = getRiskLevel(Math.abs(displayMetrics.dailyPnL), displayMetrics.maxDailyLoss);

  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        Risk Monitor
      </Typography>

      {/* Daily P&L */}
      <Box sx={{ mb: 3, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Daily P&L
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 1 }}>
          <Typography
            variant="h4"
            color={displayMetrics.dailyPnL >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            ${Math.abs(displayMetrics.dailyPnL).toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </Typography>
          <Typography
            variant="body1"
            color={displayMetrics.dailyPnL >= 0 ? 'success.main' : 'error.main'}
          >
            ({displayMetrics.dailyPnLPercent >= 0 ? '+' : ''}{displayMetrics.dailyPnLPercent.toFixed(2)}%)
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Max Daily Loss: ${displayMetrics.maxDailyLoss.toLocaleString()}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={(Math.abs(displayMetrics.dailyPnL) / displayMetrics.maxDailyLoss) * 100}
            sx={{
              flexGrow: 1,
              height: 8,
              borderRadius: 1,
              backgroundColor: theme.palette.grey[300],
              '& .MuiLinearProgress-bar': {
                backgroundColor: getRiskColor(dailyLossRiskLevel),
              },
            }}
          />
        </Box>
      </Box>

      {/* Risk Metrics Grid */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {/* Exposure */}
        <Grid size={12} sm={6}>
          <Box sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Portfolio Exposure
            </Typography>
            <Typography variant="h6">
              ${displayMetrics.currentExposure.toLocaleString()}
            </Typography>
            <Box sx={{ mt: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography variant="caption">
                  {((displayMetrics.currentExposure / displayMetrics.maxExposure) * 100).toFixed(1)}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Max: ${displayMetrics.maxExposure.toLocaleString()}
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={(displayMetrics.currentExposure / displayMetrics.maxExposure) * 100}
                sx={{
                  height: 6,
                  borderRadius: 1,
                  backgroundColor: theme.palette.grey[300],
                  '& .MuiLinearProgress-bar': {
                    backgroundColor: getRiskColor(exposureRiskLevel),
                  },
                }}
              />
            </Box>
          </Box>
        </Grid>

        {/* Margin */}
        <Grid size={12} sm={6}>
          <Box sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Margin Utilization
            </Typography>
            <Typography variant="h6">
              ${displayMetrics.marginUsed.toLocaleString()}
            </Typography>
            <Box sx={{ mt: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography variant="caption">
                  {((displayMetrics.marginUsed / (displayMetrics.marginUsed + displayMetrics.marginAvailable)) * 100).toFixed(1)}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Available: ${displayMetrics.marginAvailable.toLocaleString()}
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={(displayMetrics.marginUsed / (displayMetrics.marginUsed + displayMetrics.marginAvailable)) * 100}
                sx={{
                  height: 6,
                  borderRadius: 1,
                  backgroundColor: theme.palette.grey[300],
                  '& .MuiLinearProgress-bar': {
                    backgroundColor: getRiskColor(marginRiskLevel),
                  },
                }}
              />
            </Box>
          </Box>
        </Grid>

        {/* Positions */}
        <Grid size={12} sm={6}>
          <Box sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Open Positions
            </Typography>
            <Typography variant="h6">
              {displayMetrics.openPositions} / {displayMetrics.maxPositions}
            </Typography>
            <Box sx={{ mt: 1 }}>
              <LinearProgress
                variant="determinate"
                value={(displayMetrics.openPositions / displayMetrics.maxPositions) * 100}
                sx={{
                  height: 6,
                  borderRadius: 1,
                  backgroundColor: theme.palette.grey[300],
                  '& .MuiLinearProgress-bar': {
                    backgroundColor: getRiskColor(positionRiskLevel),
                  },
                }}
              />
            </Box>
          </Box>
        </Grid>

        {/* Buying Power */}
        <Grid size={12} sm={6}>
          <Box sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Buying Power
            </Typography>
            <Typography variant="h6" color="primary.main">
              ${displayMetrics.buyingPower.toLocaleString()}
            </Typography>
          </Box>
        </Grid>
      </Grid>

      {/* Concentration Risk */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Concentration Risk
        </Typography>
        <Box sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" gutterBottom>
              Largest Position: <strong>{displayMetrics.largestPosition.symbol}</strong>
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="caption" color="text.secondary">
                ${displayMetrics.largestPosition.value.toLocaleString()} ({displayMetrics.largestPosition.percent}%)
              </Typography>
              <LinearProgress
                variant="determinate"
                value={displayMetrics.largestPosition.percent}
                sx={{
                  flexGrow: 1,
                  height: 6,
                  borderRadius: 1,
                  backgroundColor: theme.palette.grey[300],
                }}
              />
            </Box>
          </Box>
          <Divider sx={{ my: 1 }} />
          <Typography variant="body2" gutterBottom>
            Sector Allocation
          </Typography>
          {displayMetrics.sectorConcentration.map((sector, index) => (
            <Box key={index} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Typography variant="caption" sx={{ width: 80 }}>
                {sector.sector}
              </Typography>
              <LinearProgress
                variant="determinate"
                value={sector.percent}
                sx={{
                  flexGrow: 1,
                  height: 6,
                  borderRadius: 1,
                  backgroundColor: theme.palette.grey[300],
                }}
              />
              <Typography variant="caption" sx={{ width: 40, textAlign: 'right' }}>
                {sector.percent}%
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>

      {/* Risk Alerts */}
      <Box>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Risk Alerts
        </Typography>
        <List sx={{ p: 0 }}>
          {displayMetrics.alerts.map((alert, index) => (
            <ListItem
              key={index}
              sx={{
                px: 2,
                py: 1,
                mb: 1,
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
                bgcolor: 
                  alert.level === 'error' 
                    ? 'error.lighter' 
                    : alert.level === 'warning' 
                    ? 'warning.lighter' 
                    : 'info.lighter',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                {alert.level === 'error' && <ErrorIcon color="error" fontSize="small" />}
                {alert.level === 'warning' && <WarningIcon color="warning" fontSize="small" />}
                {alert.level === 'info' && <InfoIcon color="info" fontSize="small" />}
                <ListItemText
                  primary={alert.message}
                  secondary={format(new Date(alert.timestamp), 'HH:mm:ss')}
                  primaryTypographyProps={{ variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
              </Box>
            </ListItem>
          ))}
        </List>
      </Box>
    </Paper>
  );
};
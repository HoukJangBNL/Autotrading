import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  TextField,
  Button,
  LinearProgress,
  Alert,
  InputAdornment,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
} from '@mui/icons-material';
import { BacktestConfig } from '../../types/strategy';

interface BacktestInterfaceProps {
  strategyId: string;
  onRunBacktest: (config: BacktestConfig) => void;
  onStopBacktest: () => void;
  isRunning: boolean;
  progress?: number;
}

export const BacktestInterface: React.FC<BacktestInterfaceProps> = ({
  strategyId,
  onRunBacktest,
  onStopBacktest,
  isRunning,
  progress = 0,
}) => {
  const [config, setConfig] = useState<BacktestConfig>({
    strategyId,
    startDate: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString(), // 1 year ago
    endDate: new Date().toISOString(),
    initialCapital: 100000,
    commission: 0.001,
    slippage: 0.001,
  });

  const handleRun = () => {
    onRunBacktest(config);
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Backtest Configuration
      </Typography>
      
      <Grid container spacing={3}>
        <Grid size={12} md={6}>
          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <DatePicker
              label="Start Date"
              value={new Date(config.startDate)}
              onChange={(newValue) => {
                if (newValue) {
                  setConfig({ ...config, startDate: newValue.toISOString() });
                }
              }}
              slotProps={{ textField: { fullWidth: true } }}
            />
          </LocalizationProvider>
        </Grid>
        
        <Grid size={12} md={6}>
          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <DatePicker
              label="End Date"
              value={new Date(config.endDate)}
              onChange={(newValue) => {
                if (newValue) {
                  setConfig({ ...config, endDate: newValue.toISOString() });
                }
              }}
              slotProps={{ textField: { fullWidth: true } }}
            />
          </LocalizationProvider>
        </Grid>
        
        <Grid size={12} md={4}>
          <TextField
            fullWidth
            label="Initial Capital"
            type="number"
            value={config.initialCapital}
            onChange={(e) => setConfig({ ...config, initialCapital: parseFloat(e.target.value) })}
            InputProps={{
              startAdornment: <InputAdornment position="start">$</InputAdornment>,
            }}
          />
        </Grid>
        
        <Grid size={12} md={4}>
          <TextField
            fullWidth
            label="Commission"
            type="number"
            value={config.commission}
            onChange={(e) => setConfig({ ...config, commission: parseFloat(e.target.value) })}
            InputProps={{
              endAdornment: <InputAdornment position="end">%</InputAdornment>,
            }}
          />
        </Grid>
        
        <Grid size={12} md={4}>
          <TextField
            fullWidth
            label="Slippage"
            type="number"
            value={config.slippage}
            onChange={(e) => setConfig({ ...config, slippage: parseFloat(e.target.value) })}
            InputProps={{
              endAdornment: <InputAdornment position="end">%</InputAdornment>,
            }}
          />
        </Grid>
        
        <Grid size={12}>
          {isRunning ? (
            <>
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">
                    Running backtest...
                  </Typography>
                  <Typography variant="body2">
                    {Math.round(progress)}%
                  </Typography>
                </Box>
                <LinearProgress variant="determinate" value={progress} />
              </Box>
              <Button
                fullWidth
                variant="contained"
                color="error"
                startIcon={<StopIcon />}
                onClick={onStopBacktest}
              >
                Stop Backtest
              </Button>
            </>
          ) : (
            <Button
              fullWidth
              variant="contained"
              color="primary"
              startIcon={<PlayIcon />}
              onClick={handleRun}
              size="large"
            >
              Run Backtest
            </Button>
          )}
        </Grid>
        
        <Grid size={12}>
          <Alert severity="info">
            Backtest will simulate trading using historical data with your strategy parameters.
            Results will show performance metrics, equity curve, and trade history.
          </Alert>
        </Grid>
      </Grid>
    </Paper>
  );
};
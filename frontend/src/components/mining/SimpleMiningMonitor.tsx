import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Grid,
  Chip,
  Stack,
  Paper,
  Divider,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Speed as SpeedIcon,
  Storage as StorageIcon,
  Timeline as TimelineIcon,
  TrendingUp as TrendingUpIcon,
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';

interface MiningModeStatus {
  is_running: boolean;
  current_mode: 'gap_filling' | 'expansion' | 'auto';
  configuration: {
    mode: 'gap_filling' | 'expansion' | 'auto';
    gap_filling_first: boolean;
    switch_on_completion: boolean;
    lookback_days: number;
  };
  session: {
    session_id: string;
    mode: string;
    start_time: string;
    end_time?: string;
    duration_seconds: number;
    total_symbols: number;
    processed_symbols: number;
    successful_symbols: number;
    failed_symbols: number;
    progress_percentage: number;
    gaps_filled: number;
    data_points_collected: number;
    gap_filling_completed: boolean;
    expansion_completed: boolean;
    current_symbol?: string;
    current_operation?: string;
  };
}

export const SimpleMiningMonitor: React.FC = () => {
  const [status, setStatus] = useState<MiningModeStatus | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch current status
  const fetchStatus = async () => {
    try {
      const response = await fetch('/api/mining/v2/mode-status');
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      }
    } catch (err) {
      console.error('Failed to fetch mining status:', err);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000); // Poll every 2 seconds for smoother updates
    return () => clearInterval(interval);
  }, []);

  const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  const calculateSpeed = (): number => {
    if (!status?.session || status.session.duration_seconds === 0) return 0;
    return Math.round((status.session.processed_symbols / status.session.duration_seconds) * 60);
  };

  if (!status?.session) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Mining Monitor
          </Typography>
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <Typography variant="body2" color="text.secondary">
              No active mining session
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  const { session } = status;
  const speed = calculateSpeed();

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Mining Progress
        </Typography>

        {/* Main Progress Bar */}
        <Box sx={{ mb: 3 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography variant="body2">
              {session.processed_symbols} / {session.total_symbols} symbols
            </Typography>
            <Typography variant="body2" fontWeight="bold">
              {session.progress_percentage.toFixed(1)}%
            </Typography>
          </Stack>
          <LinearProgress 
            variant="determinate" 
            value={session.progress_percentage}
            sx={{ 
              height: 10, 
              borderRadius: 1,
              '& .MuiLinearProgress-bar': {
                background: 'linear-gradient(90deg, #4caf50 0%, #8bc34a 100%)',
              }
            }}
          />
        </Box>

        {/* Stats Grid */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} sm={3}>
            <Paper variant="outlined" sx={{ p: 1.5 }}>
              <Stack alignItems="center">
                <CheckIcon color="success" fontSize="small" />
                <Typography variant="h6" color="success.main">
                  {session.successful_symbols}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Successful
                </Typography>
              </Stack>
            </Paper>
          </Grid>
          
          <Grid item xs={6} sm={3}>
            <Paper variant="outlined" sx={{ p: 1.5 }}>
              <Stack alignItems="center">
                <ErrorIcon color="error" fontSize="small" />
                <Typography variant="h6" color="error.main">
                  {session.failed_symbols}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Failed
                </Typography>
              </Stack>
            </Paper>
          </Grid>
          
          <Grid item xs={6} sm={3}>
            <Paper variant="outlined" sx={{ p: 1.5 }}>
              <Stack alignItems="center">
                <SpeedIcon color="primary" fontSize="small" />
                <Typography variant="h6" color="primary.main">
                  {speed}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Symbols/min
                </Typography>
              </Stack>
            </Paper>
          </Grid>
          
          <Grid item xs={6} sm={3}>
            <Paper variant="outlined" sx={{ p: 1.5 }}>
              <Stack alignItems="center">
                <TimelineIcon color="info" fontSize="small" />
                <Typography variant="h6" color="info.main">
                  {formatDuration(session.duration_seconds)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Duration
                </Typography>
              </Stack>
            </Paper>
          </Grid>
        </Grid>

        {/* Current Symbol */}
        {session.current_symbol && (
          <AnimatePresence>
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              transition={{ duration: 0.3 }}
            >
              <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: 'background.default' }}>
                <Stack direction="row" alignItems="center" spacing={2}>
                  <CircularProgress size={20} />
                  <Box flex={1}>
                    <Typography variant="body2" color="text.secondary">
                      Processing
                    </Typography>
                    <Typography variant="body1" fontWeight="bold">
                      {session.current_symbol}
                    </Typography>
                  </Box>
                  {session.current_operation && (
                    <Chip 
                      label={session.current_operation} 
                      size="small" 
                      color="primary"
                      variant="outlined"
                    />
                  )}
                </Stack>
              </Paper>
            </motion.div>
          </AnimatePresence>
        )}

        <Divider sx={{ my: 2 }} />

        {/* Data Collection Stats */}
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Stack direction="row" alignItems="center" spacing={1}>
            <StorageIcon fontSize="small" color="action" />
            <Typography variant="body2" color="text.secondary">
              Data Points Collected
            </Typography>
          </Stack>
          <Typography variant="h6" fontWeight="bold">
            {session.data_points_collected.toLocaleString()}
          </Typography>
        </Stack>

        {status.current_mode === 'gap_filling' && session.gaps_filled > 0 && (
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 1 }}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <TrendingUpIcon fontSize="small" color="action" />
              <Typography variant="body2" color="text.secondary">
                Gaps Filled
              </Typography>
            </Stack>
            <Typography variant="h6" fontWeight="bold" color="info.main">
              {session.gaps_filled}
            </Typography>
          </Stack>
        )}

        {/* Estimated Completion */}
        {status.is_running && session.processed_symbols > 0 && (
          <Alert severity="info" sx={{ mt: 2 }}>
            <Typography variant="body2">
              Estimated completion: {
                speed > 0 
                  ? `~${Math.ceil((session.total_symbols - session.processed_symbols) / speed)} minutes`
                  : 'Calculating...'
              }
            </Typography>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};
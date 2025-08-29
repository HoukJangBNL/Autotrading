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
  Alert,
  Button,
  IconButton,
  Tooltip,
  Paper,
  Divider,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Speed as SpeedIcon,
  Storage as StorageIcon,
  Timeline as TimelineIcon,
  Assessment as AssessmentIcon,
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';

interface MiningStatus {
  is_running: boolean;
  current_phase: number;
  progress: {
    phase: number;
    symbols_total: number;
    symbols_completed: number;
    symbols_failed: number;
    candles_collected: number;
    completion_percentage: number;
    elapsed_minutes: number;
    estimated_completion: string | null;
    current_symbol: string | null;
  };
  quality: {
    average_quality: number;
    low_quality_symbols: Array<{ symbol: string; score: number }>;
    validation_failures: number;
  };
  phase_info: {
    [key: string]: {
      name: string;
      unique_symbols: number;
      cumulative_symbols: number;
    };
  };
}

interface PhaseInfo {
  phases: {
    [key: string]: {
      name: string;
      unique_symbols: number;
      cumulative_symbols: number;
      symbols: string[];
      total_symbols: number;
    };
  };
}

export const MiningMonitor: React.FC = () => {
  const [status, setStatus] = useState<MiningStatus | null>(null);
  const [phaseInfo, setPhaseInfo] = useState<PhaseInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Fetch mining status
  const fetchStatus = async () => {
    try {
      const response = await fetch('https://localhost:8182/api/mining/v2/status/detailed', {
        credentials: 'include',
      });
      const data = await response.json();
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch mining status:', err);
    }
  };

  // Fetch phase information
  const fetchPhaseInfo = async () => {
    try {
      const response = await fetch('https://localhost:8182/api/mining/v2/phases/info', {
        credentials: 'include',
      });
      const data = await response.json();
      setPhaseInfo(data);
    } catch (err) {
      console.error('Failed to fetch phase info:', err);
    }
  };

  // Start mining
  const handleStartMining = async (startPhase: number = 1, endPhase: number = 3) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `https://localhost:8182/api/mining/v2/start-multi-phase?start_phase=${startPhase}&end_phase=${endPhase}`,
        {
          method: 'POST',
          credentials: 'include',
        }
      );
      const data = await response.json();
      if (data.status === 'started') {
        await fetchStatus();
      } else {
        setError(data.message || 'Failed to start mining');
      }
    } catch (err) {
      setError('Failed to start mining');
    } finally {
      setLoading(false);
    }
  };

  // Stop mining
  const handleStopMining = async () => {
    setLoading(true);
    try {
      await fetch('https://localhost:8182/api/mining/v2/stop', {
        method: 'POST',
        credentials: 'include',
      });
      await fetchStatus();
    } catch (err) {
      setError('Failed to stop mining');
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh
  useEffect(() => {
    fetchStatus();
    fetchPhaseInfo();

    if (autoRefresh) {
      const interval = setInterval(() => {
        if (status?.is_running) {
          fetchStatus();
        }
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, status?.is_running]);

  const getPhaseColor = (phase: number) => {
    const colors = ['primary', 'secondary', 'success'];
    return colors[phase - 1] || 'default';
  };

  const getQualityColor = (score: number) => {
    if (score >= 90) return 'success';
    if (score >= 70) return 'warning';
    return 'error';
  };

  return (
    <Box sx={{ p: 2 }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h5" fontWeight="bold">
          Historical Data Mining Monitor
        </Typography>
        <Stack direction="row" spacing={2}>
          <Tooltip title={autoRefresh ? 'Disable auto-refresh' : 'Enable auto-refresh'}>
            <IconButton onClick={() => setAutoRefresh(!autoRefresh)} color={autoRefresh ? 'primary' : 'default'}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          {status?.is_running ? (
            <Button
              variant="contained"
              color="error"
              startIcon={<StopIcon />}
              onClick={handleStopMining}
              disabled={loading}
            >
              Stop Mining
            </Button>
          ) : (
            <Button
              variant="contained"
              color="primary"
              startIcon={<PlayIcon />}
              onClick={() => handleStartMining()}
              disabled={loading}
            >
              Start All Phases
            </Button>
          )}
        </Stack>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Phase Status */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Phase Status
              </Typography>
              <Stack spacing={2}>
                {phaseInfo?.phases &&
                  Object.entries(phaseInfo.phases).map(([phase, info]) => (
                    <Paper key={phase} sx={{ p: 2, bgcolor: 'background.default' }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <Box>
                          <Typography variant="subtitle1" fontWeight="bold">
                            Phase {phase}: {info.name}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {info.total_symbols} symbols
                          </Typography>
                        </Box>
                        {status?.current_phase === parseInt(phase) && status.is_running && (
                          <Chip label="Active" color="primary" size="small" />
                        )}
                      </Box>
                    </Paper>
                  ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        {/* Progress */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Mining Progress
              </Typography>
              {status?.is_running ? (
                <Box>
                  <Box sx={{ mb: 3 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Phase {status.current_phase} Progress
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={status.progress.completion_percentage}
                      sx={{ height: 10, borderRadius: 1, mb: 1 }}
                    />
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="caption">
                        {status.progress.symbols_completed} / {status.progress.symbols_total} symbols
                      </Typography>
                      <Typography variant="caption">{status.progress.completion_percentage.toFixed(1)}%</Typography>
                    </Box>
                  </Box>

                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Paper sx={{ p: 2, bgcolor: 'success.main', color: 'white' }}>
                        <CheckIcon sx={{ mb: 1 }} />
                        <Typography variant="h4">{status.progress.symbols_completed}</Typography>
                        <Typography variant="body2">Completed</Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6}>
                      <Paper sx={{ p: 2, bgcolor: 'error.main', color: 'white' }}>
                        <ErrorIcon sx={{ mb: 1 }} />
                        <Typography variant="h4">{status.progress.symbols_failed}</Typography>
                        <Typography variant="body2">Failed</Typography>
                      </Paper>
                    </Grid>
                  </Grid>

                  {status.progress.current_symbol && (
                    <Alert severity="info" sx={{ mt: 2 }}>
                      Currently processing: {status.progress.current_symbol}
                    </Alert>
                  )}
                </Box>
              ) : (
                <Alert severity="info">Mining is not running</Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Statistics */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Collection Statistics
              </Typography>
              <List>
                <ListItem>
                  <ListItemText
                    primary="Total Candles Collected"
                    secondary={status?.progress.candles_collected?.toLocaleString() || 0}
                  />
                  <StorageIcon color="primary" />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Elapsed Time"
                    secondary={`${status?.progress.elapsed_minutes?.toFixed(1) || 0} minutes`}
                  />
                  <TimelineIcon color="primary" />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Estimated Completion"
                    secondary={
                      status?.progress.estimated_completion
                        ? new Date(status.progress.estimated_completion).toLocaleTimeString()
                        : 'N/A'
                    }
                  />
                  <SpeedIcon color="primary" />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>

        {/* Quality Metrics */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Data Quality
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Average Quality Score
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <CircularProgress
                    variant="determinate"
                    value={status?.quality.average_quality || 0}
                    color={getQualityColor(status?.quality.average_quality || 0) as any}
                    size={60}
                  />
                  <Typography variant="h4">{status?.quality.average_quality?.toFixed(1) || 0}%</Typography>
                </Box>
              </Box>

              {status?.quality.low_quality_symbols && status.quality.low_quality_symbols.length > 0 && (
                <>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Low Quality Symbols
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap">
                    {status.quality.low_quality_symbols.slice(0, 5).map((item) => (
                      <Chip
                        key={item.symbol}
                        label={`${item.symbol}: ${item.score.toFixed(1)}%`}
                        size="small"
                        color="warning"
                      />
                    ))}
                  </Stack>
                </>
              )}

              {status?.quality.validation_failures > 0 && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  {status.quality.validation_failures} validation failures detected
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
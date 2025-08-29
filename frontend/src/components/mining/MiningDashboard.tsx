import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Button,
  LinearProgress,
  Chip,
  Alert,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Tabs,
  Tab,
  CircularProgress,
  Tooltip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  Stop,
  Refresh,
  Assessment,
  Warning,
  CheckCircle,
  Error as ErrorIcon,
  Schedule,
  Storage,
  Speed,
  BugReport,
  TrendingUp,
  CloudDownload,
} from '@mui/icons-material';
import { useDispatch, useSelector } from 'react-redux';
import { RootState } from '../../store/store';
import api from '../../services/api';

interface MiningProgress {
  total_symbols: number;
  processed: number;
  successful: number;
  failed: number;
  skipped: number;
  candles_collected: number;
  gaps_filled: number;
  current_symbol: string | null;
  current_batch: number;
  total_batches: number;
  estimated_completion: string | null;
  api_calls: number;
  rate_limit_delays: number;
}

interface MiningPerformance {
  symbols_per_minute: number;
  candles_per_second: number;
  api_calls_per_minute: number;
  average_symbol_time: number;
  cache_hits: number;
  cache_misses: number;
}

interface MiningStatus {
  is_running: boolean;
  is_paused: boolean;
  mode: string;
  progress: MiningProgress;
  performance: MiningPerformance;
  failed_symbols: number;
  orchestrator: string | null;
  task_status?: string;
}

interface FailedSymbol {
  error: string;
  timestamp: string;
  permanent: boolean;
  retry_count: number;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div hidden={value !== index} {...other}>
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const MiningDashboard: React.FC = () => {
  const [status, setStatus] = useState<MiningStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [startDialogOpen, setStartDialogOpen] = useState(false);
  const [failedSymbols, setFailedSymbols] = useState<Record<string, FailedSymbol>>({});
  const [statistics, setStatistics] = useState<any>(null);
  
  // Mining configuration
  const [miningConfig, setMiningConfig] = useState({
    mode: 'full',
    days_back: 60,
    batch_size: 50,
    concurrent_limit: 10,
    start_phase: 1,
    end_phase: 3,
  });

  const fetchStatus = useCallback(async () => {
    try {
      const response = await api.get('/api/mining/status');
      setStatus(response.data);
    } catch (err) {
      console.error('Error fetching mining status:', err);
    }
  }, []);

  const fetchFailedSymbols = useCallback(async () => {
    try {
      const response = await api.get('/api/mining/failed-symbols');
      setFailedSymbols(response.data.permanent_failures || {});
    } catch (err) {
      console.error('Error fetching failed symbols:', err);
    }
  }, []);

  const fetchStatistics = useCallback(async () => {
    try {
      const response = await api.get('/api/mining/statistics');
      setStatistics(response.data);
    } catch (err) {
      console.error('Error fetching statistics:', err);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchFailedSymbols();
    fetchStatistics();
    
    // Poll for updates every 2 seconds when mining is running
    const interval = setInterval(() => {
      if (status?.is_running) {
        fetchStatus();
      }
    }, 2000);
    
    return () => clearInterval(interval);
  }, [status?.is_running]);

  const handleStartMining = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.post('/api/mining/start', miningConfig);
      setStartDialogOpen(false);
      fetchStatus();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start mining');
    } finally {
      setLoading(false);
    }
  };

  const handleControlMining = async (action: string) => {
    setLoading(true);
    try {
      await api.post('/api/mining/control', { action });
      fetchStatus();
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to ${action} mining`);
    } finally {
      setLoading(false);
    }
  };

  const handleRetryFailed = async (symbols?: string[]) => {
    setLoading(true);
    try {
      await api.post('/api/mining/retry-failed', { symbols });
      fetchFailedSymbols();
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to retry symbols');
    } finally {
      setLoading(false);
    }
  };

  const getProgressPercentage = () => {
    if (!status?.progress) return 0;
    const { total_symbols, processed } = status.progress;
    return total_symbols > 0 ? (processed / total_symbols) * 100 : 0;
  };

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hours}h ${minutes}m ${secs}s`;
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat().format(num);
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Data Mining Dashboard
      </Typography>

      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Control Panel */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              Mining Control
            </Typography>
            
            <Chip
              label={status?.is_running ? 'Running' : 'Stopped'}
              color={status?.is_running ? 'success' : 'default'}
              icon={status?.is_running ? <CheckCircle /> : <Stop />}
            />
            
            {status?.is_paused && (
              <Chip label="Paused" color="warning" icon={<Pause />} />
            )}
          </Box>

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              color="primary"
              startIcon={<PlayArrow />}
              onClick={() => setStartDialogOpen(true)}
              disabled={status?.is_running || loading}
            >
              Start Mining
            </Button>
            
            <Button
              variant="outlined"
              startIcon={<Pause />}
              onClick={() => handleControlMining('pause')}
              disabled={!status?.is_running || status?.is_paused || loading}
            >
              Pause
            </Button>
            
            <Button
              variant="outlined"
              startIcon={<PlayArrow />}
              onClick={() => handleControlMining('resume')}
              disabled={!status?.is_running || !status?.is_paused || loading}
            >
              Resume
            </Button>
            
            <Button
              variant="outlined"
              color="error"
              startIcon={<Stop />}
              onClick={() => handleControlMining('stop')}
              disabled={!status?.is_running || loading}
            >
              Stop
            </Button>
            
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={() => {
                fetchStatus();
                fetchFailedSymbols();
                fetchStatistics();
              }}
              disabled={loading}
            >
              Refresh
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Progress Overview */}
      {status?.is_running && status.progress && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Mining Progress
            </Typography>
            
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">
                  {formatNumber(status.progress.processed)} / {formatNumber(status.progress.total_symbols)} symbols
                </Typography>
                <Typography variant="body2">
                  {getProgressPercentage().toFixed(1)}%
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={getProgressPercentage()}
                sx={{ height: 10, borderRadius: 5 }}
              />
            </Box>

            <Grid container spacing={2}>
              <Grid item xs={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <CheckCircle color="success" />
                  <Typography variant="h6">{formatNumber(status.progress.successful)}</Typography>
                  <Typography variant="caption">Successful</Typography>
                </Paper>
              </Grid>
              
              <Grid item xs={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <ErrorIcon color="error" />
                  <Typography variant="h6">{formatNumber(status.progress.failed)}</Typography>
                  <Typography variant="caption">Failed</Typography>
                </Paper>
              </Grid>
              
              <Grid item xs={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <Storage color="primary" />
                  <Typography variant="h6">{formatNumber(status.progress.candles_collected)}</Typography>
                  <Typography variant="caption">Candles Collected</Typography>
                </Paper>
              </Grid>
              
              <Grid item xs={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <BugReport color="warning" />
                  <Typography variant="h6">{formatNumber(status.progress.gaps_filled)}</Typography>
                  <Typography variant="caption">Gaps Filled</Typography>
                </Paper>
              </Grid>
            </Grid>

            {status.progress.current_symbol && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="textSecondary">
                  Current Symbol: <strong>{status.progress.current_symbol}</strong>
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Batch: {status.progress.current_batch} / {status.progress.total_batches}
                </Typography>
                {status.progress.estimated_completion && (
                  <Typography variant="body2" color="textSecondary">
                    ETA: {new Date(status.progress.estimated_completion).toLocaleString()}
                  </Typography>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tabs for different views */}
      <Card>
        <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
          <Tab label="Performance" />
          <Tab label="Failed Symbols" />
          <Tab label="Statistics" />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          {status?.performance && (
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    <Speed sx={{ mr: 1, verticalAlign: 'middle' }} />
                    Processing Speed
                  </Typography>
                  <List>
                    <ListItem>
                      <ListItemText
                        primary={`${status.performance.symbols_per_minute.toFixed(2)} symbols/min`}
                        secondary="Symbol Processing Rate"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary={`${status.performance.candles_per_second.toFixed(2)} candles/sec`}
                        secondary="Data Collection Rate"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary={`${status.performance.api_calls_per_minute.toFixed(2)} calls/min`}
                        secondary="API Call Rate"
                      />
                    </ListItem>
                  </List>
                </Paper>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    <Assessment sx={{ mr: 1, verticalAlign: 'middle' }} />
                    Cache Performance
                  </Typography>
                  <List>
                    <ListItem>
                      <ListItemText
                        primary={formatNumber(status.performance.cache_hits)}
                        secondary="Cache Hits"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary={formatNumber(status.performance.cache_misses)}
                        secondary="Cache Misses"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary={`${status.progress?.rate_limit_delays || 0} delays`}
                        secondary="Rate Limit Delays"
                      />
                    </ListItem>
                  </List>
                </Paper>
              </Grid>
            </Grid>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <Box sx={{ mb: 2 }}>
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={() => handleRetryFailed()}
              disabled={loading || Object.keys(failedSymbols).length === 0}
            >
              Retry All Temporary Failures
            </Button>
          </Box>
          
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Symbol</TableCell>
                  <TableCell>Error</TableCell>
                  <TableCell>Timestamp</TableCell>
                  <TableCell>Retries</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {Object.entries(failedSymbols).map(([symbol, data]) => (
                  <TableRow key={symbol}>
                    <TableCell>{symbol}</TableCell>
                    <TableCell>
                      <Tooltip title={data.error}>
                        <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                          {data.error}
                        </Typography>
                      </Tooltip>
                    </TableCell>
                    <TableCell>{new Date(data.timestamp).toLocaleString()}</TableCell>
                    <TableCell>{data.retry_count}</TableCell>
                    <TableCell>
                      <Chip
                        label={data.permanent ? 'Permanent' : 'Temporary'}
                        size="small"
                        color={data.permanent ? 'error' : 'warning'}
                      />
                    </TableCell>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={() => handleRetryFailed([symbol])}
                        disabled={loading}
                      >
                        <Refresh />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          {statistics && (
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    Database Statistics
                  </Typography>
                  <List>
                    <ListItem>
                      <ListItemText
                        primary={formatNumber(statistics.database_stats.total_symbols)}
                        secondary="Total Symbols"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary={formatNumber(statistics.database_stats.active_symbols)}
                        secondary="Active Symbols"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary={formatNumber(statistics.database_stats.total_candles)}
                        secondary="Total Candles"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary={`${statistics.database_stats.average_quality}%`}
                        secondary="Average Data Quality"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary={statistics.database_stats.low_quality_symbols}
                        secondary="Low Quality Symbols"
                      />
                    </ListItem>
                  </List>
                </Paper>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    Recent Operations
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Operation</TableCell>
                          <TableCell align="right">Count</TableCell>
                          <TableCell align="right">Candles</TableCell>
                          <TableCell align="right">Avg Time</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {statistics.recent_operations?.map((op: any, idx: number) => (
                          <TableRow key={idx}>
                            <TableCell>{op.operation}</TableCell>
                            <TableCell align="right">{op.count}</TableCell>
                            <TableCell align="right">{formatNumber(op.candles_added)}</TableCell>
                            <TableCell align="right">{op.avg_duration_seconds.toFixed(1)}s</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              </Grid>
            </Grid>
          )}
        </TabPanel>
      </Card>

      {/* Start Mining Dialog */}
      <Dialog open={startDialogOpen} onClose={() => setStartDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Start Mining Configuration</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormControl fullWidth>
              <InputLabel>Mining Mode</InputLabel>
              <Select
                value={miningConfig.mode}
                label="Mining Mode"
                onChange={(e) => setMiningConfig({ ...miningConfig, mode: e.target.value })}
              >
                <MenuItem value="full">Full - All Symbols</MenuItem>
                <MenuItem value="gaps_only">Gaps Only - Fill Missing Data</MenuItem>
                <MenuItem value="new_only">New Only - Symbols Without Data</MenuItem>
                <MenuItem value="phases">Phases - Incremental Collection</MenuItem>
              </Select>
            </FormControl>
            
            <TextField
              label="Days Back"
              type="number"
              value={miningConfig.days_back}
              onChange={(e) => setMiningConfig({ ...miningConfig, days_back: parseInt(e.target.value) })}
              fullWidth
            />
            
            {miningConfig.mode !== 'phases' && (
              <>
                <TextField
                  label="Batch Size"
                  type="number"
                  value={miningConfig.batch_size}
                  onChange={(e) => setMiningConfig({ ...miningConfig, batch_size: parseInt(e.target.value) })}
                  fullWidth
                />
                
                <TextField
                  label="Concurrent Limit"
                  type="number"
                  value={miningConfig.concurrent_limit}
                  onChange={(e) => setMiningConfig({ ...miningConfig, concurrent_limit: parseInt(e.target.value) })}
                  fullWidth
                />
              </>
            )}
            
            {miningConfig.mode === 'phases' && (
              <>
                <TextField
                  label="Start Phase"
                  type="number"
                  value={miningConfig.start_phase}
                  onChange={(e) => setMiningConfig({ ...miningConfig, start_phase: parseInt(e.target.value) })}
                  inputProps={{ min: 1, max: 3 }}
                  fullWidth
                />
                
                <TextField
                  label="End Phase"
                  type="number"
                  value={miningConfig.end_phase}
                  onChange={(e) => setMiningConfig({ ...miningConfig, end_phase: parseInt(e.target.value) })}
                  inputProps={{ min: 1, max: 3 }}
                  fullWidth
                />
              </>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setStartDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleStartMining} variant="contained" disabled={loading}>
            {loading ? <CircularProgress size={24} /> : 'Start Mining'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default MiningDashboard;
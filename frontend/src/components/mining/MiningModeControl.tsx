import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  Button,
  Stack,
  Chip,
  Alert,
  CircularProgress,
  FormControlLabel,
  Switch,
  Slider,
  Divider,
  LinearProgress,
  Paper,
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  SwapHoriz as SwitchIcon,
  Storage as GapIcon,
  TrendingUp as ExpansionIcon,
  AutoMode as AutoIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';

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

export const MiningModeControl: React.FC = () => {
  const theme = useTheme();
  const [miningMode, setMiningMode] = useState<'gap_filling' | 'expansion' | 'auto'>('auto');
  const [gapFillingFirst, setGapFillingFirst] = useState(true);
  const [switchOnCompletion, setSwitchOnCompletion] = useState(true);
  const [lookbackDays, setLookbackDays] = useState(60);
  const [status, setStatus] = useState<MiningModeStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    const interval = setInterval(fetchStatus, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const handleStartMining = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams({
        mode: miningMode,
        days_back: lookbackDays.toString(),
        gap_filling_first: gapFillingFirst.toString(),
        switch_on_completion: switchOnCompletion.toString(),
      });
      
      const response = await fetch(`/api/mining/v2/start-with-mode?${params}`, {
        method: 'POST',
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('Mining started:', data);
        await fetchStatus();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to start mining');
      }
    } catch (err) {
      setError('Failed to start mining');
      console.error('Error starting mining:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleStopMining = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/mining/v2/stop', {
        method: 'POST',
      });
      
      if (response.ok) {
        await fetchStatus();
      } else {
        setError('Failed to stop mining');
      }
    } catch (err) {
      setError('Failed to stop mining');
      console.error('Error stopping mining:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSwitchMode = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/mining/v2/switch-mode', {
        method: 'POST',
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('Mode switched:', data);
        await fetchStatus();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to switch mode');
      }
    } catch (err) {
      setError('Failed to switch mode');
      console.error('Error switching mode:', err);
    } finally {
      setLoading(false);
    }
  };

  const getModeIcon = (mode: string) => {
    switch (mode) {
      case 'gap_filling':
        return <GapIcon />;
      case 'expansion':
        return <ExpansionIcon />;
      case 'auto':
        return <AutoIcon />;
      default:
        return <InfoIcon />;
    }
  };

  const getModeColor = (mode: string) => {
    switch (mode) {
      case 'gap_filling':
        return theme.palette.info.main;
      case 'expansion':
        return theme.palette.success.main;
      case 'auto':
        return theme.palette.primary.main;
      default:
        return theme.palette.grey[500];
    }
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Mining Mode Control
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        
        {/* Mode Selection */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Select Mining Mode
          </Typography>
          <ToggleButtonGroup
            value={miningMode}
            exclusive
            onChange={(e, value) => value && setMiningMode(value)}
            fullWidth
            disabled={status?.is_running}
          >
            <ToggleButton value="gap_filling">
              <Stack direction="row" spacing={1} alignItems="center">
                <GapIcon />
                <span>Gap Filling</span>
              </Stack>
            </ToggleButton>
            <ToggleButton value="expansion">
              <Stack direction="row" spacing={1} alignItems="center">
                <ExpansionIcon />
                <span>Expansion</span>
              </Stack>
            </ToggleButton>
            <ToggleButton value="auto">
              <Stack direction="row" spacing={1} alignItems="center">
                <AutoIcon />
                <span>Auto</span>
              </Stack>
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
        
        {/* Auto Mode Options */}
        {miningMode === 'auto' && (
          <Box sx={{ mb: 3 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={gapFillingFirst}
                  onChange={(e) => setGapFillingFirst(e.target.checked)}
                  disabled={status?.is_running}
                />
              }
              label="Start with Gap Filling mode"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={switchOnCompletion}
                  onChange={(e) => setSwitchOnCompletion(e.target.checked)}
                  disabled={status?.is_running}
                />
              }
              label="Auto-switch on completion"
            />
          </Box>
        )}
        
        {/* Lookback Days */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Lookback Days: {lookbackDays}
          </Typography>
          <Slider
            value={lookbackDays}
            onChange={(e, value) => setLookbackDays(value as number)}
            min={7}
            max={365}
            step={7}
            marks={[
              { value: 7, label: '1W' },
              { value: 30, label: '1M' },
              { value: 60, label: '2M' },
              { value: 180, label: '6M' },
              { value: 365, label: '1Y' },
            ]}
            disabled={status?.is_running}
          />
        </Box>
        
        {/* Control Buttons */}
        <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
          {!status?.is_running ? (
            <Button
              variant="contained"
              color="primary"
              startIcon={<StartIcon />}
              onClick={handleStartMining}
              disabled={loading}
              fullWidth
            >
              Start Mining
            </Button>
          ) : (
            <>
              <Button
                variant="contained"
                color="error"
                startIcon={<StopIcon />}
                onClick={handleStopMining}
                disabled={loading}
                fullWidth
              >
                Stop Mining
              </Button>
              {status?.configuration?.mode === 'auto' && (
                <Button
                  variant="outlined"
                  startIcon={<SwitchIcon />}
                  onClick={handleSwitchMode}
                  disabled={loading}
                  fullWidth
                >
                  Switch Mode
                </Button>
              )}
            </>
          )}
        </Stack>
        
        <Divider sx={{ my: 2 }} />
        
        {/* Current Status */}
        {status?.session && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Current Status
            </Typography>
            
            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
              <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1 }}>
                <Chip
                  icon={getModeIcon(status.current_mode)}
                  label={status.current_mode.replace('_', ' ').toUpperCase()}
                  color="primary"
                  size="small"
                />
                {status.session.current_operation && (
                  <Typography variant="body2" color="text.secondary">
                    {status.session.current_operation}
                  </Typography>
                )}
                {status.session.current_symbol && (
                  <Typography variant="body2" color="text.secondary">
                    Symbol: {status.session.current_symbol}
                  </Typography>
                )}
              </Stack>
              
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">
                    Progress: {status.session.processed_symbols}/{status.session.total_symbols} symbols
                  </Typography>
                  <Typography variant="body2">
                    {status.session.progress_percentage.toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress 
                  variant="determinate" 
                  value={status.session.progress_percentage}
                  sx={{ height: 8, borderRadius: 1 }}
                />
              </Box>
              
              <Stack direction="row" spacing={3}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Successful
                  </Typography>
                  <Typography variant="body1" fontWeight="bold" color="success.main">
                    {status.session.successful_symbols}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Failed
                  </Typography>
                  <Typography variant="body1" fontWeight="bold" color="error.main">
                    {status.session.failed_symbols}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Gaps Filled
                  </Typography>
                  <Typography variant="body1" fontWeight="bold" color="info.main">
                    {status.session.gaps_filled}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Data Points
                  </Typography>
                  <Typography variant="body1" fontWeight="bold">
                    {status.session.data_points_collected.toLocaleString()}
                  </Typography>
                </Box>
              </Stack>
              
              {(status.session.gap_filling_completed || status.session.expansion_completed) && (
                <Box sx={{ mt: 2 }}>
                  <Stack direction="row" spacing={1}>
                    {status.session.gap_filling_completed && (
                      <Chip label="Gap Filling Complete" color="success" size="small" />
                    )}
                    {status.session.expansion_completed && (
                      <Chip label="Expansion Complete" color="success" size="small" />
                    )}
                  </Stack>
                </Box>
              )}
            </Paper>
          </Box>
        )}
        
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
            <CircularProgress />
          </Box>
        )}
      </CardContent>
    </Card>
  );
};
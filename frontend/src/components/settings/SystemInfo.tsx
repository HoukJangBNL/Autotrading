import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Chip,
  Button,
  Grid,
  LinearProgress,
  CircularProgress,
} from '@mui/material';
import {
  Info,
  CheckCircle,
  Error,
  Warning,
  Speed,
  Storage,
  Memory,
  Update,
  BugReport,
  GitHub,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useAppSelector } from '../../store/hooks';

interface SystemStatus {
  api: 'online' | 'offline' | 'degraded';
  websocket: 'connected' | 'disconnected' | 'reconnecting';
  database: 'healthy' | 'slow' | 'error';
  broker: 'connected' | 'disconnected';
}

export const SystemInfo: React.FC = () => {
  const { connected: wsConnected } = useAppSelector((state) => state.websocket);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    api: 'online',
    websocket: wsConnected ? 'connected' : 'disconnected',
    database: 'healthy',
    broker: 'connected',
  });
  const [checking, setChecking] = useState(false);

  // App version info
  const appInfo = {
    version: '1.0.0',
    build: '2024.08.27',
    environment: process.env.NODE_ENV || 'development',
    lastUpdated: '2024-08-27',
  };

  // Performance metrics (mock)
  const [performance, setPerformance] = useState({
    cpuUsage: 25,
    memoryUsage: 45,
    networkLatency: 12,
    apiResponseTime: 85,
  });

  useEffect(() => {
    setSystemStatus(prev => ({
      ...prev,
      websocket: wsConnected ? 'connected' : 'disconnected',
    }));
  }, [wsConnected]);

  const handleCheckSystem = async () => {
    setChecking(true);
    
    // Simulate system check
    setTimeout(() => {
      // Mock random status updates
      setSystemStatus({
        api: Math.random() > 0.1 ? 'online' : 'degraded',
        websocket: wsConnected ? 'connected' : 'disconnected',
        database: Math.random() > 0.2 ? 'healthy' : 'slow',
        broker: Math.random() > 0.15 ? 'connected' : 'disconnected',
      });
      
      setPerformance({
        cpuUsage: Math.floor(Math.random() * 60) + 20,
        memoryUsage: Math.floor(Math.random() * 50) + 30,
        networkLatency: Math.floor(Math.random() * 30) + 5,
        apiResponseTime: Math.floor(Math.random() * 100) + 50,
      });
      
      setChecking(false);
    }, 2000);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online':
      case 'connected':
      case 'healthy':
        return <CheckCircle color="success" />;
      case 'degraded':
      case 'slow':
      case 'reconnecting':
        return <Warning color="warning" />;
      case 'offline':
      case 'disconnected':
      case 'error':
        return <Error color="error" />;
      default:
        return <Info color="info" />;
    }
  };

  const getStatusColor = (status: string): "success" | "warning" | "error" | "default" => {
    switch (status) {
      case 'online':
      case 'connected':
      case 'healthy':
        return 'success';
      case 'degraded':
      case 'slow':
      case 'reconnecting':
        return 'warning';
      case 'offline':
      case 'disconnected':
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        System Information
      </Typography>
      
      <Box sx={{ mb: 3 }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Application version and system status
        </Typography>
      </Box>

      {/* Version Information */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="subtitle1" gutterBottom>
          Application Details
        </Typography>
        
        <Grid container spacing={2}>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              Version
            </Typography>
            <Typography variant="body1" fontWeight="bold">
              v{appInfo.version}
            </Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              Build
            </Typography>
            <Typography variant="body1">
              {appInfo.build}
            </Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              Environment
            </Typography>
            <Chip 
              label={appInfo.environment} 
              size="small"
              color={appInfo.environment === 'production' ? 'success' : 'warning'}
            />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              Last Updated
            </Typography>
            <Typography variant="body1">
              {format(new Date(appInfo.lastUpdated), 'MMM dd, yyyy')}
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* System Status */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="subtitle1">
            System Status
          </Typography>
          <Button
            variant="outlined"
            size="small"
            onClick={handleCheckSystem}
            disabled={checking}
            startIcon={checking ? <CircularProgress size={16} /> : <Update />}
          >
            {checking ? 'Checking...' : 'Check Status'}
          </Button>
        </Box>

        <List>
          <ListItem>
            <ListItemIcon>
              {getStatusIcon(systemStatus.api)}
            </ListItemIcon>
            <ListItemText
              primary="API Server"
              secondary="Main application backend"
            />
            <Chip
              label={systemStatus.api}
              size="small"
              color={getStatusColor(systemStatus.api)}
            />
          </ListItem>

          <ListItem>
            <ListItemIcon>
              {getStatusIcon(systemStatus.websocket)}
            </ListItemIcon>
            <ListItemText
              primary="WebSocket Connection"
              secondary="Real-time data stream"
            />
            <Chip
              label={systemStatus.websocket}
              size="small"
              color={getStatusColor(systemStatus.websocket)}
            />
          </ListItem>

          <ListItem>
            <ListItemIcon>
              {getStatusIcon(systemStatus.database)}
            </ListItemIcon>
            <ListItemText
              primary="Database"
              secondary="Data storage and retrieval"
            />
            <Chip
              label={systemStatus.database}
              size="small"
              color={getStatusColor(systemStatus.database)}
            />
          </ListItem>

          <ListItem>
            <ListItemIcon>
              {getStatusIcon(systemStatus.broker)}
            </ListItemIcon>
            <ListItemText
              primary="Broker Connection"
              secondary="Schwab API integration"
            />
            <Chip
              label={systemStatus.broker}
              size="small"
              color={getStatusColor(systemStatus.broker)}
            />
          </ListItem>
        </List>
      </Paper>

      {/* Performance Metrics */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="subtitle1" gutterBottom>
          Performance Metrics
        </Typography>

        <Box sx={{ mt: 2 }}>
          <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2" color="text.secondary">
                CPU Usage
              </Typography>
              <Typography variant="body2">
                {performance.cpuUsage}%
              </Typography>
            </Box>
            <LinearProgress 
              variant="determinate" 
              value={performance.cpuUsage} 
              color={performance.cpuUsage > 80 ? 'error' : performance.cpuUsage > 60 ? 'warning' : 'success'}
            />
          </Box>

          <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2" color="text.secondary">
                Memory Usage
              </Typography>
              <Typography variant="body2">
                {performance.memoryUsage}%
              </Typography>
            </Box>
            <LinearProgress 
              variant="determinate" 
              value={performance.memoryUsage}
              color={performance.memoryUsage > 80 ? 'error' : performance.memoryUsage > 60 ? 'warning' : 'success'}
            />
          </Box>

          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={6}>
              <Typography variant="body2" color="text.secondary">
                Network Latency
              </Typography>
              <Typography variant="h6">
                {performance.networkLatency} ms
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="body2" color="text.secondary">
                API Response Time
              </Typography>
              <Typography variant="h6">
                {performance.apiResponseTime} ms
              </Typography>
            </Grid>
          </Grid>
        </Box>
      </Paper>

      {/* Support Links */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="subtitle1" gutterBottom>
          Support & Resources
        </Typography>

        <List>
          <ListItem>
            <ListItemIcon>
              <BugReport />
            </ListItemIcon>
            <ListItemText
              primary="Report an Issue"
              secondary="Submit bug reports and feature requests"
            />
            <Button variant="outlined" size="small">
              Report
            </Button>
          </ListItem>

          <ListItem>
            <ListItemIcon>
              <GitHub />
            </ListItemIcon>
            <ListItemText
              primary="Source Code"
              secondary="View project on GitHub"
            />
            <Button variant="outlined" size="small">
              GitHub
            </Button>
          </ListItem>

          <ListItem>
            <ListItemIcon>
              <Info />
            </ListItemIcon>
            <ListItemText
              primary="Documentation"
              secondary="API documentation and user guides"
            />
            <Button variant="outlined" size="small">
              Docs
            </Button>
          </ListItem>
        </List>
      </Paper>

      {/* License Info */}
      <Box sx={{ mt: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
        <Typography variant="caption" color="text.secondary">
          © 2024 Personal Trading System. Licensed for personal use only.
          This software is provided "as is" without warranty of any kind.
        </Typography>
      </Box>
    </Box>
  );
};
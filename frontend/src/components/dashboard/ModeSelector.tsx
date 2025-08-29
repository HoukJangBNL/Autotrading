import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  IconButton,
  Chip,
  Stack,
  alpha,
  useTheme,
  Tooltip,
  Fade,
  Badge,
} from '@mui/material';
import {
  ShowChart as DataMiningIcon,
  SmartToy as AutoTradingIcon,
  Assessment as BacktestingIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import { useAppDispatch, useAppSelector } from '../../store/hooks';
import { setActiveMode, TradingMode } from '../../features/mode/modeSlice';

interface ModeCardProps {
  mode: TradingMode;
  title: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  stats?: {
    label: string;
    value: string | number;
  }[];
  isActive: boolean;
  status: 'active' | 'paused' | 'stopped' | 'running' | 'completed';
  onClick: () => void;
}

const ModeCard: React.FC<ModeCardProps> = ({
  mode,
  title,
  description,
  icon,
  color,
  stats,
  isActive,
  status,
  onClick,
}) => {
  const theme = useTheme();
  
  const getStatusColor = () => {
    switch (status) {
      case 'active':
      case 'running':
        return theme.palette.success.main;
      case 'paused':
        return theme.palette.warning.main;
      case 'completed':
        return theme.palette.info.main;
      default:
        return theme.palette.text.disabled;
    }
  };

  const getStatusLabel = () => {
    switch (status) {
      case 'active':
        return 'Active';
      case 'running':
        return 'Running';
      case 'paused':
        return 'Paused';
      case 'completed':
        return 'Completed';
      default:
        return 'Stopped';
    }
  };

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      <Card
        sx={{
          height: '100%',
          cursor: 'pointer',
          position: 'relative',
          overflow: 'visible',
          border: isActive ? `2px solid ${color}` : '1px solid',
          borderColor: isActive ? color : 'divider',
          background: isActive
            ? `linear-gradient(135deg, ${alpha(color, 0.05)} 0%, ${alpha(color, 0.02)} 100%)`
            : 'background.paper',
          transition: 'all 0.3s ease',
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: theme.shadows[8],
            borderColor: color,
          },
        }}
        onClick={onClick}
      >
        {isActive && (
          <Badge
            badgeContent="ACTIVE"
            color="primary"
            sx={{
              position: 'absolute',
              top: 16,
              right: 16,
              '& .MuiBadge-badge': {
                bgcolor: color,
                fontWeight: 'bold',
                fontSize: '0.65rem',
                height: 20,
                minWidth: 20,
                borderRadius: 1,
              },
            }}
          />
        )}
        
        <CardContent sx={{ p: 3 }}>
          <Stack spacing={2}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Box
                sx={{
                  width: 56,
                  height: 56,
                  borderRadius: 2,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: alpha(color, 0.1),
                  color: color,
                }}
              >
                {icon}
              </Box>
              <Box sx={{ flex: 1 }}>
                <Typography variant="h6" fontWeight="bold" color="text.primary">
                  {title}
                </Typography>
                <Chip
                  label={getStatusLabel()}
                  size="small"
                  sx={{
                    mt: 0.5,
                    bgcolor: alpha(getStatusColor(), 0.1),
                    color: getStatusColor(),
                    fontWeight: 'medium',
                    fontSize: '0.7rem',
                  }}
                />
              </Box>
            </Box>
            
            <Typography variant="body2" color="text.secondary" sx={{ minHeight: 40 }}>
              {description}
            </Typography>
            
            {stats && stats.length > 0 && (
              <Box
                sx={{
                  pt: 2,
                  borderTop: 1,
                  borderColor: 'divider',
                  display: 'grid',
                  gridTemplateColumns: `repeat(${Math.min(stats.length, 2)}, 1fr)`,
                  gap: 2,
                }}
              >
                {stats.map((stat, index) => (
                  <Box key={index}>
                    <Typography variant="caption" color="text.secondary">
                      {stat.label}
                    </Typography>
                    <Typography variant="body1" fontWeight="bold" color={color}>
                      {stat.value}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Stack>
        </CardContent>
      </Card>
    </motion.div>
  );
};

export const ModeSelector: React.FC = () => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const { activeMode, modeStatus, settings } = useAppSelector((state) => state.mode);
  const { summary } = useAppSelector((state) => state.portfolio);
  const { strategies } = useAppSelector((state) => state.strategies);
  
  const modeConfigs = [
    {
      mode: 'data-mining' as TradingMode,
      title: 'Data Mining Mode',
      description: 'Collect and analyze real-time market data for insights and patterns',
      icon: <DataMiningIcon sx={{ fontSize: 32 }} />,
      color: theme.palette.primary.main,
      stats: [
        { label: 'Symbols', value: settings.dataMining.symbols.length || 31 },
        { label: 'Refresh', value: `${settings.dataMining.refreshInterval}s` },
      ],
      status: modeStatus.dataMining,
    },
    {
      mode: 'auto-trading' as TradingMode,
      title: 'Auto Trading Mode',
      description: 'Execute trades automatically based on configured strategies',
      icon: <AutoTradingIcon sx={{ fontSize: 32 }} />,
      color: theme.palette.success.main,
      stats: [
        { label: 'Strategies', value: strategies?.filter(s => s.is_active).length || 0 },
        { label: 'Risk Limit', value: `${settings.autoTrading.riskLimit}%` },
      ],
      status: modeStatus.autoTrading,
    },
    {
      mode: 'backtesting' as TradingMode,
      title: 'Backtesting Mode',
      description: 'Test and optimize strategies using historical market data',
      icon: <BacktestingIcon sx={{ fontSize: 32 }} />,
      color: theme.palette.warning.main,
      stats: [
        { label: 'Capital', value: `$${(settings.backtesting.initialCapital / 1000).toFixed(0)}K` },
        { label: 'Period', value: 'Custom' },
      ],
      status: modeStatus.backtesting,
    },
  ];

  const handleModeClick = async (mode: TradingMode) => {
    dispatch(setActiveMode(mode));
    
    // Start/stop multi-phase historical data mining based on mode
    if (mode === 'data-mining') {
      try {
        // Start multi-phase historical data mining (Phase 1-3)
        const response = await fetch(
          'https://localhost:8182/api/mining/v2/start-multi-phase?start_phase=1&end_phase=3&days_back=60',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
          }
        );
        const data = await response.json();
        console.log('Multi-phase historical data mining started:', data);
      } catch (error) {
        console.error('Failed to start multi-phase mining:', error);
      }
    } else {
      // Stop multi-phase data mining when switching to other modes
      try {
        await fetch('https://localhost:8182/api/mining/v2/stop', {
          method: 'POST',
          credentials: 'include'
        });
        console.log('Multi-phase mining stopped');
      } catch (error) {
        console.error('Failed to stop multi-phase mining:', error);
      }
    }
  };

  return (
    <Box sx={{ mb: 4 }}>
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box>
          <Typography variant="h5" fontWeight="bold" gutterBottom>
            Trading Mode Control Center
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Select and configure your trading operation mode
          </Typography>
        </Box>
        <Tooltip title="Mode Settings">
          <IconButton size="small">
            <SettingsIcon />
          </IconButton>
        </Tooltip>
      </Box>
      
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            sm: '1fr',
            md: 'repeat(3, 1fr)',
          },
          gap: 3,
        }}
      >
        {modeConfigs.map((config) => (
          <Fade in key={config.mode}>
            <div>
              <ModeCard
                {...config}
                isActive={activeMode === config.mode}
                onClick={() => handleModeClick(config.mode)}
              />
            </div>
          </Fade>
        ))}
      </Box>
    </Box>
  );
};
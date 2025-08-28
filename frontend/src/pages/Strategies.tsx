import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Tabs,
  Tab,
  CircularProgress,
  Snackbar,
  Alert,
} from '@mui/material';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import {
  fetchStrategies,
  createStrategy,
  updateStrategy,
  deleteStrategy,
  startStrategy,
  stopStrategy,
} from '../features/strategies/strategiesSlice';
import { StrategyList } from '../components/strategies/StrategyList';
import { StrategyForm } from '../components/strategies/StrategyForm';
import { BacktestInterface } from '../components/strategies/BacktestInterface';
import { BacktestResults } from '../components/strategies/BacktestResults';
import { 
  Strategy, 
  StrategyStatus, 
  StrategyType, 
  BacktestConfig,
  BacktestResult,
} from '../types/strategy';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`strategy-tabpanel-${index}`}
      aria-labelledby={`strategy-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

export const Strategies: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { mode } = useParams<{ mode?: string }>();
  const { strategies, loading } = useAppSelector((state) => state.strategies);
  
  const [activeTab, setActiveTab] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState<Strategy | undefined>();
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [backtestProgress, setBacktestProgress] = useState(0);
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' });

  useEffect(() => {
    dispatch(fetchStrategies());
  }, [dispatch]);

  useEffect(() => {
    // Handle routing for create/edit modes
    if (mode === 'create') {
      setShowForm(true);
      setEditingStrategy(undefined);
    } else if (mode?.startsWith('edit/')) {
      const strategyId = mode.replace('edit/', '');
      const strategy = convertToLocalStrategy(strategies.find(s => s.id === strategyId));
      if (strategy) {
        setShowForm(true);
        setEditingStrategy(strategy);
      }
    } else {
      setShowForm(false);
      setEditingStrategy(undefined);
    }
  }, [mode, strategies]);

  // Convert between Redux strategy type and local Strategy type
  const convertToLocalStrategy = (strategy: any): Strategy | undefined => {
    if (!strategy) return undefined;
    return {
      id: strategy.id,
      name: strategy.name,
      description: strategy.description || '',
      type: strategy.type as StrategyType || StrategyType.MOMENTUM,
      status: strategy.is_active ? StrategyStatus.ACTIVE : StrategyStatus.INACTIVE,
      symbols: strategy.symbols || [],
      parameters: Object.entries(strategy.parameters || {}).map(([key, value]) => ({
        name: key,
        type: typeof value === 'number' ? 'number' : 'string',
        value,
      })),
      riskManagement: {
        stopLoss: 2,
        takeProfit: 5,
        positionSize: 10,
        maxDrawdown: 10,
        maxPositions: 5,
      },
      schedule: {
        startTime: '09:30',
        endTime: '16:00',
        tradingDays: ['MON', 'TUE', 'WED', 'THU', 'FRI'],
        timezone: 'America/New_York',
      },
      performance: strategy.performance ? {
        totalReturn: strategy.performance.total_pnl || 0,
        annualizedReturn: 0,
        sharpeRatio: strategy.performance.sharpe_ratio || 0,
        maxDrawdown: strategy.performance.max_drawdown || 0,
        winRate: strategy.performance.win_rate || 0,
        profitFactor: 0,
        totalTrades: strategy.performance.total_trades || 0,
        avgWin: 0,
        avgLoss: 0,
      } : undefined,
      createdAt: strategy.created_at || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  };

  const handleToggleStrategy = async (id: string, active: boolean) => {
    try {
      if (active) {
        await dispatch(startStrategy(id)).unwrap();
        setSnackbar({ open: true, message: 'Strategy activated successfully', severity: 'success' });
      } else {
        await dispatch(stopStrategy(id)).unwrap();
        setSnackbar({ open: true, message: 'Strategy deactivated successfully', severity: 'success' });
      }
    } catch (error) {
      setSnackbar({ open: true, message: 'Failed to toggle strategy', severity: 'error' });
    }
  };

  const handleDeleteStrategy = async (id: string) => {
    try {
      await dispatch(deleteStrategy(id)).unwrap();
      setSnackbar({ open: true, message: 'Strategy deleted successfully', severity: 'success' });
    } catch (error) {
      setSnackbar({ open: true, message: 'Failed to delete strategy', severity: 'error' });
    }
  };

  const handleCloneStrategy = (id: string) => {
    const strategy = convertToLocalStrategy(strategies.find(s => s.id === id));
    if (strategy) {
      const clonedStrategy = {
        ...strategy,
        id: '',
        name: `${strategy.name} (Copy)`,
      };
      setEditingStrategy(clonedStrategy);
      setShowForm(true);
    }
  };

  const handleBacktest = (id: string) => {
    setSelectedStrategyId(id);
    setActiveTab(1); // Switch to backtest tab
  };

  const handleRunBacktest = async (config: BacktestConfig) => {
    setBacktestRunning(true);
    setBacktestProgress(0);
    
    // Simulate backtest progress
    const progressInterval = setInterval(() => {
      setBacktestProgress((prev) => {
        if (prev >= 100) {
          clearInterval(progressInterval);
          setBacktestRunning(false);
          
          // Generate mock backtest result
          const mockResult: BacktestResult = {
            id: `backtest-${Date.now()}`,
            strategyId: config.strategyId,
            config,
            performance: {
              totalReturn: 15.5,
              annualizedReturn: 18.2,
              sharpeRatio: 1.45,
              maxDrawdown: -8.3,
              winRate: 0.62,
              profitFactor: 1.8,
              totalTrades: 145,
              avgWin: 250,
              avgLoss: -140,
            },
            equityCurve: Array.from({ length: 100 }, (_, i) => ({
              date: new Date(Date.now() - (100 - i) * 24 * 60 * 60 * 1000).toISOString(),
              value: config.initialCapital * (1 + i * 0.002 + Math.random() * 0.01),
            })),
            trades: [],
            monthlyReturns: {
              'Jan': 2.5,
              'Feb': -1.2,
              'Mar': 3.8,
              'Apr': 1.9,
              'May': -0.5,
              'Jun': 2.1,
            },
            status: 'completed',
            progress: 100,
          };
          
          setBacktestResult(mockResult);
          setActiveTab(2); // Switch to results tab
          return 100;
        }
        return prev + 2;
      });
    }, 100);
  };

  const handleStopBacktest = () => {
    setBacktestRunning(false);
    setBacktestProgress(0);
  };

  const handleSubmitStrategy = async (strategyData: Partial<Strategy>) => {
    try {
      // Convert local strategy format to Redux format
      const apiData = {
        name: strategyData.name,
        type: strategyData.type,
        description: strategyData.description,
        symbols: strategyData.symbols,
        parameters: strategyData.parameters?.reduce((acc, param) => {
          acc[param.name] = param.value;
          return acc;
        }, {} as any),
        is_active: false,
      };

      if (editingStrategy?.id) {
        await dispatch(updateStrategy({ id: editingStrategy.id, data: apiData })).unwrap();
        setSnackbar({ open: true, message: 'Strategy updated successfully', severity: 'success' });
      } else {
        await dispatch(createStrategy(apiData)).unwrap();
        setSnackbar({ open: true, message: 'Strategy created successfully', severity: 'success' });
      }
      
      setShowForm(false);
      navigate('/strategies');
    } catch (error) {
      setSnackbar({ open: true, message: 'Failed to save strategy', severity: 'error' });
    }
  };

  const localStrategies = strategies.map(convertToLocalStrategy).filter(Boolean) as Strategy[];

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (showForm) {
    return (
      <StrategyForm
        strategy={editingStrategy}
        onSubmit={handleSubmitStrategy}
        onCancel={() => {
          setShowForm(false);
          navigate('/strategies');
        }}
      />
    );
  }

  return (
    <Box>
      <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)}>
        <Tab label="Strategy List" />
        <Tab label="Backtest" />
        <Tab label="Results" />
      </Tabs>

      <TabPanel value={activeTab} index={0}>
        <StrategyList
          strategies={localStrategies}
          onToggle={handleToggleStrategy}
          onDelete={handleDeleteStrategy}
          onClone={handleCloneStrategy}
          onBacktest={handleBacktest}
        />
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        {selectedStrategyId ? (
          <BacktestInterface
            strategyId={selectedStrategyId}
            onRunBacktest={handleRunBacktest}
            onStopBacktest={handleStopBacktest}
            isRunning={backtestRunning}
            progress={backtestProgress}
          />
        ) : (
          <Alert severity="info">
            Please select a strategy from the list to run a backtest.
          </Alert>
        )}
      </TabPanel>

      <TabPanel value={activeTab} index={2}>
        {backtestResult ? (
          <BacktestResults result={backtestResult} />
        ) : (
          <Alert severity="info">
            No backtest results available. Run a backtest to see results here.
          </Alert>
        )}
      </TabPanel>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};
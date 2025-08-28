import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  Grid,
  ToggleButton,
  ToggleButtonGroup,
  Alert,
  Divider,
  InputAdornment,
  Chip,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { useAppSelector } from '../../store/hooks';
import { OrderSide } from '../../types/index';

interface QuickTradeProps {
  symbol?: string;
  onTrade?: (order: any) => void;
}

export const QuickTrade: React.FC<QuickTradeProps> = ({ symbol: initialSymbol, onTrade }) => {
  const theme = useTheme();
  const { positions } = useAppSelector((state) => state.portfolio);
  
  const [symbol, setSymbol] = useState(initialSymbol || 'AAPL');
  const [quantity, setQuantity] = useState('100');
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  // Mock market data
  const marketData = {
    symbol,
    bid: 175.25,
    ask: 175.30,
    last: 175.28,
    change: 2.45,
    changePercent: 1.42,
    volume: '45.2M',
    high: 176.50,
    low: 173.80,
  };

  const currentPosition = positions.find(p => p.symbol === symbol);
  const hasPosition = currentPosition && currentPosition.quantity > 0;

  const handleQuickTrade = (side: OrderSide) => {
    if (!symbol || !quantity) {
      setError('Symbol and quantity are required');
      return;
    }

    const qty = parseFloat(quantity);
    if (isNaN(qty) || qty <= 0) {
      setError('Invalid quantity');
      return;
    }

    const order = {
      symbol,
      side,
      orderType: 'MARKET',
      quantity: qty,
      timestamp: new Date().toISOString(),
    };

    if (onTrade) {
      onTrade(order);
    }

    setSuccess(`${side} ${qty} ${symbol} @ Market`);
    setError('');
    setTimeout(() => setSuccess(''), 5000);
  };

  const handlePresetQuantity = (preset: string) => {
    setSelectedPreset(preset);
    switch (preset) {
      case 'small':
        setQuantity('100');
        break;
      case 'medium':
        setQuantity('500');
        break;
      case 'large':
        setQuantity('1000');
        break;
      case 'max':
        if (hasPosition) {
          setQuantity(currentPosition.quantity.toString());
        }
        break;
    }
  };

  const calculateOrderValue = (side: OrderSide) => {
    const price = side === OrderSide.BUY ? marketData.ask : marketData.bid;
    const qty = parseFloat(quantity) || 0;
    return qty * price;
  };

  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        Quick Trade
      </Typography>

      {/* Symbol Input */}
      <TextField
        fullWidth
        label="Symbol"
        value={symbol}
        onChange={(e) => setSymbol(e.target.value.toUpperCase())}
        size="small"
        sx={{ mb: 2 }}
      />

      {/* Market Data Display */}
      <Box sx={{ mb: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
        <Grid container spacing={2}>
          <Grid size={6}>
            <Box>
              <Typography variant="h4" fontWeight="bold">
                ${marketData.last.toFixed(2)}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {marketData.change >= 0 ? (
                  <TrendingUpIcon fontSize="small" color="success" />
                ) : (
                  <TrendingDownIcon fontSize="small" color="error" />
                )}
                <Typography
                  variant="body2"
                  color={marketData.change >= 0 ? 'success.main' : 'error.main'}
                >
                  {marketData.change >= 0 ? '+' : ''}{marketData.change.toFixed(2)} ({marketData.changePercent}%)
                </Typography>
              </Box>
            </Box>
          </Grid>
          <Grid size={6}>
            <Box sx={{ textAlign: 'right' }}>
              <Typography variant="caption" color="text.secondary">
                Vol: {marketData.volume}
              </Typography>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  H: ${marketData.high.toFixed(2)} L: ${marketData.low.toFixed(2)}
                </Typography>
              </Box>
            </Box>
          </Grid>
        </Grid>
        <Divider sx={{ my: 1 }} />
        <Grid container spacing={2}>
          <Grid size={6}>
            <Typography variant="caption" color="text.secondary">Bid</Typography>
            <Typography variant="body1" fontWeight="medium">
              ${marketData.bid.toFixed(2)}
            </Typography>
          </Grid>
          <Grid size={6} sx={{ textAlign: 'right' }}>
            <Typography variant="caption" color="text.secondary">Ask</Typography>
            <Typography variant="body1" fontWeight="medium">
              ${marketData.ask.toFixed(2)}
            </Typography>
          </Grid>
        </Grid>
      </Box>

      {/* Current Position */}
      {hasPosition && currentPosition && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Current Position: {currentPosition.quantity} shares 
          {currentPosition.avgCost !== undefined && (
            <> @ ${currentPosition.avgCost.toFixed(2)}</>
          )}
        </Alert>
      )}

      {/* Quantity Presets */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="caption" color="text.secondary" gutterBottom>
          Quick Amounts
        </Typography>
        <ToggleButtonGroup
          value={selectedPreset}
          exclusive
          onChange={(e, value) => value && handlePresetQuantity(value)}
          fullWidth
          size="small"
        >
          <ToggleButton value="small">
            100
          </ToggleButton>
          <ToggleButton value="medium">
            500
          </ToggleButton>
          <ToggleButton value="large">
            1000
          </ToggleButton>
          {hasPosition && (
            <ToggleButton value="max">
              Max ({currentPosition.quantity})
            </ToggleButton>
          )}
        </ToggleButtonGroup>
      </Box>

      {/* Quantity Input */}
      <TextField
        fullWidth
        label="Quantity"
        value={quantity}
        onChange={(e) => {
          setQuantity(e.target.value);
          setSelectedPreset(null);
        }}
        type="number"
        size="small"
        sx={{ mb: 2 }}
        InputProps={{
          inputProps: { min: 1 },
        }}
      />

      {/* Order Value Display */}
      <Box sx={{ mb: 2, p: 1, bgcolor: 'background.default', borderRadius: 1 }}>
        <Grid container spacing={2}>
          <Grid size={6}>
            <Typography variant="caption" color="text.secondary">
              Buy Value
            </Typography>
            <Typography variant="body1" color="success.main" fontWeight="medium">
              ${calculateOrderValue(OrderSide.BUY).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </Typography>
          </Grid>
          <Grid size={6}>
            <Typography variant="caption" color="text.secondary">
              Sell Value
            </Typography>
            <Typography variant="body1" color="error.main" fontWeight="medium">
              ${calculateOrderValue(OrderSide.SELL).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </Typography>
          </Grid>
        </Grid>
      </Box>

      {/* Quick Action Buttons */}
      <Grid container spacing={2}>
        <Grid size={6}>
          <Button
            fullWidth
            variant="contained"
            size="large"
            startIcon={<ArrowUpwardIcon />}
            onClick={() => handleQuickTrade(OrderSide.BUY)}
            sx={{
              bgcolor: theme.palette.success.main,
              '&:hover': {
                bgcolor: theme.palette.success.dark,
              },
              height: 56,
            }}
          >
            Quick Buy
          </Button>
        </Grid>
        <Grid size={6}>
          <Button
            fullWidth
            variant="contained"
            size="large"
            startIcon={<ArrowDownwardIcon />}
            onClick={() => handleQuickTrade(OrderSide.SELL)}
            disabled={!hasPosition}
            sx={{
              bgcolor: theme.palette.error.main,
              '&:hover': {
                bgcolor: theme.palette.error.dark,
              },
              '&:disabled': {
                bgcolor: theme.palette.action.disabledBackground,
              },
              height: 56,
            }}
          >
            Quick Sell
          </Button>
        </Grid>
      </Grid>

      {/* Status Messages */}
      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mt: 2 }}>
          {success}
        </Alert>
      )}

      {/* Market Status */}
      <Box sx={{ mt: 2, p: 1, bgcolor: 'background.default', borderRadius: 1 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid size={6}>
            <Typography variant="caption" color="text.secondary">
              Market Status
            </Typography>
          </Grid>
          <Grid size={6} sx={{ textAlign: 'right' }}>
            <Chip
              label="Market Open"
              size="small"
              color="success"
              sx={{ fontWeight: 'bold' }}
            />
          </Grid>
        </Grid>
      </Box>
    </Paper>
  );
};
import React, { useState } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  InputAdornment,
  Alert,
  Grid,
  Chip,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useAppDispatch, useAppSelector } from '../../store/hooks';

export enum OrderSide {
  BUY = 'BUY',
  SELL = 'SELL',
}

export enum OrderType {
  MARKET = 'MARKET',
  LIMIT = 'LIMIT',
  STOP = 'STOP',
  STOP_LIMIT = 'STOP_LIMIT',
}

export enum TimeInForce {
  DAY = 'DAY',
  GTC = 'GTC',
  IOC = 'IOC',
  FOK = 'FOK',
}

interface OrderFormProps {
  symbol?: string;
  onSubmit?: (order: any) => void;
}

export const OrderForm: React.FC<OrderFormProps> = ({ symbol: initialSymbol, onSubmit }) => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const { positions } = useAppSelector((state) => state.portfolio);

  const [side, setSide] = useState<OrderSide>(OrderSide.BUY);
  const [symbol, setSymbol] = useState(initialSymbol || '');
  const [orderType, setOrderType] = useState<OrderType>(OrderType.LIMIT);
  const [quantity, setQuantity] = useState('');
  const [limitPrice, setLimitPrice] = useState('');
  const [stopPrice, setStopPrice] = useState('');
  const [timeInForce, setTimeInForce] = useState<TimeInForce>(TimeInForce.DAY);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const currentPosition = positions.find(p => p.symbol === symbol);
  const hasPosition = currentPosition && currentPosition.quantity > 0;

  const calculateOrderValue = () => {
    const qty = parseFloat(quantity) || 0;
    const price = orderType === OrderType.MARKET 
      ? 0 // Would use current market price
      : parseFloat(limitPrice) || 0;
    return qty * price;
  };

  const validateOrder = () => {
    if (!symbol) {
      setError('Symbol is required');
      return false;
    }
    if (!quantity || parseFloat(quantity) <= 0) {
      setError('Quantity must be greater than 0');
      return false;
    }
    if (orderType === OrderType.LIMIT && (!limitPrice || parseFloat(limitPrice) <= 0)) {
      setError('Limit price is required for limit orders');
      return false;
    }
    if ((orderType === OrderType.STOP || orderType === OrderType.STOP_LIMIT) && 
        (!stopPrice || parseFloat(stopPrice) <= 0)) {
      setError('Stop price is required for stop orders');
      return false;
    }
    setError('');
    return true;
  };

  const handleSubmit = () => {
    if (!validateOrder()) return;

    const order = {
      symbol,
      side,
      orderType,
      quantity: parseFloat(quantity),
      limitPrice: limitPrice ? parseFloat(limitPrice) : undefined,
      stopPrice: stopPrice ? parseFloat(stopPrice) : undefined,
      timeInForce,
      timestamp: new Date().toISOString(),
    };

    // TODO: Dispatch order to Redux store
    // dispatch(submitOrder(order));
    
    if (onSubmit) {
      onSubmit(order);
    }

    setSuccess(`Order submitted: ${side} ${quantity} ${symbol}`);
    setTimeout(() => setSuccess(''), 5000);

    // Reset form
    setQuantity('');
    setLimitPrice('');
    setStopPrice('');
  };

  const handleQuickQuantity = (percent: number) => {
    if (hasPosition && side === OrderSide.SELL) {
      const qty = Math.floor(currentPosition.quantity * percent / 100);
      setQuantity(qty.toString());
    }
    // For buying, would need account balance to calculate
  };

  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        Place Order
      </Typography>

      <Box sx={{ mb: 2 }}>
        <ToggleButtonGroup
          value={side}
          exclusive
          onChange={(e, value) => value && setSide(value)}
          fullWidth
        >
          <ToggleButton
            value={OrderSide.BUY}
            sx={{
              '&.Mui-selected': {
                backgroundColor: theme.palette.success.dark,
                color: theme.palette.success.contrastText,
                '&:hover': {
                  backgroundColor: theme.palette.success.main,
                },
              },
            }}
          >
            Buy
          </ToggleButton>
          <ToggleButton
            value={OrderSide.SELL}
            sx={{
              '&.Mui-selected': {
                backgroundColor: theme.palette.error.dark,
                color: theme.palette.error.contrastText,
                '&:hover': {
                  backgroundColor: theme.palette.error.main,
                },
              },
            }}
          >
            Sell
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      <TextField
        fullWidth
        label="Symbol"
        value={symbol}
        onChange={(e) => setSymbol(e.target.value.toUpperCase())}
        margin="normal"
        size="small"
        InputProps={{
          endAdornment: hasPosition && (
            <InputAdornment position="end">
              <Chip
                label={`Pos: ${currentPosition.quantity}`}
                size="small"
                color="primary"
              />
            </InputAdornment>
          ),
        }}
      />

      <Grid container spacing={2}>
        <Grid size={6}>
          <FormControl fullWidth margin="normal" size="small">
            <InputLabel>Order Type</InputLabel>
            <Select
              value={orderType}
              onChange={(e) => setOrderType(e.target.value as OrderType)}
              label="Order Type"
            >
              <MenuItem value={OrderType.MARKET}>Market</MenuItem>
              <MenuItem value={OrderType.LIMIT}>Limit</MenuItem>
              <MenuItem value={OrderType.STOP}>Stop</MenuItem>
              <MenuItem value={OrderType.STOP_LIMIT}>Stop Limit</MenuItem>
            </Select>
          </FormControl>
        </Grid>
        <Grid size={6}>
          <FormControl fullWidth margin="normal" size="small">
            <InputLabel>Time in Force</InputLabel>
            <Select
              value={timeInForce}
              onChange={(e) => setTimeInForce(e.target.value as TimeInForce)}
              label="Time in Force"
            >
              <MenuItem value={TimeInForce.DAY}>Day</MenuItem>
              <MenuItem value={TimeInForce.GTC}>GTC</MenuItem>
              <MenuItem value={TimeInForce.IOC}>IOC</MenuItem>
              <MenuItem value={TimeInForce.FOK}>FOK</MenuItem>
            </Select>
          </FormControl>
        </Grid>
      </Grid>

      <TextField
        fullWidth
        label="Quantity"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        margin="normal"
        size="small"
        type="number"
        InputProps={{
          inputProps: { min: 1 },
        }}
      />

      {hasPosition && side === OrderSide.SELL && (
        <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
          <Button
            size="small"
            variant="outlined"
            onClick={() => handleQuickQuantity(25)}
          >
            25%
          </Button>
          <Button
            size="small"
            variant="outlined"
            onClick={() => handleQuickQuantity(50)}
          >
            50%
          </Button>
          <Button
            size="small"
            variant="outlined"
            onClick={() => handleQuickQuantity(75)}
          >
            75%
          </Button>
          <Button
            size="small"
            variant="outlined"
            onClick={() => handleQuickQuantity(100)}
          >
            100%
          </Button>
        </Box>
      )}

      {orderType !== OrderType.MARKET && (
        <TextField
          fullWidth
          label="Limit Price"
          value={limitPrice}
          onChange={(e) => setLimitPrice(e.target.value)}
          margin="normal"
          size="small"
          type="number"
          InputProps={{
            startAdornment: <InputAdornment position="start">$</InputAdornment>,
            inputProps: { min: 0, step: 0.01 },
          }}
        />
      )}

      {(orderType === OrderType.STOP || orderType === OrderType.STOP_LIMIT) && (
        <TextField
          fullWidth
          label="Stop Price"
          value={stopPrice}
          onChange={(e) => setStopPrice(e.target.value)}
          margin="normal"
          size="small"
          type="number"
          InputProps={{
            startAdornment: <InputAdornment position="start">$</InputAdornment>,
            inputProps: { min: 0, step: 0.01 },
          }}
        />
      )}

      {orderType !== OrderType.MARKET && quantity && limitPrice && (
        <Box sx={{ mt: 2, p: 1, bgcolor: 'background.default', borderRadius: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Estimated Order Value
          </Typography>
          <Typography variant="h6">
            ${calculateOrderValue().toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </Typography>
        </Box>
      )}

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

      <Button
        fullWidth
        variant="contained"
        onClick={handleSubmit}
        sx={{
          mt: 2,
          bgcolor: side === OrderSide.BUY ? theme.palette.success.main : theme.palette.error.main,
          '&:hover': {
            bgcolor: side === OrderSide.BUY ? theme.palette.success.dark : theme.palette.error.dark,
          },
        }}
      >
        {side} {quantity && `${quantity} `}{symbol}
      </Button>
    </Paper>
  );
};
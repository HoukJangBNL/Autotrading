import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Slider,
  Grid,
  Chip,
  InputAdornment,
} from '@mui/material';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useSettings, TradingPreferences as TradingPreferencesType } from '../../contexts/SettingsContext';
import { parse, format } from 'date-fns';

const TRADING_DAYS = [
  { value: 'MON', label: 'Monday' },
  { value: 'TUE', label: 'Tuesday' },
  { value: 'WED', label: 'Wednesday' },
  { value: 'THU', label: 'Thursday' },
  { value: 'FRI', label: 'Friday' },
  { value: 'SAT', label: 'Saturday' },
  { value: 'SUN', label: 'Sunday' },
];

export const TradingPreferences: React.FC = () => {
  const { settings, updateSettings } = useSettings();
  const [localSettings, setLocalSettings] = useState<TradingPreferencesType>(settings.trading);

  const handleChange = (field: keyof TradingPreferencesType, value: any) => {
    setLocalSettings((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleDayToggle = (day: string) => {
    const updatedDays = localSettings.tradingDays.includes(day)
      ? localSettings.tradingDays.filter((d) => d !== day)
      : [...localSettings.tradingDays, day];
    handleChange('tradingDays', updatedDays);
  };

  const handleSave = () => {
    updateSettings('trading', localSettings);
  };

  const parseTime = (timeString: string) => {
    const [hours, minutes] = timeString.split(':').map(Number);
    const date = new Date();
    date.setHours(hours, minutes, 0, 0);
    return date;
  };

  const formatTime = (date: Date | null) => {
    if (!date) return '09:30';
    return format(date, 'HH:mm');
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box>
        <Typography variant="h6" gutterBottom>
          Trading Preferences
        </Typography>
        
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Configure your default trading settings and risk parameters
          </Typography>
        </Box>

        {/* Auto Trading Toggle */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
          <FormControlLabel
            control={
              <Switch
                checked={localSettings.autoTradingEnabled}
                onChange={(e) => handleChange('autoTradingEnabled', e.target.checked)}
                color="primary"
              />
            }
            label={
              <Box>
                <Typography variant="subtitle1">Automated Trading</Typography>
                <Typography variant="body2" color="text.secondary">
                  Enable automatic execution of trading signals
                </Typography>
              </Box>
            }
          />
        </Box>

        {/* Order Defaults */}
        <Typography variant="subtitle1" gutterBottom sx={{ mt: 3 }}>
          Order Defaults
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Default Order Type</InputLabel>
              <Select
                value={localSettings.defaultOrderType}
                onChange={(e) => handleChange('defaultOrderType', e.target.value)}
                label="Default Order Type"
              >
                <MenuItem value="MARKET">Market</MenuItem>
                <MenuItem value="LIMIT">Limit</MenuItem>
                <MenuItem value="STOP">Stop</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Default Quantity"
              type="number"
              value={localSettings.defaultQuantity}
              onChange={(e) => handleChange('defaultQuantity', parseInt(e.target.value) || 0)}
              InputProps={{
                inputProps: { min: 1 },
              }}
            />
          </Grid>
        </Grid>

        {/* Risk Management */}
        <Typography variant="subtitle1" gutterBottom sx={{ mt: 3 }}>
          Risk Management
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Max Daily Loss"
              type="number"
              value={localSettings.maxLossPerDay}
              onChange={(e) => handleChange('maxLossPerDay', parseFloat(e.target.value) || 0)}
              InputProps={{
                startAdornment: <InputAdornment position="start">$</InputAdornment>,
                inputProps: { min: 0, step: 100 },
              }}
              helperText="Maximum allowed loss per trading day"
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Max Position Size"
              type="number"
              value={localSettings.maxPositionSize}
              onChange={(e) => handleChange('maxPositionSize', parseFloat(e.target.value) || 0)}
              InputProps={{
                startAdornment: <InputAdornment position="start">$</InputAdornment>,
                inputProps: { min: 0, step: 1000 },
              }}
              helperText="Maximum value per position"
            />
          </Grid>
        </Grid>

        {/* Trading Schedule */}
        <Typography variant="subtitle1" gutterBottom sx={{ mt: 3 }}>
          Trading Schedule
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={12} sm={6}>
            <TimePicker
              label="Trading Start Time"
              value={parseTime(localSettings.tradingStartTime)}
              onChange={(newValue) => {
                if (newValue) {
                  handleChange('tradingStartTime', formatTime(newValue));
                }
              }}
              slotProps={{ textField: { fullWidth: true } }}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TimePicker
              label="Trading End Time"
              value={parseTime(localSettings.tradingEndTime)}
              onChange={(newValue) => {
                if (newValue) {
                  handleChange('tradingEndTime', formatTime(newValue));
                }
              }}
              slotProps={{ textField: { fullWidth: true } }}
            />
          </Grid>
        </Grid>

        {/* Trading Days */}
        <Box sx={{ mt: 3 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Active Trading Days
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {TRADING_DAYS.map((day) => (
              <Chip
                key={day.value}
                label={day.label}
                onClick={() => handleDayToggle(day.value)}
                color={localSettings.tradingDays.includes(day.value) ? 'primary' : 'default'}
                variant={localSettings.tradingDays.includes(day.value) ? 'filled' : 'outlined'}
              />
            ))}
          </Box>
        </Box>

        {/* Position Size Slider */}
        <Box sx={{ mt: 3 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Position Size Allocation: {localSettings.defaultQuantity} shares
          </Typography>
          <Slider
            value={localSettings.defaultQuantity}
            onChange={(e, value) => handleChange('defaultQuantity', value as number)}
            min={1}
            max={1000}
            step={10}
            marks={[
              { value: 1, label: '1' },
              { value: 250, label: '250' },
              { value: 500, label: '500' },
              { value: 750, label: '750' },
              { value: 1000, label: '1000' },
            ]}
            valueLabelDisplay="auto"
          />
        </Box>

        {/* Save Button */}
        <Box sx={{ mt: 4, display: 'flex', gap: 2 }}>
          <Button
            variant="contained"
            onClick={handleSave}
          >
            Save Preferences
          </Button>
          <Button
            variant="outlined"
            onClick={() => setLocalSettings(settings.trading)}
          >
            Reset
          </Button>
        </Box>
      </Box>
    </LocalizationProvider>
  );
};
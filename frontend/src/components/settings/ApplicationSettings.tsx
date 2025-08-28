import React, { useState } from 'react';
import {
  Box,
  Button,
  Typography,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Slider,
  Paper,
  Grid,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import {
  DarkMode,
  LightMode,
  Language,
  ShowChart,
  CandlestickChart,
  Timeline,
  Refresh,
} from '@mui/icons-material';
import { useSettings, ApplicationSettings as ApplicationSettingsType } from '../../contexts/SettingsContext';

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'ko', label: '한국어' },
  { value: 'ja', label: '日本語' },
  { value: 'zh', label: '中文' },
];

const CHART_INTERVALS = [
  { value: '1m', label: '1 Minute' },
  { value: '5m', label: '5 Minutes' },
  { value: '15m', label: '15 Minutes' },
  { value: '30m', label: '30 Minutes' },
  { value: '1h', label: '1 Hour' },
  { value: '1d', label: '1 Day' },
];

export const ApplicationSettings: React.FC = () => {
  const { settings, updateSettings } = useSettings();
  const [localSettings, setLocalSettings] = useState<ApplicationSettingsType>(settings.application);

  const handleChange = (field: keyof ApplicationSettingsType, value: any) => {
    setLocalSettings((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSave = () => {
    updateSettings('application', localSettings);
    // Theme change will be applied immediately through SettingsContext
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Application Settings
      </Typography>
      
      <Box sx={{ mb: 3 }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Customize the application appearance and behavior
        </Typography>
      </Box>

      {/* Theme Selection */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          {localSettings.theme === 'dark' ? <DarkMode /> : <LightMode />}
          <Typography variant="subtitle1" sx={{ ml: 1 }}>
            Theme
          </Typography>
        </Box>
        
        <ToggleButtonGroup
          value={localSettings.theme}
          exclusive
          onChange={(e, value) => value && handleChange('theme', value)}
          fullWidth
        >
          <ToggleButton value="light">
            <LightMode sx={{ mr: 1 }} />
            Light Mode
          </ToggleButton>
          <ToggleButton value="dark">
            <DarkMode sx={{ mr: 1 }} />
            Dark Mode
          </ToggleButton>
        </ToggleButtonGroup>
      </Paper>

      {/* Language and Regional */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Language sx={{ mr: 1, color: 'text.secondary' }} />
          <Typography variant="subtitle1">
            Language & Regional
          </Typography>
        </Box>

        <FormControl fullWidth>
          <InputLabel>Language</InputLabel>
          <Select
            value={localSettings.language}
            onChange={(e) => handleChange('language', e.target.value)}
            label="Language"
          >
            {LANGUAGES.map((lang) => (
              <MenuItem key={lang.value} value={lang.value}>
                {lang.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Paper>

      {/* Chart Settings */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <ShowChart sx={{ mr: 1, color: 'text.secondary' }} />
          <Typography variant="subtitle1">
            Chart Settings
          </Typography>
        </Box>

        <Grid container spacing={3}>
          <Grid size={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Default Chart Type</InputLabel>
              <Select
                value={localSettings.chartType}
                onChange={(e) => handleChange('chartType', e.target.value)}
                label="Default Chart Type"
              >
                <MenuItem value="candlestick">
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <CandlestickChart sx={{ mr: 1, fontSize: 20 }} />
                    Candlestick
                  </Box>
                </MenuItem>
                <MenuItem value="line">
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <Timeline sx={{ mr: 1, fontSize: 20 }} />
                    Line
                  </Box>
                </MenuItem>
                <MenuItem value="area">
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <ShowChart sx={{ mr: 1, fontSize: 20 }} />
                    Area
                  </Box>
                </MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Default Time Interval</InputLabel>
              <Select
                value={localSettings.chartInterval}
                onChange={(e) => handleChange('chartInterval', e.target.value)}
                label="Default Time Interval"
              >
                {CHART_INTERVALS.map((interval) => (
                  <MenuItem key={interval.value} value={interval.value}>
                    {interval.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Paper>

      {/* Data Refresh Settings */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Refresh sx={{ mr: 1, color: 'text.secondary' }} />
          <Typography variant="subtitle1">
            Data Refresh
          </Typography>
        </Box>

        <Typography variant="body2" color="text.secondary" gutterBottom>
          Refresh Interval: {localSettings.refreshInterval} seconds
        </Typography>
        
        <Slider
          value={localSettings.refreshInterval}
          onChange={(e, value) => handleChange('refreshInterval', value as number)}
          min={1}
          max={60}
          step={1}
          marks={[
            { value: 1, label: '1s' },
            { value: 15, label: '15s' },
            { value: 30, label: '30s' },
            { value: 45, label: '45s' },
            { value: 60, label: '60s' },
          ]}
          valueLabelDisplay="auto"
        />
        
        <Typography variant="caption" color="text.secondary">
          Lower values provide more real-time data but may increase system load
        </Typography>
      </Paper>

      {/* Interface Options */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="subtitle1" gutterBottom>
          Interface Options
        </Typography>

        <FormControlLabel
          control={
            <Switch
              checked={localSettings.showTooltips}
              onChange={(e) => handleChange('showTooltips', e.target.checked)}
              color="primary"
            />
          }
          label={
            <Box>
              <Typography variant="body1">Show Tooltips</Typography>
              <Typography variant="body2" color="text.secondary">
                Display helpful hints and explanations throughout the app
              </Typography>
            </Box>
          }
        />
      </Paper>

      {/* Save Button */}
      <Box sx={{ mt: 4, display: 'flex', gap: 2 }}>
        <Button
          variant="contained"
          onClick={handleSave}
        >
          Save Settings
        </Button>
        <Button
          variant="outlined"
          onClick={() => setLocalSettings(settings.application)}
        >
          Reset
        </Button>
      </Box>
    </Box>
  );
};
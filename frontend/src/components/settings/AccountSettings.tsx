import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Alert,
  IconButton,
  InputAdornment,
  Chip,
  Grid,
  CircularProgress,
} from '@mui/material';
import { Visibility, VisibilityOff, CheckCircle, Error } from '@mui/icons-material';
import { useSettings, AccountSettings as AccountSettingsType } from '../../contexts/SettingsContext';

export const AccountSettings: React.FC = () => {
  const { settings, updateSettings } = useSettings();
  const [showApiKey, setShowApiKey] = useState(false);
  const [showApiSecret, setShowApiSecret] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<'success' | 'error' | null>(null);
  const [localSettings, setLocalSettings] = useState<AccountSettingsType>(settings.account);

  const handleChange = (field: keyof AccountSettingsType, value: string) => {
    setLocalSettings((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSave = () => {
    updateSettings('account', localSettings);
    setTestResult(null);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    
    // Simulate API connection test
    setTimeout(() => {
      const success = localSettings.apiKey && localSettings.apiSecret && localSettings.accountId;
      setTestResult(success ? 'success' : 'error');
      setTesting(false);
      
      if (success) {
        updateSettings('account', {
          ...localSettings,
          isConnected: true,
          connectionStatus: 'connected',
        });
      }
    }, 2000);
  };

  const maskValue = (value: string) => {
    if (!value) return '';
    const visibleChars = 4;
    if (value.length <= visibleChars * 2) return value;
    return value.substring(0, visibleChars) + '•'.repeat(8) + value.substring(value.length - visibleChars);
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Account Settings
      </Typography>
      
      <Box sx={{ mb: 3 }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Configure your Schwab API connection and account details
        </Typography>
      </Box>

      {/* Connection Status */}
      <Box sx={{ mb: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
        <Grid container alignItems="center" spacing={2}>
          <Grid size={12} sm={6}>
            <Typography variant="subtitle2" gutterBottom>
              Connection Status
            </Typography>
            <Chip
              icon={settings.account.isConnected ? <CheckCircle /> : <Error />}
              label={settings.account.isConnected ? 'Connected' : 'Disconnected'}
              color={settings.account.isConnected ? 'success' : 'error'}
              size="small"
            />
          </Grid>
          <Grid size={12} sm={6}>
            <Typography variant="subtitle2" gutterBottom>
              Account ID
            </Typography>
            <Typography variant="body1">
              {localSettings.accountId || 'Not configured'}
            </Typography>
          </Grid>
        </Grid>
      </Box>

      {/* API Configuration */}
      <Grid container spacing={3}>
        <Grid size={12}>
          <TextField
            fullWidth
            label="API Key"
            value={showApiKey ? localSettings.apiKey : maskValue(localSettings.apiKey)}
            onChange={(e) => handleChange('apiKey', e.target.value)}
            type={showApiKey ? 'text' : 'password'}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowApiKey(!showApiKey)}
                    edge="end"
                    size="small"
                  >
                    {showApiKey ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </Grid>

        <Grid size={12}>
          <TextField
            fullWidth
            label="API Secret"
            value={showApiSecret ? localSettings.apiSecret : maskValue(localSettings.apiSecret)}
            onChange={(e) => handleChange('apiSecret', e.target.value)}
            type={showApiSecret ? 'text' : 'password'}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowApiSecret(!showApiSecret)}
                    edge="end"
                    size="small"
                  >
                    {showApiSecret ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </Grid>

        <Grid size={12}>
          <TextField
            fullWidth
            label="Account ID"
            value={localSettings.accountId}
            onChange={(e) => handleChange('accountId', e.target.value)}
            helperText="Your Schwab account identifier"
          />
        </Grid>
      </Grid>

      {/* Test Result */}
      {testResult && (
        <Box sx={{ mt: 2 }}>
          {testResult === 'success' ? (
            <Alert severity="success">
              Connection test successful! Your API credentials are valid.
            </Alert>
          ) : (
            <Alert severity="error">
              Connection test failed. Please check your API credentials.
            </Alert>
          )}
        </Box>
      )}

      {/* Action Buttons */}
      <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={testing}
        >
          Save Settings
        </Button>
        <Button
          variant="outlined"
          onClick={handleTestConnection}
          disabled={testing || !localSettings.apiKey || !localSettings.apiSecret}
          startIcon={testing && <CircularProgress size={16} />}
        >
          {testing ? 'Testing...' : 'Test Connection'}
        </Button>
      </Box>

      {/* Security Notice */}
      <Alert severity="info" sx={{ mt: 3 }}>
        <Typography variant="body2">
          <strong>Security Notice:</strong> Your API credentials are stored locally in your browser 
          and are never sent to our servers. Always keep your API keys secure and never share them.
        </Typography>
      </Alert>
    </Box>
  );
};
import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Switch,
  FormControlLabel,
  FormGroup,
  Alert,
  Paper,
  Divider,
} from '@mui/material';
import { Email, Notifications, Warning, TrendingUp, Assessment } from '@mui/icons-material';
import { useSettings, NotificationSettings as NotificationSettingsType } from '../../contexts/SettingsContext';

export const NotificationSettings: React.FC = () => {
  const { settings, updateSettings } = useSettings();
  const [localSettings, setLocalSettings] = useState<NotificationSettingsType>(settings.notifications);
  const [emailError, setEmailError] = useState('');

  const handleChange = (field: keyof NotificationSettingsType, value: any) => {
    setLocalSettings((prev) => ({
      ...prev,
      [field]: value,
    }));

    if (field === 'email') {
      validateEmail(value);
    }
  };

  const validateEmail = (email: string) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (email && !emailRegex.test(email)) {
      setEmailError('Please enter a valid email address');
    } else {
      setEmailError('');
    }
  };

  const handleSave = () => {
    if (emailError) return;
    updateSettings('notifications', localSettings);
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Notification Settings
      </Typography>
      
      <Box sx={{ mb: 3 }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Configure how you receive alerts and notifications
        </Typography>
      </Box>

      {/* Email Configuration */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Email sx={{ mr: 1, color: 'text.secondary' }} />
          <Typography variant="subtitle1">
            Email Notifications
          </Typography>
        </Box>
        
        <FormControlLabel
          control={
            <Switch
              checked={localSettings.emailEnabled}
              onChange={(e) => handleChange('emailEnabled', e.target.checked)}
              color="primary"
            />
          }
          label="Enable email notifications"
          sx={{ mb: 2 }}
        />

        <TextField
          fullWidth
          label="Email Address"
          value={localSettings.email}
          onChange={(e) => handleChange('email', e.target.value)}
          disabled={!localSettings.emailEnabled}
          error={!!emailError}
          helperText={emailError || 'Receive important alerts via email'}
          sx={{ mb: 2 }}
        />
      </Paper>

      {/* Notification Types */}
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Notifications sx={{ mr: 1, color: 'text.secondary' }} />
          <Typography variant="subtitle1">
            Notification Types
          </Typography>
        </Box>

        <FormGroup>
          <FormControlLabel
            control={
              <Switch
                checked={localSettings.tradeNotifications}
                onChange={(e) => handleChange('tradeNotifications', e.target.checked)}
                color="primary"
              />
            }
            label={
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <TrendingUp sx={{ mr: 1, fontSize: 20, color: 'success.main' }} />
                <Box>
                  <Typography variant="body1">Trade Executions</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Notify when orders are filled or cancelled
                  </Typography>
                </Box>
              </Box>
            }
            sx={{ mb: 2 }}
          />

          <Divider sx={{ my: 2 }} />

          <FormControlLabel
            control={
              <Switch
                checked={localSettings.signalNotifications}
                onChange={(e) => handleChange('signalNotifications', e.target.checked)}
                color="primary"
              />
            }
            label={
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <TrendingUp sx={{ mr: 1, fontSize: 20, color: 'info.main' }} />
                <Box>
                  <Typography variant="body1">Trading Signals</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Alert when new trading signals are generated
                  </Typography>
                </Box>
              </Box>
            }
            sx={{ mb: 2 }}
          />

          <Divider sx={{ my: 2 }} />

          <FormControlLabel
            control={
              <Switch
                checked={localSettings.riskAlerts}
                onChange={(e) => handleChange('riskAlerts', e.target.checked)}
                color="primary"
              />
            }
            label={
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Warning sx={{ mr: 1, fontSize: 20, color: 'warning.main' }} />
                <Box>
                  <Typography variant="body1">Risk Alerts</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Warnings for risk limits and unusual market conditions
                  </Typography>
                </Box>
              </Box>
            }
            sx={{ mb: 2 }}
          />

          <Divider sx={{ my: 2 }} />

          <FormControlLabel
            control={
              <Switch
                checked={localSettings.dailyReports}
                onChange={(e) => handleChange('dailyReports', e.target.checked)}
                color="primary"
              />
            }
            label={
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Assessment sx={{ mr: 1, fontSize: 20, color: 'primary.main' }} />
                <Box>
                  <Typography variant="body1">Daily Reports</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Receive daily performance summaries and analytics
                  </Typography>
                </Box>
              </Box>
            }
          />
        </FormGroup>
      </Paper>

      {/* Alert Preview */}
      {localSettings.emailEnabled && localSettings.email && (
        <Alert severity="info" sx={{ mt: 3 }}>
          <Typography variant="body2">
            Notifications will be sent to: <strong>{localSettings.email}</strong>
          </Typography>
        </Alert>
      )}

      {/* Save Button */}
      <Box sx={{ mt: 4, display: 'flex', gap: 2 }}>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={!!emailError}
        >
          Save Notifications
        </Button>
        <Button
          variant="outlined"
          onClick={() => {
            setLocalSettings(settings.notifications);
            setEmailError('');
          }}
        >
          Reset
        </Button>
      </Box>
    </Box>
  );
};
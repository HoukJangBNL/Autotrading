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
  Paper,
  Alert,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  DialogContentText,
} from '@mui/material';
import {
  CloudUpload,
  CloudDownload,
  Delete,
  Storage,
  History,
  Archive,
  Download,
  Upload,
  ClearAll,
  Description,
} from '@mui/icons-material';
import { useSettings, DataSettings } from '../../contexts/SettingsContext';
import { format } from 'date-fns';

export const DataManagement: React.FC = () => {
  const { settings, updateSettings, exportSettings, importSettings, resetSettings } = useSettings();
  const [localSettings, setLocalSettings] = useState<DataSettings>(settings.data);
  const [clearCacheDialog, setClearCacheDialog] = useState(false);
  const [resetDialog, setResetDialog] = useState(false);
  const [cacheClearing, setCacheClearing] = useState(false);
  const [importSuccess, setImportSuccess] = useState(false);
  const [importError, setImportError] = useState('');

  const handleChange = (field: keyof DataSettings, value: any) => {
    setLocalSettings((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSave = () => {
    updateSettings('data', localSettings);
  };

  const handleClearCache = async () => {
    setCacheClearing(true);
    // Simulate cache clearing
    setTimeout(() => {
      localStorage.removeItem('marketDataCache');
      localStorage.removeItem('tradingHistory');
      localStorage.removeItem('backtestResults');
      setCacheClearing(false);
      setClearCacheDialog(false);
    }, 2000);
  };

  const handleExportData = () => {
    // Export all trading data
    const tradingData = {
      settings: settings,
      trades: [], // Would fetch from state/API
      strategies: [], // Would fetch from state/API
      backtests: [], // Would fetch from state/API
      timestamp: new Date().toISOString(),
    };

    const dataStr = JSON.stringify(tradingData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `trading-data-${format(new Date(), 'yyyy-MM-dd')}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const handleImportSettings = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      await importSettings(file);
      setImportSuccess(true);
      setImportError('');
      setTimeout(() => setImportSuccess(false), 3000);
    } catch (error) {
      setImportError('Failed to import settings. Please check the file format.');
      setImportSuccess(false);
    }
    
    // Reset input
    event.target.value = '';
  };

  const handleResetAll = () => {
    resetSettings();
    setResetDialog(false);
    window.location.reload(); // Reload to apply all changes
  };

  // Calculate cache size (mock)
  const calculateCacheSize = () => {
    let size = 0;
    for (const key in localStorage) {
      if (localStorage.hasOwnProperty(key)) {
        size += localStorage.getItem(key)?.length || 0;
      }
    }
    return (size / 1024).toFixed(2); // Convert to KB
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Data Management
      </Typography>
      
      <Box sx={{ mb: 3 }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Manage application data, backups, and storage
        </Typography>
      </Box>

      {/* Backup Settings */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <CloudUpload sx={{ mr: 1, color: 'text.secondary' }} />
          <Typography variant="subtitle1">
            Backup Settings
          </Typography>
        </Box>

        <FormControlLabel
          control={
            <Switch
              checked={localSettings.autoBackup}
              onChange={(e) => handleChange('autoBackup', e.target.checked)}
              color="primary"
            />
          }
          label="Enable automatic backups"
          sx={{ mb: 2 }}
        />

        <FormControl fullWidth disabled={!localSettings.autoBackup}>
          <InputLabel>Backup Frequency</InputLabel>
          <Select
            value={localSettings.backupInterval}
            onChange={(e) => handleChange('backupInterval', e.target.value)}
            label="Backup Frequency"
          >
            <MenuItem value="daily">Daily</MenuItem>
            <MenuItem value="weekly">Weekly</MenuItem>
            <MenuItem value="monthly">Monthly</MenuItem>
          </Select>
        </FormControl>
      </Paper>

      {/* Storage Management */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Storage sx={{ mr: 1, color: 'text.secondary' }} />
          <Typography variant="subtitle1">
            Storage Management
          </Typography>
        </Box>

        <List>
          <ListItem>
            <ListItemIcon>
              <History />
            </ListItemIcon>
            <ListItemText
              primary="Trading History"
              secondary={`Keep logs for ${localSettings.keepLogsFor} days`}
            />
            <ListItemSecondaryAction>
              <FormControl size="small" sx={{ minWidth: 100 }}>
                <Select
                  value={localSettings.keepLogsFor}
                  onChange={(e) => handleChange('keepLogsFor', e.target.value as number)}
                >
                  <MenuItem value={7}>7 days</MenuItem>
                  <MenuItem value={30}>30 days</MenuItem>
                  <MenuItem value={90}>90 days</MenuItem>
                  <MenuItem value={365}>1 year</MenuItem>
                </Select>
              </FormControl>
            </ListItemSecondaryAction>
          </ListItem>

          <ListItem>
            <ListItemIcon>
              <Storage />
            </ListItemIcon>
            <ListItemText
              primary="Cache Size"
              secondary={`Currently using ${calculateCacheSize()} KB`}
            />
            <ListItemSecondaryAction>
              <IconButton
                edge="end"
                onClick={() => setClearCacheDialog(true)}
                color="error"
              >
                <Delete />
              </IconButton>
            </ListItemSecondaryAction>
          </ListItem>
        </List>

        {cacheClearing && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Clearing cache...
            </Typography>
            <LinearProgress />
          </Box>
        )}
      </Paper>

      {/* Import/Export */}
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Archive sx={{ mr: 1, color: 'text.secondary' }} />
          <Typography variant="subtitle1">
            Import / Export
          </Typography>
        </Box>

        <List>
          <ListItem>
            <ListItemIcon>
              <Download />
            </ListItemIcon>
            <ListItemText
              primary="Export Settings"
              secondary="Download current settings as JSON"
            />
            <ListItemSecondaryAction>
              <Button
                variant="outlined"
                startIcon={<CloudDownload />}
                onClick={exportSettings}
              >
                Export
              </Button>
            </ListItemSecondaryAction>
          </ListItem>

          <ListItem>
            <ListItemIcon>
              <Upload />
            </ListItemIcon>
            <ListItemText
              primary="Import Settings"
              secondary="Restore settings from a backup file"
            />
            <ListItemSecondaryAction>
              <input
                accept="application/json"
                style={{ display: 'none' }}
                id="import-settings-file"
                type="file"
                onChange={handleImportSettings}
              />
              <label htmlFor="import-settings-file">
                <Button
                  variant="outlined"
                  component="span"
                  startIcon={<CloudUpload />}
                >
                  Import
                </Button>
              </label>
            </ListItemSecondaryAction>
          </ListItem>

          <ListItem>
            <ListItemIcon>
              <Description />
            </ListItemIcon>
            <ListItemText
              primary="Export All Data"
              secondary="Download complete trading history and data"
            />
            <ListItemSecondaryAction>
              <Button
                variant="outlined"
                startIcon={<Archive />}
                onClick={handleExportData}
              >
                Export All
              </Button>
            </ListItemSecondaryAction>
          </ListItem>
        </List>
      </Paper>

      {/* Success/Error Messages */}
      {importSuccess && (
        <Alert severity="success" sx={{ mt: 2 }}>
          Settings imported successfully!
        </Alert>
      )}
      {importError && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {importError}
        </Alert>
      )}

      {/* Action Buttons */}
      <Box sx={{ mt: 4, display: 'flex', gap: 2, justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="contained"
            onClick={handleSave}
          >
            Save Settings
          </Button>
        </Box>
        <Button
          variant="outlined"
          color="error"
          startIcon={<ClearAll />}
          onClick={() => setResetDialog(true)}
        >
          Reset All Settings
        </Button>
      </Box>

      {/* Clear Cache Dialog */}
      <Dialog open={clearCacheDialog} onClose={() => setClearCacheDialog(false)}>
        <DialogTitle>Clear Cache?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This will clear all cached market data and temporary files. 
            Your settings and trading history will be preserved.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setClearCacheDialog(false)}>Cancel</Button>
          <Button onClick={handleClearCache} color="error" variant="contained">
            Clear Cache
          </Button>
        </DialogActions>
      </Dialog>

      {/* Reset Settings Dialog */}
      <Dialog open={resetDialog} onClose={() => setResetDialog(false)}>
        <DialogTitle>Reset All Settings?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This will reset all application settings to their default values. 
            This action cannot be undone. Consider exporting your settings first.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResetDialog(false)}>Cancel</Button>
          <Button onClick={handleResetAll} color="error" variant="contained">
            Reset Everything
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
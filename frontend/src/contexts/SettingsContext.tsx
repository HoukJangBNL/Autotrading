import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

export interface AccountSettings {
  apiKey: string;
  apiSecret: string;
  accountId: string;
  isConnected: boolean;
  connectionStatus: 'connected' | 'disconnected' | 'testing';
}

export interface TradingPreferences {
  defaultOrderType: 'MARKET' | 'LIMIT' | 'STOP';
  defaultQuantity: number;
  maxLossPerDay: number;
  maxPositionSize: number;
  autoTradingEnabled: boolean;
  tradingStartTime: string;
  tradingEndTime: string;
  tradingDays: string[];
}

export interface NotificationSettings {
  emailEnabled: boolean;
  email: string;
  tradeNotifications: boolean;
  signalNotifications: boolean;
  riskAlerts: boolean;
  dailyReports: boolean;
}

export interface ApplicationSettings {
  theme: 'light' | 'dark';
  language: 'en' | 'ko' | 'ja' | 'zh';
  refreshInterval: number; // in seconds
  chartType: 'candlestick' | 'line' | 'area';
  chartInterval: '1m' | '5m' | '15m' | '30m' | '1h' | '1d';
  showTooltips: boolean;
}

export interface DataSettings {
  autoBackup: boolean;
  backupInterval: 'daily' | 'weekly' | 'monthly';
  keepLogsFor: number; // days
  cacheSize: number; // MB
}

export interface Settings {
  account: AccountSettings;
  trading: TradingPreferences;
  notifications: NotificationSettings;
  application: ApplicationSettings;
  data: DataSettings;
}

const defaultSettings: Settings = {
  account: {
    apiKey: '',
    apiSecret: '',
    accountId: '',
    isConnected: false,
    connectionStatus: 'disconnected',
  },
  trading: {
    defaultOrderType: 'LIMIT',
    defaultQuantity: 100,
    maxLossPerDay: 1000,
    maxPositionSize: 10000,
    autoTradingEnabled: false,
    tradingStartTime: '09:30',
    tradingEndTime: '16:00',
    tradingDays: ['MON', 'TUE', 'WED', 'THU', 'FRI'],
  },
  notifications: {
    emailEnabled: false,
    email: '',
    tradeNotifications: true,
    signalNotifications: true,
    riskAlerts: true,
    dailyReports: false,
  },
  application: {
    theme: 'dark',
    language: 'en',
    refreshInterval: 5,
    chartType: 'candlestick',
    chartInterval: '5m',
    showTooltips: true,
  },
  data: {
    autoBackup: false,
    backupInterval: 'daily',
    keepLogsFor: 30,
    cacheSize: 100,
  },
};

interface SettingsContextType {
  settings: Settings;
  updateSettings: (section: keyof Settings, values: any) => void;
  resetSettings: () => void;
  exportSettings: () => void;
  importSettings: (file: File) => Promise<void>;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export const useSettings = () => {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
};

interface SettingsProviderProps {
  children: ReactNode;
}

export const SettingsProvider: React.FC<SettingsProviderProps> = ({ children }) => {
  const [settings, setSettings] = useState<Settings>(() => {
    const saved = localStorage.getItem('tradingAppSettings');
    return saved ? { ...defaultSettings, ...JSON.parse(saved) } : defaultSettings;
  });

  const theme = React.useMemo(
    () =>
      createTheme({
        palette: {
          mode: settings.application.theme,
        },
      }),
    [settings.application.theme]
  );

  useEffect(() => {
    localStorage.setItem('tradingAppSettings', JSON.stringify(settings));
  }, [settings]);

  const updateSettings = (section: keyof Settings, values: any) => {
    setSettings((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        ...values,
      },
    }));
  };

  const resetSettings = () => {
    setSettings(defaultSettings);
    localStorage.removeItem('tradingAppSettings');
  };

  const exportSettings = () => {
    const dataStr = JSON.stringify(settings, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `trading-settings-${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const importSettings = async (file: File): Promise<void> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const imported = JSON.parse(e.target?.result as string);
          setSettings({ ...defaultSettings, ...imported });
          resolve();
        } catch (error) {
          reject(error);
        }
      };
      reader.readAsText(file);
    });
  };

  return (
    <SettingsContext.Provider
      value={{
        settings,
        updateSettings,
        resetSettings,
        exportSettings,
        importSettings,
      }}
    >
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </SettingsContext.Provider>
  );
};
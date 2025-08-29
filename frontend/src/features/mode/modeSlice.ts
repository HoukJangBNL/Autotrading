import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export type TradingMode = 'data-mining' | 'auto-trading' | 'backtesting';

export interface ModeSettings {
  dataMining: {
    enabled: boolean;
    refreshInterval: number; // seconds
    symbols: string[];
  };
  autoTrading: {
    enabled: boolean;
    maxPositions: number;
    riskLimit: number; // percentage
    activeStrategies: string[];
  };
  backtesting: {
    enabled: boolean;
    startDate: string;
    endDate: string;
    initialCapital: number;
  };
}

interface ModeState {
  activeMode: TradingMode;
  settings: ModeSettings;
  modeStatus: {
    dataMining: 'active' | 'paused' | 'stopped';
    autoTrading: 'active' | 'paused' | 'stopped';
    backtesting: 'running' | 'completed' | 'stopped';
  };
  lastModeChange: string | null;
}

const initialState: ModeState = {
  activeMode: 'data-mining',
  settings: {
    dataMining: {
      enabled: true,
      refreshInterval: 5,
      symbols: [],
    },
    autoTrading: {
      enabled: false,
      maxPositions: 10,
      riskLimit: 2,
      activeStrategies: [],
    },
    backtesting: {
      enabled: false,
      startDate: '',
      endDate: '',
      initialCapital: 100000,
    },
  },
  modeStatus: {
    dataMining: 'active',
    autoTrading: 'stopped',
    backtesting: 'stopped',
  },
  lastModeChange: null,
};

const modeSlice = createSlice({
  name: 'mode',
  initialState,
  reducers: {
    setActiveMode: (state, action: PayloadAction<TradingMode>) => {
      const previousMode = state.activeMode;
      state.activeMode = action.payload;
      state.lastModeChange = new Date().toISOString();
      
      // Update mode statuses
      state.modeStatus.dataMining = action.payload === 'data-mining' ? 'active' : 'paused';
      state.modeStatus.autoTrading = action.payload === 'auto-trading' ? 'active' : 'stopped';
      state.modeStatus.backtesting = action.payload === 'backtesting' ? 'running' : 'stopped';
      
      // Update settings
      state.settings.dataMining.enabled = action.payload === 'data-mining';
      state.settings.autoTrading.enabled = action.payload === 'auto-trading';
      state.settings.backtesting.enabled = action.payload === 'backtesting';
    },
    
    updateDataMiningSettings: (state, action: PayloadAction<Partial<ModeSettings['dataMining']>>) => {
      state.settings.dataMining = {
        ...state.settings.dataMining,
        ...action.payload,
      };
    },
    
    updateAutoTradingSettings: (state, action: PayloadAction<Partial<ModeSettings['autoTrading']>>) => {
      state.settings.autoTrading = {
        ...state.settings.autoTrading,
        ...action.payload,
      };
    },
    
    updateBacktestingSettings: (state, action: PayloadAction<Partial<ModeSettings['backtesting']>>) => {
      state.settings.backtesting = {
        ...state.settings.backtesting,
        ...action.payload,
      };
    },
    
    toggleMode: (state, action: PayloadAction<TradingMode>) => {
      if (state.activeMode === action.payload) {
        // If clicking the active mode, pause it
        switch (action.payload) {
          case 'data-mining':
            state.modeStatus.dataMining = state.modeStatus.dataMining === 'active' ? 'paused' : 'active';
            break;
          case 'auto-trading':
            state.modeStatus.autoTrading = state.modeStatus.autoTrading === 'active' ? 'paused' : 'active';
            break;
          case 'backtesting':
            state.modeStatus.backtesting = state.modeStatus.backtesting === 'running' ? 'stopped' : 'running';
            break;
        }
      } else {
        // Switch to new mode
        state.activeMode = action.payload;
        state.lastModeChange = new Date().toISOString();
      }
    },
  },
});

export const {
  setActiveMode,
  updateDataMiningSettings,
  updateAutoTradingSettings,
  updateBacktestingSettings,
  toggleMode,
} = modeSlice.actions;

export default modeSlice.reducer;
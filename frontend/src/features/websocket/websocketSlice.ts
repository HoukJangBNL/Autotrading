// WebSocket state management slice

import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface WebSocketMessage {
  type: string;
  data: any;
}

interface WebSocketState {
  isConnected: boolean;
  subscribedTopics: string[];
  subscribedSymbols: string[];
  lastMessage: WebSocketMessage | null;
  connectionError: string | null;
}

const initialState: WebSocketState = {
  isConnected: false,
  subscribedTopics: [],
  subscribedSymbols: [],
  lastMessage: null,
  connectionError: null,
};

const websocketSlice = createSlice({
  name: 'websocket',
  initialState,
  reducers: {
    connected: (state) => {
      state.isConnected = true;
      state.connectionError = null;
    },
    disconnected: (state) => {
      state.isConnected = false;
    },
    connectionError: (state, action: PayloadAction<string>) => {
      state.connectionError = action.payload;
      state.isConnected = false;
    },
    subscribed: (state, action: PayloadAction<string>) => {
      if (!state.subscribedTopics.includes(action.payload)) {
        state.subscribedTopics.push(action.payload);
      }
    },
    unsubscribed: (state, action: PayloadAction<string>) => {
      state.subscribedTopics = state.subscribedTopics.filter(
        topic => topic !== action.payload
      );
    },
    symbolSubscribed: (state, action: PayloadAction<string>) => {
      if (!state.subscribedSymbols.includes(action.payload)) {
        state.subscribedSymbols.push(action.payload);
      }
    },
    symbolUnsubscribed: (state, action: PayloadAction<string>) => {
      state.subscribedSymbols = state.subscribedSymbols.filter(
        symbol => symbol !== action.payload
      );
    },
    messageReceived: (state, action: PayloadAction<WebSocketMessage>) => {
      state.lastMessage = action.payload;
    },
  },
});

export const {
  connected,
  disconnected,
  connectionError,
  subscribed,
  unsubscribed,
  symbolSubscribed,
  symbolUnsubscribed,
  messageReceived,
} = websocketSlice.actions;

export default websocketSlice.reducer;
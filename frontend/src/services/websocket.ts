import { store } from '../store/store';
import { 
  connected, 
  disconnected, 
  messageReceived,
  connectionError 
} from '../features/websocket/websocketSlice';

class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectInterval = 5000;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private pingInterval: NodeJS.Timeout | null = null;

  connect() {
    const wsUrl = process.env.REACT_APP_WS_URL || 'wss://127.0.0.1:8182/ws';
    
    try {
      this.ws = new WebSocket(wsUrl);
      this.setupEventListeners();
    } catch (error) {
      console.error('WebSocket connection error:', error);
      store.dispatch(connectionError('Failed to connect to WebSocket'));
    }
  }

  private setupEventListeners() {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      store.dispatch(connected());
      this.reconnectAttempts = 0;
      
      // Start ping interval to keep connection alive
      this.startPingInterval();
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      store.dispatch(disconnected());
      this.stopPingInterval();
      this.scheduleReconnect();
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      store.dispatch(connectionError('WebSocket error occurred'));
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Handle different message types
        switch (data.type) {
          case 'market_data':
            store.dispatch(messageReceived({ type: 'market_data', data }));
            break;
          case 'strategy_signal':
            store.dispatch(messageReceived({ type: 'strategy_signal', data }));
            break;
          case 'order_update':
            store.dispatch(messageReceived({ type: 'order_update', data }));
            break;
          case 'portfolio_update':
            store.dispatch(messageReceived({ type: 'portfolio_update', data }));
            break;
          case 'pong':
            // Pong response from server
            break;
          case 'error':
            console.error('WebSocket error message:', data.message);
            break;
          default:
            console.log('Unknown message type:', data.type);
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };
  }

  private startPingInterval() {
    // Send ping every 30 seconds to keep connection alive
    this.pingInterval = setInterval(() => {
      if (this.isConnected()) {
        this.send({ type: 'ping' });
      }
    }, 30000);
  }

  private stopPingInterval() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      store.dispatch(connectionError('Unable to reconnect to server'));
      return;
    }

    this.reconnectAttempts++;
    console.log(`Reconnecting in ${this.reconnectInterval}ms... (attempt ${this.reconnectAttempts})`);

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, this.reconnectInterval);
  }

  private send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket is not connected. Message not sent:', data);
    }
  }

  subscribe(topic: string) {
    this.send({ type: 'subscribe', topic });
  }

  unsubscribe(topic: string) {
    this.send({ type: 'unsubscribe', topic });
  }

  subscribeSymbol(symbol: string, timeframe = '1min') {
    this.send({ 
      type: 'subscribe_symbol', 
      symbol, 
      timeframe 
    });
  }

  unsubscribeSymbol(symbol: string) {
    this.send({ 
      type: 'unsubscribe_symbol', 
      symbol 
    });
  }

  disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    this.stopPingInterval();
    
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const websocketService = new WebSocketService();
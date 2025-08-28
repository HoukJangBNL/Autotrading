import { useEffect, useCallback, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { websocketService } from '../services/websocket';
import { store } from '../store/store';
import { 
  updateCandle,
  updateQuote 
} from '../features/marketData/marketDataSlice';
import { 
  updatePosition,
  updatePortfolioSummary 
} from '../features/portfolio/portfolioSlice';
import { 
  addSignal,
  updateOrderStatus 
} from '../features/trading/tradingSlice';

interface UseWebSocketOptions {
  autoConnect?: boolean;
  reconnectInterval?: number;
}

export const useWebSocket = (options: UseWebSocketOptions = {}) => {
  const { autoConnect = true } = options;
  const dispatch = useAppDispatch();
  const { isConnected } = useAppSelector((state) => state.websocket);
  const messageHandlerRef = useRef<((data: any) => void) | null>(null);

  const handleMessage = useCallback((message: any) => {
    const { type, data } = message;
    
    switch (type) {
      case 'market_data':
        if (data.type === 'quote') {
          dispatch(updateQuote({
            symbol: data.symbol,
            quote: data.quote
          }));
        } else if (data.type === 'bar') {
          dispatch(updateCandle({
            symbol: data.symbol,
            candle: data.bar
          }));
        }
        break;
        
      case 'portfolio_update':
        if (data.type === 'summary') {
          dispatch(updatePortfolioSummary(data.summary));
        } else if (data.type === 'position') {
          dispatch(updatePosition(data.position));
        }
        break;
        
      case 'order_update':
        dispatch(updateOrderStatus({
          orderId: data.order_id,
          status: data.status,
          filled_qty: data.filled_qty,
          avg_fill_price: data.avg_fill_price
        }));
        
        if (data.status === 'filled') {
          dispatch(addSignal({
            signal_id: data.trade_id,
            timestamp: data.filled_at,
            symbol: data.symbol,
            direction: data.side,
            strength: 1,
            confidence: 1,
            strategy_name: 'manual',
            reason: 'Order filled',
            executed: true
          }));
        }
        break;
        
      case 'strategy_signal':
        // Handle strategy signals
        console.log('Strategy signal received:', data);
        break;
        
      case 'strategy_metrics':
        // Handle strategy metrics updates
        console.log('Strategy metrics received:', data);
        break;
        
      default:
        console.log('Unhandled message type:', type);
    }
    
    // Call custom message handler if provided
    if (messageHandlerRef.current) {
      messageHandlerRef.current(message);
    }
  }, [dispatch]);

  const connect = useCallback(() => {
    if (!isConnected) {
      websocketService.connect();
    }
  }, [isConnected]);

  const disconnect = useCallback(() => {
    if (isConnected) {
      websocketService.disconnect();
    }
  }, [isConnected]);

  const subscribe = useCallback((topic: string) => {
    if (isConnected) {
      websocketService.subscribe(topic);
    }
  }, [isConnected]);

  const unsubscribe = useCallback((topic: string) => {
    if (isConnected) {
      websocketService.unsubscribe(topic);
    }
  }, [isConnected]);

  const subscribeSymbol = useCallback((symbol: string, timeframe = '1min') => {
    if (isConnected) {
      websocketService.subscribeSymbol(symbol, timeframe);
    }
  }, [isConnected]);

  const unsubscribeSymbol = useCallback((symbol: string) => {
    if (isConnected) {
      websocketService.unsubscribeSymbol(symbol);
    }
  }, [isConnected]);

  const setMessageHandler = useCallback((handler: (data: any) => void) => {
    messageHandlerRef.current = handler;
  }, []);

  useEffect(() => {
    // Set up message handler
    const unsubscribe = store.subscribe(() => {
      const state = store.getState();
      const { lastMessage } = state.websocket;
      if (lastMessage) {
        handleMessage(lastMessage);
      }
    });
    
    return () => {
      unsubscribe();
    };
  }, [handleMessage]);
  
  useEffect(() => {
    // Only auto-connect if not already connected and autoConnect is true
    if (autoConnect && !isConnected) {
      // Small delay to prevent race conditions with WebSocketInitializer
      const timer = setTimeout(() => {
        if (!websocketService.isConnected()) {
          connect();
        }
      }, 100);
      
      return () => clearTimeout(timer);
    }
  }, [autoConnect]); // Remove isConnected from dependencies to prevent loops

  return {
    isConnected,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    subscribeSymbol,
    unsubscribeSymbol,
    setMessageHandler
  };
};

// Hook for subscribing to real-time data for specific symbols
export const useRealtimeData = (symbols: string[]) => {
  const { isConnected, subscribeSymbol, unsubscribeSymbol } = useWebSocket();

  useEffect(() => {
    if (isConnected && symbols.length > 0) {
      symbols.forEach(symbol => subscribeSymbol(symbol));
      
      return () => {
        symbols.forEach(symbol => unsubscribeSymbol(symbol));
      };
    }
  }, [isConnected, symbols, subscribeSymbol, unsubscribeSymbol]);
};

// Hook for subscribing to portfolio updates
export const usePortfolioUpdates = () => {
  const { isConnected, subscribe, unsubscribe } = useWebSocket();

  useEffect(() => {
    if (isConnected) {
      subscribe('portfolio');
      
      return () => {
        unsubscribe('portfolio');
      };
    }
  }, [isConnected, subscribe, unsubscribe]);
};

// Hook for subscribing to strategy updates
export const useStrategyUpdates = (strategyIds: string[]) => {
  const { isConnected, subscribe, unsubscribe } = useWebSocket();

  useEffect(() => {
    if (isConnected && strategyIds.length > 0) {
      strategyIds.forEach(id => subscribe(`strategy:${id}`));
      
      return () => {
        strategyIds.forEach(id => unsubscribe(`strategy:${id}`));
      };
    }
  }, [isConnected, strategyIds, subscribe, unsubscribe]);
};
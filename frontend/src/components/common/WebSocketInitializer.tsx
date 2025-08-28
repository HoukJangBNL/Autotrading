import React, { useEffect } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useAppSelector } from '../../store/hooks';

export const WebSocketInitializer: React.FC = () => {
  const { connect } = useWebSocket({ autoConnect: false });
  const { isAuthenticated } = useAppSelector((state) => state.auth);
  
  useEffect(() => {
    if (isAuthenticated) {
      console.log('User authenticated, initializing WebSocket connection...');
      connect();
    }
  }, [isAuthenticated, connect]);
  
  // This component doesn't render anything
  return null;
};

export default WebSocketInitializer;
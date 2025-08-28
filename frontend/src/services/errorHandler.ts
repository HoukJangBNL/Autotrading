import { isRejectedWithValue } from '@reduxjs/toolkit';
import type { MiddlewareAPI, Middleware } from '@reduxjs/toolkit';
import toastService from './toast';

interface ErrorResponse {
  status?: number;
  data?: {
    message?: string;
    detail?: string;
    errors?: Record<string, string[]>;
  };
  error?: string;
}

class ErrorHandler {
  // Handle API errors
  handleApiError(error: ErrorResponse, endpoint?: string): void {
    const status = error.status;
    const message = error.data?.message || error.data?.detail || error.error || 'An error occurred';
    
    switch (status) {
      case 400:
        this.handleBadRequest(message, error.data?.errors);
        break;
      case 401:
        this.handleUnauthorized();
        break;
      case 403:
        this.handleForbidden();
        break;
      case 404:
        this.handleNotFound(message);
        break;
      case 409:
        this.handleConflict(message);
        break;
      case 422:
        this.handleValidationError(error.data?.errors);
        break;
      case 429:
        this.handleRateLimited();
        break;
      case 500:
      case 502:
      case 503:
      case 504:
        this.handleServerError(message);
        break;
      default:
        toastService.error(message);
    }

    // Log error for debugging
    console.error(`API Error${endpoint ? ` (${endpoint})` : ''}:`, error);
  }

  // Handle WebSocket errors
  handleWebSocketError(error: any): void {
    if (error.code === 1006) {
      toastService.warning('Connection lost. Attempting to reconnect...');
    } else if (error.code === 1011) {
      toastService.error('Server error. Please try again later.');
    } else {
      toastService.error('WebSocket connection error');
    }
    
    console.error('WebSocket Error:', error);
  }

  // Handle trading errors
  handleTradingError(error: any): void {
    const message = error.message || 'Trading operation failed';
    
    if (error.code === 'INSUFFICIENT_FUNDS') {
      toastService.error('Insufficient funds for this order');
    } else if (error.code === 'MARKET_CLOSED') {
      toastService.warning('Market is closed');
    } else if (error.code === 'INVALID_SYMBOL') {
      toastService.error('Invalid symbol');
    } else if (error.code === 'ORDER_REJECTED') {
      toastService.orderRejected(error.symbol, error.reason);
    } else {
      toastService.error(message);
    }
    
    console.error('Trading Error:', error);
  }

  // Handle strategy errors
  handleStrategyError(error: any): void {
    const message = error.message || 'Strategy operation failed';
    
    if (error.code === 'STRATEGY_RUNNING') {
      toastService.warning('Strategy is already running');
    } else if (error.code === 'STRATEGY_STOPPED') {
      toastService.warning('Strategy is not running');
    } else if (error.code === 'INVALID_PARAMETERS') {
      toastService.error('Invalid strategy parameters');
    } else {
      toastService.error(message);
    }
    
    console.error('Strategy Error:', error);
  }

  // Handle backtest errors
  handleBacktestError(error: any): void {
    const message = error.message || 'Backtest operation failed';
    
    if (error.code === 'NO_DATA') {
      toastService.error('No data available for the selected period');
    } else if (error.code === 'INVALID_DATE_RANGE') {
      toastService.error('Invalid date range selected');
    } else if (error.code === 'BACKTEST_RUNNING') {
      toastService.warning('A backtest is already running');
    } else {
      toastService.backtestFailed(error.strategyName, message);
    }
    
    console.error('Backtest Error:', error);
  }

  // Specific error handlers
  private handleBadRequest(message: string, errors?: Record<string, string[]>): void {
    if (errors) {
      const errorMessages = Object.entries(errors)
        .map(([field, messages]) => `${field}: ${messages.join(', ')}`)
        .join('\n');
      toastService.error(errorMessages);
    } else {
      toastService.error(message || 'Invalid request');
    }
  }

  private handleUnauthorized(): void {
    toastService.authExpired();
    // AuthContext will handle redirect to login
  }

  private handleForbidden(): void {
    toastService.error('You do not have permission to perform this action');
  }

  private handleNotFound(message: string): void {
    toastService.error(message || 'Resource not found');
  }

  private handleConflict(message: string): void {
    toastService.error(message || 'Resource conflict');
  }

  private handleValidationError(errors?: Record<string, string[]>): void {
    if (errors) {
      const errorMessages = Object.entries(errors)
        .map(([field, messages]) => `${field}: ${messages.join(', ')}`)
        .join('\n');
      toastService.error(`Validation error:\n${errorMessages}`);
    } else {
      toastService.error('Validation error');
    }
  }

  private handleRateLimited(): void {
    toastService.apiRateLimited();
  }

  private handleServerError(message: string): void {
    toastService.error(message || 'Server error. Please try again later.');
  }

  // Retry logic for failed requests
  async retryWithBackoff<T>(
    fn: () => Promise<T>,
    maxRetries: number = 3,
    baseDelay: number = 1000
  ): Promise<T> {
    let lastError: any;
    
    for (let i = 0; i < maxRetries; i++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;
        
        // Don't retry on client errors
        if (error instanceof Error && 'status' in error) {
          const status = (error as any).status;
          if (status >= 400 && status < 500 && status !== 429) {
            throw error;
          }
        }
        
        // Calculate delay with exponential backoff
        const delay = baseDelay * Math.pow(2, i);
        const jitter = Math.random() * delay * 0.1; // Add 10% jitter
        
        if (i < maxRetries - 1) {
          console.log(`Retry attempt ${i + 1}/${maxRetries} after ${delay}ms`);
          await new Promise(resolve => setTimeout(resolve, delay + jitter));
        }
      }
    }
    
    throw lastError;
  }

  // Create error boundary message
  createErrorBoundaryMessage(error: Error, errorInfo: any): string {
    const message = `
      An unexpected error occurred:
      ${error.message}
      
      Component Stack:
      ${errorInfo.componentStack}
    `;
    
    // Log to console for debugging
    console.error('Error Boundary:', error, errorInfo);
    
    return message;
  }
}

// Redux middleware for error handling
export const errorHandlerMiddleware: Middleware =
  (api: MiddlewareAPI) => (next) => (action) => {
    // Check if this action is a rejected action from RTK Query or createAsyncThunk
    if (isRejectedWithValue(action)) {
      const error = action.payload as ErrorResponse;
      const endpoint = action.meta?.arg?.endpointName || action.type.split('/')[0];
      
      // Handle the error
      errorHandler.handleApiError(error, endpoint);
    }

    return next(action);
  };

// Export singleton instance
export const errorHandler = new ErrorHandler();
export default errorHandler;
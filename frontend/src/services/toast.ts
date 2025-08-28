import { toast, ToastOptions } from 'react-toastify';

// Toast configuration
const defaultOptions: ToastOptions = {
  position: 'bottom-right',
  autoClose: 5000,
  hideProgressBar: false,
  closeOnClick: true,
  pauseOnHover: true,
  draggable: true,
};

class ToastService {
  success(message: string, options?: ToastOptions) {
    return toast.success(message, { ...defaultOptions, ...options });
  }

  error(message: string, options?: ToastOptions) {
    return toast.error(message, { 
      ...defaultOptions, 
      autoClose: false, // Keep error messages visible longer
      ...options 
    });
  }

  warning(message: string, options?: ToastOptions) {
    return toast.warning(message, { ...defaultOptions, ...options });
  }

  info(message: string, options?: ToastOptions) {
    return toast.info(message, { ...defaultOptions, ...options });
  }

  // Trading-specific notifications
  orderPlaced(symbol: string, side: 'BUY' | 'SELL', quantity: number) {
    return this.success(`Order placed: ${side} ${quantity} ${symbol}`);
  }

  orderFilled(symbol: string, side: 'BUY' | 'SELL', quantity: number, price: number) {
    return this.success(
      `Order filled: ${side} ${quantity} ${symbol} @ $${price.toFixed(2)}`
    );
  }

  orderCancelled(symbol: string) {
    return this.info(`Order cancelled: ${symbol}`);
  }

  orderRejected(symbol: string, reason?: string) {
    return this.error(
      `Order rejected: ${symbol}${reason ? ` - ${reason}` : ''}`
    );
  }

  // Strategy notifications
  strategyStarted(name: string) {
    return this.success(`Strategy started: ${name}`);
  }

  strategyStopped(name: string) {
    return this.info(`Strategy stopped: ${name}`);
  }

  strategySignal(strategyName: string, action: string, symbol: string) {
    return this.info(
      `Signal from ${strategyName}: ${action} ${symbol}`,
      { autoClose: 10000 } // Keep signals visible longer
    );
  }

  // WebSocket notifications
  wsConnected() {
    return this.success('Connected to real-time data', { autoClose: 3000 });
  }

  wsDisconnected() {
    return this.warning('Disconnected from real-time data');
  }

  wsReconnecting(attempt: number, maxAttempts: number) {
    return this.info(
      `Reconnecting to real-time data... (${attempt}/${maxAttempts})`
    );
  }

  // Portfolio notifications
  portfolioAlert(message: string, type: 'profit' | 'loss' | 'risk') {
    const toastMethod = type === 'profit' ? this.success : 
                       type === 'loss' ? this.warning : 
                       this.error;
    
    return toastMethod.call(this, message);
  }

  // Risk notifications
  riskAlert(message: string) {
    return this.error(message, {
      autoClose: false,
      style: {
        background: '#ff4444',
        color: 'white',
      },
    });
  }

  maxLossAlert(currentLoss: number, maxLoss: number) {
    return this.riskAlert(
      `⚠️ Daily loss limit approaching: $${currentLoss.toFixed(2)} / $${maxLoss.toFixed(2)}`
    );
  }

  positionSizeAlert(symbol: string, currentSize: number, maxSize: number) {
    return this.warning(
      `Position size limit reached for ${symbol}: ${currentSize} / ${maxSize}`
    );
  }

  // Backtest notifications
  backtestStarted(strategyName: string) {
    return this.info(`Backtest started for ${strategyName}`, {
      autoClose: 3000,
    });
  }

  backtestCompleted(strategyName: string, returnPct: number) {
    const message = `Backtest completed for ${strategyName}: ${returnPct.toFixed(2)}% return`;
    return returnPct >= 0 ? this.success(message) : this.warning(message);
  }

  backtestFailed(strategyName: string, error?: string) {
    return this.error(
      `Backtest failed for ${strategyName}${error ? `: ${error}` : ''}`
    );
  }

  // API notifications
  apiError(endpoint: string, error: string) {
    return this.error(`API Error (${endpoint}): ${error}`);
  }

  apiRateLimited() {
    return this.warning('Rate limited. Please slow down requests.');
  }

  // Authentication notifications
  authSuccess(userName?: string) {
    return this.success(
      `Welcome${userName ? ` back, ${userName}` : ''}!`
    );
  }

  authLogout() {
    return this.info('You have been logged out');
  }

  authExpired() {
    return this.warning('Your session has expired. Please login again.');
  }

  authRefreshed() {
    return this.success('Session refreshed successfully', {
      autoClose: 2000,
    });
  }

  // Custom promise-based toasts
  promise<T>(
    promise: Promise<T>,
    messages: {
      pending: string;
      success: string | ((data: T) => string);
      error: string | ((error: any) => string);
    },
    options?: ToastOptions
  ) {
    return toast.promise(promise, messages, {
      ...defaultOptions,
      ...options,
    });
  }

  // Clear all toasts
  clearAll() {
    toast.dismiss();
  }

  // Clear specific toast
  clear(toastId: string | number) {
    toast.dismiss(toastId);
  }
}

export const toastService = new ToastService();
export default toastService;
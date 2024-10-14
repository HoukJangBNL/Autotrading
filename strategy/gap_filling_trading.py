import numpy as np
import pandas as pd
from strategy.strategy import Strategy

import pandas as pd

from utils.logger_mixin import LoggerMixin

class GapFillingStrategy(LoggerMixin, Strategy):
    def __init__(self, gap_threshold=0.01, volume_threshold=None):
        """
        Initialize the gap filling strategy.
        
        Parameters:
            gap_threshold (float): The minimum gap size to consider a trade (as a percentage of the previous close).
            volume_threshold (float or None): The minimum volume threshold for filtering trades (optional).
        """
        super().__init__()
        
        self.gap_threshold = gap_threshold
        self.volume_threshold = volume_threshold
        self.previous_close = None

    def generate_signal(self, symbol, df):
        """
        Generate a trading signal based on the gap conditions.
        
        Parameters:
            symbol (str): The symbol to generate the signal for.
            df (pd.DataFrame): DataFrame with 'Open', 'Close', and 'Volume' columns.
            
        Returns:
            tuple: A tuple containing the symbol and the trading signal.
        """
        # Ensure the DataFrame has the necessary columns
        if not all(col in df.columns for col in ['Open', 'Close', 'Volume']):
            self.logger.error("DataFrame must contain 'Open', 'Close', and 'Volume' columns.")
            return symbol, 0
        
        # Get today's open, close, and volume
        open_price = df['Open'].iloc[-1]
        close_price = df['Close'].iloc[-1]
        volume = df['Volume'].iloc[-1]
        
        # Calculate the gap
        gap = self.calculate_gap(open_price)
        
        # Determine the signal
        signal = 0
        if self.check_long_condition(gap, volume):
            signal = 1  # Buy signal
        elif self.check_short_condition(gap, volume):
            signal = -1  # Sell signal
        
        # Update previous close price
        self.previous_close = close_price
        
        return symbol, signal
    
    def calculate_gap(self, open_price):
        """
        Calculate the gap size between the previous day's close and today's open.
        
        Parameters:
            open_price (float): Today's open price.
            
        Returns:
            float: The calculated gap size.
        """
        if self.previous_close is None:
            return 0
        return (open_price - self.previous_close) / self.previous_close

    def check_long_condition(self, gap, volume):
        """
        Check if the conditions for a long position are met.
        
        Parameters:
            gap (float): The calculated gap size.
            volume (float): The trading volume.
            
        Returns:
            bool: True if conditions for a long position are met, otherwise False.
        """
        if gap < -self.gap_threshold:  # Downward gap
            if self.volume_threshold is None or volume > self.volume_threshold:
                return True
        return False

    def check_short_condition(self, gap, volume):
        """
        Check if the conditions for a short position are met.
        
        Parameters:
            gap (float): The calculated gap size.
            volume (float): The trading volume.
            
        Returns:
            bool: True if conditions for a short position are met, otherwise False.
        """
        if gap > self.gap_threshold:  # Upward gap
            if self.volume_threshold is None or volume > self.volume_threshold:
                return True
        return False

    def apply(self, data):
        """
        Apply the gap filling strategy to the given data.
        
        Parameters:
            data (pd.DataFrame): DataFrame with 'Open', 'Close', and 'Volume' columns.
            
        Returns:
            pd.DataFrame: DataFrame with trading signals.
        """
        signals = []
        for i, row in data.iterrows():
            signal = self.generate_signal(row['Open'], row['Close'], row['Volume'])
            signals.append(signal)
        
        data['Signal'] = signals
        return data

# Example usage
# Assume you have a DataFrame 'df' with 'Open', 'Close', and 'Volume' columns
df = pd.read_csv('your_data.csv', parse_dates=['Date'], index_col='Date')
strategy = GapFillingStrategy(gap_threshold=0.02, volume_threshold=1000000)
result = strategy.apply_strategy(df)
print(result.tail())

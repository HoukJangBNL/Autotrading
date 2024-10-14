import pandas as pd
import numpy as np
import talib
from strategy import iStrategy
from utils.logger_mixin import LoggerMixin

class SqueezeTradingStrategy(LoggerMixin, iStrategy):
    def __init__(self):
        super().__init__()
        
    def execute(self, data):
        """
        Execute the squeeze trading strategy.

        Parameters:
        data (list or dict): Raw trading data.

        Returns:
        pd.DataFrame: DataFrame containing trading data with added columns for indicators, signals, and position size.
        """

        df = self.preprocess_data(data)
        df = self.calculate_indicators(df)
        df = self.check_squeeze(df)
        df = self.generate_signals(df)
        df = self.determine_position_size(df)
        return df
        
    def preprocess_data(self, data):
        """
        Convert raw data to a pandas DataFrame and ensure it is sorted by time.

        Parameters:
        data (list or dict): Raw trading data.

        Returns:
        pd.DataFrame: Preprocessed data sorted by time.
        """
        df = pd.DataFrame(data)
        df.sort_values(by='time', inplace=True)
        return df

    def calculate_indicators(self, df):
        """
        Calculate Bollinger Bands and Keltner Channel indicators.

        Parameters:
        df (pd.DataFrame): DataFrame containing trading data with 'close', 'high', and 'low' prices.

        Returns:
        pd.DataFrame: DataFrame with added Bollinger Bands and Keltner Channel columns.
        """
        df['upper_band'], df['middle_band'], df['lower_band'] = talib.BBANDS(df['close'], timeperiod=20)
        df['keltner_upper'] = df['high'].rolling(window=20).mean() + 2 * df['high'].rolling(window=20).std()
        df['keltner_lower'] = df['low'].rolling(window=20).mean() - 2 * df['low'].rolling(window=20).std()
        return df

    def check_squeeze(self, df):
        """
        Check for the squeeze condition where Bollinger Bands are within the Keltner Channel.

        Parameters:
        df (pd.DataFrame): DataFrame containing trading data with Bollinger Bands and Keltner Channel columns.

        Returns:
        pd.DataFrame: DataFrame with an added 'squeeze_on' column indicating the squeeze condition.
        """
        df['squeeze_on'] = (df['lower_band'] > df['keltner_lower']) & (df['upper_band'] < df['keltner_upper'])
        return df

    def generate_signals(self, df):
        """
        Generate buy/hold signals based on the squeeze condition.

        Parameters:
        df (pd.DataFrame): DataFrame containing trading data with the 'squeeze_on' column.

        Returns:
        pd.DataFrame: DataFrame with an added 'signal' column indicating buy or hold signals.
        """
        df['signal'] = np.where(df['squeeze_on'], 'buy', 'hold')
        return df

    def determine_position_size(self, df):
        """
        Determine the position size based on the generated signals.

        Parameters:
        df (pd.DataFrame): DataFrame containing trading data with the 'signal' column.

        Returns:
        pd.DataFrame: DataFrame with an added 'position_size' column indicating the number of stocks to buy.
        """
        df['position_size'] = np.where(df['signal'] == 'buy', 100, 0)  # Example: buy 100 stocks if signal is 'buy'
        return df
    


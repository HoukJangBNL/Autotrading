import threading
import time

from utils.logger_mixin import LoggerMixin


class DataAnalyzer(LoggerMixin):
    def __init__(self, strategy, trader):
        super().__init__()
        
        self.strategy = strategy
        self.trader = trader
        self.data = []

    def analyze_data(self, new_data):
        """DataFetcher로부터 호출되는 콜백 함수"""
        self.data.append(new_data)
        if len(self.data) >= 2:
            signal = self.strategy.generate_signal(self.data)
            if signal and signal != 'hold':
                self.trader.execute_trade(signal, 'AAPL', 10)

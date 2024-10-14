

from utils.logger_mixin import LoggerMixin
from utils.order import Order


class Trader(LoggerMixin):
    def __init__(self, broker_api):
        super().__init__()
        self.broker_api = broker_api

        self.strategies = []
        self.symbols = []

    def add_strategy(self, strategy):
        self.strategies.append(strategy)

    def remove_strategy(self, strategy):
        self.strategies.remove(strategy)
        
    def receive_data(self, data):
        for strategy in self.strategies:
            signal = strategy.generate_signal(data)
            if signal and signal != 'hold':
                order = Order('market', 'AAPL', 10, signal)
                self.broker_api.execute(order)

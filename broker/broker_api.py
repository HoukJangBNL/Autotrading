
from utils.logger_mixin import LoggerMixin
from utils.order import Order


class BrokerAPI(LoggerMixin):
    def __init__(self):
        super().__init__()

    def execute(self, order:Order):
        if order.type == 'market':
            self.execute_market_order(order.symbol, order.quantity, order.side)
        elif order.type == 'limit':
            self.execute_limit_order(order.symbol, order.quantity, order.side, order.price)
        elif order.type == 'stop':
            self.execute_stop_order(order.symbol, order.quantity, order.side, order.price)
        else:
            raise ValueError(f"Invalid order type: {order.type}")

        self.logger.info(f"Executed order: {order.side.value} {order.quantity} shares of {order.symbol} at {order.price} ({order.type})")
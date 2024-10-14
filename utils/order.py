from dataclasses import dataclass
from enum import Enum

class OrderType(Enum):
    MARKET = 'market'
    LIMIT = 'limit'
    STOP = 'stop'

class Action(Enum):
    BUY = 'buy'
    SELL = 'sell'

@dataclass
class Order:
    side: Action     # 거래 방향 ('buy' 또는 'sell')
    symbol: str        # 주식 종목 (예: 'AAPL')
    quantity: int      # 거래할 주식 수량
    type: OrderType    # 주문 종류 ('market', 'limit', 'stop' 등)
    price: float = None  # 지정가 주문일 경우 가격 (optional)
    time_in_force: str = 'GTC'  # 주문 유효 기간 ('Day', 'GTC' 등)

    def __post_init__(self):
        # 지정가 또는 정지 주문일 경우 가격이 없으면 에러
        if self.type in ['limit', 'stop'] and self.price is None:
            raise ValueError(f"{self.type} order must have a price.")
        if self.type == 'market' and self.price is not None:
            raise ValueError("Market order should not have a price.")
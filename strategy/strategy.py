# strategy/strategy.py

from abc import abstractmethod
from utils.order import Order


class Strategy:
    def __init__(self, symbols):
        self.symbols = symbols            # 거래할 심볼 리스트
        self.positions = {symbol: 0 for symbol in symbols}  # 심볼별 포지션

    def process_data(self, data):
        """
        데이터를 받아 거래 로직을 실행하여 주문을 생성합니다.
        :param data: 심볼별 데이터 딕셔너리
        :return: 주문 리스트
        """
        orders = []

        for symbol in self.symbols:
            df = data.get(symbol)
            if df is None:
                continue

            # 시그널 및 수량 생성
            signal, quantity = self.generate_signal(symbol, df)

            if signal and quantity > 0:
                # 주문 생성
                order = Order(
                    symbol=symbol,
                    quantity=quantity,
                    order_type='market',
                    side=signal
                )
                # 포지션 업데이트
                self.update_position(symbol, signal, quantity)
                orders.append(order)

        return orders

    @abstractmethod
    def generate_signal(self, symbol, df):
        """
        데이터 분석을 통해 거래 시그널과 수량을 생성합니다.
        :param symbol: 심볼
        :param df: 해당 심볼의 데이터 프레임
        :return: (signal, quantity)
        """
        # 예시: 가격과 거래량을 기반으로 시그널과 수량 결정
        price = df['price'].iloc[-1]
        volume = df['volume'].iloc[-1]

        # 간단한 전략: 가격이 100보다 크고 거래량이 많을 때 매수
        if price > 100 and volume > 3000 and self.positions[symbol] <= 0:
            quantity = int(volume * 0.01)  # 거래량의 1% 매수
            return 'buy', quantity
        # 가격이 90보다 작고 거래량이 많을 때 매도
        elif price < 90 and volume > 3000 and self.positions[symbol] >= 0:
            quantity = int(volume * 0.01)  # 거래량의 1% 매도
            return 'sell', quantity
        else:
            return None, 0

    def update_position(self, symbol, signal, quantity):
        """
        포지션을 업데이트합니다.
        :param symbol: 심볼
        :param signal: 'buy' 또는 'sell'
        :param quantity: 거래 수량
        """
        if signal == 'buy':
            self.positions[symbol] += quantity
        elif signal == 'sell':
            self.positions[symbol] -= quantity

import threading
import time
import random

class DataFetcher(LoggerMixin):
    def __init__(self):
        super().__init__()
        self.data = []
        self.is_running = False
        self.callbacks = []  # 콜백 함수 리스트 추가

    def register_callback(self, callback):
        """콜백 함수를 등록합니다."""
        self.callbacks.append(callback)

    def fetch_data(self):
        while self.is_running:
            new_price = self.get_market_data()
            self.data.append(new_price)
            for callback in self.callbacks:
                try:
                    callback(new_price)
                except Exception as e:
                    print(f"콜백 함수 실행 중 예외 발생: {e}")
            time.sleep(1)

    def get_market_data(self):
        # 실제로는 API 호출을 통해 데이터를 수집합니다.
        return {'price': random.uniform(90, 110)}  # 예시로 랜덤 가격 생성

    def start(self):
        self.is_running = True
        threading.Thread(target=self.fetch_data, daemon=True).start()

    def stop(self):
        self.is_running = False

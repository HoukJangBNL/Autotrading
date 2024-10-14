from broker import BrokerAPI
from trader import Trader
from data import DataFetcher
from data import DataAnalyzer
from strategy import Strategy
import time

def main():
    broker_api = BrokerAPI()
    trader = Trader(broker_api)
    data_fetcher = DataFetcher()
    strategy = Strategy()
    data_analyzer = DataAnalyzer(strategy, trader)

    # DataAnalyzer를 DataFetcher의 콜백 함수로 등록
    data_fetcher.register_callback(data_analyzer.analyze_data)

    # 데이터 수집 시작
    data_fetcher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # 시스템 종료
        data_fetcher.stop()
        print("시스템을 종료합니다.")

if __name__ == "__main__":
    main()

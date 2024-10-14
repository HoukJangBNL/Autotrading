
import logging
import logging.handlers
import os

class LoggerManager:
    _instance = None

    def __new__(cls, log_file='app.log', log_level=logging.INFO):
        if cls._instance is None:
            cls._instance = super(LoggerManager, cls).__new__(cls)
            cls._instance._initialize(log_file, log_level)
        return cls._instance

    def _initialize(self, log_file, log_level):
        # 로그 디렉토리 생성
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 로거 생성
        self.logger = logging.getLogger('AutoTrading')
        self.logger.setLevel(log_level)

        # 포매터 설정
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # 스트림 핸들러 (콘솔 출력)
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(stream_handler)

        # 파일 핸들러
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def get_logger(self):
        return self.logger

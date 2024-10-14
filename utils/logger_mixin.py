from utils.logger_manager import LoggerManager


class LoggerMixin:
    def __init__(self, *args, **kwargs):
        self.logger = LoggerManager.get_logger()
        super().__init__(*args, **kwargs)
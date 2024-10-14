from utils.logger_manager import LoggerManager

class BaseClass:
    def __init__(self):
        self.logger = LoggerManager.get_logger()
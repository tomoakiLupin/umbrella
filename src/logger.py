import logging
import os
from datetime import datetime
from typing import Optional

class Logger:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger('discord_bot')
        self.setup_logger()
    
    def setup_logger(self):
        self.logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        formatter = logging.Formatter(self.config.log_format)
        
        # Console handler
        if self.config.log_console_enabled:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # File handler
        if self.config.log_file_enabled:
            if not os.path.exists('logs'):
                os.makedirs('logs')
            
            log_filename = f"logs/bot_{datetime.now().strftime('%Y%m%d')}.log"
            file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def get_logger(self):
        return self.logger
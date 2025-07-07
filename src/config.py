import configparser
import os
from typing import Optional

class Config:
    def __init__(self, config_file: str = "config.ini"):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.load_config()
    
    def load_config(self):
        if not os.path.exists(self.config_file):
            print(f"配置文件 {self.config_file} 不存在，正在创建默认配置文件...")
            self.create_default_config()
        
        self.config.read(self.config_file, encoding='utf-8')
        
        # Validate required sections
        required_sections = ['bot', 'logging', 'admin']
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required section: {section}")
    
    def create_default_config(self):
        """创建默认配置文件"""
        default_config = """[bot]
# 请将此处替换为您的Discord机器人令牌
token=YOUR_BOT_TOKEN_HERE
prefix=!
description=Discord Bot Framework
activity_type=playing
activity_name=with Discord.py

[logging]
level=INFO
format=%%(asctime)s [%%(levelname)s] %%(name)s: %%(message)s
file_enabled=true
console_enabled=true

[admin]
# 请将此处替换为超级管理员的Discord用户ID
super_admin_id=123456789012345678
"""
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write(default_config)
            print(f"✅ 默认配置文件已创建：{self.config_file}")
            print("⚠️  请编辑配置文件，设置您的机器人令牌和超级管理员ID后重新运行程序")
            input("按回车键退出...")
            exit(1)
        except Exception as e:
            raise RuntimeError(f"Failed to create default config file: {e}")
    
    @property
    def bot_token(self) -> str:
        return self.config.get('bot', 'token')
    
    @property
    def bot_prefix(self) -> str:
        return self.config.get('bot', 'prefix', fallback='!')
    
    @property
    def bot_description(self) -> str:
        return self.config.get('bot', 'description', fallback='Discord Bot')
    
    @property
    def activity_type(self) -> str:
        return self.config.get('bot', 'activity_type', fallback='playing')
    
    @property
    def activity_name(self) -> str:
        return self.config.get('bot', 'activity_name', fallback='with Discord.py')
    
    @property
    def log_level(self) -> str:
        return self.config.get('logging', 'level', fallback='INFO')
    
    @property
    def log_format(self) -> str:
        format_str = self.config.get('logging', 'format', fallback='%%(asctime)s [%%(levelname)s] %%(name)s: %%(message)s')
        # 将双百分号转换为单百分号用于logging格式
        return format_str.replace('%%', '%')
    
    @property
    def log_file_enabled(self) -> bool:
        return self.config.getboolean('logging', 'file_enabled', fallback=True)
    
    @property
    def log_console_enabled(self) -> bool:
        return self.config.getboolean('logging', 'console_enabled', fallback=True)
    
    @property
    def super_admin_id(self) -> int:
        return self.config.getint('admin', 'super_admin_id')
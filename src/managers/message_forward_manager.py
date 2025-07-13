import sqlite3
import discord
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import json

class MessageForwardManager:
    def __init__(self, config, logger_manager):
        self.config = config
        self.logger = logger_manager.get_logger()
        self.db_path = "owner_channel.db"
        self.init_database()
    
    def init_database(self):
        """初始化消息转发相关的数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 消息转发配置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_forwards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_guild_id INTEGER,
                    source_channel_id INTEGER NOT NULL,
                    target_guild_id INTEGER,
                    target_channel_id INTEGER NOT NULL,
                    created_by INTEGER NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_channel_id, target_channel_id)
                )
            ''')
            
            conn.commit()
    
    def add_forward_rule(self, source_channel_id: int, target_channel_id: int, 
                        source_guild_id: Optional[int], target_guild_id: Optional[int], 
                        created_by: int) -> bool:
        """添加消息转发规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO message_forwards 
                    (source_channel_id, target_channel_id, source_guild_id, target_guild_id, created_by)
                    VALUES (?, ?, ?, ?, ?)
                ''', (source_channel_id, target_channel_id, source_guild_id, target_guild_id, created_by))
                conn.commit()
                
                self.logger.info(f"用户 {created_by} 添加了消息转发规则：{source_channel_id} -> {target_channel_id}")
                return True
        except sqlite3.IntegrityError:
            # 规则已存在
            return False
        except Exception as e:
            self.logger.error(f"添加转发规则时发生错误：{e}")
            return False
    
    def remove_forward_rule(self, source_channel_id: int, target_channel_id: int, user_id: int) -> bool:
        """移除消息转发规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM message_forwards 
                    WHERE source_channel_id = ? AND target_channel_id = ? AND created_by = ?
                ''', (source_channel_id, target_channel_id, user_id))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    self.logger.info(f"用户 {user_id} 移除了消息转发规则：{source_channel_id} -> {target_channel_id}")
                    return True
                return False
        except Exception as e:
            self.logger.error(f"移除转发规则时发生错误：{e}")
            return False
    
    def get_forward_targets(self, source_channel_id: int) -> List[Tuple[int, int, int]]:
        """获取指定源频道的所有转发目标频道"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT target_channel_id, target_guild_id, id
                    FROM message_forwards 
                    WHERE source_channel_id = ? AND is_active = 1
                ''', (source_channel_id,))
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"获取转发目标时发生错误：{e}")
            return []
    
    def get_user_forward_rules(self, user_id: int) -> List[Dict]:
        """获取用户创建的所有转发规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM message_forwards 
                    WHERE created_by = ? AND is_active = 1
                    ORDER BY created_at DESC
                ''', (user_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"获取用户转发规则时发生错误：{e}")
            return []
    
    def toggle_forward_rule(self, rule_id: int, user_id: int, active: bool) -> bool:
        """启用或禁用转发规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE message_forwards 
                    SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND created_by = ?
                ''', (1 if active else 0, rule_id, user_id))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    status = "启用" if active else "禁用"
                    self.logger.info(f"用户 {user_id} {status}了转发规则 {rule_id}")
                    return True
                return False
        except Exception as e:
            self.logger.error(f"切换转发规则状态时发生错误：{e}")
            return False
    
    def is_valid_channel(self, bot: discord.Client, channel_id: int) -> Tuple[bool, Optional[discord.TextChannel]]:
        """验证频道是否存在且机器人有权限"""
        try:
            channel = bot.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return False, None
            
            # 检查机器人是否有发送消息的权限
            permissions = channel.permissions_for(channel.guild.me)
            if not permissions.send_messages:
                return False, None
                
            return True, channel
        except Exception:
            return False, None
    
    def can_access_channel(self, channel: discord.TextChannel, user: discord.Member) -> bool:
        """检查用户是否能访问指定频道"""
        try:
            permissions = channel.permissions_for(user)
            return permissions.read_messages and permissions.send_messages
        except Exception:
            return False
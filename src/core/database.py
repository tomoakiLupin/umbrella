import sqlite3
import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import discord

class DatabaseManager:
    def __init__(self, db_path: str = "owner_channel.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库，创建所有必要的表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 面板配置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS panel_configs (
                    guild_id INTEGER PRIMARY KEY,
                    panel_channel_id INTEGER NOT NULL,
                    owner_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    archive_channel_id INTEGER NOT NULL,
                    review_channel_id INTEGER NOT NULL,
                    allowed_roles TEXT,  -- JSON存储角色ID列表
                    allowed_days INTEGER DEFAULT 0,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 服主通道表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS owner_channels (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    complaint_content TEXT NOT NULL,
                    channel_number INTEGER NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    archived_at TIMESTAMP NULL
                )
            ''')
            
            # 通道计数器表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channel_counters (
                    guild_id INTEGER PRIMARY KEY,
                    counter INTEGER DEFAULT 0
                )
            ''')
            
            # 黑名单表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    added_by INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, user_id)
                )
            ''')
            
            # 待审核请求表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pending_requests (
                    request_id TEXT PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    complaint_content TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 管理员角色表（从admin_data.json迁移）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    added_by INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, role_id)
                )
            ''')
            
            conn.commit()
    
    def migrate_from_json(self):
        """从JSON文件迁移数据到SQLite数据库"""
        # 迁移owner_channel_data.json
        owner_data_file = "owner_channel_data.json"
        if os.path.exists(owner_data_file):
            try:
                with open(owner_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # 迁移面板配置
                    if 'panels' in data:
                        for guild_id_str, panel_config in data['panels'].items():
                            guild_id = int(guild_id_str)
                            cursor.execute('''
                                INSERT OR REPLACE INTO panel_configs 
                                (guild_id, panel_channel_id, owner_id, category_id, archive_channel_id, 
                                 review_channel_id, allowed_roles, allowed_days, created_by, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                guild_id,
                                panel_config.get('panel_channel_id'),
                                panel_config.get('owner_id'),
                                panel_config.get('category_id'),
                                panel_config.get('archive_channel_id'),
                                panel_config.get('review_channel_id'),
                                json.dumps(panel_config.get('allowed_roles', [])),
                                panel_config.get('allowed_days', 0),
                                panel_config.get('created_by'),
                                panel_config.get('created_at')
                            ))
                    
                    # 迁移通道信息
                    if 'channels' in data:
                        for channel_id_str, channel_info in data['channels'].items():
                            channel_id = int(channel_id_str)
                            cursor.execute('''
                                INSERT OR REPLACE INTO owner_channels 
                                (channel_id, guild_id, user_id, complaint_content, channel_number, status, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                channel_id,
                                channel_info.get('guild_id'),
                                channel_info.get('user_id'),
                                channel_info.get('complaint_content'),
                                channel_info.get('channel_number'),
                                channel_info.get('status', 'active'),
                                channel_info.get('created_at')
                            ))
                    
                    # 迁移计数器
                    if 'counter' in data:
                        for guild_id_str, counter in data['counter'].items():
                            guild_id = int(guild_id_str)
                            cursor.execute('''
                                INSERT OR REPLACE INTO channel_counters (guild_id, counter)
                                VALUES (?, ?)
                            ''', (guild_id, counter))
                    
                    # 迁移黑名单
                    if 'blacklist' in data:
                        for guild_id_str, user_ids in data['blacklist'].items():
                            guild_id = int(guild_id_str)
                            for user_id in user_ids:
                                cursor.execute('''
                                    INSERT OR IGNORE INTO blacklist (guild_id, user_id, added_by)
                                    VALUES (?, ?, ?)
                                ''', (guild_id, user_id, 0))  # 0表示系统迁移
                    
                    # 迁移待审核请求
                    if 'pending_requests' in data:
                        for request_id, request_info in data['pending_requests'].items():
                            cursor.execute('''
                                INSERT OR REPLACE INTO pending_requests 
                                (request_id, guild_id, user_id, complaint_content, status, created_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (
                                request_id,
                                request_info.get('guild_id'),
                                request_info.get('user_id'),
                                request_info.get('complaint_content'),
                                request_info.get('status', 'pending'),
                                request_info.get('created_at')
                            ))
                    
                    conn.commit()
                
                # 备份并删除JSON文件
                backup_name = f"{owner_data_file}.backup"
                os.rename(owner_data_file, backup_name)
                print(f"已将 {owner_data_file} 备份为 {backup_name}")
                
            except Exception as e:
                print(f"迁移owner_channel_data.json时发生错误：{e}")
        
        # 迁移admin_data.json
        admin_data_file = "admin_data.json"
        if os.path.exists(admin_data_file):
            try:
                with open(admin_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # 迁移管理员角色
                    if 'admin_roles' in data:
                        for role_id in data['admin_roles']:
                            cursor.execute('''
                                INSERT OR IGNORE INTO admin_roles (guild_id, role_id, added_by)
                                VALUES (?, ?, ?)
                            ''', (0, role_id, 0))  # 使用guild_id=0表示全局角色
                    
                    conn.commit()
                
                # 备份并删除JSON文件
                backup_name = f"{admin_data_file}.backup"
                os.rename(admin_data_file, backup_name)
                print(f"已将 {admin_data_file} 备份为 {backup_name}")
                
            except Exception as e:
                print(f"迁移admin_data.json时发生错误：{e}")
    
    def execute_query(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """执行查询并返回结果"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """执行更新操作并返回受影响的行数"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
    
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """执行插入操作并返回新插入行的ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
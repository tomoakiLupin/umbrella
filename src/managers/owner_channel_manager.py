import json
import os
from typing import Dict, List, Optional, Tuple
import discord
from ..core.database import DatabaseManager

class OwnerChannelManager:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_logger()
        self.db = DatabaseManager()
        # 运行迁移（如果有JSON文件的话）
        self.db.migrate_from_json()
    
    
    def create_panel_config(self, guild_id: int, panel_channel_id: int, owner_id: int, 
                           category_id: int, archive_channel_id: int, review_channel_id: int,
                           allowed_roles: List[int], allowed_days: int, requester_id: int) -> bool:
        """创建面板配置"""
        try:
            # 检查是否已经存在面板配置
            existing = self.db.execute_query(
                "SELECT guild_id FROM panel_configs WHERE guild_id = ?", (guild_id,)
            )
            if existing:
                return False
                
            self.db.execute_insert(
                """INSERT INTO panel_configs 
                   (guild_id, panel_channel_id, owner_id, category_id, archive_channel_id, 
                    review_channel_id, allowed_roles, allowed_days, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (guild_id, panel_channel_id, owner_id, category_id, archive_channel_id,
                 review_channel_id, json.dumps(allowed_roles), allowed_days, requester_id)
            )
            
            # 初始化计数器
            self.db.execute_insert(
                "INSERT OR IGNORE INTO channel_counters (guild_id, counter) VALUES (?, ?)",
                (guild_id, 0)
            )
                
            self.logger.info(f"Created panel config for guild {guild_id} by user {requester_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating panel config: {e}")
            return False
    
    def get_panel_config(self, guild_id: int) -> Optional[dict]:
        """获取面板配置"""
        try:
            result = self.db.execute_query(
                "SELECT * FROM panel_configs WHERE guild_id = ?", (guild_id,)
            )
            if result:
                row = result[0]
                return {
                    "panel_channel_id": row["panel_channel_id"],
                    "owner_id": row["owner_id"],
                    "category_id": row["category_id"],
                    "archive_channel_id": row["archive_channel_id"],
                    "review_channel_id": row["review_channel_id"],
                    "allowed_roles": json.loads(row["allowed_roles"]) if row["allowed_roles"] else [],
                    "allowed_days": row["allowed_days"],
                    "created_by": row["created_by"],
                    "created_at": row["created_at"]
                }
            return None
        except Exception as e:
            self.logger.error(f"Error getting panel config: {e}")
            return None
    
    def update_panel_config(self, guild_id: int, **kwargs) -> bool:
        """更新面板配置"""
        try:
            # 构建UPDATE语句
            allowed_fields = ["panel_channel_id", "owner_id", "category_id", "archive_channel_id", 
                            "review_channel_id", "allowed_roles", "allowed_days"]
            
            updates = []
            values = []
            
            for key, value in kwargs.items():
                if key in allowed_fields:
                    updates.append(f"{key} = ?")
                    if key == "allowed_roles":
                        values.append(json.dumps(value))
                    else:
                        values.append(value)
            
            if not updates:
                return False
                
            values.append(guild_id)
            
            rows_updated = self.db.execute_update(
                f"UPDATE panel_configs SET {', '.join(updates)} WHERE guild_id = ?",
                tuple(values)
            )
            
            if rows_updated > 0:
                self.logger.info(f"Updated panel config for guild {guild_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error updating panel config: {e}")
            return False
    
    def delete_panel_config(self, guild_id: int) -> bool:
        """删除面板配置"""
        try:
            rows_deleted = self.db.execute_update(
                "DELETE FROM panel_configs WHERE guild_id = ?", (guild_id,)
            )
            
            if rows_deleted > 0:
                self.logger.info(f"Deleted panel config for guild {guild_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting panel config: {e}")
            return False
    
    def get_next_channel_number(self, guild_id: int) -> int:
        """获取下一个通道编号"""
        try:
            # 确保计数器存在
            self.db.execute_insert(
                "INSERT OR IGNORE INTO channel_counters (guild_id, counter) VALUES (?, ?)",
                (guild_id, 0)
            )
            
            # 增加计数器
            self.db.execute_update(
                "UPDATE channel_counters SET counter = counter + 1 WHERE guild_id = ?",
                (guild_id,)
            )
            
            # 获取新值
            result = self.db.execute_query(
                "SELECT counter FROM channel_counters WHERE guild_id = ?", (guild_id,)
            )
            
            return result[0]["counter"] if result else 1
            
        except Exception as e:
            self.logger.error(f"Error getting next channel number: {e}")
            return 1
    
    def create_owner_channel(self, channel_id: int, guild_id: int, user_id: int, 
                           complaint_content: str, channel_number: int) -> bool:
        """创建服主通道记录"""
        try:
            self.db.execute_insert(
                """INSERT INTO owner_channels 
                   (channel_id, guild_id, user_id, complaint_content, channel_number, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (channel_id, guild_id, user_id, complaint_content, channel_number, "active")
            )
            
            self.logger.info(f"Created owner channel record for channel {channel_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating owner channel record: {e}")
            return False
    
    def get_owner_channel_info(self, channel_id: int) -> Optional[dict]:
        """获取服主通道信息"""
        try:
            result = self.db.execute_query(
                "SELECT * FROM owner_channels WHERE channel_id = ?", (channel_id,)
            )
            if result:
                row = result[0]
                return {
                    "channel_id": row["channel_id"],
                    "guild_id": row["guild_id"],
                    "user_id": row["user_id"],
                    "complaint_content": row["complaint_content"],
                    "channel_number": row["channel_number"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "archived_at": row["archived_at"]
                }
            return None
        except Exception as e:
            self.logger.error(f"Error getting owner channel info: {e}")
            return None
    
    def is_owner_channel(self, channel_name: str) -> bool:
        """检查是否是服主通道（通过频道名称）"""
        return channel_name.startswith("服主通道-")
    
    def archive_owner_channel(self, channel_id: int) -> bool:
        """归档服主通道"""
        try:
            rows_updated = self.db.execute_update(
                "UPDATE owner_channels SET status = ?, archived_at = CURRENT_TIMESTAMP WHERE channel_id = ?",
                ("archived", channel_id)
            )
            
            if rows_updated > 0:
                self.logger.info(f"Archived owner channel {channel_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error archiving owner channel: {e}")
            return False
    
    def delete_owner_channel_record(self, channel_id: int) -> bool:
        """删除服主通道记录"""
        try:
            rows_deleted = self.db.execute_update(
                "DELETE FROM owner_channels WHERE channel_id = ?", (channel_id,)
            )
            
            if rows_deleted > 0:
                self.logger.info(f"Deleted owner channel record {channel_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting owner channel record: {e}")
            return False
    
    def get_active_channels_by_guild(self, guild_id: int) -> List[dict]:
        """获取指定服务器的所有活跃服主通道"""
        try:
            result = self.db.execute_query(
                "SELECT * FROM owner_channels WHERE guild_id = ? AND status = ?",
                (guild_id, "active")
            )
            
            active_channels = []
            for row in result:
                active_channels.append({
                    "channel_id": row["channel_id"],
                    "guild_id": row["guild_id"],
                    "user_id": row["user_id"],
                    "complaint_content": row["complaint_content"],
                    "channel_number": row["channel_number"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "archived_at": row["archived_at"]
                })
            
            return active_channels
            
        except Exception as e:
            self.logger.error(f"Error getting active channels: {e}")
            return []
    
    def get_all_panels(self) -> Dict[str, dict]:
        """获取所有面板配置"""
        try:
            result = self.db.execute_query("SELECT * FROM panel_configs")
            panels = {}
            
            for row in result:
                guild_id_str = str(row["guild_id"])
                panels[guild_id_str] = {
                    "panel_channel_id": row["panel_channel_id"],
                    "owner_id": row["owner_id"],
                    "category_id": row["category_id"],
                    "archive_channel_id": row["archive_channel_id"],
                    "review_channel_id": row["review_channel_id"],
                    "allowed_roles": json.loads(row["allowed_roles"]) if row["allowed_roles"] else [],
                    "allowed_days": row["allowed_days"],
                    "created_by": row["created_by"],
                    "created_at": row["created_at"]
                }
            
            return panels
            
        except Exception as e:
            self.logger.error(f"Error getting all panels: {e}")
            return {}
    
    def add_to_blacklist(self, guild_id: int, user_id: int, added_by: int = 0) -> bool:
        """将用户添加到黑名单"""
        try:
            rows_inserted = self.db.execute_insert(
                "INSERT OR IGNORE INTO blacklist (guild_id, user_id, added_by) VALUES (?, ?, ?)",
                (guild_id, user_id, added_by)
            )
            
            if rows_inserted:
                self.logger.info(f"Added user {user_id} to blacklist in guild {guild_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error adding user to blacklist: {e}")
            return False
    
    def remove_from_blacklist(self, guild_id: int, user_id: int) -> bool:
        """从黑名单中移除用户"""
        try:
            rows_deleted = self.db.execute_update(
                "DELETE FROM blacklist WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            
            if rows_deleted > 0:
                self.logger.info(f"Removed user {user_id} from blacklist in guild {guild_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error removing user from blacklist: {e}")
            return False
    
    def get_blacklist(self, guild_id: int) -> List[int]:
        """获取指定服务器的黑名单"""
        try:
            result = self.db.execute_query(
                "SELECT user_id FROM blacklist WHERE guild_id = ?", (guild_id,)
            )
            return [row["user_id"] for row in result]
            
        except Exception as e:
            self.logger.error(f"Error getting blacklist: {e}")
            return []
    
    def has_pending_request(self, guild_id: int, user_id: int) -> bool:
        """检查用户是否有正在进行中的申请"""
        try:
            result = self.db.execute_query(
                "SELECT request_id FROM pending_requests WHERE guild_id = ? AND user_id = ? AND status = ?",
                (guild_id, user_id, "pending")
            )
            return len(result) > 0
            
        except Exception as e:
            self.logger.error(f"Error checking pending request: {e}")
            return False
    
    def is_blacklisted(self, guild_id: int, user_id: int) -> bool:
        """检查用户是否在黑名单中"""
        try:
            result = self.db.execute_query(
                "SELECT user_id FROM blacklist WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            return len(result) > 0
            
        except Exception as e:
            self.logger.error(f"Error checking blacklist: {e}")
            return False
    
    def check_user_eligibility(self, guild_id: int, user_id: int, user_roles: List[int], 
                              join_date) -> Tuple[bool, str]:
        """检查用户是否符合发起通道的条件"""
        panel_config = self.get_panel_config(guild_id)
        if not panel_config:
            return False, "未配置服主通道面板"
        
        # 检查黑名单
        if self.is_blacklisted(guild_id, user_id):
            return False, "blacklisted"
        
        # 检查身份组要求
        allowed_roles = panel_config.get("allowed_roles", [])
        if allowed_roles:  # 如果设置了身份组限制
            if not any(role_id in allowed_roles for role_id in user_roles):
                return False, "身份组不符合要求"
        
        # 检查加入时间要求
        allowed_days = panel_config.get("allowed_days", 0)
        if allowed_days > 0:
            days_since_join = (discord.utils.utcnow() - join_date).days
            if days_since_join < allowed_days:
                return False, f"需要加入服务器 {allowed_days} 天后才能使用此功能"
        
        # 检查是否有正在进行中的申请
        if self.has_pending_request(guild_id, user_id):
            return False, "您已有正在审核中的申请，请等待审核完成"
        
        return True, "符合条件"
    
    def create_pending_request(self, guild_id: int, user_id: int, complaint_content: str) -> str:
        """创建待审核请求"""
        try:
            import uuid
            request_id = str(uuid.uuid4())
            
            self.db.execute_insert(
                """INSERT INTO pending_requests 
                   (request_id, guild_id, user_id, complaint_content, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (request_id, guild_id, user_id, complaint_content, "pending")
            )
            
            self.logger.info(f"Created pending request {request_id} for user {user_id} in guild {guild_id}")
            return request_id
            
        except Exception as e:
            self.logger.error(f"Error creating pending request: {e}")
            return ""
    
    def get_pending_request(self, request_id: str) -> Optional[dict]:
        """获取待审核请求"""
        try:
            result = self.db.execute_query(
                "SELECT * FROM pending_requests WHERE request_id = ?", (request_id,)
            )
            if result:
                row = result[0]
                return {
                    "request_id": row["request_id"],
                    "guild_id": row["guild_id"],
                    "user_id": row["user_id"],
                    "complaint_content": row["complaint_content"],
                    "status": row["status"],
                    "created_at": row["created_at"]
                }
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting pending request: {e}")
            return None
    
    def update_request_status(self, request_id: str, status: str) -> bool:
        """更新请求状态"""
        try:
            rows_updated = self.db.execute_update(
                "UPDATE pending_requests SET status = ? WHERE request_id = ?",
                (status, request_id)
            )
            return rows_updated > 0
            
        except Exception as e:
            self.logger.error(f"Error updating request status: {e}")
            return False
    
    def delete_pending_request(self, request_id: str) -> bool:
        """删除待审核请求"""
        try:
            rows_deleted = self.db.execute_update(
                "DELETE FROM pending_requests WHERE request_id = ?", (request_id,)
            )
            return rows_deleted > 0
            
        except Exception as e:
            self.logger.error(f"Error deleting pending request: {e}")
            return False
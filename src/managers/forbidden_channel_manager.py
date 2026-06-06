from typing import List

class ForbiddenChannelManager:
    def __init__(self, db_manager, logger):
        self.db_manager = db_manager
        self.logger = logger.get_logger()

    def add_channel(self, guild_id: int, channel_id: int, added_by: int) -> bool:
        try:
            self.db_manager.execute_insert(
                "INSERT OR IGNORE INTO forbidden_channels (guild_id, channel_id, added_by) VALUES (?, ?, ?)",
                (guild_id, channel_id, added_by)
            )
            return True
        except Exception as e:
            self.logger.error(f"添加违规频道失败: {e}")
            return False

    def remove_channel(self, guild_id: int, channel_id: int) -> bool:
        try:
            rows = self.db_manager.execute_update(
                "DELETE FROM forbidden_channels WHERE guild_id = ? AND channel_id = ?",
                (guild_id, channel_id)
            )
            return rows > 0
        except Exception as e:
            self.logger.error(f"移除违规频道失败: {e}")
            return False

    def get_channels(self, guild_id: int) -> List[int]:
        rows = self.db_manager.execute_query(
            "SELECT channel_id FROM forbidden_channels WHERE guild_id = ?",
            (guild_id,)
        )
        return [row['channel_id'] for row in rows]

    def is_forbidden(self, guild_id: int, channel_id: int) -> bool:
        rows = self.db_manager.execute_query(
            "SELECT 1 FROM forbidden_channels WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id)
        )
        return len(rows) > 0

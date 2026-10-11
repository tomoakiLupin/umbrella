import json
import logging
import os
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

os.environ.pop("SSLKEYLOGFILE", None)

import discord

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.database import DatabaseManager
from src.managers.admin_manager import AdminManager
from src.managers.forbidden_channel_manager import ForbiddenChannelManager
from src.managers.message_forward_manager import MessageForwardManager
from src.managers.owner_channel_manager import OwnerChannelManager


class DummyConfig:
    super_admin_id = 1001


class DummyLoggerManager:
    def __init__(self):
        self._logger = logging.getLogger("test-discord-bot")
        self._logger.handlers.clear()
        self._logger.addHandler(logging.NullHandler())

    def get_logger(self):
        return self._logger


class ManagerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.tmp.name, "owner_channel.db")
        self.db = DatabaseManager(self.db_path)
        self.logger_manager = DummyLoggerManager()

    def tearDown(self):
        self.tmp.cleanup()

    def make_owner_manager(self):
        manager = OwnerChannelManager.__new__(OwnerChannelManager)
        manager.config = DummyConfig()
        manager.logger = self.logger_manager.get_logger()
        manager.db = self.db
        return manager

    def make_forward_manager(self):
        manager = MessageForwardManager.__new__(MessageForwardManager)
        manager.config = DummyConfig()
        manager.logger = self.logger_manager.get_logger()
        manager.db_path = self.db_path
        manager.init_database()
        return manager


class AdminManagerTests(ManagerTestCase):
    def test_super_admin_can_manage_admin_roles_in_sqlite(self):
        manager = AdminManager(DummyConfig(), self.logger_manager, self.db)

        self.assertTrue(manager.add_admin_role(1001, 2001))
        self.assertFalse(manager.add_admin_role(9999, 2002))
        self.assertTrue(manager.can_use_admin_commands(9999, [2001]))
        self.assertFalse(manager.can_use_admin_commands(9999, [3001]))

        reloaded = AdminManager(DummyConfig(), self.logger_manager, self.db)
        self.assertEqual(reloaded.get_admin_roles(), [2001])

        self.assertTrue(reloaded.remove_admin_role(1001, 2001))
        self.assertFalse(reloaded.has_admin_role([2001]))


class OwnerChannelManagerTests(ManagerTestCase):
    def test_panel_config_channel_lifecycle_and_blacklist(self):
        manager = self.make_owner_manager()

        self.assertTrue(
            manager.create_panel_config(
                guild_id=1,
                panel_channel_id=10,
                owner_id=20,
                category_id=30,
                archive_channel_id=40,
                review_channel_id=50,
                allowed_roles=[600, 601],
                allowed_days=7,
                requester_id=1001,
            )
        )
        self.assertFalse(
            manager.create_panel_config(1, 11, 21, 31, 41, 51, [], 0, 1001)
        )

        panel = manager.get_panel_config(1)
        self.assertEqual(panel["allowed_roles"], [600, 601])
        self.assertTrue(manager.update_panel_config(1, allowed_roles=[700], allowed_days=0))
        self.assertEqual(manager.get_panel_config(1)["allowed_roles"], [700])

        self.assertEqual(manager.get_next_channel_number(1), 1)
        self.assertEqual(manager.get_next_channel_number(1), 2)
        self.assertTrue(manager.create_owner_channel(9001, 1, 3001, "appeal text", 2))
        self.assertEqual(manager.get_owner_channel_info(9001)["status"], "active")
        self.assertEqual(len(manager.get_active_channels_by_guild(1)), 1)
        self.assertTrue(manager.archive_owner_channel(9001))
        self.assertEqual(manager.get_active_channels_by_guild(1), [])

        self.assertTrue(manager.add_to_blacklist(1, 3001, 1001))
        self.assertTrue(manager.is_blacklisted(1, 3001))
        self.assertEqual(manager.check_user_eligibility(1, 3001, [700], discord.utils.utcnow())[1], "blacklisted")
        self.assertTrue(manager.remove_from_blacklist(1, 3001))

    def test_pending_request_blocks_duplicate_eligibility(self):
        manager = self.make_owner_manager()
        self.assertTrue(manager.create_panel_config(1, 10, 20, 30, 40, 50, [], 0, 1001))

        request_id = manager.create_pending_request(1, 3001, "need help")

        self.assertTrue(request_id)
        self.assertTrue(manager.has_pending_request(1, 3001))
        self.assertEqual(manager.get_pending_request(request_id)["complaint_content"], "need help")
        eligible, _ = manager.check_user_eligibility(
            1,
            3001,
            [],
            discord.utils.utcnow() - timedelta(days=30),
        )
        self.assertFalse(eligible)
        self.assertTrue(manager.update_request_status(request_id, "approved"))
        self.assertFalse(manager.has_pending_request(1, 3001))


class MessageForwardManagerTests(ManagerTestCase):
    def test_forward_rule_crud_and_activation(self):
        manager = self.make_forward_manager()

        self.assertTrue(manager.add_forward_rule(10, 20, 1, 2, 1001))
        self.assertFalse(manager.add_forward_rule(10, 20, 1, 2, 1001))

        rules = manager.get_user_forward_rules(1001)
        self.assertEqual(len(rules), 1)
        self.assertEqual(manager.get_forward_targets(10), [(20, 2, rules[0]["id"])])

        self.assertTrue(manager.toggle_forward_rule(rules[0]["id"], 1001, False))
        self.assertEqual(manager.get_forward_targets(10), [])

        self.assertTrue(manager.toggle_forward_rule(rules[0]["id"], 1001, True))
        self.assertTrue(manager.remove_forward_rule(10, 20, 1001))
        self.assertEqual(manager.get_user_forward_rules(1001), [])


class ForbiddenChannelManagerTests(ManagerTestCase):
    def test_forbidden_channel_and_kick_log_storage(self):
        manager = ForbiddenChannelManager(self.db, self.logger_manager)

        self.assertTrue(manager.add_channel(1, 10, 1001))
        self.assertTrue(manager.is_forbidden(1, 10))
        self.assertEqual(manager.get_channels(1), [10])

        manager.add_kick_log(
            guild_id=1,
            user_id=3001,
            user_name="spammer",
            channel_id=10,
            channel_name="trap",
            message_content="bad message",
            deleted_count=5,
            kicked=True,
        )
        logs = manager.get_kick_logs(1)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["deleted_count"], 5)
        self.assertEqual(logs[0]["kicked"], 1)

        self.assertTrue(manager.remove_channel(1, 10))
        self.assertFalse(manager.is_forbidden(1, 10))


class DatabaseMigrationTests(unittest.TestCase):
    def test_migrate_legacy_json_files_into_sqlite(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            previous_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with open("admin_data.json", "w", encoding="utf-8") as f:
                    json.dump({"admin_roles": [2001, 2002]}, f)

                with open("owner_channel_data.json", "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "panels": {
                                "1": {
                                    "panel_channel_id": 10,
                                    "owner_id": 20,
                                    "category_id": 30,
                                    "archive_channel_id": 40,
                                    "review_channel_id": 50,
                                    "allowed_roles": [600],
                                    "allowed_days": 3,
                                    "created_by": 1001,
                                    "created_at": "2026-01-01 00:00:00",
                                }
                            },
                            "channels": {
                                "9001": {
                                    "guild_id": 1,
                                    "user_id": 3001,
                                    "complaint_content": "legacy",
                                    "channel_number": 1,
                                    "status": "active",
                                    "created_at": "2026-01-01 00:00:00",
                                }
                            },
                            "counter": {"1": 1},
                            "blacklist": {"1": [3002]},
                            "pending_requests": {
                                "req-1": {
                                    "guild_id": 1,
                                    "user_id": 3003,
                                    "complaint_content": "pending",
                                    "status": "pending",
                                    "created_at": "2026-01-01 00:00:00",
                                }
                            },
                        },
                        f,
                    )

                db = DatabaseManager("owner_channel.db")
                db.migrate_from_json()

                self.assertEqual(
                    [row["role_id"] for row in db.execute_query("SELECT role_id FROM admin_roles ORDER BY role_id")],
                    [2001, 2002],
                )
                self.assertEqual(
                    db.execute_query("SELECT allowed_roles FROM panel_configs WHERE guild_id = 1")[0]["allowed_roles"],
                    "[600]",
                )
                self.assertEqual(
                    db.execute_query("SELECT complaint_content FROM owner_channels WHERE channel_id = 9001")[0][0],
                    "legacy",
                )
                self.assertTrue(os.path.exists("admin_data.json.backup"))
                self.assertTrue(os.path.exists("owner_channel_data.json.backup"))
            finally:
                os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()

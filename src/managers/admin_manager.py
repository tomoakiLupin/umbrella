import json
import os
from typing import Set, List, Dict, Optional

class AdminManager:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_logger()
        self.admin_data_file = "admin_data.json"
        self.super_admin_id = config.super_admin_id
        self.admin_roles: Set[int] = set()
        self.load_admin_data()
    
    def load_admin_data(self):
        if os.path.exists(self.admin_data_file):
            try:
                with open(self.admin_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.admin_roles = set(data.get('admin_roles', []))
                self.logger.info(f"Loaded {len(self.admin_roles)} admin roles from file")
            except Exception as e:
                self.logger.error(f"Error loading admin data: {e}")
                self.admin_roles = set()
        else:
            self.admin_roles = set()
    
    def save_admin_data(self):
        try:
            data = {
                'admin_roles': list(self.admin_roles)
            }
            with open(self.admin_data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.info("Admin data saved successfully")
        except Exception as e:
            self.logger.error(f"Error saving admin data: {e}")
    
    def is_super_admin(self, user_id: int) -> bool:
        return user_id == self.super_admin_id
    
    def is_admin(self, user_id: int) -> bool:
        return self.is_super_admin(user_id)
    
    def add_admin_role(self, user_id: int, role_id: int) -> bool:
        if not self.is_super_admin(user_id):
            return False
        
        if role_id not in self.admin_roles:
            self.admin_roles.add(role_id)
            self.save_admin_data()
            self.logger.info(f"Added admin role {role_id} by super admin {user_id}")
            return True
        return False
    
    def remove_admin_role(self, user_id: int, role_id: int) -> bool:
        if not self.is_super_admin(user_id):
            return False
        
        if role_id in self.admin_roles:
            self.admin_roles.remove(role_id)
            self.save_admin_data()
            self.logger.info(f"Removed admin role {role_id} by super admin {user_id}")
            return True
        return False
    
    def get_admin_roles(self) -> List[int]:
        return list(self.admin_roles)
    
    def has_admin_role(self, member_roles: List[int]) -> bool:
        return bool(self.admin_roles.intersection(set(member_roles)))
    
    def can_use_admin_commands(self, user_id: int, member_roles: List[int]) -> bool:
        return self.is_super_admin(user_id) or self.has_admin_role(member_roles)
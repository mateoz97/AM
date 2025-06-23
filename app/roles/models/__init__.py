# app/roles/models/__init__.py
from .role import BusinessRole, RolePermission
from .main_role import MainRole, MainRolePermission

__all__ = ['BusinessRole', 'RolePermission', 'MainRole', 'MainRolePermission']
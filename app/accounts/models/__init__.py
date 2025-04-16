# Importar los modelos para que sean accesibles desde app.auth_app.models
from app.accounts.models.user import CustomUser
from app.accounts.models.business import Business, BusinessJoinRequest, BusinessInvitation
from app.accounts.models.role import BusinessRole, RolePermission

# Para mantener compatibilidad con el código existente
__all__ = [
    'CustomUser', 
    'Business', 
    'BusinessRole', 
    'RolePermission',
    'BusinessJoinRequest',
    'BusinessInvitation'
]
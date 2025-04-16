# Importar los modelos para que sean accesibles desde app.auth_app.models
from app.auth_app.models.user import CustomUser
from app.auth_app.models.business import Business, BusinessJoinRequest, BusinessInvitation
from app.auth_app.models.role import BusinessRole, RolePermission

# Para mantener compatibilidad con el código existente
__all__ = [
    'CustomUser', 
    'Business', 
    'BusinessRole', 
    'RolePermission',
    'BusinessJoinRequest',
    'BusinessInvitation'
]
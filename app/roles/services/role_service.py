# Models
from app.roles.models.role import BusinessRole, RolePermission

# Management
import logging

logger = logging.getLogger(__name__)

class RoleService:
    @staticmethod
    def create_business_roles(business):
        if not business or not business.name:
            return  # Evita errores si el negocio aún no está completamente creado

        roles_data = {
            "Admin": {
                "description": "Control total sobre el negocio",
                "is_default": True,
                "can_modify": False,
                "permissions": {
                    "can_view_dashboard": True,
                    "can_manage_users": True,
                    "can_manage_roles": True,
                    "can_view_orders": True,
                    "can_create_orders": True,
                    "can_update_orders": True,
                    "can_delete_orders": True,
                    "can_view_inventory": True,
                    "can_manage_inventory": True,
                    "can_view_reports": True,
                    "can_export_data": True
                }
            },
            "Gerente": {
                "description": "Gestión general del negocio",
                "is_default": True,
                "can_modify": True,
                "permissions": {
                    "can_view_dashboard": True,
                    "can_manage_users": True,
                    "can_view_orders": True,
                    "can_create_orders": True,
                    "can_update_orders": True,
                    "can_view_inventory": True,
                    "can_manage_inventory": True,
                    "can_view_reports": True,
                    "can_export_data": True
                }
            },
            "Cocinero": {
                "description": "Puede ver y actualizar pedidos",
                "is_default": True,
                "can_modify": True,
                "permissions": {
                    "can_view_dashboard": True,
                    "can_view_orders": True,
                    "can_update_orders": True,
                    "can_view_inventory": True
                }
            },
            "Mesero": {
                "description": "Puede gestionar pedidos y ver inventario",
                "is_default": True,
                "can_modify": True,
                "permissions": {
                    "can_view_dashboard": True,
                    "can_view_orders": True,
                    "can_create_orders": True,
                    "can_update_orders": True,
                    "can_view_inventory": True
                }
            },
            "Cliente": {
                "description": "Acceso de solo lectura a información básica",
                "is_default": True,
                "can_modify": True,
                "permissions": {
                    "can_view_dashboard": True,
                    "can_view_orders": True
                }
            }
        }

        
        
        for role_name, role_data in roles_data.items():
            # Crear o actualizar el rol
            role, created = BusinessRole.objects.get_or_create(
                business=business,
                name=role_name,
                defaults={
                    "description": role_data["description"],
                    "is_default": role_data["is_default"],
                    "can_modify": role_data["can_modify"]
                }
            )
            
            # Crear o actualizar los permisos
            if created:
                RolePermission.objects.create(
                    business_role=role,
                    **role_data["permissions"]
                )
            else:
                # Si el rol ya existe, actualizar sus permisos
                try:
                    permissions = role.role_permissions
                    for perm_name, perm_value in role_data["permissions"].items():
                        setattr(permissions, perm_name, perm_value)
                    permissions.save()
                except RolePermission.DoesNotExist:
                    # Si los permisos no existen, crearlos
                    RolePermission.objects.create(
                        business_role=role,
                        **role_data["permissions"]
                    )

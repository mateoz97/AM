# Models
from app.roles.models.role import BusinessRole, RolePermission

# Management
import logging

logger = logging.getLogger(__name__)


class BusinessRoleService:
    """Servicio para gestionar los roles personalizados de cada negocio"""
    
    @staticmethod
    def create_business_roles(business):
        """
        Crea solo el rol de Owner por defecto para el negocio.
        Los demás roles deben ser creados manualmente por el propietario.
        """
        if not business or not business.id:
            return {}

        # Solo crear el rol de Owner por defecto
        roles_data = {
            "Owner": {
                "description": "Propietario del negocio con control total",
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
            }
        }
        
        created_roles = {}
        
        for role_name, role_data in roles_data.items():
            try:
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
                
                created_roles[role_name] = role
                
                # Actualizar los permisos solo si no se acaba de crear el rol
                # porque BusinessRole.save() ya habrá creado los permisos
                if not created:
                    try:
                        # Intentar obtener los permisos existentes
                        permissions = role.role_permissions
                        # Actualizar permisos
                        for perm_name, perm_value in role_data["permissions"].items():
                            setattr(permissions, perm_name, perm_value)
                        permissions.save()
                    except RolePermission.DoesNotExist:
                        # Solo crear si no existen los permisos
                        RolePermission.objects.create(
                            business_role=role,
                            **role_data["permissions"]
                        )
            except Exception as e:
                logger.error(f"Error creando rol {role_name} para negocio {business.id}: {str(e)}")
        
        return created_roles
    
    @staticmethod
    def create_default_role_templates():
        """
        Retorna plantillas de roles que pueden ser creados por los propietarios.
        No crea los roles, solo proporciona las plantillas.
        """
        return {
            "Manager": {
                "description": "Gestión general del negocio",
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
            "Employee": {
                "description": "Empleado con permisos básicos",
                "permissions": {
                    "can_view_dashboard": True,
                    "can_view_orders": True,
                    "can_create_orders": True,
                    "can_update_orders": True,
                    "can_view_inventory": True
                }
            },
            "Viewer": {
                "description": "Acceso de solo lectura",
                "permissions": {
                    "can_view_dashboard": True,
                    "can_view_orders": True,
                    "can_view_inventory": True,
                    "can_view_reports": True
                }
            },
            "Waiter": {
                "description": "Mesero - gestión de pedidos",
                "permissions": {
                    "can_view_dashboard": True,
                    "can_view_orders": True,
                    "can_create_orders": True,
                    "can_update_orders": True,
                    "can_view_inventory": True
                }
            },
            "Chef": {
                "description": "Cocinero - actualización de pedidos",
                "permissions": {
                    "can_view_dashboard": True,
                    "can_view_orders": True,
                    "can_update_orders": True,
                    "can_view_inventory": True
                }
            }
        }
            
    @staticmethod
    def assign_role_to_user(user, role_name):
        """
        Asigna un rol específico a un usuario dentro de su negocio.
        
        Args:
            user (CustomUser): Usuario a actualizar
            role_name (str): Nombre del rol a asignar
            
        Returns:
            bool: True si se asignó correctamente, False en caso contrario
        """
        if not user.business:
            return False
            
        try:
            role = BusinessRole.objects.get(
                business=user.business,
                name=role_name
            )
            user.business_role = role
            user.save(update_fields=['business_role'])
            return True
        except BusinessRole.DoesNotExist:
            return False
    
    @staticmethod
    def get_roles_for_business(business):
        """
        Obtiene todos los roles disponibles para un negocio.
        
        Args:
            business (Business): Instancia del negocio
            
        Returns:
            QuerySet: QuerySet con los roles del negocio
        """
        return BusinessRole.objects.filter(business=business)
    
    @staticmethod
    def create_custom_role(business, name, description, permissions_data):
        """
        Crea un nuevo rol personalizado con permisos específicos.
        
        Args:
            business (Business): Instancia del negocio
            name (str): Nombre del rol
            description (str): Descripción del rol
            permissions_data (dict): Diccionario con los permisos {permiso: valor}
            
        Returns:
            BusinessRole: Instancia del rol creado o None si hubo error
        """
        try:
            # Validar que el nombre no exista ya para este negocio
            if BusinessRole.objects.filter(business=business, name=name).exists():
                return None
                
            # Crear el rol
            role = BusinessRole.objects.create(
                business=business,
                name=name,
                description=description,
                is_default=False,
                can_modify=True
            )
            
            # Actualizar los permisos
            permissions = role.role_permissions
            for permission_name, value in permissions_data.items():
                if hasattr(permissions, permission_name):
                    setattr(permissions, permission_name, value)
            
            permissions.save()
            return role
        except Exception as e:
            logger.error(f"Error creando rol personalizado: {str(e)}")
            return None
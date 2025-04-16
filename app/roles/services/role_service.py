# Models
from app.roles.models.role import BusinessRole, RolePermission

# Management
import logging

logger = logging.getLogger(__name__)


class BusinessRoleService:
    """Servicio para gestionar los roles personalizados de cada negocio"""
    
    @staticmethod
    def create_default_roles(business):
        """
        Crea los roles predeterminados para un nuevo negocio.
        
        Args:
            business (Business): Instancia del negocio
            
        Returns:
            dict: Diccionario con los roles creados {nombre: instancia}
        """
        default_roles = {
            "Administrador": {
                "description": "Acceso completo a todas las funciones del negocio",
                "is_default": True,
                "can_modify": False
            },
            "Visualizador": {
                "description": "Acceso de solo lectura a información básica",
                "is_default": True,
                "can_modify": True
            },
            "Mesero": {
                "description": "Puede gestionar pedidos y ver inventario",
                "is_default": True,
                "can_modify": True
            },
            "Cocinero": {
                "description": "Puede ver y actualizar pedidos",
                "is_default": True,
                "can_modify": True
            }
        }
        
        created_roles = {}
        
        for role_name, role_data in default_roles.items():
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
            
        return created_roles
    
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
            print(f"Error creando rol personalizado: {str(e)}")
            return None


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

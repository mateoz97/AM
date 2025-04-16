# Models
from app.auth_app.models.role import BusinessRole
# Management
import logging
import os
from django.conf import settings


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

class DatabaseService:
    @staticmethod
    def create_business_database(business):
        """
        Crea una nueva base de datos SQLite para un business
        """
        if not business or not business.id:
            print("Error: Business inválido o sin ID")
            return False
            
        # Nombre de la nueva base de datos
        db_name = f"business_{business.name}"
        db_path = settings.BASE_DIR / f"db_{db_name}.sqlite3"
        
        print(f"Intentando crear base de datos: {db_name} en {db_path}")
        
        # Si el archivo ya existe, no hacer nada
        if os.path.exists(db_path):
            print(f"Base de datos {db_name} ya existe en {db_path}")
            return True
            
        # Para crear una nueva base de datos SQLite, simplemente creamos un archivo vacío
        print(f"Creando archivo para base de datos {db_name}")
        open(db_path, 'wb').close()
            
        # Añadir la nueva base de datos a la configuración en runtime
        if db_name not in settings.DATABASES:
            print(f"Configurando {db_name} en DATABASES")
            # Copiar la configuración completa de la base de datos default
            default_config = settings.DATABASES['default'].copy()
            # Actualizar solo el nombre
            default_config['NAME'] = db_path
            # Asignar la configuración completa
            settings.DATABASES[db_name] = default_config
        else:
            print(f"Base de datos {db_name} ya existe en DATABASES")
            
        # Ejecutar migraciones en la nueva base de datos
        try:
            print(f"Migrando base de datos {db_name}")
            from django.core.management import call_command
            call_command('migrate', database=db_name)
            print(f"Migración exitosa para {db_name}")
            return True
        except Exception as e:
            print(f"Error al migrar base de datos {db_name}: {str(e)}")
            return False
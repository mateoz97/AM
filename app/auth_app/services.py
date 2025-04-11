from django.contrib.auth.models import Group, Permission
import os
import shutil
from pathlib import Path
from django.conf import settings


class RoleService:
    @staticmethod
    def create_business_roles(business):
        if not business or not business.name:
            return  # Evita errores si el negocio aún no está completamente creado

        roles_permissions = {
            "Admin": ["add", "change", "delete", "view"],
            "Gerente": ["view", "change"],
            "Cocinero": ["view", "change"],
            "Mesero": ["view", "add"],
            "Cliente": ["view"],
        }

        for role, permissions in roles_permissions.items():
            group_name = f"{business.name}_{role}"
            group, created = Group.objects.get_or_create(name=group_name)

            if created:
                for permission in permissions:
                    perms = Permission.objects.filter(codename__startswith=permission)
                    group.permissions.add(*perms)



class DatabaseService:
    @staticmethod
    def create_business_database(business):
        """
        Crea una nueva base de datos SQLite para un business
        """
        if not business or not business.id:
            return False
            
        # Nombre de la nueva base de datos
        db_name = f"business_{business.id}"
        db_path = settings.BASE_DIR / f"db_{db_name}.sqlite3"
        
        # Si el archivo ya existe, no hacer nada
        if os.path.exists(db_path):
            return True
            
        # Para crear una nueva base de datos SQLite, simplemente creamos un archivo vacío
        with open(db_path, 'w') as f:
            pass
            
        # Añadir la nueva base de datos a la configuración en runtime
        if db_name not in settings.DATABASES:
            settings.DATABASES[db_name] = {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': db_path,
            }
            
        # Ejecutar migraciones en la nueva base de datos (opcional en esta etapa)
        # Comentado por ahora para simplificar
        # from django.core.management import call_command
        # call_command('migrate', database=db_name)
        
        return True
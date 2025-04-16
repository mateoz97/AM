# Models

 
# Management
import logging
import os
from django.conf import settings


logger = logging.getLogger(__name__)



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
        
    
# Models
 
# Management
import logging
import os
import traceback
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
            logger.error("❌ Se intentó crear base de datos para un negocio inválido o sin ID")
            return False
            
        # Nombre de la nueva base de datos - Usar ID en lugar de nombre
        db_name = f"business_{business.id}"
        db_path = settings.BASE_DIR / f"db_{db_name}.sqlite3"
        
        print(f"Intentando crear base de datos: {db_name} en {db_path}")
        logger.info(f"Intentando crear base de datos: {db_name} en {db_path}")
        
        # Verificar permisos de escritura en el directorio
        try:
            base_dir_writable = os.access(settings.BASE_DIR, os.W_OK)
            print(f"El directorio base {settings.BASE_DIR} es escribible: {base_dir_writable}")
            logger.info(f"El directorio base {settings.BASE_DIR} es escribible: {base_dir_writable}")
            
            if not base_dir_writable:
                print(f"⚠️ No se puede escribir en el directorio {settings.BASE_DIR}")
                logger.error(f"⚠️ No se puede escribir en el directorio {settings.BASE_DIR}")
                return False
        except Exception as e:
            print(f"Error al verificar permisos: {str(e)}")
            logger.error(f"Error al verificar permisos: {str(e)}")
        
        # Si el archivo ya existe, no hacer nada
        if os.path.exists(db_path):
            print(f"Base de datos {db_name} ya existe en {db_path}")
            logger.info(f"Base de datos {db_name} ya existe en {db_path}")
            return True
            
        try:
            # Para crear una nueva base de datos SQLite, simplemente creamos un archivo vacío
            print(f"Creando archivo para base de datos {db_name}")
            logger.info(f"Creando archivo para base de datos {db_name}")
            
            # Intentar crear el archivo
            with open(db_path, 'wb') as f:
                f.write(b'')  # Escribir un archivo vacío
            
            # Verificar que el archivo se haya creado
            if not os.path.exists(db_path):
                print(f"❌ El archivo no se creó en {db_path}")
                logger.error(f"❌ El archivo no se creó en {db_path}")
                return False
            
            file_size = os.path.getsize(db_path)
            print(f"Archivo creado: {db_path} (tamaño: {file_size} bytes)")
            logger.info(f"Archivo creado: {db_path} (tamaño: {file_size} bytes)")
                
            # Añadir la nueva base de datos a la configuración en runtime
            if db_name not in settings.DATABASES:
                print(f"Configurando {db_name} en DATABASES")
                logger.info(f"Configurando {db_name} en DATABASES")
                # Copiar la configuración completa de la base de datos default
                default_config = settings.DATABASES['default'].copy()
                # Actualizar solo el nombre
                default_config['NAME'] = db_path
                # Asignar la configuración completa
                settings.DATABASES[db_name] = default_config
                print(f"✅ Base de datos {db_name} configurada en settings")
                logger.info(f"✅ Base de datos {db_name} configurada en settings")
            else:
                print(f"Base de datos {db_name} ya existe en DATABASES")
                logger.info(f"Base de datos {db_name} ya existe en DATABASES")
                
            # Ejecutar migraciones en la nueva base de datos
            print(f"Migrando base de datos {db_name}")
            logger.info(f"Migrando base de datos {db_name}")
            
            try:
                from django.core.management import call_command
                call_command('migrate', database=db_name, verbosity=2)
                print(f"✅ Migración exitosa para {db_name}")
                logger.info(f"✅ Migración exitosa para {db_name}")
                
                # Verificar tamaño del archivo después de migrar
                file_size_after = os.path.getsize(db_path)
                print(f"Tamaño de archivo después de migración: {file_size_after} bytes")
                logger.info(f"Tamaño de archivo después de migración: {file_size_after} bytes")
                
                return True
            except Exception as e:
                print(f"❌ Error al migrar base de datos {db_name}: {str(e)}")
                logger.error(f"❌ Error al migrar base de datos {db_name}: {str(e)}")
                traceback.print_exc()  # Imprimir el stacktrace completo
                return False
                
        except Exception as e:
            print(f"❌ Error al crear/migrar base de datos {db_name}: {str(e)}")
            logger.error(f"❌ Error al crear/migrar base de datos {db_name}: {str(e)}")
            traceback.print_exc()  # Imprimir el stacktrace completo
            return False
            
    @staticmethod
    def verify_business_database(business_id):
        """
        Verifica si la base de datos para un negocio existe y está configurada correctamente
        """
        if not business_id:
            return False, "ID de negocio no proporcionado"
            
        db_name = f"business_{business_id}"
        db_path = settings.BASE_DIR / f"db_{db_name}.sqlite3"
        
        # Verificar si el archivo existe
        file_exists = os.path.exists(db_path)
        file_size = os.path.getsize(db_path) if file_exists else 0
        
        # Verificar si está en la configuración
        config_exists = db_name in settings.DATABASES
        
        # Verificar si tiene las tablas correctas
        has_tables = False
        tables = []
        if file_exists and config_exists:
            try:
                from django.db import connections
                with connections[db_name].cursor() as cursor:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = [row[0] for row in cursor.fetchall()]
                    has_tables = len(tables) > 0
            except Exception as e:
                return False, f"Error al verificar tablas: {str(e)}"
        
        # Construir resultado
        if file_exists and config_exists and has_tables:
            return True, {
                "db_name": db_name,
                "db_path": str(db_path),
                "file_size": file_size,
                "tables": tables
            }
        else:
            issues = []
            if not file_exists:
                issues.append("El archivo de base de datos no existe")
            if not config_exists:
                issues.append("La base de datos no está configurada en settings")
            if not has_tables:
                issues.append("La base de datos no tiene tablas")
                
            return False, {
                "issues": issues,
                "db_name": db_name,
                "db_path": str(db_path),
                "file_exists": file_exists,
                "file_size": file_size,
                "config_exists": config_exists,
                "tables": tables
            }
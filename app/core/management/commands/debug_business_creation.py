from django.core.management.base import BaseCommand
from django.conf import settings
import os
import shutil
from app.business.models.business import Business
from app.business.services.business_service import DatabaseService
from django.db import connections, OperationalError

class Command(BaseCommand):
    help = 'Depura y soluciona problemas con la creación de bases de datos de negocios'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business_id', 
            type=int, 
            help='ID específico del negocio a verificar'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar recreación de la base de datos'
        )
        parser.add_argument(
            '--fix-permissions',
            action='store_true',
            help='Intentar corregir permisos en el directorio'
        )

    def handle(self, *args, **options):
        business_id = options.get('business_id')
        force = options.get('force')
        fix_permissions = options.get('fix_permissions')
        
        self.stdout.write(self.style.SUCCESS("========== DEBUGGING DE BASES DE DATOS DE NEGOCIOS =========="))
        
        # Verificar permisos en el directorio base
        self.stdout.write("1. Verificando permisos en el directorio base...")
        base_dir = settings.BASE_DIR
        
        base_dir_writable = os.access(base_dir, os.W_OK)
        self.stdout.write(f"   Directorio: {base_dir}")
        self.stdout.write(f"   ¿Es escribible?: {'✅ Sí' if base_dir_writable else '❌ No'}")
        
        if not base_dir_writable and fix_permissions:
            self.stdout.write("   Intentando corregir permisos...")
            try:
                import stat
                current_permissions = os.stat(base_dir).st_mode
                os.chmod(base_dir, current_permissions | stat.S_IWUSR | stat.S_IWGRP)
                
                # Verificar de nuevo
                base_dir_writable = os.access(base_dir, os.W_OK)
                self.stdout.write(f"   Después de corrección - ¿Es escribible?: {'✅ Sí' if base_dir_writable else '❌ No'}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   Error al intentar corregir permisos: {str(e)}"))
        
        # Comprobar la existencia del directorio logs
        logs_dir = settings.BASE_DIR / 'logs'
        if not os.path.exists(logs_dir):
            self.stdout.write(f"   Directorio de logs no existe, creando: {logs_dir}")
            try:
                os.makedirs(logs_dir, exist_ok=True)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   Error al crear directorio de logs: {str(e)}"))
        
        # Verificar bases de datos configuradas
        self.stdout.write("\n2. Bases de datos configuradas en settings:")
        for db_name, db_config in settings.DATABASES.items():
            self.stdout.write(f"   - {db_name}: {db_config['NAME']}")
        
        # Si se especificó un negocio, verificarlo
        if business_id:
            self.stdout.write(f"\n3. Verificando negocio con ID {business_id}...")
            
            try:
                business = Business.objects.get(id=business_id)
                self.stdout.write(f"   ✅ Negocio encontrado: {business.name}")
                
                # Verificar la base de datos
                db_name = f"business_{business_id}"
                db_path = settings.BASE_DIR / f"db_{db_name}.sqlite3"
                
                self.stdout.write(f"   Verificando base de datos para: {db_name}")
                self.stdout.write(f"   Ruta esperada: {db_path}")
                
                # Verificar el archivo
                file_exists = os.path.exists(db_path)
                self.stdout.write(f"   ¿Archivo existe?: {'✅ Sí' if file_exists else '❌ No'}")
                
                if file_exists:
                    file_size = os.path.getsize(db_path)
                    self.stdout.write(f"   Tamaño del archivo: {file_size} bytes")
                    
                    if file_size == 0:
                        self.stdout.write(self.style.WARNING("   ⚠️ El archivo existe pero está vacío"))
                
                # Verificar configuración
                config_exists = db_name in settings.DATABASES
                self.stdout.write(f"   ¿Configuración en settings?: {'✅ Sí' if config_exists else '❌ No'}")
                
                # Verificar conexión
                if config_exists:
                    try:
                        connections[db_name].ensure_connection()
                        self.stdout.write("   ✅ Conexión establecida correctamente")
                        
                        # Verificar tablas
                        with connections[db_name].cursor() as cursor:
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                            tables = [row[0] for row in cursor.fetchall()]
                            if tables:
                                self.stdout.write(f"   ✅ Tablas encontradas: {len(tables)}")
                                for table in tables[:5]:  # Mostrar solo las primeras 5
                                    self.stdout.write(f"      - {table}")
                                if len(tables) > 5:
                                    self.stdout.write(f"      - ...y {len(tables) - 5} más")
                            else:
                                self.stdout.write(self.style.WARNING("   ⚠️ No se encontraron tablas en la base de datos"))
                    except OperationalError as e:
                        self.stdout.write(self.style.ERROR(f"   ❌ Error de conexión: {str(e)}"))
                
                # Si force está habilitado, recrear la base de datos
                if force:
                    self.stdout.write("\n4. Recreando base de datos...")
                    
                    # Hacer backup del archivo si existe
                    if file_exists:
                        backup_path = str(db_path) + '.bak'
                        self.stdout.write("   Creando backup en: {backup_path}")
                        try:
                            shutil.copy2(db_path, backup_path)
                            self.stdout.write("   ✅ Backup creado correctamente")
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"   ❌ Error al crear backup: {str(e)}"))
                    
                    # Eliminar el archivo actual
                    if file_exists:
                        try:
                            os.remove(db_path)
                            self.stdout.write("   ✅ Archivo existente eliminado")
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"   ❌ Error al eliminar archivo: {str(e)}"))
                    
                    # Eliminar la configuración si existe
                    if config_exists:
                        del settings.DATABASES[db_name]
                        self.stdout.write("   ✅ Configuración eliminada de settings")
                    
                    # Crear nueva base de datos
                    self.stdout.write("   Creando nueva base de datos...")
                    success = DatabaseService.create_business_database(business)
                    
                    if success:
                        self.stdout.write(self.style.SUCCESS("   ✅ Base de datos creada correctamente"))
                    else:
                        self.stdout.write(self.style.ERROR("   ❌ Error al crear la base de datos"))
                
            except Business.DoesNotExist:
                self.stdout.write(self.style.ERROR("   ❌ Negocio con ID {business_id} no encontrado"))
        else:
            # Si no se especificó un negocio, mostrar información general
            self.stdout.write("\n3. Estado general de bases de datos:")
            
            # Verificar archivos de bases de datos existentes
            self.stdout.write("   Archivos de bases de datos encontrados:")
            db_files = []
            for file in os.listdir(settings.BASE_DIR):
                if file.startswith('db_business_') and file.endswith('.sqlite3'):
                    db_path = settings.BASE_DIR / file
                    size = os.path.getsize(db_path)
                    db_files.append((file, size))
            
            if db_files:
                for file, size in db_files:
                    self.stdout.write(f"   - {file} ({size} bytes)")
            else:
                self.stdout.write(self.style.WARNING("   No se encontraron archivos de bases de datos de negocios"))
            
            # Listar negocios existentes
            self.stdout.write("\n   Negocios registrados en la base de datos:")
            businesses = Business.objects.all()
            
            if businesses:
                for business in businesses:
                    # Verificar si existe la base de datos para este negocio
                    db_name = f"business_{business.id}"
                    db_path = settings.BASE_DIR / f"db_{db_name}.sqlite3"
                    file_exists = os.path.exists(db_path)
                    config_exists = db_name in settings.DATABASES
                    
                    status = "✅" if file_exists and config_exists else "⚠️"
                    
                    self.stdout.write(f"   {status} ID: {business.id}, Nombre: {business.name}")
                    self.stdout.write(f"      DB File: {'✅' if file_exists else '❌'}, Config: {'✅' if config_exists else '❌'}")
            else:
                self.stdout.write(self.style.WARNING("   No hay negocios registrados en la base de datos"))
                
        self.stdout.write(self.style.SUCCESS("\n========== FIN DEL DEBUGGING =========="))
        
        if not business_id:
            self.stdout.write("\nPara verificar un negocio específico, usa:")
            self.stdout.write("  python manage.py debug_business_creation --business_id=X")
            self.stdout.write("\nPara recrear la base de datos de un negocio:")
            self.stdout.write("  python manage.py debug_business_creation --business_id=X --force")
            self.stdout.write("\nPara intentar corregir permisos:")
            self.stdout.write("  python manage.py debug_business_creation --fix-permissions")
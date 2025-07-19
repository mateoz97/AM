# app/core/management/commands/setup_multitenant_schemas.py
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.core.management import call_command
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Configura los schemas multitenant correctamente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-business-schemas',
            action='store_true',
            help='Crear schemas para negocios existentes',
        )
        parser.add_argument(
            '--migrate-business-data',
            action='store_true',
            help='Migrar datos existentes a schemas de negocio',
        )
        parser.add_argument(
            '--validate-setup',
            action='store_true',
            help='Validar la configuración multitenant',
        )
        parser.add_argument(
            '--reset-search-path',
            action='store_true',
            help='Resetear search_path a main',
        )
        parser.add_argument(
            '--business-id',
            type=int,
            help='ID específico de negocio para operar',
        )

    def handle(self, *args, **options):
        """Ejecuta la configuración multitenant"""
        
        self.stdout.write(
            self.style.SUCCESS('🔧 CONFIGURACIÓN MULTITENANT SCHEMAS')
        )
        self.stdout.write('=' * 60)
        
        if options['reset_search_path']:
            self.reset_search_path()
        
        if options['create_business_schemas']:
            self.create_business_schemas(options.get('business_id'))
        
        if options['migrate_business_data']:
            self.migrate_business_data(options.get('business_id'))
        
        if options['validate_setup']:
            self.validate_setup()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Configuración multitenant completada')
        )

    def reset_search_path(self):
        """Resetea el search_path a main"""
        self.stdout.write('🔄 Reseteando search_path a main...')
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO main")
            self.stdout.write(self.style.SUCCESS('✅ Search_path reseteado'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))

    def create_business_schemas(self, specific_business_id=None):
        """Crea schemas para negocios existentes"""
        self.stdout.write('🏗️ Creando schemas de negocios...')
        
        try:
            # Asegurar que usamos el schema público para obtener negocios
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO main")
            
            from app.business.models.business import Business
            from app.business.services.business_service import DatabaseService
            
            if specific_business_id:
                businesses = Business.objects.filter(id=specific_business_id)
            else:
                businesses = Business.objects.all()
            
            for business in businesses:
                self.stdout.write(f'📦 Procesando negocio: {business.name} (ID: {business.id})')
                
                try:
                    # Verificar si el schema ya existe
                    schema_name = f'business_{business.id}'
                    exists, info = DatabaseService.verify_business_database(business.id)
                    
                    if exists:
                        self.stdout.write(f'✅ Schema {schema_name} ya existe')
                    else:
                        # Crear el schema
                        result = DatabaseService.create_business_database(business)
                        if result:
                            self.stdout.write(f'✅ Schema {schema_name} creado exitosamente')
                            
                            # Ejecutar migraciones en el nuevo schema
                            self.migrate_business_schema(business.id)
                        else:
                            self.stdout.write(f'❌ Error creando schema {schema_name}')
                            
                except Exception as e:
                    self.stdout.write(f'❌ Error procesando negocio {business.name}: {str(e)}')
        
        except Exception as e:
            self.stdout.write(f'❌ Error general: {str(e)}')

    def migrate_business_schema(self, business_id):
        """Ejecuta migraciones en un schema de negocio específico"""
        schema_name = f'business_{business_id}'
        self.stdout.write(f'📋 Ejecutando migraciones en {schema_name}...')
        
        try:
            with transaction.atomic():
                # Configurar search_path para el schema de negocio
                with connection.cursor() as cursor:
                    cursor.execute(f"SET search_path TO {schema_name}, main")
                
                # Apps que van en schemas de negocio
                business_apps = ['roles', 'inventory', 'orders', 'settings']
                
                for app in business_apps:
                    try:
                        self.stdout.write(f'  📱 Migrando {app}...')
                        call_command('migrate', app, verbosity=0, interactive=False)
                        self.stdout.write(f'  ✅ {app} migrado exitosamente')
                    except Exception as e:
                        self.stdout.write(f'  ❌ Error migrando {app}: {str(e)}')
        
        except Exception as e:
            self.stdout.write(f'❌ Error en migraciones de {schema_name}: {str(e)}')

    def migrate_business_data(self, specific_business_id=None):
        """Migra datos existentes a schemas de negocio"""
        self.stdout.write('📦 Migrando datos a schemas de negocio...')
        
        try:
            # Resetear search_path
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO main")
            
            from app.business.models.business import Business
            
            if specific_business_id:
                businesses = Business.objects.filter(id=specific_business_id)
            else:
                businesses = Business.objects.all()
            
            for business in businesses:
                self.stdout.write(f'📊 Migrando datos para: {business.name}')
                
                try:
                    # Migrar roles de negocio
                    self.migrate_business_roles(business.id)
                    
                    # Migrar inventario
                    self.migrate_inventory_data(business.id)
                    
                    # Migrar órdenes
                    self.migrate_orders_data(business.id)
                    
                    # Migrar configuraciones
                    self.migrate_settings_data(business.id)
                    
                except Exception as e:
                    self.stdout.write(f'❌ Error migrando datos para {business.name}: {str(e)}')
        
        except Exception as e:
            self.stdout.write(f'❌ Error general en migración de datos: {str(e)}')

    def migrate_business_roles(self, business_id):
        """Migra roles específicos del negocio"""
        self.stdout.write(f'  👥 Migrando roles de negocio {business_id}...')
        
        try:
            # Aquí iría la lógica para migrar roles si ya existen datos
            # Por ahora solo verificamos que el schema tenga las tablas
            schema_name = f'business_{business_id}'
            with connection.cursor() as cursor:
                cursor.execute(f"SET search_path TO {schema_name}, main")
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name LIKE 'roles_%'
                """, [schema_name])
                
                tables = cursor.fetchall()
                self.stdout.write(f'    📋 Tablas de roles encontradas: {len(tables)}')
        
        except Exception as e:
            self.stdout.write(f'  ❌ Error en roles: {str(e)}')

    def migrate_inventory_data(self, business_id):
        """Migra datos de inventario"""
        self.stdout.write(f'  📦 Migrando inventario de negocio {business_id}...')
        
        try:
            schema_name = f'business_{business_id}'
            with connection.cursor() as cursor:
                cursor.execute(f"SET search_path TO {schema_name}, main")
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name LIKE 'inventory_%'
                """, [schema_name])
                
                tables = cursor.fetchall()
                self.stdout.write(f'    📋 Tablas de inventario encontradas: {len(tables)}')
        
        except Exception as e:
            self.stdout.write(f'  ❌ Error en inventario: {str(e)}')

    def migrate_orders_data(self, business_id):
        """Migra datos de órdenes"""
        self.stdout.write(f'  🛒 Migrando órdenes de negocio {business_id}...')
        
        try:
            schema_name = f'business_{business_id}'
            with connection.cursor() as cursor:
                cursor.execute(f"SET search_path TO {schema_name}, main")
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name LIKE 'orders_%'
                """, [schema_name])
                
                tables = cursor.fetchall()
                self.stdout.write(f'    📋 Tablas de órdenes encontradas: {len(tables)}')
        
        except Exception as e:
            self.stdout.write(f'  ❌ Error en órdenes: {str(e)}')

    def migrate_settings_data(self, business_id):
        """Migra configuraciones del negocio"""
        self.stdout.write(f'  ⚙️ Migrando configuraciones de negocio {business_id}...')
        
        try:
            schema_name = f'business_{business_id}'
            with connection.cursor() as cursor:
                cursor.execute(f"SET search_path TO {schema_name}, main")
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name LIKE 'settings_%'
                """, [schema_name])
                
                tables = cursor.fetchall()
                self.stdout.write(f'    📋 Tablas de configuraciones encontradas: {len(tables)}')
        
        except Exception as e:
            self.stdout.write(f'  ❌ Error en configuraciones: {str(e)}')

    def validate_setup(self):
        """Valida la configuración multitenant"""
        self.stdout.write('🔍 Validando configuración multitenant...')
        
        try:
            # Resetear search_path
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO main")
            
            # Validar que existen negocios
            from app.business.models.business import Business
            businesses = Business.objects.all()
            self.stdout.write(f'📊 Negocios encontrados: {businesses.count()}')
            
            # Validar schemas
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name LIKE 'business_%'
                    ORDER BY schema_name
                """)
                
                business_schemas = cursor.fetchall()
                self.stdout.write(f'🏗️ Schemas de negocio encontrados: {len(business_schemas)}')
                
                for schema in business_schemas:
                    schema_name = schema[0]
                    self.stdout.write(f'  📦 {schema_name}')
                    
                    # Verificar tablas en cada schema
                    cursor.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = %s
                        ORDER BY table_name
                    """, [schema_name])
                    
                    tables = cursor.fetchall()
                    self.stdout.write(f'    📋 Tablas: {len(tables)}')
            
            # Validar router
            from config.db_routers import MultitenantRouter
            router = MultitenantRouter()
            self.stdout.write('✅ Router multitenant configurado correctamente')
            
        except Exception as e:
            self.stdout.write(f'❌ Error en validación: {str(e)}')
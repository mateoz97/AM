# app/core/management/commands/clean_multitenant_setup.py
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Limpia completamente la configuración multitenant y reorganiza la arquitectura'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirmar que quieres eliminar TODOS los datos de negocios',
        )
        parser.add_argument(
            '--rename-schema',
            action='store_true',
            help='Renombrar schema public a main',
        )
        parser.add_argument(
            '--create-control-table',
            action='store_true',
            help='Crear tabla de control de schemas',
        )

    def handle(self, *args, **options):
        """Ejecuta la limpieza completa"""
        
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING('⚠️ ADVERTENCIA: Esta operación eliminará TODOS los negocios y schemas.')
            )
            self.stdout.write(
                self.style.WARNING('Para confirmar, ejecuta: --confirm')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS('🧹 LIMPIEZA COMPLETA MULTITENANT')
        )
        self.stdout.write('=' * 60)
        
        # Paso 1: Eliminar todos los negocios y usuarios de prueba
        self.clean_business_data()
        
        # Paso 2: Eliminar schemas de negocio
        self.clean_business_schemas()
        
        # Paso 3: Renombrar schema public a main si se solicita
        if options['rename_schema']:
            self.rename_public_schema()
        
        # Paso 4: Crear tabla de control si se solicita
        if options['create_control_table']:
            self.create_schema_control_table()
        
        # Paso 5: Limpiar tablas de negocio del schema principal
        self.clean_business_tables_from_main()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Limpieza completa finalizada')
        )

    def clean_business_data(self):
        """Elimina todos los negocios y usuarios de prueba"""
        self.stdout.write('🗑️ Eliminando negocios y usuarios de prueba...')
        
        try:
            # Asegurar que usamos el schema principal actual
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO public")
            
            # Eliminar usuarios de prueba
            test_users = [
                'juan_owner', 'maria_owner', 'carlos_owner', 
                'ana_customer', 'luis_customer'
            ]
            
            deleted_users = User.objects.filter(username__in=test_users).delete()
            self.stdout.write(f'  👥 Usuarios eliminados: {deleted_users[0]}')
            
            # Eliminar todos los negocios excepto los del admin/teo
            from app.business.models.business import Business
            
            # Mantener solo negocios de usuarios principales (admin, teo)
            keep_users = User.objects.filter(username__in=['admin', 'teo'])
            businesses_to_delete = Business.objects.exclude(owner__in=keep_users)
            
            deleted_businesses = businesses_to_delete.delete()
            self.stdout.write(f'  🏢 Negocios eliminados: {deleted_businesses[0]}')
            
            # Mostrar negocios que se mantienen
            remaining_businesses = Business.objects.all()
            self.stdout.write(f'  📋 Negocios restantes: {remaining_businesses.count()}')
            for business in remaining_businesses:
                self.stdout.write(f'    - {business.name} (ID: {business.id}) - {business.owner.username}')
        
        except Exception as e:
            self.stdout.write(f'❌ Error eliminando datos: {str(e)}')

    def clean_business_schemas(self):
        """Elimina todos los schemas de negocio"""
        self.stdout.write('🏗️ Eliminando schemas de negocio...')
        
        try:
            with connection.cursor() as cursor:
                # Obtener todos los schemas de negocio
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name LIKE 'business_%'
                    ORDER BY schema_name
                """)
                
                business_schemas = cursor.fetchall()
                self.stdout.write(f'  📦 Schemas encontrados: {len(business_schemas)}')
                
                for schema_tuple in business_schemas:
                    schema_name = schema_tuple[0]
                    
                    try:
                        # Terminar conexiones activas al schema
                        cursor.execute("""
                            SELECT pg_terminate_backend(pid)
                            FROM pg_stat_activity
                            WHERE datname = current_database()
                            AND pid <> pg_backend_pid()
                            AND query ILIKE %s
                        """, [f'%{schema_name}%'])
                        
                        # Eliminar el schema completamente
                        cursor.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
                        self.stdout.write(f'    ✅ Eliminado: {schema_name}')
                        
                    except Exception as e:
                        self.stdout.write(f'    ❌ Error eliminando {schema_name}: {str(e)}')
                
                # Verificar que se eliminaron
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name LIKE 'business_%'
                """)
                
                remaining_schemas = cursor.fetchall()
                if len(remaining_schemas) == 0:
                    self.stdout.write('  ✅ Todos los schemas de negocio eliminados')
                else:
                    self.stdout.write(f'  ⚠️ Schemas restantes: {len(remaining_schemas)}')
        
        except Exception as e:
            self.stdout.write(f'❌ Error eliminando schemas: {str(e)}')

    def rename_public_schema(self):
        """Renombra el schema public a main"""
        self.stdout.write('🔄 Renombrando schema public a main...')
        
        try:
            with connection.cursor() as cursor:
                # Verificar si el schema main ya existe
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = 'main'
                """)
                
                if cursor.fetchone():
                    self.stdout.write('  ⚠️ Schema "main" ya existe')
                    return
                
                # El schema public no se puede renombrar directamente en PostgreSQL
                # En su lugar, creamos el schema main y movemos las tablas
                cursor.execute("CREATE SCHEMA IF NOT EXISTS main")
                self.stdout.write('  ✅ Schema "main" creado')
                
                # Obtener todas las tablas del schema public (excluyendo system tables)
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                    AND table_name NOT LIKE 'pg_%'
                    AND table_name NOT LIKE 'sql_%'
                """)
                
                tables = cursor.fetchall()
                self.stdout.write(f'  📋 Moviendo {len(tables)} tablas a schema main...')
                
                for table_tuple in tables:
                    table_name = table_tuple[0]
                    try:
                        cursor.execute(f'ALTER TABLE public.{table_name} SET SCHEMA main')
                        self.stdout.write(f'    ✅ Movida: {table_name}')
                    except Exception as e:
                        self.stdout.write(f'    ❌ Error moviendo {table_name}: {str(e)}')
                
                # Actualizar search_path por defecto
                cursor.execute("ALTER DATABASE postgres SET search_path TO main, public")
                cursor.execute("SET search_path TO main, public")
                
                self.stdout.write('  ✅ Schema renombrado a "main"')
        
        except Exception as e:
            self.stdout.write(f'❌ Error renombrando schema: {str(e)}')

    def create_schema_control_table(self):
        """Crea la tabla de control de schemas de negocio"""
        self.stdout.write('📊 Creando tabla de control de schemas...')
        
        try:
            with connection.cursor() as cursor:
                # Asegurar que usamos el schema main
                cursor.execute("SET search_path TO main, public")
                
                # Crear tabla de control
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS main.business_schemas_control (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL UNIQUE,
                        business_name VARCHAR(255) NOT NULL,
                        schema_name VARCHAR(100) NOT NULL UNIQUE,
                        owner_username VARCHAR(150) NOT NULL,
                        business_type VARCHAR(50) DEFAULT 'restaurant',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        is_active BOOLEAN DEFAULT TRUE,
                        total_tables INTEGER DEFAULT 0,
                        total_records INTEGER DEFAULT 0,
                        last_activity TIMESTAMP WITH TIME ZONE,
                        notes TEXT,
                        
                        -- Constraints
                        CONSTRAINT valid_schema_name CHECK (schema_name LIKE 'business_%'),
                        CONSTRAINT valid_business_id CHECK (business_id > 0)
                    )
                """)
                
                # Crear índices
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_business_schemas_business_id 
                    ON main.business_schemas_control(business_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_business_schemas_schema_name 
                    ON main.business_schemas_control(schema_name)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_business_schemas_active 
                    ON main.business_schemas_control(is_active, created_at)
                """)
                
                # Crear función para actualizar updated_at automáticamente
                cursor.execute("""
                    CREATE OR REPLACE FUNCTION update_business_schemas_control_updated_at()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.updated_at = NOW();
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql
                """)
                
                # Crear trigger
                cursor.execute("""
                    DROP TRIGGER IF EXISTS trigger_update_business_schemas_control_updated_at 
                    ON main.business_schemas_control
                """)
                
                cursor.execute("""
                    CREATE TRIGGER trigger_update_business_schemas_control_updated_at
                        BEFORE UPDATE ON main.business_schemas_control
                        FOR EACH ROW
                        EXECUTE FUNCTION update_business_schemas_control_updated_at()
                """)
                
                self.stdout.write('  ✅ Tabla business_schemas_control creada')
                self.stdout.write('  ✅ Índices creados')
                self.stdout.write('  ✅ Triggers configurados')
                
                # Mostrar estructura de la tabla
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'main' 
                    AND table_name = 'business_schemas_control'
                    ORDER BY ordinal_position
                """)
                
                columns = cursor.fetchall()
                self.stdout.write('  📋 Estructura de la tabla:')
                for column in columns:
                    nullable = "NULL" if column[2] == "YES" else "NOT NULL"
                    default = f" DEFAULT {column[3]}" if column[3] else ""
                    self.stdout.write(f'    - {column[0]}: {column[1]} {nullable}{default}')
        
        except Exception as e:
            self.stdout.write(f'❌ Error creando tabla de control: {str(e)}')

    def clean_business_tables_from_main(self):
        """Elimina tablas de negocios del schema principal que ahora van en schemas individuales"""
        self.stdout.write('🧹 Limpiando tablas de negocios del schema principal...')
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO main, public")
                
                # Lista de tablas que deben eliminarse del schema principal
                # porque ahora van en schemas de negocio individuales
                tables_to_drop = [
                    # Tablas de negocios que ahora van en schemas individuales
                    'business_business',
                    'business_businessjoinrequest', 
                    'business_businessinvitation',
                    'business_businessbranch',
                    'business_business_co_owners',  # tabla de relación many-to-many
                    
                    # Tablas de inventario (van en schemas de negocio)
                    'inventory_product',
                    'inventory_productcategory', 
                    'inventory_stockmovement',
                    
                    # Tablas de órdenes (van en schemas de negocio)
                    'orders_order',
                    'orders_orderauditlog',
                    'orders_orderitem', 
                    'orders_ordernotification',
                    'orders_orderstatushistory',
                    
                    # Tablas de roles de negocio (van en schemas de negocio)
                    'roles_businessrole',
                    
                    # Tablas de configuraciones (van en schemas de negocio)
                    'settings_business_settings',
                    'settings_notification_template',
                    'settings_user_settings',
                ]
                
                self.stdout.write(f'  📋 Evaluando {len(tables_to_drop)} tablas para eliminar...')
                
                for table_name in tables_to_drop:
                    try:
                        # Verificar si la tabla existe
                        cursor.execute("""
                            SELECT table_name 
                            FROM information_schema.tables 
                            WHERE table_schema = 'main' 
                            AND table_name = %s
                        """, [table_name])
                        
                        if cursor.fetchone():
                            # La tabla existe, eliminarla
                            cursor.execute(f'DROP TABLE IF EXISTS main.{table_name} CASCADE')
                            self.stdout.write(f'    ✅ Eliminada: {table_name}')
                        else:
                            self.stdout.write(f'    ℹ️ No existe: {table_name}')
                            
                    except Exception as e:
                        self.stdout.write(f'    ❌ Error eliminando {table_name}: {str(e)}')
                
                # Verificar qué tablas quedan en el schema main
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'main' 
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                
                remaining_tables = cursor.fetchall()
                self.stdout.write(f'  📊 Tablas restantes en schema main: {len(remaining_tables)}')
                
                # Mostrar tablas por categoría
                auth_tables = [t[0] for t in remaining_tables if t[0].startswith('auth_') or t[0].startswith('django_')]
                user_tables = [t[0] for t in remaining_tables if 'user' in t[0] or 'account' in t[0]]
                role_tables = [t[0] for t in remaining_tables if 'role' in t[0]]
                other_tables = [t[0] for t in remaining_tables if t[0] not in auth_tables + user_tables + role_tables]
                
                if auth_tables:
                    self.stdout.write(f'    🔐 Auth/Django: {len(auth_tables)} tablas')
                if user_tables:
                    self.stdout.write(f'    👥 Usuarios: {len(user_tables)} tablas')
                if role_tables:
                    self.stdout.write(f'    👑 Roles: {len(role_tables)} tablas')
                if other_tables:
                    self.stdout.write(f'    📦 Otras: {len(other_tables)} tablas')
                    for table in other_tables:
                        self.stdout.write(f'      - {table}')
        
        except Exception as e:
            self.stdout.write(f'❌ Error limpiando tablas: {str(e)}')
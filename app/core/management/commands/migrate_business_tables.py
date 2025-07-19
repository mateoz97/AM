# app/core/management/commands/migrate_business_tables.py
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migra tablas específicas a schemas de negocio'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id',
            type=int,
            help='ID específico de negocio',
        )

    def handle(self, *args, **options):
        """Ejecuta las migraciones en schemas de negocio"""
        
        self.stdout.write(self.style.SUCCESS('🔧 MIGRANDO TABLAS A SCHEMAS DE NEGOCIO'))
        self.stdout.write('=' * 60)
        
        business_id = options.get('business_id')
        
        if business_id:
            self.migrate_single_business(business_id)
        else:
            self.migrate_all_businesses()

    def migrate_all_businesses(self):
        """Migra todas las businesses"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO main")
            
            from app.business.models.business import Business
            businesses = Business.objects.all()
            
            for business in businesses:
                self.migrate_single_business(business.id)
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))

    def migrate_single_business(self, business_id):
        """Migra un negocio específico"""
        schema_name = f'business_{business_id}'
        self.stdout.write(f'🏗️ Migrando schema: {schema_name}')
        
        try:
            # Verificar que el schema existe
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, [schema_name])
                
                if not cursor.fetchone():
                    self.stdout.write(f'❌ Schema {schema_name} no existe')
                    return
                
                # Configurar search_path
                cursor.execute(f"SET search_path TO {schema_name}, main")
                
                # Crear tablas manualmente
                self.create_business_tables(cursor, schema_name)
                
        except Exception as e:
            self.stdout.write(f'❌ Error migrando {schema_name}: {str(e)}')

    def create_business_tables(self, cursor, schema_name):
        """Crea las tablas específicas del negocio"""
        self.stdout.write(f'  📋 Creando tablas en {schema_name}...')
        
        # Tablas de roles
        self.stdout.write('    👥 Creando tablas de roles...')
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.roles_businessrole (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                display_name VARCHAR(100) NOT NULL,
                description TEXT,
                permissions TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.roles_rolepermission (
                id SERIAL PRIMARY KEY,
                business_role_id INTEGER REFERENCES {schema_name}.roles_businessrole(id),
                can_view_orders BOOLEAN DEFAULT FALSE,
                can_create_orders BOOLEAN DEFAULT FALSE,
                can_update_orders BOOLEAN DEFAULT FALSE,
                can_delete_orders BOOLEAN DEFAULT FALSE,
                can_manage_inventory BOOLEAN DEFAULT FALSE,
                can_view_reports BOOLEAN DEFAULT FALSE,
                can_manage_users BOOLEAN DEFAULT FALSE,
                can_manage_settings BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        # Tablas de inventario
        self.stdout.write('    📦 Creando tablas de inventario...')
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.inventory_category (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.inventory_product (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                sku VARCHAR(50),
                category_id INTEGER REFERENCES {schema_name}.inventory_category(id),
                price DECIMAL(10,2) DEFAULT 0.00,
                cost DECIMAL(10,2) DEFAULT 0.00,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.inventory_stock (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES {schema_name}.inventory_product(id),
                quantity INTEGER DEFAULT 0,
                min_quantity INTEGER DEFAULT 0,
                max_quantity INTEGER DEFAULT 1000,
                last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.inventory_stockmovement (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES {schema_name}.inventory_product(id),
                movement_type VARCHAR(20) NOT NULL,
                quantity INTEGER NOT NULL,
                reason TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                created_by_id INTEGER
            )
        """)
        
        # Tablas de órdenes
        self.stdout.write('    🛒 Creando tablas de órdenes...')
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.orders_order (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                order_number VARCHAR(20) UNIQUE NOT NULL,
                business_id INTEGER NOT NULL,
                customer_id INTEGER,
                status VARCHAR(20) DEFAULT 'pending',
                priority VARCHAR(20) DEFAULT 'normal',
                order_type VARCHAR(20) DEFAULT 'dine_in',
                table_number VARCHAR(10),
                customer_name VARCHAR(100),
                customer_phone VARCHAR(20),
                delivery_address TEXT,
                subtotal DECIMAL(10,2) DEFAULT 0.00,
                tax_amount DECIMAL(10,2) DEFAULT 0.00,
                discount_amount DECIMAL(10,2) DEFAULT 0.00,
                delivery_fee DECIMAL(10,2) DEFAULT 0.00,
                total_amount DECIMAL(10,2) DEFAULT 0.00,
                waiter_id INTEGER,
                chef_id INTEGER,
                estimated_preparation_time INTERVAL,
                customer_notes TEXT,
                kitchen_notes TEXT,
                internal_notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                confirmed_at TIMESTAMP WITH TIME ZONE,
                started_at TIMESTAMP WITH TIME ZONE,
                ready_at TIMESTAMP WITH TIME ZONE,
                paid_at TIMESTAMP WITH TIME ZONE,
                delivered_at TIMESTAMP WITH TIME ZONE,
                cancelled_at TIMESTAMP WITH TIME ZONE,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.orders_orderitem (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                order_id UUID REFERENCES {schema_name}.orders_order(id),
                product_name VARCHAR(200) NOT NULL,
                product_description TEXT,
                quantity INTEGER DEFAULT 1,
                unit_price DECIMAL(10,2) NOT NULL,
                total_price DECIMAL(10,2) NOT NULL,
                modifications TEXT,
                cooking_instructions TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                started_cooking_at TIMESTAMP WITH TIME ZONE,
                finished_cooking_at TIMESTAMP WITH TIME ZONE
            )
        """)
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.orders_orderstatushistory (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                order_id UUID REFERENCES {schema_name}.orders_order(id),
                old_status VARCHAR(20) NOT NULL,
                new_status VARCHAR(20) NOT NULL,
                changed_by_id INTEGER,
                notes TEXT,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.orders_ordernotification (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                order_id UUID REFERENCES {schema_name}.orders_order(id),
                message TEXT NOT NULL,
                notification_type VARCHAR(50) NOT NULL,
                target_roles JSONB DEFAULT '[]',
                is_read BOOLEAN DEFAULT FALSE,
                is_sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                sent_at TIMESTAMP WITH TIME ZONE
            )
        """)
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.orders_orderauditlog (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                order_id UUID REFERENCES {schema_name}.orders_order(id),
                action VARCHAR(20) NOT NULL,
                user_id INTEGER,
                old_values JSONB,
                new_values JSONB,
                details TEXT,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                ip_address INET,
                user_agent TEXT
            )
        """)
        
        # Tablas de configuraciones
        self.stdout.write('    ⚙️ Creando tablas de configuraciones...')
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.settings_businesssettings (
                id SERIAL PRIMARY KEY,
                business_id INTEGER UNIQUE NOT NULL,
                auto_logout_time INTEGER DEFAULT 30,
                session_timeout INTEGER DEFAULT 60,
                require_two_factor BOOLEAN DEFAULT FALSE,
                allow_customer_registration BOOLEAN DEFAULT TRUE,
                require_order_confirmation BOOLEAN DEFAULT TRUE,
                enable_table_service BOOLEAN DEFAULT TRUE,
                enable_takeaway BOOLEAN DEFAULT TRUE,
                enable_delivery BOOLEAN DEFAULT FALSE,
                low_stock_threshold INTEGER DEFAULT 5,
                auto_deduct_inventory BOOLEAN DEFAULT TRUE,
                daily_report_time TIME,
                weekly_report_day INTEGER DEFAULT 1,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                created_by_id INTEGER
            )
        """)
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.settings_notificationtemplate (
                id SERIAL PRIMARY KEY,
                business_id INTEGER NOT NULL,
                notification_type VARCHAR(50) NOT NULL,
                title VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(business_id, notification_type)
            )
        """)
        
        # Crear índices
        self.stdout.write('    📊 Creando índices...')
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{schema_name}_orders_status 
            ON {schema_name}.orders_order(status, created_at)
        """)
        
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{schema_name}_orders_business 
            ON {schema_name}.orders_order(business_id, status)
        """)
        
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{schema_name}_inventory_product_active 
            ON {schema_name}.inventory_product(is_active)
        """)
        
        self.stdout.write(f'  ✅ Tablas creadas exitosamente en {schema_name}')
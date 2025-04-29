from django.core.management.base import BaseCommand
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.conf import settings

class Command(BaseCommand):
    help = 'Realiza migraciones iniciales para la aplicación de Business'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fake', 
            action='store_true',
            help='Marca las migraciones como realizadas sin ejecutarlas realmente',
        )

    def handle(self, *args, **options):
        fake = options['fake']
        
        self.stdout.write(self.style.SUCCESS(
            f"Iniciando migraciones iniciales. Fake={fake}"
        ))
        
        # Paso 1: Aplicar migraciones en la base de datos principal
        self.stdout.write("1. Aplicando migraciones en base de datos 'default'...")
        
        try:
            from django.core.management import call_command
            call_command('migrate', database='default')
            self.stdout.write(self.style.SUCCESS("   ✅ Migraciones en default completadas"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Error al migrar default: {str(e)}"))
            return
        
        # Paso 2: Verificar y crear la tabla Business si no existe
        self.stdout.write("2. Verificando tabla 'business_business'...")
        
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='business_business';
                """)
                table_exists = bool(cursor.fetchone())
                
                if not table_exists:
                    self.stdout.write("   ⚠️ Tabla 'business_business' no encontrada, creando...")
                    cursor.execute("""
                        CREATE TABLE "business_business" (
                            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                            "name" varchar(255) NOT NULL UNIQUE,
                            "is_main_business" bool NOT NULL,
                            "created_at" datetime NOT NULL,
                            "is_active" bool NOT NULL,
                            "updated_at" datetime NOT NULL,
                            "description" text NULL,
                            "address" varchar(255) NULL,
                            "phone" varchar(20) NULL,
                            "email" varchar(254) NULL,
                            "website" varchar(200) NULL,
                            "logo" varchar(100) NULL,
                            "owner_id" integer NULL REFERENCES "accounts_customuser" ("id") DEFERRABLE INITIALLY DEFERRED
                        );
                    """)
                    self.stdout.write(self.style.SUCCESS("   ✅ Tabla 'business_business' creada correctamente"))
                else:
                    self.stdout.write(self.style.SUCCESS("   ✅ Tabla 'business_business' ya existe"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Error al verificar/crear tabla: {str(e)}"))
            return
        
        # Paso 3: Verificar bases de datos de negocios existentes
        self.stdout.write("3. Verificando bases de datos de negocios existentes...")
        business_dbs = []
        
        # Obtener todas las bases de datos business_*
        for db_name in settings.DATABASES:
            if db_name.startswith('business_'):
                business_dbs.append(db_name)
        
        if business_dbs:
            self.stdout.write(f"   Encontradas {len(business_dbs)} bases de datos de negocios")
            for db_name in business_dbs:
                self.stdout.write(f"   - Migrando {db_name}...")
                try:
                    call_command('migrate', database=db_name)
                    self.stdout.write(self.style.SUCCESS(f"     ✅ Migración de {db_name} completada"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"     ❌ Error al migrar {db_name}: {str(e)}"))
        else:
            self.stdout.write("   No se encontraron bases de datos de negocios")
        
        # Paso 4: Marcar las migraciones como aplicadas si se solicita
        if fake:
            self.stdout.write("4. Marcando migraciones como aplicadas (fake)...")
            try:
                executor = MigrationExecutor(connections['default'])
                if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                    call_command('migrate', fake=True)
                    self.stdout.write(self.style.SUCCESS("   ✅ Migraciones marcadas como aplicadas"))
                else:
                    self.stdout.write("   ℹ️ No hay migraciones pendientes para marcar")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Error al marcar migraciones: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS("Proceso de migración inicial completado"))
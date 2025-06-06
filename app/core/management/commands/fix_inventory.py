# CREAR ARCHIVO: app/inventory/management/commands/fix_inventory.py
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Corrige la configuración del módulo de inventario'

    def handle(self, *args, **options):
        self.stdout.write("🔧 Iniciando corrección del módulo de inventario...")
        
        # 1. Crear migraciones para inventory
        try:
            self.stdout.write("📝 Creando migraciones para inventory...")
            call_command('makemigrations', 'inventory', verbosity=1)
            self.stdout.write("✅ Migraciones creadas")
        except Exception as e:
            self.stdout.write(f"⚠️ Advertencia en migraciones: {e}")
        
        # 2. Ejecutar migraciones en default
        try:
            self.stdout.write("🚀 Ejecutando migraciones en default...")
            call_command('migrate', 'inventory', verbosity=1)
            self.stdout.write("✅ Migraciones ejecutadas en default")
        except Exception as e:
            self.stdout.write(f"❌ Error en migraciones default: {e}")
        
        # 3. Migrar a todas las bases de datos de negocios
        try:
            self.stdout.write("🏢 Migrando bases de datos de negocios...")
            for db_name in settings.DATABASES:
                if db_name.startswith('business_'):
                    try:
                        call_command('migrate', 'inventory', database=db_name, verbosity=0)
                        self.stdout.write(f"✅ {db_name} migrado")
                    except Exception as e:
                        self.stdout.write(f"⚠️ Error en {db_name}: {e}")
        except Exception as e:
            self.stdout.write(f"⚠️ Advertencia en migración multi-tenant: {e}")
        
        self.stdout.write("🎉 Corrección del módulo de inventario completada")
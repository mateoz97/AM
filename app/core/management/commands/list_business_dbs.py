from django.core.management.base import BaseCommand
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Lista todas las bases de datos de negocios existentes'

    def handle(self, *args, **options):
        # Listar configuración en settings
        self.stdout.write(self.style.SUCCESS("Bases de datos configuradas en settings:"))
        for db_name, db_config in settings.DATABASES.items():
            if db_name.startswith('business_'):
                self.stdout.write(f"  - {db_name}: {db_config['NAME']}")
        
        # Buscar archivos físicos
        self.stdout.write("\n" + self.style.SUCCESS("Archivos de base de datos encontrados:"))
        db_files = []
        for file in os.listdir(settings.BASE_DIR):
            if file.startswith('db_business_') and file.endswith('.sqlite3'):
                db_path = settings.BASE_DIR / file
                size = os.path.getsize(db_path)
                db_files.append((file, size))
        
        # Ordenar por tamaño
        db_files.sort(key=lambda x: x[1], reverse=True)
        
        if db_files:
            for file, size in db_files:
                self.stdout.write(f"  - {file} ({size/1024:.1f} KB)")
        else:
            self.stdout.write(self.style.WARNING("  No se encontraron archivos de base de datos de negocios."))
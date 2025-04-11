from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Ejecuta migraciones en todas las bases de datos de negocios'

    def handle(self, *args, **options):
        # Migrar primero la base de datos default
        self.stdout.write("Migrando base de datos default...")
        call_command('migrate', database='default')
        
        # Migrar todas las bases de datos que comienzan con 'business_'
        for db_name in settings.DATABASES:
            if db_name.startswith('business_'):
                self.stdout.write(f"Migrando {db_name}...")
                try:
                    call_command('migrate', database=db_name)
                    self.stdout.write(self.style.SUCCESS(f"Migración de {db_name} completada."))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"Error al migrar {db_name}: {str(e)}"
                    ))
                
        self.stdout.write(self.style.SUCCESS('Migración de todas las bases de datos completada.'))
from django.core.management.base import BaseCommand
from django.conf import settings
import os
from app.business.models.business import Business

class Command(BaseCommand):
    help = 'Limpia y sincroniza las bases de datos de negocios'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar eliminación de archivos huérfanos',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        # Obtener todos los negocios activos
        businesses = Business.objects.filter(is_active=True)
        valid_db_names = {f"business_{b.id}" for b in businesses}
        
        # Comprobar bases de datos en settings
        self.stdout.write(self.style.SUCCESS("Verificando bases de datos en settings.DATABASES:"))
        for db_name in list(settings.DATABASES.keys()):
            if db_name.startswith('business_') and db_name not in valid_db_names:
                self.stdout.write(self.style.WARNING(f"  - {db_name}: No corresponde a un negocio activo"))
                if force:
                    del settings.DATABASES[db_name]
                    self.stdout.write(self.style.SUCCESS("    ✓ Eliminada de settings.DATABASES"))
        
        # Comprobar archivos de base de datos
        self.stdout.write(self.style.SUCCESS("\nVerificando archivos de base de datos:"))
        for file in os.listdir(settings.BASE_DIR):
            if file.startswith('db_business_') and file.endswith('.sqlite3'):
                # Extraer ID del negocio del nombre del archivo
                try:
                    db_name = file[3:-8]  # Quitar 'db_' del principio y '.sqlite3' del final
                    if db_name not in valid_db_names:
                        self.stdout.write(self.style.WARNING(f"  - {file}: No corresponde a un negocio activo"))
                        if force:
                            os.remove(settings.BASE_DIR / file)
                            self.stdout.write(self.style.SUCCESS("    ✓ Archivo eliminado"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  - Error al procesar {file}: {str(e)}"))
        
        # Verificar bases de datos faltantes
        self.stdout.write(self.style.SUCCESS("\nVerificando negocios sin base de datos:"))
        for business in businesses:
            db_name = f"business_{business.id}"
            db_file = f"db_{db_name}.sqlite3"
            db_path = settings.BASE_DIR / db_file
            
            missing_file = not os.path.exists(db_path)
            missing_settings = db_name not in settings.DATABASES
            
            if missing_file or missing_settings:
                self.stdout.write(self.style.WARNING(
                    f"  - Negocio {business.name} (ID: {business.id}): "
                    f"{'Sin archivo de base de datos' if missing_file else ''}"
                    f"{' y ' if missing_file and missing_settings else ''}"
                    f"{'No configurada en settings' if missing_settings else ''}"
                ))
                
                if force:
                    from app.business.services.business_service import DatabaseService
                    success = DatabaseService.create_business_database(business)
                    if success:
                        self.stdout.write(self.style.SUCCESS("    ✓ Base de datos creada correctamente"))
                    else:
                        self.stdout.write(self.style.ERROR("    ✗ Error al crear la base de datos"))
                        
        if not force:
            self.stdout.write(self.style.WARNING(
                "\nUtiliza --force para realizar las acciones de limpieza y corrección"
            ))
# app/core/management/commands/create_business_schema.py
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from app.business.models.business import Business
from app.business.services.business_service import DatabaseService


class Command(BaseCommand):
    help = 'Crea un esquema PostgreSQL para un negocio específico'

    def add_arguments(self, parser):
        parser.add_argument('business_id', type=int, help='ID del negocio')
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar creación incluso si el esquema ya existe'
        )

    def handle(self, *args, **options):
        business_id = options['business_id']
        force = options['force']
        
        try:
            business = Business.objects.get(id=business_id)
            schema_name = f"business_{business_id}"
            
            # Verificar si el esquema ya existe
            success, result = DatabaseService.verify_business_database(business_id)
            
            if success and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f'El esquema {schema_name} ya existe para el negocio "{business.name}". '
                        f'Usa --force para recrear.'
                    )
                )
                return
            
            # Crear el esquema
            self.stdout.write(f'Creando esquema {schema_name} para negocio "{business.name}"...')
            
            if DatabaseService.create_business_database(business):
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Esquema {schema_name} creado exitosamente para el negocio "{business.name}"'
                    )
                )
                
                # Mostrar información del esquema creado
                success, info = DatabaseService.verify_business_database(business_id)
                if success:
                    self.stdout.write(f'Esquema: {info["schema_name"]}')
                    self.stdout.write(f'Tablas: {info["table_count"]}')
                    
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Error al crear esquema para el negocio "{business.name}"'
                    )
                )
                
        except Business.DoesNotExist:
            raise CommandError(f'No existe un negocio con ID {business_id}')
        except Exception as e:
            raise CommandError(f'Error inesperado: {str(e)}')
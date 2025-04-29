from django.core.management.base import BaseCommand
from app.business.models.business import Business
from app.business.services.business_service import DatabaseService

class Command(BaseCommand):
    help = 'Prueba la creación de base de datos para un business existente'

    def add_arguments(self, parser):
        parser.add_argument('business_id', type=int, help='ID del business')

    def handle(self, *args, **options):
        business_id = options['business_id']
        
        try:
            business = Business.objects.get(id=business_id)
            self.stdout.write(f"Probando creación de BD para: {business.name} (ID: {business.id})")
            
            success = DatabaseService.create_business_database(business)
            
            if success:
                self.stdout.write(self.style.SUCCESS(
                    f'✅ Base de datos creada exitosamente para "{business.name}"'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f'❌ Error al crear base de datos para "{business.name}"'
                ))
        except Business.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Business con ID {business_id} no existe'))
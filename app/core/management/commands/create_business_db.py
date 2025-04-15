from django.core.management.base import BaseCommand
from app.auth_app.models import Business
from app.auth_app.services import DatabaseService

class Command(BaseCommand):
    help = 'Crea base de datos para un business existente'

    def add_arguments(self, parser):
        parser.add_argument('business_id', type=int, help='ID del business')

    def handle(self, *args, **options):
        business_id = options['business_id']
        
        try:
            business = Business.objects.get(id=business_id)
            success = DatabaseService.create_business_database(business)
            
            if success:
                self.stdout.write(self.style.SUCCESS(
                    f'Base de datos creada para business "{business.name}" (ID: {business.id})'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f'Error al crear base de datos para business "{business.name}"'
                ))
        except Business.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Business con ID {business_id} no existe'))
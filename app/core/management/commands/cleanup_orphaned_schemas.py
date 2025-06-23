# app/core/management/commands/cleanup_orphaned_schemas.py
from django.core.management.base import BaseCommand
from django.db import connection
from app.business.models.business import Business
from app.business.services.business_service import DatabaseService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Limpia esquemas de negocios huérfanos (que no tienen un negocio correspondiente)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra qué esquemas se eliminarían sin hacerlo realmente',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Fuerza la eliminación sin confirmación',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(
            self.style.WARNING('🧹 Iniciando limpieza de esquemas huérfanos...')
        )
        
        # Obtener todos los esquemas de negocios
        business_schemas = DatabaseService.list_business_schemas()
        
        if not business_schemas:
            self.stdout.write(
                self.style.SUCCESS('✅ No se encontraron esquemas de negocios.')
            )
            return
        
        # Obtener todos los IDs de negocios existentes
        existing_business_ids = set(
            Business.objects.values_list('id', flat=True)
        )
        
        # Encontrar esquemas huérfanos
        orphaned_schemas = []
        for schema_info in business_schemas:
            business_id = schema_info['business_id']
            schema_name = schema_info['schema_name']
            
            if business_id and business_id not in existing_business_ids:
                orphaned_schemas.append(schema_info)
                
        if not orphaned_schemas:
            self.stdout.write(
                self.style.SUCCESS('✅ No se encontraron esquemas huérfanos.')
            )
            return
        
        # Mostrar esquemas huérfanos encontrados
        self.stdout.write(
            self.style.WARNING(f'⚠️ Encontrados {len(orphaned_schemas)} esquemas huérfanos:')
        )
        
        for schema_info in orphaned_schemas:
            self.stdout.write(f"  - {schema_info['schema_name']} (Business ID: {schema_info['business_id']})")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🏃 Modo dry-run: No se eliminará nada.')
            )
            return
        
        # Pedir confirmación si no se usa --force
        if not force:
            confirm = input(
                f'\n⚠️ ¿Estás seguro de que quieres eliminar {len(orphaned_schemas)} esquemas? '
                'Esta operación es IRREVERSIBLE (y/N): '
            )
            if confirm.lower() not in ['y', 'yes', 's', 'si', 'sí']:
                self.stdout.write(
                    self.style.WARNING('❌ Operación cancelada.')
                )
                return
        
        # Eliminar esquemas huérfanos
        deleted_count = 0
        failed_count = 0
        
        for schema_info in orphaned_schemas:
            business_id = schema_info['business_id']
            schema_name = schema_info['schema_name']
            
            self.stdout.write(f'🗑️ Eliminando {schema_name}...')
            
            try:
                success = DatabaseService.delete_business_schema(business_id)
                if success:
                    deleted_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ {schema_name} eliminado exitosamente')
                    )
                else:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'❌ Error al eliminar {schema_name}')
                    )
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ Error al eliminar {schema_name}: {str(e)}')
                )
        
        # Resumen final
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS(f'✅ Eliminados: {deleted_count} esquemas')
        )
        if failed_count > 0:
            self.stdout.write(
                self.style.ERROR(f'❌ Fallidos: {failed_count} esquemas')
            )
        
        self.stdout.write(
            self.style.SUCCESS('🎉 Limpieza de esquemas huérfanos completada.')
        )
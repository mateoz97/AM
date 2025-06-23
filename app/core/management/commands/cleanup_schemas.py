# app/core/management/commands/cleanup_schemas.py
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from app.business.models.business import Business


class Command(BaseCommand):
    help = 'Limpia esquemas huérfanos (sin negocio asociado) en PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se eliminaría sin hacer cambios reales'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Eliminar esquemas sin confirmación'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        try:
            # Obtener todos los esquemas de negocios
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name LIKE 'business_%'
                    ORDER BY schema_name;
                """)
                
                schemas = [row[0] for row in cursor.fetchall()]
                
                if not schemas:
                    self.stdout.write(
                        self.style.SUCCESS('No hay esquemas de negocios para revisar')
                    )
                    return
                
                orphaned_schemas = []
                
                # Verificar cada esquema
                for schema in schemas:
                    business_id = schema.replace('business_', '')
                    
                    if not business_id.isdigit():
                        continue
                    
                    try:
                        business = Business.objects.get(id=int(business_id))
                        if not business.is_active:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'⚠️ {schema} - Negocio inactivo: {business.name}'
                                )
                            )
                    except Business.DoesNotExist:
                        orphaned_schemas.append(schema)
                        self.stdout.write(
                            self.style.ERROR(
                                f'❌ {schema} - Negocio no existe (huérfano)'
                            )
                        )
                
                if not orphaned_schemas:
                    self.stdout.write(
                        self.style.SUCCESS('✅ No se encontraron esquemas huérfanos')
                    )
                    return
                
                self.stdout.write(
                    f'\n🗑️ Encontrados {len(orphaned_schemas)} esquemas huérfanos:'
                )
                
                for schema in orphaned_schemas:
                    # Contar tablas
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM information_schema.tables 
                        WHERE table_schema = %s;
                    """, [schema])
                    
                    table_count = cursor.fetchone()[0]
                    self.stdout.write(f'   - {schema} ({table_count} tablas)')
                
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            '\n🔍 Modo dry-run: no se realizarán cambios'
                        )
                    )
                    return
                
                # Confirmar eliminación
                if not force:
                    confirm = input(
                        f'\n¿Eliminar {len(orphaned_schemas)} esquemas huérfanos? [y/N]: '
                    )
                    if confirm.lower() != 'y':
                        self.stdout.write('Operación cancelada')
                        return
                
                # Eliminar esquemas huérfanos
                deleted_count = 0
                
                with transaction.atomic():
                    for schema in orphaned_schemas:
                        try:
                            cursor.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
                            deleted_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'✅ Eliminado: {schema}')
                            )
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'❌ Error al eliminar {schema}: {str(e)}'
                                )
                            )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n🎉 Limpieza completada: {deleted_count}/{len(orphaned_schemas)} esquemas eliminados'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error durante la limpieza: {str(e)}')
            )
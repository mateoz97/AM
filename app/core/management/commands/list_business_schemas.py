# app/core/management/commands/list_business_schemas.py
from django.core.management.base import BaseCommand
from django.db import connection
from app.business.models.business import Business


class Command(BaseCommand):
    help = 'Lista todos los esquemas de negocios en PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Mostrar información detallada de cada esquema'
        )

    def handle(self, *args, **options):
        detailed = options['detailed']
        
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
                        self.style.WARNING('No se encontraron esquemas de negocios')
                    )
                    return
                
                self.stdout.write(
                    self.style.SUCCESS(f'Encontrados {len(schemas)} esquemas de negocios:')
                )
                
                for schema in schemas:
                    # Extraer business_id del nombre del esquema
                    business_id = schema.replace('business_', '')
                    
                    try:
                        business = Business.objects.get(id=business_id)
                        business_name = business.name
                        is_active = "✅ Activo" if business.is_active else "❌ Inactivo"
                    except Business.DoesNotExist:
                        business_name = "⚠️ Negocio no encontrado"
                        is_active = "❓ Desconocido"
                    
                    self.stdout.write(f'\n📂 {schema}')
                    self.stdout.write(f'   Negocio: {business_name}')
                    self.stdout.write(f'   Estado: {is_active}')
                    
                    if detailed:
                        # Contar tablas en el esquema
                        cursor.execute("""
                            SELECT COUNT(*) 
                            FROM information_schema.tables 
                            WHERE table_schema = %s;
                        """, [schema])
                        
                        table_count = cursor.fetchone()[0]
                        self.stdout.write(f'   Tablas: {table_count}')
                        
                        if table_count > 0:
                            cursor.execute("""
                                SELECT table_name 
                                FROM information_schema.tables 
                                WHERE table_schema = %s
                                ORDER BY table_name;
                            """, [schema])
                            
                            tables = [row[0] for row in cursor.fetchall()]
                            self.stdout.write(f'   Tablas: {", ".join(tables)}')
                
                self.stdout.write(f'\n📊 Total: {len(schemas)} esquemas')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error al listar esquemas: {str(e)}')
            )
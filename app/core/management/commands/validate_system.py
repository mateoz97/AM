# app/core/management/commands/validate_system.py
from django.core.management.base import BaseCommand
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import time
import psutil
import gc


class Command(BaseCommand):
    help = 'Valida la integridad y performance del sistema multitenant'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-schemas',
            action='store_true',
            help='Verificar integridad de esquemas PostgreSQL',
        )
        parser.add_argument(
            '--check-performance',
            action='store_true',
            help='Verificar performance del sistema',
        )
        parser.add_argument(
            '--check-memory',
            action='store_true',
            help='Verificar uso de memoria',
        )
        parser.add_argument(
            '--fix-issues',
            action='store_true',
            help='Intentar reparar problemas encontrados',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Ejecutar todas las validaciones',
        )

    def handle(self, *args, **options):
        """Ejecuta las validaciones del sistema"""
        
        self.stdout.write(
            self.style.SUCCESS('🔍 VALIDACIÓN DE SISTEMA MULTITENANT')
        )
        self.stdout.write('=' * 60)
        
        issues_found = []
        
        # Ejecutar validaciones
        if options['all'] or options['check_schemas']:
            issues_found.extend(self.validate_schemas())
        
        if options['all'] or options['check_performance']:
            issues_found.extend(self.validate_performance())
        
        if options['all'] or options['check_memory']:
            issues_found.extend(self.validate_memory())
        
        # Mostrar resumen
        self.show_validation_summary(issues_found)
        
        # Reparar problemas si se solicita
        if options['fix_issues'] and issues_found:
            self.fix_issues(issues_found)
    
    def validate_schemas(self):
        """Valida la integridad de los esquemas PostgreSQL"""
        self.stdout.write('\n🗄️ VALIDANDO ESQUEMAS POSTGRESQL')
        self.stdout.write('-' * 40)
        
        issues = []
        
        try:
            from app.business.services.business_service import DatabaseService
            from app.business.models.business import Business
            
            # Obtener todos los negocios
            businesses = Business.objects.all()
            self.stdout.write(f'📊 Validando {businesses.count()} negocios...')
            
            # Obtener esquemas existentes
            existing_schemas = DatabaseService.list_business_schemas()
            schema_names = [s['schema_name'] for s in existing_schemas]
            
            # Validar cada negocio
            for business in businesses:
                expected_schema = f'business_{business.id}'
                
                if expected_schema not in schema_names:
                    issue = {
                        'type': 'missing_schema',
                        'business_id': business.id,
                        'business_name': business.name,
                        'schema_name': expected_schema,
                        'severity': 'high'
                    }
                    issues.append(issue)
                    self.stdout.write(
                        self.style.ERROR(f'❌ Esquema faltante: {expected_schema}')
                    )
                else:
                    # Verificar integridad del esquema
                    exists, info = DatabaseService.verify_business_database(business.id)
                    if not exists:
                        issue = {
                            'type': 'corrupted_schema',
                            'business_id': business.id,
                            'business_name': business.name,
                            'schema_name': expected_schema,
                            'severity': 'high'
                        }
                        issues.append(issue)
                        self.stdout.write(
                            self.style.ERROR(f'❌ Esquema corrupto: {expected_schema}')
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(f'✅ Esquema válido: {expected_schema}')
                        )
            
            # Validar esquemas huérfanos
            for schema in existing_schemas:
                if schema['business_id']:
                    if not Business.objects.filter(id=schema['business_id']).exists():
                        issue = {
                            'type': 'orphaned_schema',
                            'schema_name': schema['schema_name'],
                            'business_id': schema['business_id'],
                            'severity': 'medium'
                        }
                        issues.append(issue)
                        self.stdout.write(
                            self.style.WARNING(f'⚠️ Esquema huérfano: {schema["schema_name"]}')
                        )
            
            # Validar conexiones PostgreSQL
            self.validate_database_connections(issues)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'💥 Error validando esquemas: {str(e)}')
            )
            issues.append({
                'type': 'validation_error',
                'error': str(e),
                'severity': 'high'
            })
        
        return issues
    
    def validate_database_connections(self, issues):
        """Valida las conexiones de base de datos"""
        self.stdout.write('\n🔗 VALIDANDO CONEXIONES DE BASE DE DATOS')
        
        try:
            # Verificar conexión principal
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result[0] == 1:
                    self.stdout.write('✅ Conexión principal OK')
                else:
                    issues.append({
                        'type': 'connection_error',
                        'database': 'main',
                        'severity': 'high'
                    })
            
            # Verificar configuración de conexión
            db_config = settings.DATABASES['default']
            if db_config.get('CONN_MAX_AGE', 0) < 300:
                issues.append({
                    'type': 'connection_config',
                    'issue': 'CONN_MAX_AGE muy bajo',
                    'severity': 'medium'
                })
                self.stdout.write('⚠️ CONN_MAX_AGE configurado muy bajo')
            
            # Verificar pool de conexiones
            if not db_config.get('OPTIONS', {}).get('MAX_CONNS'):
                issues.append({
                    'type': 'connection_pool',
                    'issue': 'MAX_CONNS no configurado',
                    'severity': 'medium'
                })
                self.stdout.write('⚠️ Pool de conexiones no configurado')
            
        except Exception as e:
            self.stdout.write(f'❌ Error de conexión: {str(e)}')
            issues.append({
                'type': 'connection_error',
                'error': str(e),
                'severity': 'high'
            })
    
    def validate_performance(self):
        """Valida la performance del sistema"""
        self.stdout.write('\n⚡ VALIDANDO PERFORMANCE')
        self.stdout.write('-' * 40)
        
        issues = []
        
        try:
            # Test de queries
            self.test_query_performance(issues)
            
            # Test de cache
            self.test_cache_performance(issues)
            
            # Test de State Machine
            self.test_state_machine_performance(issues)
            
        except Exception as e:
            self.stdout.write(f'💥 Error validando performance: {str(e)}')
            issues.append({
                'type': 'performance_error',
                'error': str(e),
                'severity': 'high'
            })
        
        return issues
    
    def test_query_performance(self, issues):
        """Test de performance de queries"""
        self.stdout.write('📊 Testing query performance...')
        
        # Test query simple
        start_time = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM accounts_customuser")
            cursor.fetchone()
        duration = time.time() - start_time
        
        if duration > 1.0:
            issues.append({
                'type': 'slow_query',
                'query': 'user_count',
                'duration': duration,
                'severity': 'medium'
            })
            self.stdout.write(f'⚠️ Query lenta: {duration:.2f}s')
        else:
            self.stdout.write(f'✅ Query rápida: {duration:.2f}s')
        
        # Test query compleja
        start_time = time.time()
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT b.name, COUNT(o.id) as order_count
                FROM business_business b
                LEFT JOIN orders_order o ON b.id = o.business_id
                GROUP BY b.id, b.name
                LIMIT 10
            """)
            cursor.fetchall()
        duration = time.time() - start_time
        
        if duration > 2.0:
            issues.append({
                'type': 'slow_complex_query',
                'duration': duration,
                'severity': 'medium'
            })
            self.stdout.write(f'⚠️ Query compleja lenta: {duration:.2f}s')
        else:
            self.stdout.write(f'✅ Query compleja rápida: {duration:.2f}s')
    
    def test_cache_performance(self, issues):
        """Test de performance de cache"""
        self.stdout.write('💾 Testing cache performance...')
        
        # Test escritura
        start_time = time.time()
        cache.set('performance_test', 'test_value', 60)
        write_duration = time.time() - start_time
        
        # Test lectura
        start_time = time.time()
        value = cache.get('performance_test')
        read_duration = time.time() - start_time
        
        if write_duration > 0.1:
            issues.append({
                'type': 'slow_cache_write',
                'duration': write_duration,
                'severity': 'medium'
            })
            self.stdout.write(f'⚠️ Cache write lento: {write_duration:.3f}s')
        
        if read_duration > 0.05:
            issues.append({
                'type': 'slow_cache_read',
                'duration': read_duration,
                'severity': 'medium'
            })
            self.stdout.write(f'⚠️ Cache read lento: {read_duration:.3f}s')
        
        if value == 'test_value':
            self.stdout.write('✅ Cache funcionando correctamente')
        else:
            issues.append({
                'type': 'cache_malfunction',
                'severity': 'high'
            })
            self.stdout.write('❌ Cache no funciona correctamente')
        
        # Limpiar
        cache.delete('performance_test')
    
    def test_state_machine_performance(self, issues):
        """Test de performance de State Machine"""
        self.stdout.write('🔄 Testing State Machine performance...')
        
        try:
            from app.orders.state_machine import OrderStateMachine, OrderState
            
            # Test múltiples validaciones
            state_machine = OrderStateMachine()
            
            start_time = time.time()
            for i in range(1000):
                state_machine.can_transition(OrderState.PENDING, OrderState.CONFIRMED)
            duration = time.time() - start_time
            
            if duration > 1.0:
                issues.append({
                    'type': 'slow_state_machine',
                    'duration': duration,
                    'severity': 'medium'
                })
                self.stdout.write(f'⚠️ State Machine lento: {duration:.2f}s')
            else:
                self.stdout.write(f'✅ State Machine rápido: {duration:.2f}s')
        
        except Exception as e:
            issues.append({
                'type': 'state_machine_error',
                'error': str(e),
                'severity': 'high'
            })
            self.stdout.write(f'❌ Error en State Machine: {str(e)}')
    
    def validate_memory(self):
        """Valida el uso de memoria"""
        self.stdout.write('\n🧠 VALIDANDO USO DE MEMORIA')
        self.stdout.write('-' * 40)
        
        issues = []
        
        try:
            # Obtener información de memoria
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            # Memoria RSS (Resident Set Size)
            rss_mb = memory_info.rss / 1024 / 1024
            self.stdout.write(f'📊 Memoria RSS: {rss_mb:.2f} MB')
            
            # Memoria VMS (Virtual Memory Size)
            vms_mb = memory_info.vms / 1024 / 1024
            self.stdout.write(f'📊 Memoria VMS: {vms_mb:.2f} MB')
            
            # Porcentaje de memoria del sistema
            self.stdout.write(f'📊 Porcentaje de memoria: {memory_percent:.2f}%')
            
            # Validar límites
            if rss_mb > 1000:  # 1GB
                issues.append({
                    'type': 'high_memory_usage',
                    'rss_mb': rss_mb,
                    'severity': 'high'
                })
                self.stdout.write('⚠️ Uso de memoria muy alto')
            
            if memory_percent > 80:
                issues.append({
                    'type': 'memory_percentage_high',
                    'percentage': memory_percent,
                    'severity': 'high'
                })
                self.stdout.write('⚠️ Porcentaje de memoria muy alto')
            
            # Verificar garbage collection
            gc_stats = gc.get_stats()
            total_objects = sum(stat['collections'] for stat in gc_stats)
            self.stdout.write(f'🗑️ Garbage collections: {total_objects}')
            
            # Forzar garbage collection y medir diferencia
            gc.collect()
            
        except Exception as e:
            self.stdout.write(f'💥 Error validando memoria: {str(e)}')
            issues.append({
                'type': 'memory_validation_error',
                'error': str(e),
                'severity': 'high'
            })
        
        return issues
    
    def fix_issues(self, issues):
        """Intenta reparar problemas encontrados"""
        self.stdout.write('\n🔧 REPARANDO PROBLEMAS ENCONTRADOS')
        self.stdout.write('-' * 40)
        
        for issue in issues:
            if issue['type'] == 'missing_schema':
                self.fix_missing_schema(issue)
            elif issue['type'] == 'orphaned_schema':
                self.fix_orphaned_schema(issue)
            elif issue['type'] == 'high_memory_usage':
                self.fix_memory_usage(issue)
            else:
                self.stdout.write(f'⚠️ No se puede reparar automáticamente: {issue["type"]}')
    
    def fix_missing_schema(self, issue):
        """Repara esquema faltante"""
        try:
            from app.business.services.business_service import DatabaseService
            from app.business.models.business import Business
            
            business = Business.objects.get(id=issue['business_id'])
            result = DatabaseService.create_business_database(business)
            
            if result:
                self.stdout.write(f'✅ Esquema creado: {issue["schema_name"]}')
            else:
                self.stdout.write(f'❌ Error creando esquema: {issue["schema_name"]}')
        
        except Exception as e:
            self.stdout.write(f'❌ Error reparando esquema: {str(e)}')
    
    def fix_orphaned_schema(self, issue):
        """Repara esquema huérfano"""
        try:
            from app.business.services.business_service import DatabaseService
            
            result = DatabaseService.delete_business_schema(issue['business_id'])
            
            if result:
                self.stdout.write(f'✅ Esquema huérfano eliminado: {issue["schema_name"]}')
            else:
                self.stdout.write(f'❌ Error eliminando esquema: {issue["schema_name"]}')
        
        except Exception as e:
            self.stdout.write(f'❌ Error eliminando esquema: {str(e)}')
    
    def fix_memory_usage(self, issue):
        """Intenta reducir uso de memoria"""
        try:
            # Forzar garbage collection
            collected = gc.collect()
            self.stdout.write(f'🗑️ Objetos recolectados: {collected}')
            
            # Limpiar cache
            cache.clear()
            self.stdout.write('💾 Cache limpiado')
            
        except Exception as e:
            self.stdout.write(f'❌ Error optimizando memoria: {str(e)}')
    
    def show_validation_summary(self, issues):
        """Muestra resumen de validación"""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('📋 RESUMEN DE VALIDACIÓN'))
        self.stdout.write('=' * 60)
        
        if not issues:
            self.stdout.write(self.style.SUCCESS('🎉 ¡NO SE ENCONTRARON PROBLEMAS!'))
            return
        
        # Agrupar por severidad
        high_issues = [i for i in issues if i.get('severity') == 'high']
        medium_issues = [i for i in issues if i.get('severity') == 'medium']
        low_issues = [i for i in issues if i.get('severity') == 'low']
        
        self.stdout.write(f'❌ Problemas críticos: {len(high_issues)}')
        self.stdout.write(f'⚠️ Problemas medios: {len(medium_issues)}')
        self.stdout.write(f'ℹ️ Problemas menores: {len(low_issues)}')
        
        # Mostrar detalles de problemas críticos
        if high_issues:
            self.stdout.write('\n🚨 PROBLEMAS CRÍTICOS:')
            for issue in high_issues:
                self.stdout.write(f'  - {issue["type"]}: {issue}')
        
        self.stdout.write('\n🔧 RECOMENDACIONES:')
        self.stdout.write('- Ejecutar con --fix-issues para reparar automáticamente')
        self.stdout.write('- Monitorear regularmente el sistema')
        self.stdout.write('- Optimizar queries lentas')
        self.stdout.write('- Configurar alertas de memoria')
        self.stdout.write('=' * 60)
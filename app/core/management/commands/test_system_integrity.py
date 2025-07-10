# app/core/management/commands/test_system_integrity.py
from django.core.management.base import BaseCommand
from django.test.utils import get_runner
from django.conf import settings
import sys
import time


class Command(BaseCommand):
    help = 'Ejecuta tests de integridad del sistema multitenant'

    def add_arguments(self, parser):
        parser.add_argument(
            '--module',
            type=str,
            help='Módulo específico a probar (schema, state_machine, websocket)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Salida detallada',
        )
        parser.add_argument(
            '--parallel',
            type=int,
            default=1,
            help='Número de procesos paralelos',
        )
        parser.add_argument(
            '--stress',
            action='store_true',
            help='Ejecutar tests de estrés',
        )

    def handle(self, *args, **options):
        """Ejecuta los tests de integridad"""
        
        self.stdout.write(
            self.style.SUCCESS('🧪 INICIANDO TESTS DE INTEGRIDAD DEL SISTEMA')
        )
        self.stdout.write('=' * 60)
        
        # Configurar runner de tests
        TestRunner = get_runner(settings)
        test_runner = TestRunner(
            verbosity=2 if options['verbose'] else 1,
            parallel=options['parallel'],
            keepdb=True
        )
        
        # Definir módulos de test
        test_modules = {
            'schema': 'tests.test_business_schema',
            'state_machine': 'tests.test_order_state_machine', 
            'websocket': 'tests.test_websocket_security',
        }
        
        # Determinar qué tests ejecutar
        if options['module']:
            if options['module'] not in test_modules:
                self.stdout.write(
                    self.style.ERROR(f'❌ Módulo desconocido: {options["module"]}')
                )
                return
            modules_to_test = [test_modules[options['module']]]
        else:
            modules_to_test = list(test_modules.values())
        
        # Ejecutar tests
        total_failures = 0
        results = {}
        
        for module in modules_to_test:
            self.stdout.write(f'\n🔍 Ejecutando tests: {module}')
            self.stdout.write('-' * 40)
            
            start_time = time.time()
            
            try:
                result = test_runner.run_tests([module])
                duration = time.time() - start_time
                
                if result == 0:
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ {module} - PASSED ({duration:.2f}s)')
                    )
                    results[module] = 'PASSED'
                else:
                    self.stdout.write(
                        self.style.ERROR(f'❌ {module} - FAILED ({duration:.2f}s)')
                    )
                    results[module] = 'FAILED'
                    total_failures += result
                    
            except Exception as e:
                duration = time.time() - start_time
                self.stdout.write(
                    self.style.ERROR(f'💥 {module} - ERROR ({duration:.2f}s): {str(e)}')
                )
                results[module] = 'ERROR'
                total_failures += 1
        
        # Ejecutar tests de estrés si se solicita
        if options['stress']:
            self.stdout.write('\n🔥 EJECUTANDO TESTS DE ESTRÉS')
            self.stdout.write('-' * 40)
            self.run_stress_tests()
        
        # Mostrar resumen
        self.show_summary(results, total_failures)
        
        # Salir con código de error si hay fallos
        if total_failures > 0:
            sys.exit(1)
    
    def run_stress_tests(self):
        """Ejecuta tests de estrés"""
        
        self.stdout.write('📊 Test de creación simultánea de esquemas...')
        self.test_concurrent_schema_creation()
        
        self.stdout.write('📊 Test de transiciones de estado bajo carga...')
        self.test_state_machine_under_load()
        
        self.stdout.write('📊 Test de conexiones WebSocket concurrentes...')
        self.test_concurrent_websocket_connections()
    
    def test_concurrent_schema_creation(self):
        """Test de creación concurrente de esquemas"""
        from app.business.models.business import Business
        from app.business.services.business_service import DatabaseService
        from app.accounts.models.user import CustomUser
        from app.roles.models.main_role import MainRole
        import threading
        import time
        
        # Crear usuario de prueba
        try:
            owner_role = MainRole.get_business_owner_role()
            user = CustomUser.objects.create_user(
                username='stress_test_user',
                email='stress@test.com',
                password='testpass123',
                user_type='business_owner',
                main_role=owner_role
            )
            
            # Función para crear negocio y esquema
            def create_business_and_schema(index):
                try:
                    business = Business.objects.create(
                        name=f'Stress Test Business {index}',
                        owner=user,
                        business_type='restaurant'
                    )
                    
                    result = DatabaseService.create_business_database(business)
                    if result:
                        self.stdout.write(f'✅ Esquema {index} creado exitosamente')
                        # Limpiar
                        DatabaseService.delete_business_schema(business.id)
                    else:
                        self.stdout.write(f'❌ Esquema {index} falló')
                        
                except Exception as e:
                    self.stdout.write(f'💥 Error en esquema {index}: {str(e)}')
            
            # Ejecutar creación concurrente
            threads = []
            start_time = time.time()
            
            for i in range(10):
                thread = threading.Thread(target=create_business_and_schema, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Esperar a que terminen todos
            for thread in threads:
                thread.join()
            
            duration = time.time() - start_time
            self.stdout.write(f'⏱️ Tiempo total: {duration:.2f}s')
            
            # Limpiar usuario
            user.delete()
            
        except Exception as e:
            self.stdout.write(f'💥 Error en test de estrés: {str(e)}')
    
    def test_state_machine_under_load(self):
        """Test de State Machine bajo carga"""
        from app.orders.models import Order, OrderStatus
        from app.business.models.business import Business
        from app.accounts.models.user import CustomUser
        from app.roles.models.main_role import MainRole
        import threading
        import time
        
        try:
            # Crear datos de prueba
            owner_role = MainRole.get_business_owner_role()
            user = CustomUser.objects.create_user(
                username='state_test_user',
                email='state@test.com',
                password='testpass123',
                user_type='business_owner',
                main_role=owner_role
            )
            
            business = Business.objects.create(
                name='State Machine Stress Test',
                owner=user,
                business_type='restaurant'
            )
            
            # Crear múltiples órdenes
            orders = []
            for i in range(20):
                order = Order.objects.create(
                    business=business,
                    customer_name=f'Customer {i}',
                    order_type='dine_in',
                    status=OrderStatus.PENDING,
                    total_amount=100.00
                )
                orders.append(order)
            
            # Función para transicionar estados
            def transition_order(order, index):
                try:
                    # Simular transición con items
                    with patch.object(order, 'items') as mock_items:
                        mock_items.exists.return_value = True
                        
                        order.change_status(OrderStatus.CONFIRMED, user=user)
                        order.change_status(OrderStatus.PREPARING, user=user)
                        order.change_status(OrderStatus.READY, user=user)
                        order.change_status(OrderStatus.PAID, user=user)
                        order.change_status(OrderStatus.DELIVERED, user=user)
                        
                        self.stdout.write(f'✅ Orden {index} completada')
                        
                except Exception as e:
                    self.stdout.write(f'❌ Error en orden {index}: {str(e)}')
            
            # Ejecutar transiciones concurrentes
            threads = []
            start_time = time.time()
            
            for i, order in enumerate(orders):
                thread = threading.Thread(target=transition_order, args=(order, i))
                threads.append(thread)
                thread.start()
            
            # Esperar a que terminen
            for thread in threads:
                thread.join()
            
            duration = time.time() - start_time
            self.stdout.write(f'⏱️ Tiempo total: {duration:.2f}s')
            
            # Limpiar
            user.delete()
            
        except Exception as e:
            self.stdout.write(f'💥 Error en test de State Machine: {str(e)}')
    
    def test_concurrent_websocket_connections(self):
        """Test de conexiones WebSocket concurrentes"""
        from app.orders.consumers import OrderConsumer
        from django.core.cache import cache
        import asyncio
        
        try:
            # Simular múltiples consumidores
            consumers = []
            for i in range(50):
                consumer = OrderConsumer()
                consumer.user = f'mock_user_{i}'
                consumer.business_id = 'mock_business'
                consumers.append(consumer)
            
            # Test de rate limiting bajo carga
            success_count = 0
            failed_count = 0
            
            for consumer in consumers:
                consumer.client_ip = f'192.168.1.{i % 254 + 1}'
                consumer.user = type('MockUser', (), {'id': i})()
                
                if consumer.check_connection_rate_limit():
                    success_count += 1
                else:
                    failed_count += 1
            
            self.stdout.write(f'✅ Conexiones exitosas: {success_count}')
            self.stdout.write(f'❌ Conexiones bloqueadas: {failed_count}')
            
            # Limpiar cache
            cache.clear()
            
        except Exception as e:
            self.stdout.write(f'💥 Error en test de WebSocket: {str(e)}')
    
    def show_summary(self, results, total_failures):
        """Muestra resumen de resultados"""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('📋 RESUMEN DE TESTS'))
        self.stdout.write('=' * 60)
        
        for module, result in results.items():
            if result == 'PASSED':
                self.stdout.write(f'✅ {module}: {result}')
            else:
                self.stdout.write(f'❌ {module}: {result}')
        
        self.stdout.write(f'\n📊 Total de fallos: {total_failures}')
        
        if total_failures == 0:
            self.stdout.write(
                self.style.SUCCESS('🎉 ¡TODOS LOS TESTS PASARON EXITOSAMENTE!')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'💥 {total_failures} TESTS FALLARON')
            )
        
        self.stdout.write('\n🔧 RECOMENDACIONES:')
        self.stdout.write('- Ejecutar tests regularmente en CI/CD')
        self.stdout.write('- Monitorear performance en producción')
        self.stdout.write('- Revisar logs de errores sistemáticamente')
        self.stdout.write('- Mantener cobertura de tests > 80%')
        self.stdout.write('=' * 60)
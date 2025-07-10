# tests/test_websocket_security.py
import pytest
from django.test import TestCase
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from unittest.mock import Mock, patch, AsyncMock
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from app.orders.consumers import OrderConsumer
from app.business.models.business import Business
from app.accounts.models.user import CustomUser
from app.roles.models.main_role import MainRole
from app.roles.models.business_role import BusinessRole
from app.orders.models import Order, OrderStatus
import json
import asyncio


class WebSocketSecurityTestCase(TestCase):
    """Tests de seguridad para WebSocket connections"""
    
    def setUp(self):
        """Configuración inicial"""
        self.owner_role = MainRole.get_business_owner_role()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            user_type='business_owner',
            main_role=self.owner_role
        )
        
        self.business = Business.objects.create(
            name='Test Restaurant',
            owner=self.user,
            business_type='restaurant'
        )
        
        self.unauthorized_user = CustomUser.objects.create_user(
            username='unauthorized',
            email='unauthorized@test.com',
            password='testpass123',
            user_type='client'
        )
        
        # Crear rol de negocio
        self.waiter_role = BusinessRole.objects.create(
            name='mesero',
            business=self.business
        )
        
        self.authorized_user = CustomUser.objects.create_user(
            username='authorized',
            email='authorized@test.com',
            password='testpass123',
            current_business=self.business,
            current_business_role=self.waiter_role
        )
    
    def test_consumer_authentication_required(self):
        """Test que requiere autenticación"""
        consumer = OrderConsumer()
        consumer.scope = {
            'user': AnonymousUser(),
            'url_route': {'kwargs': {'business_id': str(self.business.id)}},
            'client': ['127.0.0.1', 0]
        }
        
        # Mock métodos asyncrónicos
        consumer.close = AsyncMock()
        
        # Ejecutar connect
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(consumer.connect())
            consumer.close.assert_called_once()
        finally:
            loop.close()
    
    def test_consumer_business_access_validation(self):
        """Test validación de acceso al negocio"""
        consumer = OrderConsumer()
        consumer.scope = {
            'user': self.unauthorized_user,
            'url_route': {'kwargs': {'business_id': str(self.business.id)}},
            'client': ['127.0.0.1', 0]
        }
        
        # Mock métodos
        consumer.close = AsyncMock()
        consumer.check_business_access = AsyncMock(return_value=False)
        consumer.check_concurrent_connections = AsyncMock(return_value=True)
        consumer.join_groups = AsyncMock()
        consumer.accept = AsyncMock()
        consumer.register_connection = AsyncMock()
        consumer.send_initial_data = AsyncMock()
        
        # Ejecutar connect
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(consumer.connect())
            consumer.close.assert_called_once()
        finally:
            loop.close()
    
    def test_rate_limiting_connections(self):
        """Test rate limiting para conexiones"""
        consumer = OrderConsumer()
        consumer.client_ip = '127.0.0.1'
        consumer.user = self.user
        
        # Simular múltiples intentos de conexión
        for i in range(12):  # Más del límite de 10
            result = consumer.check_connection_rate_limit()
            if i < 10:
                self.assertTrue(result)
            else:
                self.assertFalse(result)
    
    def test_rate_limiting_messages(self):
        """Test rate limiting para mensajes"""
        consumer = OrderConsumer()
        consumer.user = self.user
        consumer.business_id = str(self.business.id)
        
        # Simular múltiples mensajes
        for i in range(65):  # Más del límite de 60
            result = consumer.check_message_rate_limit()
            if i < 60:
                self.assertTrue(result)
            else:
                self.assertFalse(result)
    
    def test_concurrent_connections_limit(self):
        """Test límite de conexiones concurrentes"""
        consumer = OrderConsumer()
        consumer.user = self.user
        consumer.business_id = str(self.business.id)
        
        # Simular múltiples conexiones activas
        user_key = f"ws_connections:{self.user.id}:{self.business_id}"
        cache.set(user_key, 6)  # Más del límite de 5
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(consumer.check_concurrent_connections())
            self.assertFalse(result)
        finally:
            loop.close()
            cache.delete(user_key)
    
    def test_business_data_isolation(self):
        """Test aislamiento de datos entre negocios"""
        # Crear otro negocio
        other_business = Business.objects.create(
            name='Other Restaurant',
            owner=self.user,
            business_type='restaurant'
        )
        
        # Crear orden en el negocio original
        order = Order.objects.create(
            business=self.business,
            customer_name='Test Customer',
            order_type='dine_in',
            status=OrderStatus.PENDING,
            total_amount=100.00
        )
        
        consumer = OrderConsumer()
        consumer.user = self.authorized_user
        consumer.business_id = str(other_business.id)  # Intentar acceder a otro negocio
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Intentar actualizar orden de otro negocio
            success, message = loop.run_until_complete(
                consumer.update_order_status(str(order.id), OrderStatus.CONFIRMED, 'test')
            )
            
            # Debe fallar porque la orden no pertenece al negocio
            self.assertFalse(success)
            self.assertIn("no encontrada", message)
        finally:
            loop.close()
    
    def test_client_ip_extraction(self):
        """Test extracción correcta de IP del cliente"""
        consumer = OrderConsumer()
        
        # Test con X-Forwarded-For
        consumer.scope = {
            'headers': [(b'x-forwarded-for', b'192.168.1.1, 10.0.0.1')],
            'client': ['127.0.0.1', 0]
        }
        ip = consumer.get_client_ip()
        self.assertEqual(ip, '192.168.1.1')
        
        # Test sin X-Forwarded-For
        consumer.scope = {
            'headers': [],
            'client': ['127.0.0.1', 0]
        }
        ip = consumer.get_client_ip()
        self.assertEqual(ip, '127.0.0.1')
    
    def test_message_validation(self):
        """Test validación de mensajes"""
        consumer = OrderConsumer()
        consumer.user = self.authorized_user
        consumer.business_id = str(self.business.id)
        consumer.client_ip = '127.0.0.1'
        consumer.send_error = AsyncMock()
        consumer.check_message_rate_limit = Mock(return_value=True)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Test mensaje sin action
            loop.run_until_complete(consumer.receive('{"data": "test"}'))
            consumer.send_error.assert_called_with("Acción requerida")
            
            # Test mensaje con action inválida
            consumer.send_error.reset_mock()
            loop.run_until_complete(consumer.receive('{"action": 123}'))
            consumer.send_error.assert_called_with("Acción requerida")
            
            # Test JSON inválido
            consumer.send_error.reset_mock()
            loop.run_until_complete(consumer.receive('invalid json'))
            consumer.send_error.assert_called_with("Formato JSON inválido")
        finally:
            loop.close()
    
    def test_order_status_update_permissions(self):
        """Test permisos para actualizar estado de orden"""
        # Crear orden
        order = Order.objects.create(
            business=self.business,
            customer_name='Test Customer',
            order_type='dine_in',
            status=OrderStatus.PENDING,
            total_amount=100.00
        )
        
        consumer = OrderConsumer()
        consumer.user = self.authorized_user
        consumer.business_id = str(self.business.id)
        
        # Mock del método can_update_order_status
        consumer.can_update_order_status = Mock(return_value=False)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Intentar actualizar sin permisos
            success, message = loop.run_until_complete(
                consumer.update_order_status(str(order.id), OrderStatus.CONFIRMED, 'test')
            )
            
            self.assertFalse(success)
            self.assertIn("permisos", message)
        finally:
            loop.close()
    
    def test_connection_cleanup_on_disconnect(self):
        """Test limpieza de conexión al desconectarse"""
        consumer = OrderConsumer()
        consumer.user = self.authorized_user
        consumer.business_id = str(self.business.id)
        consumer.groups = ['test_group']
        consumer.channel_layer = Mock()
        consumer.channel_layer.group_discard = AsyncMock()
        consumer.unregister_connection = AsyncMock()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Simular desconexión
            loop.run_until_complete(consumer.disconnect(1000))
            
            # Verificar que se llamó a group_discard
            consumer.channel_layer.group_discard.assert_called_once()
            
            # Verificar que se desregistró la conexión
            consumer.unregister_connection.assert_called_once()
        finally:
            loop.close()
    
    def test_connection_registration_and_cleanup(self):
        """Test registro y limpieza de conexiones"""
        consumer = OrderConsumer()
        consumer.user = self.authorized_user
        consumer.business_id = str(self.business.id)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Registrar conexión
            loop.run_until_complete(consumer.register_connection())
            
            # Verificar que se registró
            user_key = f"ws_connections:{self.authorized_user.id}:{self.business.id}"
            connections = cache.get(user_key, 0)
            self.assertEqual(connections, 1)
            
            # Desregistrar conexión
            loop.run_until_complete(consumer.unregister_connection())
            
            # Verificar que se desregistró
            connections = cache.get(user_key, 0)
            self.assertEqual(connections, 0)
        finally:
            loop.close()
    
    def test_group_assignment_by_role(self):
        """Test asignación de grupos según rol"""
        consumer = OrderConsumer()
        consumer.user = self.authorized_user
        consumer.business_id = str(self.business.id)
        consumer.groups = []
        consumer.channel_layer = Mock()
        consumer.channel_layer.group_add = AsyncMock()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Ejecutar join_groups
            loop.run_until_complete(consumer.join_groups())
            
            # Verificar que se asignaron los grupos correctos
            expected_groups = [
                f"orders_business_{self.business.id}",
                f"orders_waiters_{self.business.id}"
            ]
            
            for group in expected_groups:
                self.assertIn(group, consumer.groups)
        finally:
            loop.close()
    
    def tearDown(self):
        """Limpieza después de cada test"""
        cache.clear()


class WebSocketPerformanceTestCase(TestCase):
    """Tests de performance para WebSocket"""
    
    def setUp(self):
        """Configuración inicial"""
        self.owner_role = MainRole.get_business_owner_role()
        self.user = CustomUser.objects.create_user(
            username='perftest',
            email='perf@test.com',
            password='testpass123',
            user_type='business_owner',
            main_role=self.owner_role
        )
        
        self.business = Business.objects.create(
            name='Performance Test Restaurant',
            owner=self.user,
            business_type='restaurant'
        )
    
    def test_rate_limiting_performance(self):
        """Test performance del rate limiting"""
        import time
        
        consumer = OrderConsumer()
        consumer.client_ip = '127.0.0.1'
        consumer.user = self.user
        
        # Medir tiempo de 1000 verificaciones
        start_time = time.time()
        
        for i in range(1000):
            consumer.check_connection_rate_limit()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Debe completarse en menos de 1 segundo
        self.assertLess(duration, 1.0, f"Rate limiting check too slow: {duration}s")
    
    def test_concurrent_connection_tracking(self):
        """Test tracking de conexiones concurrentes"""
        consumer = OrderConsumer()
        consumer.user = self.user
        consumer.business_id = str(self.business.id)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            import time
            start_time = time.time()
            
            # Simular 100 operaciones de registro/desregistro
            for i in range(100):
                loop.run_until_complete(consumer.register_connection())
                loop.run_until_complete(consumer.unregister_connection())
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Debe completarse en menos de 2 segundos
            self.assertLess(duration, 2.0, f"Connection tracking too slow: {duration}s")
        finally:
            loop.close()
    
    def tearDown(self):
        """Limpieza después de cada test"""
        cache.clear()
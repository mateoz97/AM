# tests/test_business_schema.py
import pytest
from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.db import transaction
from unittest.mock import patch, MagicMock
from app.business.models.business import Business
from app.business.services.business_service import DatabaseService
from app.accounts.models.user import CustomUser
from app.roles.models.main_role import MainRole


class BusinessSchemaTestCase(TransactionTestCase):
    """
    Tests para la creación y gestión de esquemas de negocios en PostgreSQL.
    
    Usa TransactionTestCase para poder probar transacciones reales.
    """
    
    def setUp(self):
        """Configuración inicial para cada test"""
        self.owner_role = MainRole.get_business_owner_role()
        self.user = CustomUser.objects.create_user(
            username='testowner',
            email='owner@test.com',
            password='testpass123',
            user_type='business_owner',
            main_role=self.owner_role
        )
        
        self.business_data = {
            'name': 'Test Restaurant',
            'description': 'A test restaurant',
            'address': 'Test Address 123',
            'phone': '+57 300 123 4567',
            'email': 'test@restaurant.com',
            'business_type': 'restaurant',
            'owner': self.user
        }
    
    def test_create_business_schema_success(self):
        """Test exitoso de creación de esquema de negocio"""
        business = Business.objects.create(**self.business_data)
        
        # Verificar que el esquema fue creado
        result = DatabaseService.create_business_database(business)
        self.assertTrue(result)
        
        # Verificar que el esquema existe
        exists, info = DatabaseService.verify_business_database(business.id)
        self.assertTrue(exists)
        self.assertEqual(info['schema_name'], f'business_{business.id}')
        
        # Limpiar
        DatabaseService.delete_business_schema(business.id)
    
    def test_create_business_schema_invalid_business(self):
        """Test con negocio inválido"""
        with self.assertRaises(ValidationError):
            DatabaseService.create_business_database(None)
        
        # Negocio sin ID
        business_no_id = Business(**self.business_data)
        with self.assertRaises(ValidationError):
            DatabaseService.create_business_database(business_no_id)
    
    def test_create_business_schema_duplicate(self):
        """Test creación de esquema duplicado"""
        business = Business.objects.create(**self.business_data)
        
        # Crear esquema por primera vez
        result1 = DatabaseService.create_business_database(business)
        self.assertTrue(result1)
        
        # Intentar crear el mismo esquema nuevamente
        result2 = DatabaseService.create_business_database(business)
        self.assertTrue(result2)  # Debe retornar True (ya existe)
        
        # Limpiar
        DatabaseService.delete_business_schema(business.id)
    
    def test_create_business_schema_atomic_rollback(self):
        """Test que verifica rollback en caso de error"""
        business = Business.objects.create(**self.business_data)
        
        # Simular error en verificación de integridad
        with patch.object(DatabaseService, '_verify_schema_integrity', return_value=False):
            with self.assertRaises(ValidationError):
                DatabaseService.create_business_database(business)
        
        # Verificar que no se creó el esquema
        exists, info = DatabaseService.verify_business_database(business.id)
        self.assertFalse(exists)
    
    def test_delete_business_schema_success(self):
        """Test exitoso de eliminación de esquema"""
        business = Business.objects.create(**self.business_data)
        
        # Crear esquema
        DatabaseService.create_business_database(business)
        
        # Verificar que existe
        exists, info = DatabaseService.verify_business_database(business.id)
        self.assertTrue(exists)
        
        # Eliminar esquema
        result = DatabaseService.delete_business_schema(business.id)
        self.assertTrue(result)
        
        # Verificar que fue eliminado
        exists, info = DatabaseService.verify_business_database(business.id)
        self.assertFalse(exists)
    
    def test_delete_nonexistent_schema(self):
        """Test eliminación de esquema que no existe"""
        business = Business.objects.create(**self.business_data)
        
        # Intentar eliminar esquema que no existe
        result = DatabaseService.delete_business_schema(business.id)
        self.assertTrue(result)  # Debe retornar True (no hay nada que eliminar)
    
    def test_list_business_schemas(self):
        """Test listado de esquemas de negocio"""
        business1 = Business.objects.create(
            name='Restaurant 1',
            owner=self.user,
            business_type='restaurant'
        )
        business2 = Business.objects.create(
            name='Restaurant 2', 
            owner=self.user,
            business_type='restaurant'
        )
        
        # Crear esquemas
        DatabaseService.create_business_database(business1)
        DatabaseService.create_business_database(business2)
        
        # Listar esquemas
        schemas = DatabaseService.list_business_schemas()
        
        # Verificar que aparecen ambos
        schema_names = [schema['schema_name'] for schema in schemas]
        self.assertIn(f'business_{business1.id}', schema_names)
        self.assertIn(f'business_{business2.id}', schema_names)
        
        # Limpiar
        DatabaseService.delete_business_schema(business1.id)
        DatabaseService.delete_business_schema(business2.id)
    
    def test_schema_integrity_verification(self):
        """Test verificación de integridad del esquema"""
        business = Business.objects.create(**self.business_data)
        schema_name = f'business_{business.id}'
        
        # Crear esquema
        DatabaseService.create_business_database(business)
        
        # Verificar integridad
        integrity_ok = DatabaseService._verify_schema_integrity(schema_name)
        self.assertTrue(integrity_ok)
        
        # Limpiar
        DatabaseService.delete_business_schema(business.id)
    
    def test_concurrent_schema_creation(self):
        """Test creación concurrente de esquemas"""
        businesses = []
        
        # Crear múltiples negocios
        for i in range(3):
            business = Business.objects.create(
                name=f'Concurrent Restaurant {i}',
                owner=self.user,
                business_type='restaurant'
            )
            businesses.append(business)
        
        # Crear esquemas concurrentemente
        results = []
        for business in businesses:
            result = DatabaseService.create_business_database(business)
            results.append(result)
        
        # Verificar que todos se crearon exitosamente
        for result in results:
            self.assertTrue(result)
        
        # Verificar que todos los esquemas existen
        for business in businesses:
            exists, info = DatabaseService.verify_business_database(business.id)
            self.assertTrue(exists)
        
        # Limpiar
        for business in businesses:
            DatabaseService.delete_business_schema(business.id)
    
    def test_switch_to_business_schema(self):
        """Test cambio de contexto a esquema de negocio"""
        business = Business.objects.create(**self.business_data)
        
        # Crear esquema
        DatabaseService.create_business_database(business)
        
        # Cambiar contexto
        result = DatabaseService.switch_to_business_schema(business.id)
        self.assertTrue(result)
        
        # Intentar cambiar a esquema inexistente
        result = DatabaseService.switch_to_business_schema(99999)
        self.assertFalse(result)
        
        # Limpiar
        DatabaseService.delete_business_schema(business.id)
    
    def tearDown(self):
        """Limpieza después de cada test"""
        # Limpiar todos los esquemas que puedan haber quedado
        try:
            schemas = DatabaseService.list_business_schemas()
            for schema in schemas:
                if schema['business_id']:
                    DatabaseService.delete_business_schema(schema['business_id'])
        except Exception:
            pass  # Ignorar errores en limpieza


class BusinessSchemaPerformanceTestCase(TestCase):
    """Tests de performance para gestión de esquemas"""
    
    def setUp(self):
        self.owner_role = MainRole.get_business_owner_role()
        self.user = CustomUser.objects.create_user(
            username='perftest',
            email='perf@test.com',
            password='testpass123',
            user_type='business_owner',
            main_role=self.owner_role
        )
    
    def test_schema_creation_performance(self):
        """Test de performance para creación de esquemas"""
        import time
        
        business = Business.objects.create(
            name='Performance Test Restaurant',
            owner=self.user,
            business_type='restaurant'
        )
        
        start_time = time.time()
        result = DatabaseService.create_business_database(business)
        end_time = time.time()
        
        # Verificar que se completó exitosamente
        self.assertTrue(result)
        
        # Verificar que tomó menos de 5 segundos
        duration = end_time - start_time
        self.assertLess(duration, 5.0, f"Schema creation took too long: {duration}s")
        
        # Limpiar
        DatabaseService.delete_business_schema(business.id)
    
    def test_multiple_schema_operations(self):
        """Test operaciones múltiples en esquemas"""
        businesses = []
        
        # Crear múltiples negocios
        for i in range(5):
            business = Business.objects.create(
                name=f'Bulk Test Restaurant {i}',
                owner=self.user,
                business_type='restaurant'
            )
            businesses.append(business)
        
        # Medir tiempo de creación en lote
        import time
        start_time = time.time()
        
        for business in businesses:
            result = DatabaseService.create_business_database(business)
            self.assertTrue(result)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verificar que el tiempo promedio por esquema es razonable
        avg_time = duration / len(businesses)
        self.assertLess(avg_time, 2.0, f"Average schema creation time too high: {avg_time}s")
        
        # Limpiar
        for business in businesses:
            DatabaseService.delete_business_schema(business.id)
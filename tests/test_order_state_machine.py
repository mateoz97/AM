# tests/test_order_state_machine.py
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from unittest.mock import Mock, patch
from app.orders.models import Order, OrderStatus
from app.orders.state_machine import OrderStateMachine, OrderState, OrderRole, OrderTransitionValidator
from app.business.models.business import Business
from app.accounts.models.user import CustomUser
from app.roles.models.main_role import MainRole
from app.roles.models.business_role import BusinessRole


class OrderStateMachineTestCase(TestCase):
    """Tests para la State Machine de órdenes"""
    
    def setUp(self):
        """Configuración inicial para cada test"""
        # Crear usuario y negocio
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
        
        # Crear roles de negocio
        self.waiter_role = BusinessRole.objects.create(
            name='mesero',
            business=self.business,
            description='Mesero del restaurante'
        )
        
        self.chef_role = BusinessRole.objects.create(
            name='cocinero',
            business=self.business,
            description='Cocinero del restaurante'
        )
        
        self.manager_role = BusinessRole.objects.create(
            name='gerente',
            business=self.business,
            description='Gerente del restaurante'
        )
        
        # Crear usuarios con roles específicos
        self.waiter_user = CustomUser.objects.create_user(
            username='waiter',
            email='waiter@test.com',
            password='testpass123',
            current_business=self.business,
            current_business_role=self.waiter_role
        )
        
        self.chef_user = CustomUser.objects.create_user(
            username='chef',
            email='chef@test.com',
            password='testpass123',
            current_business=self.business,
            current_business_role=self.chef_role
        )
        
        self.manager_user = CustomUser.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123',
            current_business=self.business,
            current_business_role=self.manager_role
        )
        
        # Crear orden de prueba
        self.order = Order.objects.create(
            business=self.business,
            customer_name='Test Customer',
            order_type='dine_in',
            status=OrderStatus.PENDING,
            total_amount=100.00
        )
        
        self.state_machine = OrderStateMachine(self.order)
    
    def test_valid_transitions(self):
        """Test transiciones válidas según la State Machine"""
        # Transiciones válidas desde PENDING
        self.assertTrue(
            self.state_machine.can_transition(
                OrderState.PENDING, OrderState.CONFIRMED
            )
        )
        self.assertTrue(
            self.state_machine.can_transition(
                OrderState.PENDING, OrderState.CANCELLED
            )
        )
        
        # Transiciones inválidas desde PENDING
        self.assertFalse(
            self.state_machine.can_transition(
                OrderState.PENDING, OrderState.DELIVERED
            )
        )
        self.assertFalse(
            self.state_machine.can_transition(
                OrderState.PENDING, OrderState.PREPARING
            )
        )
    
    def test_invalid_transitions(self):
        """Test transiciones inválidas"""
        # Salto de estados no permitido
        with self.assertRaises(ValidationError):
            self.state_machine.validate_transition(
                OrderState.PENDING, OrderState.DELIVERED
            )
        
        # Regresión desde estado final
        with self.assertRaises(ValidationError):
            self.state_machine.validate_transition(
                OrderState.DELIVERED, OrderState.PENDING
            )
    
    def test_role_permissions(self):
        """Test permisos por rol"""
        # Mesero puede confirmar órdenes
        self.assertTrue(
            self.state_machine.can_transition(
                OrderState.PENDING, OrderState.CONFIRMED, 
                user=self.waiter_user
            )
        )
        
        # Cocinero puede cambiar a preparación
        self.assertTrue(
            self.state_machine.can_transition(
                OrderState.CONFIRMED, OrderState.PREPARING, 
                user=self.chef_user
            )
        )
        
        # Mesero NO puede cambiar a preparación
        self.assertFalse(
            self.state_machine.can_transition(
                OrderState.CONFIRMED, OrderState.PREPARING, 
                user=self.waiter_user
            )
        )
        
        # Manager puede hacer cualquier transición
        self.assertTrue(
            self.state_machine.can_transition(
                OrderState.CONFIRMED, OrderState.PREPARING, 
                user=self.manager_user
            )
        )
    
    def test_get_next_states(self):
        """Test obtención de estados siguientes válidos"""
        # Estados válidos desde PENDING para mesero
        next_states = self.state_machine.get_next_states(
            OrderState.PENDING, user=self.waiter_user
        )
        self.assertIn(OrderState.CONFIRMED, next_states)
        
        # Estados válidos desde CONFIRMED para cocinero
        next_states = self.state_machine.get_next_states(
            OrderState.CONFIRMED, user=self.chef_user
        )
        self.assertIn(OrderState.PREPARING, next_states)
        
        # Manager ve todos los estados válidos
        next_states = self.state_machine.get_next_states(
            OrderState.PENDING, user=self.manager_user
        )
        self.assertIn(OrderState.CONFIRMED, next_states)
        self.assertIn(OrderState.CANCELLED, next_states)
    
    def test_confirmation_required_transitions(self):
        """Test transiciones que requieren confirmación"""
        # Transición que requiere confirmación
        self.assertTrue(
            self.state_machine.requires_confirmation(
                OrderState.CANCELLED, OrderState.REFUNDED
            )
        )
        
        # Transición que no requiere confirmación
        self.assertFalse(
            self.state_machine.requires_confirmation(
                OrderState.PENDING, OrderState.CONFIRMED
            )
        )
    
    def test_role_inference(self):
        """Test inferencia de roles"""
        # Test inferencia de rol de mesero
        inferred_role = self.state_machine._infer_user_role(self.waiter_user)
        self.assertEqual(inferred_role, OrderRole.WAITER)
        
        # Test inferencia de rol de cocinero
        inferred_role = self.state_machine._infer_user_role(self.chef_user)
        self.assertEqual(inferred_role, OrderRole.KITCHEN)
        
        # Test inferencia de rol de gerente
        inferred_role = self.state_machine._infer_user_role(self.manager_user)
        self.assertEqual(inferred_role, OrderRole.MANAGER)
    
    def test_final_states(self):
        """Test estados finales"""
        # Estados finales no permiten transiciones
        with self.assertRaises(ValidationError):
            self.state_machine.validate_transition(
                OrderState.DELIVERED, OrderState.PENDING
            )
        
        with self.assertRaises(ValidationError):
            self.state_machine.validate_transition(
                OrderState.REFUNDED, OrderState.CANCELLED
            )
    
    def test_order_change_status_method(self):
        """Test método change_status del modelo Order"""
        # Cambio válido
        result = self.order.change_status(
            OrderStatus.CONFIRMED, 
            user=self.waiter_user, 
            notes='Orden confirmada'
        )
        self.assertTrue(result)
        self.assertEqual(self.order.status, OrderStatus.CONFIRMED)
        
        # Cambio inválido
        with self.assertRaises(ValidationError):
            self.order.change_status(
                OrderStatus.DELIVERED, 
                user=self.waiter_user
            )
    
    def test_order_get_next_valid_states(self):
        """Test método get_next_valid_states del modelo Order"""
        # Estados válidos para mesero
        valid_states = self.order.get_next_valid_states(self.waiter_user)
        self.assertIn('confirmed', valid_states)
        
        # Estados válidos para cocinero (desde PENDING no debería tener ninguno)
        valid_states = self.order.get_next_valid_states(self.chef_user)
        self.assertEqual(len(valid_states), 0)
    
    def test_order_can_transition_to(self):
        """Test método can_transition_to del modelo Order"""
        # Transición válida
        can_transition = self.order.can_transition_to(
            OrderStatus.CONFIRMED, 
            self.waiter_user
        )
        self.assertTrue(can_transition)
        
        # Transición inválida
        can_transition = self.order.can_transition_to(
            OrderStatus.DELIVERED, 
            self.waiter_user
        )
        self.assertFalse(can_transition)


class OrderTransitionValidatorTestCase(TestCase):
    """Tests para el validador de transiciones"""
    
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
        
        self.order = Order.objects.create(
            business=self.business,
            customer_name='Test Customer',
            order_type='dine_in',
            status=OrderStatus.PENDING,
            total_amount=100.00
        )
    
    def test_business_rule_validation_no_items(self):
        """Test validación de regla de negocio: no confirmar sin items"""
        # Orden sin items no se puede confirmar
        with self.assertRaises(ValidationError):
            OrderTransitionValidator.validate_business_rules(
                self.order, OrderState.PENDING, OrderState.CONFIRMED
            )
    
    def test_business_rule_validation_no_amount(self):
        """Test validación de regla de negocio: no pagar sin monto"""
        # Orden sin monto no se puede marcar como pagada
        self.order.total_amount = 0
        with self.assertRaises(ValidationError):
            OrderTransitionValidator.validate_business_rules(
                self.order, OrderState.READY, OrderState.PAID
            )
    
    def test_business_rule_validation_cancel_paid(self):
        """Test validación de regla de negocio: no cancelar orden pagada"""
        # Orden pagada no se puede cancelar directamente
        with self.assertRaises(ValidationError):
            OrderTransitionValidator.validate_business_rules(
                self.order, OrderState.PAID, OrderState.CANCELLED
            )
    
    def test_business_rule_validation_deliver_unpaid(self):
        """Test validación de regla de negocio: no entregar sin pagar"""
        # Orden no pagada no se puede entregar
        with self.assertRaises(ValidationError):
            OrderTransitionValidator.validate_business_rules(
                self.order, OrderState.PREPARING, OrderState.DELIVERED
            )


class OrderStateMachineIntegrationTestCase(TestCase):
    """Tests de integración para la State Machine"""
    
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
        
        # Crear roles
        self.waiter_role = BusinessRole.objects.create(
            name='mesero',
            business=self.business
        )
        
        self.chef_role = BusinessRole.objects.create(
            name='cocinero',
            business=self.business
        )
        
        self.cashier_role = BusinessRole.objects.create(
            name='cajero',
            business=self.business
        )
        
        # Crear usuarios
        self.waiter = CustomUser.objects.create_user(
            username='waiter',
            email='waiter@test.com',
            password='testpass123',
            current_business=self.business,
            current_business_role=self.waiter_role
        )
        
        self.chef = CustomUser.objects.create_user(
            username='chef',
            email='chef@test.com',
            password='testpass123',
            current_business=self.business,
            current_business_role=self.chef_role
        )
        
        self.cashier = CustomUser.objects.create_user(
            username='cashier',
            email='cashier@test.com',
            password='testpass123',
            current_business=self.business,
            current_business_role=self.cashier_role
        )
    
    def test_complete_order_workflow(self):
        """Test flujo completo de orden"""
        # Crear orden
        order = Order.objects.create(
            business=self.business,
            customer_name='Test Customer',
            order_type='dine_in',
            status=OrderStatus.PENDING,
            total_amount=100.00
        )
        
        # Crear un item (mock)
        with patch.object(order, 'items') as mock_items:
            mock_items.exists.return_value = True
            
            # 1. Mesero confirma la orden
            order.change_status(
                OrderStatus.CONFIRMED, 
                user=self.waiter,
                notes='Orden confirmada por mesero'
            )
            self.assertEqual(order.status, OrderStatus.CONFIRMED)
            
            # 2. Cocinero inicia preparación
            order.change_status(
                OrderStatus.PREPARING, 
                user=self.chef,
                notes='Iniciando preparación'
            )
            self.assertEqual(order.status, OrderStatus.PREPARING)
            
            # 3. Cocinero marca como listo
            order.change_status(
                OrderStatus.READY, 
                user=self.chef,
                notes='Orden lista para servir'
            )
            self.assertEqual(order.status, OrderStatus.READY)
            
            # 4. Cajero procesa pago
            order.change_status(
                OrderStatus.PAID, 
                user=self.cashier,
                notes='Pago procesado'
            )
            self.assertEqual(order.status, OrderStatus.PAID)
            
            # 5. Mesero entrega la orden
            order.change_status(
                OrderStatus.DELIVERED, 
                user=self.waiter,
                notes='Orden entregada al cliente'
            )
            self.assertEqual(order.status, OrderStatus.DELIVERED)
    
    def test_order_cancellation_workflow(self):
        """Test flujo de cancelación de orden"""
        order = Order.objects.create(
            business=self.business,
            customer_name='Test Customer',
            order_type='dine_in',
            status=OrderStatus.CONFIRMED,
            total_amount=100.00
        )
        
        # Cancelar desde CONFIRMED
        order.change_status(
            OrderStatus.CANCELLED, 
            user=self.waiter,
            notes='Cliente canceló la orden'
        )
        self.assertEqual(order.status, OrderStatus.CANCELLED)
    
    def test_invalid_user_transitions(self):
        """Test transiciones inválidas por usuario"""
        order = Order.objects.create(
            business=self.business,
            customer_name='Test Customer',
            order_type='dine_in',
            status=OrderStatus.CONFIRMED,
            total_amount=100.00
        )
        
        # Mesero no puede cambiar a PREPARING
        with self.assertRaises(ValidationError):
            order.change_status(
                OrderStatus.PREPARING, 
                user=self.waiter
            )
        
        # Cocinero no puede cambiar a PAID
        order.status = OrderStatus.READY
        order.save()
        
        with self.assertRaises(ValidationError):
            order.change_status(
                OrderStatus.PAID, 
                user=self.chef
            )
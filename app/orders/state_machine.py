# app/orders/state_machine.py
from enum import Enum
from typing import Dict, List, Optional, Set
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class OrderState(Enum):
    """Estados posibles de una orden"""
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    PREPARING = 'preparing'
    READY = 'ready'
    PAID = 'paid'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'


class OrderRole(Enum):
    """Roles que pueden realizar transiciones"""
    WAITER = 'waiter'
    KITCHEN = 'kitchen'
    CASHIER = 'cashier'
    MANAGER = 'manager'
    SYSTEM = 'system'


class OrderStateMachine:
    """
    State Machine para gestión de estados de órdenes con validación de transiciones
    y permisos por rol.
    """
    
    # Transiciones permitidas: estado_actual -> [estados_permitidos]
    ALLOWED_TRANSITIONS: Dict[OrderState, List[OrderState]] = {
        OrderState.PENDING: [OrderState.CONFIRMED, OrderState.CANCELLED],
        OrderState.CONFIRMED: [OrderState.PREPARING, OrderState.CANCELLED],
        OrderState.PREPARING: [OrderState.READY, OrderState.CANCELLED],
        OrderState.READY: [OrderState.PAID, OrderState.CANCELLED],
        OrderState.PAID: [OrderState.DELIVERED, OrderState.REFUNDED],
        OrderState.DELIVERED: [],  # Estado final
        OrderState.CANCELLED: [OrderState.REFUNDED],  # Solo si hay pago
        OrderState.REFUNDED: []  # Estado final
    }
    
    # Permisos por rol: rol -> [transiciones_permitidas]
    ROLE_PERMISSIONS: Dict[OrderRole, List[str]] = {
        OrderRole.WAITER: [
            'pending->confirmed',
            'confirmed->cancelled',
            'ready->delivered',
            'paid->delivered'
        ],
        OrderRole.KITCHEN: [
            'confirmed->preparing',
            'preparing->ready',
            'preparing->cancelled'
        ],
        OrderRole.CASHIER: [
            'ready->paid',
            'paid->delivered',
            'paid->refunded',
            'cancelled->refunded'
        ],
        OrderRole.MANAGER: ['*'],  # Todas las transiciones
        OrderRole.SYSTEM: [
            'pending->confirmed',  # Auto-confirmación
            'pending->cancelled'   # Auto-cancelación por timeout
        ]
    }
    
    # Estados que requieren confirmación adicional
    CONFIRMATION_REQUIRED: Set[str] = {
        'cancelled->refunded',
        'paid->refunded',
        'preparing->cancelled'
    }
    
    # Estados que no permiten regresión
    FINAL_STATES: Set[OrderState] = {
        OrderState.DELIVERED,
        OrderState.REFUNDED
    }
    
    def __init__(self, order=None):
        """
        Inicializa la máquina de estados para una orden específica.
        
        Args:
            order: Instancia del modelo Order (opcional)
        """
        self.order = order
        self.current_state = OrderState(order.status) if order else None
    
    def can_transition(self, from_state: OrderState, to_state: OrderState, 
                      user: User = None, role: OrderRole = None) -> bool:
        """
        Verifica si una transición es válida según las reglas del negocio.
        
        Args:
            from_state: Estado actual
            to_state: Estado objetivo
            user: Usuario que intenta realizar la transición
            role: Rol del usuario (opcional, se puede inferir)
            
        Returns:
            bool: True si la transición es válida
        """
        try:
            # Validar que la transición existe
            if to_state not in self.ALLOWED_TRANSITIONS.get(from_state, []):
                logger.warning(f"transition_not_allowed: from_state={from_state.value}, to_state={to_state.value}, user_id={user.id if user else None}")
                return False
            
            # Validar permisos de rol
            if user and not self._check_role_permission(from_state, to_state, user, role):
                logger.warning(f"transition_permission_denied: from_state={from_state.value}, to_state={to_state.value}, user_id={user.id}, role={role.value if role else None}")
                return False
            
            # Validar estados finales
            if from_state in self.FINAL_STATES:
                logger.warning(f"transition_from_final_state: from_state={from_state.value}, to_state={to_state.value}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"transition_validation_error: from_state={from_state.value}, to_state={to_state.value}, error={str(e)}")
            return False
    
    def validate_transition(self, from_state: OrderState, to_state: OrderState, 
                           user: User = None, role: OrderRole = None) -> None:
        """
        Valida una transición y lanza excepción si no es válida.
        
        Args:
            from_state: Estado actual
            to_state: Estado objetivo
            user: Usuario que intenta realizar la transición
            role: Rol del usuario
            
        Raises:
            ValidationError: Si la transición no es válida
        """
        if not self.can_transition(from_state, to_state, user, role):
            transition_key = f"{from_state.value}->{to_state.value}"
            
            if to_state not in self.ALLOWED_TRANSITIONS.get(from_state, []):
                raise ValidationError(
                    f"Transición no permitida: {transition_key}. "
                    f"Estados permitidos desde {from_state.value}: "
                    f"{[s.value for s in self.ALLOWED_TRANSITIONS.get(from_state, [])]}"
                )
            
            if user and not self._check_role_permission(from_state, to_state, user, role):
                raise ValidationError(
                    f"Sin permisos para realizar transición {transition_key}. "
                    f"Rol requerido: {self._get_required_roles(from_state, to_state)}"
                )
            
            if from_state in self.FINAL_STATES:
                raise ValidationError(
                    f"No se puede cambiar desde el estado final: {from_state.value}"
                )
    
    def get_next_states(self, from_state: OrderState, user: User = None, 
                       role: OrderRole = None) -> List[OrderState]:
        """
        Obtiene los estados siguientes válidos para un usuario/rol específico.
        
        Args:
            from_state: Estado actual
            user: Usuario (opcional)
            role: Rol (opcional)
            
        Returns:
            List[OrderState]: Lista de estados válidos
        """
        allowed_states = self.ALLOWED_TRANSITIONS.get(from_state, [])
        
        if not user:
            return allowed_states
        
        # Filtrar por permisos de rol
        valid_states = []
        for state in allowed_states:
            if self._check_role_permission(from_state, state, user, role):
                valid_states.append(state)
        
        return valid_states
    
    def requires_confirmation(self, from_state: OrderState, to_state: OrderState) -> bool:
        """
        Verifica si una transición requiere confirmación adicional.
        
        Args:
            from_state: Estado actual
            to_state: Estado objetivo
            
        Returns:
            bool: True si requiere confirmación
        """
        transition_key = f"{from_state.value}->{to_state.value}"
        return transition_key in self.CONFIRMATION_REQUIRED
    
    def _check_role_permission(self, from_state: OrderState, to_state: OrderState, 
                              user: User, role: OrderRole = None) -> bool:
        """
        Verifica si un usuario tiene permisos para realizar una transición.
        
        Args:
            from_state: Estado actual
            to_state: Estado objetivo
            user: Usuario
            role: Rol (opcional, se puede inferir)
            
        Returns:
            bool: True si tiene permisos
        """
        if not role:
            role = self._infer_user_role(user)
        
        if not role:
            return False
        
        # Manager puede hacer cualquier transición
        if role == OrderRole.MANAGER:
            return True
        
        # Verificar permisos específicos del rol
        allowed_transitions = self.ROLE_PERMISSIONS.get(role, [])
        
        # Verificar si el rol tiene permisos para todas las transiciones
        if '*' in allowed_transitions:
            return True
        
        # Verificar transición específica
        transition_key = f"{from_state.value}->{to_state.value}"
        return transition_key in allowed_transitions
    
    def _infer_user_role(self, user: User) -> Optional[OrderRole]:
        """
        Infiere el rol del usuario basado en su rol de negocio.
        
        Args:
            user: Usuario
            
        Returns:
            Optional[OrderRole]: Rol inferido o None
        """
        try:
            if not user or not hasattr(user, 'current_business_role'):
                return None
            
            business_role = user.current_business_role
            if not business_role:
                return None
            
            # Mapear roles de negocio a roles de orden
            role_mapping = {
                'mesero': OrderRole.WAITER,
                'waiter': OrderRole.WAITER,
                'cocinero': OrderRole.KITCHEN,
                'kitchen': OrderRole.KITCHEN,
                'cajero': OrderRole.CASHIER,
                'cashier': OrderRole.CASHIER,
                'gerente': OrderRole.MANAGER,
                'manager': OrderRole.MANAGER,
                'admin': OrderRole.MANAGER,
                'propietario': OrderRole.MANAGER,
                'owner': OrderRole.MANAGER,
            }
            
            role_name = business_role.name.lower()
            return role_mapping.get(role_name, None)
            
        except Exception as e:
            logger.error(f"role_inference_error: user_id={user.id}, error={str(e)}")
            return None
    
    def _get_required_roles(self, from_state: OrderState, to_state: OrderState) -> List[str]:
        """
        Obtiene los roles requeridos para una transición específica.
        
        Args:
            from_state: Estado actual
            to_state: Estado objetivo
            
        Returns:
            List[str]: Lista de roles que pueden realizar la transición
        """
        transition_key = f"{from_state.value}->{to_state.value}"
        required_roles = []
        
        for role, transitions in self.ROLE_PERMISSIONS.items():
            if '*' in transitions or transition_key in transitions:
                required_roles.append(role.value)
        
        return required_roles
    
    def get_state_history(self, order) -> List[Dict]:
        """
        Obtiene el historial de estados de una orden.
        
        Args:
            order: Instancia del modelo Order
            
        Returns:
            List[Dict]: Lista de cambios de estado
        """
        try:
            history = []
            for record in order.status_history.all().order_by('timestamp'):
                history.append({
                    'timestamp': record.timestamp,
                    'from_state': record.old_status,
                    'to_state': record.new_status,
                    'changed_by': record.changed_by.username if record.changed_by else 'System',
                    'notes': record.notes
                })
            return history
            
        except Exception as e:
            logger.error(f"state_history_error: order_id={order.id}, error={str(e)}")
            return []


class OrderTransitionValidator:
    """
    Validador para transiciones de estado con reglas de negocio específicas.
    """
    
    @staticmethod
    def validate_business_rules(order, from_state: OrderState, to_state: OrderState) -> None:
        """
        Valida reglas de negocio específicas para transiciones.
        
        Args:
            order: Instancia del modelo Order
            from_state: Estado actual
            to_state: Estado objetivo
            
        Raises:
            ValidationError: Si la transición viola reglas de negocio
        """
        # Validar que hay items en la orden antes de confirmar
        if from_state == OrderState.PENDING and to_state == OrderState.CONFIRMED:
            if not order.items.exists():
                raise ValidationError("No se puede confirmar una orden sin items")
        
        # Validar que hay precio antes de marcar como pagado
        if to_state == OrderState.PAID:
            if not order.total_amount or order.total_amount <= 0:
                raise ValidationError("No se puede marcar como pagado una orden sin monto")
        
        # Validar que está pagado antes de entregar
        if to_state == OrderState.DELIVERED:
            if from_state not in [OrderState.PAID, OrderState.READY]:
                raise ValidationError("Solo se puede entregar órdenes pagadas o listas")
        
        # Validar cancelación con pago
        if from_state == OrderState.PAID and to_state == OrderState.CANCELLED:
            raise ValidationError("No se puede cancelar una orden pagada. Debe reembolsarse")
        
        logger.info(f"business_rules_validated: order_id={order.id}, from_state={from_state.value}, to_state={to_state.value}")
# app/orders/consumers.py
import json
import logging
import time
from collections import defaultdict
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.core.cache import cache
from app.orders.models import Order, OrderStatus
from app.business.models.business import Business
from app.accounts.models.user import CustomUser
logger = logging.getLogger(__name__)

# Rate limiting global (en producción usar Redis)
connection_attempts = defaultdict(list)
message_counts = defaultdict(int)
last_message_time = defaultdict(float)


class OrderConsumer(AsyncWebsocketConsumer):
    """
    Consumer para manejar conexiones WebSocket de órdenes en tiempo real.
    Cada conexión se une a grupos específicos basados en el negocio y rol del usuario.
    """
    
    async def connect(self):
        """Maneja la conexión inicial del WebSocket con validaciones de seguridad"""
        self.user = self.scope["user"]
        self.client_ip = self.get_client_ip()
        
        # Rate limiting para conexiones
        if not self.check_connection_rate_limit():
            logger.warning(f"connection_rate_limit_exceeded: user_id={getattr(self.user, 'id', None)}, client_ip={self.client_ip}")
            await self.close(code=1008)  # Policy violation
            return
        
        # Obtener business_id de la URL o del contexto del usuario
        self.business_id = self.scope['url_route']['kwargs'].get('business_id')
        
        # Si no hay business_id en la URL, usar el negocio actual del usuario
        if not self.business_id:
            self.business_id = await self.get_user_current_business_id()
            if not self.business_id:
                logger.warning(f"no_business_id_determined: user_id={getattr(self.user, 'id', None)}")
                await self.close(code=1002)  # Protocol error
                return
        
        self.groups = []
        
        # Verificar autenticación
        if self.user == AnonymousUser():
            logger.warning(f"unauthenticated_websocket_attempt: client_ip={self.client_ip}")
            await self.close(code=1008)  # Policy violation
            return
        
        # Verificar acceso al negocio
        has_access = await self.check_business_access()
        if not has_access:
            logger.warning(f"unauthorized_business_access: user_id={self.user.id}, business_id={self.business_id}, client_ip={self.client_ip}")
            await self.close(code=1008)  # Policy violation
            return
        
        # Verificar si el usuario ya tiene demasiadas conexiones
        if not await self.check_concurrent_connections():
            logger.warning(f"max_concurrent_connections_exceeded: user_id={self.user.id}, business_id={self.business_id}")
            await self.close(code=1013)  # Try again later
            return
        
        # Determinar grupos según el rol del usuario
        await self.join_groups()
        
        # Aceptar la conexión
        await self.accept()
        
        # Registrar conexión activa
        await self.register_connection()
        
        # Enviar estado inicial
        await self.send_initial_data()
        
        logger.info(f"websocket_connection_established: user_id={self.user.id}, business_id={self.business_id}, client_ip={self.client_ip}")
    
    async def disconnect(self, close_code):
        """Maneja la desconexión del WebSocket"""
        # Salir de todos los grupos
        for group_name in self.groups:
            await self.channel_layer.group_discard(group_name, self.channel_name)
        
        # Desregistrar conexión activa
        await self.unregister_connection()
        
        logger.info(f"websocket_connection_closed: user_id={getattr(self.user, 'id', None)}, business_id={getattr(self, 'business_id', None)}, close_code={close_code}")
    
    async def receive(self, text_data):
        """Maneja mensajes recibidos del cliente con rate limiting"""
        try:
            # Rate limiting para mensajes
            if not self.check_message_rate_limit():
                logger.warning(f"message_rate_limit_exceeded: user_id={self.user.id}, client_ip={self.client_ip}")
                await self.send_error("Rate limit exceeded")
                return
            
            data = json.loads(text_data)
            action = data.get('action')
            
            # Validar estructura del mensaje
            if not action or not isinstance(action, str):
                await self.send_error("Acción requerida")
                return
            
            # Registrar actividad
            logger.info(f"websocket_message_received: user_id={self.user.id}, action={action}, client_ip={self.client_ip}")
            
            if action == 'update_order_status':
                await self.handle_status_update(data)
            elif action == 'assign_order':
                await self.handle_order_assignment(data)
            elif action == 'add_order_note':
                await self.handle_add_note(data)
            elif action == 'request_orders_update':
                await self.send_initial_data()
            elif action == 'ping':
                await self.handle_ping()
            elif action == 'subscribe_to_updates':
                await self.handle_subscription(data)
            else:
                await self.send_error(f"Acción desconocida: {action}")
                
        except json.JSONDecodeError:
            await self.send_error("Formato JSON inválido")
        except Exception as e:
            logger.error(f"websocket_receive_error: user_id={self.user.id}, error={str(e)}", exc_info=True)
            await self.send_error("Error interno del servidor")
    
    async def handle_status_update(self, data):
        """Maneja la actualización de estado de una orden"""
        try:
            order_id = data.get('order_id')
            new_status = data.get('new_status')
            notes = data.get('notes', '')
            
            if not order_id or not new_status:
                await self.send_error("order_id y new_status son requeridos")
                return
            
            # Verificar permisos y actualizar orden
            success, message = await self.update_order_status(order_id, new_status, notes)
            
            if success:
                await self.send_json({
                    'type': 'status_update_success',
                    'order_id': order_id,
                    'new_status': new_status,
                    'message': message
                })
            else:
                await self.send_error(message)
                
        except Exception as e:
            logger.error(f"Error en handle_status_update: {str(e)}", exc_info=True)
            await self.send_error("Error al actualizar estado de orden")
    
    async def handle_order_assignment(self, data):
        """Maneja la asignación de personal a órdenes"""
        try:
            order_id = data.get('order_id')
            assignment_type = data.get('assignment_type')  # 'waiter' o 'chef'
            user_id = data.get('user_id')
            
            success, message = await self.assign_order(order_id, assignment_type, user_id)
            
            if success:
                await self.send_json({
                    'type': 'assignment_success',
                    'order_id': order_id,
                    'assignment_type': assignment_type,
                    'user_id': user_id,
                    'message': message
                })
            else:
                await self.send_error(message)
                
        except Exception as e:
            logger.error(f"Error en handle_order_assignment: {str(e)}", exc_info=True)
            await self.send_error("Error al asignar orden")
    
    async def handle_add_note(self, data):
        """Maneja la adición de notas a órdenes"""
        try:
            order_id = data.get('order_id')
            note_type = data.get('note_type')  # 'kitchen', 'internal', 'customer'
            note_content = data.get('note_content')
            
            success, message = await self.add_order_note(order_id, note_type, note_content)
            
            if success:
                await self.send_json({
                    'type': 'note_added_success',
                    'order_id': order_id,
                    'note_type': note_type,
                    'message': message
                })
            else:
                await self.send_error(message)
                
        except Exception as e:
            logger.error(f"Error en handle_add_note: {str(e)}", exc_info=True)
            await self.send_error("Error al agregar nota")
    
    async def handle_ping(self):
        """Maneja ping para mantener conexión viva"""
        await self.send_json({
            'type': 'pong',
            'timestamp': timezone.now().isoformat(),
            'server_time': timezone.now().isoformat()
        })
    
    async def handle_subscription(self, data):
        """Maneja suscripciones a actualizaciones específicas"""
        try:
            subscription_types = data.get('subscription_types', [])
            
            # Validar tipos de suscripción
            valid_types = ['orders', 'inventory', 'notifications', 'business_events']
            filtered_types = [t for t in subscription_types if t in valid_types]
            
            # Enviar confirmación de suscripción
            await self.send_json({
                'type': 'subscription_confirmed',
                'subscribed_to': filtered_types,
                'message': f'Suscrito a {len(filtered_types)} tipos de eventos'
            })
            
        except Exception as e:
            logger.error(f"Error en handle_subscription: {str(e)}", exc_info=True)
            await self.send_error("Error al procesar suscripción")
    
    # Eventos de grupo (recibidos desde otros consumers o views)
    async def order_created(self, event):
        """Maneja evento de orden creada"""
        await self.send_json({
            'type': 'order_created',
            'order': event['order_data'],
            'message': 'Nueva orden creada'
        })
    
    async def order_updated(self, event):
        """Maneja evento de orden actualizada"""
        await self.send_json({
            'type': 'order_updated',
            'order': event['order_data'],
            'changes': event.get('changes', {}),
            'message': event.get('message', 'Orden actualizada')
        })
    
    async def order_status_changed(self, event):
        """Maneja evento de cambio de estado"""
        await self.send_json({
            'type': 'order_status_changed',
            'order_id': event['order_id'],
            'old_status': event['old_status'],
            'new_status': event['new_status'],
            'changed_by': event.get('changed_by'),
            'timestamp': event['timestamp'],
            'message': f"Orden {event['order_number']} cambió a {event['new_status_display']}"
        })
    
    async def order_assigned(self, event):
        """Maneja evento de asignación de orden"""
        await self.send_json({
            'type': 'order_assigned',
            'order_id': event['order_id'],
            'assignment_type': event['assignment_type'],
            'assigned_to': event['assigned_to'],
            'message': event['message']
        })
    
    async def order_cancelled(self, event):
        """Maneja evento de orden cancelada"""
        await self.send_json({
            'type': 'order_cancelled',
            'order': event['order_data'],
            'order_id': event['order_id'],
            'order_number': event['order_number'],
            'reason': event.get('reason', ''),
            'refund_requested': event.get('refund_requested', False),
            'cancelled_at': event.get('cancelled_at'),
            'cancelled_by': event.get('cancelled_by'),
            'message': event['message'],
            'timestamp': event['timestamp']
        })
    
    async def order_refunded(self, event):
        """Maneja evento de orden reembolsada"""
        await self.send_json({
            'type': 'order_refunded',
            'order': event['order_data'],
            'order_id': event['order_id'],
            'order_number': event['order_number'],
            'refund_amount': event['refund_amount'],
            'reason': event.get('reason', ''),
            'transaction_id': event.get('transaction_id'),
            'refunded_at': event.get('refunded_at'),
            'refunded_by': event.get('refunded_by'),
            'message': event['message'],
            'timestamp': event['timestamp']
        })
    
    async def order_notification(self, event):
        """Maneja notificaciones generales"""
        await self.send_json({
            'type': 'notification',
            'notification_type': event['notification_type'],
            'message': event['message'],
            'order_id': event.get('order_id'),
            'urgent': event.get('urgent', False),
            'timestamp': event.get('timestamp', '')
        })
    
    # Métodos auxiliares
    async def send_json(self, data):
        """Envía datos JSON al cliente"""
        await self.send(text_data=json.dumps(data))
    
    async def send_error(self, message):
        """Envía mensaje de error al cliente"""
        await self.send_json({
            'type': 'error',
            'message': message
        })
    
    async def send_initial_data(self):
        """Envía datos iniciales al conectarse"""
        try:
            orders_data = await self.get_orders_for_user()
            await self.send_json({
                'type': 'initial_data',
                'orders': orders_data,
                'business_id': self.business_id,
                'connected_as': {
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'role': self.user.current_business_role.name if self.user.current_business_role else None
                }
            })
        except Exception as e:
            logger.error(f"Error enviando datos iniciales: {str(e)}", exc_info=True)
            await self.send_error("Error cargando datos iniciales")
    
    @database_sync_to_async
    def check_business_access(self):
        """Verifica si el usuario tiene acceso al negocio"""
        try:
            business = Business.objects.get(id=self.business_id)
            return (
                business.owner == self.user or
                self.user in business.co_owners.all() or
                business.active_users.filter(id=self.user.id).exists()
            )
        except Business.DoesNotExist:
            return False
    
    @database_sync_to_async
    def join_groups(self):
        """Une el usuario a los grupos apropiados según su rol"""
        try:
            # Grupo general del negocio
            business_group = f"orders_business_{self.business_id}"
            self.groups.append(business_group)
            
            # Grupos específicos por rol
            if self.user.current_business_role:
                role_name = self.user.current_business_role.name.lower()
                
                if role_name in ['admin', 'owner', 'manager']:
                    # Managers pueden ver todas las órdenes
                    manager_group = f"orders_managers_{self.business_id}"
                    self.groups.append(manager_group)
                
                elif role_name in ['chef', 'cocinero', 'cook']:
                    # Chefs ven órdenes de cocina
                    kitchen_group = f"orders_kitchen_{self.business_id}"
                    self.groups.append(kitchen_group)
                
                elif role_name in ['waiter', 'mesero', 'waitress']:
                    # Meseros ven órdenes de servicio
                    waiters_group = f"orders_waiters_{self.business_id}"
                    self.groups.append(waiters_group)
            
            # Unirse a todos los grupos
            for group_name in self.groups:
                self.channel_layer.group_add(group_name, self.channel_name)
                
        except Exception as e:
            logger.error(f"Error al unirse a grupos: {str(e)}", exc_info=True)
    
    @database_sync_to_async
    def get_orders_for_user(self):
        """Obtiene las órdenes relevantes para el usuario"""
        try:
            # Configurar contexto del negocio
            from app.business.services.business_service import DatabaseService
            DatabaseService.switch_to_business_schema(self.business_id)
            
            # Filtrar órdenes según el rol
            role_name = self.user.current_business_role.name.lower() if self.user.current_business_role else ''
            
            if role_name in ['admin', 'owner', 'manager']:
                # Managers ven todas las órdenes activas
                orders = Order.objects.filter(
                    business_id=self.business_id,
                    status__in=[OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.READY]
                ).select_related('customer', 'waiter', 'chef').prefetch_related('items')
            
            elif role_name in ['chef', 'cocinero', 'cook']:
                # Chefs ven órdenes en preparación
                orders = Order.objects.filter(
                    business_id=self.business_id,
                    status__in=[OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.READY]
                ).select_related('customer', 'waiter').prefetch_related('items')
            
            elif role_name in ['waiter', 'mesero', 'waitress']:
                # Meseros ven sus órdenes asignadas + no asignadas
                orders = Order.objects.filter(
                    business_id=self.business_id,
                    status__in=[OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.READY, OrderStatus.DELIVERED]
                ).filter(
                    models.Q(waiter=self.user) | models.Q(waiter__isnull=True)
                ).select_related('customer', 'chef').prefetch_related('items')
            
            else:
                # Otros roles ven órdenes básicas
                orders = Order.objects.filter(
                    business_id=self.business_id,
                    status__in=[OrderStatus.PENDING, OrderStatus.CONFIRMED]
                ).select_related('customer').prefetch_related('items')
            
            # Serializar órdenes
            orders_data = []
            for order in orders[:50]:  # Limitar a 50 órdenes recientes
                orders_data.append({
                    'id': str(order.id),
                    'order_number': order.order_number,
                    'status': order.status,
                    'status_display': order.get_status_display(),
                    'priority': order.priority,
                    'order_type': order.order_type,
                    'table_number': order.table_number,
                    'customer_name': order.customer_name,
                    'total_amount': float(order.total_amount),
                    'created_at': order.created_at.isoformat(),
                    'estimated_ready_time': order.estimated_ready_time.isoformat() if order.estimated_ready_time else None,
                    'is_overdue': order.is_overdue,
                    'waiter': {
                        'id': order.waiter.id,
                        'name': order.waiter.get_full_name()
                    } if order.waiter else None,
                    'chef': {
                        'id': order.chef.id,
                        'name': order.chef.get_full_name()
                    } if order.chef else None,
                    'items': [
                        {
                            'id': str(item.id),
                            'product_name': item.product_name,
                            'quantity': item.quantity,
                            'modifications': item.modifications,
                            'status': item.status
                        }
                        for item in order.items.all()
                    ]
                })
            
            return orders_data
            
        except Exception as e:
            logger.error(f"Error obteniendo órdenes: {str(e)}", exc_info=True)
            return []
    
    @database_sync_to_async
    def update_order_status(self, order_id, new_status, notes):
        """Actualiza el estado de una orden usando State Machine"""
        try:
            # Configurar contexto del negocio
            from app.business.services.business_service import DatabaseService
            DatabaseService.switch_to_business_schema(self.business_id)
            
            order = Order.objects.get(id=order_id, business_id=self.business_id)
            
            # Verificar que la orden pertenece al negocio correcto
            if str(order.business_id) != str(self.business_id):
                return False, "Orden no pertenece al negocio actual"
            
            # Usar el nuevo método de State Machine
            order.change_status(new_status, user=self.user, notes=notes)
            
            return True, f"Estado cambiado a {order.get_status_display()}"
            
        except Order.DoesNotExist:
            return False, "Orden no encontrada"
        except ValidationError as e:
            return False, str(e)
        except Exception as e:
            logger.error(f"Error actualizando estado: {str(e)}", exc_info=True)
            return False, "Error interno al actualizar estado"
    
    @database_sync_to_async
    def assign_order(self, order_id, assignment_type, user_id):
        """Asigna personal a una orden"""
        try:
            # Configurar contexto del negocio
            from app.business.services.business_service import DatabaseService
            DatabaseService.switch_to_business_schema(self.business_id)
            
            order = Order.objects.get(id=order_id, business_id=self.business_id)
            assigned_user = CustomUser.objects.get(id=user_id) if user_id else None
            
            # Verificar permisos
            if not self.can_assign_orders():
                return False, "No tienes permisos para asignar órdenes"
            
            # Realizar asignación
            if assignment_type == 'waiter':
                order.waiter = assigned_user
            elif assignment_type == 'chef':
                order.chef = assigned_user
            else:
                return False, "Tipo de asignación inválido"
            
            order.save()
            
            assigned_name = assigned_user.get_full_name() if assigned_user else "Sin asignar"
            return True, f"{assignment_type.title()} asignado: {assigned_name}"
            
        except (Order.DoesNotExist, CustomUser.DoesNotExist):
            return False, "Orden o usuario no encontrado"
        except Exception as e:
            logger.error(f"Error asignando orden: {str(e)}", exc_info=True)
            return False, "Error interno al asignar orden"
    
    @database_sync_to_async
    def add_order_note(self, order_id, note_type, note_content):
        """Agrega una nota a una orden"""
        try:
            # Configurar contexto del negocio
            from app.business.services.business_service import DatabaseService
            DatabaseService.switch_to_business_schema(self.business_id)
            
            order = Order.objects.get(id=order_id, business_id=self.business_id)
            
            # Agregar nota según el tipo
            if note_type == 'kitchen':
                order.kitchen_notes = f"{order.kitchen_notes}\n{note_content}".strip()
            elif note_type == 'internal':
                order.internal_notes = f"{order.internal_notes}\n{note_content}".strip()
            elif note_type == 'customer':
                order.customer_notes = f"{order.customer_notes}\n{note_content}".strip()
            else:
                return False, "Tipo de nota inválido"
            
            order.save()
            
            return True, "Nota agregada exitosamente"
            
        except Order.DoesNotExist:
            return False, "Orden no encontrada"
        except Exception as e:
            logger.error(f"Error agregando nota: {str(e)}", exc_info=True)
            return False, "Error interno al agregar nota"
    
    def can_update_order_status(self, order, new_status):
        """Verifica si el usuario puede cambiar el estado de la orden"""
        if not self.user.current_business_role:
            return False
        
        role_name = self.user.current_business_role.name.lower()
        
        # Owners y managers pueden cambiar cualquier estado
        if role_name in ['admin', 'owner', 'manager']:
            return True
        
        # Chefs pueden cambiar estados relacionados con cocina
        if role_name in ['chef', 'cocinero', 'cook']:
            return new_status in [OrderStatus.PREPARING, OrderStatus.READY]
        
        # Meseros pueden cambiar estados relacionados con servicio
        if role_name in ['waiter', 'mesero', 'waitress']:
            return new_status in [OrderStatus.CONFIRMED, OrderStatus.DELIVERED]
        
        return False
    
    def can_assign_orders(self):
        """Verifica si el usuario puede asignar órdenes"""
        if not self.user.current_business_role:
            return False
        
        role_name = self.user.current_business_role.name.lower()
        return role_name in ['admin', 'owner', 'manager']
    
    @database_sync_to_async
    def get_user_current_business_id(self):
        """Obtiene el business_id actual del usuario"""
        try:
            if hasattr(self.user, 'current_business') and self.user.current_business:
                return str(self.user.current_business.id)
            
            # Fallback: obtener el primer negocio del usuario
            first_business = self.user.businesses.first()
            if first_business:
                return str(first_business.id)
            
            return None
        except Exception as e:
            logger.error(f"Error obteniendo business_id del usuario: {str(e)}", exc_info=True)
            return None
    
    def get_client_ip(self):
        """Obtiene la IP del cliente"""
        headers = dict(self.scope.get('headers', []))
        x_forwarded_for = headers.get(b'x-forwarded-for')
        if x_forwarded_for:
            return x_forwarded_for.decode().split(',')[0].strip()
        return self.scope.get('client', ['unknown'])[0]
    
    def check_connection_rate_limit(self):
        """Verifica rate limiting para conexiones"""
        now = time.time()
        client_key = f"{self.client_ip}:{getattr(self.user, 'id', 'anon')}"
        
        # Limpiar intentos antiguos (más de 1 minuto)
        connection_attempts[client_key] = [
            timestamp for timestamp in connection_attempts[client_key]
            if now - timestamp < 60
        ]
        
        # Verificar límite (máximo 10 conexiones por minuto)
        if len(connection_attempts[client_key]) >= 10:
            return False
        
        # Registrar intento
        connection_attempts[client_key].append(now)
        return True
    
    def check_message_rate_limit(self):
        """Verifica rate limiting para mensajes"""
        now = time.time()
        user_key = f"msg:{self.user.id}:{self.business_id}"
        
        # Resetear contador si ha pasado más de 1 minuto
        if now - last_message_time[user_key] > 60:
            message_counts[user_key] = 0
            last_message_time[user_key] = now
        
        # Verificar límite (máximo 60 mensajes por minuto)
        if message_counts[user_key] >= 60:
            return False
        
        # Incrementar contador
        message_counts[user_key] += 1
        return True
    
    @database_sync_to_async
    def check_concurrent_connections(self):
        """Verifica el límite de conexiones concurrentes"""
        try:
            # Usar cache para contar conexiones activas
            user_key = f"ws_connections:{self.user.id}:{self.business_id}"
            current_connections = cache.get(user_key, 0)
            
            # Límite de 5 conexiones concurrentes por usuario por negocio
            if current_connections >= 5:
                return False
            
            return True
        except Exception as e:
            logger.error(f"concurrent_connections_check_error: user_id={self.user.id}, error={str(e)}")
            return True  # Permitir conexión si hay error
    
    @database_sync_to_async
    def register_connection(self):
        """Registra una conexión activa"""
        try:
            user_key = f"ws_connections:{self.user.id}:{self.business_id}"
            current_connections = cache.get(user_key, 0)
            cache.set(user_key, current_connections + 1, timeout=3600)  # 1 hora
            
            logger.info(f"websocket_connection_registered: user_id={self.user.id}, business_id={self.business_id}, total_connections={current_connections + 1}")
        except Exception as e:
            logger.error(f"connection_registration_error: user_id={self.user.id}, error={str(e)}")
    
    @database_sync_to_async
    def unregister_connection(self):
        """Desregistra una conexión activa"""
        try:
            user_key = f"ws_connections:{self.user.id}:{self.business_id}"
            current_connections = cache.get(user_key, 0)
            if current_connections > 0:
                cache.set(user_key, current_connections - 1, timeout=3600)
            
            logger.info(f"websocket_connection_unregistered: user_id={self.user.id}, business_id={self.business_id}, remaining_connections={max(0, current_connections - 1)}")
        except Exception as e:
            logger.error(f"connection_unregistration_error: user_id={self.user.id}, error={str(e)}")
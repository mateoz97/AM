# app/orders/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import models
from app.orders.models import Order, OrderStatus
from app.business.models.business import Business
from app.accounts.models.user import CustomUser

logger = logging.getLogger(__name__)


class OrderConsumer(AsyncWebsocketConsumer):
    """
    Consumer para manejar conexiones WebSocket de órdenes en tiempo real.
    Cada conexión se une a grupos específicos basados en el negocio y rol del usuario.
    """
    
    async def connect(self):
        """Maneja la conexión inicial del WebSocket"""
        self.user = self.scope["user"]
        self.business_id = self.scope['url_route']['kwargs']['business_id']
        self.groups = []
        
        # Verificar autenticación
        if self.user == AnonymousUser():
            logger.warning("Usuario no autenticado intentó conectarse a orders WebSocket")
            await self.close()
            return
        
        # Verificar acceso al negocio
        has_access = await self.check_business_access()
        if not has_access:
            logger.warning(f"Usuario {self.user.id} sin acceso al negocio {self.business_id}")
            await self.close()
            return
        
        # Determinar grupos según el rol del usuario
        await self.join_groups()
        
        # Aceptar la conexión
        await self.accept()
        
        # Enviar estado inicial
        await self.send_initial_data()
        
        logger.info(f"Usuario {self.user.id} conectado a orders WebSocket para negocio {self.business_id}")
    
    async def disconnect(self, close_code):
        """Maneja la desconexión del WebSocket"""
        # Salir de todos los grupos
        for group_name in self.groups:
            await self.channel_layer.group_discard(group_name, self.channel_name)
        
        logger.info(f"Usuario {self.user.id} desconectado de orders WebSocket")
    
    async def receive(self, text_data):
        """Maneja mensajes recibidos del cliente"""
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'update_order_status':
                await self.handle_status_update(data)
            elif action == 'assign_order':
                await self.handle_order_assignment(data)
            elif action == 'add_order_note':
                await self.handle_add_note(data)
            elif action == 'request_orders_update':
                await self.send_initial_data()
            else:
                await self.send_error(f"Acción desconocida: {action}")
                
        except json.JSONDecodeError:
            await self.send_error("Formato JSON inválido")
        except Exception as e:
            logger.error(f"Error en receive: {str(e)}", exc_info=True)
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
    
    async def order_notification(self, event):
        """Maneja notificaciones generales"""
        await self.send_json({
            'type': 'notification',
            'notification_type': event['notification_type'],
            'message': event['message'],
            'order_id': event.get('order_id'),
            'urgent': event.get('urgent', False)
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
        """Actualiza el estado de una orden"""
        try:
            # Configurar contexto del negocio
            from app.business.services.business_service import DatabaseService
            DatabaseService.switch_to_business_schema(self.business_id)
            
            order = Order.objects.get(id=order_id, business_id=self.business_id)
            
            # Verificar permisos
            if not self.can_update_order_status(order, new_status):
                return False, "No tienes permisos para cambiar este estado"
            
            # Realizar la transición
            order.transition_to(new_status, user=self.user, notes=notes)
            
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
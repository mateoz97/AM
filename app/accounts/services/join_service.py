# Models
from app.accounts.models.business import BusinessInvitation

# Services
from .business_service import BusinessRoleService
from .join_service import BusinessJoinRequest
from .role_service import BusinessRole
# Management
import logging

logger = logging.getLogger(__name__)


class BusinessJoinService:
    """
    Servicio para gestionar todas las operaciones relacionadas con la unión de usuarios a negocios.
    """
    
    @staticmethod
    def create_join_request(user, business, message=None):
        """
        Crea una solicitud para unirse a un negocio.
        
        Args:
            user (CustomUser): Usuario que solicita unirse
            business (Business): Negocio al que desea unirse
            message (str, optional): Mensaje opcional explicando la razón
            
        Returns:
            BusinessJoinRequest: La solicitud creada o None si hay error
        """
        try:
            # Verificar si ya existe una solicitud pendiente o aprobada
            existing = BusinessJoinRequest.objects.filter(
                user=user,
                business=business
            ).exclude(status='rejected').first()
            
            if existing:
                return existing
                
            # Crear la solicitud
            request = BusinessJoinRequest.objects.create(
                user=user,
                business=business,
                message=message
            )
            
            # Aquí podríamos enviar una notificación al propietario
            # TODO: Implementar sistema de notificaciones
            
            return request
        except Exception as e:
            print(f"Error al crear solicitud: {str(e)}")
            return None
    
    @staticmethod
    def process_join_request(request_id, approve=True, role_name=None):
        """
        Procesa una solicitud de unión (aprobar o rechazar).
        
        Args:
            request_id (int): ID de la solicitud
            approve (bool): True para aprobar, False para rechazar
            role_name (str, optional): Nombre del rol a asignar si se aprueba
            
        Returns:
            bool: True si se procesó correctamente, False en caso contrario
        """
        try:
            join_request = BusinessJoinRequest.objects.get(id=request_id)
            
            if approve:
                # Aprobar solicitud
                join_request.status = 'approved'
                
                # Asignar usuario al negocio
                user = join_request.user
                business = join_request.business
                
                # Determinar rol a asignar
                if role_name:
                    # Si se especificó un rol específico
                    role = BusinessRole.objects.filter(
                        business=business,
                        name=role_name
                    ).first()
                else:
                    # Usar rol de Visualizador por defecto
                    role = BusinessRole.objects.filter(
                        business=business,
                        name__in=['Visualizador', 'viewer']
                    ).first()
                
                # Si no existe el rol, crear roles predeterminados
                if not role:
                    roles = BusinessRoleService.create_default_roles(business)
                    role = roles.get('Visualizador')
                
                # Asignar negocio y rol
                user.business = business
                user.business_role = role
                user.save(update_fields=['business', 'business_role'])
            else:
                # Rechazar solicitud
                join_request.status = 'rejected'
            
            join_request.save()
            return True
        except BusinessJoinRequest.DoesNotExist:
            return False
        except Exception as e:
            print(f"Error al procesar solicitud: {str(e)}")
            return False
    
    @staticmethod
    def create_invitation(business, created_by, role=None, expires_days=7):
        """
        Crea una invitación para unirse a un negocio.
        
        Args:
            business (Business): Negocio al que se invita
            created_by (CustomUser): Usuario que crea la invitación
            role (BusinessRole, optional): Rol que se asignará al aceptar
            expires_days (int): Días hasta que expire la invitación
            
        Returns:
            BusinessInvitation: La invitación creada o None si hay error
        """
        try:
            from django.utils import timezone
            from datetime import timedelta
            
            invitation = BusinessInvitation.objects.create(
                business=business,
                created_by=created_by,
                role=role,
                expires_at=timezone.now() + timedelta(days=expires_days)
            )
            
            return invitation
        except Exception as e:
            print(f"Error al crear invitación: {str(e)}")
            return None
    
    @staticmethod
    def use_invitation(user, token):
        """
        Usa una invitación para unir un usuario a un negocio.
        
        Args:
            user (CustomUser): Usuario que usa la invitación
            token (str): Token de la invitación
            
        Returns:
            dict: Resultado de la operación con claves 'success', 'message' y 'data'
        """
        try:
            # Buscar la invitación
            invitation = BusinessInvitation.objects.get(token=token)
            
            # Verificar validez
            if not invitation.is_valid():
                return {
                    'success': False,
                    'message': 'La invitación ha expirado o ya ha sido utilizada',
                    'data': None
                }
            
            # Determinar rol a asignar
            role = invitation.role
            if not role:
                # Si no se especificó un rol, asignar el rol de Visualizador
                role = BusinessRole.objects.filter(
                    business=invitation.business,
                    name__in=['Visualizador', 'viewer']
                ).first()
                
                # Si no existe el rol de Visualizador, crear roles predeterminados
                if not role:
                    roles = BusinessRoleService.create_default_roles(invitation.business)
                    role = roles.get('Visualizador')
            
            # Asignar negocio y rol al usuario
            user.business = invitation.business
            user.business_role = role
            user.save(update_fields=['business', 'business_role'])
            
            # Marcar invitación como usada
            invitation.used = True
            invitation.save(update_fields=['used'])
            
            return {
                'success': True,
                'message': f'Te has unido exitosamente a {invitation.business.name}',
                'data': {
                    'business': invitation.business,
                    'role': role
                }
            }
            
        except BusinessInvitation.DoesNotExist:
            return {
                'success': False,
                'message': 'Invitación no encontrada',
                'data': None
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error al usar invitación: {str(e)}',
                'data': None
            }
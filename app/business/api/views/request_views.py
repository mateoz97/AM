# API views for managing user authentication, business roles, and permissions.
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers

# Models    
from app.business.models.business import Business, BusinessJoinRequest, BusinessInvitation
from app.roles.models.role import BusinessRole

# Serializers
from app.business.api.serializers  import BusinessJoinRequestSerializer

# Validators
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class JoinBusinessRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        class JoinRequestSerializer(serializers.Serializer):
            business = serializers.IntegerField(required=True)
            message = serializers.CharField(required=False, allow_blank=True)
            
        serializer = JoinRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        business_id = request.data.get("business")
        message = request.data.get("message", "")  # Mensaje opcional
        
        # Validación básica
        if not business_id:
            return Response({"error": "Se requiere un ID de negocio"}, status=400)
        
        # Validar que el usuario no pertenezca ya a un negocio
        if request.user.business:
            return Response({
                "error": "Ya perteneces a un negocio. Debes salir primero para solicitar unirte a otro."
            }, status=400)
            
        try:
            business = Business.objects.get(id=business_id)
            
            # Verificar si ya existe una solicitud pendiente o aprobada
            existing_request = BusinessJoinRequest.objects.filter(
                user=request.user,
                business=business
            ).exclude(status='rejected').first()
            
            if existing_request:
                if existing_request.status == 'pending':
                    return Response({
                        "error": "Ya tienes una solicitud pendiente para este negocio",
                        "request_id": existing_request.id
                    }, status=400)
                elif existing_request.status == 'approved':
                    return Response({
                        "error": "Ya tienes una solicitud aprobada para este negocio",
                        "request_id": existing_request.id
                    }, status=400)
            
            # Crear nueva solicitud
            join_request = BusinessJoinRequest.objects.create(
                user=request.user,
                business=business,
                message=message  # Añadir el mensaje si se proporciona
            )
            
            # Serializar para la respuesta
            from app.accounts.api.serializers import BusinessJoinRequestSerializer
            serializer = BusinessJoinRequestSerializer(join_request)
            
            # Aquí podríamos enviar una notificación al propietario del negocio
            # TODO: Implementar sistema de notificaciones
            
            return Response({
                "message": "Solicitud enviada exitosamente. El propietario debe aprobarla.",
                "request": serializer.data
            }, status=201)  # 201 Created
            
        except Business.DoesNotExist:
            return Response({"error": "Negocio no encontrado."}, status=404)
        except Exception as e:
            return Response({"error": f"Error: {str(e)}"}, status=500)
    
    def get(self, request):
        """Obtener solicitudes pendientes enviadas por el usuario"""
        requests = BusinessJoinRequest.objects.filter(
            user=request.user
        ).order_by('-created_at')
        
        from app.business.services.join_service import BusinessJoinRequestSerializer
        serializer = BusinessJoinRequestSerializer(requests, many=True)
        
        return Response(serializer.data)
        
class BusinessJoinRequestManagementView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Ver solicitudes pendientes para el negocio del usuario"""
        if not request.user.business or not request.user.has_business_permission('can_manage_users'):
            return Response({"error": "No tienes permiso para ver solicitudes"}, status=403)
            
        # Filtrar por estado si se proporciona
        status_filter = request.query_params.get('status', 'pending')
        
        if status_filter == 'all':
            pending_requests = BusinessJoinRequest.objects.filter(
                business=request.user.business
            )
        else:
            pending_requests = BusinessJoinRequest.objects.filter(
                business=request.user.business,
                status=status_filter
            )
        
        # Ordenar por fecha de creación (más recientes primero)
        pending_requests = pending_requests.order_by('-created_at')
        
        serializer = BusinessJoinRequestSerializer(pending_requests, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Aprobar o rechazar una solicitud"""
        request_id = request.data.get('request_id')
        action = request.data.get('action')  # 'approve' o 'reject'
        role_name = request.data.get('role_name')  # Opcional
        
        if not request_id or not action:
            return Response({"error": "Se requiere request_id y action"}, status=400)
            
        if not request.user.business or not request.user.has_business_permission('can_manage_users'):
            return Response({"error": "No tienes permiso para gestionar solicitudes"}, status=403)
            
        try:
            # Verificar que la solicitud pertenezca al negocio del usuario
            join_request = BusinessJoinRequest.objects.get(
                id=request_id, 
                business=request.user.business,
                status='pending'
            )
            
            # Usar el servicio para procesar la solicitud
            from app.accounts.services import BusinessJoinService
            success = BusinessJoinService.process_join_request(
                request_id=request_id,
                approve=(action == 'approve'),
                role_name=role_name
            )
            
            if success:
                message = "Solicitud aprobada exitosamente" if action == 'approve' else "Solicitud rechazada"
                return Response({"message": message})
            else:
                return Response({"error": "Error al procesar la solicitud"}, status=500)
                
        except BusinessJoinRequest.DoesNotExist:
            return Response({"error": "Solicitud no encontrada o ya procesada"}, status=404)
        
class BusinessInvitationCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        if not request.user.business or not request.user.has_business_permission('can_manage_users'):
            return Response({"error": "No tienes permiso para crear invitaciones"}, status=403)
            
        role_id = request.data.get('role_id')  # Opcional
        expiration_days = request.data.get('expiration_days', 7)  # Por defecto 7 días
        
        try:
            # Verificar rol si se proporciona
            role = None
            if role_id:
                role = BusinessRole.objects.get(
                    id=role_id,
                    business=request.user.business
                )
                
            # Usar el servicio para crear la invitación
            from app.business.services.join_service import BusinessJoinService
            invitation = BusinessJoinService.create_invitation(
                business=request.user.business,
                created_by=request.user,
                role=role,
                expires_days=expiration_days
            )
            
            if not invitation:
                return Response({"error": "Error al crear invitación"}, status=500)
            
            # Serializar la respuesta
            from app.accounts.api.serializers import BusinessInvitationSerializer
            serializer = BusinessInvitationSerializer(invitation)
            
            return Response({
                "message": "Invitación creada exitosamente",
                "invitation": serializer.data
            }, status=201)
            
        except BusinessRole.DoesNotExist:
            return Response({"error": "Rol no encontrado"}, status=404)
        except Exception as e:
            return Response({"error": f"Error al crear invitación: {str(e)}"}, status=500)

        
class BusinessInvitationUseView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        token = request.data.get('token')
        
        if not token:
            return Response({"error": "Se requiere token de invitación"}, status=400)
            
        # Verificar si el usuario ya pertenece a un negocio
        if request.user.business:
            return Response(
                {"error": "Ya perteneces a un negocio. Debes salir primero para unirte a otro."},
                status=400
            )
        
        # Usar el servicio para procesar la invitación
        from app.business.services.join_service import BusinessJoinService
        result = BusinessJoinService.use_invitation(request.user, token)
        
        if result['success']:
            return Response({
                "message": result['message'],
                "business": result['data']['business'].name,
                "role": result['data']['role'].name
            })
        else:
            return Response({"error": result['message']}, status=400)

class UserBusinessInvitationsListView(APIView):
    """
    Endpoint para listar invitaciones creadas por el usuario
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        if not request.user.business or not request.user.has_business_permission('can_manage_users'):
            return Response({"error": "No tienes permiso para ver invitaciones"}, status=403)
        
        # Obtener invitaciones activas del negocio del usuario
        invitations = BusinessInvitation.objects.filter(
            business=request.user.business,
            used=False,
            expires_at__gt=timezone.now()
        )
        
        from app.accounts.api.serializers import BusinessInvitationSerializer
        serializer = BusinessInvitationSerializer(invitations, many=True)
        
        return Response(serializer.data)
    
    

        
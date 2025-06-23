# app/accounts/api/views/profile_views.py
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class UserBusinessProfilesView(APIView):
    """Vista para obtener todos los perfiles/negocios disponibles para el usuario"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Obtiene todos los perfiles disponibles para el usuario"""
        user = request.user
        profiles = []
        
        # Perfil personal
        profiles.append({
            'type': 'personal',
            'id': None,
            'name': user.get_full_name() or user.username,
            'description': 'Perfil personal',
            'is_current': user.current_business is None,
            'role': None
        })
        
        # Negocios propios
        owned_businesses = user.get_owned_businesses()
        for business in owned_businesses:
            profiles.append({
                'type': 'business_owner',
                'id': business.id,
                'name': business.name,
                'description': business.description or 'Negocio propio',
                'is_current': user.current_business == business,
                'role': 'Owner'
            })
        
        # Negocios co-propios
        co_owned_businesses = user.get_co_owned_businesses()
        for business in co_owned_businesses:
            profiles.append({
                'type': 'business_co_owner',
                'id': business.id,
                'name': business.name,
                'description': business.description or 'Co-propietario',
                'is_current': user.current_business == business,
                'role': 'Co-Owner'
            })
        
        # Negocios donde es empleado
        from app.business.models.business import Business
        employee_businesses = Business.objects.filter(
            business_roles__users=user,
            is_active=True
        ).exclude(
            id__in=[b.id for b in owned_businesses] + 
                   [b.id for b in co_owned_businesses]
        ).distinct()
        
        for business in employee_businesses:
            # Obtener rol del usuario en este negocio
            role = business.business_roles.filter(users=user).first()
            profiles.append({
                'type': 'business_employee',
                'id': business.id,
                'name': business.name,
                'description': business.description or 'Empleado',
                'is_current': user.current_business == business,
                'role': role.name if role else 'Employee'
            })
        
        return Response({
            'current_profile': {
                'type': user.user_type,
                'business_id': user.current_business.id if user.current_business else None,
                'business_name': user.current_business.name if user.current_business else None,
                'role': user.current_business_role.name if user.current_business_role else None
            },
            'available_profiles': profiles
        })


class SwitchBusinessProfileView(APIView):
    """Vista para cambiar entre perfiles de negocio"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Cambia al perfil de negocio especificado"""
        business_id = request.data.get('business_id')
        
        try:
            with transaction.atomic():
                if business_id is None:
                    # Cambiar a perfil personal
                    request.user.switch_to_personal_profile()
                    
                    return Response({
                        'message': 'Cambiado a perfil personal',
                        'current_profile': {
                            'type': 'personal',
                            'business_id': None,
                            'business_name': None,
                            'role': None
                        }
                    })
                
                else:
                    # Cambiar a negocio específico
                    success, message = request.user.switch_to_business(business_id)
                    
                    if success:
                        # Configurar el contexto del esquema
                        from config.middleware import set_current_business_id
                        from app.business.services.business_service import DatabaseService
                        
                        set_current_business_id(business_id)
                        DatabaseService.switch_to_business_schema(business_id)
                        
                        return Response({
                            'message': message,
                            'current_profile': {
                                'type': request.user.user_type,
                                'business_id': request.user.current_business.id,
                                'business_name': request.user.current_business.name,
                                'role': request.user.current_business_role.name if request.user.current_business_role else None
                            }
                        })
                    else:
                        return Response({
                            'error': message
                        }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error al cambiar perfil de negocio: {str(e)}")
            return Response({
                'error': 'Error interno al cambiar perfil'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateBusinessPostView(APIView):
    """Vista para crear posts desde el perfil de un negocio"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Crea un post desde el perfil de negocio actual"""
        from app.posts.api.serializers import PostSerializer
        
        # Verificar que el usuario tenga un negocio activo
        if not request.user.current_business:
            return Response({
                'error': 'Debes tener un negocio activo para publicar como negocio'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Agregar el negocio actual a los datos
        data = request.data.copy()
        data['business'] = request.user.current_business.id
        data['post_type'] = data.get('post_type', 'business')
        
        serializer = PostSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            post = serializer.save(
                author=request.user,
                business=request.user.current_business
            )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_current_profile(request):
    """Obtiene el perfil actual del usuario"""
    user = request.user
    
    if user.current_business:
        return Response({
            'type': user.user_type,
            'business_id': user.current_business.id,
            'business_name': user.current_business.name,
            'role': user.current_business_role.name if user.current_business_role else None,
            'permissions': {
                'can_create_posts': True,
                'can_manage_business': user.current_business.owner == user,
                'can_manage_roles': user.current_business.owner == user
            }
        })
    else:
        return Response({
            'type': 'personal',
            'business_id': None,
            'business_name': None,
            'role': None,
            'permissions': {
                'can_create_posts': True,
                'can_manage_business': False,
                'can_manage_roles': False
            }
        })
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def debug_user_status(request):
    """Endpoint para debuggear el estado del usuario autenticado"""
    user = request.user
    
    return Response({
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'is_active': user.is_active,
        'is_superuser': user.is_superuser,
        'current_business': {
            'id': user.current_business.id if user.current_business else None,
            'name': user.current_business.name if user.current_business else None,
        } if user.current_business else None,
        'current_business_role': {
            'id': user.current_business_role.id if user.current_business_role else None,
            'name': user.current_business_role.name if user.current_business_role else None,
        } if user.current_business_role else None,
        'has_business': bool(user.current_business),
        'debug_info': {
            'auth_header': request.headers.get('Authorization', 'No auth header'),
            'user_agent': request.headers.get('User-Agent', 'No user agent'),
        }
    })

@api_view(['GET'])
def debug_public_status(request):
    """Endpoint público para verificar el servidor"""
    return Response({
        'server_status': 'OK',
        'authenticated': request.user.is_authenticated if hasattr(request, 'user') else False,
        'user': request.user.username if hasattr(request, 'user') and request.user.is_authenticated else None,
    })
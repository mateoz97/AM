#!/usr/bin/env python3
"""
Script para debuggear el estado del usuario desde el frontend
"""
import os
import sys
import django

# Configurar Django
sys.path.append('/home/teo/Documents/ADB')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
            'request_headers': dict(request.headers),
            'auth_header': request.headers.get('Authorization', 'No auth header'),
        }
    })

if __name__ == '__main__':
    print("Script para agregar endpoint de debug")
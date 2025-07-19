# app/orders/middleware.py
"""
Middleware de autenticación JWT para WebSockets
"""
from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class JWTAuthMiddleware:
    """
    Middleware para autenticar usuarios en WebSockets usando JWT tokens
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        # Solo aplicar a conexiones WebSocket
        if scope['type'] != 'websocket':
            return await self.app(scope, receive, send)
        
        # Obtener el token de la query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        
        # Buscar token en diferentes lugares
        token = None
        
        # 1. Query parameter 'token'
        if 'token' in query_params:
            token = query_params['token'][0]
        
        # 2. Headers (si está disponible)
        elif 'headers' in scope:
            for name, value in scope['headers']:
                if name == b'authorization':
                    auth_header = value.decode()
                    if auth_header.startswith('Bearer '):
                        token = auth_header[7:]  # Remover "Bearer "
                    break
        
        # Autenticar usuario
        user = await self.get_user_from_token(token)
        
        # Agregar usuario al scope
        scope['user'] = user
        
        return await self.app(scope, receive, send)
    
    async def get_user_from_token(self, token):
        """
        Autentica al usuario usando el JWT token
        """
        if not token:
            logger.warning("websocket_no_token_provided")
            return AnonymousUser()
        
        try:
            # Validar y decodificar el token
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            
            # Obtener el usuario
            user = await self.get_user_by_id(user_id)
            if user and user.is_active:
                logger.info(f"websocket_auth_success: user_id={user.id}, username={user.username}")
                return user
            else:
                logger.warning(f"websocket_user_inactive: user_id={user_id}")
                return AnonymousUser()
                
        except TokenError as e:
            logger.warning(f"websocket_invalid_token: error={str(e)}")
            return AnonymousUser()
        except Exception as e:
            logger.error(f"websocket_auth_error: error={str(e)}")
            return AnonymousUser()
    
    async def get_user_by_id(self, user_id):
        """
        Obtiene usuario por ID de forma asíncrona
        """
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def _get_user():
            try:
                return User.objects.select_related('business', 'main_role').get(
                    id=user_id,
                    is_active=True
                )
            except User.DoesNotExist:
                return None
        
        return await _get_user()


def JWTAuthMiddlewareStack(app):
    """
    Función helper para agregar el middleware JWT a la pila
    """
    return JWTAuthMiddleware(app)
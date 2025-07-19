import threading
import logging

logger = logging.getLogger(__name__)

# Variable thread-local para almacenar el business_id actual
_thread_local = threading.local()

def get_current_business_id():
    """Obtiene el business_id almacenado en el hilo actual"""
    return getattr(_thread_local, 'business_id', None)

def set_current_business_id(business_id):
    """Establece el business_id en el hilo actual"""
    _thread_local.business_id = business_id

def get_current_schema():
    """Obtiene el nombre del esquema actual basado en el business_id"""
    business_id = get_current_business_id()
    if business_id:
        return f"business_{business_id}"
    return "main"

# Middleware para gestionar el business_id y esquemas en el contexto actual
class BusinessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Limpiar al inicio
        set_current_business_id(None)
        
        try:
            # Skip business context for ALL admin requests to avoid issues
            if request.path.startswith('/admin/'):
                # For all admin access, clear business context completely
                set_current_business_id(None)
                self._set_postgres_schema(None)
                response = self.get_response(request)
                return response
            elif request.user.is_authenticated and hasattr(request.user, 'current_business'):
                # Use current_business instead of business property
                if request.user.current_business:
                    business_id = request.user.current_business.id
                    set_current_business_id(business_id)
                    
                    # Configurar el esquema PostgreSQL automáticamente
                    self._set_postgres_schema(business_id)
                else:
                    # Si no hay negocio, usar esquema public
                    self._set_postgres_schema(None)
            else:
                # Si no hay negocio, usar esquema public
                self._set_postgres_schema(None)
            
            response = self.get_response(request)
            
            return response
        finally:
            # Limpiar al final (asegurarse de que siempre se ejecute)
            set_current_business_id(None)
            # Restaurar esquema público
            self._set_postgres_schema(None)
    
    def _set_postgres_schema(self, business_id):
        """Configura el esquema PostgreSQL para el negocio actual"""
        try:
            from django.db import connection
            
            if business_id:
                schema_name = f"business_{business_id}"
                search_path = f"{schema_name}, main"
            else:
                search_path = "main"
            
            with connection.cursor() as cursor:
                cursor.execute(f"SET search_path TO {search_path}")
                
        except Exception as e:
            logger.error(f"Error al configurar esquema PostgreSQL: {str(e)}")
            # No fallar la request por problemas de esquema
            pass
import threading

# Variable thread-local para almacenar el business_id actual
_thread_local = threading.local()

def get_current_business_id():
    """Obtiene el business_id almacenado en el hilo actual"""
    return getattr(_thread_local, 'business_id', None)

def set_current_business_id(business_id):
    """Establece el business_id en el hilo actual"""
    _thread_local.business_id = business_id

class BusinessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Limpiar al inicio
        set_current_business_id(None)
        
        # En desarrollo inicial, siempre usamos business_id=1
        set_current_business_id(1)
        
        # En futuras versiones, obtendremos el business del usuario autenticado
        # if request.user.is_authenticated and hasattr(request.user, 'business_id'):
        #     business_id = request.user.business_id
        #     set_current_business_id(business_id)
        
        response = self.get_response(request)
        
        # Limpiar al final
        set_current_business_id(None)
        
        return response
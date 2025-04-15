import threading

# Variable thread-local para almacenar el business_id actual
_thread_local = threading.local()

def get_current_business_id():
    """Obtiene el business_id almacenado en el hilo actual"""
    return getattr(_thread_local, 'business_id', None)

def set_current_business_id(business_id):
    """Establece el business_id en el hilo actual"""
    _thread_local.business_id = business_id

# Actualización en middleware.py
class BusinessMiddleware:
    def __call__(self, request):
        set_current_business_id(None)
        if request.user.is_authenticated and hasattr(request.user, 'business'):
            if request.user.business:
                business_id = request.user.business.id
                set_current_business_id(business_id)
        response = self.get_response(request)
        set_current_business_id(None)
        return response
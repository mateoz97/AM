
class BusinessRouter:
    """
    Router para dirigir consultas a la base de datos correcta según el business.
    """
    
    # Aplicaciones de Django core que siempre van en la base de datos default
    django_core_apps = {
        'admin', 'auth', 'contenttypes', 'sessions', 'messages', 
        'staticfiles', 'rest_framework', 'rest_framework_simplejwt',
        'corsheaders', 'django_filters'
    }
    
    def db_for_read(self, model, **hints):
        """Determina qué base de datos usar para lecturas"""
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        
        # Los modelos de Django core siempre a default
        if app_label in self.django_core_apps:
            return 'default'
        
        # Todos los modelos de accounts van a default
        if app_label == 'accounts' and model_name in ['business', 'customuser', 'businessrole', 'rolepermission']:
            return 'default'
        
        # MODIFICAR ESTA PARTE - Verificar que la conexión exista antes de intentar usarla
        from config.middleware import get_current_business_id
        from django.conf import settings
        
        business_id = get_current_business_id()
        if business_id:
            db_name = f'business_{business_id}'
            # Verificar si la base de datos existe en la configuración
            if db_name in settings.DATABASES:
                return db_name
        
        # Si no hay business en el contexto o la bd no existe, usar default
        return 'default'
    
    def db_for_write(self, model, **hints):
        """Misma lógica que para lectura"""
        return self.db_for_read(model, **hints)
    
    def allow_relation(self, obj1, obj2, **hints):
        """Permitir relaciones entre objetos"""
        # Permitir relaciones dentro de las apps de Django core
        if (obj1._meta.app_label in self.django_core_apps and
            obj2._meta.app_label in self.django_core_apps):
            return True
            
        # Permitir relaciones entre modelos de accounts
        if obj1._meta.app_label == 'accounts' and obj2._meta.app_label == 'accounts':
            return True
            
        # Por ahora, permitir todas las relaciones durante desarrollo
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Controla qué tablas se crean en qué bases de datos"""
        # Apps core de Django solo migran a default
        if app_label in self.django_core_apps:
            return db == 'default'
            
        # Modelos de accounts migran a default
        if app_label == 'business' and model_name in ['business', 'customuser', 'businessrole', 'rolepermission']:
            return db == 'default'
            
        # En etapa inicial, permitimos migrar todos los demás modelos a business_1
        if db.startswith('business_') and app_label not in self.django_core_apps:
            return True
            
        # Por defecto, permitir migración a default
        return db == 'default'
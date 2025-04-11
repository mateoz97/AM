

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
        
        # Los modelos de Django core siempre a default
        if app_label in self.django_core_apps:
            return 'default'
        
        # El modelo Business y CustomUser van a default
        if app_label == 'auth_app' and model._meta.model_name in ['business', 'customuser']:
            return 'default'
            
        # Para el desarrollo inicial, usamos business_1 para todos los demás modelos
        # Más adelante implementaremos la lógica para obtener el business del contexto
        return 'business_1'
    
    def db_for_write(self, model, **hints):
        """Misma lógica que para lectura"""
        return self.db_for_read(model, **hints)
    
    def allow_relation(self, obj1, obj2, **hints):
        """Permitir relaciones entre objetos"""
        # Permitir relaciones dentro de las apps de Django core
        if (obj1._meta.app_label in self.django_core_apps and
            obj2._meta.app_label in self.django_core_apps):
            return True
            
        # Permitir relaciones entre modelos de auth_app
        if obj1._meta.app_label == 'auth_app' and obj2._meta.app_label == 'auth_app':
            return True
            
        # Por ahora, permitir todas las relaciones durante desarrollo
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Controla qué tablas se crean en qué bases de datos"""
        # Apps core de Django solo migran a default
        if app_label in self.django_core_apps:
            return db == 'default'
            
        # Business y CustomUser migran a default
        if app_label == 'auth_app' and model_name in ['business', 'customuser']:
            return db == 'default'
            
        # En etapa inicial, permitimos migrar todos los demás modelos a business_1
        if db == 'business_1' and app_label not in self.django_core_apps:
            return True
            
        # Por defecto, permitir migración a default
        return db == 'default'
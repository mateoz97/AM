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
    
    # Modelos que siempre van en la base de datos default
    default_models = {
        # Modelos de business
        'business.business', 'business.businessjoinrequest', 'business.businessinvitation', 'business.businessbranch',
        # Modelos de roles
        'roles.businessrole', 'roles.rolepermission',
        # Modelos de accounts
        'accounts.customuser',
    }
    
    def db_for_read(self, model, **hints):
        """Determina qué base de datos usar para lecturas"""
        app_label = model._meta.app_label.lower()
        model_name = model._meta.model_name.lower()
        model_path = f"{app_label}.{model_name}"
        
        # Siempre usar 'default' para modelos del sistema y core
        if app_label in self.django_core_apps or model_path in self.default_models:
            return 'default'
        
        # Para otros modelos, seguir el business del contexto
        from config.middleware import get_current_business_id
        from django.conf import settings
        
        business_id = get_current_business_id()
        if business_id:
            db_name = f'business_{business_id}'
            if db_name in settings.DATABASES:
                return db_name
        
        # Si no hay business en el contexto o la base de datos no existe, usar default
        return 'default'
    
    def db_for_write(self, model, **hints):
        """Misma lógica que para lectura"""
        return self.db_for_read(model, **hints)
    
    def allow_relation(self, obj1, obj2, **hints):
        """Permitir relaciones entre objetos"""
        # Permitir relaciones entre modelos de la misma base de datos
        db1 = self.db_for_read(obj1.__class__)
        db2 = self.db_for_read(obj2.__class__)
        
        # Si ambos están en la misma base de datos, permitir la relación
        if db1 == db2:
            return True
            
        # Si uno de ellos está en default, permitir la relación
        if db1 == 'default' or db2 == 'default':
            return True
            
        # Para desarrollo, permitir todas las relaciones
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Controla qué tablas se crean en qué bases de datos"""
        # Convertir a minúsculas para comparaciones consistentes
        app_label = app_label.lower()
        if model_name:
            model_name = model_name.lower()
        
        model_path = f"{app_label}.{model_name}" if model_name else None
        
        # Apps core de Django solo migran a default
        if app_label in self.django_core_apps:
            return db == 'default'
            
        # Modelos que deben estar en la base de datos principal
        if model_path and model_path in self.default_models:
            return db == 'default'
            
        # Para bases de datos de negocios, permitir migraciones de modelos específicos
        if db.startswith('business_'):
            # No migrar modelos principales a bases de datos de negocios
            if model_path and model_path in self.default_models:
                return False
                
            # Permitir migrar los demás modelos a las bases de datos de negocios
            return True
            
        # Por defecto, permitir migración a default
        return db == 'default'
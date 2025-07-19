class MultitenantRouter:
    """
    Router para arquitectura multitenant con PostgreSQL schemas.
    
    Schema Principal (public): Usuarios, negocios (metadata), red social
    Schemas de Negocio (business_X): Roles, inventario, órdenes, pagos
    """
    
    # Aplicaciones de Django core que siempre van en el esquema public
    django_core_apps = {
        'admin', 'auth', 'contenttypes', 'sessions', 'messages', 
        'staticfiles', 'rest_framework', 'rest_framework_simplejwt',
        'corsheaders', 'django_filters', 'channels'
    }
    
    # Modelos que van en el schema PRINCIPAL (public)
    public_schema_models = {
        # Usuarios y autenticación
        'accounts.customuser',
        
        # Negocios (solo metadatos)
        'business.business', 
        'business.businessjoinrequest', 
        'business.businessinvitation', 
        'business.businessbranch',
        
        # Red social global
        'posts.post',
        'posts.comment', 
        'posts.like',
        'posts.follow',
        
        # Configuraciones globales de usuario
        'settings.usersettings',
    }
    
    # Modelos que van en schemas de NEGOCIO (business_X)
    business_schema_models = {
        # Roles específicos del negocio
        'roles.businessrole',
        'roles.rolepermission',
        
        # Inventario
        'inventory.product',
        'inventory.category', 
        'inventory.stock',
        'inventory.stockmovement',
        
        # Órdenes
        'orders.order',
        'orders.orderitem',
        'orders.orderstatushistory',
        'orders.ordernotification',
        'orders.orderauditlog',
        
        # Configuraciones del negocio
        'settings.businesssettings',
        'settings.notificationtemplate',
        
        # Pagos (futuro)
        'payments.transaction',
        'payments.paymentmethod', 
        'payments.invoice',
    }
    
    def _get_model_key(self, model):
        """Obtiene la clave del modelo para comparación"""
        if hasattr(model, '_meta'):
            return f"{model._meta.app_label}.{model._meta.model_name}"
        return None
    
    def _should_use_business_schema(self, model):
        """Determina si un modelo debe usar schema de negocio"""
        model_key = self._get_model_key(model)
        return model_key and model_key.lower() in self.business_schema_models
    
    def _should_use_public_schema(self, model):
        """Determina si un modelo debe usar schema público"""
        model_key = self._get_model_key(model)
        if not model_key:
            return True
            
        app_label = model._meta.app_label
        
        # Django core apps siempre van a public
        if app_label in self.django_core_apps:
            return True
            
        # Modelos específicamente marcados para public
        return model_key.lower() in self.public_schema_models
    
    def db_for_read(self, model, **hints):
        """Todas las operaciones usan la misma base de datos PostgreSQL"""
        return 'default'
    
    def db_for_write(self, model, **hints):
        """Todas las operaciones usan la misma base de datos PostgreSQL"""
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """Permitir relaciones dentro de la misma base de datos"""
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Controla dónde se ejecutan las migraciones según el modelo"""
        if db != 'default':
            return False
            
        # Si no hay modelo específico, permitir (migraciones iniciales)
        if not model_name:
            return True
            
        # Determinar si la migración debe ejecutarse
        model_key = f"{app_label}.{model_name}".lower()
        
        # Django core apps siempre migran
        if app_label in self.django_core_apps:
            return True
            
        # Permitir migración si el modelo está en alguna de nuestras listas
        return (model_key in self.public_schema_models or 
                model_key in self.business_schema_models)
    
    def get_schema_for_model(self, model):
        """Obtiene el schema apropiado para un modelo"""
        if self._should_use_public_schema(model):
            return 'public'
        elif self._should_use_business_schema(model):
            # Obtener business_id del contexto actual
            from config.middleware import get_current_business_id
            business_id = get_current_business_id()
            if business_id:
                return f'business_{business_id}'
            else:
                # Si no hay contexto de negocio, usar public como fallback
                return 'public'
        else:
            return 'public'


# Alias para compatibilidad
BusinessRouter = MultitenantRouter
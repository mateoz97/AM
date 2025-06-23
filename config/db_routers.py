class BusinessRouter:
    """
    Router para dirigir consultas según el business usando esquemas PostgreSQL.
    En PostgreSQL usamos un solo database con múltiples esquemas.
    """
    
    # Aplicaciones de Django core que siempre van en el esquema public (default)
    django_core_apps = {
        'admin', 'auth', 'contenttypes', 'sessions', 'messages', 
        'staticfiles', 'rest_framework', 'rest_framework_simplejwt',
        'corsheaders', 'django_filters'
    }
    
    # Modelos que siempre van en el esquema public (default)
    default_models = {
        # Modelos de business
        'business.business', 'business.businessjoinrequest', 'business.businessinvitation', 'business.businessbranch',
        # Modelos de roles
        'roles.businessrole', 'roles.rolepermission',
        # Modelos de accounts
        'accounts.customuser',
    }
    
    def db_for_read(self, model, **hints):
        """Con PostgreSQL, siempre usamos la misma base de datos"""
        return 'default'
    
    def db_for_write(self, model, **hints):
        """Con PostgreSQL, siempre usamos la misma base de datos"""
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """Permitir todas las relaciones ya que estamos en la misma base de datos"""
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Permitir todas las migraciones en la base de datos default"""
        return db == 'default'
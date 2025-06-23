# app/core/managers.py
"""
Managers personalizados para manejar esquemas de PostgreSQL automáticamente.
"""

from django.db import models
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class SchemaAwareManager(models.Manager):
    """
    Manager que automáticamente configura el esquema correcto basado en el negocio actual.
    """
    
    def get_queryset(self):
        """Retorna el queryset con el esquema correcto configurado"""
        self._ensure_schema_context()
        return super().get_queryset()
    
    def _ensure_schema_context(self):
        """Asegura que el contexto del esquema esté configurado correctamente"""
        try:
            from config.middleware import get_current_business_id, get_current_schema
            
            business_id = get_current_business_id()
            if business_id:
                schema_name = get_current_schema()
                
                # Verificar que el esquema existe
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT schema_name 
                        FROM information_schema.schemata 
                        WHERE schema_name = %s
                    """, [schema_name])
                    
                    if not cursor.fetchone():
                        # Si el esquema no existe, crearlo automáticamente
                        self._create_schema_if_needed(business_id)
                        
        except Exception as e:
            logger.error(f"Error en contexto de esquema: {str(e)}")
            # No fallar las queries por problemas de esquema
            pass
    
    def _create_schema_if_needed(self, business_id):
        """Crea el esquema si no existe"""
        try:
            from app.business.services.business_service import DatabaseService
            from app.business.models.business import Business
            
            business = Business.objects.get(id=business_id)
            DatabaseService.create_business_database(business)
            logger.info(f"Esquema creado automáticamente para negocio {business_id}")
            
        except Exception as e:
            logger.error(f"Error al crear esquema automáticamente: {str(e)}")
    
    def create(self, **kwargs):
        """Override create para asegurar el contexto del esquema"""
        self._ensure_schema_context()
        return super().create(**kwargs)
    
    def get_or_create(self, defaults=None, **kwargs):
        """Override get_or_create para asegurar el contexto del esquema"""
        self._ensure_schema_context()
        return super().get_or_create(defaults=defaults, **kwargs)
    
    def update_or_create(self, defaults=None, **kwargs):
        """Override update_or_create para asegurar el contexto del esquema"""
        self._ensure_schema_context()
        return super().update_or_create(defaults=defaults, **kwargs)


class BusinessSpecificManager(SchemaAwareManager):
    """
    Manager específico para modelos que pertenecen a un negocio.
    Automáticamente filtra por el negocio actual.
    """
    
    def get_queryset(self):
        """Filtra automáticamente por el negocio actual"""
        queryset = super().get_queryset()
        
        try:
            from config.middleware import get_current_business_id
            
            business_id = get_current_business_id()
            if business_id and hasattr(self.model, 'business'):
                queryset = queryset.filter(business_id=business_id)
                
        except Exception as e:
            logger.error(f"Error al filtrar por negocio: {str(e)}")
        
        return queryset
    
    def create(self, **kwargs):
        """Asigna automáticamente el negocio actual al crear"""
        try:
            from config.middleware import get_current_business_id
            
            business_id = get_current_business_id()
            if business_id and hasattr(self.model, 'business') and 'business' not in kwargs:
                from app.business.models.business import Business
                business = Business.objects.get(id=business_id)
                kwargs['business'] = business
                
        except Exception as e:
            logger.error(f"Error al asignar negocio automáticamente: {str(e)}")
        
        return super().create(**kwargs)


class UserSpecificManager(SchemaAwareManager):
    """
    Manager para modelos que están vinculados a un usuario específico.
    """
    
    def for_user(self, user):
        """Filtra por usuario específico"""
        return self.get_queryset().filter(user=user)
    
    def for_current_business(self):
        """Filtra por el negocio actual del contexto"""
        try:
            from config.middleware import get_current_business_id
            
            business_id = get_current_business_id()
            if business_id and hasattr(self.model, 'business'):
                return self.get_queryset().filter(business_id=business_id)
            
        except Exception as e:
            logger.error(f"Error al filtrar por negocio actual: {str(e)}")
        
        return self.get_queryset()
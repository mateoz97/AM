# app/core/managers.py
"""
Managers personalizados para manejar esquemas de PostgreSQL automáticamente.
Optimizado para performance y memory management.
"""

from django.db import models
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import logging
import time
import threading
import weakref
import structlog

logger = structlog.get_logger(__name__)
django_logger = logging.getLogger(__name__)

# Cache global para esquemas verificados
_schema_cache = {}
_schema_cache_lock = threading.Lock()
_connection_pool = weakref.WeakSet()

# Configuración de timeouts
SCHEMA_CACHE_TIMEOUT = getattr(settings, 'SCHEMA_CACHE_TIMEOUT', 300)  # 5 minutos
QUERY_TIMEOUT = getattr(settings, 'QUERY_TIMEOUT', 30)  # 30 segundos


class SchemaAwareManager(models.Manager):
    """
    Manager que automáticamente configura el esquema correcto basado en el negocio actual.
    Optimizado para performance con cache y connection pooling.
    """
    
    def __init__(self):
        super().__init__()
        self._local_cache = {}
    
    def get_queryset(self):
        """Retorna el queryset con el esquema correcto configurado"""
        try:
            self._ensure_schema_context()
            return super().get_queryset()
        except Exception as e:
            logger.error("get_queryset_error", error=str(e))
            # Retornar queryset vacío en caso de error para evitar crashes
            return super().get_queryset().none()
    
    def _ensure_schema_context(self):
        """Asegura que el contexto del esquema esté configurado correctamente"""
        try:
            from config.middleware import get_current_business_id, get_current_schema
            
            business_id = get_current_business_id()
            if not business_id:
                return
                
            schema_name = get_current_schema()
            
            # Verificar cache primero
            if self._is_schema_cached(schema_name):
                return
            
            # Verificar con timeout
            if self._verify_schema_exists(schema_name):
                self._cache_schema(schema_name)
            else:
                # Si el esquema no existe, crearlo automáticamente
                self._create_schema_if_needed(business_id)
                        
        except Exception as e:
            logger.error("schema_context_error", error=str(e))
            # No fallar las queries por problemas de esquema
            pass
    
    def _is_schema_cached(self, schema_name):
        """Verifica si el esquema está en cache y es válido"""
        with _schema_cache_lock:
            cache_entry = _schema_cache.get(schema_name)
            if cache_entry:
                # Verificar si no ha expirado
                if time.time() - cache_entry['timestamp'] < SCHEMA_CACHE_TIMEOUT:
                    return True
                else:
                    # Limpiar entrada expirada
                    del _schema_cache[schema_name]
        return False
    
    def _cache_schema(self, schema_name):
        """Guarda el esquema en cache"""
        with _schema_cache_lock:
            _schema_cache[schema_name] = {
                'timestamp': time.time(),
                'verified': True
            }
    
    def _verify_schema_exists(self, schema_name):
        """Verifica que el esquema existe con timeout"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, [schema_name])
                
                # Registrar conexión en pool
                _connection_pool.add(connection)
                
                result = cursor.fetchone()
                return result is not None
                
        except Exception as e:
            logger.error("schema_verification_error", 
                        schema_name=schema_name,
                        error=str(e))
            return False
    
    def create(self, **kwargs):
        """Override create con manejo de errores optimizado"""
        try:
            return super().create(**kwargs)
        except Exception as e:
            logger.error("manager_create_error", 
                        model=self.model.__name__,
                        error=str(e))
            raise
    
    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        """Override bulk_create con manejo optimizado"""
        try:
            if batch_size is None:
                batch_size = 1000  # Batch size por defecto
            
            return super().bulk_create(objs, batch_size, ignore_conflicts)
        except Exception as e:
            logger.error("manager_bulk_create_error", 
                        model=self.model.__name__,
                        count=len(objs),
                        error=str(e))
            raise
    
    def _create_schema_if_needed(self, business_id):
        """Crea el esquema si no existe"""
        try:
            from app.business.services.business_service import DatabaseService
            from app.business.models.business import Business
            
            business = Business.objects.get(id=business_id)
            result = DatabaseService.create_business_database(business)
            
            if result:
                logger.info("schema_auto_created", 
                           business_id=business_id,
                           schema_name=f"business_{business_id}")
            else:
                logger.error("schema_auto_creation_failed", 
                            business_id=business_id)
                
        except Exception as e:
            logger.error("schema_creation_error", 
                        business_id=business_id,
                        error=str(e))


class OptimizedBusinessSpecificManager(SchemaAwareManager):
    """
    Manager optimizado específico para modelos de negocio.
    Incluye optimizaciones adicionales para queries frecuentes.
    """
    
    def __init__(self):
        super().__init__()
        self._query_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def get_for_business(self, business_id):
        """Obtiene objetos para un negocio específico con cache"""
        cache_key = f"business_{business_id}_{self.model.__name__}"
        
        # Verificar cache
        cached_result = self._query_cache.get(cache_key)
        if cached_result and time.time() - cached_result['timestamp'] < 60:  # 1 minuto
            self._cache_hits += 1
            return cached_result['queryset']
        
        # Query a la base de datos
        queryset = self.filter(business_id=business_id)
        
        # Guardar en cache
        self._query_cache[cache_key] = {
            'queryset': queryset,
            'timestamp': time.time()
        }
        self._cache_misses += 1
        
        return queryset
    
    def get_cache_stats(self):
        """Obtiene estadísticas de cache"""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'hit_rate': hit_rate,
            'cache_size': len(self._query_cache)
        }
    
    def clear_cache(self):
        """Limpia el cache del manager"""
        self._query_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("manager_cache_cleared", 
                   model=self.model.__name__)


# Alias para compatibilidad
BusinessSpecificManager = OptimizedBusinessSpecificManager


class ConnectionPoolManager:
    """Manager para el pool de conexiones"""
    
    @staticmethod
    def get_active_connections():
        """Obtiene el número de conexiones activas"""
        return len(_connection_pool)
    
    @staticmethod
    def cleanup_connections():
        """Limpia conexiones inactivas"""
        try:
            # Las conexiones se limpian automáticamente por WeakSet
            # cuando son garbage collected
            import gc
            gc.collect()
            
            logger.info("connections_cleaned", 
                       active_connections=len(_connection_pool))
        except Exception as e:
            logger.error("connection_cleanup_error", error=str(e))
    
    @staticmethod
    def get_connection_stats():
        """Obtiene estadísticas de conexiones"""
        return {
            'active_connections': len(_connection_pool),
            'schema_cache_size': len(_schema_cache),
            'cache_timeout': SCHEMA_CACHE_TIMEOUT,
            'query_timeout': QUERY_TIMEOUT
        }


class SchemaCacheManager:
    """Manager para el cache de esquemas"""
    
    @staticmethod
    def clear_cache():
        """Limpia el cache de esquemas"""
        with _schema_cache_lock:
            _schema_cache.clear()
        logger.info("schema_cache_cleared")
    
    @staticmethod
    def get_cache_stats():
        """Obtiene estadísticas del cache"""
        with _schema_cache_lock:
            now = time.time()
            valid_entries = 0
            expired_entries = 0
            
            for entry in _schema_cache.values():
                if now - entry['timestamp'] < SCHEMA_CACHE_TIMEOUT:
                    valid_entries += 1
                else:
                    expired_entries += 1
            
            return {
                'total_entries': len(_schema_cache),
                'valid_entries': valid_entries,
                'expired_entries': expired_entries,
                'cache_timeout': SCHEMA_CACHE_TIMEOUT
            }
    
    @staticmethod
    def cleanup_expired():
        """Limpia entradas expiradas del cache"""
        with _schema_cache_lock:
            now = time.time()
            expired_keys = []
            
            for key, entry in _schema_cache.items():
                if now - entry['timestamp'] >= SCHEMA_CACHE_TIMEOUT:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del _schema_cache[key]
            
            logger.info("schema_cache_cleanup", 
                       expired_entries=len(expired_keys))
            
            return len(expired_keys)


def cleanup_managers():
    """Función global para limpiar todos los managers"""
    try:
        # Limpiar cache de esquemas
        SchemaCacheManager.clear_cache()
        
        # Limpiar conexiones
        ConnectionPoolManager.cleanup_connections()
        
        # Forzar garbage collection
        import gc
        collected = gc.collect()
        
        logger.info("managers_cleanup_completed", 
                   objects_collected=collected)
        
        return True
    except Exception as e:
        logger.error("managers_cleanup_error", error=str(e))
        return False


def get_system_stats():
    """Obtiene estadísticas del sistema de managers"""
    return {
        'connection_stats': ConnectionPoolManager.get_connection_stats(),
        'schema_cache_stats': SchemaCacheManager.get_cache_stats(),
        'timestamp': time.time()
    }
# Models
 
# Management
import logging
import os
import traceback
import time
from django.conf import settings
from django.db import transaction, connection
from django.core.exceptions import ValidationError
import structlog

# Configurar logging estructurado
logger = structlog.get_logger(__name__)
django_logger = logging.getLogger(__name__)



class DatabaseService:
    
    @staticmethod
    @transaction.atomic
    def create_business_database(business):
        """
        Crea un nuevo esquema en PostgreSQL para un business de manera atómica.
        Con PostgreSQL usamos esquemas en lugar de bases de datos separadas.
        Implementa rollback automático en caso de error.
        """
        if not business or not business.id:
            logger.error("schema_creation_failed", 
                        error="invalid_business", 
                        business_id=getattr(business, 'id', None))
            raise ValidationError("Se intentó crear esquema para un negocio inválido o sin ID")
            
        schema_name = f"business_{business.id}"
        start_time = time.time()
        
        logger.info("schema_creation_started", 
                   business_id=business.id,
                   business_name=business.name,
                   schema_name=schema_name)
        
        try:
            # Verificar si el esquema ya existe
            if DatabaseService._schema_exists(schema_name):
                logger.warning("schema_already_exists", 
                             schema_name=schema_name, 
                             business_id=business.id)
                return True
            
            # Crear savepoint para rollback granular
            with transaction.savepoint():
                with connection.cursor() as cursor:
                    # Crear el esquema
                    cursor.execute(f"CREATE SCHEMA {schema_name}")
                    logger.info("schema_created", 
                               schema_name=schema_name,
                               business_id=business.id)
                    
                    # Configurar permisos básicos
                    cursor.execute(f"""
                        GRANT USAGE ON SCHEMA {schema_name} TO CURRENT_USER;
                        GRANT CREATE ON SCHEMA {schema_name} TO CURRENT_USER;
                    """)
                    
                    # Verificar creación exitosa
                    if not DatabaseService._schema_exists(schema_name):
                        raise ValidationError(f"Schema {schema_name} no fue creado correctamente")
                    
                    # Configurar search_path
                    DatabaseService._configure_search_path(business.id)
                    
                    # Crear tablas específicas del negocio si es necesario
                    DatabaseService._create_business_tables(cursor, schema_name)
                    
                    # Verificar integridad post-creación
                    if not DatabaseService._verify_schema_integrity(schema_name):
                        raise ValidationError(f"Verificación de integridad falló para {schema_name}")
                    
                    duration = time.time() - start_time
                    logger.info("schema_creation_completed", 
                               schema_name=schema_name,
                               business_id=business.id,
                               duration=round(duration, 3))
                    
                    return True
                    
        except Exception as e:
            duration = time.time() - start_time
            logger.error("schema_creation_failed", 
                        schema_name=schema_name,
                        business_id=business.id,
                        error=str(e),
                        duration=round(duration, 3),
                        exc_info=True)
            
            # El rollback se maneja automáticamente por @transaction.atomic
            raise ValidationError(f"Error al crear esquema {schema_name}: {str(e)}")
    
    @staticmethod
    def _schema_exists(schema_name):
        """
        Verifica si un esquema existe en PostgreSQL.
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 1 FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, [schema_name])
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error("schema_exists_check_failed", 
                        schema_name=schema_name, 
                        error=str(e))
            return False
    
    @staticmethod
    def _create_business_tables(cursor, schema_name):
        """
        Crea tablas específicas del negocio en el esquema.
        """
        try:
            # Establecer el search_path para crear tablas en el esquema correcto
            cursor.execute(f"SET search_path TO {schema_name}, public")
            
            # Aquí puedes agregar creación de tablas específicas si es necesario
            # Por ejemplo, tablas de configuración específicas por negocio
            
            logger.info("business_tables_created", schema_name=schema_name)
            
        except Exception as e:
            logger.error("business_tables_creation_failed", 
                        schema_name=schema_name, 
                        error=str(e))
            raise
    
    @staticmethod
    def _verify_schema_integrity(schema_name):
        """
        Verifica la integridad del esquema después de su creación.
        """
        try:
            with connection.cursor() as cursor:
                # Verificar que el esquema existe
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, [schema_name])
                
                if not cursor.fetchone():
                    return False
                
                # Verificar permisos básicos
                cursor.execute(f"""
                    SELECT has_schema_privilege(CURRENT_USER, '{schema_name}', 'USAGE')
                """)
                
                has_usage = cursor.fetchone()[0]
                if not has_usage:
                    logger.error("schema_integrity_failed", 
                                schema_name=schema_name, 
                                error="missing_usage_permission")
                    return False
                
                logger.info("schema_integrity_verified", schema_name=schema_name)
                return True
                
        except Exception as e:
            logger.error("schema_integrity_check_failed", 
                        schema_name=schema_name, 
                        error=str(e))
            return False
    
    @staticmethod
    def _configure_search_path(business_id):
        """
        Configura el search_path para incluir el esquema del negocio.
        """
        try:
            schema_name = f"business_{business_id}"
            
            with connection.cursor() as cursor:
                # Configurar search_path para incluir el esquema del negocio
                cursor.execute(f"SET search_path TO {schema_name}, public")
                logger.info("search_path_configured", 
                           schema_name=schema_name,
                           business_id=business_id)
                
        except Exception as e:
            logger.error("search_path_configuration_failed", 
                        schema_name=f"business_{business_id}",
                        business_id=business_id,
                        error=str(e))
            raise
    
    @staticmethod
    def switch_to_business_schema(business_id):
        """
        Cambia el contexto actual al esquema del negocio especificado.
        """
        if not business_id:
            return False
            
        try:
            DatabaseService._configure_search_path(business_id)
            return True
        except Exception as e:
            logger.error(f"❌ Error al cambiar al esquema del negocio {business_id}: {str(e)}")
            return False
            
    @staticmethod
    def verify_business_database(business_id):
        """
        Verifica si el esquema PostgreSQL para un negocio existe
        """
        if not business_id:
            return False, "ID de negocio no proporcionado"
            
        schema_name = f"business_{business_id}"
        
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Verificar si el esquema existe
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, [schema_name])
                
                schema_exists = cursor.fetchone() is not None
                
                if schema_exists:
                    # Obtener lista de tablas en el esquema
                    cursor.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = %s
                    """, [schema_name])
                    
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    return True, {
                        "schema_name": schema_name,
                        "tables": tables,
                        "table_count": len(tables)
                    }
                else:
                    return False, {
                        "schema_name": schema_name,
                        "error": "El esquema no existe"
                    }
                    
        except Exception as e:
            return False, f"Error al verificar esquema: {str(e)}"
    
    @staticmethod
    def delete_business_schema(business_id):
        """
        Elimina el esquema PostgreSQL de un negocio.
        ¡CUIDADO! Esta operación es irreversible y elimina todos los datos.
        """
        if not business_id:
            logger.error("❌ Se intentó eliminar esquema para un negocio sin ID")
            return False
            
        schema_name = f"business_{business_id}"
        
        logger.warning(f"⚠️ ELIMINANDO esquema PostgreSQL: {schema_name} - Esta operación es IRREVERSIBLE")
        
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Verificar que el esquema existe antes de intentar eliminarlo
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, [schema_name])
                
                if not cursor.fetchone():
                    logger.warning(f"⚠️ El esquema {schema_name} no existe, no hay nada que eliminar")
                    return True
                
                # Terminar todas las conexiones activas al esquema
                try:
                    cursor.execute("""
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = current_database()
                        AND pid <> pg_backend_pid()
                        AND query ILIKE %s
                    """, [f'%{schema_name}%'])
                    logger.info(f"Conexiones activas terminadas para esquema {schema_name}")
                except Exception as conn_error:
                    logger.warning(f"No se pudieron terminar algunas conexiones para {schema_name}: {str(conn_error)}")
                
                # Eliminar el esquema y todo su contenido
                cursor.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
                
                # Pequeña pausa para evitar problemas de concurrencia
                import time
                time.sleep(0.1)
                
                logger.info(f"✅ Esquema {schema_name} eliminado exitosamente")
                
                # Verificar que el esquema fue eliminado
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, [schema_name])
                
                if cursor.fetchone():
                    logger.error(f"❌ El esquema {schema_name} aún existe después de la eliminación")
                    return False
                else:
                    logger.info(f"✅ Eliminación del esquema {schema_name} verificada")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Error al eliminar esquema {schema_name}: {str(e)}", exc_info=True)
            return False
    
    @staticmethod
    def get_business_schema_name(business_id):
        """
        Obtiene el nombre del esquema para un negocio específico.
        """
        if not business_id:
            return None
        return f"business_{business_id}"
    
    @staticmethod
    def list_business_schemas():
        """
        Lista todos los esquemas de negocios existentes en la base de datos.
        """
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Buscar todos los esquemas que sigan el patrón business_*
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name LIKE 'business_%'
                    ORDER BY schema_name
                """)
                
                schemas = [row[0] for row in cursor.fetchall()]
                
                # Extraer los IDs de negocio de los nombres de esquema
                business_schemas = []
                for schema in schemas:
                    try:
                        business_id = int(schema.replace('business_', ''))
                        business_schemas.append({
                            'schema_name': schema,
                            'business_id': business_id
                        })
                    except ValueError:
                        # Esquema que no sigue el patrón esperado
                        business_schemas.append({
                            'schema_name': schema,
                            'business_id': None
                        })
                
                return business_schemas
                
        except Exception as e:
            logger.error(f"❌ Error al listar esquemas de negocios: {str(e)}")
            return []
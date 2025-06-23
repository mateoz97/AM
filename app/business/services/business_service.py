# Models
 
# Management
import logging
import os
import traceback
from django.conf import settings


logger = logging.getLogger(__name__)



class DatabaseService:
    
    @staticmethod
    def create_business_database(business):
        """
        Crea un nuevo esquema en PostgreSQL para un business.
        Con PostgreSQL usamos esquemas en lugar de bases de datos separadas.
        """
        if not business or not business.id:
            logger.error("❌ Se intentó crear esquema para un negocio inválido o sin ID")
            return False
            
        schema_name = f"business_{business.id}"
        
        logger.info(f"Creando esquema PostgreSQL: {schema_name} para negocio {business.name}")
        
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Crear el esquema si no existe
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
                logger.info(f"✅ Esquema {schema_name} creado exitosamente")
                
                # Verificar que el esquema fue creado
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, [schema_name])
                
                if cursor.fetchone():
                    logger.info(f"✅ Esquema {schema_name} verificado en PostgreSQL")
                    
                    # Configurar el search_path para incluir el nuevo esquema
                    DatabaseService._configure_search_path(business.id)
                    
                    return True
                else:
                    logger.error(f"❌ No se pudo verificar la creación del esquema {schema_name}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error al crear esquema {schema_name}: {str(e)}", exc_info=True)
            return False
    
    @staticmethod
    def _configure_search_path(business_id):
        """
        Configura el search_path para incluir el esquema del negocio.
        """
        try:
            from django.db import connection
            schema_name = f"business_{business_id}"
            
            with connection.cursor() as cursor:
                # Configurar search_path para incluir el esquema del negocio
                cursor.execute(f"SET search_path TO {schema_name}, public")
                logger.info(f"✅ Search path configurado para esquema {schema_name}")
                
        except Exception as e:
            logger.error(f"❌ Error al configurar search_path: {str(e)}")
    
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
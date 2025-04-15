from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import Business
import os
from django.conf import settings

@receiver(post_delete, sender=Business)
def delete_business_database(sender, instance, **kwargs):
    """
    Signal que se activa antes de eliminar un negocio
    Elimina la base de datos asociada
    """
    # Nombre de la base de datos asociada
    db_name = f"business_{instance.name}"
    db_path = None
    
    # Verificar si la base de datos existe en la configuración
    if db_name in settings.DATABASES:
        db_config = settings.DATABASES[db_name]
        db_path = db_config.get('NAME')
        print(f"Path de base de datos a eliminar: {db_path}")
        
        # Si es un objeto Path, convertirlo a string
        if hasattr(db_path, 'resolve'):
            db_path = str(db_path.resolve())
            
        # Eliminar la base de datos de la configuración
        del settings.DATABASES[db_name]
        print(f"Eliminada configuración de base de datos {db_name}")
    else:
        # Si no está en DATABASES, construir el path manualmente
        db_path = str(settings.BASE_DIR / f"db_{db_name}.sqlite3")
        print(f"Base de datos no encontrada en settings, intentando path: {db_path}")
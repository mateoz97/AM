# app/accounts/services/role_service.py
"""
Servicio para gestionar roles de negocio desde el contexto de accounts.
Este módulo proporciona una interfaz para trabajar con roles cuando se crean usuarios.
"""

from app.roles.services.role_service import BusinessRoleService as BaseBusinessRoleService


class BusinessRoleService:
    """
    Wrapper del BusinessRoleService para mantener compatibilidad con imports existentes.
    Delega todas las operaciones al servicio principal en la app roles.
    """
    
    @staticmethod
    def create_default_roles(business):
        """
        Crea roles por defecto para un negocio.
        
        Args:
            business (Business): Instancia del negocio
            
        Returns:
            dict: Diccionario con los roles creados
        """
        return BaseBusinessRoleService.create_business_roles(business)
    
    @staticmethod
    def create_business_roles(business):
        """
        Alias para create_default_roles para mantener compatibilidad.
        
        Args:
            business (Business): Instancia del negocio
            
        Returns:
            dict: Diccionario con los roles creados
        """
        return BaseBusinessRoleService.create_business_roles(business)
    
    @staticmethod
    def assign_role_to_user(user, role_name):
        """
        Asigna un rol específico a un usuario.
        
        Args:
            user (CustomUser): Usuario a actualizar
            role_name (str): Nombre del rol a asignar
            
        Returns:
            bool: True si se asignó correctamente, False en caso contrario
        """
        return BaseBusinessRoleService.assign_role_to_user(user, role_name)
    
    @staticmethod
    def get_roles_for_business(business):
        """
        Obtiene todos los roles disponibles para un negocio.
        
        Args:
            business (Business): Instancia del negocio
            
        Returns:
            QuerySet: QuerySet con los roles del negocio
        """
        return BaseBusinessRoleService.get_roles_for_business(business)
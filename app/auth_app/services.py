from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from .models import Business 

class RoleService:
    @staticmethod
    def create_business_roles(business):
        if not business or not business.name:
            return  # Evita errores si el negocio aún no está completamente creado

        roles_permissions = {
            "Admin": ["add", "change", "delete", "view"],
            "Gerente": ["view", "change"],
            "Cocinero": ["view", "change"],
            "Mesero": ["view", "add"],
            "Cliente": ["view"],
        }

        for role, permissions in roles_permissions.items():
            group_name = f"{business.name}_{role}"
            group, created = Group.objects.get_or_create(name=group_name)

            if created:
                for permission in permissions:
                    perms = Permission.objects.filter(codename__startswith=permission)
                    group.permissions.add(*perms)

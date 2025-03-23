from django.contrib.auth.models import Group
from .models import Business

class RoleService:
    @staticmethod
    def create_business_roles(Business):
        roles = ["Admin", "Gerente", "Cocinero", "Mesero", "Cliente"]
        for role in roles:
            group_name = f"{Business.name}_{role}"
            Group.objects.get_or_create(name=group_name)

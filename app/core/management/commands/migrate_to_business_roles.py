from django.core.management.base import BaseCommand
from app.accounts.models import CustomUser, Business, BusinessRole
from app.accounts.services import BusinessRoleService

class Command(BaseCommand):
    help = 'Migra usuarios existentes al nuevo sistema de roles de negocio'

    def handle(self, *args, **options):
        # Asegurarse de que todos los negocios tengan los roles predeterminados
        self.stdout.write("Creando roles predeterminados para todos los negocios...")
        businesses = Business.objects.all()
        
        for business in businesses:
            self.stdout.write(f"Procesando negocio: {business.name}")
            roles = BusinessRoleService.create_default_roles(business)
            
            # Migrar usuarios del negocio
            users = CustomUser.objects.filter(business=business)
            
            for user in users:
                # Determinar qué rol asignar basado en el rol antiguo
                old_role_name = user.role.name if user.role else None
                new_role = None
                
                if old_role_name:
                    # Si el rol antiguo contiene "Admin", asignar rol de Administrador
                    if "admin" in old_role_name.lower():
                        new_role = roles.get("Administrador")
                    # Si contiene "Mesero", asignar rol de Mesero, etc.
                    elif "mesero" in old_role_name.lower():
                        new_role = roles.get("Mesero")
                    elif "cocinero" in old_role_name.lower():
                        new_role = roles.get("Cocinero")
                    else:
                        # Por defecto, asignar Visualizador
                        new_role = roles.get("Visualizador")
                else:
                    # Si no tiene rol, asignar Visualizador
                    new_role = roles.get("Visualizador")
                
                # Asignar el nuevo rol
                if new_role:
                    user.business_role = new_role
                    user.save(update_fields=['business_role'])
                    self.stdout.write(f"  Usuario {user.username}: {new_role.name}")
        
        self.stdout.write(self.style.SUCCESS('Migración completada exitosamente'))
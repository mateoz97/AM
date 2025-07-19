# app/core/management/commands/create_simple_test_user.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import connection
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Crea un usuario simple para probar WebSockets'

    def handle(self, *args, **options):
        """Crea un usuario básico para pruebas"""
        
        self.stdout.write(self.style.SUCCESS('👤 CREANDO USUARIO DE PRUEBA'))
        self.stdout.write('=' * 50)
        
        # Asegurar que usamos el schema main
        with connection.cursor() as cursor:
            cursor.execute("SET search_path TO main")
        
        try:
            # Crear o actualizar usuario de prueba
            user, created = User.objects.get_or_create(
                username='test_user',
                defaults={
                    'email': 'test@example.com',
                    'first_name': 'Usuario',
                    'last_name': 'Prueba',
                    'user_type': 'business_owner',
                    'is_active': True,
                    'is_staff': False,
                    'is_superuser': False
                }
            )
            
            # Establecer password
            user.set_password('password123')
            user.save()
            
            status = '✅ Creado' if created else '⚠️ Actualizado'
            self.stdout.write(f'{status} Usuario: {user.username}')
            self.stdout.write(f'   - Email: {user.email}')
            self.stdout.write(f'   - Nombre: {user.get_full_name()}')
            self.stdout.write(f'   - Password: password123')
            self.stdout.write(f'   - ID: {user.id}')
            
            # Crear rol principal si no existe
            from app.roles.models.main_role import MainRole
            
            try:
                owner_role = MainRole.get_business_owner_role()
                user.main_role = owner_role
                user.save()
                self.stdout.write(f'   - Rol asignado: {owner_role.display_name}')
            except Exception as e:
                self.stdout.write(f'   ⚠️ Error asignando rol: {str(e)}')
            
            self.stdout.write('')
            self.stdout.write('🔑 CREDENCIALES PARA PRUEBAS:')
            self.stdout.write(f'   Username: {user.username}')
            self.stdout.write(f'   Password: password123')
            self.stdout.write('')
            self.stdout.write('📋 INSTRUCCIONES:')
            self.stdout.write('1. Ejecuta el servidor: python manage.py runserver')
            self.stdout.write('2. Obtén token JWT:')
            self.stdout.write('   curl -X POST http://127.0.0.1:8000/api/auth/login/ \\')
            self.stdout.write('     -H "Content-Type: application/json" \\')
            self.stdout.write('     -d \'{"username": "test_user", "password": "password123"}\'')
            self.stdout.write('3. Abre test_websocket.html en tu navegador')
            self.stdout.write('4. Pega el access_token y prueba la conexión')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
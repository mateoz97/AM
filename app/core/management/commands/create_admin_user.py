from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from app.roles.models.main_role import MainRole

User = get_user_model()

class Command(BaseCommand):
    help = 'Create an admin user with proper configuration'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Username for the admin user')
        parser.add_argument('--email', type=str, help='Email for the admin user')
        parser.add_argument('--password', type=str, help='Password for the admin user')

    def handle(self, *args, **options):
        username = options.get('username') or input('Username: ')
        email = options.get('email') or input('Email: ')
        password = options.get('password') or input('Password: ')

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.ERROR(f'User with username "{username}" already exists')
            )
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.ERROR(f'User with email "{email}" already exists')
            )
            return

        try:
            # Create the admin user
            admin_user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name='Admin',
                last_name='User',
                is_staff=True,
                is_superuser=True,
                is_active=True,
                user_type='business_owner'
            )
            
            # Ensure main role is set
            admin_user.ensure_main_role()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created admin user "{username}" (ID: {admin_user.id})'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating admin user: {e}')
            )
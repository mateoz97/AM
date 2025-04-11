# Generated by Django 5.1.7 on 2025-04-11 05:40

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('auth_app', '0007_customuser_address_customuser_date_of_birth_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='business',
            options={'ordering': ['-created_at'], 'permissions': [('view_inactive_business', 'Puede ver negocios inactivos'), ('activate_business', 'Puede activar o desactivar negocios')], 'verbose_name': 'Negocio', 'verbose_name_plural': 'Negocios'},
        ),
        migrations.AlterModelOptions(
            name='customuser',
            options={'ordering': ['username'], 'permissions': [('change_user_role', 'Puede cambiar el rol de un usuario'), ('assign_to_business', 'Puede asignar usuarios a negocios')], 'verbose_name': 'Usuario', 'verbose_name_plural': 'Usuarios'},
        ),
        migrations.AlterField(
            model_name='business',
            name='address',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Dirección'),
        ),
        migrations.AlterField(
            model_name='business',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación'),
        ),
        migrations.AlterField(
            model_name='business',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Descripción'),
        ),
        migrations.AlterField(
            model_name='business',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='Email de contacto'),
        ),
        migrations.AlterField(
            model_name='business',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Activo'),
        ),
        migrations.AlterField(
            model_name='business',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='business_logos/', verbose_name='Logo'),
        ),
        migrations.AlterField(
            model_name='business',
            name='name',
            field=models.CharField(max_length=255, unique=True, verbose_name='Nombre'),
        ),
        migrations.AlterField(
            model_name='business',
            name='owner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_businesses', to='auth_app.customuser', verbose_name='Propietario'),
        ),
        migrations.AlterField(
            model_name='business',
            name='phone',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Teléfono'),
        ),
        migrations.AlterField(
            model_name='business',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Última actualización'),
        ),
        migrations.AlterField(
            model_name='business',
            name='website',
            field=models.URLField(blank=True, null=True, verbose_name='Sitio web'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='address',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Dirección'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='business',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='members', to='auth_app.business', verbose_name='Negocio'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='date_joined',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Fecha de registro'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True, verbose_name='Fecha de nacimiento'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='email',
            field=models.EmailField(max_length=254, unique=True, verbose_name='Correo electrónico'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='first_name',
            field=models.CharField(blank=True, max_length=30, verbose_name='Nombre'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='groups',
            field=models.ManyToManyField(blank=True, related_name='auth_app_users', to='auth.group', verbose_name='grupos'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='id_number',
            field=models.CharField(blank=True, max_length=20, null=True, unique=True, verbose_name='Número de identificación'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Activo'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='is_staff',
            field=models.BooleanField(default=False, verbose_name='Es staff'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='is_superuser',
            field=models.BooleanField(default=False, verbose_name='Es superusuario'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='is_verified',
            field=models.BooleanField(default=False, verbose_name='Verificado'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='last_login',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Último ingreso'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='last_name',
            field=models.CharField(blank=True, max_length=30, verbose_name='Apellido'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='nationality',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Nacionalidad'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='password',
            field=models.CharField(max_length=128, verbose_name='Contraseña'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='phone',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Teléfono'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='profile_picture',
            field=models.ImageField(blank=True, null=True, upload_to='profile_pictures/', verbose_name='Foto de perfil'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='role',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.group', verbose_name='Rol'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='user_permissions',
            field=models.ManyToManyField(blank=True, related_name='auth_app_users_permissions', to='auth.permission', verbose_name='permisos de usuario'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='username',
            field=models.CharField(max_length=150, unique=True, verbose_name='Nombre de usuario'),
        ),
    ]

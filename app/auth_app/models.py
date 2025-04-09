from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models

class Business(models.Model):
    name = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey(
        "auth_app.CustomUser",
        on_delete=models.SET_NULL,
        related_name="owned_businesses",
        null=True,  # Permitir que sea `null` inicialmente
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    logo = models.ImageField(upload_to="business_logos/", null=True, blank=True)

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):  
    business = models.ForeignKey(
        "auth_app.Business", 
        on_delete=models.SET_NULL, 
        related_name="members",
        null=True, 
        blank=True,
    )
    role = models.ForeignKey(
        Group, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )  # Relación con roles

    groups = models.ManyToManyField(
        Group,
        related_name="auth_app_users", 
        blank=True
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="auth_app_users_permissions",
        blank=True
    )
    
    id_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    profile_picture = models.ImageField(upload_to="profile_pictures/", null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=50, null=True, blank=True)
    

    def __str__(self):
        return f"{self.username} - {self.role.name if self.role else 'Sin rol'}"
    
    def deactivate(self):
        """Desactiva el usuario sin eliminarlo"""
        self.is_active = False
        self.save()
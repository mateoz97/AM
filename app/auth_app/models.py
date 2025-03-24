from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models

class Business(models.Model):
    name = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey("auth_app.CustomUser", on_delete=models.CASCADE, related_name="businesses")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class CustomUser(AbstractUser):  
    business = models.ForeignKey("auth_app.Business", on_delete=models.CASCADE, null=True, blank=True)
    role = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)  # Relación con roles

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

    def __str__(self):
        return f"{self.username} - {self.role.name if self.role else 'Sin rol'}"

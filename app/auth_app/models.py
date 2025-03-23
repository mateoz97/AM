from django.contrib.auth.models import AbstractUser, Group
from django.db import models

class Business(models.Model):
    name = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey("auth_app.User", on_delete=models.CASCADE, related_name="businesses")
    created_at = models.DateTimeField(auto_now_add=True)
    
class User(AbstractUser):
    groups = models.ManyToManyField(
        "auth.Group",
        related_name="auth_app_users", 
        blank=True
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="auth_app_users_permissions",
        blank=True
    )
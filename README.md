# 🏪 Aplicación de Control 

## 📌 Descripción
Este proyecto es una aplicación web basada en Django y Django REST Framework (DRF) que permite gestionar pedidos, inventarios y roles de usuarios dentro de un negocio. Cada negocio tiene su propio administrador, meseros, cocineros y clientes.

## 🚀 Tecnologías Utilizadas
- Python 3
- Django 4
- Django REST Framework
- Django Simple JWT (Autenticación con JSON Web Tokens)
- PostgreSQL (opcional) / SQLite

---

## 📂 Estructura del Proyecto
```
├── app
│   ├── auth_app
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── services.py
│   │   ├── urls.py
│   │   ├── views.py
│   ├── ping  # Endpoint de prueba
│   │   ├── views.py
├── config  # Configuración del proyecto
│   ├── settings.py
│   ├── urls.py
├── manage.py
├── pyproject.toml  # Configuración de dependencias con Poetry
├── README.md
```

---

## 🔑 Configuración de Autenticación con JWT
La autenticación se maneja con **Django Simple JWT**.

### 📌 Instalación de Dependencias
```bash
poetry add djangorestframework-simplejwt
```

### 📌 Configuración en `settings.py`
```python
INSTALLED_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'auth_app',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}
```

### 📌 Generar Token de Acceso
```bash
POST /api/token/
{
    "username": "admin",
    "password": "password"
}
```
Respuesta:
```json
{
    "access": "TOKEN_AQUI",
    "refresh": "REFRESH_TOKEN_AQUI"
}
```

### 📌 Endpoint de Prueba
```bash
GET /api/ping/  # Requiere autenticación JWT
```

---

## 🛠️ Modelos y Roles de Usuario
### 📌 `models.py`
```python
from django.contrib.auth.models import AbstractUser, Group
from django.db import models

class Business(models.Model):
    name = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey("auth_app.CustomUser", on_delete=models.CASCADE, related_name="businesses")
    created_at = models.DateTimeField(auto_now_add=True)

class CustomUser(AbstractUser):  
    business = models.ForeignKey(Business, on_delete=models.CASCADE, null=True, blank=True)
    role = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
```

---

## 📌 Migraciones y Base de Datos

### 📌 Aplicar Migraciones
```bash
python manage.py makemigrations
python manage.py migrate
```

### 📌 Crear Superusuario
```bash
python manage.py createsuperuser
```

---

## 📌 Consideraciones Finales
- La API está diseñada para manejar roles como **Admin, Gerente, Mesero, Cocinero y Cliente**.
- Todo el backend está en inglés, pero los mensajes para usuarios pueden traducirse a español.
- Se recomienda PostgreSQL para entornos de producción.

---

## 📌 Próximos Pasos
✅ Configurar permisos para cada rol
✅ Crear endpoints para gestión de pedidos e inventarios
✅ Desplegar la aplicación en un servidor en la nube

---

## 📬 Contacto y Soporte
Si tienes dudas, contáctame en Mateooh97@gmail.com. 🚀


# 🏪 ADB - Aplicación Multi-Tenant para Gestión de Restaurantes y Red Social

## 📌 Descripción

ADB es una aplicación web multi-tenant basada en Django y Django REST Framework que permite gestionar restaurantes y negocios de manera independiente, cada uno con su propia base de datos (esquema PostgreSQL). La aplicación incluye funcionalidades de red social donde los usuarios pueden crear publicaciones desde diferentes perfiles de negocio, cambiar entre múltiples negocios, y gestionar roles tanto a nivel global como por negocio.

## 🏗️ Arquitectura del Sistema

### Diagrama de Arquitectura Multi-Tenant

```
┌─────────────────────────────────────────────────────────────┐
│                    BASE DE DATOS PRINCIPAL                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────── │
│  │     USUARIOS    │  │   ROLES MAIN    │  │     POSTS     │ │
│  │                 │  │                 │  │   (Red Social)│ │
│  │ • CustomUser    │  │ • MainRole      │  │ • Post        │ │
│  │ • user_type     │  │ • Permissions   │  │ • PostLike    │ │
│  │ • main_role     │  │                 │  │ • PostComment │ │
│  │ • current_*     │  │                 │  │               │ │
│  └─────────────────┘  └─────────────────┘  └─────────────── │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │    NEGOCIOS     │  │   CONFIGURACIÓN │                  │
│  │                 │  │                 │                  │
│  │ • Business      │  │ • Settings      │                  │
│  │ • Invitations   │  │ • Core Models   │                  │
│  │ • JoinRequests  │  │                 │                  │
│  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               ESQUEMAS POR NEGOCIO (PostgreSQL)            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  business_1             business_2             business_N   │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────── │
│  │ Inventory   │        │ Inventory   │        │ Inventory │ │
│  │ Orders      │        │ Orders      │        │ Orders    │ │
│  │ Roles       │   ...  │ Roles       │   ...  │ Roles     │ │
│  │ Reports     │        │ Reports     │        │ Reports   │ │
│  │ Employees   │        │ Employees   │        │ Employees │ │
│  └─────────────┘        └─────────────┘        └─────────── │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Flujo de Autenticación y Contexto

```
Usuario Login → JWT Token → Middleware → Contexto de Negocio
                                    ↓
    ┌─────────────────────────────────────────────────────────┐
    │                MIDDLEWARE FLOW                          │
    │                                                         │
    │  1. BusinessMiddleware detecta business_id              │
    │  2. Configura search_path: "business_X, public"        │
    │  3. Establece contexto para modelos                    │
    │  4. Usuario puede cambiar entre negocios               │
    └─────────────────────────────────────────────────────────┘
```

## 🚀 Tecnologías Utilizadas

- **Backend**: Python 3.x, Django 4.x
- **API**: Django REST Framework
- **Autenticación**: Django Simple JWT
- **Base de Datos**: PostgreSQL con esquemas multi-tenant
- **ORM**: Django ORM con managers personalizados
- **Middleware**: Middleware personalizado para contexto de negocio

## 📊 Modelo de Datos Conceptual

### Entidades Principales

#### 1. Sistema Principal (Base de Datos Main)

**CustomUser**
```
- id (PK)
- username, email, password (campos estándar)
- user_type: 'client' | 'business_owner'
- main_role → MainRole (FK)
- current_business → Business (FK, nullable)
- current_business_role → BusinessRole (FK, nullable)
```

**MainRole**
```
- id (PK)
- name: 'client' | 'business_owner'
- display_name
- permissions → MainRolePermission (OneToOne)
```

**Business**
```
- id (PK)
- name, description, address
- owner → CustomUser (FK)
- co_owners → CustomUser (M2M)
- is_active
```

**Post (Red Social)**
```
- id (PK)
- author → CustomUser (FK)
- business → Business (FK, nullable)
- post_type: 'personal' | 'business' | 'promotion'
- content, image, video
- likes_count, comments_count
```

#### 2. Esquemas de Negocio (business_X)

**BusinessRole**
```
- id (PK)
- business → Business (FK)
- name (Owner, Manager, Employee, etc.)
- permissions → RolePermission (OneToOne)
- is_default, can_modify
```

**Inventory**
```
- Productos específicos del negocio
- Stock, precios, categorías
```

**Orders**
```
- Pedidos del negocio
- Items, estados, clientes
```

### Relaciones Clave

1. **Usuario ↔ Negocios**: Un usuario puede ser propietario de múltiples negocios y empleado en otros
2. **Contexto Activo**: `current_business` define el esquema PostgreSQL activo
3. **Roles Duales**: Rol principal (sistema) + rol de negocio (esquema específico)
4. **Posts Globales**: Red social unificada con posts de todos los negocios

## 📂 Estructura del Proyecto

```
ADB/
├── app/
│   ├── accounts/           # Gestión de usuarios y autenticación
│   │   ├── models/user.py     # CustomUser con multi-business
│   │   ├── api/
│   │   │   ├── views/auth_views.py
│   │   │   └── views/profile_views.py  # Business profile switching
│   │   └── services/
│   ├── business/           # Gestión de negocios
│   │   ├── models/business.py
│   │   ├── services/business_service.py  # PostgreSQL schemas
│   │   └── api/views/
│   ├── roles/              # Sistema de roles
│   │   ├── models/
│   │   │   ├── role.py           # BusinessRole, RolePermission
│   │   │   └── main_role.py      # MainRole, MainRolePermission
│   │   ├── services/role_service.py
│   │   └── api/views/role_management_views.py
│   ├── posts/              # Red social
│   │   ├── models.py          # Post, PostLike, PostComment
│   │   └── api/
│   ├── inventory/          # Inventario (por negocio)
│   ├── settings/           # Configuraciones
│   └── core/               # Managers, middleware, commands
│       ├── managers.py        # Schema-aware managers
│       ├── middleware.py      # Business context middleware
│       └── management/commands/
├── config/
│   ├── settings.py         # PostgreSQL multi-database config
│   ├── middleware.py       # BusinessMiddleware
│   └── urls.py
└── CLAUDE.md              # Documentación para Claude Code
```

## 🔑 Características Principales

### 1. **Multi-Tenancy con PostgreSQL Schemas**
- Cada negocio tiene su propio esquema PostgreSQL
- Aislamiento completo de datos por negocio
- Middleware automático para cambio de contexto
- Comandos de gestión para esquemas

### 2. **Sistema de Roles Dual**
- **Roles Principales**: Client, Business Owner (sistema global)
- **Roles de Negocio**: Owner, Manager, Employee, etc. (por negocio)
- Permisos granulares por rol y contexto
- Gestión de roles solo por propietarios

### 3. **Business Profile Switching**
- Usuarios pueden cambiar entre múltiples negocios
- Contexto automático de base de datos
- APIs para gestión de perfiles de negocio
- Compatibilidad con código existente

### 4. **Red Social Integrada**
- Posts globales en base de datos principal
- Publicaciones desde perfil personal o de negocio
- Sistema de likes y comentarios
- Tipos de posts: personal, negocio, promoción

### 5. **Gestión Automática de Esquemas**
- Creación automática de esquemas al crear negocio
- Solo rol "Owner" por defecto
- Plantillas de roles para crear según necesidad
- Comandos de limpieza de esquemas huérfanos

## 🛠️ Configuración y Uso

### Instalación

```bash
# Clonar repositorio
git clone [repository-url]
cd ADB

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"

# Aplicar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser
```

### Comandos Útiles

```bash
# Limpiar esquemas huérfanos
python manage.py cleanup_schemas --dry-run

# Migrar a roles de negocio
python manage.py migrate_to_business_roles

# Verificar esquemas
python manage.py shell
>>> from app.business.services.business_service import DatabaseService
>>> DatabaseService.verify_business_database(business_id)
```

### APIs Principales

#### Autenticación y Perfiles
```bash
POST /api/accounts/login/                    # Login
GET  /api/accounts/profiles/                 # Lista perfiles de negocio
POST /api/accounts/profiles/switch/          # Cambiar perfil activo
GET  /api/accounts/profiles/current/         # Perfil actual
```

#### Gestión de Roles (Solo Owners)
```bash
GET  /api/roles/management/                  # Listar roles del negocio
POST /api/roles/management/                  # Crear rol personalizado
GET  /api/roles/templates/                   # Plantillas de roles
POST /api/roles/create-from-template/        # Crear desde plantilla
```

#### Red Social
```bash
GET  /api/posts/                            # Feed de posts
POST /api/posts/                            # Crear post
POST /api/accounts/profiles/create-post/     # Post desde negocio
```

## 🔐 Seguridad y Permisos

### Niveles de Permisos

1. **Sistema Principal**
   - `can_create_business`: Crear nuevos negocios
   - `can_manage_own_businesses`: Gestionar negocios propios
   - `can_create_posts`: Crear publicaciones

2. **Negocio Específico**
   - `can_manage_users`: Gestionar empleados
   - `can_manage_roles`: Crear/editar roles
   - `can_view_orders`: Ver pedidos
   - `can_manage_inventory`: Gestionar inventario

### Middleware de Seguridad

- Verificación automática de acceso a esquemas
- Contexto de base de datos por usuario
- Validación de permisos por endpoint
- Logging de cambios de contexto

## 📋 Flujos de Trabajo Principales

### 1. Crear Nuevo Negocio
```
Usuario → Crear Business → Esquema PostgreSQL → Rol Owner → Cambio Contexto
```

### 2. Cambiar Perfil de Negocio
```
Usuario → Lista Negocios → Seleccionar → Validar Acceso → Cambio Contexto
```

### 3. Gestionar Roles de Negocio
```
Owner → Ver Plantillas → Crear Rol → Asignar Permisos → Asignar Usuarios
```

### 4. Crear Post de Negocio
```
Usuario → Cambiar a Perfil Negocio → Crear Post → Publicar en Red Social
```

## 🧪 Testing y Debugging

### Comandos de Debug
```bash
# Ver contexto actual del usuario
python manage.py shell
>>> user = CustomUser.objects.get(username='test')
>>> user.current_business
>>> user.current_business_role

# Verificar esquemas
>>> from django.db import connection
>>> with connection.cursor() as cursor:
...     cursor.execute("SHOW search_path")
...     print(cursor.fetchone())
```

### Logs Importantes
- Business context switching: `config.middleware`
- Schema operations: `app.business.services.business_service`
- Role management: `app.roles.services.role_service`

## 📈 Próximas Funcionalidades

- [ ] Sistema de notificaciones
- [ ] Analytics por negocio
- [ ] API de reportes avanzados
- [ ] Integración con pagos
- [ ] App móvil
- [ ] Sistema de reviews y ratings
- [ ] Geolocalización de negocios

## 🤝 Contribución

Para contribuir al proyecto:

1. Fork el repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📬 Contacto y Soporte

- **Email**: Mateooh97@gmail.com
- **Documentación**: Ver `CLAUDE.md` para información técnica detallada
- **Issues**: Usar GitHub Issues para reportar bugs o solicitar features

---

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver `LICENSE` para más detalles.

## 🙏 Agradecimientos

Desarrollado para optimizar la gestión de restaurantes y crear una experiencia de red social integrada para negocios locales.
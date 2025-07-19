# Arquitectura Multitenant Corregida

## Schema Principal (`public`)
**Propósito**: Datos globales y funcionalidad de red social

### Modelos que van en el schema principal:
- **Usuarios y Autenticación**:
  - `accounts.CustomUser` - Usuarios del sistema
  - Modelos de Django auth (User, Group, Permission)
  
- **Negocios (metadatos)**:
  - `business.Business` - Información básica del negocio
  - `business.BusinessJoinRequest` - Solicitudes para unirse
  - `business.BusinessInvitation` - Invitaciones
  - `business.BusinessBranch` - Sucursales
  
- **Red Social Global**:
  - `posts.Post` - Posts públicos en el feed global
  - `posts.Comment` - Comentarios en posts
  - `posts.Like` - Likes en posts
  - `posts.Follow` - Seguimientos entre usuarios/negocios
  
- **Configuraciones Globales**:
  - `settings.UserSettings` - Configuraciones personales del usuario

## Schemas de Negocio (`business_{id}`)
**Propósito**: Datos específicos y privados de cada negocio

### Modelos que van en cada schema de negocio:
- **Gestión de Roles Internos**:
  - `roles.BusinessRole` - Roles específicos del negocio
  - `roles.RolePermission` - Permisos por rol
  
- **Inventario**:
  - `inventory.Product` - Productos del negocio
  - `inventory.Category` - Categorías de productos
  - `inventory.Stock` - Stock de productos
  - `inventory.StockMovement` - Movimientos de inventario
  
- **Órdenes**:
  - `orders.Order` - Órdenes del negocio
  - `orders.OrderItem` - Items de órdenes
  - `orders.OrderStatusHistory` - Historial de estados
  - `orders.OrderNotification` - Notificaciones
  - `orders.OrderAuditLog` - Auditoría
  
- **Configuraciones del Negocio**:
  - `settings.BusinessSettings` - Configuraciones específicas
  - `settings.NotificationTemplate` - Plantillas de notificación
  
- **Pagos (futuro)**:
  - `payments.Transaction`
  - `payments.PaymentMethod`
  - `payments.Invoice`

## Flujo de Datos
1. **Usuario se registra** → Schema principal
2. **Usuario crea negocio** → Schema principal (metadatos) + Nuevo schema de negocio
3. **Usuario se une a negocio** → Asignación de rol en schema del negocio
4. **Operaciones del negocio** → Schema específico del negocio
5. **Posts públicos/feed** → Schema principal
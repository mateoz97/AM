# app/inventory/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from app.inventory.models import Product, ProductCategory, StockMovement

class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    readonly_fields = ['movement_type', 'quantity', 'previous_stock', 'new_stock', 'notes', 'created_at', 'created_by']
    can_delete = False
    max_num = 0  # No permitir añadir nuevos desde el admin
    verbose_name = _("Movimiento de Stock")
    verbose_name_plural = _("Movimientos de Stock")

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'category', 'price', 'stock', 'is_active', 'created_at')
    list_filter = ('business', 'category', 'is_active')
    search_fields = ('name', 'description', 'category__name')
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    inlines = [StockMovementInline]
    
    fieldsets = (
        (_('Información básica'), {
            'fields': ('business', 'name', 'description', 'category')
        }),
        (_('Precio y Stock'), {
            'fields': ('price', 'stock')
        }),
        (_('Estado'), {
            'fields': ('is_active',)
        }),
        (_('Imagen'), {
            'fields': ('image',)
        }),
        (_('Auditoría'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        # Si es superusuario, mostrar todos los productos
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        # Si no es superusuario, filtrar por su negocio actual
        if hasattr(request.user, 'current_business') and request.user.current_business:
            return qs.filter(business=request.user.current_business)
        return qs.none()
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filtrar categorías por negocio del usuario actual"""
        if db_field.name == "category":
            if hasattr(request.user, 'current_business') and request.user.current_business:
                kwargs["queryset"] = ProductCategory.objects.filter(
                    business=request.user.current_business,
                    is_active=True
                )
            elif request.user.is_superuser:
                # Los superusuarios ven todas las categorías
                kwargs["queryset"] = ProductCategory.objects.filter(is_active=True)
            else:
                kwargs["queryset"] = ProductCategory.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        # Asignar el usuario que crea el producto
        if not change:  # Solo si es nuevo
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'is_active')
    list_filter = ('business', 'is_active')
    search_fields = ('name', 'description')
    
    fieldsets = (
        (_('Información'), {
            'fields': ('business', 'name', 'description', 'is_active')
        }),
    )
    
    def get_queryset(self, request):
        # Filtrar por negocio del usuario
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'current_business') and request.user.current_business:
            return qs.filter(business=request.user.current_business)
        return qs.none()

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    # Force using default database for StockMovement
    using = 'default'
    
    list_display = ('get_product_name', 'get_business', 'movement_type', 'quantity', 'previous_stock', 'new_stock', 'created_at', 'get_created_by')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('product__name', 'notes', 'product__business__name')
    readonly_fields = ('previous_stock', 'new_stock', 'created_at', 'created_by')
    ordering = ['-created_at']
    
    fieldsets = (
        (_('Movimiento'), {
            'fields': ('product', 'movement_type', 'quantity', 'notes')
        }),
        (_('Estado de Stock'), {
            'fields': ('previous_stock', 'new_stock')
        }),
        (_('Auditoría'), {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_product_name(self, obj):
        """Mostrar nombre del producto"""
        return obj.product.name if obj.product else 'N/A'
    get_product_name.short_description = _('Producto')
    get_product_name.admin_order_field = 'product__name'
    
    def get_business(self, obj):
        """Mostrar negocio del producto"""
        return obj.product.business.name if obj.product and obj.product.business else 'N/A'
    get_business.short_description = _('Negocio')
    get_business.admin_order_field = 'product__business__name'
    
    def get_created_by(self, obj):
        """Mostrar quién creó el movimiento"""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return 'Sistema'
    get_created_by.short_description = _('Creado por')
    get_created_by.admin_order_field = 'created_by__username'
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filtrar productos por negocio del usuario actual"""
        if db_field.name == "product":
            if hasattr(request.user, 'current_business') and request.user.current_business:
                kwargs["queryset"] = Product.objects.filter(
                    business=request.user.current_business,
                    is_active=True
                )
            elif request.user.is_superuser:
                kwargs["queryset"] = Product.objects.filter(is_active=True)
            else:
                kwargs["queryset"] = Product.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_queryset(self, request):
        """Filtrar movimientos por negocio del usuario"""
        # Force using default database and clear business context
        from config.middleware import set_current_business_id
        set_current_business_id(None)
        
        qs = super().get_queryset(request).using('default')
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'current_business') and request.user.current_business:
            return qs.filter(product__business=request.user.current_business)
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        """Configurar valores automáticos al guardar"""
        if not change:  # Solo para nuevos movimientos
            # Asignar usuario que crea el movimiento
            obj.created_by = request.user
            
            # Calcular stock anterior y nuevo
            product = obj.product
            obj.previous_stock = product.stock
            
            # Calcular nuevo stock según tipo de movimiento
            if obj.movement_type == 'add':
                new_stock = product.stock + obj.quantity
            elif obj.movement_type == 'remove':
                new_stock = max(0, product.stock - obj.quantity)
            elif obj.movement_type == 'adjustment':
                new_stock = obj.quantity
            else:
                new_stock = product.stock
                
            obj.new_stock = new_stock
            
            # Guardar el movimiento primero usando la base de datos default
            obj.save(using=self.using)
            
            # Actualizar stock del producto
            product.stock = new_stock
            product.save(update_fields=['stock'], using=self.using)
        else:
            obj.save(using=self.using)
    
    def delete_model(self, request, obj):
        """Delete always from the main schema"""
        obj.delete(using=self.using)
    
    def has_change_permission(self, request, obj=None):
        """Solo permitir editar notas, no modificar movimientos"""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Solo superusuarios pueden eliminar movimientos"""
        return request.user.is_superuser
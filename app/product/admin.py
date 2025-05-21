# app/inventory/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from app.product.models import Product, ProductCategory, StockMovement

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
    search_fields = ('name', 'description', 'category')
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
        
        # Si no es superusuario, filtrar por su negocio
        if hasattr(request.user, 'business') and request.user.business:
            return qs.filter(business=request.user.business)
        return qs.none()
    
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
        
        if hasattr(request.user, 'business') and request.user.business:
            return qs.filter(business=request.user.business)
        return qs.none()

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'movement_type', 'quantity', 'previous_stock', 'new_stock', 'created_at', 'created_by')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('product__name', 'notes')
    readonly_fields = ('product', 'movement_type', 'quantity', 'previous_stock', 'new_stock', 'created_at', 'created_by')
    
    fieldsets = (
        (_('Movimiento'), {
            'fields': ('product', 'movement_type', 'quantity', 'notes')
        }),
        (_('Estado de Stock'), {
            'fields': ('previous_stock', 'new_stock')
        }),
        (_('Auditoría'), {
            'fields': ('created_by', 'created_at'),
        }),
    )
    
    def get_queryset(self, request):
        # Filtrar por negocio del usuario
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'business') and request.user.business:
            return qs.filter(product__business=request.user.business)
        return qs.none()
    
    def has_add_permission(self, request):
        # No permitir añadir movimientos directamente
        return False
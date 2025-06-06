# app/inventory/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.forms import TextInput, Textarea

from app.inventory.models import Product, ProductCategory, StockMovement

class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    readonly_fields = ['movement_type', 'quantity', 'previous_stock', 'new_stock', 'notes', 'created_at', 'created_by']
    can_delete = False
    max_num = 0
    verbose_name = _("Movimiento de Stock")
    verbose_name_plural = _("Movimientos de Stock")
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'category', 'price', 'stock', 'is_active', 'created_at')
    list_filter = ('business', 'category', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    inlines = [StockMovementInline]
    
    # Mejorar la interfaz del admin
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'50'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':60})},
    }
    
    fieldsets = (
        (_('Información básica'), {
            'fields': ('business', 'name', 'description', 'category')
        }),
        (_('Precio y Stock'), {
            'fields': ('price', 'stock'),
            'classes': ('wide',)
        }),
        (_('Imagen'), {
            'fields': ('image',),
            'classes': ('collapse',)
        }),
        (_('Estado'), {
            'fields': ('is_active',)
        }),
        (_('Auditoría'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Si es superusuario, mostrar todos
        if request.user.is_superuser:
            return qs
        
        # Si tiene negocio, mostrar solo productos de su negocio
        if hasattr(request.user, 'business') and request.user.business:
            return qs.filter(business=request.user.business)
        
        # Si no tiene negocio, no mostrar nada
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        # Asignar negocio del usuario si no se especifica
        if not obj.business and hasattr(request.user, 'business') and request.user.business:
            obj.business = request.user.business
            
        # Asignar usuario creador solo en creación
        if not change:
            obj.created_by = request.user
            
        super().save_model(request, obj, form, change)
    
    def has_view_permission(self, request, obj=None):
        # Verificar permisos básicos
        if not super().has_view_permission(request, obj):
            return False
        
        # Superusuario tiene acceso completo
        if request.user.is_superuser:
            return True
            
        # Verificar permisos de negocio
        return request.user.has_business_permission('can_view_inventory')
    
    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
            
        if request.user.is_superuser:
            return True
            
        return request.user.has_business_permission('can_manage_inventory')
    
    def has_add_permission(self, request):
        if not super().has_add_permission(request):
            return False
            
        if request.user.is_superuser:
            return True
            
        return request.user.has_business_permission('can_manage_inventory')
    
    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
            
        if request.user.is_superuser:
            return True
            
        return request.user.has_business_permission('can_manage_inventory')

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
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            return qs
            
        if hasattr(request.user, 'business') and request.user.business:
            return qs.filter(business=request.user.business)
            
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        if not obj.business and hasattr(request.user, 'business') and request.user.business:
            obj.business = request.user.business
        super().save_model(request, obj, form, change)

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'movement_type', 'quantity', 'previous_stock', 'new_stock', 'created_at', 'created_by')
    list_filter = ('movement_type', 'created_at', 'product__business')
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
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            return qs
            
        if hasattr(request.user, 'business') and request.user.business:
            return qs.filter(product__business=request.user.business)
            
        return qs.none()
    
    def has_add_permission(self, request):
        # Los movimientos se crean desde la API, no desde admin
        return False
    
    def has_change_permission(self, request, obj=None):
        # Los movimientos no se pueden editar
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Solo superusuario puede eliminar movimientos (para correcciones)
        return request.user.is_superuser
# Django admin configuration for the accounts
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

# Models
from app.accounts.models.user import CustomUser

# admins
from app.business.admin import UserOwnedBusinessInline



@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_business', 'get_business_role', 'user_type', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'current_business', 'current_business_role', 'user_type', 'is_verified')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'id_number')
    readonly_fields = ('date_joined', 'last_login')
    inlines = [UserOwnedBusinessInline]
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Información personal'), {'fields': ('first_name', 'last_name', 'email', 'phone', 'address',
                                              'profile_picture', 'date_of_birth', 'nationality', 'id_number')}),

        (_('Negocio y rol'), {'fields': ('user_type', 'main_role', 'current_business', 'current_business_role')}),
        (_('Fechas importantes'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
        (_('Información personal'), {
            'fields': ('first_name', 'last_name', 'phone')
        }),
        (_('Permisos'), {
            'fields': ('is_staff', 'is_active')
        }),
    )
    
    actions = ['activate_users', 'deactivate_users', 'verify_users']
    
    def save_model(self, request, obj, form, change):
        """Override to ensure proper user creation and admin logging"""
        # For new users, ensure password is properly hashed
        if not change and hasattr(form, 'cleaned_data'):
            # If creating a new user through admin
            password = form.cleaned_data.get('password1')
            if password:
                obj.set_password(password)
        
        # Save the user
        super().save_model(request, obj, form, change)
        
        # Ensure main role is set for new users
        if not change:
            obj.ensure_main_role()
    
    def log_addition(self, request, object, message):
        """Override to handle admin log creation safely"""
        try:
            # Ensure the current user exists before logging
            if request.user.pk and CustomUser.objects.filter(pk=request.user.pk).exists():
                super().log_addition(request, object, message)
        except Exception:
            # Skip logging if there's an issue
            pass
    
    def log_change(self, request, object, message):
        """Override to handle admin log creation safely"""
        try:
            # Ensure the current user exists before logging
            if request.user.pk and CustomUser.objects.filter(pk=request.user.pk).exists():
                super().log_change(request, object, message)
        except Exception:
            # Skip logging if there's an issue
            pass
    
    def log_deletion(self, request, object, object_repr):
        """Override to handle admin log creation safely"""
        try:
            # Ensure the current user exists before logging
            if request.user.pk and CustomUser.objects.filter(pk=request.user.pk).exists():
                super().log_deletion(request, object, object_repr)
        except Exception:
            # Skip logging if there's an issue
            pass

    def get_business(self, obj):
        return obj.current_business.name if obj.current_business else _('Sin negocio')
    get_business.short_description = _('Negocio Actual')
    get_business.admin_order_field = 'current_business__name'  # Permitir ordenamiento
    
    def get_business_role(self, obj):
        return obj.current_business_role.name if obj.current_business_role else _('Sin rol')
    get_business_role.short_description = _('Rol Actual')
    get_business_role.admin_order_field = 'current_business_role__name'




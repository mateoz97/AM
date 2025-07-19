from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from app.posts.models import Post, PostLike, PostComment


class PostLikeInline(admin.TabularInline):
    model = PostLike
    extra = 0
    readonly_fields = ('user', 'created_at')
    max_num = 10


class PostCommentInline(admin.TabularInline):
    model = PostComment
    extra = 0
    readonly_fields = ('author', 'created_at')
    fields = ('author', 'content', 'is_active', 'created_at')
    max_num = 10


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'business', 'post_type', 'content_preview', 'likes_count', 'comments_count', 'is_active', 'created_at')
    list_filter = ('post_type', 'is_active', 'is_pinned', 'business', 'created_at')
    search_fields = ('content', 'author__username', 'business__name')
    readonly_fields = ('likes_count', 'comments_count', 'created_at', 'updated_at')
    inlines = [PostCommentInline, PostLikeInline]
    
    fieldsets = (
        (_('Información básica'), {
            'fields': ('author', 'business', 'post_type')
        }),
        (_('Contenido'), {
            'fields': ('content', 'image', 'video')
        }),
        (_('Estado'), {
            'fields': ('is_active', 'is_pinned')
        }),
        (_('Estadísticas'), {
            'fields': ('likes_count', 'comments_count'),
            'classes': ('collapse',)
        }),
        (_('Fechas'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def content_preview(self, obj):
        """Muestra una vista previa del contenido"""
        if obj.content:
            return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return _('Sin contenido de texto')
    content_preview.short_description = _('Vista previa')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        # Filter posts by user's business if not superuser
        if hasattr(request.user, 'current_business') and request.user.current_business:
            return qs.filter(business=request.user.current_business)
        # Show user's own posts if no business context
        return qs.filter(author=request.user)


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('post__content', 'user__username')
    readonly_fields = ('created_at',)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        # Filter likes by user's business posts if not superuser
        if hasattr(request.user, 'current_business') and request.user.current_business:
            return qs.filter(post__business=request.user.current_business)
        # Show user's own likes if no business context
        return qs.filter(user=request.user)


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ('post', 'author', 'content_preview', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('content', 'author__username', 'post__content')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (_('Información'), {
            'fields': ('post', 'author', 'content', 'is_active')
        }),
        (_('Fechas'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def content_preview(self, obj):
        """Muestra una vista previa del comentario"""
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = _('Comentario')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        # Filter comments by user's business posts if not superuser
        if hasattr(request.user, 'current_business') and request.user.current_business:
            return qs.filter(post__business=request.user.current_business)
        # Show user's own comments if no business context
        return qs.filter(author=request.user)

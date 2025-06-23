# app/posts/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from app.accounts.models.user import CustomUser
from app.business.models.business import Business

class Post(models.Model):
    """
    Modelo de posts para la red social.
    Los posts se almacenan en la base de datos principal para funcionar como red social global.
    """
    POST_TYPES = (
        ('personal', _('Personal')),
        ('business', _('Negocio')),
        ('promotion', _('Promoción')),
        ('announcement', _('Anuncio')),
    )
    
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='posts')
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='posts', 
        null=True, 
        blank=True,
        help_text=_("Negocio desde el cual se publica (si aplica)")
    )
    post_type = models.CharField(
        _("Tipo de publicación"), 
        max_length=20, 
        choices=POST_TYPES, 
        default='personal'
    )
    content = models.TextField(_("Contenido"), blank=True)
    image = models.ImageField(_("Imagen"), upload_to='posts/', null=True, blank=True)
    video = models.FileField(_("Video"), upload_to='posts/videos/', null=True, blank=True)
    likes_count = models.IntegerField(_("Número de likes"), default=0)
    comments_count = models.IntegerField(_("Número de comentarios"), default=0)
    is_pinned = models.BooleanField(_("Fijado"), default=False)
    is_active = models.BooleanField(_("Activo"), default=True)
    created_at = models.DateTimeField(_("Creado"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Actualizado"), auto_now=True)
    
    # Manager normal - los posts van en la base de datos principal
    objects = models.Manager()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Publicación")
        verbose_name_plural = _("Publicaciones")
    
    def __str__(self):
        return f"{self.author.username} - {self.created_at}"
    
    def save(self, *args, **kwargs):
        # Verificar que hay al menos contenido o multimedia
        if not self.content and not self.image and not self.video:
            raise ValueError("La publicación debe tener al menos contenido, imagen o video")
        
        # Si se publica desde un negocio, marcar como tipo business
        if self.business and self.post_type == 'personal':
            self.post_type = 'business'
            
        super().save(*args, **kwargs)
    
    @property
    def is_business_post(self):
        """Determina si es un post de negocio"""
        return self.business is not None
    
    @property
    def display_name(self):
        """Nombre a mostrar del autor (negocio o usuario)"""
        if self.business:
            return self.business.name
        return self.author.get_full_name() or self.author.username

class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='liked_posts')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Manager normal - los likes van en la base de datos principal
    objects = models.Manager()
    
    class Meta:
        unique_together = ('post', 'user')
        verbose_name = _("Me gusta")
        verbose_name_plural = _("Me gustas")

class PostComment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField(_("Comentario"))
    is_active = models.BooleanField(_("Activo"), default=True)
    created_at = models.DateTimeField(_("Creado"), auto_now_add=True)
    
    # Manager normal - los comentarios van en la base de datos principal
    objects = models.Manager()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Comentario")
        verbose_name_plural = _("Comentarios")
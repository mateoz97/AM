# app/posts/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from app.accounts.models.user import CustomUser
from app.business.models.business import Business

class Post(models.Model):
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='posts')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='posts', null=True, blank=True)
    content = models.TextField(_("Contenido"), blank=True)  # Ahora puede estar vacío si hay media
    image = models.ImageField(_("Imagen"), upload_to='posts/', null=True, blank=True)
    video = models.FileField(_("Video"), upload_to='posts/videos/', null=True, blank=True)
    likes_count = models.IntegerField(_("Número de likes"), default=0)
    comments_count = models.IntegerField(_("Número de comentarios"), default=0)
    created_at = models.DateTimeField(_("Creado"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Actualizado"), auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Publicación")
        verbose_name_plural = _("Publicaciones")
    
    def __str__(self):
        return f"{self.author.username} - {self.created_at}"
    
    def save(self, *args, **kwargs):
        # Establecer el negocio del autor si no se proporciona
        if not self.business and self.author.business:
            self.business = self.author.business
            
        # Verificar que hay al menos contenido o multimedia
        if not self.content and not self.image and not self.video:
            raise ValueError("La publicación debe tener al menos contenido, imagen o video")
            
        super().save(*args, **kwargs)

class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='liked_posts')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('post', 'user')

class PostComment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField(_("Comentario"))
    created_at = models.DateTimeField(_("Creado"), auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
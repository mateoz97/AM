# app/posts/api/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import F

from app.posts.models import Post, PostLike, PostComment
from app.posts.api.serializers import PostSerializer, CommentSerializer

class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Retorna posts del feed según la lógica de negocio
        user = self.request.user
        # Por ahora, retornamos todos los posts. Puedes filtrar por negocios relacionados
        return Post.objects.all().order_by('-created_at')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user, business=self.request.user.business)
    
    @action(detail=False, methods=['get'])
    def feed(self, request):
        """Obtiene el feed de publicaciones"""
        posts = self.get_queryset()
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """Like/Unlike a post"""
        post = self.get_object()
        user = request.user
        
        # Verificar si ya existe un like
        like_exists = PostLike.objects.filter(post=post, user=user).exists()
        
        if like_exists:
            # Si existe, eliminar el like
            PostLike.objects.filter(post=post, user=user).delete()
            post.likes_count = F('likes_count') - 1
            post.save(update_fields=['likes_count'])
            # Refrescar para obtener el valor actual
            post.refresh_from_db()
            return Response({'liked': False, 'likes_count': post.likes_count})
        else:
            # Si no existe, crear el like
            PostLike.objects.create(post=post, user=user)
            post.likes_count = F('likes_count') + 1
            post.save(update_fields=['likes_count'])
            # Refrescar para obtener el valor actual
            post.refresh_from_db()
            return Response({'liked': True, 'likes_count': post.likes_count})
    
    @action(detail=True, methods=['post'])
    def comment(self, request, pk=None):
        """Add a comment to a post"""
        post = self.get_object()
        serializer = CommentSerializer(data=request.data)
        
        if serializer.is_valid():
            # Crear el comentario
            comment = serializer.save(author=request.user, post=post)
            # Actualizar contador de comentarios
            post.comments_count = F('comments_count') + 1
            post.save(update_fields=['comments_count'])
            post.refresh_from_db()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        """Get all comments for a post"""
        post = self.get_object()
        comments = post.comments.all().order_by('-created_at')
        serializer = CommentSerializer(comments, many=True, context={'request': request})
        return Response(serializer.data)
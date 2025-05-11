# app/posts/api/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import F
from app.posts.models import Post, PostLike
from app.posts.api.serializers import PostSerializer, CommentSerializer

class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Retorna posts del feed según la lógica de negocio
        user = self.request.user
        # Por ahora, retornamos todos los posts. Puedes filtrar por negocios relacionados
        return Post.objects.all().order_by('-created_at')
    
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
        
        like, created = PostLike.objects.get_or_create(post=post, user=user)
        
        if not created:
            like.delete()
            post.likes_count = F('likes_count') - 1
            post.save()
            return Response({'liked': False, 'likes_count': post.likes_count})
        else:
            post.likes_count = F('likes_count') + 1
            post.save()
            return Response({'liked': True, 'likes_count': post.likes_count})
    
    @action(detail=True, methods=['post'])
    def comment(self, request, pk=None):
        """Add a comment to a post"""
        post = self.get_object()
        serializer = CommentSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(author=request.user, post=post)
            post.comments_count = F('comments_count') + 1
            post.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        """Get all comments for a post"""
        post = self.get_object()
        comments = post.comments.all()
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)
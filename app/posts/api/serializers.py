# app/posts/api/serializers.py
from rest_framework import serializers
from app.posts.models import Post, PostComment, PostLike

class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    likes = serializers.IntegerField(source='likes_count', read_only=True)
    comments = serializers.IntegerField(source='comments_count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    comments_list = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = ['id', 'author', 'business', 'content', 'image', 'video', 
                 'likes', 'comments', 'is_liked', 'created_at', 'comments_list']
        read_only_fields = ['id', 'author', 'created_at', 'likes', 'comments', 'is_liked', 'comments_list']
    
    def get_author(self, obj):
        author_data = {
            'id': obj.author.id,
            'name': obj.author.get_full_name() or obj.author.username,
            'username': obj.author.username,
            'business': None,
            'role': None
        }
        
        # Incluir información del negocio
        try:
            if obj.author.current_business:
                author_data['business'] = obj.author.current_business.name
        except Exception:
            pass
        
        # Incluir información del rol
        try:
            if obj.author.current_business_role:
                author_data['role'] = obj.author.current_business_role.name
        except Exception:
            pass
            
        return author_data
    
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False
    
    def get_comments_list(self, obj):
        # Obtener los 3 primeros comentarios
        comments = obj.comments.all().order_by('-created_at')[:3]
        return CommentSerializer(comments, many=True, context=self.context).data
    
    def validate(self, data):
        # Verificar que hay al menos contenido o media
        content = data.get('content', '')
        image = data.get('image')
        video = data.get('video')
        
        if not content and not image and not video:
            raise serializers.ValidationError("La publicación debe contener al menos texto, imagen o video")
        
        # Verificar que no hay imagen y video simultáneamente
        if image and video:
            raise serializers.ValidationError("No se puede adjuntar imagen y video en la misma publicación")
        
        return data
    
    def create(self, validated_data):
        # Asignar el autor automáticamente
        validated_data['author'] = self.context['request'].user
        
        # Si no se proporciona un negocio, usar el del autor
        try:
            if 'business' not in validated_data and validated_data['author'].current_business:
                validated_data['business'] = validated_data['author'].current_business
        except Exception:
            pass
            
        return super().create(validated_data)

class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    
    class Meta:
        model = PostComment
        fields = ['id', 'author', 'content', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']
    
    def get_author(self, obj):
        author_data = {
            'id': obj.author.id,
            'name': obj.author.get_full_name() or obj.author.username,
            'username': obj.author.username,
            'business': None,
            'role': None
        }
        
        # Incluir información del negocio
        try:
            if obj.author.current_business:
                author_data['business'] = obj.author.current_business.name
        except Exception:
            pass
        
        # Incluir información del rol
        try:
            if obj.author.current_business_role:
                author_data['role'] = obj.author.current_business_role.name
        except Exception:
            pass
            
        return author_data
        
    def create(self, validated_data):
        # Asignar el autor automáticamente
        validated_data['author'] = self.context['request'].user
        
        # Crear el comentario
        comment = super().create(validated_data)
        
        # Actualizar contador de comentarios en el post
        post = comment.post
        post.comments_count = post.comments.count()
        post.save(update_fields=['comments_count'])
        
        return comment
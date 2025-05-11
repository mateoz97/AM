# app/posts/api/serializers.py
from rest_framework import serializers
from app.posts.models import Post, PostComment

class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    likes = serializers.IntegerField(source='likes_count', read_only=True)
    comments = serializers.IntegerField(source='comments_count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = ['id', 'author', 'business', 'content', 'image', 'video', 
                 'likes', 'comments', 'is_liked', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_author(self, obj):
        return {
            'id': obj.author.id,
            'name': obj.author.get_full_name() or obj.author.username,
            'username': obj.author.username
        }
    
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False
    
    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)

class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    
    class Meta:
        model = PostComment
        fields = ['id', 'author', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_author(self, obj):
        return {
            'id': obj.author.id,
            'name': obj.author.get_full_name() or obj.author.username,
            'username': obj.author.username
        }
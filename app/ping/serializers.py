# ping_pong/serializers.py
from rest_framework import serializers

class PingSerializer(serializers.Serializer):
    message = serializers.CharField(default="pong")
    timestamp = serializers.DateTimeField()
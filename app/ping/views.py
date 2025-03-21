# ping_pong/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import PingSerializer
from datetime import datetime

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ping_view(request):
    serializer = PingSerializer({"message": "pong", "timestamp": datetime.now()})
    return Response(serializer.data)
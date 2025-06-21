# app/settings/api/views.py
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import Http404

from app.settings.models import UserSettings, BusinessSettings, NotificationTemplate
from app.settings.api.serializers import (
    UserSettingsSerializer, 
    BusinessSettingsSerializer,
    NotificationTemplateSerializer,
    SettingsSummarySerializer
)
from app.settings.services import SettingsService


class UserSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet para configuraciones de usuario
    """
    serializer_class = UserSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Solo devolver las configuraciones del usuario actual"""
        return UserSettings.objects.filter(user=self.request.user)
    
    def get_object(self):
        """Obtener o crear configuraciones del usuario actual"""
        settings, created = UserSettings.objects.get_or_create(
            user=self.request.user
        )
        return settings
    
    def list(self, request, *args, **kwargs):
        """Devolver las configuraciones del usuario actual"""
        settings = self.get_object()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """No permitir crear nuevas configuraciones (se crean automáticamente)"""
        return Response(
            {"error": "Las configuraciones se crean automáticamente"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def perform_update(self, serializer):
        """Actualizar configuraciones del usuario actual"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def reset_to_defaults(self, request):
        """Resetear configuraciones a valores por defecto"""
        try:
            settings = self.get_object()
            SettingsService.reset_user_settings_to_defaults(settings)
            
            serializer = self.get_serializer(settings)
            return Response({
                "message": "Configuraciones restablecidas a valores por defecto",
                "data": serializer.data
            })
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class BusinessSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet para configuraciones de negocio
    """
    serializer_class = BusinessSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Solo devolver configuraciones del negocio del usuario"""
        if not self.request.user.business:
            return BusinessSettings.objects.none()
        return BusinessSettings.objects.filter(business=self.request.user.business)
    
    def get_object(self):
        """Obtener o crear configuraciones del negocio"""
        if not self.request.user.business:
            raise Http404("Usuario no tiene negocio asignado")
        
        settings, created = BusinessSettings.objects.get_or_create(
            business=self.request.user.business,
            defaults={'created_by': self.request.user}
        )
        return settings
    
    def list(self, request, *args, **kwargs):
        """Devolver las configuraciones del negocio"""
        if not request.user.business:
            return Response(
                {"error": "Usuario no tiene negocio asignado"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        settings = self.get_object()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """No permitir crear nuevas configuraciones"""
        return Response(
            {"error": "Las configuraciones se crean automáticamente"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def check_permissions(self, request):
        """Verificar permisos para modificar configuraciones del negocio"""
        super().check_permissions(request)
        
        if self.action in ['update', 'partial_update', 'destroy']:
            if not request.user.has_business_permission('can_manage_business_settings'):
                self.permission_denied(
                    request,
                    message="No tienes permiso para modificar configuraciones del negocio"
                )
    
    @action(detail=False, methods=['post'])
    def reset_to_defaults(self, request):
        """Resetear configuraciones de negocio a valores por defecto"""
        try:
            settings = self.get_object()
            SettingsService.reset_business_settings_to_defaults(settings)
            
            serializer = self.get_serializer(settings)
            return Response({
                "message": "Configuraciones del negocio restablecidas",
                "data": serializer.data
            })
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet para plantillas de notificación
    """
    serializer_class = NotificationTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Solo devolver plantillas del negocio del usuario"""
        if not self.request.user.business:
            return NotificationTemplate.objects.none()
        return NotificationTemplate.objects.filter(
            business=self.request.user.business
        ).order_by('notification_type')
    
    def perform_create(self, serializer):
        """Crear plantilla para el negocio del usuario"""
        if not self.request.user.business:
            raise serializers.ValidationError("Usuario no tiene negocio asignado")
        
        serializer.save(business=self.request.user.business)
    
    def check_permissions(self, request):
        """Verificar permisos para gestionar plantillas"""
        super().check_permissions(request)
        
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            if not request.user.has_business_permission('can_manage_notifications'):
                self.permission_denied(
                    request,
                    message="No tienes permiso para gestionar plantillas de notificación"
                )
    
    @action(detail=False, methods=['post'])
    def create_default_templates(self, request):
        """Crear plantillas por defecto para el negocio"""
        try:
            if not request.user.business:
                return Response(
                    {"error": "Usuario no tiene negocio asignado"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            templates_created = SettingsService.create_default_notification_templates(
                request.user.business
            )
            
            return Response({
                "message": f"Se crearon {templates_created} plantillas por defecto",
                "templates_created": templates_created
            })
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class SettingsSummaryViewSet(viewsets.ViewSet):
    """
    ViewSet para obtener resumen de todas las configuraciones
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        """Obtener resumen completo de configuraciones"""
        try:
            # Obtener configuraciones de usuario
            user_settings, _ = UserSettings.objects.get_or_create(
                user=request.user
            )
            
            # Obtener configuraciones de negocio si existe
            business_settings = None
            if request.user.business:
                business_settings, _ = BusinessSettings.objects.get_or_create(
                    business=request.user.business,
                    defaults={'created_by': request.user}
                )
            
            # Contar plantillas de notificación
            notification_templates_count = 0
            if request.user.business:
                notification_templates_count = NotificationTemplate.objects.filter(
                    business=request.user.business
                ).count()
            
            # Preparar datos para el serializer
            summary_data = {
                'user_settings': user_settings,
                'business_settings': business_settings,
                'notification_templates_count': notification_templates_count,
                'has_business': bool(request.user.business),
                'is_business_owner': (
                    request.user.business and 
                    request.user.business.owner == request.user
                ) if request.user.business else False,
            }
            
            serializer = SettingsSummarySerializer(summary_data)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def export_settings(self, request):
        """Exportar todas las configuraciones del usuario"""
        try:
            export_data = SettingsService.export_user_settings(request.user)
            return Response({
                "message": "Configuraciones exportadas exitosamente",
                "data": export_data
            })
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
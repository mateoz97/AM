# app/inventory/api/views.py
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from app.inventory.models import Product, ProductCategory, StockMovement
from app.inventory.api.serializers import (
    ProductSerializer, 
    ProductCategorySerializer,
    StockMovementSerializer
)

class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet para operaciones CRUD en productos.
    """
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'description', 'category']
    ordering_fields = ['name', 'price', 'stock', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """
        Filtra productos por el negocio del usuario con optimizaciones.
        """
        user = self.request.user
        
        # Verificar si el usuario tiene un negocio asignado
        if not user.business:
            return Product.objects.none()
            
        # Filtrar por el negocio del usuario con optimizaciones
        return Product.objects.filter(
            business=user.business
        ).select_related('business', 'created_by').prefetch_related('stock_movements')
    
    def perform_create(self, serializer):
        """
        Asigna el negocio del usuario al crear un producto.
        """
        serializer.save(business=self.request.user.business)
    
    def check_permissions(self, request):
        """
        Verificar permisos adicionales según la acción.
        """
        # Llamar a la verificación de permisos original
        super().check_permissions(request)
        
        # Verificar permisos según la acción
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            if not request.user.has_business_permission('can_manage_inventory'):
                self.permission_denied(
                    request,
                    message="No tienes permiso para gestionar productos"
                )
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """
        Devuelve las categorías utilizadas en los productos del negocio.
        """
        # Obtener categorías de las categorías personalizadas
        custom_categories = ProductCategory.objects.filter(
            business=request.user.business,
            is_active=True
        ).values_list('name', flat=True)
        
        # Obtener categorías utilizadas en productos
        product_categories = Product.objects.filter(
            business=request.user.business
        ).exclude(
            category__isnull=True
        ).exclude(
            category=''
        ).values_list('category', flat=True).distinct()
        
        # Combinar y eliminar duplicados
        all_categories = set(list(custom_categories) + list(product_categories))
        
        return Response(sorted(all_categories))
    
    @action(detail=True, methods=['post'])
    def adjust_stock(self, request, pk=None):
        """
        Ajusta el stock de un producto.
        """
        product = self.get_object()
        
        # Verificar permisos
        if not request.user.has_business_permission('can_manage_inventory'):
            return Response(
                {"error": "No tienes permiso para ajustar el stock"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validar datos
        quantity = request.data.get('quantity')
        movement_type = request.data.get('movement_type')
        notes = request.data.get('notes', '')
        
        if quantity is None or movement_type not in ['add', 'remove', 'adjustment']:
            return Response(
                {"error": "Se requiere cantidad y tipo de movimiento válido"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            quantity = int(quantity)
            if quantity < 0 and movement_type != 'adjustment':
                return Response(
                    {"error": "La cantidad debe ser un número positivo"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "La cantidad debe ser un número entero"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear movimiento de stock
        movement_data = {
            'product': product,
            'movement_type': movement_type,
            'quantity': quantity,
            'notes': notes,
            'created_by': request.user
        }
        
        # Crear el movimiento (el serializer actualizará el stock)
        serializer = StockMovementSerializer(data=movement_data, context={'request': request})
        if serializer.is_valid():
            movement = serializer.save()
            
            # Devolver resultado
            return Response({
                'message': f'Stock actualizado correctamente. Nuevo stock: {product.stock}',
                'new_stock': product.stock,
                'movement_id': movement.id
            })
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    @action(detail=True, methods=['get'])
    def stock_movements(self, request, pk=None):
        """
        Devuelve los movimientos de stock de un producto.
        """
        product = self.get_object()
        
        # Filtrar por fechas si se proporcionan
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = StockMovement.objects.filter(product=product)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
            
        # Paginar resultados
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = StockMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = StockMovementSerializer(queryset, many=True)
        return Response(serializer.data)

class ProductCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet para operaciones CRUD en categorías de productos.
    """
    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'is_active']
    ordering = ['name']
    
    def get_queryset(self):
        """
        Filtra categorías por el negocio del usuario.
        """
        user = self.request.user
        
        # Verificar si el usuario tiene un negocio asignado
        if not user.business:
            return ProductCategory.objects.none()
            
        # Filtrar por el negocio del usuario
        return ProductCategory.objects.filter(business=user.business)
    
    def perform_create(self, serializer):
        """
        Asigna el negocio del usuario al crear una categoría.
        """
        serializer.save(business=self.request.user.business)
    
    def check_permissions(self, request):
        """
        Verificar permisos adicionales según la acción.
        """
        # Llamar a la verificación de permisos original
        super().check_permissions(request)
        
        # Verificar permisos según la acción
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            if not request.user.has_business_permission('can_manage_inventory'):
                self.permission_denied(
                    request,
                    message="No tienes permiso para gestionar categorías"
                )

class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar movimientos de stock.
    Solo lectura, los movimientos se crean desde el endpoint adjust_stock.
    """
    serializer_class = StockMovementSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product', 'movement_type', 'created_by']
    ordering_fields = ['created_at', 'quantity']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Filtra movimientos por el negocio del usuario.
        """
        user = self.request.user
        
        # Verificar si el usuario tiene un negocio asignado
        if not user.business:
            return StockMovement.objects.none()
            
        # Filtrar por productos del negocio del usuario
        return StockMovement.objects.filter(product__business=user.business)
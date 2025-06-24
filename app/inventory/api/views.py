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
    ordering_fields = ['name', 'price', 'stock', 'created_at', 'updated_at']
    ordering = ['name']
    
    def get_queryset(self):
        """
        Filtra productos por el negocio del usuario.
        """
        user = self.request.user
        
        # Verificar si el usuario tiene un negocio asignado
        if not user.current_business:
            return Product.objects.none()
            
        # Filtrar por el negocio del usuario
        return Product.objects.filter(business=user.current_business)
    
    def perform_create(self, serializer):
        """
        Asigna el negocio del usuario al crear un producto.
        """
        # Verificar que el usuario tiene un negocio asignado
        if not self.request.user.current_business:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'business': 'Debes tener un negocio asignado para crear productos'
            })
        
        serializer.save(business=self.request.user.current_business)
    
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
            business=request.user.current_business,
            is_active=True
        ).values_list('name', flat=True)
        
        # Obtener categorías utilizadas en productos
        product_categories = Product.objects.filter(
            business=request.user.current_business
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
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """
        Devuelve productos con stock bajo según el umbral configurado del negocio.
        """
        business = request.user.current_business
        if not business:
            return Response([])
        
        # Obtener el umbral de stock bajo del negocio (default: 5)
        threshold = getattr(business.business_settings, 'low_stock_threshold', 5) if hasattr(business, 'business_settings') else 5
        
        # Filtrar productos con stock bajo
        low_stock_products = Product.objects.filter(
            business=business,
            is_active=True,
            stock__lte=threshold
        ).order_by('stock', 'name')
        
        serializer = self.get_serializer(low_stock_products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def advanced_search(self, request):
        """
        Búsqueda avanzada con múltiples filtros.
        """
        queryset = self.get_queryset()
        
        # Filtros básicos
        name = request.query_params.get('name')
        category = request.query_params.get('category')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        min_stock = request.query_params.get('min_stock')
        max_stock = request.query_params.get('max_stock')
        is_active = request.query_params.get('is_active')
        
        # Aplicar filtros
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        if category:
            queryset = queryset.filter(category__icontains=category)
        
        if min_price:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except ValueError:
                pass
        
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                pass
        
        if min_stock:
            try:
                queryset = queryset.filter(stock__gte=int(min_stock))
            except ValueError:
                pass
        
        if max_stock:
            try:
                queryset = queryset.filter(stock__lte=int(max_stock))
            except ValueError:
                pass
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Ordenamiento personalizado
        sort_by = request.query_params.get('sort_by', 'name')
        sort_order = request.query_params.get('sort_order', 'asc')
        
        if sort_by in self.ordering_fields:
            if sort_order == 'desc':
                sort_by = f'-{sort_by}'
            queryset = queryset.order_by(sort_by)
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def inventory_summary(self, request):
        """
        Resumen del inventario con estadísticas útiles.
        """
        business = request.user.current_business
        if not business:
            return Response({
                'error': 'Usuario no tiene negocio asignado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        products = Product.objects.filter(business=business)
        
        # Estadísticas básicas
        total_products = products.count()
        active_products = products.filter(is_active=True).count()
        inactive_products = products.filter(is_active=False).count()
        
        # Análisis de stock
        total_stock_value = sum(
            product.price * product.stock 
            for product in products.filter(is_active=True)
        )
        
        # Stock bajo
        threshold = getattr(business.business_settings, 'low_stock_threshold', 5) if hasattr(business, 'business_settings') else 5
        low_stock_count = products.filter(
            is_active=True,
            stock__lte=threshold
        ).count()
        
        # Stock cero
        out_of_stock_count = products.filter(
            is_active=True,
            stock=0
        ).count()
        
        # Categorías
        categories = products.exclude(
            category__isnull=True
        ).exclude(
            category=''
        ).values_list('category', flat=True).distinct()
        
        categories_stats = {}
        for category in categories:
            category_products = products.filter(category=category, is_active=True)
            categories_stats[category] = {
                'count': category_products.count(),
                'total_stock': sum(p.stock for p in category_products),
                'total_value': sum(p.price * p.stock for p in category_products)
            }
        
        # Top productos por valor de stock
        top_products_by_value = []
        for product in products.filter(is_active=True).order_by('-stock')[:5]:
            top_products_by_value.append({
                'id': product.id,
                'name': product.name,
                'stock': product.stock,
                'price': product.price,
                'stock_value': product.price * product.stock
            })
        
        summary = {
            'overview': {
                'total_products': total_products,
                'active_products': active_products,
                'inactive_products': inactive_products,
                'total_stock_value': total_stock_value,
                'low_stock_count': low_stock_count,
                'out_of_stock_count': out_of_stock_count,
                'low_stock_threshold': threshold
            },
            'categories': {
                'total_categories': len(categories),
                'categories_stats': categories_stats
            },
            'top_products_by_value': top_products_by_value
        }
        
        return Response(summary)
    
    @action(detail=False, methods=['post'])
    def bulk_update_stock(self, request):
        """
        Actualización masiva de stock para múltiples productos.
        """
        if not request.user.has_business_permission('can_manage_inventory'):
            return Response(
                {"error": "No tienes permiso para actualizar stock masivamente"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        updates = request.data.get('updates', [])
        if not updates:
            return Response(
                {"error": "No se proporcionaron actualizaciones"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = {
            'successful_updates': [],
            'failed_updates': [],
            'total_processed': len(updates)
        }
        
        for update in updates:
            try:
                product_id = update.get('product_id')
                quantity = update.get('quantity')
                movement_type = update.get('movement_type', 'adjustment')
                notes = update.get('notes', 'Actualización masiva de stock')
                
                if not product_id or quantity is None:
                    results['failed_updates'].append({
                        'product_id': product_id,
                        'error': 'ID de producto y cantidad son requeridos'
                    })
                    continue
                
                try:
                    product = Product.objects.get(
                        id=product_id,
                        business=request.user.current_business
                    )
                except Product.DoesNotExist:
                    results['failed_updates'].append({
                        'product_id': product_id,
                        'error': 'Producto no encontrado'
                    })
                    continue
                
                # Crear movimiento de stock
                movement_data = {
                    'product': product,
                    'movement_type': movement_type,
                    'quantity': int(quantity),
                    'notes': notes,
                    'created_by': request.user
                }
                
                movement_serializer = StockMovementSerializer(
                    data=movement_data, 
                    context={'request': request}
                )
                
                if movement_serializer.is_valid():
                    movement_serializer.save()
                    results['successful_updates'].append({
                        'product_id': product_id,
                        'product_name': product.name,
                        'new_stock': product.stock,
                        'movement_type': movement_type,
                        'quantity': quantity
                    })
                else:
                    results['failed_updates'].append({
                        'product_id': product_id,
                        'error': movement_serializer.errors
                    })
                    
            except Exception as e:
                results['failed_updates'].append({
                    'product_id': update.get('product_id', 'unknown'),
                    'error': str(e)
                })
        
        return Response({
            'message': f'Actualización masiva completada. {len(results["successful_updates"])} exitosas, {len(results["failed_updates"])} fallidas.',
            'results': results
        })

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
        if not user.current_business:
            return ProductCategory.objects.none()
            
        # Filtrar por el negocio del usuario
        return ProductCategory.objects.filter(business=user.current_business)
    
    def perform_create(self, serializer):
        """
        Asigna el negocio del usuario al crear una categoría.
        """
        # Verificar que el usuario tiene un negocio asignado
        if not self.request.user.current_business:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'business': 'Debes tener un negocio asignado para crear categorías'
            })
        
        serializer.save(business=self.request.user.current_business)
    
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
        if not user.current_business:
            return StockMovement.objects.none()
            
        # Filtrar por productos del negocio del usuario
        return StockMovement.objects.filter(product__business=user.current_business)
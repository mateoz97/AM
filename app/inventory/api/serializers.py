# app/inventory/api/serializers.py
from rest_framework import serializers
from app.inventory.models import Product, ProductCategory, StockMovement

class ProductSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Product"""
    category_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'category', 'category_name',
            'image', 'stock', 'is_active', 'created_at', 'updated_at',
            'created_by', 'created_by_name'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'created_by_name']
    
    def get_category_name(self, obj):
        # Obtener el nombre de la categoría personalizada si existe
        if not obj.category:
            return None
        
        # Verificar si es una categoría personalizada
        try:
            category = ProductCategory.objects.get(
                business=obj.business,
                name=obj.category
            )
            return category.name
        except ProductCategory.DoesNotExist:
            # Si no existe como categoría personalizada, devolver el valor del campo
            return obj.category
            
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None
        
    def create(self, validated_data):
        """
        Sobrescribir create para asignar el usuario y negocio actuales
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            # Asignar el negocio del usuario si no se proporciona
            if 'business' not in validated_data and request.user.business:
                validated_data['business'] = request.user.business
                
            # Asignar el usuario que crea el producto
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)
        
    def validate(self, data):
        """
        Validar que el stock no sea negativo y que precio sea positivo
        """
        if 'stock' in data and data['stock'] < 0:
            data['stock'] = 0
            
        if 'price' in data and data['price'] <= 0:
            raise serializers.ValidationError("El precio debe ser mayor que cero")
            
        return data
        
    def to_representation(self, instance):
        """
        Transformar la representación final del objeto
        """
        data = super().to_representation(instance)
        
        # Formatear la URL de la imagen si existe
        if instance.image and hasattr(instance.image, 'url'):
            data['image'] = instance.image.url
            
        # Incluir información extra si es necesario
        request = self.context.get('request')
        if request and request.query_params.get('include_extra') == 'true':
            data['stock_movements_count'] = instance.stock_movements.count()
            
        return data

class ProductCategorySerializer(serializers.ModelSerializer):
    """Serializer para el modelo ProductCategory"""
    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'description', 'is_active']
        read_only_fields = ['id']
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.business:
            validated_data['business'] = request.user.business
        return super().create(validated_data)
        
    def validate_name(self, value):
        """
        Validar que no exista otra categoría con el mismo nombre en el negocio
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.business:
            # Verificar en caso de creación
            if self.instance is None:
                if ProductCategory.objects.filter(
                    business=request.user.business,
                    name__iexact=value
                ).exists():
                    raise serializers.ValidationError(
                        "Ya existe una categoría con este nombre en tu negocio"
                    )
            # Verificar en caso de actualización
            else:
                if ProductCategory.objects.filter(
                    business=request.user.business,
                    name__iexact=value
                ).exclude(id=self.instance.id).exists():
                    raise serializers.ValidationError(
                        "Ya existe una categoría con este nombre en tu negocio"
                    )
        return value

class StockMovementSerializer(serializers.ModelSerializer):
    """Serializer para el modelo StockMovement"""
    product_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_name', 'movement_type', 'quantity',
            'previous_stock', 'new_stock', 'notes', 'created_at',
            'created_by', 'created_by_name'
        ]
        read_only_fields = [
            'id', 'previous_stock', 'new_stock', 'created_at',
            'created_by', 'created_by_name', 'product_name'
        ]
    
    def get_product_name(self, obj):
        return obj.product.name
        
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None
        
    def create(self, validated_data):
        """
        Sobrescribir create para actualizar el stock del producto
        """
        product = validated_data.get('product')
        quantity = validated_data.get('quantity', 0)
        movement_type = validated_data.get('movement_type')
        
        # Guardar stock anterior
        previous_stock = product.stock
        
        # Calcular nuevo stock según el tipo de movimiento
        if movement_type == 'add':
            product.stock += quantity
        elif movement_type == 'remove':
            product.stock = max(0, product.stock - quantity)
        elif movement_type == 'adjustment':
            product.stock = quantity
        
        # Guardar nuevo stock
        new_stock = product.stock
        
        # Actualizar el producto
        product.save(update_fields=['stock'])
        
        # Asignar valores calculados
        validated_data['previous_stock'] = previous_stock
        validated_data['new_stock'] = new_stock
        
        # Asignar usuario que realiza el movimiento
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)
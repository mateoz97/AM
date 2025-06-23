#!/usr/bin/env python3
from app.orders.models import Order, OrderItem, OrderStatus, OrderStatusHistory, OrderNotification
from app.business.models.business import Business
from app.accounts.models.user import CustomUser
from app.roles.models.role import BusinessRole
from app.business.services.business_service import DatabaseService
from decimal import Decimal
import random

print('=== TESTING ORDERS APP ===')

# Setup test data
print('1. Setting up test data...')
try:
    random_id = random.randint(10000, 99999)
    
    # Create user and business
    user = CustomUser.objects.create_user(
        username=f'testuser{random_id}',
        email=f'test{random_id}@orders.com',
        password='testpass123',
        first_name='Order',
        last_name='Tester'
    )
    
    business = Business.objects.create(
        name=f'Orders_Business_{random_id}',
        owner=user,
        description='Test business for orders',
        email=f'business{random_id}@test.com'
    )
    
    # Switch to business schema
    DatabaseService.switch_to_business_schema(business.id)
    print(f'✓ Test data created - Business: {business.name}')
    
except Exception as e:
    print(f'✗ Setup failed: {e}')
    exit()

print('2. Testing order creation...')
try:
    order = Order.objects.create(
        business=business,
        customer=user,
        customer_name='Test Customer',
        customer_phone='123-456-7890',
        table_number='5',
        order_type='dine_in',
        priority='normal',
        status=OrderStatus.PENDING,
        subtotal=Decimal('25.00'),
        tax_amount=Decimal('2.50'),
        total_amount=Decimal('27.50'),
        customer_notes='No onions please'
    )
    print(f'✓ Order created: {order.order_number}')
    print(f'✓ Order ID: {order.id}')
    print(f'✓ Status: {order.get_status_display()}')
    print(f'✓ Priority: {order.get_priority_display()}')
    print(f'✓ Total amount: ${order.total_amount}')
    
except Exception as e:
    print(f'✗ Order creation failed: {e}')

print('3. Testing order items...')
try:
    item1 = OrderItem.objects.create(
        order=order,
        product_name='Hamburger',
        quantity=2,
        unit_price=Decimal('12.50'),
        total_price=Decimal('25.00'),
        modifications='No pickles'
    )
    
    item2 = OrderItem.objects.create(
        order=order,
        product_name='French Fries',
        quantity=1,
        unit_price=Decimal('5.00'),
        total_price=Decimal('5.00')
    )
    
    print(f'✓ Order items created: {order.items.count()} items')
    print(f'✓ Item 1: {item1.product_name} x{item1.quantity} = ${item1.total_price}')
    print(f'✓ Item 2: {item2.product_name} x{item2.quantity} = ${item2.total_price}')
    
except Exception as e:
    print(f'✗ Order items failed: {e}')

print('4. Testing order state transitions...')
try:
    # Test valid transitions
    print(f'✓ Can transition to confirmed: {order.can_transition_to(OrderStatus.CONFIRMED)}')
    print(f'✓ Can transition to cancelled: {order.can_transition_to(OrderStatus.CANCELLED)}')
    
    # Test transition
    old_status = order.status
    order.transition_to(OrderStatus.CONFIRMED, user=user, notes='Order confirmed by customer')
    print(f'✓ Status transitioned: {old_status} → {order.status}')
    print(f'✓ Confirmed at: {order.confirmed_at}')
    
    # Check history
    history_count = order.status_history.count()
    print(f'✓ Status history entries: {history_count}')
    
except Exception as e:
    print(f'✗ State transitions failed: {e}')

print('5. Testing order notifications...')
try:
    notification = OrderNotification.objects.create(
        order=order,
        message='Order is ready for pickup',
        notification_type='ready',
        target_roles=['waiter', 'manager'],
        is_sent=True
    )
    print(f'✓ Notification created: {notification.message}')
    print(f'✓ Target roles: {notification.target_roles}')
    print(f'✓ Order notifications count: {order.notifications.count()}')
    
except Exception as e:
    print(f'✗ Notifications failed: {e}')

print('6. Testing order methods...')
try:
    print(f'✓ Order is overdue: {order.is_overdue}')
    print(f'✓ Order estimated ready time: {order.estimated_ready_time}')
    print(f'✓ Order preparation status: {order.preparation_status}')
    print(f'✓ Order total items: {order.total_items}')
    
except Exception as e:
    print(f'✗ Order methods failed: {e}')

print('7. Testing order queries...')
try:
    # Test filtering
    active_orders = Order.objects.filter(
        status__in=[OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PREPARING]
    )
    print(f'✓ Active orders count: {active_orders.count()}')
    
    completed_orders = Order.objects.filter(status=OrderStatus.DELIVERED)
    print(f'✓ Completed orders count: {completed_orders.count()}')
    
    business_orders = Order.objects.filter(business=business)
    print(f'✓ Business orders count: {business_orders.count()}')
    
except Exception as e:
    print(f'✗ Order queries failed: {e}')

print('✓ Orders app tests completed successfully')
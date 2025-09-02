"""
채팅 관련 모델
"""
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Product
import uuid


class ChatSession(models.Model):
    """채팅 세션"""
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    user_identifier = models.CharField(max_length=50, help_text="비로그인 사용자 식별자")
    
    STATUS_CHOICES = [
        ('active', '활성'),
        ('completed', '완료'),
        ('timeout', '타임아웃'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chat_sessions'
        verbose_name = '채팅 세션'
        verbose_name_plural = '채팅 세션'
    
    def __str__(self):
        return f"Session {self.session_id}"


class ChatMessage(models.Model):
    """채팅 메시지"""
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    
    ROLE_CHOICES = [
        ('user', '사용자'),
        ('bot', '봇'),
        ('system', '시스템'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    
    # 메타데이터
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_messages'
        verbose_name = '채팅 메시지'
        verbose_name_plural = '채팅 메시지'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class Order(models.Model):
    """주문 정보"""
    order_id = models.CharField(max_length=50, unique=True)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='orders')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    STATUS_CHOICES = [
        ('pending', '대기중'),
        ('confirmed', '확정'),
        ('shipped', '배송중'),
        ('delivered', '배송완료'),
        ('cancelled', '취소됨'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    delivery_address = models.TextField(blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'orders'
        verbose_name = '주문'
        verbose_name_plural = '주문'
    
    def __str__(self):
        return f"Order {self.order_id}"


class OrderItem(models.Model):
    """주문 아이템"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'order_items'
        verbose_name = '주문 아이템'
        verbose_name_plural = '주문 아이템'
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Cart(models.Model):
    """장바구니"""
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart'
        verbose_name = '장바구니'
        verbose_name_plural = '장바구니'
        unique_together = ['session', 'product']
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"



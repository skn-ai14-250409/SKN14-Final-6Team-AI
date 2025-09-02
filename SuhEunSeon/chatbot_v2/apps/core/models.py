"""
공통 모델 정의
"""
from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """사용자 프로필 확장"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    birth_date = models.DateField(null=True, blank=True)
    phone_num = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=200, blank=True)
    post_num = models.CharField(max_length=10, blank=True)
    
    # 식단 정보
    GENDER_CHOICES = [
        ('M', '남성'),
        ('F', '여성'),
    ]
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    age = models.IntegerField(null=True, blank=True)
    allergy = models.CharField(max_length=100, blank=True)
    vegan = models.BooleanField(default=False)
    house_hold = models.IntegerField(null=True, blank=True)
    unfavorite = models.CharField(max_length=100, blank=True)
    
    MEMBERSHIP_CHOICES = [
        ('basic', '기본'),
        ('premium', '프리미엄'),
        ('gold', '골드'),
    ]
    membership = models.CharField(max_length=20, choices=MEMBERSHIP_CHOICES, default='basic')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'userinfo_tbl'
        verbose_name = '사용자 프로필'
        verbose_name_plural = '사용자 프로필'

    def __str__(self):
        return f"{self.user.username} 프로필"


class Category(models.Model):
    """상품 카테고리"""
    name = models.CharField(max_length=45, unique=True)
    category_id = models.IntegerField(unique=True)
    
    class Meta:
        db_table = 'category_tbl'
        verbose_name = '카테고리'
        verbose_name_plural = '카테고리'
    
    def __str__(self):
        return self.name


class Product(models.Model):
    """상품 정보"""
    name = models.CharField(max_length=45, unique=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    origin = models.CharField(max_length=45)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_tbl'
        verbose_name = '상품'
        verbose_name_plural = '상품'
    
    def __str__(self):
        return self.name


class ProductItem(models.Model):
    """상품 아이템 (유기농 등 변형)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=45)
    organic = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'item_tbl'
        verbose_name = '상품 아이템'
        verbose_name_plural = '상품 아이템'
    
    def __str__(self):
        return f"{self.product.name} - {self.item_name}"


class Stock(models.Model):
    """재고 관리"""
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='stock')
    quantity = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'stock_tbl'
        verbose_name = '재고'
        verbose_name_plural = '재고'
    
    def __str__(self):
        return f"{self.product.name} - {self.quantity}개"


class FAQ(models.Model):
    """자주 묻는 질문"""
    question = models.CharField(max_length=500)
    answer = models.TextField()
    category = models.CharField(max_length=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'faq_tbl'
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQ'
    
    def __str__(self):
        return self.question[:50]
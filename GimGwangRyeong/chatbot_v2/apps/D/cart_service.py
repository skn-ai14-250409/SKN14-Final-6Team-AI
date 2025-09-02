"""
카트 관리 서비스
멱등성을 보장하는 장바구니 관리 기능
"""
from decimal import Decimal
from typing import Dict, List, Any, Optional
from django.db import transaction
from django.db.models import F
from apps.chat.models import Cart, ChatSession
from apps.core.models import Product, Stock


class CartState:
    """카트 상태 관리 클래스"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session = None
        self.items = []
        self.subtotal = Decimal('0.00')
        self.discount = Decimal('0.00')  
        self.total = Decimal('0.00')
        self._load_session()
        self._load_cart_items()
    
    def _load_session(self):
        """채팅 세션 로드"""
        try:
            self.session = ChatSession.objects.get(session_id=self.session_id)
        except ChatSession.DoesNotExist:
            raise ValueError(f"채팅 세션을 찾을 수 없습니다: {self.session_id}")
    
    def _load_cart_items(self):
        """카트 아이템 로드"""
        cart_items = Cart.objects.filter(session=self.session).select_related('product')
        self.items = []
        
        for cart_item in cart_items:
            item_data = {
                'product_id': cart_item.product.id,
                'product_name': cart_item.product.name,
                'quantity': cart_item.quantity,
                'unit_price': cart_item.unit_price,
                'total_price': cart_item.total_price,
                'origin': cart_item.product.origin,
                'category': cart_item.product.category.name
            }
            self.items.append(item_data)
        
        self._calculate_totals()
    
    def _calculate_totals(self):
        """합계 계산"""
        self.subtotal = sum(Decimal(str(item['total_price'])) for item in self.items)
        # TODO: 할인 로직 구현 (쿠폰, 프로모션 등)
        self.discount = Decimal('0.00')
        self.total = self.subtotal - self.discount
    
    def add_item(self, product_id: int, quantity: int) -> Dict[str, Any]:
        """
        카트에 상품 추가 (멱등성 보장)
        같은 상품이 있으면 수량을 업데이트
        """
        try:
            with transaction.atomic():
                # 상품 존재 확인
                try:
                    product = Product.objects.get(id=product_id)
                except Product.DoesNotExist:
                    return {
                        'success': False,
                        'message': f'상품을 찾을 수 없습니다 (ID: {product_id})'
                    }
                
                # 재고 확인
                try:
                    stock = Stock.objects.get(product=product)
                    if stock.quantity < quantity:
                        return {
                            'success': False,
                            'message': f'{product.name}의 재고가 부족합니다. (재고: {stock.quantity}개)'
                        }
                except Stock.DoesNotExist:
                    return {
                        'success': False,
                        'message': f'{product.name}의 재고 정보가 없습니다.'
                    }
                
                # 카트 아이템 추가/업데이트 (멱등성)
                cart_item, created = Cart.objects.get_or_create(
                    session=self.session,
                    product=product,
                    defaults={
                        'quantity': quantity,
                        'unit_price': product.unit_price,
                        'total_price': product.unit_price * quantity
                    }
                )
                
                if not created:
                    # 기존 아이템 수량 업데이트
                    new_quantity = cart_item.quantity + quantity
                    if stock.quantity < new_quantity:
                        return {
                            'success': False,
                            'message': f'{product.name}의 재고가 부족합니다. (현재 카트: {cart_item.quantity}개, 재고: {stock.quantity}개)'
                        }
                    
                    cart_item.quantity = new_quantity
                    cart_item.total_price = cart_item.unit_price * new_quantity
                    cart_item.save()
                
                # 상태 새로고침
                self._load_cart_items()
                
                return {
                    'success': True,
                    'message': f'{product.name} {quantity}개가 장바구니에 추가되었습니다.',
                    'item': {
                        'product_id': product.id,
                        'product_name': product.name,
                        'quantity': cart_item.quantity,
                        'unit_price': float(cart_item.unit_price),
                        'total_price': float(cart_item.total_price)
                    }
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'장바구니 추가 중 오류가 발생했습니다: {str(e)}'
            }
    
    def update_item(self, product_id: int, quantity: int) -> Dict[str, Any]:
        """카트 아이템 수량 업데이트"""
        try:
            with transaction.atomic():
                try:
                    cart_item = Cart.objects.get(session=self.session, product_id=product_id)
                    product = cart_item.product
                except Cart.DoesNotExist:
                    return {
                        'success': False,
                        'message': '장바구니에서 해당 상품을 찾을 수 없습니다.'
                    }
                
                if quantity <= 0:
                    return self.remove_item(product_id)
                
                # 재고 확인
                try:
                    stock = Stock.objects.get(product=product)
                    if stock.quantity < quantity:
                        return {
                            'success': False,
                            'message': f'{product.name}의 재고가 부족합니다. (재고: {stock.quantity}개)'
                        }
                except Stock.DoesNotExist:
                    return {
                        'success': False,
                        'message': f'{product.name}의 재고 정보가 없습니다.'
                    }
                
                cart_item.quantity = quantity
                cart_item.total_price = cart_item.unit_price * quantity
                cart_item.save()
                
                # 상태 새로고침
                self._load_cart_items()
                
                return {
                    'success': True,
                    'message': f'{product.name}의 수량이 {quantity}개로 변경되었습니다.',
                    'item': {
                        'product_id': product.id,
                        'product_name': product.name,
                        'quantity': quantity,
                        'unit_price': float(cart_item.unit_price),
                        'total_price': float(cart_item.total_price)
                    }
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'수량 변경 중 오류가 발생했습니다: {str(e)}'
            }
    
    def remove_item(self, product_id: int) -> Dict[str, Any]:
        """카트에서 상품 제거"""
        try:
            cart_item = Cart.objects.get(session=self.session, product_id=product_id)
            product_name = cart_item.product.name
            cart_item.delete()
            
            # 상태 새로고침
            self._load_cart_items()
            
            return {
                'success': True,
                'message': f'{product_name}이(가) 장바구니에서 제거되었습니다.'
            }
            
        except Cart.DoesNotExist:
            return {
                'success': False,
                'message': '장바구니에서 해당 상품을 찾을 수 없습니다.'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'상품 제거 중 오류가 발생했습니다: {str(e)}'
            }
    
    def clear_cart(self) -> Dict[str, Any]:
        """카트 비우기"""
        try:
            Cart.objects.filter(session=self.session).delete()
            
            # 상태 새로고침
            self._load_cart_items()
            
            return {
                'success': True,
                'message': '장바구니가 비워졌습니다.'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'장바구니 비우기 중 오류가 발생했습니다: {str(e)}'
            }
    
    def get_cart_summary(self) -> Dict[str, Any]:
        """카트 요약 정보 반환"""
        return {
            'session_id': self.session_id,
            'items': self.items,
            'item_count': len(self.items),
            'total_quantity': sum(item['quantity'] for item in self.items),
            'subtotal': float(self.subtotal),
            'discount': float(self.discount),
            'total': float(self.total)
        }


def cart_manage(session_id: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    장바구니 관리 메인 함수
    
    Args:
        session_id: 채팅 세션 ID
        action: 수행할 작업 ('add', 'update', 'remove', 'clear', 'get')
        **kwargs: 작업별 파라미터
            - product_id: 상품 ID
            - quantity: 수량
    
    Returns:
        Dict: 작업 결과 및 카트 상태
    """
    try:
        cart_state = CartState(session_id)
        
        if action == 'add':
            product_id = kwargs.get('product_id')
            quantity = kwargs.get('quantity', 1)
            
            if not product_id:
                return {
                    'success': False,
                    'message': 'product_id가 필요합니다.',
                    'cart': cart_state.get_cart_summary()
                }
            
            result = cart_state.add_item(product_id, quantity)
            
        elif action == 'update':
            product_id = kwargs.get('product_id')
            quantity = kwargs.get('quantity', 1)
            
            if not product_id:
                return {
                    'success': False,
                    'message': 'product_id가 필요합니다.',
                    'cart': cart_state.get_cart_summary()
                }
            
            result = cart_state.update_item(product_id, quantity)
            
        elif action == 'remove':
            product_id = kwargs.get('product_id')
            
            if not product_id:
                return {
                    'success': False,
                    'message': 'product_id가 필요합니다.',
                    'cart': cart_state.get_cart_summary()
                }
            
            result = cart_state.remove_item(product_id)
            
        elif action == 'clear':
            result = cart_state.clear_cart()
            
        elif action == 'get':
            result = {
                'success': True,
                'message': '장바구니 조회 완료'
            }
            
        else:
            return {
                'success': False,
                'message': f'지원하지 않는 작업입니다: {action}',
                'cart': cart_state.get_cart_summary()
            }
        
        # 결과에 카트 상태 추가
        result['cart'] = cart_state.get_cart_summary()
        return result
        
    except ValueError as e:
        return {
            'success': False,
            'message': str(e),
            'cart': {'session_id': session_id, 'items': [], 'item_count': 0, 'total_quantity': 0, 'subtotal': 0.0, 'discount': 0.0, 'total': 0.0}
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'장바구니 관리 중 오류가 발생했습니다: {str(e)}',
            'cart': {'session_id': session_id, 'items': [], 'item_count': 0, 'total_quantity': 0, 'subtotal': 0.0, 'discount': 0.0, 'total': 0.0}
        }
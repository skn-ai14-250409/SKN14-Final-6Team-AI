"""
주문 처리 서비스
주문 확정/취소 및 주문 기록 생성
"""
from typing import Dict, List, Any, Optional
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.chat.models import Cart, ChatSession, Order, OrderItem
from apps.core.models import Stock
from .checkout_service import CheckoutState
import uuid
import logging

logger = logging.getLogger(__name__)


class OrderProcessor:
    """주문 처리 클래스"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session = None
        self.checkout_state = None
        self._load_session()
        self._load_checkout_state()
    
    def _load_session(self):
        """채팅 세션 로드"""
        try:
            self.session = ChatSession.objects.get(session_id=self.session_id)
        except ChatSession.DoesNotExist:
            raise ValueError(f"채팅 세션을 찾을 수 없습니다: {self.session_id}")
    
    def _load_checkout_state(self):
        """체크아웃 상태 로드"""
        try:
            self.checkout_state = CheckoutState(self.session_id)
        except ValueError as e:
            raise ValueError(f"체크아웃 상태를 로드할 수 없습니다: {str(e)}")
    
    def _generate_order_id(self) -> str:
        """주문 번호 생성"""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_suffix = str(uuid.uuid4()).split('-')[0].upper()
        return f"ORD{timestamp}{random_suffix}"
    
    def _validate_stock_availability(self) -> Dict[str, Any]:
        """재고 가용성 재확인"""
        unavailable_items = []
        
        for item in self.checkout_state.cart_items:
            try:
                stock = Stock.objects.get(product_id=item['product_id'])
                if stock.quantity < item['quantity']:
                    unavailable_items.append({
                        'product_name': item['product_name'],
                        'requested_quantity': item['quantity'],
                        'available_quantity': stock.quantity
                    })
            except Stock.DoesNotExist:
                unavailable_items.append({
                    'product_name': item['product_name'],
                    'requested_quantity': item['quantity'],
                    'available_quantity': 0
                })
        
        if unavailable_items:
            return {
                'available': False,
                'unavailable_items': unavailable_items
            }
        
        return {'available': True}
    
    def _reserve_stock(self) -> Dict[str, Any]:
        """재고 예약 (차감)"""
        try:
            with transaction.atomic():
                reserved_items = []
                
                for item in self.checkout_state.cart_items:
                    stock = Stock.objects.select_for_update().get(product_id=item['product_id'])
                    
                    if stock.quantity < item['quantity']:
                        # 롤백을 위해 예외 발생
                        raise ValueError(f"{item['product_name']}의 재고가 부족합니다.")
                    
                    # 재고 차감
                    stock.quantity -= item['quantity']
                    stock.save()
                    
                    reserved_items.append({
                        'product_id': item['product_id'],
                        'product_name': item['product_name'],
                        'reserved_quantity': item['quantity'],
                        'remaining_stock': stock.quantity
                    })
                
                return {
                    'success': True,
                    'reserved_items': reserved_items
                }
                
        except Exception as e:
            logger.error(f"재고 예약 실패: {str(e)}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def _release_stock(self) -> Dict[str, Any]:
        """재고 해제 (복원)"""
        try:
            with transaction.atomic():
                released_items = []
                
                for item in self.checkout_state.cart_items:
                    stock = Stock.objects.select_for_update().get(product_id=item['product_id'])
                    
                    # 재고 복원
                    stock.quantity += item['quantity']
                    stock.save()
                    
                    released_items.append({
                        'product_id': item['product_id'],
                        'product_name': item['product_name'],
                        'released_quantity': item['quantity'],
                        'restored_stock': stock.quantity
                    })
                
                return {
                    'success': True,
                    'released_items': released_items
                }
                
        except Exception as e:
            logger.error(f"재고 해제 실패: {str(e)}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def confirm_order(self) -> Dict[str, Any]:
        """주문 확정"""
        try:
            # 체크아웃 준비 상태 확인
            if not self.checkout_state._is_ready_for_order():
                missing_info = self.checkout_state.get_missing_info()
                return {
                    'success': False,
                    'message': f'주문 정보가 완전하지 않습니다. 누락된 정보: {", ".join(missing_info)}',
                    'missing_info': missing_info
                }
            
            # 재고 가용성 재확인
            stock_check = self._validate_stock_availability()
            if not stock_check['available']:
                return {
                    'success': False,
                    'message': '일부 상품의 재고가 부족합니다.',
                    'unavailable_items': stock_check['unavailable_items']
                }
            
            with transaction.atomic():
                # 재고 예약
                stock_reservation = self._reserve_stock()
                if not stock_reservation['success']:
                    return {
                        'success': False,
                        'message': f'재고 예약에 실패했습니다: {stock_reservation["message"]}'
                    }
                
                # 주문 생성
                order_id = self._generate_order_id()
                total_amount = sum(Decimal(str(item['total_price'])) for item in self.checkout_state.cart_items)
                
                checkout_info = self.checkout_state.checkout_info
                delivery_address = f"{checkout_info['delivery_address']}"
                if checkout_info['detailed_address']:
                    delivery_address += f" {checkout_info['detailed_address']}"
                if checkout_info['post_code']:
                    delivery_address = f"({checkout_info['post_code']}) " + delivery_address
                
                order = Order.objects.create(
                    order_id=order_id,
                    session=self.session,
                    user=self.session.user,
                    total_amount=total_amount,
                    status='confirmed',
                    delivery_address=delivery_address,
                    payment_method=checkout_info['payment_method']
                )
                
                # 주문 아이템 생성
                order_items = []
                for item in self.checkout_state.cart_items:
                    order_item = OrderItem.objects.create(
                        order=order,
                        product_id=item['product_id'],
                        quantity=item['quantity'],
                        unit_price=item['unit_price'],
                        total_price=item['total_price']
                    )
                    order_items.append({
                        'product_name': item['product_name'],
                        'quantity': item['quantity'],
                        'unit_price': float(item['unit_price']),
                        'total_price': float(item['total_price'])
                    })
                
                # 장바구니 비우기
                Cart.objects.filter(session=self.session).delete()
                
                # 체크아웃 확정 상태로 변경
                self.checkout_state.checkout_info['confirmed'] = True
                
                logger.info(f"주문 확정 완료: {order_id}")
                
                return {
                    'success': True,
                    'message': '주문이 성공적으로 확정되었습니다.',
                    'order': {
                        'order_id': order_id,
                        'status': 'confirmed',
                        'total_amount': float(total_amount),
                        'items': order_items,
                        'delivery_info': {
                            'address': delivery_address,
                            'recipient': checkout_info['recipient_name'],
                            'phone': checkout_info['recipient_phone'],
                            'delivery_time': checkout_info['delivery_time'],
                            'memo': checkout_info.get('delivery_memo', '')
                        },
                        'payment_method': checkout_info['payment_method'],
                        'created_at': order.created_at.isoformat()
                    },
                    'reserved_stock': stock_reservation['reserved_items']
                }
                
        except Exception as e:
            logger.error(f"주문 확정 실패: {str(e)}")
            return {
                'success': False,
                'message': f'주문 확정 중 오류가 발생했습니다: {str(e)}'
            }
    
    def cancel_order(self, reason: str = '') -> Dict[str, Any]:
        """주문 취소"""
        try:
            with transaction.atomic():
                # 재고 해제
                stock_release = self._release_stock()
                if not stock_release['success']:
                    logger.warning(f"재고 해제 실패: {stock_release['message']}")
                
                # 취소 주문 기록 생성
                order_id = self._generate_order_id()
                total_amount = sum(Decimal(str(item['total_price'])) for item in self.checkout_state.cart_items)
                
                checkout_info = self.checkout_state.checkout_info
                delivery_address = f"{checkout_info.get('delivery_address', 'N/A')}"
                
                order = Order.objects.create(
                    order_id=order_id,
                    session=self.session,
                    user=self.session.user,
                    total_amount=total_amount,
                    status='cancelled',
                    delivery_address=delivery_address,
                    payment_method=checkout_info.get('payment_method', 'N/A')
                )
                
                # 취소된 주문 아이템 기록
                cancelled_items = []
                for item in self.checkout_state.cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product_id=item['product_id'],
                        quantity=item['quantity'],
                        unit_price=item['unit_price'],
                        total_price=item['total_price']
                    )
                    cancelled_items.append({
                        'product_name': item['product_name'],
                        'quantity': item['quantity'],
                        'unit_price': float(item['unit_price']),
                        'total_price': float(item['total_price'])
                    })
                
                # 장바구니는 유지 (사용자가 다시 주문할 수 있도록)
                
                logger.info(f"주문 취소 완료: {order_id}, 사유: {reason}")
                
                return {
                    'success': True,
                    'message': '주문이 취소되었습니다.',
                    'order': {
                        'order_id': order_id,
                        'status': 'cancelled',
                        'total_amount': float(total_amount),
                        'items': cancelled_items,
                        'cancellation_reason': reason,
                        'created_at': order.created_at.isoformat()
                    },
                    'released_stock': stock_release.get('released_items', [])
                }
                
        except Exception as e:
            logger.error(f"주문 취소 실패: {str(e)}")
            return {
                'success': False,
                'message': f'주문 취소 중 오류가 발생했습니다: {str(e)}'
            }
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """주문 상태 조회"""
        try:
            order = Order.objects.get(order_id=order_id, session=self.session)
            order_items = order.items.select_related('product').all()
            
            items_data = []
            for item in order_items:
                items_data.append({
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'unit_price': float(item.unit_price),
                    'total_price': float(item.total_price)
                })
            
            return {
                'success': True,
                'order': {
                    'order_id': order.order_id,
                    'status': order.status,
                    'total_amount': float(order.total_amount),
                    'items': items_data,
                    'delivery_address': order.delivery_address,
                    'payment_method': order.payment_method,
                    'created_at': order.created_at.isoformat(),
                    'updated_at': order.updated_at.isoformat()
                }
            }
            
        except Order.DoesNotExist:
            return {
                'success': False,
                'message': f'주문을 찾을 수 없습니다: {order_id}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'주문 조회 중 오류가 발생했습니다: {str(e)}'
            }


def order_process(session_id: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    주문 처리 메인 함수
    
    Args:
        session_id: 채팅 세션 ID
        action: 수행할 작업 ('confirm', 'cancel', 'status')
        **kwargs: 작업별 파라미터
            - reason: 취소 사유 (cancel 시)
            - order_id: 주문 ID (status 시)
    
    Returns:
        Dict: 작업 결과
    """
    try:
        order_processor = OrderProcessor(session_id)
        
        if action == 'confirm':
            result = order_processor.confirm_order()
            
        elif action == 'cancel':
            reason = kwargs.get('reason', '사용자 요청')
            result = order_processor.cancel_order(reason)
            
        elif action == 'status':
            order_id = kwargs.get('order_id')
            if not order_id:
                return {
                    'success': False,
                    'message': 'order_id가 필요합니다.'
                }
            result = order_processor.get_order_status(order_id)
            
        else:
            return {
                'success': False,
                'message': f'지원하지 않는 작업입니다: {action}'
            }
        
        return result
        
    except ValueError as e:
        return {
            'success': False,
            'message': str(e)
        }
    except Exception as e:
        logger.error(f"주문 처리 중 오류 발생: {str(e)}")
        return {
            'success': False,
            'message': f'주문 처리 중 오류가 발생했습니다: {str(e)}'
        }
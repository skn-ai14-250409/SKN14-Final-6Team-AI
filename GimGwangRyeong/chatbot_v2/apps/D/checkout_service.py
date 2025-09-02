"""
결제 진행 서비스
배송지, 배송시간, 결제수단 정보 수집 및 검증
"""
from typing import Dict, List, Any, Optional
from decimal import Decimal
from django.db import transaction
from apps.chat.models import Cart, ChatSession
from apps.core.models import UserProfile, Product
import re
from datetime import datetime, timedelta


class CheckoutState:
    """결제 진행 상태 관리 클래스"""
    
    # 클래스 변수로 상태 저장 (세션 간 유지)
    _session_states = {}
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session = None
        self.cart_items = []
        self.user_profile = None
        
        # 기존 상태가 있으면 복원, 없으면 초기화
        if session_id in CheckoutState._session_states:
            self.checkout_info = CheckoutState._session_states[session_id].copy()
        else:
            self.checkout_info = {
                'delivery_address': '',
                'detailed_address': '',
                'post_code': '',
                'delivery_time': '',
                'payment_method': '',
                'recipient_name': '',
                'recipient_phone': '',
                'delivery_memo': '',
                'confirmed': False
            }
        
        self._load_session()
        self._load_cart_items()
        self._load_user_profile()
    
    def _load_session(self):
        """채팅 세션 로드"""
        try:
            self.session = ChatSession.objects.get(session_id=self.session_id)
        except ChatSession.DoesNotExist:
            raise ValueError(f"채팅 세션을 찾을 수 없습니다: {self.session_id}")
    
    def _load_cart_items(self):
        """카트 아이템 로드"""
        cart_items = Cart.objects.filter(session=self.session).select_related('product')
        if not cart_items.exists():
            raise ValueError("장바구니가 비어있습니다. 결제를 진행할 수 없습니다.")
        
        self.cart_items = []
        for cart_item in cart_items:
            item_data = {
                'product_id': cart_item.product.id,
                'product_name': cart_item.product.name,
                'quantity': cart_item.quantity,
                'unit_price': cart_item.unit_price,
                'total_price': cart_item.total_price
            }
            self.cart_items.append(item_data)
    
    def _load_user_profile(self):
        """사용자 프로필 로드 (있는 경우)"""
        if self.session.user:
            try:
                self.user_profile = UserProfile.objects.get(user=self.session.user)
                # 기존 정보로 체크아웃 정보 초기화
                self.checkout_info.update({
                    'delivery_address': self.user_profile.address or '',
                    'post_code': self.user_profile.post_num or '',
                    'recipient_name': self.session.user.get_full_name() or self.session.user.username,
                    'recipient_phone': self.user_profile.phone_num or ''
                })
            except UserProfile.DoesNotExist:
                self.user_profile = None
    
    def validate_address(self, address: str, detailed_address: str = '', post_code: str = '') -> Dict[str, Any]:
        """배송지 주소 검증"""
        if not address or len(address.strip()) < 5:
            return {
                'valid': False,
                'message': '배송지 주소는 최소 5자 이상 입력해주세요.'
            }
        
        # 우편번호 검증 (5자리 숫자)
        if post_code and not re.match(r'^\d{5}$', post_code):
            return {
                'valid': False,
                'message': '우편번호는 5자리 숫자로 입력해주세요.'
            }
        
        return {
            'valid': True,
            'message': '주소 검증 완료'
        }
    
    def validate_phone(self, phone: str) -> Dict[str, Any]:
        """전화번호 검증"""
        if not phone:
            return {
                'valid': False,
                'message': '연락처를 입력해주세요.'
            }
        
        # 전화번호 패턴 검증 (010-1234-5678, 01012345678 등)
        phone_pattern = r'^(010|011|016|017|018|019)-?\d{3,4}-?\d{4}$'
        if not re.match(phone_pattern, phone.replace('-', '').replace(' ', '')):
            return {
                'valid': False,
                'message': '올바른 전화번호 형식이 아닙니다. (예: 010-1234-5678)'
            }
        
        return {
            'valid': True,
            'message': '전화번호 검증 완료'
        }
    
    def validate_delivery_time(self, delivery_time: str) -> Dict[str, Any]:
        """배송시간 검증"""
        valid_times = [
            '오전 (09:00-12:00)',
            '오후 (12:00-17:00)',
            '저녁 (17:00-21:00)',
            '상관없음'
        ]
        
        if delivery_time not in valid_times:
            return {
                'valid': False,
                'message': f'올바른 배송시간을 선택해주세요. 가능한 시간: {", ".join(valid_times)}'
            }
        
        return {
            'valid': True,
            'message': '배송시간 검증 완료'
        }
    
    def validate_payment_method(self, payment_method: str) -> Dict[str, Any]:
        """결제수단 검증"""
        valid_methods = [
            '신용카드',
            '체크카드', 
            '계좌이체',
            '간편결제',
            '무통장입금'
        ]
        
        if payment_method not in valid_methods:
            return {
                'valid': False,
                'message': f'올바른 결제수단을 선택해주세요. 가능한 결제수단: {", ".join(valid_methods)}'
            }
        
        return {
            'valid': True,
            'message': '결제수단 검증 완료'
        }
    
    def set_delivery_info(self, address: str, detailed_address: str = '', post_code: str = '', 
                         recipient_name: str = '', recipient_phone: str = '', 
                         delivery_memo: str = '') -> Dict[str, Any]:
        """배송 정보 설정"""
        try:
            # 주소 검증
            addr_validation = self.validate_address(address, detailed_address, post_code)
            if not addr_validation['valid']:
                return {
                    'success': False,
                    'message': addr_validation['message']
                }
            
            # 수신자명 검증
            if not recipient_name or len(recipient_name.strip()) < 2:
                return {
                    'success': False,
                    'message': '수신자명은 최소 2자 이상 입력해주세요.'
                }
            
            # 전화번호 검증
            phone_validation = self.validate_phone(recipient_phone)
            if not phone_validation['valid']:
                return {
                    'success': False,
                    'message': phone_validation['message']
                }
            
            # 정보 업데이트
            self.checkout_info.update({
                'delivery_address': address.strip(),
                'detailed_address': detailed_address.strip(),
                'post_code': post_code.strip(),
                'recipient_name': recipient_name.strip(),
                'recipient_phone': recipient_phone.strip(),
                'delivery_memo': delivery_memo.strip()
            })
            
            # 상태 저장
            self._save_state()
            
            return {
                'success': True,
                'message': '배송 정보가 설정되었습니다.'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'배송 정보 설정 중 오류가 발생했습니다: {str(e)}'
            }
    
    def set_delivery_time(self, delivery_time: str) -> Dict[str, Any]:
        """배송 시간 설정"""
        try:
            time_validation = self.validate_delivery_time(delivery_time)
            if not time_validation['valid']:
                return {
                    'success': False,
                    'message': time_validation['message']
                }
            
            self.checkout_info['delivery_time'] = delivery_time
            
            # 상태 저장
            self._save_state()
            
            return {
                'success': True,
                'message': f'배송시간이 {delivery_time}으로 설정되었습니다.'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'배송시간 설정 중 오류가 발생했습니다: {str(e)}'
            }
    
    def set_payment_method(self, payment_method: str) -> Dict[str, Any]:
        """결제수단 설정"""
        try:
            payment_validation = self.validate_payment_method(payment_method)
            if not payment_validation['valid']:
                return {
                    'success': False,
                    'message': payment_validation['message']
                }
            
            self.checkout_info['payment_method'] = payment_method
            
            # 상태 저장
            self._save_state()
            
            return {
                'success': True,
                'message': f'결제수단이 {payment_method}으로 설정되었습니다.'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'결제수단 설정 중 오류가 발생했습니다: {str(e)}'
            }
    
    def get_checkout_summary(self) -> Dict[str, Any]:
        """결제 요약 정보 반환"""
        total_amount = sum(Decimal(str(item['total_price'])) for item in self.cart_items)
        
        return {
            'session_id': self.session_id,
            'cart_items': self.cart_items,
            'item_count': len(self.cart_items),
            'total_amount': float(total_amount),
            'delivery_info': {
                'address': self.checkout_info['delivery_address'],
                'detailed_address': self.checkout_info['detailed_address'],
                'post_code': self.checkout_info['post_code'],
                'recipient_name': self.checkout_info['recipient_name'],
                'recipient_phone': self.checkout_info['recipient_phone'],
                'delivery_memo': self.checkout_info['delivery_memo']
            },
            'delivery_time': self.checkout_info['delivery_time'],
            'payment_method': self.checkout_info['payment_method'],
            'confirmed': self.checkout_info['confirmed'],
            'ready_for_order': self._is_ready_for_order()
        }
    
    def _is_ready_for_order(self) -> bool:
        """주문 준비 완료 상태 확인"""
        required_fields = [
            'delivery_address',
            'recipient_name', 
            'recipient_phone',
            'delivery_time',
            'payment_method'
        ]
        
        for field in required_fields:
            if not self.checkout_info.get(field):
                return False
        
        return True
    
    def get_missing_info(self) -> List[str]:
        """누락된 필수 정보 반환"""
        missing = []
        
        if not self.checkout_info.get('delivery_address'):
            missing.append('배송주소')
        if not self.checkout_info.get('recipient_name'):
            missing.append('수신자명')
        if not self.checkout_info.get('recipient_phone'):
            missing.append('연락처')
        if not self.checkout_info.get('delivery_time'):
            missing.append('배송시간')
        if not self.checkout_info.get('payment_method'):
            missing.append('결제수단')
        
        return missing


def checkout(session_id: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    결제 진행 메인 함수
    
    Args:
        session_id: 채팅 세션 ID
        action: 수행할 작업 ('set_delivery', 'set_time', 'set_payment', 'get_summary')
        **kwargs: 작업별 파라미터
    
    Returns:
        Dict: 작업 결과 및 체크아웃 상태
    """
    try:
        checkout_state = CheckoutState(session_id)
        
        if action == 'set_delivery':
            address = kwargs.get('address', '')
            detailed_address = kwargs.get('detailed_address', '')
            post_code = kwargs.get('post_code', '')
            recipient_name = kwargs.get('recipient_name', '')
            recipient_phone = kwargs.get('recipient_phone', '')
            delivery_memo = kwargs.get('delivery_memo', '')
            
            result = checkout_state.set_delivery_info(
                address, detailed_address, post_code, 
                recipient_name, recipient_phone, delivery_memo
            )
            
        elif action == 'set_time':
            delivery_time = kwargs.get('delivery_time', '')
            result = checkout_state.set_delivery_time(delivery_time)
            
        elif action == 'set_payment':
            payment_method = kwargs.get('payment_method', '')
            result = checkout_state.set_payment_method(payment_method)
            
        elif action == 'get_summary':
            result = {
                'success': True,
                'message': '결제 정보 조회 완료'
            }
            
        elif action == 'check_ready':
            missing_info = checkout_state.get_missing_info()
            if missing_info:
                result = {
                    'success': False,
                    'message': f'다음 정보가 누락되었습니다: {", ".join(missing_info)}',
                    'missing_info': missing_info
                }
            else:
                result = {
                    'success': True,
                    'message': '주문 준비 완료'
                }
                
        else:
            return {
                'success': False,
                'message': f'지원하지 않는 작업입니다: {action}',
                'checkout': checkout_state.get_checkout_summary()
            }
        
        # 결과에 체크아웃 상태 추가
        result['checkout'] = checkout_state.get_checkout_summary()
        return result
        
    except ValueError as e:
        return {
            'success': False,
            'message': str(e),
            'checkout': {
                'session_id': session_id, 
                'cart_items': [], 
                'ready_for_order': False,
                'missing_info': ['장바구니가 비어있음']
            }
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'결제 진행 중 오류가 발생했습니다: {str(e)}',
            'checkout': {
                'session_id': session_id, 
                'cart_items': [], 
                'ready_for_order': False,
                'error': str(e)
            }
        }
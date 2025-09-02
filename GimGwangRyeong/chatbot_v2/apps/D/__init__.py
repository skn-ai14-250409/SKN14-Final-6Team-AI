"""
담당자 D - 카트 및 결제 모듈
- cart_manage: 장바구니 관리 (멱등성 보장)
- checkout: 결제 정보 수집  
- order_process: 주문 확정/취소 처리

사용 예시:
1. 장바구니 관리
   cart_manage(session_id, 'add', product_id=1, quantity=2)
   cart_manage(session_id, 'update', product_id=1, quantity=3)
   cart_manage(session_id, 'remove', product_id=1)
   cart_manage(session_id, 'get')

2. 결제 진행
   checkout(session_id, 'set_delivery', address='서울시...', recipient_name='홍길동', recipient_phone='010-1234-5678')
   checkout(session_id, 'set_time', delivery_time='오전 (09:00-12:00)')
   checkout(session_id, 'set_payment', payment_method='신용카드')
   checkout(session_id, 'check_ready')

3. 주문 처리
   order_process(session_id, 'confirm')
   order_process(session_id, 'cancel', reason='변심')
   order_process(session_id, 'status', order_id='ORD202509...')
"""

from .cart_service import cart_manage
from .checkout_service import checkout
from .order_service import order_process

__all__ = ['cart_manage', 'checkout', 'order_process']
"""
API 뷰
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.utils import timezone
from apps.chat.models import ChatSession, ChatMessage
import uuid
import sys
import os

# CS 모듈 import
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from cs_module import cs_intake, faq_policy_rag
from graph_interfaces import ChatState


class HealthCheckView(APIView):
    """헬스 체크 API"""
    
    def get(self, request):
        return Response({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0'
        })


class ChatAPIView(APIView):
    """챗봇 대화 API (기본 구현)"""
    
    def post(self, request):
        try:
            # 일반 JSON 요청과 FormData 요청 모두 처리
            if hasattr(request, 'FILES') and 'image' in request.FILES:
                # 이미지가 포함된 FormData 요청
                message = request.POST.get('message', '').strip()
                user_id = request.POST.get('user_id', f'user_{uuid.uuid4().hex[:8]}')
                session_id = request.POST.get('session_id')
                uploaded_image = request.FILES['image']
            else:
                # 일반 JSON 요청
                message = request.data.get('message', '').strip()
                user_id = request.data.get('user_id', f'user_{uuid.uuid4().hex[:8]}')
                session_id = request.data.get('session_id')
                uploaded_image = None
            
            if not message:
                return Response({
                    'error': 'Message is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 세션 가져오기 또는 생성
            if session_id:
                try:
                    session = ChatSession.objects.get(session_id=session_id)
                except ChatSession.DoesNotExist:
                    session = ChatSession.objects.create(
                        user_identifier=user_id,
                        status='active'
                    )
            else:
                session = ChatSession.objects.create(
                    user_identifier=user_id,
                    status='active'
                )
            
            # 사용자 메시지 저장
            user_message = ChatMessage.objects.create(
                session=session,
                role='user',
                content=message
            )
            
            # CS 모듈 연동 (실제 챗봇 구현)
            bot_response, metadata = self.process_with_cs_module(message, user_id, str(session.session_id), uploaded_image)
            
            # 봇 응답 저장
            bot_message = ChatMessage.objects.create(
                session=session,
                role='bot',
                content=bot_response,
                metadata=metadata
            )
            
            # 세션 업데이트
            session.updated_at = timezone.now()
            session.save()
            
            return Response({
                'response': bot_response,
                'session_id': str(session.session_id),
                'user_id': user_id,
                'artifacts': metadata.get('artifacts', []),
                'current_step': metadata.get('current_step', 'unknown'),
                'metadata': {
                    'message_count': session.messages.count(),
                    'session_duration': str(timezone.now() - session.created_at),
                    **metadata.get('extra_metadata', {})
                }
            })
            
        except Exception as e:
            print(f"Chat API error: {e}")
            return Response({
                'error': f'Internal server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def process_with_cs_module(self, message, user_id, session_id, uploaded_image=None):
        """CS 모듈을 사용한 메시지 처리 (이미지 지원)"""
        try:
            # ChatState 생성
            state = ChatState()
            state.query = message
            state.user_id = user_id
            state.session_id = session_id
            state.turn_id = 1  # 간소화
            
            # 이미지 처리
            if uploaded_image:
                # 임시로 이미지를 저장하고 파일 경로를 첨부
                import tempfile
                import os
                
                # 임시 파일로 저장
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_image.name)[1]) as tmp_file:
                    for chunk in uploaded_image.chunks():
                        tmp_file.write(chunk)
                    temp_image_path = tmp_file.name
                
                state.attachments = [temp_image_path]
                print(f"이미지 업로드됨: {uploaded_image.name} -> {temp_image_path}")
            
            # LLM 기반 라우팅 시뮬레이션
            is_cs_query = self._is_cs_related_query(message, uploaded_image)
            
            if is_cs_query:
                # CS 처리
                cs_result = cs_intake(state)
                
                if cs_result['cs']['next_action'] == 'auto_resolve':
                    # 자동 해결
                    auto_response = cs_result['cs']['auto_response']
                    response_text = auto_response['text']
                    
                    metadata = {
                        'current_step': 'auto_resolve',
                        'cs_result': 'auto_resolved',
                        'ticket_id': cs_result['cs']['ticket']['ticket_id'],
                        'resolution_type': auto_response['resolution_type'],
                        'artifacts': [f"티켓번호: {cs_result['cs']['ticket']['ticket_id']}"]
                    }
                    
                elif cs_result['cs']['next_action'] == 'manual_review':
                    # FAQ RAG 처리
                    state.cs = cs_result['cs']
                    rag_result = faq_policy_rag(state)
                    
                    response_text = rag_result['cs']['answer']['text']
                    
                    metadata = {
                        'current_step': 'faq_answered',
                        'cs_result': 'faq_provided',
                        'ticket_id': cs_result['cs']['ticket']['ticket_id'],
                        'confidence': rag_result['cs']['answer']['confidence'],
                        'citations': rag_result['cs']['answer']['citations'],
                        'artifacts': [f"티켓번호: {cs_result['cs']['ticket']['ticket_id']}"]
                    }
                else:
                    # 기본 CS 접수 완료
                    response_text = f"문의를 접수했습니다. 티켓번호: {cs_result['cs']['ticket']['ticket_id']}"
                    
                    metadata = {
                        'current_step': 'cs_ticket_created',
                        'cs_result': 'ticket_created',
                        'ticket_id': cs_result['cs']['ticket']['ticket_id'],
                        'artifacts': [f"티켓번호: {cs_result['cs']['ticket']['ticket_id']}"]
                    }
            else:
                # 일반 FAQ 처리
                rag_result = faq_policy_rag(state)
                response_text = rag_result['cs']['answer']['text']
                
                metadata = {
                    'current_step': 'faq_answered',
                    'cs_result': 'general_faq',
                    'confidence': rag_result['cs']['answer']['confidence'],
                    'citations': rag_result['cs']['answer']['citations'],
                    'artifacts': []
                }
            
            # 임시 파일 정리
            if uploaded_image and 'temp_image_path' in locals():
                try:
                    os.unlink(temp_image_path)
                except:
                    pass
            
            return response_text, metadata
            
        except Exception as e:
            print(f"CS Module processing error: {e}")
            
            # 임시 파일 정리 (에러 시에도)
            if uploaded_image and 'temp_image_path' in locals():
                try:
                    os.unlink(temp_image_path)
                except:
                    pass
                    
            # 에러 시 기본 응답
            return f"죄송합니다. 처리 중 오류가 발생했습니다: {str(e)}", {
                'current_step': 'error',
                'cs_result': 'error',
                'artifacts': []
            }
    
    def _is_cs_related_query(self, message: str, uploaded_image=None) -> bool:
        """
        LLM 기반 CS 관련 질의 판단 (라우팅)
        실제로는 router_route 함수에 해당
        """
        # 이미지가 있으면 CS 관련일 가능성이 높음
        if uploaded_image:
            return True
        
        message_lower = message.lower()
        
        # CS 관련 패턴들 (LLM 라우팅 시뮬레이션)
        cs_patterns = [
            # 직접적인 CS 키워드
            ['배송', '문의', '도움', '문제', '불만'],
            ['환불', '반품', '교환', '취소', '돌려'],
            ['불량', '상함', '썩', '품질', '이상', '손상'],
            ['늦', '지연', '안옴', '안와'],
            ['잘못', '다른', '오류', '실수'],
            
            # 감정적 표현
            ['화나', '짜증', '실망', '속상'],
            ['급해', '빨리', '언제', '시간'],
            
            # 요청/명령 표현
            ['해주세요', '도와주세요', '처리', '확인'],
            ['어떻게', '왜', '방법', '절차']
        ]
        
        # 비CS 패턴들 (상품 검색, 레시피 등)
        non_cs_patterns = [
            ['추천', '찾아', '보여', '검색'],
            ['레시피', '요리', '만들', '조리'],
            ['가격', '얼마', '비교', '저렴'],
            ['영양', '칼로리', '건강', '다이어트'],
            ['안녕', '처음', '시작', '도움말']
        ]
        
        # CS 패턴 매칭
        cs_score = 0
        for pattern_group in cs_patterns:
            if any(keyword in message_lower for keyword in pattern_group):
                cs_score += 1
        
        # 비CS 패턴 매칭
        non_cs_score = 0
        for pattern_group in non_cs_patterns:
            if any(keyword in message_lower for keyword in pattern_group):
                non_cs_score += 1
        
        # CS 점수가 더 높거나, 강한 CS 키워드가 있으면 CS로 라우팅
        strong_cs_keywords = ['불량', '환불', '반품', '교환', '문의', '문제', '배송', '지연']
        has_strong_cs = any(keyword in message_lower for keyword in strong_cs_keywords)
        
        return cs_score > non_cs_score or has_strong_cs


class SessionAPIView(APIView):
    """세션 관련 API"""
    
    def get(self, request, session_id):
        """세션 정보 조회"""
        try:
            session = ChatSession.objects.get(session_id=session_id)
            return Response({
                'session_id': str(session.session_id),
                'user_id': session.user_identifier,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'message_count': session.messages.count(),
                'status': session.status
            })
        except ChatSession.DoesNotExist:
            return Response({
                'error': 'Session not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def delete(self, request, session_id):
        """세션 삭제"""
        try:
            session = ChatSession.objects.get(session_id=session_id)
            session.delete()
            return Response({'message': 'Session deleted successfully'})
        except ChatSession.DoesNotExist:
            return Response({
                'error': 'Session not found'
            }, status=status.HTTP_404_NOT_FOUND)


class StatsAPIView(APIView):
    """시스템 통계 API"""
    
    def get(self, request):
        total_sessions = ChatSession.objects.count()
        active_sessions = ChatSession.objects.filter(status='active').count()
        total_messages = ChatMessage.objects.count()
        
        return Response({
            'total_sessions': total_sessions,
            'active_sessions': active_sessions,
            'completed_sessions': total_sessions - active_sessions,
            'total_messages': total_messages,
            'avg_messages_per_session': total_messages / total_sessions if total_sessions > 0 else 0
        })
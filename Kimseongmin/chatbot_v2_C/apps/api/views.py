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
            message = request.data.get('message', '').strip()
            user_id = request.data.get('user_id', f'user_{uuid.uuid4().hex[:8]}')
            session_id = request.data.get('session_id')
            
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
            
            # 기본 봇 응답 (워크플로우 구현 전)
            bot_response = f"안녕하세요! '{message}' 메시지를 받았습니다. 곧 더 똑똑한 챗봇으로 업그레이드될 예정입니다."
            
            # 봇 응답 저장
            bot_message = ChatMessage.objects.create(
                session=session,
                role='bot',
                content=bot_response,
                metadata={'current_step': 'basic_response'}
            )
            
            # 세션 업데이트
            session.updated_at = timezone.now()
            session.save()
            
            return Response({
                'response': bot_response,
                'session_id': str(session.session_id),
                'user_id': user_id,
                'artifacts': [],
                'current_step': 'basic_response',
                'metadata': {
                    'message_count': session.messages.count(),
                    'session_duration': str(timezone.now() - session.created_at)
                }
            })
            
        except Exception as e:
            print(f"Chat API error: {e}")
            return Response({
                'error': f'Internal server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
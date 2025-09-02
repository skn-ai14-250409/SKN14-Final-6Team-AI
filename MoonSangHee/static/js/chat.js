/**
 * 챗봇 클라이언트 JavaScript
 * 채팅 인터페이스 및 API 통신을 담당합니다.
 */

class ChatBot {
    constructor() {
        this.sessionId = null;
        this.userId = 'user_' + Math.random().toString(36).substr(2, 9);
        this.init();
    }

    init() {
        this.bindEvents();
        this.updateSessionInfo();
    }

    bindEvents() {
        // 채팅 폼 제출
        document.getElementById('chatForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });

        // 엔터키 처리
        document.getElementById('messageInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // 빠른 액션 버튼들
        document.querySelectorAll('.quick-action').forEach(btn => {
            btn.addEventListener('click', () => {
                const message = btn.dataset.message;
                document.getElementById('messageInput').value = message;
                this.sendMessage();
            });
        });

        // 채팅 초기화
        document.getElementById('clearChat').addEventListener('click', () => {
            this.clearChat();
        });

        // 음성 입력 (향후 구현)
        document.getElementById('voiceInput').addEventListener('click', () => {
            alert('음성 입력 기능은 곧 제공될 예정입니다! 🎤');
        });
    }

    async sendMessage() {
        const input = document.getElementById('messageInput');
        const message = input.value.trim();
        
        if (!message) return;

        // 사용자 메시지 추가
        this.addMessage(message, 'user');
        input.value = '';

        // 타이핑 인디케이터 표시
        this.showTyping();

        try {
            // API 호출
            const response = await fetch('/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    user_id: this.userId,
                    session_id: this.sessionId
                })
            });

            const data = await response.json();

            if (response.ok) {
                this.sessionId = data.session_id;
                this.addMessage(data.response, 'bot');
                this.updateSidebar(data);
                this.updateSessionInfo(data.metadata);
            } else {
                throw new Error(data.error || 'API 호출 실패');
            }

        } catch (error) {
            console.error('Error:', error);
            this.addMessage('죄송합니다. 일시적인 오류가 발생했습니다. 다시 시도해주세요.', 'bot', true);
        } finally {
            this.hideTyping();
        }
    }
    

    addMessage(content, sender, isError = false) {
        const messagesContainer = document.getElementById('messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message-animation mb-4';

        if (sender === 'user') {
            messageDiv.innerHTML = `
                <div class="flex items-start justify-end">
                    <div class="bg-green-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 max-w-md">
                        <p>${this.escapeHtml(content)}</p>
                        <span class="text-xs text-green-100 block mt-1">${new Date().toLocaleTimeString('ko-KR', {hour: '2-digit', minute:'2-digit'})}</span>
                    </div>
                    <div class="w-8 h-8 bg-green-600 rounded-full flex items-center justify-center ml-3 flex-shrink-0">
                        <i class="fas fa-user text-white text-sm"></i>
                    </div>
                </div>
            `;
        } else {
            const bgColor = isError ? 'bg-red-50' : 'bg-green-50';
            const iconColor = isError ? 'text-red-600' : 'text-green-600';
            
            messageDiv.innerHTML = `
                <div class="flex items-start">
                    <div class="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0">
                        <i class="fas fa-robot ${iconColor} text-sm"></i>
                    </div>
                    <div class="${bgColor} rounded-2xl rounded-tl-sm px-4 py-3 max-w-md">
                        <div>${this.formatBotMessage(content)}</div>
                        <span class="text-xs text-gray-500 block mt-1">${new Date().toLocaleTimeString('ko-KR', {hour: '2-digit', minute:'2-digit'})}</span>
                    </div>
                </div>
            `;
        }

        messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatBotMessage(content) {
        // 간단한 마크다운 스타일 적용
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>')
            .replace(/📋|🎉|🚚|💰|✅|🥬|🍎|✨|🛒|🔍|🌱|🥗/g, '<span class="text-lg">$&</span>');
    }

    updateSidebar(data) {
        // 상품 정보 업데이트 (모의)
        if (data.current_step && data.current_step.includes('products_found')) {
            this.showProductsSection();
        }

        // 장바구니 업데이트 (모의)
        if (data.current_step && data.current_step.includes('cart_updated')) {
            this.showCartSection();
        }

        // 주문 정보 업데이트 (모의)
        if (data.artifacts && data.artifacts.some(a => a.type === 'receipt')) {
            this.showOrderSection(data.artifacts.find(a => a.type === 'receipt'));
        }
    }

    showProductsSection() {
        const section = document.getElementById('productsSection');
        const productsList = document.getElementById('productsList');
        
        // 모의 상품 데이터
        const mockProducts = [
            { name: '유기농 사과', price: '6,000원', origin: '경북 안동', stock: '충분' },
            { name: '친환경 바나나', price: '4,000원', origin: '필리핀', stock: '5개 남음' }
        ];

        productsList.innerHTML = mockProducts.map(product => `
            <div class="product-card bg-white rounded-lg p-3 border cursor-pointer">
                <div class="flex justify-between items-start mb-2">
                    <h4 class="font-medium text-gray-800">${product.name}</h4>
                    <span class="text-green-600 font-bold">${product.price}</span>
                </div>
                <p class="text-sm text-gray-600">원산지: ${product.origin}</p>
                <p class="text-xs text-blue-600 mt-1">재고: ${product.stock}</p>
                <button class="mt-2 w-full bg-green-100 text-green-800 py-1 px-2 rounded text-sm hover:bg-green-200 transition">
                    장바구니 담기
                </button>
            </div>
        `).join('');

        section.classList.remove('hidden');
    }

    showCartSection() {
        const section = document.getElementById('cartSection');
        const cartCount = document.getElementById('cartCount');
        const totalAmount = document.getElementById('totalAmount');
        
        // 모의 장바구니 업데이트
        cartCount.textContent = '2';
        totalAmount.textContent = '10,000원';
        
        section.classList.remove('hidden');
    }

    showOrderSection(receiptData) {
        const section = document.getElementById('orderSection');
        const orderInfo = document.getElementById('orderInfo');
        
        orderInfo.innerHTML = `
            <div class="space-y-2">
                <div class="flex justify-between">
                    <span class="text-sm text-gray-600">주문번호:</span>
                    <span class="text-sm font-medium">${receiptData.data.order_id || 'ORD_12345'}</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-sm text-gray-600">총 금액:</span>
                    <span class="text-sm font-medium text-green-600">${receiptData.data.total_amount || '10,000'}원</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-sm text-gray-600">주문일:</span>
                    <span class="text-sm font-medium">${new Date().toLocaleDateString('ko-KR')}</span>
                </div>
            </div>
        `;
        
        section.classList.remove('hidden');
    }

    showTyping() {
        document.getElementById('typingIndicator').classList.remove('hidden');
        this.scrollToBottom();
    }

    hideTyping() {
        document.getElementById('typingIndicator').classList.add('hidden');
    }

    scrollToBottom() {
        const container = document.getElementById('chatContainer');
        container.scrollTop = container.scrollHeight;
    }

    updateSessionInfo(metadata) {
        const sessionInfo = document.getElementById('sessionInfo');
        if (metadata && metadata.message_count) {
            sessionInfo.textContent = `${metadata.message_count}개 메시지`;
        } else {
            sessionInfo.textContent = '새로운 세션';
        }
    }

    clearChat() {
        if (confirm('채팅을 초기화하시겠습니까?')) {
            document.getElementById('messages').innerHTML = '';
            this.sessionId = null;
            this.updateSessionInfo();
            
            // 사이드바 초기화
            document.getElementById('productsSection').classList.add('hidden');
            document.getElementById('cartSection').classList.add('hidden');
            document.getElementById('orderSection').classList.add('hidden');
            document.getElementById('recipesSection').classList.add('hidden');
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// DOM 로드 완료 후 초기화
document.addEventListener('DOMContentLoaded', () => {
    // 챗봇 인스턴스 생성
    const chatBot = new ChatBot();
    
    // 메시지 입력 필드에 포커스
    document.getElementById('messageInput').focus();
});
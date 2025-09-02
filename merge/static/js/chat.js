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
            const response = await fetch('/api/chat', {
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
                throw new Error(data.detail || 'API 호출 실패');
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
        messageDiv.className = 'mb-4 message-animation';

        if (sender === 'user') {
            messageDiv.innerHTML = `
                <div class="flex items-end justify-end">
                    <div class="message-bubble-user mr-2">
                        ${this.escapeHtml(content)}
                    </div>
                    <div class="w-8 h-8 bg-green-600 rounded-full flex items-center justify-center flex-shrink-0">
                        <i class="fas fa-user text-white text-sm"></i>
                    </div>
                </div>
            `;
        } else {
            const errorClass = isError ? 'error' : '';
            messageDiv.innerHTML = `
                <div class="flex items-start">
                    <div class="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0">
                        <i class="fas fa-robot text-green-600 text-sm"></i>
                    </div>
                    <div class="message-bubble-bot ${errorClass}">
                        ${this.formatBotMessage(content)}
                    </div>
                </div>
            `;
        }

        messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatBotMessage(content) {
        // URL 링크 포맷팅
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        content = content.replace(urlRegex, '<a href="$1" target="_blank" class="text-blue-600 hover:underline">$1</a>');
        
        // 줄바꿈 처리
        content = content.replace(/\n/g, '<br>');
        
        return content;
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

    updateSidebar(data) {
        // 상품 목록 업데이트
        if (data.search && data.search.candidates) {
            this.updateProductsList(data.search.candidates);
        }

        // 레시피 정보 업데이트
        if (data.recipe) {
            this.updateRecipesList(data.recipe);
        }

        // 장바구니 업데이트
        if (data.cart) {
            this.updateCart(data.cart);
        }

        // 주문 정보 업데이트
        if (data.order) {
            this.updateOrderInfo(data.order);
        }
    }

    updateProductsList(products) {
        const productsList = document.getElementById('productsList');
        const productsSection = document.getElementById('productsSection');
        
        if (!products || products.length === 0) {
            productsSection.classList.add('hidden');
            return;
        }

        productsSection.classList.remove('hidden');
        productsList.innerHTML = '';

        products.slice(0, 5).forEach(product => {
            const productCard = document.createElement('div');
            productCard.className = 'product-card bg-white rounded-lg p-3 border hover:shadow-md transition cursor-pointer';
            productCard.innerHTML = `
                <div class="flex items-center justify-between">
                    <div class="flex-1">
                        <h4 class="font-medium text-sm text-gray-800">${this.escapeHtml(product.product || product.name)}</h4>
                        <p class="text-xs text-gray-500 mt-1">${this.escapeHtml(product.origin || '원산지 정보 없음')}</p>
                        <p class="text-green-600 font-bold text-sm mt-1">${this.formatPrice(product.price)}원</p>
                    </div>
                    <button class="add-to-cart bg-green-100 text-green-600 px-2 py-1 rounded text-xs hover:bg-green-200" 
                            data-product='${JSON.stringify(product)}'>
                        담기
                    </button>
                </div>
            `;
            
            // 장바구니 담기 이벤트
            productCard.querySelector('.add-to-cart').addEventListener('click', (e) => {
                e.stopPropagation();
                this.addToCartFromSidebar(product);
            });
            
            productsList.appendChild(productCard);
        });
    }

    updateRecipesList(recipe) {
        const recipesList = document.getElementById('recipesList');
        const recipesSection = document.getElementById('recipesSection');
        
        if (!recipe) {
            recipesSection.classList.add('hidden');
            return;
        }

        recipesSection.classList.remove('hidden');
        recipesList.innerHTML = `
            <div class="recipe-card rounded-lg p-3 text-sm">
                <h4 class="font-semibold text-gray-800 mb-2">${this.escapeHtml(recipe.name || '레시피')}</h4>
                <p class="text-gray-600 mb-2">${this.escapeHtml(recipe.description || '')}</p>
                ${recipe.url ? `<a href="${recipe.url}" target="_blank" class="text-blue-600 text-xs hover:underline">전체 레시피 보기</a>` : ''}
            </div>
        `;
    }

    updateCart(cart) {
        const cartItems = document.getElementById('cartItems');
        const cartSection = document.getElementById('cartSection');
        const cartCount = document.getElementById('cartCount');
        const totalAmount = document.getElementById('totalAmount');

        if (!cart || !cart.items || cart.items.length === 0) {
            cartSection.classList.add('hidden');
            return;
        }

        cartSection.classList.remove('hidden');
        cartCount.textContent = cart.items.length;
        cartItems.innerHTML = '';

        cart.items.forEach((item, index) => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'flex items-center justify-between bg-white rounded p-2 text-sm';
            itemDiv.innerHTML = `
                <div class="flex-1">
                    <span class="font-medium">${this.escapeHtml(item.name)}</span>
                    <div class="text-xs text-gray-500">${item.quantity}개 × ${this.formatPrice(item.price)}원</div>
                </div>
                <button class="remove-item text-red-500 hover:text-red-700 text-xs" data-index="${index}">
                    <i class="fas fa-times"></i>
                </button>
            `;
            
            // 상품 제거 이벤트
            itemDiv.querySelector('.remove-item').addEventListener('click', () => {
                this.removeFromCart(index);
            });
            
            cartItems.appendChild(itemDiv);
        });

        totalAmount.textContent = this.formatPrice(cart.total) + '원';
    }

    updateOrderInfo(order) {
        const orderInfo = document.getElementById('orderInfo');
        const orderSection = document.getElementById('orderSection');
        
        if (!order) {
            orderSection.classList.add('hidden');
            return;
        }

        orderSection.classList.remove('hidden');
        orderInfo.innerHTML = `
            <div class="text-sm">
                <p><strong>주문번호:</strong> ${order.order_code || 'N/A'}</p>
                <p><strong>총 금액:</strong> ${this.formatPrice(order.total_price)}원</p>
                <p><strong>주문 상태:</strong> <span class="text-blue-600">${order.status || '대기중'}</span></p>
            </div>
        `;
    }

    addToCartFromSidebar(product) {
        // 실제로는 서버에 장바구니 추가 API를 호출해야 함
        const message = `${product.product || product.name} 장바구니에 담아주세요`;
        document.getElementById('messageInput').value = message;
        this.sendMessage();
    }

    removeFromCart(index) {
        // 실제로는 서버에 장바구니 제거 API를 호출해야 함
        const message = `장바구니에서 ${index + 1}번째 상품을 제거해주세요`;
        document.getElementById('messageInput').value = message;
        this.sendMessage();
    }

    updateSessionInfo(metadata) {
        const sessionInfo = document.getElementById('sessionInfo');
        if (metadata && metadata.session_id) {
            sessionInfo.textContent = `세션: ${metadata.session_id.slice(-8)}`;
        }
    }

    clearChat() {
        if (confirm('채팅 기록을 모두 지우시겠습니까?')) {
            document.getElementById('messages').innerHTML = '';
            this.sessionId = null;
            this.updateSessionInfo();
            
            // 사이드바도 초기화
            document.getElementById('productsSection').classList.add('hidden');
            document.getElementById('recipesSection').classList.add('hidden');
            document.getElementById('cartSection').classList.add('hidden');
            document.getElementById('orderSection').classList.add('hidden');
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatPrice(price) {
        if (typeof price === 'string') {
            price = parseFloat(price.replace(/[^\d]/g, ''));
        }
        return new Intl.NumberFormat('ko-KR').format(price);
    }
}

// 페이지 로드 시 챗봇 초기화
document.addEventListener('DOMContentLoaded', () => {
    new ChatBot();
});
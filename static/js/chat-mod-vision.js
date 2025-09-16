/**
 * chat-mod-vision.js — 비전 AI 기능을 위한 JavaScript 모듈
 * 책임:
 * - 이미지 업로드 및 처리 기능
 * - 비전 레시피 검색 UI 상호작용
 * - 이미지 미리보기 및 관리
 */

// 이미지 업로드 및 처리 관련 변수
let uploadedImageData = null;
let imagePreviewContainer = null;

/**
 * 비전 기능 초기화
 */
function initializeVisionFeatures() {
    console.log('Vision features initializing...');

    // 이미지 업로드 버튼 생성 및 추가
    createImageUploadButton();

    // 이미지 미리보기 컨테이너 생성
    createImagePreviewContainer();

    // 퀵 버튼에 이벤트 리스너 추가
    setupQuickButton();

    // 드래그 앤 드롭 기능 설정
    setupDragAndDrop();

    console.log('Vision features initialized successfully');
}

/**
 * 퀵 버튼 설정
 */
function setupQuickButton() {
    const quickButton = document.querySelector('#vision-quick-btn');
    if (quickButton) {
        // 기존 이벤트 리스너 제거
        quickButton.replaceWith(quickButton.cloneNode(true));
        const newButton = document.querySelector('#vision-quick-btn');

        newButton.onclick = function(e) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            console.log('Vision quick button clicked');
            triggerImageUpload();
            return false;
        };
        console.log('Vision quick button event listener added');
    } else {
        console.warn('Vision quick button not found - retrying in 1 second');
        // 재시도
        setTimeout(setupQuickButton, 1000);
    }
}

/**
 * 이미지 업로드 버튼 생성
 */
function createImageUploadButton() {
    const chatInputContainer = document.querySelector('.chat-input') ||
                              document.querySelector('#chatForm') ||
                              document.querySelector('form');

    if (!chatInputContainer) {
        console.warn('Chat input container not found');
        return;
    }

    // 기존 이미지 업로드 버튼이 있으면 제거
    const existingButton = document.querySelector('#vision-upload-btn');
    if (existingButton) {
        existingButton.remove();
    }

    // 이미지 업로드 버튼 생성
    const uploadButton = document.createElement('button');
    uploadButton.type = 'button';
    uploadButton.id = 'vision-upload-btn';
    uploadButton.innerHTML = '📷';
    uploadButton.title = '음식 사진 업로드하여 레시피 찾기';
    uploadButton.className = 'input-btn';
    uploadButton.style.cssText = `
        background: #f97316;
        color: white;
        border: none;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        cursor: pointer;
        font-size: 18px;
        transition: background-color 0.3s;
        margin-left: 8px;
    `;

    // 호버 효과
    uploadButton.addEventListener('mouseenter', () => {
        uploadButton.style.backgroundColor = '#ea580c';
    });

    uploadButton.addEventListener('mouseleave', () => {
        uploadButton.style.backgroundColor = '#f97316';
    });

    // 클릭 이벤트
    uploadButton.addEventListener('click', (e) => {
        e.preventDefault();
        triggerImageUpload();
    });

    // 숨겨진 파일 입력 생성
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.id = 'vision-file-input';
    fileInput.accept = 'image/*';
    fileInput.style.display = 'none';
    fileInput.addEventListener('change', handleImageUpload);

    // 전송 버튼 앞에 추가
    const sendButton = chatInputContainer.querySelector('button[type="submit"]') ||
                      chatInputContainer.querySelector('#send-btn');

    if (sendButton) {
        chatInputContainer.insertBefore(uploadButton, sendButton);
    } else {
        chatInputContainer.appendChild(uploadButton);
    }

    chatInputContainer.appendChild(fileInput);

    console.log('Vision upload button created successfully');
}

/**
 * 이미지 미리보기 컨테이너 생성
 */
function createImagePreviewContainer() {
    // 기존 컨테이너가 있으면 제거
    const existingContainer = document.querySelector('#image-preview-container');
    if (existingContainer) {
        existingContainer.remove();
    }

    imagePreviewContainer = document.createElement('div');
    imagePreviewContainer.id = 'image-preview-container';
    imagePreviewContainer.style.cssText = `
        display: none;
        margin: 10px 0;
        padding: 15px;
        border: 2px dashed #f97316;
        border-radius: 10px;
        background-color: #fef3c7;
        text-align: center;
        position: relative;
    `;

    // 채팅 입력 영역 위에 삽입
    const chatArea = document.querySelector('#chatArea') ||
                    document.querySelector('.chat-area') ||
                    document.querySelector('#chatForm')?.parentElement;

    if (chatArea) {
        const chatForm = chatArea.querySelector('#chatForm') || chatArea.querySelector('.chat-input');
        if (chatForm) {
            chatArea.insertBefore(imagePreviewContainer, chatForm);
        } else {
            chatArea.appendChild(imagePreviewContainer);
        }
    } else {
        document.body.appendChild(imagePreviewContainer);
    }

    console.log('Image preview container created');
}

/**
 * 이미지 업로드 트리거
 */
function triggerImageUpload() {
    console.log('triggerImageUpload called');

    // 항상 새로운 파일 입력 생성 (더 확실한 작동을 위해)
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';
    fileInput.style.position = 'absolute';
    fileInput.style.left = '-9999px';
    fileInput.style.top = '-9999px';
    fileInput.style.opacity = '0';

    fileInput.addEventListener('change', function(e) {
        console.log('File input change event triggered');
        handleImageUpload(e);
        // 사용 후 제거
        document.body.removeChild(fileInput);
    });

    document.body.appendChild(fileInput);
    console.log('Triggering file input click');

    // 약간의 지연을 주고 클릭
    setTimeout(() => {
        fileInput.click();
    }, 10);
}

/**
 * 이미지 업로드 처리
 */
function handleImageUpload(event) {
    console.log('handleImageUpload called', event);
    const file = event.target.files[0];
    if (!file) {
        console.warn('No file selected');
        return;
    }

    console.log('File selected:', file.name, file.type, file.size);

    // 파일 타입 검증
    if (!file.type.startsWith('image/')) {
        alert('이미지 파일만 업로드 가능합니다.');
        return;
    }

    // 파일 크기 검증 (10MB 제한)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
        alert('이미지 파일 크기는 10MB 이하여야 합니다.');
        return;
    }

    console.log('File validation passed, reading file...');

    // 파일을 base64로 변환
    const reader = new FileReader();
    reader.onload = function(e) {
        console.log('File read successfully');
        uploadedImageData = e.target.result;
        displayImagePreview(uploadedImageData, file.name);

        // 자동으로 레시피 검색 시작
        setTimeout(() => {
            console.log('Starting recipe search...');
            searchRecipeFromImage();
        }, 500);
    };
    reader.onerror = function() {
        console.error('File read error');
        alert('이미지 파일을 읽는 중 오류가 발생했습니다.');
    };
    reader.readAsDataURL(file);
}

/**
 * 이미지 미리보기 표시
 */
function displayImagePreview(imageData, fileName) {
    // 미리보기 컨테이너는 생성하지 않고 바로 레시피 검색 시작
    console.log('Image preview skipped, starting recipe search immediately');
}

/**
 * 이미지 미리보기 제거
 */
function removeImagePreview() {
    uploadedImageData = null;
    if (imagePreviewContainer) {
        imagePreviewContainer.style.display = 'none';
        imagePreviewContainer.innerHTML = '';
    }

    // 파일 입력 초기화
    const fileInput = document.querySelector('#vision-file-input');
    if (fileInput) {
        fileInput.value = '';
    }
}

/**
 * 이미지에서 레시피 검색
 */
async function searchRecipeFromImage() {
    if (!uploadedImageData) {
        alert('먼저 이미지를 업로드해주세요.');
        return;
    }

    try {
        // 1. 먼저 채팅창에 이미지 표시
        displayImageInChat(uploadedImageData);

        // 2. 먼저 기본 메시지로 사용자 메시지 표시
        let searchMessage = '이 이미지에 해당하는 레시피를 검색해줘';
        displayUserMessage(searchMessage);

        // 4. 로딩 상태 표시
        const loadingMessage = addLoadingMessage('이미지를 분석하고 레시피를 검색 중입니다...');

        // 5. base64 데이터를 Blob으로 변환
        const response = await fetch(uploadedImageData);
        const blob = await response.blob();

        // 6. FormData 생성
        const formData = new FormData();
        formData.append('image', blob, 'uploaded_image.jpg');
        formData.append('message', searchMessage);

        // 사용자 ID 가져오기 (기존 chatbot 인스턴스에서 가져오기)
        let userId = 'anonymous';

        // 1. 기존 chatbot 인스턴스에서 userId 가져오기
        const botInstance = window.chatbot || window._chatbot;
        if (botInstance && botInstance.userId) {
            userId = botInstance.userId;
            console.log('Got userId from chatbot instance:', userId);
        } else {
            // 2. localStorage에서 user_info 파싱
            try {
                const userInfo = localStorage.getItem('user_info');
                if (userInfo) {
                    const parsed = JSON.parse(userInfo);
                    userId = parsed.user_id || 'anonymous';
                    console.log('Got userId from localStorage:', userId);
                }
            } catch (e) {
                console.warn('Failed to parse user_info from localStorage:', e);
            }

            // 3. 폴백으로 다른 방법들 시도
            if (userId === 'anonymous') {
                const metaUserId = document.querySelector('meta[name="current-user-id"]')?.getAttribute('content');
                userId = metaUserId ||
                        window.CURRENT_USER_ID ||
                        localStorage.getItem('user_id') ||
                        sessionStorage.getItem('user_id') ||
                        'anonymous';
                console.log('Got userId from fallback methods:', userId);
            }
        }

        formData.append('user_id', userId);

        // 세션 ID 가져오기
        const sessionId = localStorage.getItem('session_id') ||
                         sessionStorage.getItem('session_id') ||
                         window.sessionId ||
                         '';
        formData.append('session_id', sessionId);

        // 7. 비전 API로 전송
        const apiResponse = await fetch('/api/chat/vision', {
            method: 'POST',
            body: formData
        });

        if (!apiResponse.ok) {
            throw new Error(`HTTP error! status: ${apiResponse.status}`);
        }

        const result = await apiResponse.json();
        console.log('API Response:', result);
        console.log('Recipe data:', result.recipe);
        console.log('Recipe results:', result.recipe?.results);
        console.log('Recipe results length:', result.recipe?.results?.length);

        // 8. 로딩 메시지 제거
        removeLoadingMessage(loadingMessage);

        // 9. 음식 이름 추출하여 사용자 메시지 업데이트
        let extractedFoodName = '음식';
        console.log('Extracting food name from result.rewrite:', result.rewrite);

        if (result.rewrite && result.rewrite.text && result.rewrite.text !== searchMessage) {
            extractedFoodName = result.rewrite.text.replace(' 레시피 검색', '').replace(' 레시피', '');
            console.log('Extracted food name:', extractedFoodName);

            if (extractedFoodName && extractedFoodName !== '이미지 레시피 검색') {
                updateLastUserMessage(`${extractedFoodName} 레시피를 검색해줘`);
                console.log('Updated user message with:', `${extractedFoodName} 레시피를 검색해줘`);
            }
        } else {
            console.warn('No valid rewrite data found or same as search message');
        }

        // 10. 레시피 결과 업데이트 (일반 채팅과 동일하게 처리)
        if (window.ChatRecipes && result.recipe) {
            console.log('Updating recipe list with:', result.recipe);
            // 기존 chatbot 인스턴스를 전달하여 재료 버튼이 올바르게 작동하도록 함
            const botInstance = window.chatbot || window._chatbot || null;
            ChatRecipes.updateRecipesList(botInstance, result.recipe);
        }

        // 11. 기본 응답 표시
        let responseText = result.response || '레시피 검색이 완료되었습니다.';

        // 레시피가 있으면 메시지 수정
        if (result.recipe?.results?.length > 0) {
            const recipeCount = result.recipe.results.length;
            if (extractedFoodName && extractedFoodName !== '음식') {
                responseText = `${extractedFoodName} 레시피를 ${recipeCount}개 찾았습니다.`;
            } else {
                responseText = `레시피를 ${recipeCount}개 찾았습니다.`;
            }
            console.log('Updated response text to:', responseText);
        }

        console.log('Final response text:', responseText);
        console.log('About to call displayBotResponse with:', responseText);

        // 강제로 봇 메시지 표시
        if (typeof addMessageToChat === 'function') {
            addMessageToChat('bot', responseText);
            console.log('Used addMessageToChat directly');
        } else {
            displayBotResponse(responseText);
            console.log('Used displayBotResponse fallback');
        }

    } catch (error) {
        console.error('Vision API 호출 실패:', error);
        removeLoadingMessage();
        displayBotResponse('이미지 분석 중 오류가 발생했습니다. 다시 시도해주세요.');
    }
}

/**
 * 채팅창에 이미지 표시 (기존 addImageMessage 활용)
 */
function displayImageInChat(imageData) {
    if (window.chatbot && typeof window.chatbot.addImageMessage === 'function') {
        window.chatbot.addImageMessage(imageData, 'user');
    } else {
        // 폴백: 직접 DOM 조작
        const chatContainer = getChatContainer();
        if (!chatContainer) return;

        const imageMessage = document.createElement('div');
        imageMessage.className = 'message user-message image-message';
        imageMessage.innerHTML = `
            <div class="image-container" style="max-width: 300px; margin: 10px 0;">
                <img src="${imageData}" alt="업로드된 음식 이미지"
                     style="width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            </div>
        `;

        chatContainer.appendChild(imageMessage);
        scrollToBottom();
    }
}

/**
 * 사용자 메시지 표시
 */
function displayUserMessage(message) {
    console.log('Displaying user message:', message);
    if (!message || message.trim() === '') {
        console.warn('Empty message, skipping display');
        return;
    }

    if (typeof addMessageToChat === 'function') {
        addMessageToChat('user', message);
    }
}

/**
 * 봇 응답 표시
 */
function displayBotResponse(message) {
    console.log('Displaying bot response:', message);
    if (!message || message.trim() === '') {
        console.warn('Empty bot response, using default message');
        message = '죄송합니다. 응답을 생성할 수 없습니다.';
    }

    if (typeof addMessageToChat === 'function') {
        addMessageToChat('bot', message);
    }
}

/**
 * 로딩 메시지 추가 (기존 showCustomLoading 활용)
 */
function addLoadingMessage(message) {
    if (window.chatbot && typeof window.chatbot.showCustomLoading === 'function') {
        window.chatbot.showCustomLoading(message);
        return { id: 'custom-loading' }; // 식별자 반환
    } else {
        // 폴백: 직접 DOM 조작
        const chatContainer = getChatContainer();
        if (!chatContainer) return null;

        const loadingMessage = document.createElement('div');
        loadingMessage.className = 'message bot-message loading-message';
        loadingMessage.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner" style="display: inline-block; width: 20px; height: 20px; border: 2px solid #f3f3f3; border-top: 2px solid #007bff; border-radius: 50%; animation: spin 1s linear infinite; margin-right: 10px;"></div>
                ${message}
            </div>
        `;

        chatContainer.appendChild(loadingMessage);
        scrollToBottom();
        return loadingMessage;
    }
}

/**
 * 로딩 메시지 제거 (기존 hideCustomLoading 활용)
 */
function removeLoadingMessage(loadingElement) {
    if (window.chatbot && typeof window.chatbot.hideCustomLoading === 'function') {
        window.chatbot.hideCustomLoading();
    } else {
        // 폴백: 직접 DOM 조작
        if (loadingElement && loadingElement.parentNode) {
            loadingElement.parentNode.removeChild(loadingElement);
        } else {
            const loadingMessages = document.querySelectorAll('.loading-message');
            loadingMessages.forEach(msg => msg.remove());
        }
    }
}

/**
 * 음식 이름 추출 (빠른 분석) - 사용하지 않음
 */
async function extractFoodNameFromImage(imageData) {
    // 현재 사용하지 않는 함수 - 단순화를 위해 null 반환
    console.log('extractFoodNameFromImage called but not used');
    return null;
}

/**
 * API 응답에서 음식 이름 추출
 */
function extractFoodNameFromResponse(response) {
    // 간단한 정규식으로 음식 이름 추출
    if (!response) return null;

    // "김치찌개", "불고기" 등의 패턴 찾기
    const patterns = [
        /^([가-힣]+(?:\s+[가-힣]+)?)/,  // 한글 음식명
        /([가-힣]+\s*[가-힣]*)/,       // 일반적인 한글 패턴
    ];

    for (const pattern of patterns) {
        const match = response.match(pattern);
        if (match && match[1]) {
            return match[1].trim();
        }
    }

    return null;
}

/**
 * 채팅 컨테이너 가져오기 (기존 방식 활용)
 */
function getChatContainer() {
    return document.querySelector('#messages') ||
           document.querySelector('.chat-messages') ||
           document.querySelector('#chat-container') ||
           document.querySelector('.message-container');
}

/**
 * 채팅 스크롤 아래로 (기존 scrollToBottom 활용)
 */
function scrollToBottom() {
    if (window.chatbot && typeof window.chatbot.scrollToBottom === 'function') {
        window.chatbot.scrollToBottom();
    } else {
        // 폴백: 직접 스크롤
        const chatContainer = getChatContainer();
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    }
}

/**
 * 마지막 사용자 메시지 업데이트 (기존 addMessage 구조 활용)
 */
function updateLastUserMessage(newMessage) {
    const chatContainer = getChatContainer();
    if (!chatContainer) return;

    // 마지막 사용자 메시지 찾기 (이미지 메시지는 제외)
    const userMessages = chatContainer.querySelectorAll('.message.user-message:not(.image-message)');
    if (userMessages.length > 0) {
        const lastUserMessage = userMessages[userMessages.length - 1];
        // 기존 message-bubble-user 구조 유지하면서 텍스트만 업데이트
        const bubbleElement = lastUserMessage.querySelector('.message-bubble-user');
        if (bubbleElement) {
            bubbleElement.textContent = newMessage;
        } else {
            // 폴백: 전체 메시지 업데이트
            lastUserMessage.innerHTML = newMessage;
        }
        console.log('Updated last user message to:', newMessage);
    }
}

/**
 * 드래그 앤 드롭 기능 설정
 */
function setupDragAndDrop() {
    const dropZone = document.body;

    // 드래그 오버 효과 방지
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // 드래그 오버 시 시각적 피드백
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        dropZone.style.backgroundColor = 'rgba(0, 123, 255, 0.1)';
    }

    function unhighlight(e) {
        dropZone.style.backgroundColor = '';
    }

    // 파일 드롭 처리
    dropZone.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length > 0) {
            const file = files[0];
            if (file.type.startsWith('image/')) {
                // 파일 입력에 설정하고 이벤트 트리거
                const fileInput = document.querySelector('#vision-file-input');
                if (fileInput) {
                    // FileList 객체 생성은 복잡하므로 직접 처리
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        uploadedImageData = e.target.result;
                        displayImagePreview(uploadedImageData, file.name);

                        // 자동으로 레시피 검색 시작
                        setTimeout(() => {
                            searchRecipeFromImage();
                        }, 500);
                    };
                    reader.readAsDataURL(file);
                }
            } else {
                alert('이미지 파일만 업로드 가능합니다.');
            }
        }
    }
}

/**
 * 메시지 전송 시 이미지 데이터 포함 처리
 */
function enhanceMessageSending() {
    // 기존 메시지 전송 함수를 확장
    const originalSendMessage = window.sendMessage || function() {};

    window.sendMessage = function(message) {
        // 이미지 데이터가 있으면 메시지에 포함
        if (window.currentImageData) {
            const enhancedMessage = {
                text: message,
                image: window.currentImageData,
                type: 'vision_recipe'
            };

            // 이미지 데이터 초기화
            window.currentImageData = null;
            removeImagePreview();

            // 서버로 전송 (실제 구현에 따라 조정 필요)
            return originalSendMessage(enhancedMessage);
        }

        return originalSendMessage(message);
    };
}

/**
 * 페이지 로드 시 비전 기능 초기화
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded - starting vision features initialization');

    // 즉시 초기화 시도
    initializeVisionFeatures();

    // 지연 초기화 (DOM이 완전히 로드되지 않았을 경우 대비)
    setTimeout(() => {
        console.log('Delayed initialization starting...');
        initializeVisionFeatures();
        enhanceMessageSending();
    }, 2000);
});

// 윈도우 로드 이벤트에도 초기화 추가 (모든 리소스 로드 후)
window.addEventListener('load', function() {
    console.log('Window loaded - initializing vision features');
    setTimeout(initializeVisionFeatures, 500);
});

// 이미지 데이터 접근을 위한 전역 함수
window.getUploadedImageData = function() {
    return uploadedImageData;
};

window.clearUploadedImageData = function() {
    uploadedImageData = null;
    removeImagePreview();
};

// 전역 함수로 수동 초기화 가능
window.initVisionFeatures = initializeVisionFeatures;
window.triggerImageUpload = triggerImageUpload;

console.log('chat-mod-vision.js loaded successfully');
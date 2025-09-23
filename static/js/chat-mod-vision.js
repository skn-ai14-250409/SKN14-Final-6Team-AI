/**
 * 채팅창에 메시지를 동적으로 추가하는 통합 함수
 * @param {string} sender 'user' 또는 'bot'
 * @param {string|object} content 메시지 내용 (문자열 또는 이미지 객체 {src: '...'})
 */
function addMessage(sender, content) {
    const messagesContainer = document.getElementById('messages');
    if (!messagesContainer) {
        console.error("채팅 메시지 컨테이너를 찾을 수 없습니다.");
        return;
    }

    const messageWrapper = document.createElement('div');
    messageWrapper.className = 'mb-4 message-animation';

    let messageHTML = '';

    if (sender === 'user') {

        messageHTML = `
            <div class="flex items-end justify-end">
                ${typeof content === 'string'
                    ? `<div class="message-bubble-user mr-2">${content}</div>`
                    : `<div class="message-bubble-user mr-2 p-2"><img src="${content.src}" alt="업로드 이미지" class="max-w-xs rounded-lg"></div>`
                }
                <div class="w-8 h-8 bg-green-600 rounded-full flex items-center justify-center flex-shrink-0">
                    <i class="fas fa-user text-white text-sm"></i>
                </div>
            </div>`;
    } else { 

        messageHTML = `
            <div class="flex items-start">
                <div class="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0">
                    <i class="fas fa-robot text-green-600 text-sm"></i>
                </div>
                <div class="message-bubble-bot">${content}</div>
            </div>`;
    }

    messageWrapper.innerHTML = messageHTML;
    messagesContainer.appendChild(messageWrapper);

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

let uploadedImageData = null;
let imagePreviewContainer = null;

async function searchRecipeFromImage() {
    if (!uploadedImageData) {
        alert('먼저 이미지를 업로드해주세요.');
        return;
    }

    try {

        addMessage('user', { src: uploadedImageData });

        const searchMessage = '이 이미지에 해당하는 음식의 레시피를 찾아줘';
        addMessage('user', searchMessage);

        const loadingMessage = addLoadingMessage('이미지를 분석하고 레시피를 검색 중입니다...');

        const response = await fetch(uploadedImageData);
        const blob = await response.blob();
        const formData = new FormData();
        formData.append('image', blob, 'uploaded_image.jpg');
        formData.append('message', searchMessage);

        let userId = 'anonymous';
        const botInstance = window.chatbot || window._chatbot;
        if (botInstance && botInstance.userId) {
            userId = botInstance.userId;
        } else {
            try {
                const userInfo = localStorage.getItem('user_info');
                if (userInfo) userId = JSON.parse(userInfo).user_id || 'anonymous';
            } catch (e) {}
        }
        formData.append('user_id', userId);
        const sessionId = localStorage.getItem(`chat_session_${userId}`) || '';
        formData.append('session_id', sessionId);


        const apiResponse = await fetch('/api/chat/vision', {
            method: 'POST',
            body: formData
        });

        if (!apiResponse.ok) {
            throw new Error(`HTTP error! status: ${apiResponse.status}`);
        }
        const result = await apiResponse.json(); 

        removeLoadingMessage(loadingMessage);

        let responseText;
        const recipeResults = result.recipe?.results || [];
        const recipeCount = recipeResults.length;
        const searchQuery = result.recipe?.search_query; 

        if (recipeCount > 0 && searchQuery) {

            const cleanQuery = searchQuery.replace(/'/g, '');
            responseText = `${cleanQuery} 레시피를 ${recipeCount}개 찾았습니다.`;
        } else {

            responseText = result.response || '관련 레시피를 찾지 못했습니다.';
        }
        addMessage('bot', responseText);

        if (window.ChatRecipes && result.recipe) {
            ChatRecipes.updateRecipesList(botInstance, result.recipe);
        }

    } catch (error) {
        console.error('Vision API 호출 실패:', error);
        removeLoadingMessage();
        addMessage('bot', '이미지 분석 중 오류가 발생했습니다. 다시 시도해주세요.');
    } finally {

        removeImagePreview();
    }
}

function initializeVisionFeatures() {
    console.log('Vision features initializing...');
    createImagePreviewContainer();
    setupQuickButton();
    setupDragAndDrop();
    console.log('Vision features initialized successfully');
}


function setupQuickButton() {
    const quickButton = document.querySelector('#vision-quick-btn');
    if (quickButton) {
        quickButton.replaceWith(quickButton.cloneNode(true));
        const newButton = document.querySelector('#vision-quick-btn');
        newButton.onclick = function(e) {
            e.preventDefault();
            triggerImageUpload();
            return false;
        };
    } else {
        setTimeout(setupQuickButton, 1000);
    }
}


function createImagePreviewContainer() {
    if (document.querySelector('#image-preview-container')) return;
    imagePreviewContainer = document.createElement('div');
    imagePreviewContainer.id = 'image-preview-container';
    imagePreviewContainer.style.display = 'none';
    const chatForm = document.querySelector('#chatForm');
    if (chatForm) chatForm.parentElement.insertBefore(imagePreviewContainer, chatForm);
}


function triggerImageUpload() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';
    fileInput.style.display = 'none';
    fileInput.addEventListener('change', (e) => {
        handleImageUpload(e);
        document.body.removeChild(fileInput);
    });
    document.body.appendChild(fileInput);
    fileInput.click();
}

function handleImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
        alert('이미지 파일만 업로드 가능합니다.');
        return;
    }
    if (file.size > 10 * 1024 * 1024) { 
        alert('이미지 파일 크기는 10MB 이하여야 합니다.');
        return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
        uploadedImageData = e.target.result;
        searchRecipeFromImage(); 
    };
    reader.onerror = () => alert('이미지를 읽는 중 오류가 발생했습니다.');
    reader.readAsDataURL(file);
}

function removeImagePreview() {
    uploadedImageData = null;
    if (imagePreviewContainer) {
        imagePreviewContainer.style.display = 'none';
        imagePreviewContainer.innerHTML = '';
    }
}

function setupDragAndDrop() {
    const dropZone = document.body;
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, e => {
            e.preventDefault();
            e.stopPropagation();
        }, false);
    });
    dropZone.addEventListener('drop', e => {
        const file = e.dataTransfer.files[0];
        if (file) {
            handleImageUpload({ target: { files: [file] } });
        }
    }, false);
}


function addLoadingMessage(message) {
    if (window.chatbot && typeof window.chatbot.showCustomLoading === 'function') {
        window.chatbot.showCustomLoading(message);
        return { id: 'custom-loading' };
    }
    return null;
}


function removeLoadingMessage(loadingElement) {
    if (window.chatbot && typeof window.chatbot.hideCustomLoading === 'function') {
        window.chatbot.hideCustomLoading();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    setTimeout(initializeVisionFeatures, 1000); 
});

window.triggerImageUpload = triggerImageUpload;
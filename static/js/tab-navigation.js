let currentTab = 'chatbot';

function switchTab(targetTab) {
    if (currentTab === targetTab) return;
    
    console.log(`탭 전환: ${currentTab} → ${targetTab}`);
    
    const currentContent = document.getElementById(`${currentTab}-content`);
    if (currentContent) {
        currentContent.classList.remove('active');
    }
    
    setTimeout(() => {
        const targetContent = document.getElementById(`${targetTab}-content`);
        if (targetContent) {
            targetContent.classList.add('active');
        }
    }, 150);
    
    const allTabs = document.querySelectorAll('.tab-btn');
    allTabs.forEach(tab => {
        tab.classList.remove('active');
    });
    
    const activeTab = document.querySelector(`[data-tab="${targetTab}"]`);
    if (activeTab) {
        activeTab.classList.add('active');
    }
    
    currentTab = targetTab;
    
    initializeTabContent(targetTab);
}

function initializeTabContent(tab) {
    console.log(`${tab} 탭 초기화`);
    
    switch(tab) {
        case 'chatbot':

            setTimeout(() => {
                initializeChatbotTab();
            }, 100);
            break;
        case 'mypage':
            initializeMypageTab();
            break;
    }
}

function initializeChatbotTab() {
    console.log('챗봇 탭 초기화 시작');
    
    const chatbotContent = document.getElementById('chatbot-content');
    if (!chatbotContent || !chatbotContent.classList.contains('active')) {
        console.log('챗봇 탭이 활성화되지 않음, 초기화 건너뜀');
        return;
    }
    
    initializeSidebars();
    
    setTimeout(() => {
        if (window.initializeTabChatBot) {
            console.log('TabChatBot 초기화 호출');
            window.initializeTabChatBot();
        } else {
            console.warn('initializeTabChatBot 함수를 찾을 수 없습니다');
        }
    }, 200);
    
    console.log('챗봇 탭 초기화 완료');
}

function initializeMypageTab() {
    console.log('마이페이지 탭 초기화');
}


function initializeKeyboardNavigation() {
    document.addEventListener('keydown', function(e) {

        if (e.altKey) {
            switch(e.key) {
                case '1':
                    e.preventDefault();
                    switchTab('chatbot');
                    break;
                case '2':
                    e.preventDefault();
                    switchTab('mypage');
                    break;
            }
        }
        
        if (e.ctrlKey && e.key === 'Tab') {
            e.preventDefault();
            const nextTab = currentTab === 'chatbot' ? 'mypage' : 'chatbot';
            switchTab(nextTab);
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('탭 네비게이션 시스템 초기화');
    
    const initialContent = document.getElementById('chatbot-content');
    if (initialContent) {
        initialContent.classList.add('active');
    }

    initializeKeyboardNavigation();
    
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tab = this.getAttribute('data-tab');
            if (tab) {
                switchTab(tab);
            }
        });
    });
    
    setTimeout(() => {
        const chatbotContent = document.getElementById('chatbot-content');
        if (chatbotContent && chatbotContent.classList.contains('active')) {
            console.log('페이지 로드 시 챗봇 탭 초기화');
            initializeChatbotTab();
        }
    }, 500);
});

function initializeSidebars() {
    console.log('사이드바 시스템 초기화');
    
    const leftRecipesBtn = document.getElementById('leftSidebarRecipes');
    const leftFavoritesBtn = document.getElementById('leftSidebarFavorites');
    
    console.log('좌측 사이드바 버튼 찾기:', leftRecipesBtn, leftFavoritesBtn);
    
    if (leftRecipesBtn && leftFavoritesBtn) {

        leftRecipesBtn.removeEventListener('click', handleLeftRecipesClick);
        leftFavoritesBtn.removeEventListener('click', handleLeftFavoritesClick);
        
        leftRecipesBtn.addEventListener('click', handleLeftRecipesClick);
        leftFavoritesBtn.addEventListener('click', handleLeftFavoritesClick);
        
        console.log('좌측 사이드바 이벤트 리스너 등록 완료');
    } else {
        console.error('좌측 사이드바 버튼을 찾을 수 없습니다');
    }
    
    const rightProductsBtn = document.getElementById('rightSidebarProducts');
    const rightCartBtn = document.getElementById('rightSidebarCart');
    
    console.log('우측 사이드바 버튼 찾기:', rightProductsBtn, rightCartBtn);
    
    if (rightProductsBtn && rightCartBtn) {
        rightProductsBtn.removeEventListener('click', handleRightProductsClick);
        rightCartBtn.removeEventListener('click', handleRightCartClick);
        
        rightProductsBtn.addEventListener('click', handleRightProductsClick);
        rightCartBtn.addEventListener('click', handleRightCartClick);
        
        console.log('우측 사이드바 이벤트 리스너 등록 완료');
    } else {
        console.error('우측 사이드바 버튼을 찾을 수 없습니다');
    }
}

function handleLeftRecipesClick() {
    console.log('레시피 버튼 클릭됨');
    switchLeftSidebar('recipes');
}

function handleLeftFavoritesClick() {
    console.log('즐겨찾기 버튼 클릭됨');
    switchLeftSidebar('favorites');
}

function handleRightProductsClick() {
    console.log('상품 버튼 클릭됨');
    switchRightSidebar('products');
}

function handleRightCartClick() {
    console.log('장바구니 버튼 클릭됨');
    switchRightSidebar('cart');
}

function switchLeftSidebar(section) {
    console.log(`좌측 사이드바 전환: ${section}`);
    
    const recipesBtn = document.getElementById('leftSidebarRecipes');
    const favoritesBtn = document.getElementById('leftSidebarFavorites');
    
    if (!recipesBtn || !favoritesBtn) {
        console.error('좌측 사이드바 버튼을 찾을 수 없습니다');
        return;
    }
    
    recipesBtn.classList.remove('active', 'bg-green-600', 'text-white');
    recipesBtn.classList.add('bg-gray-200', 'text-gray-800');
    
    favoritesBtn.classList.remove('active', 'bg-green-600', 'text-white');
    favoritesBtn.classList.add('bg-gray-200', 'text-gray-800');
    
    if (section === 'recipes') {
        recipesBtn.classList.add('active', 'bg-green-600', 'text-white');
        recipesBtn.classList.remove('bg-gray-200', 'text-gray-800');
    } else {
        favoritesBtn.classList.add('active', 'bg-green-600', 'text-white');
        favoritesBtn.classList.remove('bg-gray-200', 'text-gray-800');
    }
    
    const recipesContent = document.getElementById('leftSidebarRecipesContent');
    const favoritesContent = document.getElementById('leftSidebarFavoritesContent');
    
    if (!recipesContent || !favoritesContent) {
        console.error('좌측 사이드바 콘텐츠를 찾을 수 없습니다');
        return;
    }
    
    recipesContent.classList.remove('active');
    recipesContent.classList.add('hidden');
    
    favoritesContent.classList.remove('active');
    favoritesContent.classList.add('hidden');
    
    if (section === 'recipes') {
        recipesContent.classList.add('active');
        recipesContent.classList.remove('hidden');
    } else {
        favoritesContent.classList.add('active');
        favoritesContent.classList.remove('hidden');
    }
    
    console.log(`좌측 사이드바 전환 완료: ${section}`);
}

function switchRightSidebar(section) {
    console.log(`우측 사이드바 전환: ${section}`);
    
    const productsBtn = document.getElementById('rightSidebarProducts');
    const cartBtn = document.getElementById('rightSidebarCart');
    
    if (!productsBtn || !cartBtn) {
        console.error('우측 사이드바 버튼을 찾을 수 없습니다');
        return;
    }
    
    productsBtn.classList.remove('active', 'bg-green-600', 'text-white');
    productsBtn.classList.add('bg-gray-200', 'text-gray-800');
    
    cartBtn.classList.remove('active', 'bg-green-600', 'text-white');
    cartBtn.classList.add('bg-gray-200', 'text-gray-800');
    
    if (section === 'products') {
        productsBtn.classList.add('active', 'bg-green-600', 'text-white');
        productsBtn.classList.remove('bg-gray-200', 'text-gray-800');
    } else {
        cartBtn.classList.add('active', 'bg-green-600', 'text-white');
        cartBtn.classList.remove('bg-gray-200', 'text-gray-800');
    }
    
    const productsContent = document.getElementById('rightSidebarProductsContent');
    const cartContent = document.getElementById('rightSidebarCartContent');
    
    if (!productsContent || !cartContent) {
        console.error('우측 사이드바 콘텐츠를 찾을 수 없습니다');
        return;
    }
    
    productsContent.classList.remove('active');
    productsContent.classList.add('hidden');
    
    cartContent.classList.remove('active');
    cartContent.classList.add('hidden');
    
    if (section === 'products') {
        productsContent.classList.add('active');
        productsContent.classList.remove('hidden');
    } else {
        cartContent.classList.add('active');
        cartContent.classList.remove('hidden');
        
        updateCartDisplay();
    }
    
    console.log(`우측 사이드바 전환 완료: ${section}`);
}

function updateCartDisplay() {
    console.log('장바구니 표시 업데이트');
    
    try {

        const cartCountHeader = document.getElementById('cartCountHeader');
        const cartCount = document.getElementById('cartCount');
        
        console.log('장바구니 요소 찾기:', { cartCountHeader, cartCount });
        
        if (cartCountHeader && cartCount) {
            const count = cartCount.textContent || '0';
            cartCountHeader.textContent = count;
            
            console.log('장바구니 카운트 업데이트:', count);
            
            if (parseInt(count) > 0) {
                cartCountHeader.classList.remove('hidden');
            } else {
                cartCountHeader.classList.add('hidden');
            }
        } else {
            console.warn('장바구니 카운트 요소를 찾을 수 없습니다');
        }
        
        if (window.tabChatBot && typeof window.tabChatBot.loadCartState === 'function') {
            console.log('TabChatBot 장바구니 상태 로드');
            window.tabChatBot.loadCartState();
        }
        
    } catch (error) {
        console.error('장바구니 표시 업데이트 오류:', error);
    }
}

function forceSidebarReinitialization() {
    console.log('사이드바 강제 재초기화');
    setTimeout(() => {
        initializeSidebars();
    }, 100);
}

window.switchTab = switchTab;
window.switchLeftSidebar = switchLeftSidebar;
window.switchRightSidebar = switchRightSidebar;
window.updateCartDisplay = updateCartDisplay;
window.initializeSidebars = initializeSidebars;
window.forceSidebarReinitialization = forceSidebarReinitialization;
window.getCurrentTab = () => currentTab;

console.log('탭 네비게이션 시스템 로드 완료');
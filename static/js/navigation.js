let isTransitioning = false;

function navigateToPage(targetUrl) {
    if (isTransitioning) return;
    
    isTransitioning = true;
    
    const currentPage = getCurrentPageType();
    const targetPage = getPageTypeFromUrl(targetUrl);
    
    console.log(`페이지 전환 시작: ${currentPage} → ${targetPage}`);
    
    createTransitionOverlay(targetPage);
    
    document.body.classList.add('page-fade-out');
    
    setTimeout(() => {
        const overlay = document.querySelector('.slide-overlay');
        if (overlay) {
            overlay.classList.add('active');
        }
    }, 100);
    
    setTimeout(() => {
        window.location.href = targetUrl;
    }, 800); 
}

function getCurrentPageType() {
    const path = window.location.pathname;
    if (path === '/chat') return 'chatbot';
    if (path === '/mypage') return 'mypage';
    return 'unknown';
}

function getPageTypeFromUrl(url) {
    if (url.includes('/chat')) return 'chatbot';
    if (url.includes('/mypage')) return 'mypage';
    return 'unknown';
}

function createTransitionOverlay(targetPage) {

    const existingOverlay = document.querySelector('.page-transition');
    if (existingOverlay) {
        existingOverlay.remove();
    }
    
    const pageConfig = {
        chatbot: {
            icon: 'fas fa-robot',
            title: '챗봇으로 이동 중...',
            subtitle: '신선한 대화를 준비하고 있어요'
        },
        mypage: {
            icon: 'fas fa-user',
            title: '마이페이지로 이동 중...',
            subtitle: '개인 정보를 불러오고 있어요'
        }
    };
    
    const config = pageConfig[targetPage] || pageConfig.chatbot;
    
    const overlay = document.createElement('div');
    overlay.className = 'page-transition';
    overlay.innerHTML = `
        <div class="slide-overlay">
            <div class="transition-content">
                <div class="transition-icon">
                    <i class="${config.icon}"></i>
                </div>
                <div class="transition-text">${config.title}</div>
                <div class="transition-subtitle">${config.subtitle}</div>
            </div>
        </div>
    `;
    
    document.body.appendChild(overlay);
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('네비게이션 시스템 초기화');
    
    updateNavigationState();
    
    setTimeout(() => {
        document.body.classList.add('page-fade-in');
    }, 100);

    initializeNavigationListeners();
});

function updateNavigationState() {
    const currentPage = getCurrentPageType();
    const navButtons = document.querySelectorAll('.nav-btn');
    
    navButtons.forEach(btn => {
        btn.classList.remove('active');
        
        if ((currentPage === 'chatbot' && btn.id === 'navChatbot') ||
            (currentPage === 'mypage' && btn.id === 'navMypage')) {
            btn.classList.add('active');
        }
    });
}

function initializeNavigationListeners() {
    const chatbotBtn = document.getElementById('navChatbot');
    if (chatbotBtn) {
        chatbotBtn.addEventListener('click', () => {
            if (getCurrentPageType() !== 'chatbot') {
                navigateToPage('/chat');
            }
        });
    }
    
    const mypageBtn = document.getElementById('navMypage');
    if (mypageBtn) {
        mypageBtn.addEventListener('click', () => {
            if (getCurrentPageType() !== 'mypage') {
                navigateToPage('/mypage');
            }
        });
    }
    
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case '1':
                    e.preventDefault();
                    if (getCurrentPageType() !== 'chatbot') {
                        navigateToPage('/chat');
                    }
                    break;
                case '2':
                    e.preventDefault();
                    if (getCurrentPageType() !== 'mypage') {
                        navigateToPage('/mypage');
                    }
                    break;
            }
        }
    });
}

function cleanupTransition() {
    isTransitioning = false;
    const overlay = document.querySelector('.page-transition');
    if (overlay) {
        overlay.remove();
    }
    document.body.classList.remove('page-fade-out');
}

window.addEventListener('beforeunload', function() {
    if (!isTransitioning) {
        document.body.classList.add('page-fade-out');
    }

    try {

        if (navigator.sendBeacon) {
            navigator.sendBeacon('/auth/logout-beacon', JSON.stringify({}));
        } else {

            fetch('/auth/logout-beacon', {
                method: 'POST',
                keepalive: true,
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            }).catch(() => {

            });
        }
    } catch (error) {

        console.warn('브라우저 종료 시 로그아웃 처리 중 오류:', error);
    }
});

window.addEventListener('unload', function() {
    try {
        if (navigator.sendBeacon) {
            navigator.sendBeacon('/auth/logout-beacon', JSON.stringify({}));
        }
    } catch (error) {

    }
});

document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible') {
        cleanupTransition();
        updateNavigationState();
    }
});

window.navigateToPage = navigateToPage;

console.log('네비게이션 시스템 로드 완료');
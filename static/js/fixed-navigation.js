let currentPage = 'chatbot';

function switchToPage(targetPage) {
    if (currentPage === targetPage) return;
    
    console.log(`페이지 전환: ${currentPage} → ${targetPage}`);
    
    const slider = document.getElementById('pageSlider');
    const navButtons = document.querySelectorAll('.nav-tab');
    
    if (!slider) return;
    
    if (targetPage === 'chatbot') {
        slider.className = 'page-slider show-chatbot slide-transition';
    } else if (targetPage === 'mypage') {
        slider.className = 'page-slider show-mypage slide-transition';
    }
    
    navButtons.forEach(btn => {
        btn.classList.remove('active');
        if ((targetPage === 'chatbot' && btn.id === 'navChatbot') ||
            (targetPage === 'mypage' && btn.id === 'navMypage')) {
            btn.classList.add('active');
        }
    });
    
    currentPage = targetPage;
    
    if (targetPage === 'chatbot') {
        initializeChatbotPage();
    } else if (targetPage === 'mypage') {
        initializeMypagePage();
    }
}

function initializeChatbotPage() {
    console.log('챗봇 페이지 초기화');
    
    const chatContainer = document.querySelector('#chatbotPage .page-content-wrapper');
    if (chatContainer) {

    }
}


function initializeMypagePage() {
    console.log('마이페이지 초기화');
    
    const mypageContainer = document.querySelector('#mypagePage .page-content-wrapper');
    if (mypageContainer) {

    }
}

function initializeKeyboardNavigation() {
    document.addEventListener('keydown', function(e) {
       
        if (e.altKey) {
            switch(e.key) {
                case '1':
                    e.preventDefault();
                    switchToPage('chatbot');
                    break;
                case '2':
                    e.preventDefault();
                    switchToPage('mypage');
                    break;
            }
        }
        
        if (e.ctrlKey) {
            switch(e.key) {
                case 'ArrowLeft':
                    e.preventDefault();
                    if (currentPage === 'mypage') {
                        switchToPage('chatbot');
                    }
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    if (currentPage === 'chatbot') {
                        switchToPage('mypage');
                    }
                    break;
            }
        }
    });
}


document.addEventListener('DOMContentLoaded', function() {
    console.log('고정 네비게이션 시스템 초기화');
    
    const urlPath = window.location.pathname;
    if (urlPath.includes('/mypage')) {
        currentPage = 'mypage';
        switchToPage('mypage');
    } else {
        currentPage = 'chatbot';
        switchToPage('chatbot');
    }
    
    initializeKeyboardNavigation();
    
    window.addEventListener('popstate', function(e) {
        const urlPath = window.location.pathname;
        if (urlPath.includes('/mypage')) {
            switchToPage('mypage');
        } else if (urlPath.includes('/chat')) {
            switchToPage('chatbot');
        }
    });
});

function updateBrowserHistory(page) {
    const url = page === 'chatbot' ? '/chat' : '/mypage';
    const title = page === 'chatbot' ? 'Qook 챗봇' : 'Qook 마이페이지';
    
    if (window.location.pathname !== url) {
        window.history.pushState({ page }, title, url);
    }
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

const handleResize = debounce(() => {

    const slider = document.getElementById('pageSlider');
    if (slider) {

        slider.style.display = 'none';
        slider.offsetHeight; 
        slider.style.display = 'flex';
    }
}, 250);

window.addEventListener('resize', handleResize);

window.switchToPage = switchToPage;

window.getCurrentPage = () => currentPage;

console.log('고정 네비게이션 시스템 로드 완료');
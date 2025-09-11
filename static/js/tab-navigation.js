// 탭 네비게이션 시스템

// 현재 활성 탭
let currentTab = 'chatbot';

// 탭 전환 함수
function switchTab(targetTab) {
    if (currentTab === targetTab) return;
    
    console.log(`탭 전환: ${currentTab} → ${targetTab}`);
    
    // 현재 활성 콘텐츠 숨기기
    const currentContent = document.getElementById(`${currentTab}-content`);
    if (currentContent) {
        currentContent.classList.remove('active');
    }
    
    // 타겟 콘텐츠 보이기
    setTimeout(() => {
        const targetContent = document.getElementById(`${targetTab}-content`);
        if (targetContent) {
            targetContent.classList.add('active');
        }
    }, 150);
    
    // 탭 버튼 상태 업데이트
    const allTabs = document.querySelectorAll('.tab-btn');
    allTabs.forEach(tab => {
        tab.classList.remove('active');
    });
    
    const activeTab = document.querySelector(`[data-tab="${targetTab}"]`);
    if (activeTab) {
        activeTab.classList.add('active');
    }
    
    // 현재 탭 업데이트
    currentTab = targetTab;
    
    // 탭별 초기화
    initializeTabContent(targetTab);
}

// 탭별 콘텐츠 초기화
function initializeTabContent(tab) {
    console.log(`${tab} 탭 초기화`);
    
    switch(tab) {
        case 'chatbot':
            initializeChatbotTab();
            break;
        case 'mypage':
            initializeMypageTab();
            break;
    }
}

// 챗봇 탭 초기화
function initializeChatbotTab() {
    console.log('챗봇 탭 초기화');
    // 챗봇 관련 초기화 로직
    // 기존 chat.js의 초기화 함수들을 호출할 수 있음
}

// 마이페이지 탭 초기화
function initializeMypageTab() {
    console.log('마이페이지 탭 초기화');
    // 마이페이지 관련 초기화 로직
    // 기존 mypage.js의 초기화 함수들을 호출할 수 있음
}

// 키보드 네비게이션
function initializeKeyboardNavigation() {
    document.addEventListener('keydown', function(e) {
        // Alt + 숫자 키로 빠른 전환
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
        
        // Ctrl + Tab으로 탭 전환
        if (e.ctrlKey && e.key === 'Tab') {
            e.preventDefault();
            const nextTab = currentTab === 'chatbot' ? 'mypage' : 'chatbot';
            switchTab(nextTab);
        }
    });
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    console.log('탭 네비게이션 시스템 초기화');
    
    // 초기 탭 설정
    const initialContent = document.getElementById('chatbot-content');
    if (initialContent) {
        initialContent.classList.add('active');
    }
    
    // 키보드 네비게이션 초기화
    initializeKeyboardNavigation();
    
    // 탭 버튼 클릭 이벤트 등록
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tab = this.getAttribute('data-tab');
            if (tab) {
                switchTab(tab);
            }
        });
    });
});

// 전역 함수로 내보내기
window.switchTab = switchTab;

// 디버깅용
window.getCurrentTab = () => currentTab;

console.log('탭 네비게이션 시스템 로드 완료');
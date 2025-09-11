// 마이페이지 JavaScript 기능

// 현재 활성화된 메뉴를 추적
let currentActiveMenu = 'orders';

// DOM이 로드된 후 실행
document.addEventListener('DOMContentLoaded', function() {
    console.log('마이페이지가 로드되었습니다.');
    
    // 메뉴 항목들에 클릭 이벤트 추가
    initializeMenuEvents();
    
    // 사용자 정보 로드
    loadUserInfo();
    
    // 기본 메뉴 활성화 (주문내역을 기본으로)
    setActiveMenu('orders');
    showContent('orders');
});

// 메뉴 이벤트 초기화
function initializeMenuEvents() {
    // 모든 메뉴 항목에 클릭 효과 추가
    const menuItems = document.querySelectorAll('.menu-item');
    menuItems.forEach(item => {
        item.addEventListener('click', function() {
            // 클릭 효과
            this.style.transform = 'translateX(8px) scale(0.98)';
            setTimeout(() => {
                this.style.transform = 'translateX(4px)';
            }, 150);
        });
    });
}

// 메뉴 클릭 시 콘텐츠 전환
function showContent(contentType) {
    console.log(`메뉴 전환: ${contentType}`);
    
    // 모든 콘텐츠 섹션 숨기기
    const allSections = document.querySelectorAll('.content-section');
    allSections.forEach(section => {
        section.classList.add('hidden');
        section.classList.remove('active');
    });
    
    // 선택된 콘텐츠 보이기
    const targetSection = document.getElementById(`content-${contentType}`);
    if (targetSection) {
        targetSection.classList.remove('hidden');
        targetSection.classList.add('active');
        
        // 부드러운 애니메이션 효과
        targetSection.style.opacity = '0';
        targetSection.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            targetSection.style.transition = 'all 0.3s ease';
            targetSection.style.opacity = '1';
            targetSection.style.transform = 'translateY(0)';
        }, 50);
    }
    
    // 메뉴 활성화 상태 업데이트
    setActiveMenu(contentType);
    currentActiveMenu = contentType;
}

// 메뉴 활성화 상태 설정
function setActiveMenu(menuType) {
    // 모든 메뉴 아이템에서 활성화 상태 제거
    const menuItems = document.querySelectorAll('.menu-item');
    menuItems.forEach(item => {
        item.classList.remove('bg-green-600', 'bg-opacity-30');
        item.style.backgroundColor = '';
    });
    
    // 선택된 메뉴 아이템 활성화
    const activeMenuItem = document.querySelector(`[data-menu="${menuType}"]`);
    if (activeMenuItem) {
        activeMenuItem.style.backgroundColor = 'rgba(34, 197, 94, 0.3)';
        activeMenuItem.classList.add('bg-green-600', 'bg-opacity-30');
    }
}

// 회원정보 수정 버튼 클릭
function editProfile() {
    console.log('회원정보 수정 버튼이 클릭되었습니다.');
    showNotification('회원정보 수정 기능은 곧 추가될 예정입니다.', 'info');
    
    // 미래에 모달이나 다른 페이지로 이동하는 기능을 여기에 추가
    // 예: window.location.href = '/profile/edit';
}

// 사용자 정보 로드
function loadUserInfo() {
    // 현재는 하드코딩된 "홍길동"을 사용
    // 미래에 실제 사용자 정보를 API에서 가져오는 기능 추가
    
    console.log('사용자 정보를 로드합니다.');
    
    // 예시: API 호출
    /*
    fetch('/api/user/profile')
        .then(response => response.json())
        .then(data => {
            updateUserName(data.name);
        })
        .catch(error => {
            console.error('사용자 정보 로드 실패:', error);
        });
    */
}

// 사용자 이름 업데이트 (미래 사용)
function updateUserName(name) {
    const userNameElements = document.querySelectorAll('.user-name, .welcome-name');
    userNameElements.forEach(element => {
        element.textContent = `${name} 님`;
    });
}

// 알림 표시 함수
function showNotification(message, type = 'info') {
    // 기존 알림이 있으면 제거
    const existingNotification = document.querySelector('.notification');
    if (existingNotification) {
        existingNotification.remove();
    }
    
    // 새 알림 생성
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'info' ? '#10b981' : '#ef4444'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 1000;
        animation: slideIn 0.3s ease;
        max-width: 300px;
        font-weight: 500;
    `;
    
    // 애니메이션 스타일 추가
    if (!document.querySelector('#notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            @keyframes slideOut {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    notification.textContent = message;
    document.body.appendChild(notification);
    
    // 3초 후 자동 제거
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 300);
    }, 3000);
}

// 페이지 전환 효과 (부드러운 로딩)
function smoothPageTransition(url) {
    document.body.style.opacity = '0.5';
    setTimeout(() => {
        window.location.href = url;
    }, 150);
}

// 키보드 네비게이션 지원
document.addEventListener('keydown', function(event) {
    // ESC 키로 알림 닫기
    if (event.key === 'Escape') {
        const notification = document.querySelector('.notification');
        if (notification) {
            notification.remove();
        }
    }
});

// 마우스 오버 효과를 위한 추가 이벤트
document.addEventListener('DOMContentLoaded', function() {
    const menuItems = document.querySelectorAll('.menu-item');
    
    menuItems.forEach(item => {
        // 마우스 진입시
        item.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(8px)';
        });
        
        // 마우스 떠날 때
        item.addEventListener('mouseleave', function() {
            this.style.transform = 'translateX(0)';
        });
    });
});

console.log('마이페이지 JavaScript가 로드되었습니다.');
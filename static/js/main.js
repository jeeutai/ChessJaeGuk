document.addEventListener('DOMContentLoaded', function() {
    // 현재 페이지 URL을 기반으로 하단 메뉴 활성화
    highlightCurrentPage();
    
    // 메뉴 아이템 개수에 따른 클래스 추가
    adjustBottomNav();
    
    // 알림 토스트 설정
    setupToasts();
    
    // 로딩 인디케이터 설정
    setupLoadingIndicator();
    
    // 모달 닫을 때 폼 초기화
    resetFormsOnModalClose();
});

/**
 * 현재 페이지 URL에 해당하는 하단 메뉴 항목 활성화
 */
function highlightCurrentPage() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.bottom-nav .nav-link');
    
    navLinks.forEach(link => {
        const linkPath = link.getAttribute('href');
        
        // 링크 경로가 현재 경로와 일치하거나, 
        // 현재 경로가 링크 경로로 시작하면서(서브페이지) 링크 경로가 단순 루트가 아닌 경우
        if (
            linkPath === currentPath || 
            (currentPath.startsWith(linkPath) && linkPath !== '/' && linkPath !== '/home')
        ) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
        
        // 홈 링크는 특별 처리
        if ((currentPath === '/' || currentPath === '/home') && (linkPath === '/' || linkPath === '/home')) {
            link.classList.add('active');
        }
    });
}

/**
 * 하단 메뉴 아이템의 개수에 따라 스타일 조정
 */
function adjustBottomNav() {
    const bottomNav = document.querySelector('.bottom-nav');
    if (!bottomNav) return;
    
    const navItems = bottomNav.querySelectorAll('.nav-link');
    if (navItems.length >= 7) {
        bottomNav.classList.add('many-items');
    } else {
        bottomNav.classList.remove('many-items');
    }
}

/**
 * Bootstrap 토스트 설정
 */
function setupToasts() {
    var toastElList = [].slice.call(document.querySelectorAll('.toast'));
    var toastList = toastElList.map(function (toastEl) {
        return new bootstrap.Toast(toastEl, {
            autohide: true,
            delay: 5000
        });
    });
    
    // 모든 토스트 표시
    toastList.forEach(toast => toast.show());
}

/**
 * 로딩 인디케이터 설정
 */
function setupLoadingIndicator() {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (!loadingOverlay) return;
    
    // 폼 제출 시 로딩 인디케이터 표시
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function() {
            // 서버에 송금, 구매, 베팅 등 트랜잭션 요청을 보낼 때만 로딩 표시
            if (this.method.toLowerCase() === 'post' && !this.classList.contains('no-loading')) {
                loadingOverlay.style.display = 'flex';
            }
        });
    });
    
    // AJAX 요청 시 로딩 인디케이터 처리
    setupAjaxLoadingIndicator(loadingOverlay);
}

/**
 * AJAX 요청에 대한 로딩 인디케이터 설정
 */
function setupAjaxLoadingIndicator(loadingOverlay) {
    // XMLHttpRequest 래핑
    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function() {
        this.addEventListener('loadstart', function() {
            loadingOverlay.style.display = 'flex';
        });
        
        this.addEventListener('loadend', function() {
            loadingOverlay.style.display = 'none';
        });
        
        originalOpen.apply(this, arguments);
    };
    
    // fetch API 래핑 (필요한 경우)
    const originalFetch = window.fetch;
    window.fetch = function() {
        loadingOverlay.style.display = 'flex';
        
        return originalFetch.apply(this, arguments)
            .finally(() => {
                loadingOverlay.style.display = 'none';
            });
    };
}

/**
 * 모달이 닫힐 때 폼 초기화
 */
function resetFormsOnModalClose() {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        modal.addEventListener('hidden.bs.modal', function() {
            const forms = this.querySelectorAll('form');
            forms.forEach(form => form.reset());
        });
    });
}

/**
 * 토스트 알림 표시
 * @param {string} message - 표시할 메시지
 * @param {string} type - 알림 유형 (success, error, warning, info 중 하나)
 */
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) return;
    
    // Bootstrap 클래스 매핑
    const typeClass = {
        'success': 'bg-success',
        'error': 'bg-danger',
        'warning': 'bg-warning text-dark',
        'info': 'bg-info text-dark'
    };
    
    // 아이콘 매핑
    const typeIcon = {
        'success': 'fas fa-check-circle',
        'error': 'fas fa-exclamation-circle',
        'warning': 'fas fa-exclamation-triangle',
        'info': 'fas fa-info-circle'
    };
    
    // 토스트 HTML 생성
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast ${typeClass[type] || 'bg-info text-dark'}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header">
                <i class="${typeIcon[type] || 'fas fa-info-circle'} me-2"></i>
                <strong class="me-auto">${type.charAt(0).toUpperCase() + type.slice(1)}</strong>
                <small>지금</small>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    // 토스트 생성 및 표시
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: 5000
    });
    
    toast.show();
    
    // 자동 제거
    toastElement.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}
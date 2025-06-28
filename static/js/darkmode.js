/**
 * 다크모드 관련 스크립트
 */

// DOM이 로드되면 테마 설정 초기화
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
});

/**
 * 테마 초기화 - 저장된 설정 또는 시스템 기본값 적용
 */
function initTheme() {
  // 저장된 테마 확인
  const savedTheme = localStorage.getItem('theme');
  const systemDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  
  // 저장된 테마가 있으면 해당 테마 적용, 없으면 시스템 설정 확인
  if (savedTheme) {
    setTheme(savedTheme);
  } else {
    // 시스템 테마가 다크모드이면 다크모드 적용
    if (systemDarkMode) {
      setTheme('dark');
    } else {
      setTheme('light');
    }
  }
  
  // 시스템 테마 변경 감지 (다크/라이트 모드)
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
      if (!localStorage.getItem('theme')) {
        setTheme(e.matches ? 'dark' : 'light');
      }
    });
  }
}

/**
 * 테마 토글 - 현재 테마와 반대로 변경
 */
function toggleTheme() {
  const currentTheme = document.body.getAttribute('data-theme') || 'light';
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  setTheme(newTheme);
  
  // 서버에 사용자 선호도 저장 (로그인 상태인 경우)
  if (document.querySelector('meta[name="user-logged-in"]')) {
    saveUserThemePreference(newTheme);
  }
}

/**
 * 특정 테마 적용
 * @param {string} theme - 'light' 또는 'dark'
 */
function setTheme(theme) {
  document.body.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  
  // 토글 스위치 상태 업데이트
  const themeSwitch = document.getElementById('theme-switch');
  if (themeSwitch) {
    themeSwitch.checked = theme === 'dark';
  }
  
  // 테마 아이콘 업데이트
  updateThemeIcon(theme);
}

/**
 * 테마 아이콘 업데이트
 * @param {string} theme - 현재 테마
 */
function updateThemeIcon(theme) {
  const themeIcon = document.getElementById('theme-icon');
  if (themeIcon) {
    if (theme === 'dark') {
      themeIcon.classList.remove('fa-sun');
      themeIcon.classList.add('fa-moon');
    } else {
      themeIcon.classList.remove('fa-moon');
      themeIcon.classList.add('fa-sun');
    }
  }
}

/**
 * 사용자 테마 선호도를 서버에 저장
 * @param {string} theme - 사용자가 선택한 테마
 */
function saveUserThemePreference(theme) {
  fetch('/save_user_preference', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      preference_type: 'theme',
      preference_value: theme
    })
  })
  .then(response => response.json())
  .then(data => {
    console.log('테마 선호도가 저장되었습니다:', data);
  })
  .catch(error => {
    console.error('테마 선호도 저장 중 오류 발생:', error);
  });
}
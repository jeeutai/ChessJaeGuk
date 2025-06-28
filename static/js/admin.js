
// 실시간 시스템 모니터링
function initializeMonitoring() {
    const statsUpdateInterval = 30000; // 30초마다 업데이트로 변경
    let monitoringEnabled = true;
    
    function updateStats() {
        if (!monitoringEnabled) return;
        
        fetch('/admin/stats')
            .then(response => response.json())
            .then(data => {
                const activeUsersElement = document.getElementById('active-users-count');
                const transactionElement = document.getElementById('transaction-count');
                const gameElement = document.getElementById('game-count');
                
                if (activeUsersElement) activeUsersElement.textContent = data.active_users;
                if (transactionElement) transactionElement.textContent = data.transactions;
                if (gameElement) gameElement.textContent = data.game_plays;
                
                // 차트 업데이트
                if(window.systemChart) {
                    window.systemChart.data.datasets[0].data = [
                        data.cpu_usage,
                        data.memory_usage,
                        data.disk_usage
                    ];
                    window.systemChart.update();
                }
            })
            .catch(error => {
                console.warn('Stats update failed:', error);
                monitoringEnabled = false; // 오류 발생시 모니터링 중지
            });
    }
    
    // 초기 차트 설정
    const chartElement = document.getElementById('systemChart');
    if (chartElement) {
        const ctx = chartElement.getContext('2d');
        window.systemChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['CPU', 'Memory', 'Disk'],
            datasets: [{
                label: 'System Resources',
                data: [0, 0, 0],
                backgroundColor: [
                    'rgba(255, 99, 132, 0.2)',
                    'rgba(54, 162, 235, 0.2)',
                    'rgba(255, 206, 86, 0.2)'
                ],
                borderColor: [
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
    }
    
    // 실시간 업데이트 시작
    setInterval(updateStats, statsUpdateInterval);
    updateStats(); // 초기 데이터 로드
}

// 데이터 수정 기능
function editData(fileId, rowId) {
    const row = document.querySelector(`#row-${rowId}`);
    const cells = row.querySelectorAll('td[contenteditable="true"]');
    
    const data = {};
    cells.forEach(cell => {
        const field = cell.getAttribute('data-field');
        data[field] = cell.textContent.trim();
    });
    
    fetch('/admin/csv_editor', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `file_name=${fileId}&operation=modify_row&data=${JSON.stringify(data)}`
    })
    .then(response => response.json())
    .then(result => {
        if(result.success) {
            showToast('success', '데이터가 성공적으로 수정되었습니다.');
        } else {
            showToast('error', '데이터 수정 중 오류가 발생했습니다.');
        }
    });
}

// 관리자 페이지 초기화
document.addEventListener('DOMContentLoaded', function() {
    initializeMonitoring();
    
    // 툴팁 초기화
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => new bootstrap.Tooltip(tooltip));
    
    // 데이터 편집 이벤트 리스너
    document.querySelectorAll('[contenteditable="true"]').forEach(cell => {
        cell.addEventListener('blur', function() {
            const rowId = this.closest('tr').getAttribute('data-row-id');
            const fileId = this.closest('table').getAttribute('data-file-id');
            editData(fileId, rowId);
        });
    });
});

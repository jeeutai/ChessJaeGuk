
document.addEventListener('DOMContentLoaded', function() {
    // 매수 모달 데이터 설정
    document.querySelectorAll('.buy-btn').forEach(button => {
        button.addEventListener('click', function() {
            const stockId = this.dataset.stockId;
            const stockName = this.dataset.stockName;
            const stockPrice = this.dataset.stockPrice;
            const maxQuantity = Math.floor(parseFloat(document.getElementById('user-balance').textContent) / parseFloat(stockPrice));

            document.getElementById('buy-stock-id').value = stockId;
            document.getElementById('buy-stock-name').textContent = stockName;
            document.getElementById('buy-stock-price').textContent = stockPrice;
            document.getElementById('buy-quantity').max = maxQuantity;
            
            // 초기 수량을 1로 설정하고 총액 계산
            document.getElementById('buy-quantity').value = 1;
            calculateBuyTotal();
        });
    });

    // 매도 모달 데이터 설정
    document.querySelectorAll('.sell-btn').forEach(button => {
        button.addEventListener('click', function() {
            const stockId = this.dataset.stockId;
            const stockName = this.dataset.stockName;
            const stockPrice = this.dataset.stockPrice;
            const maxQuantity = this.dataset.maxQuantity;

            document.getElementById('sell-stock-id').value = stockId;
            document.getElementById('sell-stock-name').textContent = stockName;
            document.getElementById('sell-stock-price').textContent = stockPrice;
            document.getElementById('sell-quantity').max = maxQuantity;
            
            // 초기 수량을 1로 설정하고 총액 계산
            document.getElementById('sell-quantity').value = 1;
            calculateSellTotal();
        });
    });

    // 매수 수량 변경 시 총액 계산
    document.getElementById('buy-quantity').addEventListener('input', function() {
        const maxQuantity = parseInt(this.max);
        let quantity = parseInt(this.value);
        
        if (quantity > maxQuantity) {
            quantity = maxQuantity;
            this.value = maxQuantity;
        }
        
        calculateBuyTotal();
    });
    
    // 매도 수량 변경 시 총액 계산
    document.getElementById('sell-quantity').addEventListener('input', function() {
        const maxQuantity = parseInt(this.max);
        let quantity = parseInt(this.value);
        
        if (quantity > maxQuantity) {
            quantity = maxQuantity;
            this.value = maxQuantity;
        }
        
        calculateSellTotal();
    });

    function calculateBuyTotal() {
        const quantity = parseInt(document.getElementById('buy-quantity').value) || 0;
        const price = parseFloat(document.getElementById('buy-stock-price').textContent) || 0;
        const total = quantity * price;
        document.getElementById('buy-total').textContent = total.toLocaleString();
    }

    function calculateSellTotal() {
        const quantity = parseInt(document.getElementById('sell-quantity').value) || 0;
        const price = parseFloat(document.getElementById('sell-stock-price').textContent) || 0;
        const total = quantity * price;
        document.getElementById('sell-total').textContent = total.toLocaleString();
    }

    // 주식 가격 자동 업데이트
    function updateStockPrices() {
        fetch('/stocks/update')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                }
            })
            .catch(error => console.error('주식 가격 업데이트 중 오류:', error));
    }

    // 1분마다 주식 가격 업데이트
    setInterval(updateStockPrices, 60000);
});

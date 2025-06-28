from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
import random
from datetime import datetime, timedelta
from app import CSV_FILES
from utils import read_csv, update_csv, update_user_balance, add_transaction, generate_id, get_system_config, get_stocks_config, award_points_for_action, update_achievement_progress

stocks_bp = Blueprint('stocks', __name__, url_prefix='/stocks')

@stocks_bp.route('/')
def index():
    if not g.user:
        return redirect(url_for('auth.login'))

    # 시스템 설정 가져오기
    system_config = get_system_config()

    # 주식 기능이 비활성화된 경우
    if system_config.get('enable_stocks') == 'False':
        flash('주식 기능이 현재 비활성화되어 있습니다.', 'warning')
        return redirect(url_for('home'))

    # 주식 정보 가져오기
    stocks = read_csv(CSV_FILES['stocks'])

    # 주식 설정 정보 가져오기
    stocks_config = get_stocks_config()

    # 주식 정보에 설정 정보 병합
    for stock in stocks:
        for config in stocks_config:
            if stock['id'] == config['id']:
                stock['code'] = config.get('code', '')
                stock['sector'] = config.get('sector', '')
                stock['description'] = config.get('description', '')
                break

    # 시스템 설정 정보 추가
    currency_name = system_config.get('currency_name', '체스머니')
    currency_symbol = system_config.get('currency_symbol', 'CM')
    country_name = system_config.get('country_name', '체스제국')

    # 사용자 보유 주식 정보 (거래 내역에서 계산)
    transactions = read_csv(CSV_FILES['transactions'])
    user_stocks = calculate_user_stocks(g.user['id'], stocks, transactions)

    return render_template('stocks.html', 
                          stocks=stocks, 
                          user_stocks=user_stocks, 
                          currency_name=currency_name,
                          currency_symbol=currency_symbol,
                          country_name=country_name,
                          system_config=system_config)

@stocks_bp.route('/buy', methods=['POST'])
def buy_stock():
    if not g.user:
        return redirect(url_for('auth.login'))

    # 시스템 설정 가져오기
    system_config = get_system_config()

    # 주식 기능이 비활성화된 경우
    if system_config.get('enable_stocks') == 'False':
        flash('주식 기능이 현재 비활성화되어 있습니다.', 'warning')
        return redirect(url_for('home'))

    try:
        stock_id = request.form.get('stock_id')
        quantity_str = request.form.get('quantity', '1')

        # 입력값 검증
        if not stock_id:
            flash('주식 ID가 누락되었습니다.', 'error')
            return redirect(url_for('stocks.index'))

        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                raise ValueError("수량은 양수여야 합니다.")
        except ValueError:
            flash('유효하지 않은 수량입니다. 양의 정수를 입력해주세요.', 'error')
            return redirect(url_for('stocks.index'))

        # 주식 정보 가져오기
        stocks = read_csv(CSV_FILES['stocks'])
        stock = None
        for s in stocks:
            if s['id'] == stock_id:
                stock = s
                break

        if not stock:
            flash('주식을 찾을 수 없습니다.', 'error')
            return redirect(url_for('stocks.index'))

        # 총 금액 계산
        try:
            try:
                price = float(stock['current_price'])
                total_amount = int(price * quantity)

                # 최소 구매 금액 체크
                if total_amount <= 0:
                    flash('주식 구매 금액은 0보다 커야 합니다.', 'error')
                    return redirect(url_for('stocks.index'))
            except (ValueError, TypeError) as e:
                flash(f'주식 가격 계산 중 오류가 발생했습니다: {str(e)}', 'error')
                return redirect(url_for('stocks.index'))

            # 잔액 확인
            user_balance = int(g.user['balance'])
            if user_balance < total_amount:
                flash(f'잔액이 부족합니다. 필요한 금액: {total_amount}{system_config.get("currency_symbol", "CM")}, 보유 잔액: {user_balance}{system_config.get("currency_symbol", "CM")}', 'error')
                return redirect(url_for('stocks.index'))

            # 구매 처리
            update_user_balance(g.user['id'], total_amount, "subtract")

            # 거래 기록 추가
            transaction_type = f'stock_buy_{stock_id}_{quantity}'
            add_transaction(g.user['id'], f'stock_{stock_id}', total_amount, transaction_type)

            # 시스템 설정에서 화폐 이름 가져오기
            currency_name = system_config.get('currency_name', '체스머니')

            # 포인트 적립 - 주식 구매 포인트
            points_result = award_points_for_action(g.user['id'], 'stock_trade', total_amount)
            if points_result['success']:
                flash(points_result['message'], 'success')

            # 업적 진행도 업데이트
            update_achievement_progress(g.user['id'], 'stock_trader', quantity)

            # 대량 주식 구매 업적 (10주 이상 구매)
            if quantity >= 10:
                update_achievement_progress(g.user['id'], 'bulk_investor', 1)

            # 특정 주식 구매 업적
            update_achievement_progress(g.user['id'], f'stock_{stock_id}_buyer', quantity)

            flash(f"{stock['name']} {quantity}주를 {total_amount}{currency_name}에 구매했습니다.", 'success')

        except Exception as e:
            flash(f"주식 구매 중 오류가 발생했습니다: {str(e)}", 'error')
            return redirect(url_for('stocks.index'))

    except Exception as e:
        flash(f"주식 구매 처리 중 오류가 발생했습니다: {str(e)}", 'error')

    return redirect(url_for('stocks.index'))

@stocks_bp.route('/sell', methods=['POST'])
def sell_stock():
    if not g.user:
        return redirect(url_for('auth.login'))

    # 시스템 설정 가져오기
    system_config = get_system_config()

    # 주식 기능이 비활성화된 경우
    if system_config.get('enable_stocks') == 'False':
        flash('주식 기능이 현재 비활성화되어 있습니다.', 'warning')
        return redirect(url_for('home'))

    try:
        stock_id = request.form.get('stock_id')
        quantity_str = request.form.get('quantity', '1')

        # 입력값 검증
        if not stock_id:
            flash('주식 ID가 누락되었습니다.', 'error')
            return redirect(url_for('stocks.index'))

        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                raise ValueError("수량은 양수여야 합니다.")
        except ValueError:
            flash('유효하지 않은 수량입니다. 양의 정수를 입력해주세요.', 'error')
            return redirect(url_for('stocks.index'))

        # 주식 정보 가져오기
        stocks = read_csv(CSV_FILES['stocks'])
        stock = None
        for s in stocks:
            if s['id'] == stock_id:
                stock = s
                break

        if not stock:
            flash('주식을 찾을 수 없습니다.', 'error')
            return redirect(url_for('stocks.index'))

        # 사용자 보유 주식 정보 확인
        transactions = read_csv(CSV_FILES['transactions'])
        user_stocks = calculate_user_stocks(g.user['id'], stocks, transactions)

        # 보유량 확인
        if stock_id not in user_stocks:
            flash(f'{stock["name"]} 주식을 보유하고 있지 않습니다.', 'error')
            return redirect(url_for('stocks.index'))

        if user_stocks[stock_id]['quantity'] < quantity:
            flash(f'보유한 주식이 부족합니다. 보유량: {user_stocks[stock_id]["quantity"]}주, 판매 시도: {quantity}주', 'error')
            return redirect(url_for('stocks.index'))

        # 판매 금액 계산
        try:
            price = float(stock['current_price'])
            total_amount = int(price * quantity)

            # 최소 판매 금액 체크
            if total_amount <= 0:
                flash('주식 판매 금액은 0보다 커야 합니다.', 'error')
                return redirect(url_for('stocks.index'))

            # 판매 처리
            update_user_balance(g.user['id'], total_amount, "add")

            # 거래 기록 추가
            transaction_id = generate_id()
            transaction = {
                'id': transaction_id,
                'sender_id': f'stock_{stock_id}',
                'receiver_id': g.user['id'],
                'amount': str(total_amount),
                'type': f'stock_sell_{stock_id}_{quantity}',
                'timestamp': str(datetime.now()),
                'sell_price': stock['current_price']  # 판매 당시 가격 기록
            }

            add_transaction(transaction['sender_id'], transaction['receiver_id'], int(transaction['amount']), transaction['type'])

            # 시스템 설정에서 화폐 이름 가져오기
            currency_name = system_config.get('currency_name', '체스머니')
            currency_symbol = system_config.get('currency_symbol', 'CM')

            # 포인트 적립 - 주식 판매 포인트
            points_result = award_points_for_action(g.user['id'], 'stock_trade', total_amount)
            if points_result['success']:
                flash(points_result['message'], 'success')

            # 주식 판매 업적 진행도 업데이트
            update_achievement_progress(g.user['id'], 'stock_seller', quantity)

            # 판매 이익 계산
            try:
                if user_stocks[stock_id]['current_price'] > 0 and float(stock['previous_price']) > 0:
                    price_diff = (float(stock['current_price']) - float(stock['previous_price'])) / float(stock['previous_price']) * 100
                    if price_diff > 10:
                        update_achievement_progress(g.user['id'], 'stock_profit', 1)

                        if price_diff > 0:
                            flash(f"이익률: +{price_diff:.2f}%로 판매에 성공했습니다!", 'success')
                        else:
                            flash(f"이익률: {price_diff:.2f}%로 판매했습니다.", 'info')
            except Exception as e:
                print(f"이익률 계산 오류: {str(e)}")

            flash(f"{stock['name']} {quantity}주를 {total_amount}{currency_symbol}에 판매했습니다.", 'success')

        except Exception as e:
            flash(f"주식 판매 처리 중 오류가 발생했습니다: {str(e)}", 'error')
            return redirect(url_for('stocks.index'))

    except Exception as e:
        flash(f"주식 판매 중 오류가 발생했습니다: {str(e)}", 'error')

    return redirect(url_for('stocks.index'))

@stocks_bp.route('/update', methods=['GET'])
def update_stock_prices():
    """주식 가격 업데이트 (실시간 랜덤 변동)"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})

    # 시스템 설정 가져오기
    system_config = get_system_config()

    # 주식 기능이 비활성화된 경우
    if system_config.get('enable_stocks') == 'False':
        return jsonify({'success': False, 'message': '주식 기능이 비활성화되었습니다.'})

    # 주식 정보 가져오기
    stocks = read_csv(CSV_FILES['stocks'])

    # 주식 설정 정보 가져오기
    stocks_config = get_stocks_config()

    # 주식 설정을 ID로 매핑
    config_map = {}
    for config in stocks_config:
        config_map[config['id']] = config

    updated_stocks = []

    for stock in stocks:
        previous_price = float(stock['current_price'])
        stock_id = stock['id']

        # 해당 주식의 설정 정보 가져오기
        config = config_map.get(stock_id, {})
        volatility = float(config.get('volatility', 5))  # 기본 변동성 5%
        min_price = float(config.get('min_price', 100))
        max_price = float(config.get('max_price', previous_price * 10))

        # 변동성에 따른 랜덤 변동 (-volatility% ~ +volatility%)
        change_percent = (random.random() * 2 * volatility) - volatility
        new_price = previous_price * (1 + (change_percent / 100))

        # 최소/최대 가격 제한
        new_price = max(min_price, min(max_price, new_price))
        new_price = round(new_price, 2)

        stock['previous_price'] = str(previous_price)
        stock['current_price'] = str(new_price)
        stock['change_percent'] = f"{change_percent:.2f}"
        stock['last_update'] = str(datetime.now())

        # 설정 정보 추가
        if stock_id in config_map:
            stock['code'] = config_map[stock_id].get('code', '')
            stock['sector'] = config_map[stock_id].get('sector', '')
            stock['description'] = config_map[stock_id].get('description', '')

        updated_stocks.append(stock)

    update_csv(CSV_FILES['stocks'], updated_stocks)

    # 사용자 보유 주식 정보 갱신
    transactions = read_csv(CSV_FILES['transactions'])
    user_stocks = calculate_user_stocks(g.user['id'], updated_stocks, transactions)

    return jsonify({
        'success': True,
        'stocks': updated_stocks,
        'user_stocks': user_stocks
    })

def calculate_user_stocks(user_id, stocks, transactions):
    """사용자의 보유 주식 계산"""
    user_stocks = {}

    # 각 주식의 현재 가격 매핑
    stock_prices = {}
    for stock in stocks:
        stock_id = stock['id']
        stock_prices[stock_id] = {
            'name': stock['name'],
            'price': float(stock['current_price'])
        }

    # 거래 내역에서 구매/판매 계산
    for tx in transactions:
        if 'stock_buy' in tx['type'] and tx['sender_id'] == user_id:
            # 주식 구매 거래
            parts = tx['type'].split('_')
            stock_id = parts[2]
            quantity = int(parts[3])

            if stock_id not in user_stocks:
                user_stocks[stock_id] = {
                    'name': stock_prices.get(stock_id, {}).get('name', 'Unknown'),
                    'quantity': 0,
                    'current_price': stock_prices.get(stock_id, {}).get('price', 0),
                    'total_value': 0
                }

            user_stocks[stock_id]['quantity'] += quantity

        elif 'stock_sell' in tx['type'] and tx['receiver_id'] == user_id:
            # 주식 판매 거래
            parts = tx['type'].split('_')
            stock_id = parts[2]
            quantity = int(parts[3])

            if stock_id in user_stocks:
                user_stocks[stock_id]['quantity'] -= quantity

    # 총 가치 계산 및 0 보유량 제거
    for stock_id in list(user_stocks.keys()):
        if user_stocks[stock_id]['quantity'] <= 0:
            del user_stocks[stock_id]
        else:
            user_stocks[stock_id]['total_value'] = user_stocks[stock_id]['quantity'] * user_stocks[stock_id]['current_price']

    return user_stocks
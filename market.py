from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session
from app import CSV_FILES
from datetime import datetime, timedelta
from utils import read_csv, update_user_balance, add_transaction, add_market_log, get_item
from utils import get_system_config, get_market_items_config, award_points_for_action, update_achievement_progress

market_bp = Blueprint('market', __name__, url_prefix='/market')

@market_bp.route('/')
def index():
    if not g.user:
        return redirect(url_for('auth.login'))
    
    # 시스템 설정 가져오기
    system_config = get_system_config()
    
    # 마켓 기능이 비활성화된 경우
    if system_config.get('enable_market') == 'False':
        flash('마켓 기능이 현재 비활성화되어 있습니다.', 'warning')
        return redirect(url_for('home'))
    
    # 할인율 설정 확인
    discount_rate = float(system_config.get('market_discount', '0'))
    
    # 아이템 목록 가져오기
    items = [item for item in read_csv(CSV_FILES['items']) if item.get('enabled', 'True').lower() == 'true']
    
    # 마켓 아이템 설정 가져오기
    market_items_config = get_market_items_config()
    
    # 아이템 정보에 설정 정보 추가 및 할인 적용
    for item in items:
        # 할인 적용
        if discount_rate > 0:
            original_price = int(item['price'])
            discounted_price = int(original_price * (1 - discount_rate/100))
            item['original_price'] = str(original_price)
            item['price'] = str(discounted_price)
            item['discount_rate'] = str(discount_rate)
        
        # 상세 정보 추가
        for config in market_items_config:
            if item['id'] == config['id']:
                item['category'] = config.get('category', '기타')
                item['description'] = config.get('description', '')
                item['image_url'] = config.get('image_url', '')
                break
    
    # 사용자 구매 내역 가져오기
    market_logs = read_csv(CSV_FILES['market_logs'])
    user_purchases = [log for log in market_logs if log['user_id'] == g.user['id']]
    
    return render_template('market.html', 
                          items=items, 
                          user_purchases=user_purchases, 
                          system_config=system_config)

@market_bp.route('/buy/<item_id>', methods=['POST'])
def buy_item(item_id):
    if not g.user:
        return redirect(url_for('auth.login'))
    
    # 아이템 정보 가져오기
    item = get_item(item_id)
    if not item:
        flash('아이템을 찾을 수 없습니다.', 'error')
        return redirect(url_for('market.index'))
    
    quantity = int(request.form.get('quantity', 1))
    total_price = int(item['price']) * quantity
    
    # 잔액 확인
    if int(g.user['balance']) < total_price:
        flash('잔액이 부족합니다.', 'error')
        return redirect(url_for('market.index'))
    
    # 구매 처리
    update_user_balance(g.user['id'], total_price, "subtract")
    
    # 거래 기록 추가
    add_transaction(g.user['id'], 'system', total_price, 'market_purchase')
    
    # 마트 로그 추가
    add_market_log(g.user['id'], item_id, quantity, item['price'])
    
    # 포인트 적립 - 마켓 구매 포인트
    points_result = award_points_for_action(g.user['id'], 'market_purchase', total_price)
    if points_result['success']:
        flash(points_result['message'], 'success')
    
    # 업적 진행도 업데이트
    update_achievement_progress(g.user['id'], 'shopper', quantity)
    
    # 비싼 아이템 구매 업적 (10,000 이상 아이템)
    if int(item['price']) >= 10000:
        update_achievement_progress(g.user['id'], 'big_spender', 1)
    
    # 특정 아이템 카테고리 구매 업적
    try:
        # 마켓 아이템 설정 가져오기
        market_items_config = get_market_items_config()
        for config in market_items_config:
            if item['id'] == config['id']:
                category = config.get('category', '기타')
                if category:
                    update_achievement_progress(g.user['id'], f'buy_{category.lower()}', quantity)
                break
    except:
        pass  # 카테고리 업적 처리 오류 무시
    
    flash(f"{item['name']} {quantity}개를 구매했습니다.", 'success')
    return redirect(url_for('market.index'))

@market_bp.route('/use/<log_id>', methods=['POST'])
def use_item(log_id):
    if not g.user:
        return redirect(url_for('auth.login'))
    
    # 시스템 설정 가져오기
    system_config = get_system_config()
    
    # 마켓 기능이 비활성화된 경우
    if system_config.get('enable_market') == 'False':
        flash('마켓 기능이 현재 비활성화되어 있습니다.', 'warning')
        return redirect(url_for('home'))
    
    # 구매 로그 찾기
    market_logs = read_csv(CSV_FILES['market_logs'])
    log = None
    for l in market_logs:
        if l['id'] == log_id and l['user_id'] == g.user['id']:
            log = l
            break
    
    if not log:
        flash('아이템 구매 내역을 찾을 수 없습니다.', 'error')
        return redirect(url_for('market.index'))
    
    # 아이템 정보 가져오기
    item = get_item(log['item_id'])
    if not item:
        flash('아이템을 찾을 수 없습니다.', 'error')
        return redirect(url_for('market.index'))
    
    # 마켓 아이템 상세 설정 가져오기
    market_items_config = get_market_items_config()
    item_config = None
    for config in market_items_config:
        if config['id'] == log['item_id']:
            item_config = config
            break
    
    # 아이템 카테고리와 효과
    category = item_config.get('category', '기타') if item_config else '기타'
    effect = item['effect']
    
    # 아이템 효과 적용 로직 (카테고리와 효과에 따라 다름)
    effect_applied = False
    effect_message = ""
    
    # 카테고리별 처리
    if category == '무기':
        # 무기 아이템은 채팅에서 사용할 수 있는 아이템
        target_user = request.form.get('target_user', '')
        if not target_user:
            flash('대상 사용자를 선택해주세요.', 'error')
            return redirect(url_for('market.index'))
        
        # 사용자 존재 여부 확인 필요
        session['weapon'] = {
            'name': item['name'],
            'effect': effect,
            'target': target_user
        }
        effect_applied = True
        effect_message = f"{item['name']}이(가) {target_user}에게 사용 준비되었습니다."
    
    elif category == '부스터':
        # 부스터 아이템 (게임, 거래 등에서 이점 제공)
        if "승리 확률" in effect or "게임" in effect:
            # 게임 부스트
            boost_amount = 10  # 기본 10%
            try:
                # 효과에서 숫자 추출 (예: "10% 증가"에서 10 추출)
                import re
                num = re.search(r'(\d+)', effect)
                if num:
                    boost_amount = int(num.group(1))
            except:
                pass
            
            session['game_boost'] = boost_amount / 100 + 1.0
            effect_applied = True
            effect_message = f"{item['name']}의 효과가 적용되었습니다. 다음 게임에서 승리 확률이 {boost_amount}% 증가합니다."
        
        elif "거래" in effect or "적립" in effect:
            # 거래 부스트
            boost_amount = 10  # 기본 10%
            try:
                import re
                num = re.search(r'(\d+)', effect)
                if num:
                    boost_amount = int(num.group(1))
            except:
                pass
            
            session['transaction_boost'] = boost_amount / 100 + 1.0
            effect_applied = True
            effect_message = f"{item['name']}의 효과가 적용되었습니다. 다음 거래에서 {boost_amount}% 추가 적립됩니다."
    
    elif category == '장식':
        # 프로필 장식, 뱃지 등
        if "프로필" in effect or "뱃지" in effect:
            # 뱃지, 프로필 효과
            session['badge'] = {
                'name': item['name'],
                'image': item_config.get('image_url', '') if item_config else '',
                'expires': datetime.now() + timedelta(days=int(item.get('duration', 30)))
            }
            effect_applied = True
            effect_message = f"{item['name']}이(가) 프로필에 적용되었습니다. {item.get('duration', 30)}일간 유지됩니다."
    
    elif category == '아이템':
        # 일반 아이템들
        if "채팅" in effect or "메시지" in effect:
            # 채팅 관련 아이템
            session['chat_effect'] = {
                'name': item['name'],
                'effect': effect
            }
            effect_applied = True
            effect_message = f"{item['name']}의 효과가 채팅에 적용되었습니다."
            
        elif "주식" in effect:
            # 주식 관련 아이템
            session['stock_effect'] = {
                'name': item['name'],
                'effect': effect
            }
            effect_applied = True
            effect_message = f"{item['name']}의 효과가 주식 거래에 적용되었습니다."
    
    else:
        # 기타 아이템: 기본 효과 (잔액 증가)
        bonus = int(item['price']) // 2
        update_user_balance(g.user['id'], bonus, "add")
        add_transaction('system', g.user['id'], bonus, 'item_effect')
        effect_applied = True
        
        # 시스템 설정에서 화폐 이름 가져오기
        currency_name = system_config.get('currency_name', '체스머니')
        effect_message = f"{item['name']}의 효과로 {bonus}{currency_name}이 추가되었습니다."
    
    if effect_applied:
        # 사용 완료된 아이템 제거 또는 사용 횟수 감소
        updated_logs = []
        for l in market_logs:
            if l['id'] == log_id:
                # 이 예제에서는 사용 후 완전히 제거
                pass
            else:
                updated_logs.append(l)
        
        # 업데이트된 로그 저장
        with open(CSV_FILES['market_logs'], 'w', newline='', encoding='utf-8') as file:
            import csv
            writer = csv.DictWriter(file, fieldnames=market_logs[0].keys())
            writer.writeheader()
            writer.writerows(updated_logs)
        
        # 아이템 사용 포인트 적립
        points_result = award_points_for_action(g.user['id'], 'use_item')
        
        # 아이템 사용 업적 진행도 업데이트
        update_achievement_progress(g.user['id'], 'item_user', 1)
        
        # 특정 카테고리 아이템 사용 업적
        update_achievement_progress(g.user['id'], f'use_{category.lower()}', 1)
        
        flash(effect_message, 'success')
    else:
        flash('아이템을 사용할 수 없습니다.', 'error')
    
    return redirect(url_for('market.index'))

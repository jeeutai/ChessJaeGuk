from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, jsonify
from datetime import datetime, timedelta
import csv
import os
import json
import shutil
import time
from datetime import datetime, timedelta
from app import CSV_FILES
from utils import read_csv, update_csv, generate_id, get_timestamp, update_user_balance, append_to_csv
from utils import get_system_config, get_market_items_config, get_stocks_config, get_games_config, get_politicians
from utils import update_system_config, add_transaction
from utils import get_achievements, get_user_achievements, get_reward_items, add_points
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def add_login_log(user_id, status, ip=None):
    # 시스템 설정 가져오기
    system_config = get_system_config()
    
    # 로그인 IP 확인이 비활성화된 경우
    if system_config.get('login_ip_check') == 'False':
        ip = "IP확인비활성화"
    elif ip is None:
        ip = request.remote_addr
    
    # 사용자 정보 가져오기 (로그 세부 정보용)
    user_agent = request.user_agent.string if hasattr(request, 'user_agent') else "알 수 없음"
    browser = "알 수 없음"
    platform = "알 수 없음"
    
    if hasattr(request, 'user_agent') and request.user_agent.browser:
        browser = f"{request.user_agent.browser} {request.user_agent.version}"
        platform = request.user_agent.platform
    
    # 로그 생성
    log = {
        'id': generate_id(),
        'user_id': user_id,
        'timestamp': get_timestamp(),
        'ip': ip,
        'status': status,
        'browser': browser,
        'platform': platform,
        'user_agent': user_agent
    }
    
    append_to_csv(CSV_FILES['login_logs'], log)


# 관리자 권한 확인 데코레이터
def admin_required(view):
    def wrapped_view(**kwargs):
        if not g.user:
            flash('로그인이 필요합니다.', 'error')
            return redirect(url_for('auth.login'))
        if g.user['is_admin'] != 'True':
            flash('관리자 권한이 필요합니다.', 'error')
            return redirect(url_for('home'))
        # 세션 유효성 검사 추가
        if 'last_activity' not in session:
            session['last_activity'] = time.time()
        elif time.time() - session['last_activity'] > 3600:  # 1시간 타임아웃
            session.clear()
            flash('세션이 만료되었습니다. 다시 로그인해주세요.', 'warning')
            return redirect(url_for('auth.login'))
        session['last_activity'] = time.time()
        return view(**kwargs)
    wrapped_view.__name__ = view.__name__
    return wrapped_view

def superadmin_required(view):
    def wrapped_view(**kwargs):
        if not g.user or g.user['id'] != 'admin':
            flash('최고 관리자 권한이 필요합니다.', 'error')
            return redirect(url_for('home'))
        return view(**kwargs)
    wrapped_view.__name__ = view.__name__
    return wrapped_view

@admin_bp.route('/')
@admin_required
def index():
    # 시스템 설정 불러오기
    system_config = get_system_config()
    
    # 관리자 대시보드 정보 준비
    dashboard = {
        'config_count': {
            'system': len(read_csv(CSV_FILES['system_config'])),
            'games': len(get_games_config()),
            'stocks': len(get_stocks_config()),
            'market': len(get_market_items_config()),
            'politicians': len(get_politicians())
        },
        'data_count': {
            'users': len(read_csv(CSV_FILES['users'])),
            'transactions': len(read_csv(CSV_FILES['transactions'])),
            'market_logs': len(read_csv(CSV_FILES['market_logs'])),
            'game_logs': len(read_csv(CSV_FILES['game_logs'])),
            'login_logs': len(read_csv(CSV_FILES['login_logs']))
        }
    }
    
    return render_template('admin.html', section='dashboard', system_config=system_config, dashboard=dashboard)

@admin_bp.route('/users')
@admin_required
def users():
    users = read_csv(CSV_FILES['users'])
    active_sessions = read_csv(CSV_FILES['login_logs'])
    
    # 최근 24시간 내 활성 세션만 필터링
    from datetime import datetime, timedelta
    cutoff_time = datetime.now() - timedelta(hours=24)
    
    active_users = {}
    for log in active_sessions:
        try:
            log_time = datetime.strptime(log['timestamp'].split('.')[0], '%Y-%m-%d %H:%M:%S')
            if log_time > cutoff_time and log['status'] == 'success':
                active_users[log['user_id']] = log['timestamp']
        except:
            continue

    # 사용자 정보에 활성 상태 추가
    for user in users:
        user['is_active'] = user['id'] in active_users
        user['last_active'] = active_users.get(user['id'], '활동 없음')
        
        # 최근 7일간의 로그인 시도 실패 횟수 계산
        failed_attempts = 0
        for log in active_sessions:
            if log['user_id'] == user['id'] and log['status'] == 'failed':
                try:
                    log_time = datetime.strptime(log['timestamp'].split('.')[0], '%Y-%m-%d %H:%M:%S')
                    if log_time > (datetime.now() - timedelta(days=7)):
                        failed_attempts += 1
                except:
                    continue
        user['failed_attempts'] = failed_attempts

    return render_template('admin.html', section='users', users=users)

@admin_bp.route('/users/logout/<user_id>', methods=['POST'])
@admin_required
def logout_user(user_id):
    """특정 사용자 로그아웃"""
    users = read_csv(CSV_FILES['users'])
    found = False
    for user in users:
        if user['id'] == user_id:
            found = True
            break
    
    if not found:
        flash('사용자를 찾을 수 없습니다.', 'error')
        return redirect(url_for('admin.users'))
        
    # 로그아웃 로그 추가
    add_login_log(user_id, 'force_logout', request.remote_addr)
    flash(f'사용자 {user_id}가 강제 로그아웃되었습니다.', 'success')
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/logout_all', methods=['POST'])
@admin_required
def logout_all_users():
    """모든 사용자 로그아웃"""
    users = read_csv(CSV_FILES['users'])
    count = 0
    
    for user in users:
        if user['is_admin'] != 'True':  # 관리자 제외
            add_login_log(user['id'], 'force_logout', request.remote_addr)
            count += 1
    
    flash(f'총 {count}명의 사용자가 강제 로그아웃되었습니다.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/ban/<user_id>', methods=['POST'])
@admin_required
def ban_user(user_id):
    """사용자 계정 정지"""
    if user_id == 'admin' or user_id == g.user['id']:
        flash('관리자 계정은 정지할 수 없습니다.', 'error')
        return redirect(url_for('admin.users'))
        
    users = read_csv(CSV_FILES['users'])
    updated_users = []
    
    for user in users:
        if user['id'] == user_id:
            user['status'] = 'banned'
            user['ban_reason'] = request.form.get('ban_reason', '')
            user['banned_at'] = get_timestamp()
            user['banned_by'] = g.user['id']
            
            # 강제 로그아웃
            add_login_log(user_id, 'force_logout', request.remote_addr)
        updated_users.append(user)
    
    update_csv(CSV_FILES['users'], updated_users)
    flash(f'사용자 {user_id}가 정지되었습니다.', 'success')
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/memo/<user_id>', methods=['POST'])
@admin_required
def update_memo(user_id):
    """사용자 메모 업데이트"""
    memo = request.form.get('memo', '')
    
    users = read_csv(CSV_FILES['users'])
    updated_users = []
    
    for user in users:
        if user['id'] == user_id:
            user['memo'] = memo
        updated_users.append(user)
    
    update_csv(CSV_FILES['users'], updated_users)
    flash('메모가 업데이트되었습니다.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/unban/<user_id>', methods=['POST'])
@admin_required
def unban_user(user_id):
    """사용자 계정 정지 해제"""
    users = read_csv(CSV_FILES['users'])
    updated_users = []
    
    for user in users:
        if user['id'] == user_id:
            user['status'] = 'active'
            user['unbanned_at'] = get_timestamp()
            user['unbanned_by'] = g.user['id']
        updated_users.append(user)
    
    update_csv(CSV_FILES['users'], updated_users)
    flash(f'사용자 {user_id}의 정지가 해제되었습니다.', 'success')
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/edit/<user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    if request.method == 'POST':
        # 사용자 정보 업데이트
        users = read_csv(CSV_FILES['users'])
        updated_users = []
        
        for user in users:
            if user['id'] == user_id:
                user['nickname'] = request.form['nickname']
                user['email'] = request.form['email']
                user['phone'] = request.form['phone']
                user['balance'] = request.form['balance']
                user['is_admin'] = 'True' if request.form.get('is_admin') else 'False'
            updated_users.append(user)
        
        update_csv(CSV_FILES['users'], updated_users)
        flash('사용자 정보가 업데이트되었습니다.', 'success')
        return redirect(url_for('admin.users'))
    
    # 사용자 정보 가져오기
    user = None
    users = read_csv(CSV_FILES['users'])
    for u in users:
        if u['id'] == user_id:
            user = u
            break
    
    if not user:
        flash('사용자를 찾을 수 없습니다.', 'error')
        return redirect(url_for('admin.users'))
    
    return render_template('admin.html', section='edit_user', user=user)

@admin_bp.route('/users/delete/<user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == 'admin' or user_id == g.user['id']:
        flash('관리자 계정은 삭제할 수 없습니다.', 'error')
        return redirect(url_for('admin.users'))
    
    users = read_csv(CSV_FILES['users'])
    updated_users = [user for user in users if user['id'] != user_id]
    
    with open(CSV_FILES['users'], 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=users[0].keys())
        writer.writeheader()
        writer.writerows(updated_users)
    
    flash('사용자가 삭제되었습니다.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/transactions')
@admin_required
def transactions():
    transactions = read_csv(CSV_FILES['transactions'])
    transactions.sort(key=lambda x: x['timestamp'], reverse=True)
    return render_template('admin.html', section='transactions', transactions=transactions)

@admin_bp.route('/login_logs')
@admin_required
def login_logs():
    logs = read_csv(CSV_FILES['login_logs'])
    logs.sort(key=lambda x: x['timestamp'], reverse=True)
    return render_template('admin.html', section='login_logs', logs=logs)

@admin_bp.route('/game_logs')
@admin_required
def game_logs():
    logs = read_csv(CSV_FILES['game_logs'])
    logs.sort(key=lambda x: x['timestamp'], reverse=True)
    return render_template('admin.html', section='game_logs', logs=logs)

@admin_bp.route('/market_logs')
@admin_required
def market_logs():
    logs = read_csv(CSV_FILES['market_logs'])
    logs.sort(key=lambda x: x['timestamp'], reverse=True)
    return render_template('admin.html', section='market_logs', logs=logs)

@admin_bp.route('/notices', methods=['GET', 'POST'])
@admin_required
def notices():
    if request.method == 'POST':
        # 새 공지사항 추가
        notice = {
            'id': generate_id(),
            'title': request.form['title'],
            'content': request.form['content'],
            'author_id': g.user['id'],
            'timestamp': get_timestamp()
        }
        append_to_csv(CSV_FILES['notices'], notice)
        flash('공지사항이 추가되었습니다.', 'success')
    
    notices = read_csv(CSV_FILES['notices'])
    notices.sort(key=lambda x: x['timestamp'], reverse=True)
    return render_template('admin.html', section='notices', notices=notices)

@admin_bp.route('/notices/delete/<notice_id>', methods=['POST'])
@admin_required
def delete_notice(notice_id):
    notices = read_csv(CSV_FILES['notices'])
    updated_notices = [notice for notice in notices if notice['id'] != notice_id]
    
    with open(CSV_FILES['notices'], 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=notices[0].keys())
        writer.writeheader()
        writer.writerows(updated_notices)
    
    flash('공지사항이 삭제되었습니다.', 'success')
    return redirect(url_for('admin.notices'))

@admin_bp.route('/items', methods=['GET', 'POST'])
@admin_required
def items():
    if request.method == 'POST':
        # 새 아이템 추가
        item = {
            'id': generate_id(),
            'name': request.form['name'],
            'effect': request.form['effect'],
            'price': request.form['price'],
            'duration': request.form['duration'],
            'max_uses': request.form['max_uses']
        }
        append_to_csv(CSV_FILES['items'], item)
        flash('아이템이 추가되었습니다.', 'success')
    
    items = read_csv(CSV_FILES['items'])
    return render_template('admin.html', section='items', items=items)

@admin_bp.route('/items/edit/<item_id>', methods=['GET', 'POST'])
@admin_required
def edit_item(item_id):
    if request.method == 'POST':
        # 아이템 정보 업데이트
        items = read_csv(CSV_FILES['items'])
        updated_items = []
        
        for item in items:
            if item['id'] == item_id:
                item['name'] = request.form['name']
                item['effect'] = request.form['effect']
                item['price'] = request.form['price']
                item['duration'] = request.form['duration']
                item['max_uses'] = request.form['max_uses']
            updated_items.append(item)
        
        update_csv(CSV_FILES['items'], updated_items)
        flash('아이템 정보가 업데이트되었습니다.', 'success')
        return redirect(url_for('admin.items'))
    
    # 아이템 정보 가져오기
    item = None
    items = read_csv(CSV_FILES['items'])
    for i in items:
        if i['id'] == item_id:
            item = i
            break
    
    if not item:
        flash('아이템을 찾을 수 없습니다.', 'error')
        return redirect(url_for('admin.items'))
    
    return render_template('admin.html', section='edit_item', item=item)

@admin_bp.route('/items/delete/<item_id>', methods=['POST'])
@admin_required
def delete_item(item_id):
    items = read_csv(CSV_FILES['items'])
    updated_items = [item for item in items if item['id'] != item_id]
    
    with open(CSV_FILES['items'], 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=items[0].keys())
        writer.writeheader()
        writer.writerows(updated_items)
    
    flash('아이템이 삭제되었습니다.', 'success')
    return redirect(url_for('admin.items'))

@admin_bp.route('/stocks', methods=['GET', 'POST'])
@admin_required
def stocks():
    if request.method == 'POST':
        # 새 주식 추가
        stock = {
            'id': generate_id(),
            'name': request.form['name'],
            'current_price': request.form['current_price'],
            'previous_price': request.form['current_price'],
            'change_percent': '0.0',
            'last_update': get_timestamp()
        }
        append_to_csv(CSV_FILES['stocks'], stock)
        flash('주식이 추가되었습니다.', 'success')
    
    stocks = read_csv(CSV_FILES['stocks'])
    return render_template('admin.html', section='stocks', stocks=stocks)

@admin_bp.route('/stocks/edit/<stock_id>', methods=['GET', 'POST'])
@admin_required
def edit_stock(stock_id):
    if request.method == 'POST':
        # 주식 정보 업데이트
        stocks = read_csv(CSV_FILES['stocks'])
        updated_stocks = []
        
        for stock in stocks:
            if stock['id'] == stock_id:
                previous_price = float(stock['current_price'])
                current_price = float(request.form['current_price'])
                
                change = ((current_price - previous_price) / previous_price) * 100
                
                stock['name'] = request.form['name']
                stock['previous_price'] = str(previous_price)
                stock['current_price'] = str(current_price)
                stock['change_percent'] = f"{change:.2f}"
                stock['last_update'] = get_timestamp()
            updated_stocks.append(stock)
        
        update_csv(CSV_FILES['stocks'], updated_stocks)
        flash('주식 정보가 업데이트되었습니다.', 'success')
        return redirect(url_for('admin.stocks'))
    
    # 주식 정보 가져오기
    stock = None
    stocks = read_csv(CSV_FILES['stocks'])
    for s in stocks:
        if s['id'] == stock_id:
            stock = s
            break
    
    if not stock:
        flash('주식을 찾을 수 없습니다.', 'error')
        return redirect(url_for('admin.stocks'))
    
    return render_template('admin.html', section='edit_stock', stock=stock)

@admin_bp.route('/stocks/delete/<stock_id>', methods=['POST'])
@admin_required
def delete_stock(stock_id):
    stocks = read_csv(CSV_FILES['stocks'])
    updated_stocks = [stock for stock in stocks if stock['id'] != stock_id]
    
    with open(CSV_FILES['stocks'], 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=stocks[0].keys())
        writer.writeheader()
        writer.writerows(updated_stocks)
    
    flash('주식이 삭제되었습니다.', 'success')
    return redirect(url_for('admin.stocks'))

@admin_bp.route('/send_money', methods=['POST'])
@admin_required
def send_money():
    receiver_id = request.form['receiver_id']
    amount = int(request.form['amount'])
    
    # 수신자 확인
    users = read_csv(CSV_FILES['users'])
    receiver = None
    for user in users:
        if user['id'] == receiver_id:
            receiver = user
            break
    
    if not receiver:
        flash('존재하지 않는 사용자입니다.', 'error')
        return redirect(url_for('admin.users'))
    
    # 송금 처리
    update_user_balance(receiver_id, amount, "add")
    
    # 거래 기록 추가
    transaction = {
        'id': generate_id(),
        'sender_id': g.user['id'],
        'receiver_id': receiver_id,
        'amount': str(amount),
        'type': 'admin_transfer',
        'timestamp': get_timestamp()
    }
    append_to_csv(CSV_FILES['transactions'], transaction)
    
    flash(f'{receiver_id}님에게 {amount}원을 송금했습니다.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/system', methods=['GET', 'POST'])
@admin_required
def system():
    # 시스템 설정 업데이트 처리
    if request.method == 'POST':
        setting_key = request.form.get('setting_key')
        setting_value = request.form.get('setting_value')
        
        if setting_key and setting_value is not None:
            success = update_system_config(setting_key, setting_value)
            if success:
                flash(f'시스템 설정 "{setting_key}"이(가) 업데이트되었습니다.', 'success')
            else:
                flash('시스템 설정 업데이트에 실패했습니다.', 'error')
    
    # 시스템 설정 불러오기
    system_config = get_system_config()
    
    # CSV 파일 크기 및 상태 확인
    csv_stats = []
    for key, path in CSV_FILES.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            row_count = 0
            with open(path, 'r', encoding='utf-8') as file:
                row_count = sum(1 for _ in file) - 1  # 헤더 제외
            
            csv_stats.append({
                'name': key,
                'path': path,
                'size': f"{size / 1024:.2f} KB",
                'rows': row_count
            })
    
    stats = {
        'active_users': len([u for u in read_csv(CSV_FILES['users']) if u.get('status') != 'banned']),
        'transactions': len(read_csv(CSV_FILES['transactions'])),
        'game_plays': len(read_csv(CSV_FILES['game_logs']))
    }
    return render_template('admin.html', section='system', csv_stats=csv_stats, system_config=system_config, stats=stats)

@admin_bp.route('/config/system', methods=['GET', 'POST'])
@admin_required
def config_system():
    """시스템 설정 관리"""
    if request.method == 'POST':
        # 시스템 설정 업데이트
        key = request.form.get('key')
        value = request.form.get('value')
        description = request.form.get('description')
        
        # 새 설정 추가
        if key and value and description and 'add_setting' in request.form:
            configs = read_csv(CSV_FILES['system_config'])
            
            # 이미 존재하는 키 확인
            exists = False
            for config in configs:
                if config['key'] == key:
                    exists = True
                    break
            
            if exists:
                flash(f'이미 존재하는 설정 키입니다: {key}', 'error')
            else:
                new_config = {
                    'key': key,
                    'value': value,
                    'description': description
                }
                append_to_csv(CSV_FILES['system_config'], new_config)
                flash('새 시스템 설정이 추가되었습니다.', 'success')
        
        # 설정 일괄 업데이트
        elif 'update_settings' in request.form:
            configs = read_csv(CSV_FILES['system_config'])
            updated_configs = []
            
            for config in configs:
                key = config['key']
                if key in request.form:
                    config['value'] = request.form[key]
                updated_configs.append(config)
            
            update_csv(CSV_FILES['system_config'], updated_configs, key_field='key')
            flash('시스템 설정이 업데이트되었습니다.', 'success')
    
    # 시스템 설정 불러오기
    system_config = get_system_config()
    configs = read_csv(CSV_FILES['system_config'])
    
    return render_template('admin.html', section='config_system', configs=configs, system_config=system_config)

@admin_bp.route('/config/games', methods=['GET', 'POST'])
@admin_required
def config_games():
    """게임 설정 관리"""
    if request.method == 'POST':
        # 게임 설정 업데이트
        game_id = request.form.get('id')
        name = request.form.get('name')
        description = request.form.get('description')
        min_bet = request.form.get('min_bet')
        max_bet = request.form.get('max_bet')
        enabled = request.form.get('enabled', 'False')
        win_multiplier = request.form.get('win_multiplier')
        special_win_multiplier = request.form.get('special_win_multiplier')
        draw_multiplier = request.form.get('draw_multiplier')
        
        # 새 게임 추가
        if game_id and name and 'add_game' in request.form:
            games = read_csv(CSV_FILES['games_config'])
            
            # 이미 존재하는 게임 ID 확인
            exists = False
            for game in games:
                if game['id'] == game_id:
                    exists = True
                    break
            
            if exists:
                flash(f'이미 존재하는 게임 ID입니다: {game_id}', 'error')
            else:
                new_game = {
                    'id': game_id,
                    'name': name,
                    'description': description or '',
                    'min_bet': min_bet or '100',
                    'max_bet': max_bet or '10000',
                    'enabled': enabled,
                    'win_multiplier': win_multiplier or '1.5',
                    'special_win_multiplier': special_win_multiplier or '2.0',
                    'draw_multiplier': draw_multiplier or '1.0'
                }
                append_to_csv(CSV_FILES['games_config'], new_game)
                flash('새 게임 설정이 추가되었습니다.', 'success')
        
        # 기존 게임 설정 업데이트
        elif 'update_game' in request.form:
            game_id = request.form.get('edit_id')
            games = read_csv(CSV_FILES['games_config'])
            updated_games = []
            
            for game in games:
                if game['id'] == game_id:
                    # 필수 필드는 직접 값을 할당
                    game['name'] = request.form.get('edit_name')
                    game['description'] = request.form.get('edit_description')
                    game['min_bet'] = request.form.get('edit_min_bet')
                    game['max_bet'] = request.form.get('edit_max_bet')
                    game['enabled'] = 'True' if request.form.get('edit_enabled') else 'False'
                    game['win_multiplier'] = request.form.get('edit_win_multiplier')
                    game['special_win_multiplier'] = request.form.get('edit_special_win_multiplier', '0')
                    game['draw_multiplier'] = request.form.get('edit_draw_multiplier', '1.0')
                    
                    # 값 검증
                    if not all([game['name'], game['min_bet'], game['max_bet'], game['win_multiplier']]):
                        flash('필수 입력값이 누락되었습니다.', 'error')
                        return redirect(url_for('admin.config_games'))
                        
                    # 숫자 필드 검증
                    try:
                        min_bet = int(game['min_bet'])
                        max_bet = int(game['max_bet'])
                        win_mult = float(game['win_multiplier'])
                        if min_bet < 0 or max_bet < min_bet or win_mult <= 0:
                            raise ValueError
                    except ValueError:
                        flash('베팅 금액과 승리 배수는 올바른 숫자여야 합니다.', 'error')
                        return redirect(url_for('admin.config_games'))
                        
                updated_games.append(game)
            
            update_csv(CSV_FILES['games_config'], updated_games)
            flash('게임 설정이 업데이트되었습니다.', 'success')
        
        # 게임 삭제
        elif 'delete_game' in request.form:
            game_id = request.form.get('delete_id')
            games = read_csv(CSV_FILES['games_config'])
            updated_games = [game for game in games if game['id'] != game_id]
            
            update_csv(CSV_FILES['games_config'], updated_games)
            flash('게임 설정이 삭제되었습니다.', 'success')
    
    # 게임 설정 불러오기
    games = get_games_config()
    
    return render_template('admin.html', section='config_games', games=games)

@admin_bp.route('/config/stocks', methods=['GET', 'POST'])
@admin_required
def config_stocks():
    """주식 설정 관리"""
    if request.method == 'POST':
        # 주식 설정 업데이트
        stock_id = request.form.get('id')
        name = request.form.get('name')
        code = request.form.get('code')
        sector = request.form.get('sector')
        initial_price = request.form.get('initial_price')
        min_price = request.form.get('min_price')
        max_price = request.form.get('max_price')
        volatility = request.form.get('volatility')
        description = request.form.get('description')
        
        # 새 주식 추가
        if stock_id and name and 'add_stock' in request.form:
            stocks = read_csv(CSV_FILES['stocks_config'])
            
            # 이미 존재하는 주식 ID 확인
            exists = False
            for stock in stocks:
                if stock['id'] == stock_id:
                    exists = True
                    break
            
            if exists:
                flash(f'이미 존재하는 주식 ID입니다: {stock_id}', 'error')
            else:
                new_stock = {
                    'id': stock_id,
                    'name': name,
                    'code': code or '',
                    'sector': sector or '',
                    'initial_price': initial_price or '10000',
                    'min_price': min_price or '1000',
                    'max_price': max_price or '100000',
                    'volatility': volatility or '5',
                    'description': description or ''
                }
                append_to_csv(CSV_FILES['stocks_config'], new_stock)
                flash('새 주식 설정이 추가되었습니다.', 'success')
                
                # 실시간 주식 테이블에도 추가
                live_stock = {
                    'id': stock_id,
                    'name': name,
                    'current_price': initial_price or '10000',
                    'previous_price': initial_price or '10000',
                    'change_percent': '0.0',
                    'last_update': get_timestamp()
                }
                append_to_csv(CSV_FILES['stocks'], live_stock)
        
        # 기존 주식 설정 업데이트
        elif 'update_stock' in request.form:
            stock_id = request.form.get('edit_id')
            stocks = read_csv(CSV_FILES['stocks_config'])
            updated_stocks = []
            
            for stock in stocks:
                if stock['id'] == stock_id:
                    stock['name'] = request.form.get('edit_name') or stock['name']
                    stock['code'] = request.form.get('edit_code') or stock['code']
                    stock['sector'] = request.form.get('edit_sector') or stock['sector']
                    stock['initial_price'] = request.form.get('edit_initial_price') or stock['initial_price']
                    stock['min_price'] = request.form.get('edit_min_price') or stock['min_price']
                    stock['max_price'] = request.form.get('edit_max_price') or stock['max_price']
                    stock['volatility'] = request.form.get('edit_volatility') or stock['volatility']
                    stock['description'] = request.form.get('edit_description') or stock['description']
                updated_stocks.append(stock)
            
            update_csv(CSV_FILES['stocks_config'], updated_stocks)
            flash('주식 설정이 업데이트되었습니다.', 'success')
            
            # 실시간 주식 테이블도 이름 업데이트
            live_stocks = read_csv(CSV_FILES['stocks'])
            updated_live_stocks = []
            for stock in live_stocks:
                if stock['id'] == stock_id:
                    stock['name'] = request.form.get('edit_name') or stock['name']
                updated_live_stocks.append(stock)
            update_csv(CSV_FILES['stocks'], updated_live_stocks)
    
    # 주식 설정 불러오기
    stocks_config = get_stocks_config()
    
    return render_template('admin.html', section='config_stocks', stocks=stocks_config)

@admin_bp.route('/simple_csv_editor')
@admin_bp.route('/simple_csv_editor/<file>')
@admin_required
def simple_csv_editor(file=None):
    """간단한 CSV 텍스트 편집기"""
    # CSV 파일 목록 가져오기
    csv_files = {key: path for key, path in CSV_FILES.items()}
    file_rows = {}
    
    # 각 파일의 행 수 계산
    for key, path in csv_files.items():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                file_rows[key] = sum(1 for _ in f) - 1  # 헤더 제외
        except:
            file_rows[key] = 0
    
    # 선택된 파일이 없거나 유효하지 않은 경우
    if file is None or file not in csv_files:
        return render_template('simple_csv_editor.html', 
                              csv_files=csv_files, 
                              file_rows=file_rows,
                              current_file=None,
                              csv_content=None)
    
    # 선택된 CSV 파일 내용 읽기
    try:
        with open(csv_files[file], 'r', encoding='utf-8') as f:
            csv_content = f.read()
        
        return render_template('simple_csv_editor.html', 
                              csv_files=csv_files, 
                              file_rows=file_rows,
                              current_file=file,
                              csv_content=csv_content)
    except Exception as e:
        flash(f'CSV 파일을 로드하는 중 오류가 발생했습니다: {str(e)}', 'error')
        return render_template('simple_csv_editor.html', 
                              csv_files=csv_files, 
                              file_rows=file_rows,
                              current_file=file,
                              csv_content=None)

@admin_bp.route('/save_simple_csv', methods=['POST'])
@admin_required
def save_simple_csv():
    """CSV 텍스트 저장"""
    import shutil
    
    file_name = request.form.get('file_name')
    csv_content = request.form.get('csv_content')
    
    if not file_name or file_name not in CSV_FILES:
        flash('유효하지 않은 파일 이름입니다.', 'error')
        return redirect(url_for('admin.simple_csv_editor'))
    
    try:
        # 백업 생성
        backup_file = f"{CSV_FILES[file_name]}.bak"
        shutil.copy2(CSV_FILES[file_name], backup_file)
        
        # 새 내용 저장
        with open(CSV_FILES[file_name], 'w', encoding='utf-8') as f:
            f.write(csv_content)
        
        flash(f'{file_name}.csv 파일이 성공적으로 저장되었습니다.', 'success')
        return redirect(url_for('admin.simple_csv_editor', file=file_name))
    except Exception as e:
        flash(f'CSV 파일 저장 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('admin.simple_csv_editor', file=file_name))
    
    
@admin_bp.route('/config/politicians', methods=['GET', 'POST'])
@admin_required
def config_politicians():
    """정치인 설정 관리"""
    if request.method == 'POST':
        # 정치인 설정 업데이트
        politician_id = request.form.get('id')
        name = request.form.get('name')
        party = request.form.get('party')
        power = request.form.get('power')
        special = request.form.get('special', 'False')
        image_url = request.form.get('image_url')
        description = request.form.get('description')
        
        # 새 정치인 추가
        if politician_id and name and 'add_politician' in request.form:
            politicians = read_csv(CSV_FILES['politicians'])
            
            # 이미 존재하는 정치인 ID 확인
            exists = False
            for politician in politicians:
                if politician['id'] == politician_id:
                    exists = True
                    break
            
            if exists:
                flash(f'이미 존재하는 정치인 ID입니다: {politician_id}', 'error')
            else:
                new_politician = {
                    'id': politician_id,
                    'name': name,
                    'party': party or '',
                    'power': power or '5',
                    'special': special,
                    'image_url': image_url or '',
                    'description': description or ''
                }
                append_to_csv(CSV_FILES['politicians'], new_politician)
                flash('새 정치인 설정이 추가되었습니다.', 'success')
        
        # 기존 정치인 설정 업데이트
        elif 'update_politician' in request.form:
            politician_id = request.form.get('edit_id')
            politicians = read_csv(CSV_FILES['politicians'])
            updated_politicians = []
            
            for politician in politicians:
                if politician['id'] == politician_id:
                    politician['name'] = request.form.get('edit_name') or politician['name']
                    politician['party'] = request.form.get('edit_party') or politician['party']
                    politician['power'] = request.form.get('edit_power') or politician['power']
                    politician['special'] = 'True' if request.form.get('edit_special') else 'False'
                    politician['image_url'] = request.form.get('edit_image_url') or politician['image_url']
                    politician['description'] = request.form.get('edit_description') or politician['description']
                updated_politicians.append(politician)
            
            update_csv(CSV_FILES['politicians'], updated_politicians)
            flash('정치인 설정이 업데이트되었습니다.', 'success')
        
        # 정치인 삭제
        elif 'delete_politician' in request.form:
            politician_id = request.form.get('delete_id')
            politicians = read_csv(CSV_FILES['politicians'])
            updated_politicians = [p for p in politicians if p['id'] != politician_id]
            
            update_csv(CSV_FILES['politicians'], updated_politicians)
            flash('정치인 설정이 삭제되었습니다.', 'success')
    
    # 정치인 설정 불러오기
    politicians = get_politicians()
    
    return render_template('admin.html', section='config_politicians', politicians=politicians)

@admin_bp.route('/config/market', methods=['GET', 'POST'])
@admin_required
def config_market():
    """마켓 아이템 설정 관리"""
    if request.method == 'POST':
        # 마켓 아이템 설정 업데이트
        item_id = request.form.get('id')
        name = request.form.get('name')
        effect = request.form.get('effect')
        price = request.form.get('price')
        duration = request.form.get('duration')
        max_uses = request.form.get('max_uses')
        category = request.form.get('category')
        description = request.form.get('description')
        image_url = request.form.get('image_url')
        
        # 새 아이템 추가
        if item_id and name and 'add_item' in request.form:
            items = read_csv(CSV_FILES['market_items'])
            
            # 이미 존재하는 아이템 ID 확인
            exists = False
            for item in items:
                if item['id'] == item_id:
                    exists = True
                    break
            
            if exists:
                flash(f'이미 존재하는 아이템 ID입니다: {item_id}', 'error')
            else:
                new_item = {
                    'id': item_id,
                    'name': name,
                    'effect': effect or '',
                    'price': price or '1000',
                    'duration': duration or '1',
                    'max_uses': max_uses or '1',
                    'category': category or '기타',
                    'description': description or '',
                    'image_url': image_url or ''
                }
                append_to_csv(CSV_FILES['market_items'], new_item)
                flash('새 마켓 아이템 설정이 추가되었습니다.', 'success')
                
                # 실제 아이템 테이블에도 추가
                real_item = {
                    'id': item_id,
                    'name': name,
                    'effect': effect or '',
                    'price': price or '1000',
                    'duration': duration or '1',
                    'max_uses': max_uses or '1'
                }
                append_to_csv(CSV_FILES['items'], real_item)
        
        # 기존 아이템 설정 업데이트
        elif 'update_item' in request.form:
            item_id = request.form.get('edit_id')
            items = read_csv(CSV_FILES['market_items'])
            updated_items = []
            
            for item in items:
                if item['id'] == item_id:
                    item['name'] = request.form.get('edit_name') or item['name']
                    item['effect'] = request.form.get('edit_effect') or item['effect']
                    item['price'] = request.form.get('edit_price') or item['price']
                    item['duration'] = request.form.get('edit_duration') or item['duration']
                    item['max_uses'] = request.form.get('edit_max_uses') or item['max_uses']
                    item['category'] = request.form.get('edit_category') or item['category']
                    item['description'] = request.form.get('edit_description') or item['description']
                    item['image_url'] = request.form.get('edit_image_url') or item['image_url']
                updated_items.append(item)
            
            update_csv(CSV_FILES['market_items'], updated_items)
            flash('마켓 아이템 설정이 업데이트되었습니다.', 'success')
            
            # 실제 아이템 테이블도 업데이트
            real_items = read_csv(CSV_FILES['items'])
            updated_real_items = []
            for item in real_items:
                if item['id'] == item_id:
                    item['name'] = request.form.get('edit_name') or item['name']
                    item['effect'] = request.form.get('edit_effect') or item['effect']
                    item['price'] = request.form.get('edit_price') or item['price']
                    item['duration'] = request.form.get('edit_duration') or item['duration']
                    item['max_uses'] = request.form.get('edit_max_uses') or item['max_uses']
                updated_real_items.append(item)
            update_csv(CSV_FILES['items'], updated_real_items)
    
    # 마켓 아이템 설정 불러오기
    market_items = get_market_items_config()
    
    return render_template('admin.html', section='config_market', items=market_items)

@admin_bp.route('/csv_editor', methods=['GET', 'POST'])
@admin_required
def csv_editor():
    """향상된 CSV 데이터 직접 편집 기능"""
    if request.method == 'POST':
        try:
            file_name = request.form.get('file_name')
            operation = request.form.get('operation')
            data = request.form.get('data')
            
            if operation == 'modify_row':
                # 행 수정
                row_data = json.loads(data)
                rows = read_csv(CSV_FILES[file_name])
                for row in rows:
                    if row.get('id') == row_data.get('id'):
                        row.update(row_data)
                update_csv(CSV_FILES[file_name], rows)
                flash('데이터가 성공적으로 수정되었습니다.', 'success')
                
            elif operation == 'delete_row':
                # 행 삭제
                row_id = data
                rows = read_csv(CSV_FILES[file_name])
                updated_rows = [row for row in rows if row.get('id') != row_id]
                update_csv(CSV_FILES[file_name], rows)
                flash('데이터가 삭제되었습니다.', 'success')
                
            elif operation == 'add_row':
                # 새 행 추가
                new_row = json.loads(data)
                new_row['id'] = generate_id()
                append_to_csv(CSV_FILES[file_name], new_row)
                flash('새 데이터가 추가되었습니다.', 'success')
                
            elif operation == 'backup':
                # 백업 생성
                backup_path = f"data/backups/{file_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                shutil.copy2(CSV_FILES[file_name], backup_path)
                flash('백업이 생성되었습니다.', 'success')
                
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    """CSV 파일 직접 편집 기능"""
    # 모든 CSV 파일 목록
    csv_files = [
        {'name': 'system_config', 'path': CSV_FILES['system_config'], 'description': '시스템 설정'},
        {'name': 'games_config', 'path': CSV_FILES['games_config'], 'description': '게임 설정'},
        {'name': 'stocks_config', 'path': CSV_FILES['stocks_config'], 'description': '주식 설정'},
        {'name': 'politicians', 'path': CSV_FILES['politicians'], 'description': '정치인 설정'},
        {'name': 'market_items', 'path': CSV_FILES['market_items'], 'description': '마켓 아이템 설정'},
        {'name': 'users', 'path': CSV_FILES['users'], 'description': '사용자 데이터'},
        {'name': 'transactions', 'path': CSV_FILES['transactions'], 'description': '거래 내역'},
        {'name': 'login_logs', 'path': CSV_FILES['login_logs'], 'description': '로그인 로그'},
        {'name': 'game_logs', 'path': CSV_FILES['game_logs'], 'description': '게임 로그'},
        {'name': 'market_logs', 'path': CSV_FILES['market_logs'], 'description': '마켓 로그'},
        {'name': 'notices', 'path': CSV_FILES['notices'], 'description': '공지사항'},
        {'name': 'chat_messages', 'path': CSV_FILES['chat_messages'], 'description': '채팅 메시지'},
        {'name': 'stocks', 'path': CSV_FILES['stocks'], 'description': '주식 데이터'},
        {'name': 'items', 'path': CSV_FILES['items'], 'description': '아이템 데이터'},
        {'name': 'achievements', 'path': CSV_FILES['achievements'], 'description': '업적 설정'},
        {'name': 'user_achievements', 'path': CSV_FILES['user_achievements'], 'description': '사용자 업적 데이터'},
        {'name': 'levels', 'path': CSV_FILES['levels'], 'description': '레벨 시스템 설정'},
        {'name': 'points', 'path': CSV_FILES['points'], 'description': '포인트 적립 규칙'},
        {'name': 'point_logs', 'path': CSV_FILES['point_logs'], 'description': '포인트 적립 내역'},
        {'name': 'quests', 'path': CSV_FILES['quests'], 'description': '퀘스트 설정'},
        {'name': 'user_quests', 'path': CSV_FILES['user_quests'], 'description': '사용자 퀘스트 진행 상황'},
        {'name': 'reward_items', 'path': CSV_FILES['reward_items'], 'description': '보상 아이템 설정'},
        {'name': 'friends', 'path': CSV_FILES['friends'], 'description': '친구 관계 데이터'},
        {'name': 'friend_activities', 'path': CSV_FILES['friend_activities'], 'description': '친구 활동 내역'}
    ]
    
    file_name = request.args.get('file')
    csv_data = None
    csv_headers = None
    
    if file_name and file_name in CSV_FILES:
        try:
            # CSV 파일 내용 읽기
            with open(CSV_FILES[file_name], 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                csv_headers = next(reader)  # 헤더
                csv_data = list(reader)     # 데이터
        except Exception as e:
            flash(f'CSV 파일을 읽는 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return render_template('admin.html', section='csv_editor', 
                          csv_files=csv_files, 
                          file_name=file_name,
                          csv_data=csv_data,
                          csv_headers=csv_headers)

@admin_bp.route('/csv_editor/save', methods=['POST'])
@admin_required
def save_csv():
    """CSV 파일 저장 기능"""
    file_name = request.form.get('file_name')
    csv_data = request.form.get('csv_data')
    
    if not file_name or file_name not in CSV_FILES:
        flash('유효하지 않은 파일 이름입니다.', 'error')
        return redirect(url_for('admin.csv_editor'))
    
    try:
        # JSON 문자열을 리스트로 변환
        data = json.loads(csv_data)
        headers = data[0]
        rows = data[1:]
        
        # CSV 파일로 저장
        with open(CSV_FILES[file_name], 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        
        flash(f'{file_name} 파일이 성공적으로 저장되었습니다.', 'success')
    except Exception as e:
        flash(f'CSV 파일을 저장하는 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('admin.csv_editor', file=file_name))

@admin_bp.route('/csv/get/<file_name>', methods=['GET'])
@admin_required
def get_csv_data(file_name):
    """CSV 파일 데이터 JSON 형식으로 반환 (AJAX용)"""
    if file_name not in CSV_FILES:
        return jsonify({'error': '유효하지 않은 파일 이름입니다.'}), 400
    
    try:
        with open(CSV_FILES[file_name], 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            data = list(reader)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 새로운 고급 관리자 기능들

@admin_bp.route('/backup_data', methods=['GET', 'POST'])
@admin_required
def backup_data():
    """데이터 백업 기능"""
    import shutil
    from datetime import datetime
    
    # 백업 결과 메시지
    backup_status = None
    backup_files = []
    
    # 백업 경로 설정
    backup_dir = os.path.join(os.path.dirname(__file__), 'data', 'backups')
    
    # 백업 디렉토리가 없으면 생성
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # 기존 백업 목록
    try:
        backup_list = sorted([d for d in os.listdir(backup_dir) if os.path.isdir(os.path.join(backup_dir, d))], reverse=True)
    except:
        backup_list = []
    
    if request.method == 'POST':
        try:
            # 백업 타임스탬프 (폴더명)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(backup_dir, timestamp)
            
            # 백업 디렉토리 생성
            os.makedirs(backup_path, exist_ok=True)
            
            # CSV 파일 백업
            for file_key, file_path in CSV_FILES.items():
                if os.path.exists(file_path):
                    dest_path = os.path.join(backup_path, os.path.basename(file_path))
                    shutil.copy2(file_path, dest_path)
                    backup_files.append(os.path.basename(file_path))
            
            backup_status = {
                'success': True,
                'timestamp': timestamp,
                'file_count': len(backup_files),
                'files': backup_files
            }
            
            flash(f'시스템 데이터 백업이 성공적으로 완료되었습니다. ({len(backup_files)}개 파일)', 'success')
            
            # 백업 목록 새로고침
            backup_list = sorted([d for d in os.listdir(backup_dir) if os.path.isdir(os.path.join(backup_dir, d))], reverse=True)
            
        except Exception as e:
            backup_status = {
                'success': False,
                'error': str(e)
            }
            flash(f'백업 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return render_template('admin_backup_data.html', 
                           section='backup_data', 
                           backup_status=backup_status,
                           backup_list=backup_list,
                           backup_dir=backup_dir)

@admin_bp.route('/restore_data', methods=['GET', 'POST'])
@admin_required
def restore_data():
    """데이터 복원 기능"""
    import shutil
    
    # 백업 경로 설정
    backup_dir = os.path.join(os.path.dirname(__file__), 'data', 'backups')
    
    # 백업 디렉토리가 없으면 생성
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # 기존 백업 목록
    try:
        backup_list = sorted([d for d in os.listdir(backup_dir) if os.path.isdir(os.path.join(backup_dir, d))], reverse=True)
    except:
        backup_list = []
    
    restore_status = None
    
    if request.method == 'POST':
        try:
            backup_id = request.form.get('backup_id')
            if not backup_id:
                flash('복원할 백업을 선택해주세요.', 'error')
                return redirect(url_for('admin.restore_data'))
            
            backup_path = os.path.join(backup_dir, backup_id)
            if not os.path.exists(backup_path):
                flash('선택한 백업이 존재하지 않습니다.', 'error')
                return redirect(url_for('admin.restore_data'))
            
            restored_files = []
            
            # 백업에서 CSV 파일 복원
            for file_name in os.listdir(backup_path):
                source_path = os.path.join(backup_path, file_name)
                
                # CSV_FILES에서 대상 경로 찾기
                for file_key, file_path in CSV_FILES.items():
                    if os.path.basename(file_path) == file_name:
                        shutil.copy2(source_path, file_path)
                        restored_files.append(file_name)
                        break
            
            restore_status = {
                'success': True,
                'backup_id': backup_id,
                'file_count': len(restored_files),
                'files': restored_files
            }
            
            flash(f'백업 데이터 복원이 성공적으로 완료되었습니다. ({len(restored_files)}개 파일)', 'success')
            
        except Exception as e:
            restore_status = {
                'success': False,
                'error': str(e)
            }
            flash(f'복원 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return render_template('admin_restore_data.html', 
                           section='restore_data', 
                           restore_status=restore_status,
                           backup_list=backup_list)

@admin_bp.route('/system/backup', methods=['POST'])
@superadmin_required
def backup_system():
    """시스템 전체 백업"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.join('data', 'backups', timestamp)
        os.makedirs(backup_dir, exist_ok=True)
        
        # 모든 CSV 파일 백업
        for file_name, file_path in CSV_FILES.items():
            if os.path.exists(file_path):
                shutil.copy2(file_path, os.path.join(backup_dir, os.path.basename(file_path)))
        
        # 백업 메타데이터 저장
        with open(os.path.join(backup_dir, 'metadata.json'), 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'admin_id': g.user['id'],
                'files': list(CSV_FILES.keys())
            }, f)
            
        flash('시스템 백업이 완료되었습니다.', 'success')
    except Exception as e:
        flash(f'백업 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('admin.system'))

@admin_bp.route('/system/restore/<timestamp>', methods=['POST'])
@superadmin_required
def restore_system(timestamp):
    """시스템 복원"""
    try:
        backup_dir = os.path.join('data', 'backups', timestamp)
        if not os.path.exists(backup_dir):
            flash('백업을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin.system'))
            
        # 백업 파일 복원
        for file_name, file_path in CSV_FILES.items():
            backup_file = os.path.join(backup_dir, os.path.basename(file_path))
            if os.path.exists(backup_file):
                shutil.copy2(backup_file, file_path)
                
        flash('시스템이 성공적으로 복원되었습니다.', 'success')
    except Exception as e:
        flash(f'복원 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('admin.system'))

@admin_bp.route('/api/settings', methods=['GET', 'POST'])
@admin_required
def api_settings():
    """API 설정 관리"""
    secrets = __import__('secrets')
    if request.method == 'POST':
        # API 키 생성
        if 'generate_key' in request.form:
            key = secrets.token_hex(32)
            expires_at = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
            append_to_csv(CSV_FILES['api_keys'], {
                'id': generate_id(),
                'key': key,
                'description': request.form.get('description'),
                'created_at': get_timestamp(),
                'expires_at': expires_at,
                'status': 'active'
            })
            flash('새 API 키가 생성되었습니다.', 'success')
            
    api_keys = read_csv(CSV_FILES['api_keys'])
    return render_template('admin_api_settings.html', section='api_settings', api_keys=api_keys)

@admin_bp.route('/security/settings', methods=['GET', 'POST'])
@admin_required
def security_settings():
    """보안 설정 관리"""
    if request.method == 'POST':
        # 보안 설정 업데이트
        update_system_config('password_min_length', request.form.get('password_min_length', '8'))
        update_system_config('login_attempts_limit', request.form.get('login_attempts_limit', '5'))
        update_system_config('session_timeout_minutes', request.form.get('session_timeout_minutes', '60'))
        update_system_config('require_2fa', 'True' if request.form.get('require_2fa') else 'False')
        
        flash('보안 설정이 업데이트되었습니다.', 'success')
        
    security_config = get_system_config()
    return render_template('admin_security_settings.html', section='security_settings', config=security_config)


@admin_bp.route('/system_logs', methods=['GET'])
@admin_required
def system_logs():
    """시스템 로그 조회"""
    import logging
    
    # 로그 파일 경로
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    log_file = os.path.join(log_dir, 'system.log')
    
    # 로그 디렉토리가 없으면 생성
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 로그 파일이 없으면 생성
    if not os.path.exists(log_file):
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"# 시스템 로그 파일 생성됨: {get_timestamp()}\n")
    
    # 로그 파일 내용 읽기
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.readlines()
        
        # 최대 1000줄만 표시
        if len(log_content) > 1000:
            log_content = log_content[-1000:]
    except:
        log_content = ['로그 파일을 읽을 수 없습니다.']
    
    return render_template('admin_system_logs.html', 
                           section='system_logs', 
                           log_content=log_content,
                           log_file=log_file)

@admin_bp.route('/api_management', methods=['GET', 'POST'])
@admin_required
def api_management():
    """API 설정 관리"""
    from secrets import token_hex
    
    # 시스템 설정 불러오기
    system_config = get_system_config()
    
    # API 관련 파일 경로
    api_keys_file = os.path.join('data', 'api_keys.csv')
    api_logs_file = os.path.join('data', 'api_logs.csv')
    api_clients_file = os.path.join('data', 'api_clients.csv')
    
    # API 키 파일이 없으면 생성
    if not os.path.exists(api_keys_file):
        with open(api_keys_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'key', 'client_id', 'description', 'created_at', 'expires_at', 'permissions', 'status', 'rate_limit', 'last_used'])
    
    # API 로그 파일이 없으면 생성
    if not os.path.exists(api_logs_file):
        with open(api_logs_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'timestamp', 'key_id', 'endpoint', 'client_ip', 'request_data', 'response_code', 'response_time'])
    
    # API 클라이언트 파일이 없으면 생성
    if not os.path.exists(api_clients_file):
        with open(api_clients_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'client_name', 'client_type', 'contact_email', 'contact_name', 'approved_by', 'approval_date', 'status', 'api_quota'])
    
    # API 키 목록 불러오기
    api_keys = read_csv(api_keys_file)
    
    # API 클라이언트 목록 불러오기
    api_clients = read_csv(api_clients_file)
    
    # API 로그 목록 불러오기 (최근 100건)
    api_logs = read_csv(api_logs_file)
    api_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    api_logs = api_logs[:100]
    
    if request.method == 'POST':
        if 'generate_key' in request.form:
            # 새 API 키 생성
            new_key = token_hex(24)  # 더 강력한 48자 키 생성
            description = request.form.get('description', '새 API 키')
            permissions = request.form.get('permissions', 'read')
            client_id = request.form.get('client_id', '')
            rate_limit = request.form.get('rate_limit', '100')  # 기본 분당 100 요청
            
            # 만료일 계산 (기본 1년)
            expiry_days = int(request.form.get('expiry_days', '365'))
            expires_at = ''
            if expiry_days > 0:
                expires_timestamp = datetime.now() + timedelta(days=expiry_days)
                expires_at = expires_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            
            # API 키 정보 저장
            api_key_info = {
                'id': generate_id(),
                'key': new_key,
                'client_id': client_id,
                'description': description,
                'created_at': get_timestamp(),
                'expires_at': expires_at,
                'permissions': permissions,
                'status': 'active',
                'rate_limit': rate_limit,
                'last_used': ''
            }
            
            # CSV 파일에 추가
            append_to_csv(api_keys_file, api_key_info)
            
            flash('새 API 키가 생성되었습니다.', 'success')
            return redirect(url_for('admin.api_settings'))
        
        elif 'revoke_key' in request.form:
            # API 키 취소
            key_id = request.form.get('key_id')
            
            if not key_id:
                flash('취소할 API 키 ID를 지정해주세요.', 'error')
            else:
                updated_keys = []
                for key in api_keys:
                    if key['id'] == key_id:
                        key['status'] = 'revoked'
                    updated_keys.append(key)
                
                # 변경된 API 키 목록 저장
                update_csv(api_keys_file, updated_keys)
                
                flash('API 키가 취소되었습니다.', 'success')
                return redirect(url_for('admin.api_settings'))
        
        elif 'add_client' in request.form:
            # 새 API 클라이언트 추가
            client_name = request.form.get('client_name', '')
            client_type = request.form.get('client_type', 'application')
            contact_email = request.form.get('contact_email', '')
            contact_name = request.form.get('contact_name', '')
            api_quota = request.form.get('api_quota', '10000')  # 기본 월 10,000 요청
            
            if not client_name or not contact_email:
                flash('클라이언트 이름과 연락처 이메일은 필수입니다.', 'error')
            else:
                # 클라이언트 정보 저장
                client_info = {
                    'id': generate_id(),
                    'client_name': client_name,
                    'client_type': client_type,
                    'contact_email': contact_email,
                    'contact_name': contact_name,
                    'approved_by': g.user['id'],
                    'approval_date': get_timestamp(),
                    'status': 'active',
                    'api_quota': api_quota
                }
                
                # CSV 파일에 추가
                append_to_csv(api_clients_file, client_info)
                
                flash('새 API 클라이언트가 추가되었습니다.', 'success')
                return redirect(url_for('admin.api_settings'))
        
        elif 'update_client' in request.form:
            # API 클라이언트 업데이트
            client_id = request.form.get('client_id')
            status = request.form.get('status')
            api_quota = request.form.get('api_quota')
            
            if not client_id:
                flash('업데이트할 클라이언트 ID를 지정해주세요.', 'error')
            else:
                updated_clients = []
                for client in api_clients:
                    if client['id'] == client_id:
                        if status:
                            client['status'] = status
                        if api_quota:
                            client['api_quota'] = api_quota
                    updated_clients.append(client)
                
                # 변경된 클라이언트 목록 저장
                update_csv(api_clients_file, updated_clients)
                
                flash('API 클라이언트가 업데이트되었습니다.', 'success')
                return redirect(url_for('admin.api_settings'))
        
        elif 'delete_client' in request.form:
            # API 클라이언트 삭제
            client_id = request.form.get('client_id')
            
            if not client_id:
                flash('삭제할 클라이언트 ID를 지정해주세요.', 'error')
            else:
                # 해당 클라이언트를 제외한 목록으로 업데이트
                updated_clients = [client for client in api_clients if client['id'] != client_id]
                update_csv(api_clients_file, updated_clients)
                
                # 연결된 API 키도 취소
                updated_keys = []
                for key in api_keys:
                    if key['client_id'] == client_id:
                        key['status'] = 'revoked'
                    updated_keys.append(key)
                
                update_csv(api_keys_file, updated_keys)
                
                flash('API 클라이언트가 삭제되었습니다. 연결된 모든 API 키가 취소되었습니다.', 'success')
                return redirect(url_for('admin.api_settings'))
        
        elif 'clear_logs' in request.form:
            # API 로그 초기화
            days = int(request.form.get('days', 30))
            
            if days <= 0:
                # 모든 로그 삭제
                with open(api_logs_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['id', 'timestamp', 'key_id', 'endpoint', 'client_ip', 'request_data', 'response_code', 'response_time'])
                flash('모든 API 로그가 초기화되었습니다.', 'success')
            else:
                # 특정 기간 이전 로그만 삭제
                cutoff_time = (datetime.now() - timedelta(days=days)).timestamp()
                updated_logs = []
                removed_count = 0
                
                for log in api_logs:
                    try:
                        log_time = datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S.%f').timestamp()
                    except:
                        try:
                            log_time = datetime.strptime(log['timestamp'].split('.')[0], '%Y-%m-%d %H:%M:%S').timestamp()
                        except:
                            # 날짜 변환 실패 시 보존
                            updated_logs.append(log)
                            continue
                    
                    if log_time > cutoff_time:
                        updated_logs.append(log)
                    else:
                        removed_count += 1
                
                update_csv(api_logs_file, updated_logs)
                flash(f'{days}일 이전의 API 로그가 삭제되었습니다. ({removed_count}건)', 'success')
            
            return redirect(url_for('admin.api_settings'))
        
        elif 'update_api_settings' in request.form:
            # API 전역 설정 업데이트
            api_enabled = 'True' if request.form.get('api_enabled') else 'False'
            api_rate_limit_global = request.form.get('api_rate_limit_global', '1000')
            api_require_key = 'True' if request.form.get('api_require_key') else 'False'
            api_allow_cors = 'True' if request.form.get('api_allow_cors') else 'False'
            api_cors_origins = request.form.get('api_cors_origins', '*')
            
            # 시스템 설정에 반영
            update_system_config('api_enabled', api_enabled)
            update_system_config('api_rate_limit_global', api_rate_limit_global)
            update_system_config('api_require_key', api_require_key)
            update_system_config('api_allow_cors', api_allow_cors)
            update_system_config('api_cors_origins', api_cors_origins)
            
            flash('API 설정이 업데이트되었습니다.', 'success')
            return redirect(url_for('admin.api_settings'))
    
    # API 통계 계산
    api_stats = {
        'total_keys': len(api_keys),
        'active_keys': sum(1 for key in api_keys if key.get('status') == 'active'),
        'revoked_keys': sum(1 for key in api_keys if key.get('status') == 'revoked'),
        'total_clients': len(api_clients),
        'active_clients': sum(1 for client in api_clients if client.get('status') == 'active'),
        'total_logs': len(api_logs),
        'error_logs': sum(1 for log in api_logs if log.get('response_code', '').startswith(('4', '5'))),
        'success_logs': sum(1 for log in api_logs if log.get('response_code', '').startswith(('2', '3')))
    }
    
    # API 설정 정보 가져오기
    api_enabled = system_config.get('api_enabled', 'False')
    api_rate_limit_global = system_config.get('api_rate_limit_global', '1000')
    api_require_key = system_config.get('api_require_key', 'True')
    api_allow_cors = system_config.get('api_allow_cors', 'False')
    api_cors_origins = system_config.get('api_cors_origins', '*')
    
    return render_template('admin_api_settings.html', 
                           section='api_settings', 
                           api_keys=api_keys,
                           api_clients=api_clients,
                           api_logs=api_logs,
                           api_stats=api_stats,
                           api_enabled=api_enabled,
                           api_rate_limit_global=api_rate_limit_global,
                           api_require_key=api_require_key,
                           api_allow_cors=api_allow_cors,
                           api_cors_origins=api_cors_origins,
                           system_config=system_config)

@admin_bp.route('/security_management', methods=['GET', 'POST'])
@admin_required
def security_management():
    """보안 설정 관리"""
    import time
    
    # 보안 로그 파일 경로
    security_logs_file = os.path.join('data', 'security_logs.csv')
    
    # 보안 로그 파일이 없으면 생성
    if not os.path.exists(security_logs_file):
        with open(security_logs_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'timestamp', 'user_id', 'action', 'ip', 'details'])
    
    # IP 화이트리스트 파일 경로
    ip_whitelist_file = os.path.join('data', 'ip_whitelist.csv')
    
    # IP 화이트리스트 파일이 없으면 생성
    if not os.path.exists(ip_whitelist_file):
        with open(ip_whitelist_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'ip', 'description', 'added_by', 'added_at'])
    
    # IP 블랙리스트 파일 경로
    ip_blacklist_file = os.path.join('data', 'ip_blacklist.csv')
    
    # IP 블랙리스트 파일이 없으면 생성
    if not os.path.exists(ip_blacklist_file):
        with open(ip_blacklist_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'ip', 'reason', 'blocked_by', 'blocked_at', 'duration', 'expires_at'])
    
    # 시스템 설정 불러오기
    system_config = get_system_config()
    
    if request.method == 'POST':
        if 'update_basic_security' in request.form:
            # 기본 보안 설정 업데이트
            password_min_length = request.form.get('password_min_length', '4')
            require_captcha = 'True' if request.form.get('require_captcha') else 'False'
            max_login_attempts = request.form.get('max_login_attempts', '5')
            session_expire_minutes = request.form.get('session_expire_minutes', '30')
            require_email_verification = 'True' if request.form.get('require_email_verification') else 'False'
            block_ip_after_attempts = request.form.get('block_ip_after_attempts', '10')
            ip_block_duration = request.form.get('ip_block_duration', '1440')  # 단위: 분 (기본 24시간)
            
            # 시스템 설정에 반영
            updates = {
                'password_min_length': password_min_length,
                'require_captcha': require_captcha,
                'max_login_attempts': max_login_attempts,
                'session_expire_minutes': session_expire_minutes,
                'require_email_verification': require_email_verification,
                'block_ip_after_attempts': block_ip_after_attempts,
                'ip_block_duration': ip_block_duration
            }
            
            for key, value in updates.items():
                update_system_config(key, value)
            
            # 보안 로그 추가
            append_to_csv(security_logs_file, {
                'id': generate_id(),
                'timestamp': get_timestamp(),
                'user_id': g.user['id'],
                'action': 'update_security',
                'ip': request.remote_addr,
                'details': '기본 보안 설정 업데이트'
            })
            
            flash('기본 보안 설정이 업데이트되었습니다.', 'success')
        
        elif 'update_advanced_security' in request.form:
            # 고급 보안 설정 업데이트
            enable_2fa = 'True' if request.form.get('enable_2fa') else 'False'
            password_expiry_days = request.form.get('password_expiry_days', '0')  # 0은 비밀번호 만료 없음
            enforce_password_policy = 'True' if request.form.get('enforce_password_policy') else 'False'
            require_special_chars = 'True' if request.form.get('require_special_chars') else 'False'
            require_numbers = 'True' if request.form.get('require_numbers') else 'False'
            require_uppercase = 'True' if request.form.get('require_uppercase') else 'False'
            
            # 시스템 설정에 반영
            updates = {
                'enable_2fa': enable_2fa,
                'password_expiry_days': password_expiry_days,
                'enforce_password_policy': enforce_password_policy,
                'require_special_chars': require_special_chars,
                'require_numbers': require_numbers,
                'require_uppercase': require_uppercase
            }
            
            for key, value in updates.items():
                update_system_config(key, value)
            
            # 보안 로그 추가
            append_to_csv(security_logs_file, {
                'id': generate_id(),
                'timestamp': get_timestamp(),
                'user_id': g.user['id'],
                'action': 'update_security',
                'ip': request.remote_addr,
                'details': '고급 보안 설정 업데이트'
            })
            
            flash('고급 보안 설정이 업데이트되었습니다.', 'success')
        
        elif 'whitelist_ip' in request.form:
            # IP 화이트리스트 추가
            ip_address = request.form.get('ip_address', '')
            description = request.form.get('ip_description', '관리자 추가')
            
            # IP 추가
            append_to_csv(ip_whitelist_file, {
                'id': generate_id(),
                'ip': ip_address,
                'description': description,
                'added_by': g.user['id'],
                'added_at': get_timestamp()
            })
            
            # 보안 로그 추가
            append_to_csv(security_logs_file, {
                'id': generate_id(),
                'timestamp': get_timestamp(),
                'user_id': g.user['id'],
                'action': 'whitelist_ip',
                'ip': request.remote_addr,
                'details': f'IP 화이트리스트 추가: {ip_address} ({description})'
            })
            
            flash(f'IP 주소 {ip_address}가 화이트리스트에 추가되었습니다.', 'success')
        
        elif 'blacklist_ip' in request.form:
            # IP 블랙리스트 추가
            ip_address = request.form.get('ip_address', '')
            reason = request.form.get('ip_reason', '관리자 차단')
            duration = request.form.get('ip_block_duration', '0')  # 0은 영구 차단
            
            # 만료 시간 계산
            expires_at = ''
            if int(duration) > 0:
                expires_timestamp = time.time() + (int(duration) * 60)
                expires_at = datetime.fromtimestamp(expires_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            # IP 추가
            append_to_csv(ip_blacklist_file, {
                'id': generate_id(),
                'ip': ip_address,
                'reason': reason,
                'blocked_by': g.user['id'],
                'blocked_at': get_timestamp(),
                'duration': duration,
                'expires_at': expires_at
            })
            
            # 보안 로그 추가
            append_to_csv(security_logs_file, {
                'id': generate_id(),
                'timestamp': get_timestamp(),
                'user_id': g.user['id'],
                'action': 'blacklist_ip',
                'ip': request.remote_addr,
                'details': f'IP 블랙리스트 추가: {ip_address} ({reason})'
            })
            
            flash(f'IP 주소 {ip_address}가 블랙리스트에 추가되었습니다.', 'success')
        
        elif 'remove_ip_whitelist' in request.form:
            # IP 화이트리스트에서 제거
            ip_id = request.form.get('ip_id')
            
            # 현재 화이트리스트 불러오기
            whitelist = read_csv(ip_whitelist_file)
            
            # 제거할 IP 정보 찾기
            ip_info = next((ip for ip in whitelist if ip['id'] == ip_id), None)
            
            if ip_info:
                # 해당 ID를 제외한 목록으로 업데이트
                updated_whitelist = [ip for ip in whitelist if ip['id'] != ip_id]
                update_csv(ip_whitelist_file, updated_whitelist)
                
                # 보안 로그 추가
                append_to_csv(security_logs_file, {
                    'id': generate_id(),
                    'timestamp': get_timestamp(),
                    'user_id': g.user['id'],
                    'action': 'remove_whitelist_ip',
                    'ip': request.remote_addr,
                    'details': f'IP 화이트리스트 제거: {ip_info.get("ip")}'
                })
                
                flash('IP 주소가 화이트리스트에서 제거되었습니다.', 'success')
            else:
                flash('해당 IP 정보를 찾을 수 없습니다.', 'error')
        
        elif 'remove_ip_blacklist' in request.form:
            # IP 블랙리스트에서 제거
            ip_id = request.form.get('ip_id')
            
            # 현재 블랙리스트 불러오기
            blacklist = read_csv(ip_blacklist_file)
            
            # 제거할 IP 정보 찾기
            ip_info = next((ip for ip in blacklist if ip['id'] == ip_id), None)
            
            if ip_info:
                # 해당 ID를 제외한 목록으로 업데이트
                updated_blacklist = [ip for ip in blacklist if ip['id'] != ip_id]
                update_csv(ip_blacklist_file, updated_blacklist)
                
                # 보안 로그 추가
                append_to_csv(security_logs_file, {
                    'id': generate_id(),
                    'timestamp': get_timestamp(),
                    'user_id': g.user['id'],
                    'action': 'remove_blacklist_ip',
                    'ip': request.remote_addr,
                    'details': f'IP 블랙리스트 제거: {ip_info.get("ip")}'
                })
                
                flash('IP 주소가 블랙리스트에서 제거되었습니다.', 'success')
            else:
                flash('해당 IP 정보를 찾을 수 없습니다.', 'error')
        
        elif 'reset_failed_attempts' in request.form:
            # 실패한 로그인 시도 초기화
            
            # 로그인 로그 파일 불러오기
            login_logs = read_csv(CSV_FILES['login_logs'])
            
            # 로그에서 실패한 로그인 시도만 카운트
            failed_count = sum(1 for log in login_logs if log.get('status') == 'failed')
            
            # CSV 파일 업데이트 (실패 로그 제거)
            updated_logs = [log for log in login_logs if log.get('status') != 'failed']
            update_csv(CSV_FILES['login_logs'], updated_logs)
            
            # 보안 로그 추가
            append_to_csv(security_logs_file, {
                'id': generate_id(),
                'timestamp': get_timestamp(),
                'user_id': g.user['id'],
                'action': 'reset_failed_attempts',
                'ip': request.remote_addr,
                'details': f'모든 로그인 실패 시도 초기화 ({failed_count}건)'
            })
            
            flash(f'모든 실패한 로그인 시도가 초기화되었습니다. ({failed_count}건)', 'success')
        
        elif 'clear_security_logs' in request.form:
            # 보안 로그 초기화
            with open(security_logs_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'timestamp', 'user_id', 'action', 'ip', 'details'])
            
            flash('보안 로그가 초기화되었습니다.', 'success')
        
        # 최신 설정 다시 불러오기
        system_config = get_system_config()
    
    # 현재 설정 값 가져오기
    password_min_length = system_config.get('password_min_length', '4')
    require_captcha = system_config.get('require_captcha', 'False')
    max_login_attempts = system_config.get('max_login_attempts', '5')
    session_expire_minutes = system_config.get('session_expire_minutes', '30')
    require_email_verification = system_config.get('require_email_verification', 'False')
    block_ip_after_attempts = system_config.get('block_ip_after_attempts', '10')
    ip_block_duration = system_config.get('ip_block_duration', '1440')
    
    # 고급 보안 설정
    enable_2fa = system_config.get('enable_2fa', 'False')
    password_expiry_days = system_config.get('password_expiry_days', '0')
    enforce_password_policy = system_config.get('enforce_password_policy', 'False')
    require_special_chars = system_config.get('require_special_chars', 'False')
    require_numbers = system_config.get('require_numbers', 'False')
    require_uppercase = system_config.get('require_uppercase', 'False')
    
    # IP 화이트리스트 불러오기
    ip_whitelist = read_csv(ip_whitelist_file)
    
    # IP 블랙리스트 불러오기
    ip_blacklist = read_csv(ip_blacklist_file)
    
    # 보안 로그 불러오기
    security_logs = read_csv(security_logs_file)
    # 최신 로그가 위에 오도록 정렬
    security_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    # 최대 100개만 표시
    security_logs = security_logs[:100]
    
    # 로그인 실패 통계
    login_logs = read_csv(CSV_FILES['login_logs'])
    failed_logins = [log for log in login_logs if log.get('status') == 'failed']
    failed_login_count = len(failed_logins)
    
    # IP별 실패 횟수 계산
    ip_failure_count = {}
    for log in failed_logins:
        ip = log.get('ip', 'unknown')
        ip_failure_count[ip] = ip_failure_count.get(ip, 0) + 1
    
    # 가장 실패 횟수가 많은 IP 추출 (최대 10개)
    suspicious_ips = sorted(ip_failure_count.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return render_template('admin_security_settings.html', 
                           section='security_settings', 
                           system_config=system_config,
                           password_min_length=password_min_length,
                           require_captcha=require_captcha,
                           max_login_attempts=max_login_attempts,
                           session_expire_minutes=session_expire_minutes,
                           require_email_verification=require_email_verification,
                           block_ip_after_attempts=block_ip_after_attempts,
                           ip_block_duration=ip_block_duration,
                           enable_2fa=enable_2fa,
                           password_expiry_days=password_expiry_days,
                           enforce_password_policy=enforce_password_policy,
                           require_special_chars=require_special_chars,
                           require_numbers=require_numbers,
                           require_uppercase=require_uppercase,
                           ip_whitelist=ip_whitelist,
                           ip_blacklist=ip_blacklist,
                           security_logs=security_logs,
                           failed_login_count=failed_login_count,
                           suspicious_ips=suspicious_ips)

@admin_bp.route('/batch_operations', methods=['GET', 'POST'])
@admin_required
def batch_operations():
    """일괄 작업 관리"""
    import time
    
    # 시스템 설정 불러오기
    system_config = get_system_config()
    
    # 배치 작업 로그 파일 경로
    batch_logs_file = os.path.join('data', 'batch_logs.csv')
    
    # 배치 작업 로그 파일이 없으면 생성
    if not os.path.exists(batch_logs_file):
        with open(batch_logs_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'timestamp', 'admin_id', 'operation', 'details', 'affected_count', 'status', 'duration'])
    
    # 작업 결과
    batch_result = None
    
    if request.method == 'POST':
        operation = request.form.get('operation')
        
        # 작업 시작 시간
        start_time = time.time()
        
        if operation == 'reset_daily_bonuses':
            # 모든 사용자의 일일 보너스 초기화
            users = read_csv(CSV_FILES['users'])
            updated_users = []
            
            for user in users:
                user['last_bonus'] = ''  # 마지막 보너스 날짜 초기화
                updated_users.append(user)
            
            update_csv(CSV_FILES['users'], updated_users)
            
            # 작업 종료 시간 및 소요 시간
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            
            # 작업 로그 추가
            append_to_csv(batch_logs_file, {
                'id': generate_id(),
                'timestamp': get_timestamp(),
                'admin_id': g.user['id'],
                'operation': 'reset_daily_bonuses',
                'details': '일일 보너스 초기화',
                'affected_count': str(len(users)),
                'status': 'success',
                'duration': str(duration)
            })
            
            batch_result = {
                'operation': '일일 보너스 초기화',
                'affected_users': len(users),
                'duration': duration,
                'success': True
            }
            
            flash(f'모든 사용자({len(users)}명)의 일일 보너스가 초기화되었습니다. (소요 시간: {duration}초)', 'success')
        
        elif operation == 'add_bonus_all':
            # 모든 사용자에게 보너스 지급
            amount = int(request.form.get('bonus_amount', 0))
            description = request.form.get('bonus_description', '관리자 보너스')
            
            if amount <= 0:
                flash('유효한 보너스 금액을 입력해주세요.', 'error')
            else:
                users = read_csv(CSV_FILES['users'])
                updated_count = 0
                
                for user in users:
                    # 관리자에게는 지급하지 않음
                    if user['is_admin'] != 'True':
                        # 사용자 잔액 업데이트
                        update_user_balance(user['id'], amount, "add")
                        
                        # 거래 기록 추가
                        add_transaction('system', user['id'], amount, 'admin_bonus')
                        updated_count += 1
                
                batch_result = {
                    'operation': '전체 사용자 보너스 지급',
                    'amount': amount,
                    'affected_users': updated_count,
                    'description': description,
                    'success': True
                }
                
                flash(f'모든 사용자({updated_count}명)에게 {amount}{system_config.get("currency_name", "체스머니")}가 지급되었습니다.', 'success')
        
        elif operation == 'reset_stock_prices':
            # 모든 주식 가격 초기화
            stocks = read_csv(CSV_FILES['stocks'])
            stocks_config = get_stocks_config()
            
            # 주식 설정을 ID로 매핑
            config_map = {}
            for config in stocks_config:
                config_map[config['id']] = config
            
            updated_stocks = []
            
            for stock in stocks:
                stock_id = stock['id']
                
                # 해당 주식의 설정 정보 가져오기
                if stock_id in config_map:
                    initial_price = config_map[stock_id].get('initial_price', '10000')
                    stock['current_price'] = initial_price
                    stock['previous_price'] = initial_price
                    stock['change_percent'] = '0.00'
                
                updated_stocks.append(stock)
            
            update_csv(CSV_FILES['stocks'], updated_stocks)
            
            # 작업 종료 시간 및 소요 시간
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            
            # 작업 로그 추가
            append_to_csv(batch_logs_file, {
                'id': generate_id(),
                'timestamp': get_timestamp(),
                'admin_id': g.user['id'],
                'operation': 'reset_stock_prices',
                'details': '주식 가격 초기화',
                'affected_count': str(len(updated_stocks)),
                'status': 'success',
                'duration': str(duration)
            })
            
            batch_result = {
                'operation': '주식 가격 초기화',
                'affected_stocks': len(updated_stocks),
                'duration': duration,
                'success': True
            }
            
            flash(f'모든 주식({len(updated_stocks)}개)의 가격이 초기화되었습니다. (소요 시간: {duration}초)', 'success')
        
        elif operation == 'add_points_all':
            # 모든 사용자에게 포인트 지급
            points = int(request.form.get('points_amount', 0))
            reason = request.form.get('points_reason', '관리자 포인트 부여')
            
            if points <= 0:
                flash('유효한 포인트 금액을 입력해주세요.', 'error')
            else:
                users = read_csv(CSV_FILES['users'])
                affected_users = 0
                
                for user in users:
                    # 관리자 제외 (선택적)
                    if request.form.get('exclude_admins') and user['is_admin'] == 'True':
                        continue
                    
                    # 포인트 추가
                    add_points(user['id'], points, reason)
                    affected_users += 1
                
                # 작업 종료 시간 및 소요 시간
                end_time = time.time()
                duration = round(end_time - start_time, 2)
                
                # 작업 로그 추가
                append_to_csv(batch_logs_file, {
                    'id': generate_id(),
                    'timestamp': get_timestamp(),
                    'admin_id': g.user['id'],
                    'operation': 'add_points_all',
                    'details': f'일괄 포인트 지급: {points}점, 이유: {reason}',
                    'affected_count': str(affected_users),
                    'status': 'success',
                    'duration': str(duration)
                })
                
                batch_result = {
                    'operation': '일괄 포인트 지급',
                    'points': points,
                    'affected_users': affected_users,
                    'duration': duration,
                    'success': True
                }
                
                flash(f'총 {affected_users}명의 사용자에게 {points} 포인트가 지급되었습니다. (소요 시간: {duration}초)', 'success')
        
        elif operation == 'reset_achievements':
            # 특정 업적 또는 모든 업적 진행 상황 초기화
            achievement_code = request.form.get('achievement_code', '')
            
            user_achievements = read_csv(CSV_FILES['user_achievements'])
            
            if achievement_code:
                # 특정 업적만 초기화
                updated_achievements = [ua for ua in user_achievements if ua['achievement_code'] != achievement_code]
                affected_count = len(user_achievements) - len(updated_achievements)
                details = f'특정 업적 초기화: {achievement_code}'
            else:
                # 모든 업적 초기화
                updated_achievements = []
                affected_count = len(user_achievements)
                details = '모든 업적 초기화'
            
            # 빈 헤더가 있는 파일로 초기화
            if not updated_achievements:
                with open(CSV_FILES['user_achievements'], 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['id', 'user_id', 'achievement_code', 'progress', 'completed', 'completed_at'])
            else:
                update_csv(CSV_FILES['user_achievements'], updated_achievements)
            
            # 작업 종료 시간 및 소요 시간
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            
            # 작업 로그 추가
            append_to_csv(batch_logs_file, {
                'id': generate_id(),
                'timestamp': get_timestamp(),
                'admin_id': g.user['id'],
                'operation': 'reset_achievements',
                'details': details,
                'affected_count': str(affected_count),
                'status': 'success',
                'duration': str(duration)
            })
            
            batch_result = {
                'operation': '업적 초기화',
                'achievement_code': achievement_code if achievement_code else '모든 업적',
                'affected_records': affected_count,
                'duration': duration,
                'success': True
            }
            
            flash(f'업적이 초기화되었습니다. ({affected_count}건) (소요 시간: {duration}초)', 'success')
        
        elif operation == 'reset_quests':
            # 퀘스트 진행 상황 초기화
            user_quests = read_csv(CSV_FILES['user_quests'])
            quest_type = request.form.get('quest_type', 'all')
            
            if quest_type == 'daily':
                # 일일 퀘스트만 초기화
                updated_quests = [uq for uq in user_quests if not uq.get('quest_type') or uq.get('quest_type') != 'daily']
                affected_count = len(user_quests) - len(updated_quests)
                details = '일일 퀘스트 초기화'
            elif quest_type == 'weekly':
                # 주간 퀘스트만 초기화
                updated_quests = [uq for uq in user_quests if not uq.get('quest_type') or uq.get('quest_type') != 'weekly']
                affected_count = len(user_quests) - len(updated_quests)
                details = '주간 퀘스트 초기화'
            else:
                # 모든 퀘스트 초기화
                updated_quests = []
                affected_count = len(user_quests)
                details = '모든 퀘스트 초기화'
            
            # 업데이트 또는 빈 파일로 초기화
            if not updated_quests:
                with open(CSV_FILES['user_quests'], 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['id', 'user_id', 'quest_id', 'progress', 'completed', 'completed_at', 'quest_type'])
            else:
                update_csv(CSV_FILES['user_quests'], updated_quests)
            
            # 작업 종료 시간 및 소요 시간
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            
            # 작업 로그 추가
            append_to_csv(batch_logs_file, {
                'id': generate_id(),
                'timestamp': get_timestamp(),
                'admin_id': g.user['id'],
                'operation': 'reset_quests',
                'details': details,
                'affected_count': str(affected_count),
                'status': 'success',
                'duration': str(duration)
            })
            
            batch_result = {
                'operation': '퀘스트 초기화',
                'quest_type': '일일' if quest_type == 'daily' else '주간' if quest_type == 'weekly' else '모든',
                'affected_records': affected_count,
                'duration': duration,
                'success': True
            }
            
            flash(f'퀘스트가 초기화되었습니다. ({affected_count}건) (소요 시간: {duration}초)', 'success')
        
        elif operation == 'cleanup_old_logs':
            # 오래된 로그 정리
            days = int(request.form.get('days', 30))
            log_type = request.form.get('log_type', 'all')
            
            if days <= 0:
                flash('유효한 일수를 입력해주세요.', 'error')
            else:
                # 기준 시간 (n일 전)
                cutoff_time = (datetime.now() - timedelta(days=days)).timestamp()
                
                affected_count = 0
                details = f'{days}일 이전 로그 정리'
                
                if log_type == 'login' or log_type == 'all':
                    # 로그인 로그 정리
                    login_logs = read_csv(CSV_FILES['login_logs'])
                    updated_logs = []
                    
                    for log in login_logs:
                        # 타임스탬프를 날짜 객체로 변환
                        try:
                            log_time = datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S.%f').timestamp()
                        except:
                            try:
                                log_time = datetime.strptime(log['timestamp'].split('.')[0], '%Y-%m-%d %H:%M:%S').timestamp()
                            except:
                                # 날짜 변환 실패 시 보존
                                updated_logs.append(log)
                                continue
                        
                        if log_time > cutoff_time:
                            updated_logs.append(log)
                    
                    removed_count = len(login_logs) - len(updated_logs)
                    affected_count += removed_count
                    
                    update_csv(CSV_FILES['login_logs'], updated_logs)
                    details += f', 로그인 로그: {removed_count}건 제거'
                
                if log_type == 'game' or log_type == 'all':
                    # 게임 로그 정리
                    game_logs = read_csv(CSV_FILES['game_logs'])
                    updated_logs = []
                    
                    for log in game_logs:
                        # 타임스탬프를 날짜 객체로 변환
                        try:
                            log_time = datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S.%f').timestamp()
                        except:
                            try:
                                log_time = datetime.strptime(log['timestamp'].split('.')[0], '%Y-%m-%d %H:%M:%S').timestamp()
                            except:
                                # 날짜 변환 실패 시 보존
                                updated_logs.append(log)
                                continue
                        
                        if log_time > cutoff_time:
                            updated_logs.append(log)
                    
                    removed_count = len(game_logs) - len(updated_logs)
                    affected_count += removed_count
                    
                    update_csv(CSV_FILES['game_logs'], updated_logs)
                    details += f', 게임 로그: {removed_count}건 제거'
                
                if log_type == 'market' or log_type == 'all':
                    # 마켓 로그 정리
                    market_logs = read_csv(CSV_FILES['market_logs'])
                    updated_logs = []
                    
                    for log in market_logs:
                        # 타임스탬프를 날짜 객체로 변환
                        try:
                            log_time = datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S.%f').timestamp()
                        except:
                            try:
                                log_time = datetime.strptime(log['timestamp'].split('.')[0], '%Y-%m-%d %H:%M:%S').timestamp()
                            except:
                                # 날짜 변환 실패 시 보존
                                updated_logs.append(log)
                                continue
                        
                        if log_time > cutoff_time:
                            updated_logs.append(log)
                    
                    removed_count = len(market_logs) - len(updated_logs)
                    affected_count += removed_count
                    
                    update_csv(CSV_FILES['market_logs'], updated_logs)
                    details += f', 마켓 로그: {removed_count}건 제거'
                
                # 작업 종료 시간 및 소요 시간
                end_time = time.time()
                duration = round(end_time - start_time, 2)
                
                # 작업 로그 추가
                append_to_csv(batch_logs_file, {
                    'id': generate_id(),
                    'timestamp': get_timestamp(),
                    'admin_id': g.user['id'],
                    'operation': 'cleanup_logs',
                    'details': details,
                    'affected_count': str(affected_count),
                    'status': 'success',
                    'duration': str(duration)
                })
                
                batch_result = {
                    'operation': '로그 정리',
                    'days': days,
                    'log_type': log_type,
                    'affected_records': affected_count,
                    'duration': duration,
                    'success': True
                }
                
                flash(f'{days}일 이전의 로그가 정리되었습니다. (총 {affected_count}건) (소요 시간: {duration}초)', 'success')
        
        elif operation == 'backup_data':
            # 데이터 백업
            backup_dir = os.path.join('data', 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            # 타임스탬프로 백업 폴더 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(backup_dir, f'backup_{timestamp}')
            os.makedirs(backup_path, exist_ok=True)
            
            # 모든 CSV 파일 백업
            backed_up_files = []
            for file_name, file_path in CSV_FILES.items():
                if os.path.exists(file_path):
                    backup_file = os.path.join(backup_path, os.path.basename(file_path))
                    shutil.copy2(file_path, backup_file)
                    backed_up_files.append(file_name)
            
            # 백업 정보 저장
            backup_info = {
                'id': generate_id(),
                'timestamp': get_timestamp(),
                'admin_id': g.user['id'],
                'files': ','.join(backed_up_files),
                'path': backup_path,
                'size': sum(os.path.getsize(os.path.join(backup_path, f)) for f in os.listdir(backup_path) if os.path.isfile(os.path.join(backup_path, f)))
            }
            
            # 백업 목록 파일
            backup_list_file = os.path.join('data', 'backup_list.csv')
            
            # 백업 목록 파일이 없으면 생성
            if not os.path.exists(backup_list_file):
                with open(backup_list_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['id', 'timestamp', 'admin_id', 'files', 'path', 'size'])
            
            # 백업 정보 추가
            append_to_csv(backup_list_file, backup_info)
            
            # 작업 종료 시간 및 소요 시간
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            
            # 작업 로그 추가
            append_to_csv(batch_logs_file, {
                'id': generate_id(),
                'timestamp': get_timestamp(),
                'admin_id': g.user['id'],
                'operation': 'backup_data',
                'details': f'데이터 백업: {len(backed_up_files)}개 파일',
                'affected_count': str(len(backed_up_files)),
                'status': 'success',
                'duration': str(duration)
            })
            
            batch_result = {
                'operation': '데이터 백업',
                'backup_path': backup_path,
                'backed_up_files': len(backed_up_files),
                'duration': duration,
                'success': True
            }
            
            flash(f'데이터가 성공적으로 백업되었습니다. ({len(backed_up_files)}개 파일, 소요 시간: {duration}초)', 'success')
    
    # 배치 작업 로그 불러오기
    batch_logs = read_csv(batch_logs_file)
    # 최신 로그가 위에 오도록 정렬
    batch_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    # 최대 20개만 표시
    batch_logs = batch_logs[:20]
    
    # 업적 목록 불러오기 (선택적인 업적 초기화용)
    achievements = read_csv(CSV_FILES['achievements'])
    
    # 각종 통계
    stats = {}
    
    # 사용자 수
    users = read_csv(CSV_FILES['users'])
    stats['total_users'] = len(users)
    stats['admin_users'] = sum(1 for user in users if user.get('is_admin') == 'True')
    stats['regular_users'] = stats['total_users'] - stats['admin_users']
    
    # 현재 일일 보너스 상태
    today = datetime.now().strftime('%Y-%m-%d')
    stats['daily_bonus_claimed'] = sum(1 for user in users if user.get('last_bonus', '').startswith(today))
    
    # 퀘스트 상태
    quests = read_csv(CSV_FILES['quests'])
    user_quests = read_csv(CSV_FILES['user_quests'])
    
    stats['total_quests'] = len(quests)
    stats['daily_quests'] = sum(1 for quest in quests if quest.get('type') == 'daily')
    stats['weekly_quests'] = sum(1 for quest in quests if quest.get('type') == 'weekly')
    stats['completed_quests'] = sum(1 for uq in user_quests if uq.get('completed') == 'True')
    
    # 백업 목록 불러오기
    backup_list_file = os.path.join('data', 'backup_list.csv')
    backups = []
    if os.path.exists(backup_list_file):
        backups = read_csv(backup_list_file)
        # 최신 백업이 위에 오도록 정렬
        backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        # 최대 5개만 표시
        backups = backups[:5]
    
    return render_template('admin_batch_operations.html', 
                           section='batch_operations', 
                           batch_result=batch_result,
                           batch_logs=batch_logs,
                           achievements=achievements,
                           stats=stats,
                           backups=backups,
                           system_config=system_config)

# 업적 수동 수여
@admin_bp.route('/achievements/award', methods=['POST'])
@admin_required
def award_achievement():
    """사용자에게 업적 수동 수여"""
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        achievement_code = request.form.get('achievement_code')
        
        if not user_id or not achievement_code:
            flash('사용자 ID와 업적 코드를 모두 입력해주세요.', 'error')
            return redirect(url_for('admin.config_achievements'))
        
        # 업적 수여 처리
        from utils import update_achievement_progress
        success = update_achievement_progress(user_id, achievement_code, 9999, False)
        
        if success:
            flash(f'사용자 {user_id}에게 업적 {achievement_code}이(가) 수여되었습니다.', 'success')
        else:
            flash('업적 수여 중 오류가 발생했습니다.', 'error')
        
        return redirect(url_for('admin.config_achievements'))

# 업적 시스템 관리
@admin_bp.route('/config/achievements', methods=['GET', 'POST'])
@admin_required
def config_achievements():
    """업적 시스템 관리"""
    if request.method == 'POST':
        # 업적 추가 처리
        if 'add_achievement' in request.form:
            achievement = {
                'id': request.form.get('id'),
                'code': request.form.get('code'),
                'name': request.form.get('name'),
                'description': request.form.get('description'),
                'category': request.form.get('category'),
                'level': request.form.get('level'),
                'points': request.form.get('points'),
                'requirement': request.form.get('requirement'),
                'requirement_value': request.form.get('requirement_value'),
                'hidden': 'True' if request.form.get('hidden') else 'False',
                'icon_url': request.form.get('icon_url'),
                'enabled': 'True' if request.form.get('enabled') else 'False'
            }
            
            # 업적 추가
            achievements = read_csv(CSV_FILES['achievements'])
            
            # ID 중복 확인
            for a in achievements:
                if a['id'] == achievement['id']:
                    flash('이미 존재하는 업적 ID입니다.', 'error')
                    return redirect(url_for('admin.config_achievements'))
            
            # 업적 추가
            append_to_csv(CSV_FILES['achievements'], achievement)
            flash('새 업적이 추가되었습니다.', 'success')
        
        # 업적 수정 처리
        elif 'edit_achievement' in request.form:
            achievement_id = request.form.get('achievement_id')
            achievements = read_csv(CSV_FILES['achievements'])
            updated_achievements = []
            
            for a in achievements:
                if a['id'] == achievement_id:
                    a['code'] = request.form.get('code')
                    a['name'] = request.form.get('name')
                    a['description'] = request.form.get('description')
                    a['category'] = request.form.get('category')
                    a['level'] = request.form.get('level')
                    a['points'] = request.form.get('points')
                    a['requirement'] = request.form.get('requirement')
                    a['requirement_value'] = request.form.get('requirement_value')
                    a['hidden'] = 'True' if request.form.get('hidden') else 'False'
                    a['icon_url'] = request.form.get('icon_url')
                    a['enabled'] = 'True' if request.form.get('enabled') else 'False'
                updated_achievements.append(a)
            
            update_csv(CSV_FILES['achievements'], updated_achievements)
            flash('업적이 업데이트되었습니다.', 'success')
        
        # 업적 삭제 처리
        elif 'delete_achievement' in request.form:
            achievement_id = request.form.get('achievement_id')
            achievements = read_csv(CSV_FILES['achievements'])
            updated_achievements = [a for a in achievements if a['id'] != achievement_id]
            
            update_csv(CSV_FILES['achievements'], updated_achievements)
            flash('업적이 삭제되었습니다.', 'success')
    
    # 업적 목록 불러오기
    achievements = read_csv(CSV_FILES['achievements'])
    
    # 업적 카테고리 목록
    categories = sorted(list(set(a['category'] for a in achievements)))
    
    # 업적 요구사항 유형 목록
    requirements = sorted(list(set(a['requirement'] for a in achievements)))
    
    # 사용자 목록 (업적 관리용)
    users = read_csv(CSV_FILES['users'])
    
    return render_template('admin_achievements.html', 
                           section='config_achievements', 
                           achievements=achievements,
                           categories=categories,
                           requirements=requirements,
                           users=users)

# 레벨 시스템 관리
@admin_bp.route('/config/levels', methods=['GET', 'POST'])
@admin_required
def config_levels():
    """레벨 시스템 관리"""
    if request.method == 'POST':
        # 레벨 추가 처리
        if 'add_level' in request.form:
            level = {
                'level': request.form.get('level'),
                'title': request.form.get('title'),
                'required_points': request.form.get('required_points'),
                'bonus_reward': request.form.get('bonus_reward'),
                'description': request.form.get('description'),
                'icon_url': request.form.get('icon_url'),
                'enabled': 'True' if request.form.get('enabled') else 'False'
            }
            
            # 레벨 추가
            levels = read_csv(CSV_FILES['levels'])
            
            # 레벨 중복 확인
            for l in levels:
                if l['level'] == level['level']:
                    flash('이미 존재하는 레벨입니다.', 'error')
                    return redirect(url_for('admin.config_levels'))
            
            # 레벨 추가
            append_to_csv(CSV_FILES['levels'], level)
            flash('새 레벨이 추가되었습니다.', 'success')
        
        # 레벨 수정 처리
        elif 'edit_level' in request.form:
            level_id = request.form.get('level_id')
            levels = read_csv(CSV_FILES['levels'])
            updated_levels = []
            
            for l in levels:
                if l['level'] == level_id:
                    l['title'] = request.form.get('title')
                    l['required_points'] = request.form.get('required_points')
                    l['bonus_reward'] = request.form.get('bonus_reward')
                    l['description'] = request.form.get('description')
                    l['icon_url'] = request.form.get('icon_url')
                    l['enabled'] = 'True' if request.form.get('enabled') else 'False'
                updated_levels.append(l)
            
            update_csv(CSV_FILES['levels'], updated_levels)
            flash('레벨이 업데이트되었습니다.', 'success')
        
        # 레벨 삭제 처리
        elif 'delete_level' in request.form:
            level_id = request.form.get('level_id')
            levels = read_csv(CSV_FILES['levels'])
            updated_levels = [l for l in levels if l['level'] != level_id]
            
            update_csv(CSV_FILES['levels'], updated_levels)
            flash('레벨이 삭제되었습니다.', 'success')
    
    # 레벨 목록 불러오기
    levels = read_csv(CSV_FILES['levels'])
    
    # 레벨 순서대로 정렬
    levels.sort(key=lambda x: int(x['level']))
    
    return render_template('admin_levels.html', 
                           section='config_levels', 
                           levels=levels)

# 퀘스트 시스템 관리
@admin_bp.route('/config/quests', methods=['GET', 'POST'])
@admin_required
def config_quests():
    """퀘스트 시스템 관리"""
    if request.method == 'POST':
        # 퀘스트 추가 처리
        if 'add_quest' in request.form:
            quest = {
                'id': request.form.get('id'),
                'title': request.form.get('title'),
                'description': request.form.get('description'),
                'type': request.form.get('type'),
                'goal_action': request.form.get('goal_action'),
                'goal_value': request.form.get('goal_value'),
                'reward_type': request.form.get('reward_type'),
                'reward_value': request.form.get('reward_value'),
                'difficulty': request.form.get('difficulty'),
                'time_limit_hours': request.form.get('time_limit_hours'),
                'prerequisite_quest_id': request.form.get('prerequisite_quest_id') or '',
                'enabled': 'True' if request.form.get('enabled') else 'False'
            }
            
            # 퀘스트 추가
            quests = read_csv(CSV_FILES['quests'])
            
            # ID 중복 확인
            for q in quests:
                if q['id'] == quest['id']:
                    flash('이미 존재하는 퀘스트 ID입니다.', 'error')
                    return redirect(url_for('admin.config_quests'))
            
            # 퀘스트 추가
            append_to_csv(CSV_FILES['quests'], quest)
            flash('새 퀘스트가 추가되었습니다.', 'success')
        
        # 퀘스트 수정 처리
        elif 'edit_quest' in request.form:
            quest_id = request.form.get('quest_id')
            quests = read_csv(CSV_FILES['quests'])
            updated_quests = []
            
            for q in quests:
                if q['id'] == quest_id:
                    q['title'] = request.form.get('title')
                    q['description'] = request.form.get('description')
                    q['type'] = request.form.get('type')
                    q['goal_action'] = request.form.get('goal_action')
                    q['goal_value'] = request.form.get('goal_value')
                    q['reward_type'] = request.form.get('reward_type')
                    q['reward_value'] = request.form.get('reward_value')
                    q['difficulty'] = request.form.get('difficulty')
                    q['time_limit_hours'] = request.form.get('time_limit_hours')
                    q['prerequisite_quest_id'] = request.form.get('prerequisite_quest_id') or ''
                    q['enabled'] = 'True' if request.form.get('enabled') else 'False'
                updated_quests.append(q)
            
            update_csv(CSV_FILES['quests'], updated_quests)
            flash('퀘스트가 업데이트되었습니다.', 'success')
        
        # 퀘스트 삭제 처리
        elif 'delete_quest' in request.form:
            quest_id = request.form.get('quest_id')
            quests = read_csv(CSV_FILES['quests'])
            updated_quests = [q for q in quests if q['id'] != quest_id]
            
            update_csv(CSV_FILES['quests'], updated_quests)
            flash('퀘스트가 삭제되었습니다.', 'success')
    
    # 퀘스트 목록 불러오기
    quests = read_csv(CSV_FILES['quests'])
    
    # 퀘스트 유형별로 분류
    daily_quests = [q for q in quests if q['type'] == 'daily']
    weekly_quests = [q for q in quests if q['type'] == 'weekly']
    
    # 목표 행동 목록
    goal_actions = sorted(list(set(q['goal_action'] for q in quests)))
    
    # 난이도 목록
    difficulties = sorted(list(set(q['difficulty'] for q in quests)))
    
    return render_template('admin_quests.html', 
                           section='config_quests', 
                           quests=quests,
                           daily_quests=daily_quests,
                           weekly_quests=weekly_quests,
                           goal_actions=goal_actions,
                           difficulties=difficulties)

# 포인트 시스템 관리
@admin_bp.route('/config/points', methods=['GET', 'POST'])
@admin_required
def config_points():
    """포인트 시스템 관리"""
    if request.method == 'POST':
        # 포인트 규칙 추가 처리
        if 'add_point_rule' in request.form:
            point_rule = {
                'action_code': request.form.get('action_code'),
                'name': request.form.get('name'),
                'description': request.form.get('description'),
                'base_points': request.form.get('base_points'),
                'cooldown_minutes': request.form.get('cooldown_minutes'),
                'daily_limit': request.form.get('daily_limit'),
                'enabled': 'True' if request.form.get('enabled') else 'False'
            }
            
            # 포인트 규칙 추가
            points = read_csv(CSV_FILES['points'])
            
            # 액션 코드 중복 확인
            for p in points:
                if p['action_code'] == point_rule['action_code']:
                    flash('이미 존재하는 액션 코드입니다.', 'error')
                    return redirect(url_for('admin.config_points'))
            
            # 포인트 규칙 추가
            append_to_csv(CSV_FILES['points'], point_rule)
            flash('새 포인트 규칙이 추가되었습니다.', 'success')
        
        # 포인트 규칙 수정 처리
        elif 'edit_point_rule' in request.form:
            action_code = request.form.get('action_code')
            points = read_csv(CSV_FILES['points'])
            updated_points = []
            
            for p in points:
                if p['action_code'] == action_code:
                    p['name'] = request.form.get('name')
                    p['description'] = request.form.get('description')
                    p['base_points'] = request.form.get('base_points')
                    p['cooldown_minutes'] = request.form.get('cooldown_minutes')
                    p['daily_limit'] = request.form.get('daily_limit')
                    p['enabled'] = 'True' if request.form.get('enabled') else 'False'
                updated_points.append(p)
            
            update_csv(CSV_FILES['points'], updated_points)
            flash('포인트 규칙이 업데이트되었습니다.', 'success')
        
        # 포인트 규칙 삭제 처리
        elif 'delete_point_rule' in request.form:
            action_code = request.form.get('action_code')
            points = read_csv(CSV_FILES['points'])
            updated_points = [p for p in points if p['action_code'] != action_code]
            
            update_csv(CSV_FILES['points'], updated_points)
            flash('포인트 규칙이 삭제되었습니다.', 'success')
    
    # 포인트 규칙 목록 불러오기
    points = read_csv(CSV_FILES['points'])
    
    return render_template('admin_points.html', 
                           section='config_points', 
                           points=points)

# 보상 아이템 관리
@admin_bp.route('/config/reward_items', methods=['GET', 'POST'])
@admin_required
def config_reward_items():
    """보상 아이템 관리"""
    if request.method == 'POST':
        # 보상 아이템 추가 처리
        if 'add_reward_item' in request.form:
            reward_item = {
                'id': request.form.get('id'),
                'name': request.form.get('name'),
                'description': request.form.get('description'),
                'price': request.form.get('price'),
                'type': request.form.get('type'),
                'effect': request.form.get('effect'),
                'effect_value': request.form.get('effect_value'),
                'duration': request.form.get('duration'),
                'level_required': request.form.get('level_required'),
                'image_url': request.form.get('image_url'),
                'enabled': 'True' if request.form.get('enabled') else 'False'
            }
            
            # 보상 아이템 추가
            reward_items = read_csv(CSV_FILES['reward_items'])
            
            # ID 중복 확인
            for item in reward_items:
                if item['id'] == reward_item['id']:
                    flash('이미 존재하는 보상 아이템 ID입니다.', 'error')
                    return redirect(url_for('admin.config_reward_items'))
            
            # 보상 아이템 추가
            append_to_csv(CSV_FILES['reward_items'], reward_item)
            flash('새 보상 아이템이 추가되었습니다.', 'success')
        
        # 보상 아이템 수정 처리
        elif 'edit_reward_item' in request.form:
            item_id = request.form.get('item_id')
            reward_items = read_csv(CSV_FILES['reward_items'])
            updated_items = []
            
            for item in reward_items:
                if item['id'] == item_id:
                    item['name'] = request.form.get('name')
                    item['description'] = request.form.get('description')
                    item['price'] = request.form.get('price')
                    item['type'] = request.form.get('type')
                    item['effect'] = request.form.get('effect')
                    item['effect_value'] = request.form.get('effect_value')
                    item['duration'] = request.form.get('duration')
                    item['level_required'] = request.form.get('level_required')
                    item['image_url'] = request.form.get('image_url')
                    item['enabled'] = 'True' if request.form.get('enabled') else 'False'
                updated_items.append(item)
            
            update_csv(CSV_FILES['reward_items'], updated_items)
            flash('보상 아이템이 업데이트되었습니다.', 'success')
        
        # 보상 아이템 삭제 처리
        elif 'delete_reward_item' in request.form:
            item_id = request.form.get('item_id')
            reward_items = read_csv(CSV_FILES['reward_items'])
            updated_items = [item for item in reward_items if item['id'] != item_id]
            
            update_csv(CSV_FILES['reward_items'], updated_items)
            flash('보상 아이템이 삭제되었습니다.', 'success')
    
    # 보상 아이템 목록 불러오기
    reward_items = read_csv(CSV_FILES['reward_items'])
    
    # 아이템 유형 및 효과 목록
    item_types = sorted(list(set(item['type'] for item in reward_items)))
    item_effects = sorted(list(set(item['effect'] for item in reward_items)))
    
    return render_template('admin_reward_items.html', 
                           section='config_reward_items', 
                           reward_items=reward_items,
                           item_types=item_types,
                           item_effects=item_effects)





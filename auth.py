from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from datetime import datetime, timedelta
import csv
from admin import notices
from app import CSV_FILES, app
from utils import get_user_by_username, append_to_csv, get_timestamp, add_login_log, generate_id

auth_bp = Blueprint('auth', __name__)

CSV_FILES.update({
    'points': 'data/points.csv',
    'point_logs': 'data/point_logs.csv',
    'reward_config': 'data/reward_config.csv',
    'reward_items': 'data/reward_items.csv',
    'user_levels': 'data/user_levels.csv',
    'achievements': 'data/achievements.csv',
    'user_achievements': 'data/user_achievements.csv'
})


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 시스템 설정 가져오기
    from utils import get_system_config, update_user_balance, add_transaction, read_csv
    from app import CSV_FILES
    system_config = get_system_config()
    
    # 시스템 유지보수 모드 확인
    if system_config.get('maintenance_mode') == 'True':
        flash('시스템이 현재 유지보수 중입니다. 잠시 후 다시 시도해주세요.', 'warning')
        return render_template('login.html', maintenance_mode=True)
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # 시스템 설정에서 비밀번호 최소 길이 가져오기
        min_password_length = int(system_config.get('password_min_length', '4'))
        
        # 비밀번호 길이 검증
        if len(password) < min_password_length:
            flash(f'비밀번호는 최소 {min_password_length}자 이상이어야 합니다.', 'error')
            return render_template('login.html')
        
        # 로그인 IP 확인 설정
        login_ip_check = system_config.get('login_ip_check', 'True') == 'True'
        
        # 사용자 확인
        user = get_user_by_username(username)
        
        # 최대 로그인 실패 횟수 설정
        max_failed_login = int(system_config.get('max_failed_login', '5'))
        
        if user is None:
            flash('존재하지 않는 사용자입니다.', 'error')
            return render_template('login.html')
        
        # 로그인 성공
        if user and user['password'] == password:
            session.clear()
            session['user_id'] = user['id']
            session['login_time'] = datetime.now().timestamp()
            
            # 자동 로그아웃 시간 설정
            auto_logout_minutes = int(system_config.get('auto_logout_minutes', '30'))
            session['expires_at'] = datetime.now().timestamp() + (auto_logout_minutes * 60)
            
            # 로그인 로그 기록
            client_ip = request.remote_addr if login_ip_check else "IP확인비활성화"
            add_login_log(user['id'], 'success', client_ip)
            
            # 포인트 지급 - 로그인 보상
            from utils import award_points_for_action
            login_points_result = award_points_for_action(user['id'], 'daily_login')
            if login_points_result['success']:
                flash(login_points_result['message'], 'success')
            
            # 일일 로그인 보너스 지급
            daily_login_bonus = int(system_config.get('daily_login_bonus', '0'))
            if daily_login_bonus > 0:
                # 마지막 로그인 보너스 지급 일자 확인 (거래 내역에서)
                from app import CSV_FILES
                import csv
                last_bonus_date = None
                today = datetime.now().date()
                
                with open(CSV_FILES['transactions'], 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        if row['type'] == 'daily_login_bonus' and row['receiver_id'] == user['id']:
                            tx_date = datetime.fromisoformat(row['timestamp'].split('.')[0]).date()
                            if last_bonus_date is None or tx_date > last_bonus_date:
                                last_bonus_date = tx_date
                
                # 오늘 지급받지 않았으면 보너스 지급
                if last_bonus_date is None or last_bonus_date < today:
                    update_user_balance(user['id'], daily_login_bonus, "add")
                    add_transaction('system', user['id'], daily_login_bonus, 'daily_login_bonus')
                    
                    # 화폐 이름 가져오기
                    currency_name = system_config.get('currency_name', '체스머니')
                    flash(f'일일 로그인 보너스 {daily_login_bonus}{currency_name}이 지급되었습니다!', 'success')
            
            flash('로그인 성공!', 'success')
            
            # 공지사항 가져오기 - 여기가 수정된 부분
            notices_list = []
            try:
                notices_list = read_csv(CSV_FILES['notices'])
            except Exception as e:
                app.logger.error(f"공지사항을 로드하는 중 오류가 발생했습니다: {e}")
            
            # 관리자인 경우 관리자 페이지로 리다이렉트
            if user['is_admin'] == 'True':
                return redirect(url_for('home'))
            
            return render_template('home.html', 
                                  notices=notices_list,  # 리스트로 전달
                                  system_config=system_config,
                                  user=user)
        else:
            # 로그인 실패
            client_ip = request.remote_addr if login_ip_check else "IP확인비활성화"
            add_login_log(username, 'failed', client_ip)
            
            # 일정 횟수 이상 실패 시 추가 메시지
            from app import CSV_FILES
            import csv
            failed_count = 0
            
            with open(CSV_FILES['login_logs'], 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                recent_time = datetime.now() - timedelta(hours=1)  # 최근 1시간
                
                for row in reader:
                    log_time = datetime.fromisoformat(row['timestamp'].split('.')[0])
                    if (row['user_id'] == username or (user and row['user_id'] == user['id'])) and \
                       row['status'] == 'failed' and log_time > recent_time:
                        failed_count += 1
            
            if failed_count >= max_failed_login:
                flash(f'로그인 시도가 {max_failed_login}회 이상 실패했습니다. 잠시 후 다시 시도하거나 관리자에게 문의하세요.', 'error')
            else:
                flash('아이디 또는 비밀번호가 잘못되었습니다.', 'error')
    
    return render_template('login.html', system_config=system_config)



@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        nickname = request.form['nickname']
        email = request.form['email']
        phone = request.form['phone']
        birth_date = request.form['birth_date']

        # 중복 사용자 확인
        if get_user_by_username(username):
            flash('이미 사용 중인 아이디입니다.', 'error')
            return render_template('register.html')

        # 시스템 설정에서 초기 잔액 및 설정 가져오기
        from utils import get_system_config
        system_config = get_system_config()
        initial_balance = system_config.get('initial_balance', '10000')

        # 사용자 생성
        import random
        user = {
            'id': username,
            'password': password,
            'nickname': nickname,
            'email': email,
            'phone': phone,
            'birth_date': birth_date,
            'balance': initial_balance,  # 시스템 설정에서 가져온 초기 잔액
            'is_admin': 'False',
            'created_at': get_timestamp(),
            'number': str(random.randint(102947, 998576)),
            'memo': '없음'
        }

        append_to_csv(CSV_FILES['users'], user)
        flash('회원가입이 완료되었습니다. 로그인해 주세요.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/logout')
def logout():
    if 'user_id' in session:
        add_login_log(session['user_id'], 'logout')
    session.clear()
    flash('로그아웃 되었습니다.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
def profile():
    if not g.user:
        return redirect(url_for('auth.login'))

    # 시스템 설정 가져오기
    from utils import get_system_config
    system_config = get_system_config()

    # 송금 관련 설정값 가져오기
    min_transfer_amount = int(system_config.get('min_transfer_amount', '100'))
    max_transfer_amount = int(
        system_config.get('max_transfer_amount', '1000000'))
    transfer_fee_percent = float(system_config.get('transfer_fee_percent',
                                                   '0'))
    country_name = system_config.get('country_name', '체스제국')
    currency_name = system_config.get('currency_name', '체스머니')
    currency_symbol = system_config.get('currency_symbol', 'CM')

    # 사용자 거래 내역 가져오기
    transactions = []
    with open(CSV_FILES['transactions'], 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['sender_id'] == g.user['id'] or row[
                    'receiver_id'] == g.user['id']:
                transactions.append(row)

    # 최근 거래 내역 먼저 표시 (최대 30일)

    thirty_days_ago = datetime.now() - timedelta(days=30)

    # 최근 거래 내역 필터링 및 정렬
    recent_transactions = []
    for tx in transactions:
        tx_date = datetime.fromisoformat(tx['timestamp'].split('.')[0])
        if tx_date >= thirty_days_ago:
            recent_transactions.append(tx)

    recent_transactions.sort(key=lambda x: x['timestamp'], reverse=True)

    return render_template('profile.html',
                           transactions=recent_transactions,
                           min_transfer_amount=min_transfer_amount,
                           max_transfer_amount=max_transfer_amount,
                           transfer_fee_percent=transfer_fee_percent,
                           country_name=country_name,
                           currency_name=currency_name,
                           currency_symbol=currency_symbol,
                           system_config=system_config)


@auth_bp.route('/send_money', methods=['GET', 'POST'])
def send_money():
    if not g.user:
        return redirect(url_for('auth.login'))

    # 시스템 설정 가져오기
    from utils import get_system_config
    system_config = get_system_config()

    # 송금 기능이 비활성화된 경우
    if system_config.get('enable_transfer') == 'False':
        flash('송금 기능이 현재 비활성화되어 있습니다.', 'warning')
        return redirect(url_for('home'))

    # 시스템 설정에서 송금 관련 설정값 가져오기
    min_transfer_amount = int(system_config.get('min_transfer_amount', '100'))
    max_transfer_amount = int(
        system_config.get('max_transfer_amount', '1000000'))
    transfer_fee_percent = float(system_config.get('transfer_fee_percent',
                                                   '0'))
    currency_name = system_config.get('currency_name', '체스머니')

    if request.method == 'POST':
        receiver_id = request.form['receiver_id']
        amount = int(request.form['amount'])

        # 송금액 범위 검증
        if amount < min_transfer_amount:
            flash(f'최소 송금 금액은 {min_transfer_amount}{currency_name}입니다.',
                  'error')
            return redirect(url_for('auth.profile'))

        if amount > max_transfer_amount:
            flash(f'최대 송금 금액은 {max_transfer_amount}{currency_name}입니다.',
                  'error')
            return redirect(url_for('auth.profile'))

        # 수신자 확인
        receiver = get_user_by_username(receiver_id)
        if not receiver:
            flash('존재하지 않는 사용자입니다.', 'error')
            return redirect(url_for('auth.profile'))

        # 자기 자신에게 송금 방지
        if receiver_id == g.user['id']:
            flash('자기 자신에게는 송금할 수 없습니다.', 'error')
            return redirect(url_for('auth.profile'))

        # 수수료 계산
        fee = int(amount * transfer_fee_percent / 100)
        total_amount = amount + fee

        # 잔액 확인
        if int(g.user['balance']) < total_amount:
            flash('잔액이 부족합니다.', 'error')
            return redirect(url_for('auth.profile'))

        # 송금 처리
        from utils import update_user_balance, add_transaction

        update_user_balance(g.user['id'], total_amount, "subtract")
        update_user_balance(receiver_id, amount, "add")

        # 거래 기록 추가 (송금 금액)
        add_transaction(g.user['id'], receiver_id, amount, 'transfer')

        # 수수료가 있는 경우 수수료 기록 추가
        if fee > 0:
            add_transaction(g.user['id'], 'system', fee, 'transfer_fee')

        # 화폐 이름에 따라 조사 처리
        josa = "을" if currency_name[-1] not in [
            '아', '어', '오', '우', '이', '에', '애'
        ] else "를"

        # 수수료 안내 메시지
        fee_message = f" (수수료: {fee}{currency_name})" if fee > 0 else ""

        # 포인트 적립 - 송금 관련 포인트
        from utils import award_points_for_action
        transfer_points = award_points_for_action(g.user['id'],
                                                  'money_transfer', amount)
        if transfer_points['success']:
            flash(transfer_points['message'], 'success')

        flash(
            f'{receiver_id}님에게 {amount}{currency_name}{josa} 송금했습니다.{fee_message}',
            'success')
        return redirect(url_for('auth.profile'))

    # GET 요청 시 송금 페이지 표시
    return render_template(
        'send_money.html',
        min_amount=min_transfer_amount,
        max_amount=max_transfer_amount,
        fee_percent=transfer_fee_percent,
        country_name=system_config.get('country_name', '체스제국'),
        currency_name=currency_name,
        currency_symbol=system_config.get('currency_symbol', 'CM'),
        system_config=system_config)


# SNS 로그인 관련 라우트들
@auth_bp.route('/social_login_options')
def social_login_options():
    """소셜 로그인 옵션 페이지"""
    # 시스템 설정 가져오기
    from utils import get_system_config
    system_config = get_system_config()

    # 소셜 로그인 활성화 여부 확인
    if system_config.get('enable_social_login', 'False') == 'False':
        flash('소셜 로그인 기능이 현재 비활성화되어 있습니다.', 'warning')
        return redirect(url_for('auth.login'))

    return render_template('auth/social_login.html',
                           system_config=system_config)


@auth_bp.route('/social_login/<provider>')
def social_login(provider):
    """특정 소셜 미디어 로그인 처리"""
    # 시스템 설정 가져오기
    from utils import get_system_config
    system_config = get_system_config()

    # 소셜 로그인 활성화 여부 확인
    if system_config.get('enable_social_login', 'False') == 'False':
        flash('소셜 로그인 기능이 현재 비활성화되어 있습니다.', 'warning')
        return redirect(url_for('auth.login'))

    # 현재는 플레이스홀더 구현 (실제로는 OAuth 라이브러리를 사용하여 각 제공자에 맞는 인증 과정을 수행해야 함)
    if provider == 'google':
        flash('Google 로그인은 아직 구현 중입니다.', 'warning')

    elif provider == 'kakao':
        flash('카카오 로그인은 아직 구현 중입니다.', 'warning')

    elif provider == 'naver':
        flash('네이버 로그인은 아직 구현 중입니다.', 'warning')

    elif provider == 'facebook':
        flash('Facebook 로그인은 아직 구현 중입니다.', 'warning')

    elif provider == 'apple':
        flash('Apple 로그인은 아직 구현 중입니다.', 'warning')

    else:
        flash(f'지원하지 않는 소셜 로그인 제공자: {provider}', 'error')

    return redirect(url_for('auth.login'))


@auth_bp.route('/social_callback/<provider>')
def social_callback(provider):
    """소셜 로그인 콜백 처리"""
    # OAuth 콜백을 처리하는 로직 (실제 구현시 추가)
    # 현재는 이 기능의 존재만 표시

    # 시스템 설정 가져오기
    from utils import get_system_config
    system_config = get_system_config()

    # 기본 안내 메시지 (실제 구현 시 대체)
    flash(f'{provider} 로그인 콜백이 호출되었습니다. 이 기능은 아직 구현 중입니다.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/link_social_account/<provider>', methods=['GET', 'POST'])
def link_social_account(provider):
    """기존 계정과 소셜 계정 연동"""
    if not g.user:
        flash('계정 연동을 위해 먼저 로그인해주세요.', 'warning')
        return redirect(url_for('auth.login'))

    # 소셜 계정 연동 로직 (실제 구현시 추가)
    # 현재는 이 기능의 존재만 표시

    flash(f'{provider} 계정 연동 기능은 아직 구현 중입니다.', 'info')
    return redirect(url_for('auth.profile'))


@auth_bp.route('/id_card')
def id_card():
    if not g.user:
        return redirect(url_for('auth.login'))
    return render_template('id_card.html')

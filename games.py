from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, session
import random
from app import CSV_FILES
from utils import update_user_balance, add_transaction, add_game_log, get_games_config, get_system_config, get_politicians, award_points_for_action, update_achievement_progress

games_bp = Blueprint('games', __name__, url_prefix='/games')

@games_bp.route('/')
def index():
    if not g.user:
        return redirect(url_for('auth.login'))

    # 시스템 설정 가져오기
    system_config = get_system_config()

    # 게임 기능이 비활성화된 경우
    if system_config.get('enable_games') == 'False':
        flash('게임 기능이 현재 비활성화되어 있습니다.', 'warning')
        return redirect(url_for('home'))

    # CSV에서 게임 목록 가져오기
    games = get_games_config()

    # 활성화된 게임만 필터링
    enabled_games = [game for game in games if game['enabled'] == 'True']

    # 시스템 설정 정보 추가
    currency_name = system_config.get('currency_name', '체스머니')
    currency_symbol = system_config.get('currency_symbol', 'CM')
    country_name = system_config.get('country_name', '체스제국')
    game_win_boost = float(system_config.get('game_win_boost', '10'))

    return render_template('games.html', 
                          games=enabled_games,
                          currency_name=currency_name,
                          currency_symbol=currency_symbol,
                          country_name=country_name,
                          game_win_boost=game_win_boost,
                          system_config=system_config)

@games_bp.route('/<game_id>')
def game_page(game_id):
    if not g.user:
        return redirect(url_for('auth.login'))

    # 시스템 설정 가져오기
    system_config = get_system_config()

    # 게임 기능이 비활성화된 경우
    if system_config.get('enable_games') == 'False':
        flash('게임 기능이 현재 비활성화되어 있습니다.', 'warning')
        return redirect(url_for('home'))

    # 게임 설정 가져오기
    games_config = get_games_config()
    game_config = None
    for game in games_config:
        if game['id'] == game_id:
            game_config = game
            break

    # 존재하지 않는 게임이거나 비활성화된 게임인 경우
    if not game_config or game_config['enabled'] != 'True':
        flash('존재하지 않거나 비활성화된 게임입니다.', 'warning')
        return redirect(url_for('games.index'))

    # 게임별 추가 데이터 준비
    context = {'game_config': game_config}

    # 시스템 설정 정보 추가
    currency_name = system_config.get('currency_name', '체스머니')
    currency_symbol = system_config.get('currency_symbol', 'CM')
    country_name = system_config.get('country_name', '체스제국')
    game_win_boost = float(system_config.get('game_win_boost', '10'))

    context.update({
        'currency_name': currency_name,
        'currency_symbol': currency_symbol,
        'country_name': country_name,
        'game_win_boost': game_win_boost,
        'system_config': system_config
    })

    # 특정 게임에 필요한 추가 데이터
    if game_id == 'cards':
        # 정치인 데이터 가져오기
        politicians = get_politicians()
        context['politicians'] = politicians

    # 템플릿 결정
    template_name = f'game_{game_id}.html'

    return render_template(template_name, **context)

@games_bp.route('/bet', methods=['POST'])
def place_bet():
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})

    game_id = request.form.get('game_id')
    bet_amount = int(request.form.get('bet_amount', 0))
    game_data = request.form.get('game_data', '')  # 게임별 추가 데이터

    # 배팅 금액 검증
    if bet_amount <= 0:
        return jsonify({'success': False, 'message': '유효한 배팅 금액을 입력하세요.'})

    if int(g.user['balance']) < bet_amount:
        return jsonify({'success': False, 'message': '잔액이 부족합니다.'})

    # 게임 결과 처리
    result, win_amount = process_game_result(game_id, bet_amount, game_data)

    # 시스템 설정에서 화폐 이름 가져오기
    system_config = get_system_config()
    currency_name = system_config.get('currency_name', '체스머니')

    # 결과에 따른 잔액 업데이트
    if result == 'corrupt':
        # 나쁜 정치인으로 인한 손실
        total_loss = abs(win_amount)
        update_user_balance(g.user['id'], total_loss, "subtract")
        result_text = f"부패한 정치인! 손실 -{total_loss}{currency_name}"
    elif win_amount > 0:
        # 승리 - 순수익만 추가
        update_user_balance(g.user['id'], win_amount, "add")
        result_text = f"승리! +{win_amount}{currency_name}"
    elif win_amount < 0:
        # 패배
        update_user_balance(g.user['id'], abs(win_amount), "subtract")
        result_text = f"패배! -{abs(win_amount)}{currency_name}"
    else:
        # 무승부 - 잔액 변동 없음
        result_text = f"무승부! 배팅금이 반환됩니다."

    # 게임 로그 추가
    add_game_log(g.user['id'], game_id, bet_amount, result)

    # 거래 기록 추가
    if result == 'corrupt':
        # 나쁜 정치인으로 인한 손실
        add_transaction(g.user['id'], 'system', abs(win_amount), 'corrupt_politician')
    elif win_amount > 0:
        # 일반 승리
        add_transaction('system', g.user['id'], win_amount, 'game_win')

        # 게임 승리 포인트 지급
        points_result = award_points_for_action(g.user['id'], 'game_win', bet_amount)

        # 업적 진행도 업데이트
        update_achievement_progress(g.user['id'], 'game_winner', 1)
        if win_amount >= bet_amount * 2:
            update_achievement_progress(g.user['id'], 'big_winner', 1)
    else:
        # 일반 패배
        add_transaction(g.user['id'], 'system', bet_amount, 'game_loss')

        # 게임 참여 포인트 지급 (패배해도 참여 포인트는 지급)
        points_result = award_points_for_action(g.user['id'], 'game_play')

    # 게임 종류별 업적 진행도 업데이트
    update_achievement_progress(g.user['id'], f'play_{game_id}', 1)

    return jsonify({
        'success': True, 
        'message': result_text,
        'result': result,
        'win_amount': win_amount,
        'new_balance': g.user['balance']
    })

def process_game_result(game_id, bet_amount, game_data):
    # 시스템 설정 가져오기
    system_config = get_system_config()
    game_win_boost = float(system_config.get('game_win_boost', '10')) / 100 + 1.0

    # 승리 확률 부스트 적용 (아이템 등의 효과)
    user_boost = 1.0
    if session.get('game_boost'):
        user_boost = 1.1  # 10% 증가
        session.pop('game_boost', None)  # 사용 후 제거

    # 게임 설정 가져오기
    games_config = get_games_config()
    game_config = None
    for game in games_config:
        if game['id'] == game_id:
            game_config = game
            break

    # 게임 설정이 없으면 기본값 사용
    if not game_config:
        # 알 수 없는 게임
        win_amount = 0
        result = 'unknown_game'
        return result, win_amount

    # 배수 설정 가져오기
    win_multiplier = float(game_config.get('win_multiplier', '1.5'))
    special_win_multiplier = float(game_config.get('special_win_multiplier', '3.0'))
    draw_multiplier = float(game_config.get('draw_multiplier', '1.0'))

    # 게임 종류별 처리
    if game_id == 'running':
        # 러닝 게임: 장애물 충돌 여부에 따라 결과 결정
        if game_data == 'success':
            win_amount = int(bet_amount * win_multiplier)
            result = 'win'
        else:
            win_amount = 0
            result = 'lose'

    elif game_id == 'cards':
        # 카드 게임: 선택한 카드 ID로 정치인 정보 찾기
        card_id = request.form.get('card_id')
        politicians = get_politicians()

        selected_politician = None
        for politician in politicians:
            if str(politician['id']) == str(card_id):
                selected_politician = politician
                break

        if not selected_politician:
            return 'error', 0

        politician_power = int(selected_politician['power'])

        # 무조건 (배팅 금액 * power / 2) 공식 적용
        if politician_power <= 0:
            win_amount = -bet_amount  # power가 0 이하면 전체 손실
        else:
            win_amount = int(bet_amount * politician_power / 2) - bet_amount  # 순수 수익/손실 계산

        # 결과 메시지에 power 값과 금액 변화 표시
        if win_amount > 0:
            result = f'power {politician_power}로 {win_amount}원 획득!'
        else:
            result = f'power {politician_power}로 {abs(win_amount)}원 손실...'

    elif game_id == 'casino':
        # 카지노 게임: 랜덤 결과 (룰렛, 슬롯머신)
        casino_type = game_data.split('_')[0] if '_' in game_data else 'roulette'

        if casino_type == 'roulette':
            # 룰렛: 36분의 1 확률로 큰 승리, 3분의 1 확률로 작은 승리
            roulette_result = random.randint(1, 36)
            user_number = int(game_data.split('_')[1]) if '_' in game_data else 0

            if roulette_result == user_number:
                win_amount = int(bet_amount * special_win_multiplier)
                result = 'big_win'
            elif (roulette_result % 2 == user_number % 2):
                win_amount = int(bet_amount * win_multiplier)
                result = 'small_win'
            else:
                win_amount = 0
                result = 'lose'

        else:  # slot
            # 슬롯머신: 8분의 1 확률로 승리
            slot_result = random.randint(1, 8)
            if slot_result == 1:
                win_amount = int(bet_amount * special_win_multiplier)
                result = 'win'
            else:
                win_amount = 0
                result = 'lose'

    elif game_id == 'tictactoe':
        # 틱택토: 게임 결과에 따라 결정
        if game_data == 'win':
            win_amount = int(bet_amount * win_multiplier)
            result = 'win'
        elif game_data == 'draw':
            win_amount = int(bet_amount * draw_multiplier)  # 무승부는 원금 반환
            result = 'draw'
        else:
            win_amount = 0
            result = 'lose'

    elif game_id == 'rps':
        # 가위바위보: 게임 결과에 따라 결정
        if game_data == 'win':
            win_amount = int(bet_amount * win_multiplier)
            result = 'win'
        elif game_data == 'draw':
            win_amount = int(bet_amount * draw_multiplier)  # 무승부는 원금 반환
            result = 'draw'
        else:
            win_amount = 0
            result = 'lose'

    elif game_id == 'snake':
        # 스네이크 게임: 점수에 따라 배수 결정
        try:
            score = int(game_data)
            if score > 50:
                win_amount = int(bet_amount * special_win_multiplier)
                result = 'big_win'
            elif score > 20:
                win_amount = int(bet_amount * win_multiplier)
                result = 'win'
            elif score > 10:
                win_amount = int(bet_amount * draw_multiplier)
                result = 'small_win'
            else:
                win_amount = 0
                result = 'lose'
        except:
            win_amount = 0
            result = 'error'

    elif game_id == 'betting':
        # 배팅 게임: 숫자 맞추기
        try:
            user_number = int(game_data)
            winning_number = random.randint(1, 10)

            if user_number == winning_number:
                win_amount = int(bet_amount * special_win_multiplier)
                result = f'win_{winning_number}'
            else:
                win_amount = 0
                result = f'lose_{winning_number}'
        except:
            win_amount = 0
            result = 'error'

    elif game_id == 'slot':
        # 슬롯 머신 게임: 클라이언트에서 결과 계산하여 서버에 전송
        if request.form.get('result') == 'win':
            win_amount = int(request.form.get('win_amount', 0))
            result = 'win'
        else:
            win_amount = 0
            result = 'lose'

    elif game_id == 'dice':
        # 주사위 게임: 클라이언트에서 결과 계산하여 서버에 전송
        if request.form.get('result') == 'win':
            win_amount = int(request.form.get('win_amount', 0))
            result = 'win'
        else:
            win_amount = 0
            result = 'lose'

    elif game_id == 'blackjack':
        # 블랙잭 게임: 클라이언트에서 결과 계산하여 서버에 전송
        if request.form.get('result') == 'win':
            win_amount = int(request.form.get('win_amount', 0))
            result = 'win'
        else:
            win_amount = 0
            result = 'lose'

    elif game_id == 'bingo':
        # 빙고 게임: 클라이언트에서 결과 계산하여 서버에 전송
        if request.form.get('result') == 'win':
            win_amount = int(request.form.get('win_amount', 0))
            result = 'win'
        else:
            win_amount = 0
            result = 'lose'

    else:
        # 알 수 없는 게임
        win_amount = 0
        result = 'unknown_game'

    # 부스트 적용 (시스템 전역 + 사용자 특정)
    win_amount = int(win_amount * game_win_boost * user_boost)

    return result, win_amount
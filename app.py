import os
import logging
import csv
from datetime import datetime
from flask import Flask, redirect, render_template, session, url_for, g, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)

# Flask 애플리케이션 초기화
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "chess_empire_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# 시스템 점검 모드 미들웨어
class MaintenanceModeMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        from utils import get_system_config

        # 공통 예외 경로 (점검 중에도 접근 가능)
        exempt_paths = ['/admin', '/static', '/maintenance']

        try:
            system_config = get_system_config()
            maintenance_mode = system_config.get('maintenance_mode', 'False')

            if maintenance_mode == 'True':
                path_info = environ.get('PATH_INFO', '')
                # 관리자와 정적 파일, 유지보수 페이지는 항상 접근 가능
                if not any(path_info.startswith(path) for path in exempt_paths):
                    # 유지보수 페이지로 리다이렉트
                    start_response('302 Found', [('Location', '/maintenance')])
                    return [b'']
        except Exception as e:
            app.logger.error(f"Maintenance check error: {str(e)}")

        return self.app(environ, start_response)

# 미들웨어 적용
app.wsgi_app = MaintenanceModeMiddleware(app.wsgi_app)

# 데이터 디렉토리 생성
os.makedirs('data', exist_ok=True)

# CSV 파일 경로
CSV_FILES = {
    'events': 'data/events.csv',
    'users': 'data/users.csv',
    'transactions': 'data/transactions.csv',
    'login_logs': 'data/login_logs.csv',
    'market_logs': 'data/market_logs.csv',
    'game_logs': 'data/game_logs.csv',
    'items': 'data/items.csv',
    'stocks': 'data/stocks.csv',
    'notices': 'data/notices.csv',
    'chat_messages': 'data/chat_messages.csv',
    'system_config': 'data/system_config.csv',
    'games_config': 'data/games_config.csv',
    'politicians': 'data/politicians.csv',
    'stocks_config': 'data/stocks_config.csv',
    'market_items': 'data/market_items.csv',
    'friends': 'data/friends.csv',
    'friend_activities': 'data/friend_activities.csv',
    'points': 'data/points.csv',
    'point_logs': 'data/point_logs.csv',
    'reward_config': 'data/reward_config.csv',
    'reward_items': 'data/reward_items.csv',
    'user_levels': 'data/user_levels.csv',
    'achievements': 'data/achievements.csv',
    'user_achievements': 'data/user_achievements.csv',
    'levels': 'data/levels.csv',
    'quests': 'data/quests.csv',
    'user_quests': 'data/user_quests.csv',
    'characters': 'data/characters.csv',
    'character_skills': 'data/character_skills.csv',
    'battle_logs': 'data/battle_logs.csv'
}

# CSV 파일 초기 구조 확인 및 생성
def init_csv_files():
    # users.csv
    if not os.path.exists(CSV_FILES['users']):
        with open(CSV_FILES['users'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'password', 'nickname', 'email', 'phone', 'birth_date', 'balance', 'is_admin', 'created_at'])
            # 관리자 계정 생성
            writer.writerow(['admin', 'admin123', '관리자', 'admin@chess.com', '01012345678', '990101', '9999999999', 'True', str(datetime.now())])

    # transactions.csv
    if not os.path.exists(CSV_FILES['transactions']):
        with open(CSV_FILES['transactions'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'sender_id', 'receiver_id', 'amount', 'type', 'timestamp'])

    # login_logs.csv
    if not os.path.exists(CSV_FILES['login_logs']):
        with open(CSV_FILES['login_logs'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'timestamp', 'ip', 'status', 'browser', 'platform', 'user_agent'])

    # game_logs.csv
    if not os.path.exists(CSV_FILES['game_logs']):
        with open(CSV_FILES['game_logs'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'game_type', 'bet_amount', 'result', 'timestamp'])

    # market_logs.csv
    if not os.path.exists(CSV_FILES['market_logs']):
        with open(CSV_FILES['market_logs'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'item_id', 'quantity', 'price', 'timestamp'])

    # notices.csv
    if not os.path.exists(CSV_FILES['notices']):
        with open(CSV_FILES['notices'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'title', 'content', 'author_id', 'timestamp'])
            writer.writerow(['1', '체스제국 송금 시스템 오픈', '체스제국 송금 시스템이 오픈되었습니다. 많은 이용 바랍니다.', 'admin', str(datetime.now())])

    # chat_messages.csv
    if not os.path.exists(CSV_FILES['chat_messages']):
        with open(CSV_FILES['chat_messages'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'message', 'timestamp'])
            writer.writerow(['1', 'admin', '체스제국 채팅방에 오신 것을 환영합니다!', str(datetime.now())])

    # 시스템 설정 파일
    if not os.path.exists(CSV_FILES['system_config']):
        with open(CSV_FILES['system_config'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['key', 'value', 'description'])
            writer.writerow(['app_name', '체스제국', '앱 이름'])
            writer.writerow(['system_name', '체스제국 송금 시스템', '시스템 전체 이름'])
            writer.writerow(['country_name', '체스제국', '국가/조직 이름'])
            writer.writerow(['currency_name', '체스머니', '화폐 이름'])
            writer.writerow(['currency_symbol', 'CM', '화폐 단위 기호'])
            writer.writerow(['primary_color', '#3f51b5', '시스템 주요 색상'])
            writer.writerow(['secondary_color', '#f50057', '시스템 보조 색상'])
            writer.writerow(['register_ip_check', 'True', '회원가입 시 IP 확인 사용 여부'])
            writer.writerow(['login_ip_check', 'True', '로그인 시 IP 확인 사용 여부'])
            writer.writerow(['initial_balance', '10000', '신규 회원 기본 지급 금액'])
            writer.writerow(['max_transfer_amount', '1000000', '최대 송금 가능 금액'])
            writer.writerow(['min_transfer_amount', '100', '최소 송금 가능 금액'])
            writer.writerow(['transfer_fee_percent', '0', '송금 수수료 퍼센트'])
            writer.writerow(['game_win_boost', '10', '게임 승리 시 보너스 % (기본 10%)'])
            writer.writerow(['market_discount', '0', '마켓 아이템 할인율 % (기본 0%)'])
            writer.writerow(['enable_chat', 'True', '채팅 기능 활성화 여부'])
            writer.writerow(['enable_stocks', 'True', '주식 기능 활성화 여부'])
            writer.writerow(['enable_games', 'True', '게임 기능 활성화 여부'])
            writer.writerow(['enable_market', 'True', '마켓 기능 활성화 여부'])
            writer.writerow(['enable_profile', 'True', '프로필 기능 활성화 여부'])
            writer.writerow(['enable_transfer', 'True', '송금 기능 활성화 여부'])
            writer.writerow(['enable_friends', 'True', '친구 기능 활성화 여부'])
            writer.writerow(['maintenance_mode', 'False', '시스템 유지보수 모드'])
            writer.writerow(['footer_message', '© 2025 체스제국 송금 시스템', '푸터 메시지'])
            writer.writerow(['admin_contact', 'admin@chess.com', '관리자 연락처'])
            writer.writerow(['max_notice_count', '5', '메인화면에 표시할 최대 공지 수'])
            writer.writerow(['site_description', '체스제국 송금 시스템: 모바일 친화적인 웹 기반 가상 화폐 플랫폼', '사이트 설명'])
            writer.writerow(['daily_login_bonus', '100', '일일 로그인 보너스'])
            writer.writerow(['referral_bonus', '1000', '친구 추천 보너스'])
            writer.writerow(['service_level', 'standard', '서비스 수준 (standard, premium, enterprise)'])
            writer.writerow(['password_min_length', '4', '비밀번호 최소 길이'])
            writer.writerow(['auto_logout_minutes', '30', '자동 로그아웃 시간(분)'])
            writer.writerow(['default_language', 'ko', '기본 언어'])
            writer.writerow(['theme', 'light', '테마 (light, dark)'])
            writer.writerow(['allow_guest_view', 'False', '게스트 조회 허용'])
            writer.writerow(['max_failed_login', '5', '로그인 실패 최대 횟수'])
            writer.writerow(['enable_social_login', 'True', '소셜 로그인 활성화 여부'])
            writer.writerow(['social_login_providers', 'google,kakao,naver,facebook,apple', '활성화된 소셜 로그인 제공자'])
            writer.writerow(['google_client_id', '', 'Google OAuth 클라이언트 ID'])
            writer.writerow(['google_client_secret', '', 'Google OAuth 클라이언트 비밀키'])
            writer.writerow(['kakao_client_id', '', '카카오 OAuth 클라이언트 ID'])
            writer.writerow(['naver_client_id', '', '네이버 OAuth 클라이언트 ID'])
            writer.writerow(['naver_client_secret', '', '네이버 OAuth 클라이언트 비밀키'])
            writer.writerow(['facebook_app_id', '', 'Facebook 앱 ID'])
            writer.writerow(['facebook_app_secret', '', 'Facebook 앱 비밀키'])
            writer.writerow(['apple_client_id', '', 'Apple 클라이언트 ID'])
            writer.writerow(['apple_team_id', '', 'Apple 팀 ID'])
            # system_config.csv 초기화 부분에 추가
            writer.writerow(['enable_character_battle', 'True', '캐릭터 배틀 기능 활성화 여부'])
            writer.writerow(['battle_reward', '100', '배틀 승리 시 보상 금액'])
            writer.writerow(['battle_exp', '50', '배틀 승리 시 경험치'])
            writer.writerow(['battle_points', '10', '배틀 승리 시 포인트'])
            writer.writerow(['battle_cooldown_minutes', '5', '배틀 쿨다운 시간(분)'])
            writer.writerow(['battle_daily_limit', '10', '일일 배틀 제한 횟수'])


    # 게임 설정 파일
    if not os.path.exists(CSV_FILES['games_config']):
        with open(CSV_FILES['games_config'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'description', 'min_bet', 'max_bet', 'enabled', 'win_multiplier', 'special_win_multiplier', 'draw_multiplier'])
            writer.writerow(['running', '러닝 게임', '장애물을 피해 달리는 모바일 게임', '100', '10000', 'True', '1.5', '2.0', '1.0'])
            writer.writerow(['cards', '정치인 카드 게임', '카드를 모으고 겨루는 게임', '200', '5000', 'True', '2.0', '3.0', '1.0'])
            writer.writerow(['casino', '카지노 게임', '룰렛과 슬롯머신 게임', '500', '20000', 'True', '1.8', '35.0', '1.0'])
            writer.writerow(['tictactoe', '틱택토', '3x3 보드에서 즐기는 전략 게임', '100', '1000', 'True', '2.0', '0.0', '1.0'])
            writer.writerow(['rps', '가위바위보', '운에 의존하는 고전 게임', '50', '2000', 'True', '1.8', '0.0', '1.0'])
            writer.writerow(['snake', '스네이크 게임', '뱀을 조종하여 먹이를 먹는 게임', '200', '5000', 'True', '1.5', '3.0', '1.0'])
            writer.writerow(['betting', '배팅 게임', '숫자를 맞추는 배팅 게임', '1000', '50000', 'True', '9.0', '0.0', '1.0'])

    # 정치인 정보 파일
    if not os.path.exists(CSV_FILES['politicians']):
        with open(CSV_FILES['politicians'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'party', 'power', 'special', 'image_url', 'description'])
            writer.writerow(['1', '윤석열', '국민의힘', '10', 'True', '/static/img/politicians/yoon.png', '대한민국 제20대 대통령'])
            writer.writerow(['2', '이재명', '더불어민주당', '9', 'False', '/static/img/politicians/lee.png', '더불어민주당 대표'])
            writer.writerow(['3', '한동훈', '국민의힘', '8', 'False', '/static/img/politicians/han.png', '국민의힘 대표'])
            writer.writerow(['4', '심상정', '정의당', '7', 'False', '/static/img/politicians/sim.png', '정의당 전 대표'])
            writer.writerow(['5', '안철수', '국민의힘', '7', 'False', '/static/img/politicians/ahn.png', '국민의힘 의원'])

    # 주식 설정 파일
    if not os.path.exists(CSV_FILES['stocks_config']):
        with open(CSV_FILES['stocks_config'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'code', 'sector', 'initial_price', 'min_price', 'max_price', 'volatility', 'description'])
            writer.writerow(['1', '삼성전자', '005930', '전자', '67000', '50000', '100000', '5', '대한민국 대표 전자기업으로 반도체, 스마트폰, 가전제품 등을 생산합니다.'])
            writer.writerow(['2', 'SK하이닉스', '000660', '반도체', '125000', '80000', '200000', '7', '메모리 반도체 분야에서 세계적인 기업으로 D램과 낸드플래시를 주로 생산합니다.'])
            writer.writerow(['3', '네이버', '035420', 'IT서비스', '325000', '200000', '450000', '6', '대한민국의 대표적인 인터넷 기업으로 검색 엔진, 커머스 등 다양한 온라인 서비스를 제공합니다.'])

    # 마켓 아이템 설정 파일
    if not os.path.exists(CSV_FILES['market_items']):
        with open(CSV_FILES['market_items'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'effect', 'price', 'duration', 'max_uses', 'category', 'description', 'image_url'])
            writer.writerow(['1', '자주포', '3회 맞으면 즉시 퇴장', '1500', '7', '3', '무기', '강력한 자주포로 대상을 공격합니다. 3회 누적 시 퇴장 조치됩니다.', '/static/img/items/artillery.png'])
            writer.writerow(['2', 'ICBM', '맞으면 강제퇴장', '500000000', '30', '1', '무기', '대륙간 탄도 미사일로 단 한 번의 타격으로 즉시 퇴장시킵니다.', '/static/img/items/icbm.png'])
            writer.writerow(['3', '기관총', '3분 채팅 금지', '100', '1', '5', '무기', '빠른 연사 속도의 기관총입니다. 타격 시 3분간 채팅이 금지됩니다.', '/static/img/items/machinegun.png'])

    # 기존 stocks.csv가 있다면 stocks_config.csv의 데이터로 최초 초기화
    if not os.path.exists(CSV_FILES['stocks']):
        with open(CSV_FILES['stocks'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'current_price', 'previous_price', 'change_percent', 'last_update'])

            # stocks_config.csv에서 데이터 가져오기
            if os.path.exists(CSV_FILES['stocks_config']):
                stocks_config = []
                with open(CSV_FILES['stocks_config'], 'r', encoding='utf-8') as config_file:
                    reader = csv.DictReader(config_file)
                    stocks_config = list(reader)

                for stock in stocks_config:
                    writer.writerow([
                        stock['id'], 
                        stock['name'], 
                        stock['initial_price'],
                        stock['initial_price'],
                        '0.0',
                        str(datetime.now())
                    ])
            else:
                # 기존 주식 데이터 유지
                writer.writerow(['1', '체스제국', '10000', '9500', '5.26', str(datetime.now())])
                writer.writerow(['2', '디지털뱅크', '5000', '5100', '-1.96', str(datetime.now())])
                writer.writerow(['3', '게임테크', '8000', '7800', '2.56', str(datetime.now())])

    # 기존 items.csv가 있다면 market_items.csv의 데이터로 최초 초기화
    if not os.path.exists(CSV_FILES['items']):
        with open(CSV_FILES['items'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'effect', 'price', 'duration', 'max_uses'])

            # market_items.csv에서 데이터 가져오기
            if os.path.exists(CSV_FILES['market_items']):
                market_items = []
                with open(CSV_FILES['market_items'], 'r', encoding='utf-8') as items_file:
                    reader = csv.DictReader(items_file)
                    market_items = list(reader)

                for item in market_items:
                    writer.writerow([
                        item['id'], 
                        item['name'], 
                        item['effect'],
                        item['price'],
                        item['duration'],
                        item['max_uses']
                    ])
            else:
                # 기존 아이템 데이터 유지
                writer.writerow(['1', '행운의 부적', '다음 게임에서 승리 확률 10% 증가', '1000', '1', '1'])
                writer.writerow(['2', '보너스 카드', '다음 거래에서 10% 추가 적립', '2000', '1', '1'])
                writer.writerow(['3', '프리미엄 뱃지', '프로필에 특별 뱃지 표시', '5000', '30', '1'])

    # 포인트 관련 CSV 파일 초기화
    # points.csv
    if not os.path.exists(CSV_FILES['points']):
        with open(CSV_FILES['points'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['action_code', 'name', 'description', 'base_points', 'cooldown_minutes', 'daily_limit', 'enabled'])
            writer.writerow(['login', '로그인', '시스템에 로그인', '5', '1440', '1', 'True'])
            writer.writerow(['transfer', '송금하기', '다른 유저에게 송금', '2', '0', '0', 'True'])
            writer.writerow(['receive', '송금받기', '다른 유저에게서 송금 받음', '1', '0', '0', 'True'])
            writer.writerow(['game_play', '게임 참여', '게임에 참여', '1', '5', '10', 'True'])
            writer.writerow(['game_win', '게임 승리', '게임에서 승리', '5', '5', '10', 'True'])
            writer.writerow(['market_purchase', '마켓에서 아이템 구매', '3', '10', '5', 'True'])
            writer.writerow(['stock_buy', '주식 구매', '주식 구매', '2', '10', '10', 'True'])
            writer.writerow(['stock_sell', '주식 판매', '주식 판매', '2', '10', '10', 'True'])
            writer.writerow(['stock_profit', '주식 수익', '주식 거래로 수익 실현', '5', '0', '0', 'True'])
            writer.writerow(['profile_update', '프로필 정보 업데이트', '10', '1440', '1', 'True'])
            writer.writerow(['chat_message', '채팅 참여', '채팅방에 메시지 전송', '1', '5', '20', 'True'])
            writer.writerow(['achievement', '업적 달성', '새로운 업적 달성', '10', '0', '0', 'True'])
            writer.writerow(['quest_complete', '퀘스트 완료', '퀘스트 완료', '20', '0', '0', 'True'])
            writer.writerow(['daily_streak', '연속 접속', '연속 로그인 유지', '3', '1440', '1', 'True'])
            writer.writerow(['friend_add', '친구 추가', '친구 추가', '5', '60', '10', 'True'])

    # point_logs.csv
    if not os.path.exists(CSV_FILES['point_logs']):
        with open(CSV_FILES['point_logs'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'action_code', 'points', 'reason', 'timestamp'])
            writer.writerow(['1', 'admin', 'login', '5', '첫 로그인', str(datetime.now())])

    # reward_config.csv
    if not os.path.exists(CSV_FILES['reward_config']):
        with open(CSV_FILES['reward_config'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'action', 'points', 'description', 'enable'])
            writer.writerow(['1', 'daily_login', '10', '매일 로그인 시 포인트 획득', 'True'])
            writer.writerow(['2', 'game_win', '5', '게임 승리 시 포인트 획득', 'True'])
            writer.writerow(['3', 'game_play', '2', '게임 참여 시 포인트 획득', 'True'])
            writer.writerow(['4', 'money_transfer', '1', '송금 시 포인트 획득(1000단위당)', 'True'])
            writer.writerow(['5', 'profile_update', '10', '프로필 정보 업데이트 시 포인트 획득', 'True'])
            writer.writerow(['6', 'friend_add', '15', '친구 추가 시 포인트 획득', 'True'])
            writer.writerow(['7', 'chat_message', '1', '채팅 메시지 작성 시 포인트 획득', 'True'])
            writer.writerow(['8', 'item_purchase', '3', '아이템 구매 시 포인트 획득(1000단위당)', 'True'])
            writer.writerow(['9', 'stock_trade', '2', '주식 거래 시 포인트 획득(1000단위당)', 'True'])
            writer.writerow(['10', 'referral', '50', '친구 초대 시 포인트 획득', 'True'])
            writer.writerow(['11', 'achievement', '100', '업적 달성 시 포인트 획득', 'True'])
            writer.writerow(['12', 'level_up', '25', '레벨 업 시 포인트 획득', 'True'])
            writer.writerow(['13', 'streak_login', '5', '연속 로그인 보너스(일당)', 'True'])
            writer.writerow(['14', 'first_game', '20', '첫 게임 참여 시 포인트 획득', 'True'])
            writer.writerow(['15', 'birthday', '100', '생일 축하 포인트', 'True'])

    # reward_items.csv
    if not os.path.exists(CSV_FILES['reward_items']):
        with open(CSV_FILES['reward_items'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'description', 'price', 'type', 'effect', 'effect_value', 'duration', 'level_required', 'image_url', 'enabled'])
            writer.writerow(['1', '게임 부스트', '다음 게임에서 배당률 10% 증가', '500', 'boost', 'game_boost', '10', '1', '2', '/static/img/rewards/game_boost.png', 'True'])
            writer.writerow(['2', '송금 수수료 면제', '다음 송금 시 수수료 면제', '1000', 'discount', 'transfer_fee', '100', '1', '3', '/static/img/rewards/transfer_free.png', 'True'])
            writer.writerow(['3', '주식 부스트', '다음 주식 거래 시 이익 15% 증가', '2000', 'boost', 'stock_boost', '15', '1', '3', '/static/img/rewards/stock_boost.png', 'True'])
            writer.writerow(['4', 'VIP 티켓', '전용 VIP 혜택 3일간 이용', '5000', 'status', 'vip_status', '1', '72', '5', '/static/img/rewards/vip_ticket.png', 'True'])
            writer.writerow(['5', '경험치 부스트', '모든 포인트 획득량 2배로 적용', '3000', 'boost', 'point_boost', '100', '24', '4', '/static/img/rewards/xp_boost.png', 'True'])

    # user_levels.csv - 사용자 레벨 진행 상황
    if not os.path.exists(CSV_FILES['user_levels']):
        with open(CSV_FILES['user_levels'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'level', 'current_points', 'total_points', 'last_updated'])
            writer.writerow(['1', 'admin', '1', '0', '0', str(datetime.now())])

    # achievements.csv
    if not os.path.exists(CSV_FILES['achievements']):
        with open(CSV_FILES['achievements'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'code', 'name', 'description', 'category', 'level', 'points', 'requirement', 'requirement_value', 'hidden', 'icon_url', 'enabled'])
            writer.writerow(['1', 'first_login', '첫 로그인', '처음으로 로그인하셨습니다!', '계정', '쉬움', '10', 'login_count', '1', 'False', '/static/img/achievements/first_login.png', 'True'])
            writer.writerow(['2', 'login_master', '로그인 마스터', '10일 연속 로그인하셨습니다!', '계정', '중간', '50', 'login_streak', '10', 'False', '/static/img/achievements/login_master.png', 'True'])
            writer.writerow(['3', 'transfer_first', '첫 송금', '첫 송금을 완료하셨습니다!', '송금', '쉬움', '15', 'transfer_count', '1', 'False', '/static/img/achievements/transfer_first.png', 'True'])
            writer.writerow(['4', 'transfer_100k', '대량 송금', '한 번에 10만 이상 송금하셨습니다!', '송금', '중간', '30', 'transfer_amount', '100000', 'False', '/static/img/achievements/transfer_100k.png', 'True'])
            writer.writerow(['5', 'game_winner', '게임 승리자', '게임에서 첫 승리를 거두셨습니다!', '게임', '쉬움', '20', 'game_win_count', '1', 'False', '/static/img/achievements/game_winner.png', 'True'])
            writer.writerow(['6', 'big_winner', '대박 승리', '배팅 금액의 2배 이상 획득하셨습니다!', '게임', '중간', '50', 'big_win_count', '1', 'False', '/static/img/achievements/big_winner.png', 'True'])
            writer.writerow(['7', 'stock_trader', '주식 거래자', '첫 주식 거래를 완료하셨습니다!', '주식', '쉬움', '15', 'stock_trade_count', '1', 'False', '/static/img/achievements/stock_trader.png', 'True'])
            writer.writerow(['8', 'stock_profit', '주식 수익', '주식 거래로 수익을 냈습니다!', '주식', '중간', '30', 'stock_profit', '1000', 'False', '/static/img/achievements/stock_profit.png', 'True'])
            writer.writerow(['9', 'market_shopper', '쇼핑객', '마켓에서 첫 구매를 하셨습니다!', '마켓', '쉬움', '10', 'market_purchase_count', '1', 'False', '/static/img/achievements/market_shopper.png', 'True'])
            writer.writerow(['10', 'weapon_master', '무기 마스터', '다양한 무기 아이템을 구매하셨습니다!', '마켓', '어려움', '100', 'weapon_item_count', '5', 'False', '/static/img/achievements/weapon_master.png', 'True'])

    # user_achievements.csv
    if not os.path.exists(CSV_FILES['user_achievements']):
        with open(CSV_FILES['user_achievements'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'achievement_code', 'progress', 'completed', 'completed_at'])
            writer.writerow(['1', 'admin', 'first_login', '1', 'True', str(datetime.now())])

    # levels.csv - 레벨 시스템 설정
    if not os.path.exists(CSV_FILES['levels']):
        with open(CSV_FILES['levels'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['level', 'title', 'required_points', 'bonus_reward', 'description', 'icon_url', 'enabled'])
            writer.writerow(['1', '초보자', '0', '0', '체스제국 송금 시스템에 가입한 초보 사용자입니다.', '/static/img/levels/level1.png', 'True'])
            writer.writerow(['2', '견습생', '1000', '500', '기본적인 시스템 기능을 익힌 견습생입니다.', '/static/img/levels/level2.png', 'True'])
            writer.writerow(['3', '일반 사용자', '3000', '1000', '체스제국 송금 시스템을 능숙하게 이용하는 사용자입니다.', '/static/img/levels/level3.png', 'True'])
            writer.writerow(['4', '숙련자', '7000', '2000', '다양한 기능을 활용하는 숙련된 사용자입니다.', '/static/img/levels/level4.png', 'True'])
            writer.writerow(['5', '전문가', '12000', '3000', '송금 시스템의 모든 기능을 자유자재로 사용하는 전문가입니다.', '/static/img/levels/level5.png', 'True'])

    # quests.csv - 퀘스트 설정
    if not os.path.exists(CSV_FILES['quests']):
        with open(CSV_FILES['quests'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'title', 'description', 'type', 'goal_action', 'goal_value', 'reward_type', 'reward_value', 'difficulty', 'time_limit_hours', 'prerequisite_quest_id', 'enabled'])
            writer.writerow(['daily1', '송금 3회 하기', '오늘 송금을 3회 이상 해보세요.', 'daily', 'transfer_count', '3', 'points', '15', 'easy', '24', '', 'True'])
            writer.writerow(['daily2', '게임 5회 플레이', '오늘 게임을 5회 이상 플레이해보세요.', 'daily', 'game_play_count', '5', 'points', '15', 'easy', '24', '', 'True'])
            writer.writerow(['daily3', '채팅 10회 하기', '오늘 채팅 메시지를 10회 이상 작성해보세요.', 'daily', 'chat_message_count', '10', 'points', '10', 'easy', '24', '', 'True'])
            writer.writerow(['weekly1', '30회 송금하기', '이번 주에 총 30회 이상 송금해보세요.', 'weekly', 'transfer_count', '30', 'points', '50', 'medium', '168', '', 'True'])
            writer.writerow(['weekly2', '게임 20회 승리', '이번 주에 게임에서 총 20회 이상 승리해보세요.', 'weekly', 'game_win_count', '20', 'points', '75', 'hard', '168', '', 'True'])

    # user_quests.csv - 사용자 퀘스트 진행 상황
    if not os.path.exists(CSV_FILES['user_quests']):
        with open(CSV_FILES['user_quests'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'quest_id', 'progress', 'completed', 'started_at', 'completed_at', 'expires_at'])
            writer.writerow(['1', 'admin', 'daily1', '3', 'True', str(datetime.now()), str(datetime.now()), ''])

    # CSV 파일 초기 구조 확인 및 생성 함수에 추가
    # characters.csv
    if not os.path.exists(CSV_FILES['characters']):
        with open(CSV_FILES['characters'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                'id', 'user_id', 'name', 'class', 'level', 'exp', 'next_level_exp', 
                'strength', 'dexterity', 'intelligence', 'vitality', 'luck', 
                'stat_points', 'battles', 'wins', 'losses', 'is_active', 'created_at'
            ])

    # character_skills.csv
    if not os.path.exists(CSV_FILES['character_skills']):
        with open(CSV_FILES['character_skills'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                'id', 'character_id', 'skill_id', 'skill_name', 'skill_level', 
                'acquired_at'
            ])


# 애플리케이션 시작 시 CSV 파일 초기화
init_csv_files()

# 모듈 임포트
from auth import auth_bp
from admin import admin_bp
from market import market_bp
from games import games_bp
from stocks import stocks_bp
from chat import chat_bp
from friends import friends_bp
from rewards import rewards_bp
from events import events_bp
from character import character_bp

# 블루프린트 등록
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(market_bp)
app.register_blueprint(games_bp)
app.register_blueprint(stocks_bp)
app.register_blueprint(events_bp)
app.register_blueprint(character_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(friends_bp)
app.register_blueprint(rewards_bp)

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        with open(CSV_FILES['users'], 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for user in reader:
                if user['id'] == user_id:
                    g.user = user
                    break
            else:
                g.user = None

# 템플릿 context processor - 모든 템플릿에서 시스템 설정에 접근할 수 있게 합니다
@app.context_processor
def inject_system_config():
    from utils_fix import get_system_config, get_user_points, get_user_level

    system_config = get_system_config()

    # 현재 로그인한 사용자의 포인트 및 레벨 정보
    user_points = 0
    user_level = {'current': {'level': '1', 'name': '초보자'}, 'next': None, 'points': 0}

    if hasattr(g, 'user') and g.user:
        user_points = get_user_points(g.user['id'])
        user_level = get_user_level(g.user['id'])

    return {
        'system_config': system_config,
        'app_name': system_config.get('app_name', '체스제국'),
        'system_name': system_config.get('system_name', '체스제국 송금 시스템'),
        'country_name': system_config.get('country_name', '체스제국'),
        'currency_name': system_config.get('currency_name', '체스머니'),
        'currency_symbol': system_config.get('currency_symbol', 'CM'),
        'primary_color': system_config.get('primary_color', '#3f51b5'),
        'secondary_color': system_config.get('secondary_color', '#f50057'),
        'theme': system_config.get('theme', 'light'),
        'maintenance_mode': system_config.get('maintenance_mode', 'False'),
        'footer_message': system_config.get('footer_message', '© 2025 체스제국 송금 시스템'),
        'user_points': user_points,
        'user_level': user_level
    }

# 템플릿에서 사용할 전역 함수 등록
@app.context_processor
def utility_processor():
    return {
        'int': int,
        'float': float,
        'str': str
    }

@app.route('/')
def index():
    if g.user:
        return redirect(url_for('home'))
    return redirect(url_for('auth.login'))

@app.route('/home')
def home():
    if not g.user:
        return redirect(url_for('auth.login'))

    # 시스템 설정 불러오기
    from utils import get_system_config
    system_config = get_system_config()

    # 공지사항 가져오기
    notices = []
    try:
        with open(CSV_FILES['notices'], 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                notices.append(row)
    except Exception as e:
        logging.error(f"공지사항을 로드하는 중 오류가 발생했습니다: {e}")

    return render_template('home.html', notices=notices, system_config=system_config, user=g.user)

# 시스템 점검 페이지
@app.route('/maintenance')
def maintenance():
    # 시스템 설정 불러오기
    from utils import get_system_config
    system_config = get_system_config()

    # 점검 모드가 아니면 메인 페이지로 리다이렉트
    if system_config.get('maintenance_mode', 'False') == 'False':
        return redirect(url_for('index'))

    # 점검 관련 정보
    maintenance_reason = system_config.get('maintenance_reason', '시스템 점검 중입니다.')
    maintenance_until = system_config.get('maintenance_until', '빠른 시일 내')

    return render_template('maintenance.html', 
                           system_config=system_config,
                           maintenance_reason=maintenance_reason,
                           maintenance_until=maintenance_until)

# 에러 핸들러 추가
@app.errorhandler(404)
def page_not_found(e):
    # 시스템 설정 불러오기
    from utils import get_system_config
    system_config = get_system_config()

    return render_template('errors/404.html', system_config=system_config), 404

@app.errorhandler(500)
def internal_server_error(e):
    # 시스템 설정 불러오기
    from utils import get_system_config
    system_config = get_system_config()

    # 로그에 오류 기록
    app.logger.error(f"500 오류 발생: {str(e)}")

    return render_template('errors/500.html', system_config=system_config), 500

@app.errorhandler(Exception)
def internal_server_error(e):
    # 시스템 설정 불러오기
    from utils import get_system_config
    system_config = get_system_config()

    # 로그에 오류 기록
    app.logger.error(f"500 오류 발생: {str(e)}")

    return render_template('errors/500.html', system_config=system_config), 500


@app.errorhandler(403)
def forbidden(e):
    # 시스템 설정 불러오기
    from utils import get_system_config
    system_config = get_system_config()

    return render_template('errors/403.html', system_config=system_config), 403

# 사용자 환경설정 저장 API
@app.route('/save_user_preference', methods=['POST'])
def save_user_preference():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    # 요청 데이터 확인
    if not request.is_json:
        return jsonify({'success': False, 'message': '올바른 형식의 요청이 아닙니다.'}), 400

    data = request.get_json()
    preference_type = data.get('preference_type')
    preference_value = data.get('preference_value')

    if not preference_type or preference_value is None:
        return jsonify({'success': False, 'message': '필수 값이 누락되었습니다.'}), 400

    # 사용자 환경설정 CSV 파일 경로
    user_preferences_file = 'data/user_preferences.csv'

    # 파일이 없으면 생성
    if not os.path.exists(user_preferences_file):
        # 디렉토리 확인
        os.makedirs(os.path.dirname(user_preferences_file), exist_ok=True)

        with open(user_preferences_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'preference_type', 'preference_value', 'updated_at'])

    # 사용자의 기존 환경설정 가져오기
    from utils import read_csv, append_to_csv, generate_id

    preferences = read_csv(user_preferences_file)
    found = False
    updated_preferences = []

    # 기존 설정 업데이트
    for pref in preferences:
        if pref.get('user_id') == session['user_id'] and pref.get('preference_type') == preference_type:
            pref['preference_value'] = preference_value
            pref['updated_at'] = str(datetime.now())
            found = True
        updated_preferences.append(pref)

    # 새 설정 추가
    if not found:
        new_preference = {
            'id': generate_id(),
            'user_id': session['user_id'],
            'preference_type': preference_type,
            'preference_value': preference_value,
            'updated_at': str(datetime.now())
        }
        updated_preferences.append(new_preference)

        # 파일에 항목이 없는 경우 직접 추가
        if not preferences:
            append_to_csv(user_preferences_file, new_preference)
            return jsonify({'success': True, 'message': '환경설정이 저장되었습니다.'})

    # CSV 파일에 다시 쓰기
    with open(user_preferences_file, 'w', newline='', encoding='utf-8') as file:
        if updated_preferences:
            writer = csv.DictWriter(file, fieldnames=updated_preferences[0].keys())
            writer.writeheader()
            writer.writerows(updated_preferences)

    return jsonify({'success': True, 'message': '환경설정이 저장되었습니다.'})

# 유지보수 모드 전환 API (관리자용)
@app.route('/api/toggle_maintenance', methods=['POST'])
def toggle_maintenance():
    # 관리자 확인
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    # 관리자 권한 확인
    from utils import get_user_by_id
    user = get_user_by_id(session['user_id'])
    if not user or user.get('is_admin') != 'True':
        return jsonify({'success': False, 'message': '관리자 권한이 필요합니다.'}), 403

    # 요청 데이터 확인
    if not request.is_json:
        return jsonify({'success': False, 'message': '올바른 형식의 요청이 아닙니다.'}), 400

    data = request.get_json()
    maintenance_mode = data.get('maintenance_mode', False)
    maintenance_reason = data.get('maintenance_reason', '시스템 점검 중입니다.')
    maintenance_until = data.get('maintenance_until', '빠른 시일 내')

    # 시스템 설정 업데이트
    from utils import update_system_config

    update_system_config('maintenance_mode', 'True' if maintenance_mode else 'False')
    update_system_config('maintenance_reason', maintenance_reason)
    update_system_config('maintenance_until', maintenance_until)

    # 유지보수 모드 로그 기록
    log_file = 'data/system_logs.csv'
    if not os.path.exists(log_file):
        with open(log_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'action', 'details', 'timestamp'])

    from utils import append_to_csv, generate_id

    log_entry = {
        'id': generate_id(),
        'user_id': session['user_id'],
        'action': 'maintenance_mode_toggle',
        'details': f"Maintenance mode changed to: {maintenance_mode}, Reason: {maintenance_reason}",
        'timestamp': str(datetime.now())
    }

    append_to_csv(log_file, log_entry)

    return jsonify({
        'success': True, 
        'message': f"유지보수 모드가 {'활성화' if maintenance_mode else '비활성화'}되었습니다."
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
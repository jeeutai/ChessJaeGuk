import os
import csv
import uuid
import qrcode
import io
import base64
from datetime import datetime
from flask import g, request
from app import CSV_FILES

# CSV 파일 경로 확장
CSV_FILES.update({
    'points': 'data/points.csv',
    'point_logs': 'data/point_logs.csv',
    'reward_config': 'data/reward_config.csv',
    'reward_items': 'data/reward_items.csv',
    'user_levels': 'data/user_levels.csv',
    'achievements': 'data/achievements.csv',
    'user_achievements': 'data/user_achievements.csv'
})

# 시스템 설정 읽기
def get_system_config():
    system_config = {}
    system_config_path = 'data/system_config.csv'
    
    if os.path.exists(system_config_path):
        with open(system_config_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                system_config[row['key']] = row['value']
    
    return system_config

# 게임 설정 읽기
def get_games_config():
    games = []
    games_config_path = 'data/games_config.csv'
    
    if os.path.exists(games_config_path):
        with open(games_config_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            games = list(reader)
    
    return games

# 정치인 정보 읽기
def get_politicians():
    politicians = []
    politicians_path = 'data/politicians.csv'
    
    if os.path.exists(politicians_path):
        with open(politicians_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            politicians = list(reader)
    
    return politicians

# 주식 설정 읽기
def get_stocks_config():
    stocks = []
    stocks_config_path = 'data/stocks_config.csv'
    
    if os.path.exists(stocks_config_path):
        with open(stocks_config_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            stocks = list(reader)
    
    return stocks

# 마켓 아이템 설정 읽기
def get_market_items_config():
    items = []
    market_items_path = 'data/market_items.csv'
    
    if os.path.exists(market_items_path):
        with open(market_items_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            items = list(reader)
    
    return items

# 시스템 설정 업데이트
def update_system_config(key, value):
    system_config_path = 'data/system_config.csv'
    
    if not os.path.exists(system_config_path):
        return False
    
    configs = []
    with open(system_config_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['key'] == key:
                row['value'] = value
            configs.append(row)
    
    with open(system_config_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['key', 'value', 'description'])
        writer.writeheader()
        writer.writerows(configs)
    
    return True

# 새 ID 생성 함수
def generate_id():
    return str(uuid.uuid4())

# 현재 시간 문자열 반환
def get_timestamp():
    return str(datetime.now())

# 사용자 ID로 사용자 정보 가져오기
def get_user_by_id(user_id):
    with open(CSV_FILES['users'], 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for user in reader:
            if user['id'] == user_id:
                return user
    return None

# 사용자명으로 사용자 정보 가져오기
def get_user_by_username(username):
    with open(CSV_FILES['users'], 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for user in reader:
            if user['id'] == username:
                return user
    return None

# CSV 파일에 새 행 추가
def append_to_csv(csv_file, row_dict):
    file_exists = os.path.isfile(csv_file)
    
    if file_exists:
        # 파일이 존재하면 헤더 읽기
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames if reader.fieldnames else list(row_dict.keys())
    else:
        # 파일이 없으면 딕셔너리 키를 헤더로 사용
        fieldnames = list(row_dict.keys())
    
    # CSV 파일에 정의되지 않은 필드 제거
    filtered_row = {k: v for k, v in row_dict.items() if k in fieldnames}
    
    with open(csv_file, 'a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(filtered_row)

# CSV 파일 전체 읽기
def read_csv(csv_file):
    if not os.path.exists(csv_file):
        return []
    
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        return list(reader)

# CSV 파일 업데이트
def update_csv(csv_file, updated_rows, key_field='id'):
    # 파일 경로가 None인 경우 처리
    if csv_file is None:
        return False
        
    rows = read_csv(csv_file)
    
    # 기존 CSV가 비어있는 경우
    if not rows and updated_rows:
        with open(csv_file, 'w', newline='', encoding='utf-8') as file:
            # 필드명은 updated_rows의 첫 번째 행의 키로 설정
            fieldnames = updated_rows[0].keys()
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)
        return True
    
    # 빈 배열인 경우 처리
    if not rows or not updated_rows:
        return False
    
    # 키 필드 기준으로 일치하는 행 업데이트
    for i, row in enumerate(rows):
        for updated_row in updated_rows:
            # 키 필드가 없는 경우 건너뛰기
            if key_field not in row or key_field not in updated_row:
                continue
                
            if row[key_field] == updated_row[key_field]:
                rows[i] = updated_row
    
    # 새로운 fieldnames 생성: rows와 updated_rows의 키를 합친 값
    # 새로운 fieldnames 생성: rows와 updated_rows의 키를 합친 값
    all_keys = set()
    for row in rows:
        all_keys.update(row.keys())
    for row in updated_rows:
        all_keys.update(row.keys())

    
    fieldnames = list(all_keys)
    
    # CSV 파일에 다시 쓰기
    with open(csv_file, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        
        # 각 행에 필드가 없는 경우 None으로 설정
        for row in rows:
            for field in fieldnames:
                if field not in row:
                    row[field] = None
        
        writer.writerows(rows)
        
    return True

# 사용자 잔액 업데이트
def update_user_balance(user_id, amount, operation="add"):
    users = read_csv(CSV_FILES['users'])
    updated_users = []
    
    for user in users:
        if user['id'] == user_id:
            current_balance = int(user['balance'])
            if operation == "add":
                user['balance'] = str(current_balance + amount)
            elif operation == "subtract":
                user['balance'] = str(max(0, current_balance - amount))
            elif operation == "set":
                user['balance'] = str(amount)
        updated_users.append(user)
    
    update_csv(CSV_FILES['users'], updated_users)

# 거래 기록 추가
def add_transaction(sender_id, receiver_id, amount, type_):
    transaction = {
        'id': generate_id(),
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'amount': str(amount),
        'type': type_,
        'timestamp': get_timestamp()
    }
    append_to_csv(CSV_FILES['transactions'], transaction)

# 로그인 로그 추가
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

def get_character_by_user_id(user_id):
    """사용자 ID로 캐릭터 정보 가져오기"""
    characters = read_csv(CSV_FILES['characters'])
    for character in characters:
        if character.get('user_id') == user_id:
            return character
    return None

def get_character_skills(character_id):
    """캐릭터 ID로 스킬 목록 가져오기"""
    skills = []
    character_skills = read_csv(CSV_FILES['character_skills'])
    
    for skill in character_skills:
        if skill.get('character_id') == character_id:
            skills.append(skill)
    
    return skills

def update_csv(file_path, data):
    """CSV 파일 전체 업데이트"""
    if not data:
        return False
    
    with open(file_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    
    return True

def get_battle_logs_by_user_id(user_id):
    """사용자 ID로 배틀 로그 가져오기"""
    battle_logs = []
    character = get_character_by_user_id(user_id)
    
    if not character:
        return battle_logs
    
    character_id = character.get('id')
    
    # 배틀 로그 파일이 없으면 빈 리스트 반환
    if not os.path.exists(CSV_FILES['battle_logs']):
        return battle_logs
    
    with open(CSV_FILES['battle_logs'], 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row.get('attacker_id') == character_id or row.get('defender_id') == character_id:
                battle_logs.append(row)
    
    # 최신 로그가 먼저 오도록 정렬
    battle_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return battle_logs


# QR 코드 생성
def generate_qr_code(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # 이미지를 base64 인코딩
    buffer = io.BytesIO()
    img.save(buffer)
    return base64.b64encode(buffer.getvalue()).decode()

# 주민등록증 생성
def generate_id_card(user):
    # 기본 정보로 주민등록증 텍스트 생성
    id_card_data = f"{user['id']},{user['nickname']},{user['birth_date']},{datetime.now().strftime('%Y-%m-%d')}"
    
    # QR 코드 생성
    qr_code = generate_qr_code(id_card_data)
    
    return {
        'user_id': user['id'],
        'name': user['nickname'],
        'birth_date': user['birth_date'],
        'issue_date': datetime.now().strftime('%Y-%m-%d'),
        'qr_code': qr_code
    }

# 게임 로그 추가
def add_game_log(user_id, game_type, bet_amount, result):
    log = {
        'id': generate_id(),
        'user_id': user_id,
        'game_type': game_type,
        'bet_amount': str(bet_amount),
        'result': result,
        'timestamp': get_timestamp()
    }
    append_to_csv(CSV_FILES['game_logs'], log)

# 마트 로그 추가
def add_market_log(user_id, item_id, quantity, price):
    log = {
        'id': generate_id(),
        'user_id': user_id,
        'item_id': item_id,
        'quantity': str(quantity),
        'price': str(price),
        'timestamp': get_timestamp()
    }
    append_to_csv(CSV_FILES['market_logs'], log)

# 아이템 정보 가져오기
def get_item(item_id):
    with open(CSV_FILES['items'], 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for item in reader:
            if item['id'] == item_id:
                return item
    return None

# 주식 정보 업데이트
def update_stock(stock_id, current_price):
    stocks = read_csv(CSV_FILES['stocks'])
    updated_stocks = []
    
    for stock in stocks:
        if stock['id'] == stock_id:
            previous_price = float(stock['current_price'])
            stock['previous_price'] = str(previous_price)
            stock['current_price'] = str(current_price)
            
            change = ((current_price - previous_price) / previous_price) * 100
            stock['change_percent'] = f"{change:.2f}"
            stock['last_update'] = get_timestamp()
        updated_stocks.append(stock)
    
    update_csv(CSV_FILES['stocks'], updated_stocks)

# 채팅 메시지 추가
def add_chat_message(user_id, message):
    msg = {
        'id': generate_id(),
        'user_id': user_id,
        'message': message,
        'timestamp': get_timestamp()
    }
    append_to_csv(CSV_FILES['chat_messages'], msg)

# 가장 최근 채팅 메시지 가져오기
def get_recent_chat_messages(limit=50):
    messages = read_csv(CSV_FILES['chat_messages'])
    messages.sort(key=lambda x: x['timestamp'], reverse=True)
    return messages[:limit]

# 포인트 관련 유틸리티 함수 ------------------------------------------------

# 포인트 보상 규칙 가져오기
def get_reward_config():
    reward_config = {}
    rewards_data = read_csv(CSV_FILES['reward_config'])
    
    for reward in rewards_data:
        if reward.get('enable', 'True').lower() == 'true':
            reward_config[reward['action']] = {
                'id': reward['id'],
                'points': int(reward['points']),
                'description': reward['description']
            }
    
    return reward_config

# 사용자 포인트 가져오기
def get_user_points(user_id):
    total_points = 0
    point_logs_data = read_csv(CSV_FILES['point_logs'])
    
    for point_record in point_logs_data:
        if point_record.get('user_id') == user_id:
            total_points += int(point_record.get('points', 0))
    
    return total_points

# 포인트 지급
def add_points(user_id, points, reason):
    # 포인트 로그 추가
    point_log = {
        'id': generate_id(),
        'user_id': user_id,
        'action_code': reason,
        'points': str(points),
        'reason': reason,
        'timestamp': get_timestamp()
    }
    
    append_to_csv(CSV_FILES['point_logs'], point_log)
    
    # 사용자 레벨 업데이트 체크
    update_user_level(user_id, points)
    
    return point_log

# 사용자 레벨 확인 및 업데이트
def update_user_level(user_id, new_points=0):
    user_level_data = None
    user_levels = read_csv(CSV_FILES['user_levels'])
    
    # 사용자 레벨 데이터 확인
    for level_data in user_levels:
        if level_data.get('user_id') == user_id:
            user_level_data = level_data
            break
    
    # 사용자 레벨 데이터가 없으면 생성
    if not user_level_data:
        user_level_data = {
            'user_id': user_id,
            'level': '1',
            'current_points': '0',
            'total_points': '0',
            'last_updated': get_timestamp()
        }
        append_to_csv(CSV_FILES['user_levels'], user_level_data)
    
    # 포인트 업데이트
    current_points = int(user_level_data.get('current_points', 0)) + new_points
    total_points = int(user_level_data.get('total_points', 0)) + new_points
    
    # 레벨 정보 가져오기
    levels = read_csv(CSV_FILES['levels'])
    levels.sort(key=lambda x: int(x.get('required_points', 0)))
    
    # 현재 레벨 확인
    current_level = 1
    for level in levels:
        if total_points >= int(level.get('required_points', 0)):
            current_level = int(level.get('level', 1))
        else:
            break
    
    # 레벨업 여부 확인
    if current_level > int(user_level_data.get('level', 1)):
        # 레벨업 보상 지급
        for level in levels:
            if int(level.get('level', 0)) == current_level:
                bonus_reward = int(level.get('bonus_reward', 0))
                if bonus_reward > 0:
                    update_user_balance(user_id, bonus_reward, "add")
                    add_transaction('system', user_id, bonus_reward, 'level_up_bonus')
                break
    
    # 사용자 레벨 데이터 업데이트
    updated_user_levels = []
    for level_data in user_levels:
        if level_data.get('user_id') == user_id:
            level_data['level'] = str(current_level)
            level_data['current_points'] = str(current_points)
            level_data['total_points'] = str(total_points)
            level_data['last_updated'] = get_timestamp()
        updated_user_levels.append(level_data)
    
    update_csv(CSV_FILES['user_levels'], updated_user_levels)

# 보상 아이템 목록 가져오기
def get_reward_items():
    items = read_csv(CSV_FILES['reward_items'])
    enabled_items = [item for item in items if item.get('enabled', 'True').lower() == 'true']
    return enabled_items

# 보상 아이템 구매
def purchase_reward_item(user_id, item_id):
    items = read_csv(CSV_FILES['reward_items'])
    user_points = get_user_points(user_id)
    
    for item in items:
        if item['id'] == item_id:
            if item.get('enabled', 'True').lower() != 'true':
                return {
                    'success': False,
                    'message': '이 아이템은 현재 구매할 수 없습니다.'
                }
            
            if int(item.get('stock', 0)) <= 0:
                return {
                    'success': False,
                    'message': '재고가 소진되었습니다.'
                }
            
            # 가격 확인 (price 필드 사용)
            cost = int(item.get('price', 0))
            if user_points < cost:
                return {
                    'success': False,
                    'message': '포인트가 부족합니다.'
                }
            
            # 레벨 제한 확인
            required_level = int(item.get('level_required', 1))
            user_level_info = get_user_level(user_id)
            user_current_level = int(user_level_info['current']['level'])
            
            if user_current_level < required_level:
                return {
                    'success': False,
                    'message': f'이 아이템은 레벨 {required_level} 이상부터 구매 가능합니다.'
                }
            
            # 아이템 효과 적용
            effect_result = apply_item_effect(user_id, item)
            
            if effect_result['success']:
                # 포인트 차감
                add_points(user_id, -cost, f"아이템 구매: {item['name']}")
                
                # 재고 감소
                if item.get('stock') and int(item['stock']) > 0:
                    updated_items = []
                    for i in items:
                        if i['id'] == item_id:
                            i['stock'] = str(int(i['stock']) - 1)
                        updated_items.append(i)
                    
                    update_csv(CSV_FILES['reward_items'], updated_items)
                
                return {
                    'success': True,
                    'message': f"{item['name']} 아이템을 성공적으로 구매했습니다.",
                    'effect': effect_result['message']
                }
            else:
                return effect_result
            
    return {
        'success': False,
        'message': '존재하지 않는 아이템입니다.'
    }

# 아이템 효과 적용
def apply_item_effect(user_id, item):
    # 새로운 CSV 구조에 맞게 필드명 업데이트
    effect_type = item.get('type', '')
    effect = item.get('effect', '')
    effect_value = item.get('effect_value', '0')
    duration = int(item.get('duration', 0))
    
    if effect_type == 'boost':
        # 각종 부스트 효과
        if effect == 'game_boost':
            # 게임 승률 부스트 효과 적용 로직
            return {
                'success': True,
                'message': f"다음 게임 승률이 {effect_value}% 증가합니다. (유효기간: {duration}일)"
            }
        elif effect == 'stock_boost':
            # 주식 거래 이익 증가 효과 적용 로직
            return {
                'success': True,
                'message': f"다음 주식 거래 이익이 {effect_value}% 증가합니다. (유효기간: {duration}일)"
            }
        elif effect == 'point_boost':
            # 포인트 획득량 증가 효과 적용 로직
            return {
                'success': True,
                'message': f"포인트 획득량이 {effect_value}% 증가합니다. (유효기간: {duration}시간)"
            }
    elif effect_type == 'discount':
        # 수수료 면제 등 할인 효과
        if effect == 'transfer_fee':
            # 송금 수수료 면제 효과 적용 로직
            return {
                'success': True,
                'message': f"다음 {duration}회 송금 시 수수료가 면제됩니다."
            }
    elif effect_type == 'status':
        # 상태 효과 (VIP 등)
        if effect == 'vip_status':
            # VIP 상태 효과 적용 로직
            return {
                'success': True,
                'message': f"VIP 상태가 {duration}시간 동안 적용됩니다."
            }
    
    return {
        'success': True,
        'message': f"{item['name']} 아이템 효과가 적용되었습니다."
    }

# 업적 관련 유틸리티 함수 ------------------------------------------------

# 사용자 레벨 정보 가져오기
def get_user_level(user_id):
    # 사용자 레벨 데이터 조회
    user_level_data = None
    user_levels = read_csv(CSV_FILES['user_levels'])
    
    for level_data in user_levels:
        if level_data.get('user_id') == user_id:
            user_level_data = level_data
            break
    
    # 레벨 정보가 없으면 기본값 생성
    if not user_level_data:
        user_level_data = {
            'id': generate_id(),
            'user_id': user_id,
            'level': '1',
            'current_points': '0',
            'total_points': '0',
            'last_updated': get_timestamp()
        }
        append_to_csv(CSV_FILES['user_levels'], user_level_data)
    
    # 레벨 시스템 정보 가져오기
    levels_info = read_csv(CSV_FILES['levels'])
    levels_info.sort(key=lambda x: int(x.get('required_points', 0)))
    
    # 현재 레벨 정보
    current_level_info = None
    for level_info in levels_info:
        if level_info.get('level') == user_level_data.get('level'):
            current_level_info = level_info
            break
    
    # 현재 레벨 정보가 없으면 첫 번째 레벨 사용
    if not current_level_info and levels_info:
        current_level_info = levels_info[0]
    
    # 다음 레벨 정보 찾기
    next_level_info = None
    current_level_num = int(user_level_data.get('level', '1'))
    
    for level_info in levels_info:
        if int(level_info.get('level', '0')) > current_level_num:
            next_level_info = level_info
            break
    
    # 사용자 총 포인트
    user_points = int(user_level_data.get('total_points', '0'))
    
    # 레벨 정보 반환
    return {
        'current': {
            'level': user_level_data.get('level', '1'),
            'title': current_level_info.get('title', '초보자') if current_level_info else '초보자',
            'required_points': current_level_info.get('required_points', '0') if current_level_info else '0',
            'bonus_reward': current_level_info.get('bonus_reward', '0') if current_level_info else '0',
            'description': current_level_info.get('description', '') if current_level_info else '',
            'icon_url': current_level_info.get('icon_url', '') if current_level_info else ''
        },
        'next': next_level_info,
        'points': user_points,
        'current_points': int(user_level_data.get('current_points', '0')),
        'last_updated': user_level_data.get('last_updated', '')
    }

# 업적 목록 가져오기
def get_achievements():
    return read_csv(CSV_FILES['achievements'])

# 사용자 업적 목록 가져오기
def get_user_achievements(user_id):
    user_achievements = read_csv(CSV_FILES['user_achievements'])
    user_achievements = [a for a in user_achievements if a.get('user_id') == user_id]
    
    # 전체 업적 목록
    all_achievements = get_achievements()
    
    # 사용자 업적 상태 추가
    result = []
    for achievement in all_achievements:
        achievement_code = achievement.get('code')
        user_progress = next((a for a in user_achievements if a.get('achievement_code') == achievement_code), None)
        
        if user_progress:
            result.append({
                **achievement,
                'progress': user_progress.get('progress', '0'),
                'completed': user_progress.get('completed', 'False') == 'True',
                'completed_at': user_progress.get('completed_at', '')
            })
        else:
            result.append({
                **achievement,
                'progress': '0',
                'completed': False,
                'completed_at': ''
            })
    
    # 카테고리별로 정렬
    result.sort(key=lambda x: (x.get('category', ''), x.get('level', ''), x.get('name', '')))
    
    return result

# 사용자 업적 업데이트
def update_achievement_progress(user_id, achievement_code, progress_value=1, increment=True):
    # 업적 정보 가져오기
    achievements = get_achievements()
    target_achievement = None
    
    for achievement in achievements:
        if achievement.get('code') == achievement_code:
            target_achievement = achievement
            break
    
    if not target_achievement:
        return False
    
    # 사용자 업적 진행 상태 가져오기
    user_achievements_data = read_csv(CSV_FILES['user_achievements'])
    user_achievement = None
    
    for a in user_achievements_data:
        if a.get('user_id') == user_id and a.get('achievement_code') == achievement_code:
            user_achievement = a
            break
    
    if user_achievement:
        # 이미 완료된 업적인 경우 업데이트 하지 않음
        if user_achievement.get('completed') == 'True':
            return False
        
        # 업적 진행도 업데이트
        updated_achievements = []
        for a in user_achievements_data:
            if a.get('user_id') == user_id and a.get('achievement_code') == achievement_code:
                current_progress = int(a.get('progress', 0))
                requirement_value = int(target_achievement.get('requirement_value', 0))
                
                if increment:
                    new_progress = current_progress + progress_value
                else:
                    new_progress = progress_value
                
                a['progress'] = str(new_progress)
                
                # 업적 달성 완료 시
                if new_progress >= requirement_value and a.get('completed') != 'True':
                    a['completed'] = 'True'
                    a['completed_at'] = get_timestamp()
                    
                    # 업적 포인트 보상 지급
                    points_reward = int(target_achievement.get('points', 0))
                    if points_reward > 0:
                        add_points(user_id, points_reward, f"업적 달성: {target_achievement.get('name')}")
            
            updated_achievements.append(a)
        
        update_csv(CSV_FILES['user_achievements'], updated_achievements)
    else:
        # 새 업적 진행 기록 생성
        progress = progress_value
        completed = False
        completed_date = ''
        
        requirement_value = int(target_achievement.get('requirement_value', 0))
        if progress >= requirement_value:
            completed = True
            completed_date = get_timestamp()
            
            # 업적 포인트 보상 지급
            points_reward = int(target_achievement.get('points', 0))
            if points_reward > 0:
                add_points(user_id, points_reward, f"업적 달성: {target_achievement.get('name')}")
        
        new_achievement = {
            'id': generate_id(),
            'user_id': user_id,
            'achievement_code': achievement_code,
            'progress': str(progress),
            'completed': str(completed),
            'completed_at': completed_date
        }
        
        append_to_csv(CSV_FILES['user_achievements'], new_achievement)
    
    return True

# 특정 이벤트에 따른 포인트 지급
def award_points_for_action(user_id, action, action_value=1):
    reward_config = get_reward_config()
    
    if action in reward_config:
        reward = reward_config[action]
        points = reward['points']
        
        # 특정 금액 기반 포인트 보상 (1000단위당 계산)
        if action in ['money_transfer', 'item_purchase', 'stock_trade']:
            points = int((action_value / 1000) * points)
            if points <= 0:
                points = 1  # 최소 1포인트 
        
        if points > 0:
            add_points(user_id, points, f"{reward['description']}")
            
            # 관련 업적 업데이트
            if action == 'daily_login':
                update_achievement_progress(user_id, 'first_login')
                
                # 연속 로그인 처리
                # TODO: 연속 로그인 업적 업데이트 로직 추가
            
            elif action == 'game_win':
                update_achievement_progress(user_id, 'game_addict')
                
                # 대박 승리 업적 업데이트
                if action_value >= 100000:
                    update_achievement_progress(user_id, 'big_winner', action_value, False)
            
            elif action == 'friend_add':
                update_achievement_progress(user_id, 'social_butterfly')
            
            elif action == 'chat_message':
                update_achievement_progress(user_id, 'chat_master')
                
                # 하루 채팅 30개 이상 업적
                # TODO: 하루 채팅수 카운트 로직 추가
                
            elif action == 'stock_trade':
                update_achievement_progress(user_id, 'trader')
                
                # 대규모 주식 거래 업적
                if action_value >= 100000:
                    update_achievement_progress(user_id, 'market_mover', 1)
                
                # 누적 거래액 기반 업적
                update_achievement_progress(user_id, 'trade_volume', action_value, False)
                
            elif action == 'market_purchase':
                update_achievement_progress(user_id, 'consumer')
                
                # 대규모 구매 업적
                if action_value >= 50000:
                    update_achievement_progress(user_id, 'big_spender', 1)
                
                # 누적 구매액 기반 업적
                update_achievement_progress(user_id, 'purchase_volume', action_value, False)
            
            return {
                'success': True,
                'points': points,
                'message': f"{reward['description']} - {points}포인트 획득!"
            }
    
    return {
        'success': False,
        'points': 0,
        'message': ''
    }

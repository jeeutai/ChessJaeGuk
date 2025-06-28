from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, session
from app import CSV_FILES, app
from utils import (
    read_csv, update_csv, append_to_csv, generate_id, update_user_balance,
    get_timestamp, add_points, add_transaction, get_system_config, get_user_by_id, get_battle_logs_by_user_id, get_character_by_user_id)
from datetime import datetime
import random
import os
import csv
import json
import uuid
import copy

character_bp = Blueprint('character', __name__, url_prefix='/character')

# 캐릭터 상태 효과
STATUS_EFFECTS = {
    'poison': {'name': '중독', 'damage': 2, 'duration': 3},
    'burn': {'name': '화상', 'damage': 3, 'duration': 2},
    'heal': {'name': '회복', 'heal': 2, 'duration': 3},
    'buff': {'name': '강화', 'bonus': 2, 'duration': 3}
}

# 캐릭터 직업
# 캐릭터 직업 정의
CHARACTER_CLASSES = {
    'warrior': {
        'name': '전사',
        'description': '강력한 물리 공격을 가하는 전사입니다.',
        'hp_bonus': 20,
        'mp_bonus': 0,
        'str_bonus': 5,
        'agi_bonus': 2,
        'int_bonus': 0,
        'icon': 'fas fa-shield-alt'
    },
    'mage': {
        'name': '마법사',
        'description': '강력한 마법을 사용하는 마법사입니다.',
        'hp_bonus': 0,
        'mp_bonus': 20,
        'str_bonus': 0,
        'agi_bonus': 2,
        'int_bonus': 5,
        'icon': 'fas fa-hat-wizard'
    },
    'archer': {
        'name': '궁수',
        'description': '빠른 공격과 회피가 특기인 궁수입니다.',
        'hp_bonus': 10,
        'mp_bonus': 10,
        'str_bonus': 2,
        'agi_bonus': 5,
        'int_bonus': 2,
        'icon': 'fas fa-bullseye'
    },
    'thief': {
        'name': '도적',
        'description': '은밀한 공격과 빠른 움직임이 특기인 도적입니다.',
        'hp_bonus': 5,
        'mp_bonus': 5,
        'str_bonus': 3,
        'agi_bonus': 7,
        'int_bonus': 0,
        'icon': 'fas fa-mask'
    },
    'cleric': {
        'name': '성직자',
        'description': '치유와 버프 마법을 사용하는 성직자입니다.',
        'hp_bonus': 10,
        'mp_bonus': 15,
        'str_bonus': 0,
        'agi_bonus': 0,
        'int_bonus': 7,
        'icon': 'fas fa-pray'
    }
}

# 아이템 효과
ITEM_EFFECTS = {
    'hp_potion': {'name': 'HP 포션', 'heal': 20, 'cost': 100},
    'mp_potion': {'name': 'MP 포션', 'mp_heal': 20, 'cost': 100},
    'str_potion': {'name': '힘의 물약', 'str_bonus': 5, 'duration': 5, 'cost': 200},
    'agi_potion': {'name': '민첩의 물약', 'agi_bonus': 5, 'duration': 5, 'cost': 200},
    'int_potion': {'name': '지능의 물약', 'int_bonus': 5, 'duration': 5, 'cost': 200}
}

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

def safe_int(value, default=0):
    """안전하게 정수로 변환하는 함수"""
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (ValueError, TypeError):
        return default

# CSV 파일 초기화 함수
def init_character_csv_files():
    """캐릭터 관련 CSV 파일 초기화"""
    # 캐릭터 CSV 파일
    if not os.path.exists(CSV_FILES.get('characters')):
        with open(CSV_FILES['characters'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'name', 'class', 'level', 'exp', 'hp', 'mp', 'strength', 'agility',
                           'intelligence', 'skill_points', 'gold', 'status_effects', 'equipment', 'inventory',
                           'wins', 'losses', 'quests_completed', 'last_training', 'pet_id', 'guild_id',
                           'title', 'achievement_points', 'avatar', 'color'])
   
    # 캐릭터 스킬 CSV 파일
    if not os.path.exists(CSV_FILES.get('character_skills')):
        with open(CSV_FILES['character_skills'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'character_id', 'skill_id', 'name', 'description', 'effect',
                           'effect_value', 'acquired_at', 'level', 'icon'])

# 초기화 실행
init_character_csv_files()

@character_bp.route('/')
def index():
    """캐릭터 메인 페이지"""
    if 'user_id' not in session:
        flash('로그인이 필요합니다.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        my_character = get_my_character()
        if not my_character:
            flash('캐릭터를 생성해주세요.', 'info')
            return redirect(url_for('character.create'))
            
        # 전투 상대 목록 가져오기
        characters = read_csv(CSV_FILES['characters'])
        opponents = [
            char for char in characters
            if char['id'] != my_character['id'] and char['user_id'] != str(session['user_id'])
        ]
        
        # 각 상대의 정보 보강
        for opp in opponents:
            opp['class_info'] = CHARACTER_CLASSES.get(opp.get('class', ''), {
                'name': '무직',
                'icon': 'fas fa-user'
            })
            # 승률 계산
            total_battles = int(opp.get('wins', 0)) + int(opp.get('losses', 0))
            opp['win_rate'] = round(int(opp.get('wins', 0)) / total_battles * 100, 1) if total_battles > 0 else 0
        
        # 진행 중인 전투가 있는지 확인
        in_battle = 'battle_opponent_id' in session and session['battle_opponent_id'] is not None
        
        # 정렬: 레벨 > 승률 > 이름
        opponents.sort(key=lambda x: (
            int(x.get('level', 1)),
            x['win_rate'],
            x.get('name', '')
        ), reverse=True)
        
        return render_template('character.html',
            character=my_character,
            opponents=opponents,
            in_battle=in_battle,
            class_info=CHARACTER_CLASSES.get(my_character.get('class', ''), {
                'name': '무직',
                'icon': 'fas fa-user'
            })
        )
        
    except Exception as e:
        app.logger.error(f'캐릭터 정보 로드 중 오류 발생: {str(e)}')
        flash('캐릭터 정보를 불러오는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('main.index'))

def create_character(user_id, char_class='warrior'):
    """새 캐릭터 생성"""
    class_info = CHARACTER_CLASSES.get(char_class, CHARACTER_CLASSES['warrior'])
    char_id = generate_id()
    character = {
        'id': char_id,
        'user_id': user_id,
        'name': g.user.get('nickname', '캐릭터'),
        'class': char_class,
        'level': '1',
        'exp': '0',
        'hp': str(100 + class_info['hp_bonus']),
        'mp': str(50 + class_info.get('mp_bonus', 0)),
        'strength': str(10 + class_info.get('str_bonus', 0)),
        'agility': str(10 + class_info.get('agi_bonus', 0)),
        'intelligence': str(10 + class_info.get('int_bonus', 0)),
        'skill_points': '3',
        'gold': '1000',
        'status_effects': '',
        'equipment': '',
        'inventory': '',
        'wins': '0',
        'losses': '0',
        'quests_completed': '0',
        'last_training': '',
        'pet_id': '',
        'guild_id': '',
        'title': '초보자',
        'achievement_points': '0',
        'avatar': '1',
        'color': '#3f51b5'
    }
    append_to_csv(CSV_FILES.get('characters'), character)
    return character

@character_bp.route('/train', methods=['POST'])
def train():
    """캐릭터 훈련"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
   
    characters = read_csv(CSV_FILES.get('characters'))
    character = None
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
   
    if not character:
        return jsonify({'success': False, 'message': '캐릭터가 없습니다.'})
   
    # 하루 한 번만 훈련 가능
    last_training = character.get('last_training', '')
    if last_training and last_training.split()[0] == datetime.now().strftime('%Y-%m-%d'):
        return jsonify({'success': False, 'message': '오늘은 이미 훈련했습니다.'})
   
    # 랜덤 스탯 증가
    stat = random.choice(['strength', 'agility', 'intelligence'])
    character[stat] = str(int(character[stat]) + 1)
    character['last_training'] = get_timestamp()
   
    # 경험치 획득
    exp_gain = random.randint(10, 30)
    character['exp'] = str(int(character['exp']) + exp_gain)
   
    # 레벨업 체크
    level = safe_int(character['level'])
    exp = safe_int(character['exp'])
    exp_required = level * 100
    if exp >= exp_required:
        character['level'] = str(level + 1)
        character['exp'] = '0'
        character['skill_points'] = str(int(character['skill_points']) + 3)
   
    update_csv(CSV_FILES.get('characters'), characters)
   
    return jsonify({
        'success': True,
        'message': f'훈련 완료! {stat}이(가) 1 증가했습니다.',
        'exp_gain': exp_gain,
        'level_up': exp >= exp_required
    })

@character_bp.route('/heal', methods=['POST'])
def heal():
    """체력 회복"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
   
    cost = 50  # 회복 비용
    characters = read_csv(CSV_FILES.get('characters'))
    character = None
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
   
    if not character:
        return jsonify({'success': False, 'message': '캐릭터가 없습니다.'})
   
    if int(character['gold']) < cost:
        return jsonify({'success': False, 'message': '골드가 부족합니다.'})
   
    # HP 완전 회복
    max_hp = 100 + safe_int(character.get('level', 1)) * 10
    character['hp'] = str(max_hp)
    character['gold'] = str(int(character['gold']) - cost)
   
    update_csv(CSV_FILES.get('characters'), characters)
   
    return jsonify({'success': True, 'message': 'HP가 완전히 회복되었습니다.'})


@character_bp.route('/stats')
def stats():
    """캐릭터 스탯 페이지"""
    if not g.user:
        return redirect(url_for('auth.login'))
    
    # 캐릭터 정보 가져오기
    characters = read_csv(CSV_FILES['characters'])
    character = None
    
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
    
    if not character:
        return redirect(url_for('character.index'))
    
    # 직업별 정보 추가
    class_info = {
        'warrior': {
            'name': '전사',
            'description': '높은 체력과 방어력을 가진 근접 전투 전문가',
            'icon': 'fas fa-shield-alt'
        },
        'mage': {
            'name': '마법사',
            'description': '강력한 마법을 사용하는 원거리 공격 전문가',
            'icon': 'fas fa-hat-wizard'
        },
        'archer': {
            'name': '궁수',
            'description': '빠른 공격 속도와 회피 능력을 가진 원거리 전투가',
            'icon': 'fas fa-bullseye'
        },
        'paladin': {
            'name': '성기사',
            'description': '신성한 힘을 사용하는 탱커 및 힐러',
            'icon': 'fas fa-cross'
        },
        'assassin': {
            'name': '암살자',
            'description': '치명타와 은신 능력을 가진 근접 딜러',
            'icon': 'fas fa-user-ninja'
        },
        'default': {
            'name': '초보자',
            'description': '기본 능력을 가진 초보 모험가',
            'icon': 'fas fa-user'
        }
    }
    
    # 캐릭터의 직업에 따른 정보 가져오기
    character_class = character.get('class', 'default')
    current_class_info = class_info.get(character_class, class_info['default'])
    
    return render_template('character_stats.html', 
                          character=character,
                          class_info=current_class_info)  # class_info 변수를 템플릿에 전달


@character_bp.route('/class_change', methods=['GET', 'POST'])
def class_change():
    """캐릭터 직업 변경"""
    if not g.user:
        return redirect(url_for('auth.login'))
    
    # 캐릭터 정보 가져오기
    characters = read_csv(CSV_FILES['characters'])
    character = None
    
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
    
    if not character:
        return redirect(url_for('character.index'))
    
    # 사용 가능한 직업 목록
    available_classes = [
        {
            'id': 'warrior',
            'name': '전사',
            'description': '높은 체력과 방어력을 가진 근접 전투 전문가',
            'strength_bonus': 5,
            'agility_bonus': 2,
            'intelligence_bonus': 1,
            'hp_bonus': 50,
            'mp_bonus': 10,
            'required_level': 5,
            'image': '/static/img/classes/warrior.png'
        },
        {
            'id': 'mage',
            'name': '마법사',
            'description': '강력한 마법을 사용하는 원거리 공격 전문가',
            'strength_bonus': 1,
            'agility_bonus': 2,
            'intelligence_bonus': 5,
            'hp_bonus': 20,
            'mp_bonus': 50,
            'required_level': 5,
            'image': '/static/img/classes/mage.png'
        },
        {
            'id': 'archer',
            'name': '궁수',
            'description': '빠른 공격 속도와 회피 능력을 가진 원거리 전투가',
            'strength_bonus': 2,
            'agility_bonus': 5,
            'intelligence_bonus': 2,
            'hp_bonus': 30,
            'mp_bonus': 20,
            'required_level': 5,
            'image': '/static/img/classes/archer.png'
        },
        {
            'id': 'paladin',
            'name': '성기사',
            'description': '신성한 힘을 사용하는 탱커 및 힐러',
            'strength_bonus': 4,
            'agility_bonus': 1,
            'intelligence_bonus': 3,
            'hp_bonus': 40,
            'mp_bonus': 30,
            'required_level': 10,
            'image': '/static/img/classes/paladin.png'
        },
        {
            'id': 'assassin',
            'name': '암살자',
            'description': '치명타와 은신 능력을 가진 근접 딜러',
            'strength_bonus': 3,
            'agility_bonus': 5,
            'intelligence_bonus': 2,
            'hp_bonus': 25,
            'mp_bonus': 15,
            'required_level': 10,
            'image': '/static/img/classes/assassin.png'
        }
    ]
    
    # 직업별 정보 추가 - 이 부분을 추가합니다
    class_info = {
        'warrior': {
            'name': '전사',
            'description': '높은 체력과 방어력을 가진 근접 전투 전문가',
            'skills': [
                {'id': 'slash', 'name': '베기', 'description': '적에게 물리 데미지를 입힙니다.', 'mp_cost': 5},
                {'id': 'bash', 'name': '강타', 'description': '적을 기절시키고 데미지를 입힙니다.', 'mp_cost': 10},
                {'id': 'taunt', 'name': '도발', 'description': '적의 공격을 자신에게 유도합니다.', 'mp_cost': 8}
            ]
        },
        'mage': {
            'name': '마법사',
            'description': '강력한 마법을 사용하는 원거리 공격 전문가',
            'skills': [
                {'id': 'fireball', 'name': '파이어볼', 'description': '적에게 화염 데미지를 입힙니다.', 'mp_cost': 15},
                {'id': 'ice_bolt', 'name': '얼음 화살', 'description': '적을 얼려 이동속도를 감소시킵니다.', 'mp_cost': 12},
                {'id': 'teleport', 'name': '텔레포트', 'description': '짧은 거리를 순간이동합니다.', 'mp_cost': 20}
            ]
        },
        'archer': {
            'name': '궁수',
            'description': '빠른 공격 속도와 회피 능력을 가진 원거리 전투가',
            'skills': [
                {'id': 'quick_shot', 'name': '빠른 사격', 'description': '적에게 빠르게 화살을 발사합니다.', 'mp_cost': 8},
                {'id': 'snipe', 'name': '저격', 'description': '적의 약점을 노려 치명타 확률이 증가합니다.', 'mp_cost': 15},
                {'id': 'trap', 'name': '함정', 'description': '적이 밟으면 데미지를 입히는 함정을 설치합니다.', 'mp_cost': 12}
            ]
        },
        'paladin': {
            'name': '성기사',
            'description': '신성한 힘을 사용하는 탱커 및 힐러',
            'skills': [
                {'id': 'holy_strike', 'name': '신성한 일격', 'description': '적에게 신성 데미지를 입힙니다.', 'mp_cost': 10},
                {'id': 'heal', 'name': '치유', 'description': '자신이나 아군의 체력을 회복시킵니다.', 'mp_cost': 20},
                {'id': 'divine_shield', 'name': '신의 방패', 'description': '잠시 동안 모든 데미지를 무효화합니다.', 'mp_cost': 30}
            ]
        },
        'assassin': {
            'name': '암살자',
            'description': '치명타와 은신 능력을 가진 근접 딜러',
            'skills': [
                {'id': 'backstab', 'name': '기습', 'description': '적의 뒤에서 공격하면 추가 데미지를 입힙니다.', 'mp_cost': 12},
                {'id': 'stealth', 'name': '은신', 'description': '잠시 동안 투명 상태가 됩니다.', 'mp_cost': 15},
                {'id': 'poison', 'name': '독', 'description': '적에게 지속적인 독 데미지를 입힙니다.', 'mp_cost': 18}
            ]
        },
        'default': {
            'name': '초보자',
            'description': '기본 능력을 가진 초보 모험가',
            'skills': [
                {'id': 'strike', 'name': '타격', 'description': '기본 공격을 가합니다.', 'mp_cost': 0}
            ]
        }
    }
    
    # 캐릭터의 직업에 따른 정보 가져오기
    character_class = character.get('class', 'default')
    current_class_info = class_info.get(character_class, class_info['default'])
    
    # 직업 변경 처리
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        
        # 선택한 직업 찾기
        selected_class = None
        for cls in available_classes:
            if cls['id'] == class_id:
                selected_class = cls
                break
        
        if not selected_class:
            flash('유효하지 않은 직업입니다.', 'error')
            return redirect(url_for('character.class_change'))
        
        # 레벨 요구사항 확인
        character_level = safe_int(character.get('level', '1'))
        required_level = safe_int(selected_class.get('required_level', 1))
        
        if character_level < required_level:
            flash(f'이 직업으로 전직하기 위해서는 레벨 {required_level}이 필요합니다.', 'error')
            return redirect(url_for('character.class_change'))
        
        # 직업 변경 비용
        class_change_cost = 5000
        
        # 잔액 확인
        user_balance = safe_int(g.user.get('balance', '0'))
        if user_balance < class_change_cost:
            flash(f'직업 변경에 필요한 {class_change_cost} {get_system_config().get("currency_name", "체스머니")}이 부족합니다.', 'error')
            return redirect(url_for('character.class_change'))
        
        # 비용 차감
        update_user_balance(g.user['id'], -class_change_cost)
        
        # 캐릭터 정보 업데이트
        for i, c in enumerate(characters):
            if c.get('id') == character['id']:
                c['class'] = selected_class['id']
                c['class_name'] = selected_class['name']
                
                # 스탯 보너스 적용
                c['strength'] = str(int(c.get('base_strength', 10)) + selected_class['strength_bonus'])
                c['agility'] = str(int(c.get('base_agility', 10)) + selected_class['agility_bonus'])
                c['intelligence'] = str(int(c.get('base_intelligence', 10)) + selected_class['intelligence_bonus'])
                
                # HP, MP 보너스 적용
                c['max_hp'] = str(int(c.get('base_hp', 100)) + selected_class['hp_bonus'])
                c['max_mp'] = str(int(c.get('base_mp', 50)) + selected_class['mp_bonus'])
                
                # 체력, 마나 회복
                c['hp'] = c['max_hp']
                c['mp'] = c['max_mp']
                
                characters[i] = c
                break
        
        update_csv(CSV_FILES['characters'], characters)
        
        # 거래 기록 추가
        add_transaction(g.user['id'], 'system', class_change_cost, 'class_change')
        
        # 알림 추가
        add_notification(g.user['id'], 'class_change', f'{selected_class["name"]} 직업으로 전직했습니다!')
        
        flash(f'{selected_class["name"]} 직업으로 성공적으로 전직했습니다!', 'success')
        return redirect(url_for('character.index'))
    
    return render_template('character_class_change.html',
                          character=character,
                          available_classes=available_classes,
                          user_balance=g.user.get('balance', '0'),
                          class_info=current_class_info)  # class_info 변수를 템플릿에 전달



@character_bp.route('/use_item', methods=['POST'])
def use_item():
    """아이템 사용"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
   
    item_id = request.form.get('item_id')
    if item_id not in ITEM_EFFECTS:
        return jsonify({'success': False, 'message': '잘못된 아이템입니다.'})
   
    characters = read_csv(CSV_FILES['characters'])
    character = None
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
   
    if not character:
        return jsonify({'success': False, 'message': '캐릭터가 없습니다.'})
   
    # 인벤토리에서 아이템 확인
    inventory = character.get('inventory', '').split(',')
    if '' in inventory:
        inventory.remove('')
   
    if item_id not in inventory:
        return jsonify({'success': False, 'message': '해당 아이템이 없습니다.'})
   
    # 아이템 효과 적용
    item = ITEM_EFFECTS[item_id]
    if 'heal' in item:
        character['hp'] = str(int(character['hp']) + item['heal'])
    if 'mp_heal' in item:
        character['mp'] = str(int(character['mp']) + item['mp_heal'])
   
    # 버프 효과 추가
    status_effects = character.get('status_effects', '').split(',')
    if '' in status_effects:
        status_effects.remove('')
   
    if 'duration' in item:
        status_effects.append(f"{item_id}:{get_timestamp()}")
        character['status_effects'] = ','.join(status_effects)
   
    # 인벤토리에서 아이템 제거
    inventory.remove(item_id)
    character['inventory'] = ','.join(inventory)
   
    update_csv(CSV_FILES.get('characters'), characters)
   
    return jsonify({'success': True, 'message': f'{item["name"]}을(를) 사용했습니다.'})

@character_bp.route('/level_up', methods=['POST'])
def level_up():
    """레벨업 처리"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
   
    stat = request.form.get('stat')
    if stat not in ['strength', 'agility', 'intelligence']:
        return jsonify({'success': False, 'message': '잘못된 스탯입니다.'})
   
    # 캐릭터 정보 업데이트
    characters = read_csv(CSV_FILES.get('characters'))
    updated = False
    updated_characters = []
   
    for character in characters:
        if character.get('user_id') == g.user['id']:
            if safe_int(character.get('skill_points', 0)) > 0:
                character['skill_points'] = str(int(character['skill_points']) - 1)
                character[stat] = str(int(character.get(stat, 0)) + 1)
                updated = True
        updated_characters.append(character)
   
    if not updated:
        return jsonify({'success': False, 'message': '스킬 포인트가 부족합니다.'})
   
    update_csv(CSV_FILES.get('characters'), updated_characters)
   
    return jsonify({'success': True, 'message': f'{stat} 스탯이 증가했습니다!'})

@character_bp.route('/customize', methods=['GET', 'POST'])
def customize():
    """캐릭터 커스터마이징"""
    if not g.user:
        return redirect(url_for('auth.login'))
   
    characters_file = CSV_FILES['characters']
    characters = read_csv(characters_file)
    character = None
   
    # 기존 캐릭터 찾기
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
   
    if not character:
        return redirect(url_for('character.index'))
    
    if 'id' not in character:
        from utils import generate_id
        character['id'] = generate_id()
   
    if request.method == 'POST':
        # 캐릭터 정보 업데이트
        character['name'] = request.form.get('name', character.get('name', g.user.get('nickname', '캐릭터')))
        character['avatar'] = request.form.get('avatar', character.get('avatar', '1'))
        character['color'] = request.form.get('color', character.get('color', '#3f51b5'))
        character['title'] = request.form.get('title', character.get('title', '초보자'))
           
        # 캐릭터 정보 저장
        for i, c in enumerate(characters):
            if c.get('id') == character['id']:
                characters[i] = character
                break

        from utils import update_csv
        # 업데이트할 캐릭터만 전달
        update_csv(characters_file, [character])

           
        # 포인트 지급 (캐릭터 커스터마이징 보상)
        add_points(g.user['id'], 5, "캐릭터 커스터마이징")
           
        flash('캐릭터 정보가 업데이트되었습니다!', 'success')
        return redirect(url_for('character.index'))
   
    # 사용 가능한 아바타 목록
    avatars = [f"{i}" for i in range(1, 21)]  # 20개의 아바타 옵션
   
    # 사용 가능한 칭호 목록
    titles = [
        '초보자', '모험가', '전사', '마법사', '궁수',
        '체스 마스터', '전략가', '부자', '상인', '정치인',
        '영웅', '전설', '황제', '제국의 수호자'
    ]
   
    return render_template('character_customize.html',
                          character=character,
                          avatars=avatars,
                          titles=titles)

@character_bp.route('/skills')
def skills():
    """캐릭터 스킬 관리"""
    if not g.user:
        return redirect(url_for('auth.login'))
    
    characters = read_csv(CSV_FILES['characters'])
    character = None
    
    # 캐릭터 정보 가져오기
    characters = read_csv(CSV_FILES['characters'])
    character = None
    
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
    
    if not character:
        return redirect(url_for('character.index'))
    
    # 스킬 목록
    all_skills = read_csv(CSV_FILES['character_skills'])
    user_skills = [s for s in all_skills if s.get('character_id') == character['id']]
    character_skills = read_csv(CSV_FILES['character_skills'])
    skills = [s for s in character_skills if s.get('character_id') == character.get('id')]
    
    # 사용 가능한 스킬 목록
    available_skills = [
        {
            'id': 'skill_1',
            'name': '송금 마스터',
            'description': '송금 수수료 10% 할인',
            'effect': 'transfer_fee_discount',
            'effect_value': '10',
            'required_level': '2',
            'cost': '1000',
            'icon': 'fas fa-money-bill-wave'
        },
        {
            'id': 'skill_2',
            'name': '게임 전략가',
            'description': '게임 승리 시 보상 15% 증가',
            'effect': 'game_reward_boost',
            'effect_value': '15',
            'required_level': '3',
            'cost': '2000',
            'icon': 'fas fa-gamepad'
        },
        {
            'id': 'skill_3',
            'name': '주식 투자자',
            'description': '주식 거래 시 수수료 면제',
            'effect': 'stock_fee_waiver',
            'effect_value': '100',
            'required_level': '4',
            'cost': '3000',
            'icon': 'fas fa-chart-line'
        },
        {
            'id': 'skill_4',
            'name': '경험치 부스터',
            'description': '모든 활동에서 얻는 포인트 20% 증가',
            'effect': 'point_boost',
            'effect_value': '20',
            'required_level': '5',
            'cost': '5000',
            'icon': 'fas fa-star'
        },
        {
            'id': 'skill_5',
            'name': '아이템 수집가',
            'description': '마켓 아이템 구매 시 10% 할인',
            'effect': 'market_discount',
            'effect_value': '10',
            'required_level': '3',
            'cost': '2500',
            'icon': 'fas fa-shopping-cart'
        }
    ]
    
    # 이미 습득한 스킬 제외
    user_skill_ids = [s.get('skill_id') for s in user_skills]
    available_skills = [s for s in available_skills if s['id'] not in user_skill_ids]
    
    # 캐릭터 레벨에 따라 사용 가능한 스킬 필터링
    character_level = int(character.get('level', '1'))
    available_skills = [s for s in available_skills if safe_int(s['required_level']) <= character_level]
    
    # 직업별 정보 추가 - 이 부분을 추가합니다
    class_info = {
        'warrior': {
            'name': '전사',
            'description': '높은 체력과 방어력을 가진 근접 전투 전문가',
            'skills': [
                {'id': 'slash', 'name': '베기', 'description': '적에게 물리 데미지를 입힙니다.', 'mp_cost': 5},
                {'id': 'bash', 'name': '강타', 'description': '적을 기절시키고 데미지를 입힙니다.', 'mp_cost': 10},
                {'id': 'taunt', 'name': '도발', 'description': '적의 공격을 자신에게 유도합니다.', 'mp_cost': 8}
            ]
        },
        'mage': {
            'name': '마법사',
            'description': '강력한 마법을 사용하는 원거리 공격 전문가',
            'skills': [
                {'id': 'fireball', 'name': '파이어볼', 'description': '적에게 화염 데미지를 입힙니다.', 'mp_cost': 15},
                {'id': 'ice_bolt', 'name': '얼음 화살', 'description': '적을 얼려 이동속도를 감소시킵니다.', 'mp_cost': 12},
                {'id': 'teleport', 'name': '텔레포트', 'description': '짧은 거리를 순간이동합니다.', 'mp_cost': 20}
            ]
        },
        'archer': {
            'name': '궁수',
            'description': '빠른 공격 속도와 회피 능력을 가진 원거리 전투가',
            'skills': [
                {'id': 'quick_shot', 'name': '빠른 사격', 'description': '적에게 빠르게 화살을 발사합니다.', 'mp_cost': 8},
                {'id': 'snipe', 'name': '저격', 'description': '적의 약점을 노려 치명타 확률이 증가합니다.', 'mp_cost': 15},
                {'id': 'trap', 'name': '함정', 'description': '적이 밟으면 데미지를 입히는 함정을 설치합니다.', 'mp_cost': 12}
            ]
        },
        'paladin': {
            'name': '성기사',
            'description': '신성한 힘을 사용하는 탱커 및 힐러',
            'skills': [
                {'id': 'holy_strike', 'name': '신성한 일격', 'description': '적에게 신성 데미지를 입힙니다.', 'mp_cost': 10},
                {'id': 'heal', 'name': '치유', 'description': '자신이나 아군의 체력을 회복시킵니다.', 'mp_cost': 20},
                {'id': 'divine_shield', 'name': '신의 방패', 'description': '잠시 동안 모든 데미지를 무효화합니다.', 'mp_cost': 30}
            ]
        },
        'assassin': {
            'name': '암살자',
            'description': '치명타와 은신 능력을 가진 근접 딜러',
            'skills': [
                {'id': 'backstab', 'name': '기습', 'description': '적의 뒤에서 공격하면 추가 데미지를 입힙니다.', 'mp_cost': 12},
                {'id': 'stealth', 'name': '은신', 'description': '잠시 동안 투명 상태가 됩니다.', 'mp_cost': 15},
                {'id': 'poison', 'name': '독', 'description': '적에게 지속적인 독 데미지를 입힙니다.', 'mp_cost': 18}
            ]
        },
        'default': {
            'name': '초보자',
            'description': '기본 능력을 가진 초보 모험가',
            'skills': [
                {'id': 'strike', 'name': '타격', 'description': '기본 공격을 가합니다.', 'mp_cost': 0}
            ]
        }
    }
    
    # 캐릭터의 직업에 따른 정보 가져오기
    character_class = character.get('class', 'default')
    current_class_info = class_info.get(character_class, class_info['default'])
    
    return render_template('character_skills.html',
                          character=character,
                          user_skills=user_skills,
                          available_skills=available_skills,
                          class_info=current_class_info)  # class_info 변수를 템플릿에 전달

@character_bp.route('/learn_skill', methods=['POST'])
def learn_skill():
    """스킬 습득"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
   
    skill_id = request.form.get('skill_id')
    if not skill_id:
        return jsonify({'success': False, 'message': '스킬 ID가 필요합니다.'})
   
    # 캐릭터 정보 가져오기
    characters = read_csv(CSV_FILES['characters'])
    character = None
   
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
   
    if not character:
        return jsonify({'success': False, 'message': '캐릭터를 찾을 수 없습니다.'})
   
    # 사용 가능한 스킬 목록
    available_skills = [
        {
            'id': 'skill_1',
            'name': '송금 마스터',
            'description': '송금 수수료 10% 할인',
            'effect': 'transfer_fee_discount',
            'effect_value': '10',
            'required_level': '2',
            'cost': '1000',
            'icon': 'fas fa-money-bill-wave'
        },
        {
            'id': 'skill_2',
            'name': '게임 전략가',
            'description': '게임 승리 시 보상 15% 증가',
            'effect': 'game_reward_boost',
            'effect_value': '15',
            'required_level': '3',
            'cost': '2000',
            'icon': 'fas fa-gamepad'
        },
        {
            'id': 'skill_3',
            'name': '주식 투자자',
            'description': '주식 거래 시 수수료 면제',
            'effect': 'stock_fee_waiver',
            'effect_value': '100',
            'required_level': '4',
            'cost': '3000',
            'icon': 'fas fa-chart-line'
        },
        {
            'id': 'skill_4',
            'name': '경험치 부스터',
            'description': '모든 활동에서 얻는 포인트 20% 증가',
            'effect': 'point_boost',
            'effect_value': '20',
            'required_level': '5',
            'cost': '5000',
            'icon': 'fas fa-star'
        },
        {
            'id': 'skill_5',
            'name': '아이템 수집가',
            'description': '마켓 아이템 구매 시 10% 할인',
            'effect': 'market_discount',
            'effect_value': '10',
            'required_level': '3',
            'cost': '2500',
            'icon': 'fas fa-shopping-cart'
        }
    ]
   
    # 선택한 스킬 찾기
    selected_skill = None
    for skill in available_skills:
        if skill['id'] == skill_id:
            selected_skill = skill
            break
   
    if not selected_skill:
        return jsonify({'success': False, 'message': '유효하지 않은 스킬입니다.'})
   
    # 레벨 요구사항 확인
    character_level =safe_int(character.get('level', '1'))
    required_level =safe_int(selected_skill['required_level'])
   
    if character_level < required_level:
        return jsonify({
            'success': False,
            'message': f'이 스킬을 배우기 위해서는 레벨 {required_level}이 필요합니다.'
        })
   
    # 비용 확인
    user_balance =safe_int(g.user.get('balance', '0'))
    skill_cost =safe_int(selected_skill['cost'])
   
    if user_balance < skill_cost:
        return jsonify({
            'success': False,
            'message': f'스킬 습득에 필요한 {skill_cost} {get_system_config().get("currency_name", "체스머니")}이 부족합니다.'
        })
   
    # 이미 습득한 스킬인지 확인
    character_skills = read_csv(CSV_FILES['character_skills'])
    for skill in character_skills:
        if skill.get('character_id') == character['id'] and skill.get('skill_id') == skill_id:
            return jsonify({'success': False, 'message': '이미 습득한 스킬입니다.'})
   
    # 비용 차감
    update_user_balance(g.user['id'], -skill_cost)
   
    # 스킬 추가
    new_skill = {
        'id': generate_id(),
        'character_id': character['id'],
        'skill_id': skill_id,
        'name': selected_skill['name'],
        'description': selected_skill['description'],
        'effect': selected_skill['effect'],
        'effect_value': selected_skill['effect_value'],
        'acquired_at': get_timestamp(),
        'level': '1',
        'icon': selected_skill['icon']
    }
   
    character_skills.append(new_skill)
    update_csv(CSV_FILES['character_skills'], character_skills)
   
    # 거래 기록 추가
    add_transaction(g.user['id'], 'system', skill_cost, 'skill_purchase')
   
    # 업적 체크 및 포인트 지급
    add_points(g.user['id'], 10, "스킬 습득")
   
    return jsonify({
        'success': True,
        'message': f'{selected_skill["name"]} 스킬을 습득했습니다!',
        'skill': new_skill
    })


def update_character_exp(user_id, exp_amount):
    """캐릭터 경험치 업데이트 및 레벨업 처리"""
    characters = read_csv(CSV_FILES['characters'])
    updated = False
    updated_characters = []
    
    for character in characters:
        if character.get('user_id') == user_id:
            # 현재 경험치 및 레벨
            current_exp =safe_int(character.get('exp', '0'))
            current_level =safe_int(character.get('level', '1'))
            
            # 경험치 추가
            new_exp = current_exp + exp_amount
            character['exp'] = str(new_exp)
            
            # 레벨업 체크
            level_up_exp = current_level * 1000  # 레벨당 필요 경험치
            
            if new_exp >= level_up_exp:
                # 레벨업
                character['level'] = str(current_level + 1)
                character['skill_points'] = str(int(character.get('skill_points', '0')) + 3)  # 레벨업 시 스킬 포인트 3개 지급
                
                # 레벨업 보상 (HP, MP 회복 및 증가)
                character['max_hp'] = str(int(character.get('max_hp', '100')) + 20)
                character['max_mp'] = str(int(character.get('max_mp', '50')) + 10)
                character['hp'] = character['max_hp']  # 체력 완전 회복
                character['mp'] = character['max_mp']  # 마나 완전 회복
                
                # 레벨업 알림 및 보상 지급
                add_notification(user_id, 'level_up', f'축하합니다! 레벨 {current_level + 1}로 올랐습니다.')
                add_points(user_id, 50, f"레벨 {current_level + 1} 달성")
                
                # 레벨업 이벤트 기록
                add_event(user_id, 'level_up', {'level': current_level + 1})
            
            updated = True
        
        updated_characters.append(character)
    
    if updated:
        update_csv(CSV_FILES['characters'], updated_characters)
    
    return updated


def simulate_battle(character, enemy):
    """전투 시뮬레이션"""
    battle_log = []
    
    # 캐릭터 스탯
    char_hp =safe_int(character.get('hp', '100'))
    char_attack =safe_int(character.get('strength', '10'))
    char_defense =safe_int(character.get('agility', '5'))
    
    # 적 스탯
    enemy_hp =safe_int(enemy['hp'])
    enemy_attack =safe_int(enemy['attack'])
    enemy_defense =safe_int(enemy['defense'])
    
    # 전투 시작
    battle_log.append(f"{character.get('name', '캐릭터')}와(과) {enemy['name']}의 전투가 시작되었습니다!")
    
    # 턴 기반 전투
    turn = 1
    while char_hp > 0 and enemy_hp > 0:
        battle_log.append(f"--- 턴 {turn} ---")
        
        # 캐릭터 공격
        damage_to_enemy = max(1, char_attack - enemy_defense // 2)
        enemy_hp -= damage_to_enemy
        battle_log.append(f"{character.get('name', '캐릭터')}가 {enemy['name']}에게 {damage_to_enemy}의 피해를 입혔습니다.")
        
        if enemy_hp <= 0:
            battle_log.append(f"{enemy['name']}을(를) 물리쳤습니다!")
            break
        
        # 적 공격
        damage_to_char = max(1, enemy_attack - char_defense // 2)
        char_hp -= damage_to_char
        battle_log.append(f"{enemy['name']}이(가) {character.get('name', '캐릭터')}에게 {damage_to_char}의 피해를 입혔습니다.")
        
        if char_hp <= 0:
            battle_log.append(f"{character.get('name', '캐릭터')}가 전투에서 패배했습니다.")
            break
        
        turn += 1
    
    # 전투 결과
    result = 'win' if enemy_hp <= 0 else 'lose'
    
    return {
        'result': result,
        'log': battle_log,
        'enemy': enemy,
        'remaining_hp': max(0, char_hp)
    }

def calculate_damage(attacker, defender):
    """공격 데미지 계산"""
    import random
    
    # 기본 공격력 = (힘 * 2.5 + 레벨 * 2)
    base_attack = safe_int(attacker.get('strength', 10)) * 2.5 + safe_int(attacker.get('level', 1)) * 2
    
    # 방어력 = (체력 * 0.3 + 레벨 * 0.5)
    defense = safe_int(defender.get('vitality', 10)) * 0.3 + safe_int(defender.get('level', 1)) * 0.5
    
    # 크리티컬 확률 (행운 + 민첩성 기반)
    crit_chance = (safe_int(attacker.get('luck', 10)) * 0.015) + (safe_int(attacker.get('dexterity', 10)) * 0.005)
    is_critical = random.random() < crit_chance
    
    # 데미지 계산 (방어력은 데미지를 25~75% 감소시킴)
    damage_reduction = min(0.75, max(0.25, defense / (base_attack + defense)))
    damage = base_attack * (1 - damage_reduction)
    
    # 약간의 랜덤성 추가 (±20%)
    damage *= random.uniform(0.8, 1.2)
    
    # 크리티컬 히트 (2.5배 데미지)
    if is_critical:
        damage *= 2.5
    
    return max(1, round(damage))  # 최소 1 데미지 보장

def process_battle(attacker, defender, safe_int_func=None):
    """배틀 로직 처리"""
    import random
    from datetime import datetime
    
    # safe_int 함수가 전달되지 않은 경우 기본 함수 정의
    if safe_int_func is None:
        def safe_int_func(value, default=0):
            try:
                if value is None or value == '':
                    return default
                return int(value)
            except (ValueError, TypeError):
                return default

    # 배틀 ID 생성
    battle_id = generate_id()

    # 현재 캐릭터의 HP 계산 (vitality * 15)
    if safe_int_func(attacker.get('hp', 0)) > 0:
        attacker_hp = safe_int_func(attacker.get('hp'))
    else:
        attacker_hp = safe_int_func(attacker.get('vitality', 10)) * 15

    if safe_int_func(defender.get('hp', 0)) > 0:
        defender_hp = safe_int_func(defender.get('hp'))
    else:
        defender_hp = safe_int_func(defender.get('vitality', 10)) * 15

    # 선공 결정 (민첩성이 높은 쪽이 선공)
    attacker_dex = safe_int_func(attacker.get('dexterity', 10))
    defender_dex = safe_int_func(defender.get('dexterity', 10))
    
    # 민첩성에 따른 선공 확률 계산 (민첩성이 높을수록 선공확률 증가)
    attacker_first_chance = (attacker_dex + 5) / (attacker_dex + defender_dex + 10)
    
    first_attacker = 'attacker' if random.random() < attacker_first_chance else 'defender'
    current_attacker = first_attacker
    
    # 배틀 라운드 기록
    rounds = []

    # 최대 10라운드까지 전투 진행
    for round_num in range(1, 11):
        # 한쪽이 죽었으면 전투 종료
        if attacker_hp <= 0 or defender_hp <= 0:
            break
            
        # 현재 공격자 결정
        if current_attacker == 'attacker':
            # 공격자의 공격
            damage = calculate_damage(attacker, defender)
            defender_hp -= damage
            
            rounds.append({
                'round': round_num,
                'attacker': 'attacker',
                'damage': damage,
                'attacker_hp': attacker_hp,
                'defender_hp': max(0, defender_hp)
            })
            
            current_attacker = 'defender'
        else:
            # 방어자의 공격
            damage = calculate_damage(defender, attacker)
            attacker_hp -= damage
            
            rounds.append({
                'round': round_num,
                'attacker': 'defender',
                'damage': damage,
                'attacker_hp': max(0, attacker_hp),
                'defender_hp': defender_hp
            })
            
            current_attacker = 'attacker'

    # 승자 결정
    if attacker_hp > defender_hp:
        winner = 'attacker'
    elif defender_hp > attacker_hp:
        winner = 'defender'
    else:
        winner = 'draw'  # 무승부
        
    # 배틀 결과 저장
    battle_result = {
        'id': battle_id,
        'attacker_id': attacker['id'],
        'defender_id': defender['id'],
        'winner': winner,
        'rounds': rounds,
        'timestamp': str(datetime.now())
    }
    
    # 캐릭터 HP 업데이트
    attacker['hp'] = str(max(0, attacker_hp))
    defender['hp'] = str(max(0, defender_hp))
    
    return battle_result

@character_bp.route('/rest', methods=['POST'])
def rest():
    """휴식 (HP, MP 회복)"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
    
    # 캐릭터 정보 가져오기
    characters = read_csv(CSV_FILES['characters'])
    character = None
    
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
    
    if not character:
        return jsonify({'success': False, 'message': '캐릭터를 찾을 수 없습니다.'})
    
    # 휴식 비용
    rest_cost = 100
    
    # 잔액 확인
    user_balance =safe_int(g.user.get('balance', '0'))
    if user_balance < rest_cost:
        return jsonify({
            'success': False,
            'message': f'휴식에 필요한 {rest_cost} {get_system_config().get("currency_name", "체스머니")}이 부족합니다.'
        })
    
    # 이미 최대 HP, MP인지 확인
    current_hp =safe_int(character.get('hp', '0'))
    current_mp =safe_int(character.get('mp', '0'))
    max_hp =safe_int(character.get('max_hp', '100'))
    max_mp =safe_int(character.get('max_mp', '50'))
    
    if current_hp >= max_hp and current_mp >= max_mp:
        return jsonify({
            'success': False,
            'message': '이미 체력과 마나가 최대입니다.'
        })
    
    # 비용 차감
    update_user_balance(g.user['id'], -rest_cost)
    
    # HP, MP 회복
    for i, c in enumerate(characters):
        if c.get('id') == character['id']:
            c['hp'] = str(max_hp)
            c['mp'] = str(max_mp)
            characters[i] = c
            break
    
    update_csv(CSV_FILES['characters'], characters)
    
    # 거래 기록 추가
    add_transaction(g.user['id'], 'system', rest_cost, 'rest')
    
    return jsonify({
        'success': True,
        'message': '휴식을 취했습니다. 체력과 마나가 모두 회복되었습니다!',
        'hp': max_hp,
        'mp': max_mp
    })

@character_bp.route('/shop')
def shop():
    """캐릭터 아이템 상점"""
    if not g.user:
        return redirect(url_for('auth.login'))
    
    # 캐릭터 정보 가져오기
    characters = read_csv(CSV_FILES['characters'])
    character = None
    
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
    
    if not character:
        return redirect(url_for('character.index'))
    
    # 상점 아이템 목록
    shop_items = [
        {
            'id': 'potion_small',
            'name': '소형 체력 물약',
            'description': 'HP를 30 회복합니다.',
            'effect': 'heal',
            'effect_value': '30',
            'price': '50',
            'image': '/static/img/items/potion_small.png',
            'category': '소모품'
        },
        {
            'id': 'potion_medium',
            'name': '중형 체력 물약',
            'description': 'HP를 70 회복합니다.',
            'effect': 'heal',
            'effect_value': '70',
            'price': '100',
            'image': '/static/img/items/potion_medium.png',
            'category': '소모품'
        },
        {
            'id': 'potion_large',
            'name': '대형 체력 물약',
            'description': 'HP를 150 회복합니다.',
            'effect': 'heal',
            'effect_value': '150',
            'price': '200',
            'image': '/static/img/items/potion_large.png',
            'category': '소모품'
        },
        {
            'id': 'mana_potion_small',
            'name': '소형 마나 물약',
            'description': 'MP를 20 회복합니다.',
            'effect': 'mp_heal',
            'effect_value': '20',
            'price': '60',
            'image': '/static/img/items/mana_small.png',
            'category': '소모품'
        },
        {
            'id': 'mana_potion_medium',
            'name': '중형 마나 물약',
            'description': 'MP를 50 회복합니다.',
            'effect': 'mp_heal',
            'effect_value': '50',
            'price': '120',
            'image': '/static/img/items/mana_medium.png',
            'category': '소모품'
        },
        {
            'id': 'strength_potion',
            'name': '힘의 물약',
            'description': '10분간 힘이 5 증가합니다.',
            'effect': 'strength_boost',
            'effect_value': '5',
            'duration': '600',
            'price': '300',
            'image': '/static/img/items/strength_potion.png',
            'category': '버프'
        },
        {
            'id': 'agility_potion',
            'name': '민첩의 물약',
            'description': '10분간 민첩이 5 증가합니다.',
            'effect': 'agility_boost',
            'effect_value': '5',
            'duration': '600',
            'price': '300',
            'image': '/static/img/items/agility_potion.png',
            'category': '버프'
        },
        {
            'id': 'intelligence_potion',
            'name': '지능의 물약',
            'description': '10분간 지능이 5 증가합니다.',
            'effect': 'intelligence_boost',
            'effect_value': '5',
            'duration': '600',
            'price': '300',
            'image': '/static/img/items/intelligence_potion.png',
            'category': '버프'
        },
        {
            'id': 'bronze_sword',
            'name': '청동 검',
            'description': '기본 공격력이 5 증가합니다.',
            'effect': 'weapon',
            'effect_value': '5',
            'slot': 'weapon',
            'price': '500',
            'image': '/static/img/items/bronze_sword.png',
            'category': '장비'
        },
        {
            'id': 'leather_armor',
            'name': '가죽 갑옷',
            'description': '방어력이 3 증가합니다.',
            'effect': 'armor',
            'effect_value': '3',
            'slot': 'armor',
            'price': '400',
            'image': '/static/img/items/leather_armor.png',
            'category': '장비'
        }
    ]
    
    # 캐릭터 레벨에 따라 아이템 필터링
    character_level =safe_int(character.get('level', '1'))
    
    # 레벨 3 이상일 때 추가 아이템
    if character_level >= 3:
        shop_items.extend([
            {
                'id': 'iron_sword',
                'name': '철 검',
                'description': '기본 공격력이 10 증가합니다.',
                'effect': 'weapon',
                'effect_value': '10',
                'slot': 'weapon',
                'price': '1000',
                'image': '/static/img/items/iron_sword.png',
                'category': '장비',
                'required_level': '3'
            },
            {
                'id': 'chain_mail',
                'name': '사슬 갑옷',
                'description': '방어력이 7 증가합니다.',
                'effect': 'armor',
                'effect_value': '7',
                'slot': 'armor',
                'price': '800',
                'image': '/static/img/items/chain_mail.png',
                'category': '장비',
                'required_level': '3'
            }
        ])
    
    # 레벨 5 이상일 때 추가 아이템
    if character_level >= 5:
        shop_items.extend([
            {
                'id': 'steel_sword',
                'name': '강철 검',
                'description': '기본 공격력이 15 증가합니다.',
                'effect': 'weapon',
                'effect_value': '15',
                'slot': 'weapon',
                'price': '2000',
                'image': '/static/img/items/steel_sword.png',
                'category': '장비',
                'required_level': '5'
            },
            {
                'id': 'plate_armor',
                'name': '판금 갑옷',
                'description': '방어력이 12 증가합니다.',
                'effect': 'armor',
                'effect_value': '12',
                'slot': 'armor',
                'price': '1500',
                'image': '/static/img/items/plate_armor.png',
                'category': '장비',
                'required_level': '5'
            },
            {
                'id': 'elixir',
                'name': '엘릭서',
                'description': 'HP와 MP를 모두 완전히 회복합니다.',
                'effect': 'full_heal',
                'price': '500',
                'image': '/static/img/items/elixir.png',
                'category': '소모품',
                'required_level': '5'
            }
        ])
    
    # 인벤토리 아이템 확인
    inventory = character.get('inventory', '').split(',')
    if '' in inventory:
        inventory.remove('')
    
    return render_template('character_shop.html',
                          character=character,
                          shop_items=shop_items,
                          inventory=inventory,
                          user_balance=g.user.get('balance', '0'))

@character_bp.route('/buy_item', methods=['POST'])
def buy_item():
    """아이템 구매"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
    
    item_id = request.form.get('item_id')
    if not item_id:
        return jsonify({'success': False, 'message': '아이템 ID가 필요합니다.'})
    
    # 캐릭터 정보 가져오기
    characters = read_csv(CSV_FILES['characters'])
    character = None
    
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
    
    if not character:
        return jsonify({'success': False, 'message': '캐릭터를 찾을 수 없습니다.'})
    
    # 상점 아이템 목록 (위의 shop 함수와 동일한 목록)
    shop_items = [
        {
            'id': 'potion_small',
            'name': '소형 체력 물약',
            'description': 'HP를 30 회복합니다.',
            'effect': 'heal',
            'effect_value': '30',
            'price': '50',
            'image': '/static/img/items/potion_small.png',
            'category': '소모품'
        },
        {
            'id': 'potion_medium',
            'name': '중형 체력 물약',
            'description': 'HP를 70 회복합니다.',
            'effect': 'heal',
            'effect_value': '70',
            'price': '100',
            'image': '/static/img/items/potion_medium.png',
            'category': '소모품'
        },
        {
            'id': 'potion_large',
            'name': '대형 체력 물약',
            'description': 'HP를 150 회복합니다.',
            'effect': 'heal',
            'effect_value': '150',
            'price': '200',
            'image': '/static/img/items/potion_large.png',
            'category': '소모품'
        },
        {
            'id': 'mana_potion_small',
            'name': '소형 마나 물약',
            'description': 'MP를 20 회복합니다.',
            'effect': 'mp_heal',
            'effect_value': '20',
            'price': '60',
            'image': '/static/img/items/mana_small.png',
            'category': '소모품'
        },
        {
            'id': 'mana_potion_medium',
            'name': '중형 마나 물약',
            'description': 'MP를 50 회복합니다.',
            'effect': 'mp_heal',
            'effect_value': '50',
            'price': '120',
            'image': '/static/img/items/mana_medium.png',
            'category': '소모품'
        },
        {
            'id': 'strength_potion',
            'name': '힘의 물약',
            'description': '10분간 힘이 5 증가합니다.',
            'effect': 'strength_boost',
            'effect_value': '5',
            'duration': '600',
            'price': '300',
            'image': '/static/img/items/strength_potion.png',
            'category': '버프'
        },
        {
            'id': 'agility_potion',
            'name': '민첩의 물약',
            'description': '10분간 민첩이 5 증가합니다.',
            'effect': 'agility_boost',
            'effect_value': '5',
            'duration': '600',
            'price': '300',
            'image': '/static/img/items/agility_potion.png',
            'category': '버프'
        },
        {
            'id': 'intelligence_potion',
            'name': '지능의 물약',
            'description': '10분간 지능이 5 증가합니다.',
            'effect': 'intelligence_boost',
            'effect_value': '5',
            'duration': '600',
            'price': '300',
            'image': '/static/img/items/intelligence_potion.png',
            'category': '버프'
        },
        {
            'id': 'bronze_sword',
            'name': '청동 검',
            'description': '기본 공격력이 5 증가합니다.',
            'effect': 'weapon',
            'effect_value': '5',
            'slot': 'weapon',
            'price': '500',
            'image': '/static/img/items/bronze_sword.png',
            'category': '장비'
        },
        {
            'id': 'leather_armor',
            'name': '가죽 갑옷',
            'description': '방어력이 3 증가합니다.',
            'effect': 'armor',
            'effect_value': '3',
            'slot': 'armor',
            'price': '400',
            'image': '/static/img/items/leather_armor.png',
            'category': '장비'
        },
        {
            'id': 'iron_sword',
            'name': '철 검',
            'description': '기본 공격력이 10 증가합니다.',
            'effect': 'weapon',
            'effect_value': '10',
            'slot': 'weapon',
            'price': '1000',
            'image': '/static/img/items/iron_sword.png',
            'category': '장비',
            'required_level': '3'
        },
        {
            'id': 'chain_mail',
            'name': '사슬 갑옷',
            'description': '방어력이 7 증가합니다.',
            'effect': 'armor',
            'effect_value': '7',
            'slot': 'armor',
            'price': '800',
            'image': '/static/img/items/chain_mail.png',
            'category': '장비',
            'required_level': '3'
        },
        {
            'id': 'steel_sword',
            'name': '강철 검',
            'description': '기본 공격력이 15 증가합니다.',
            'effect': 'weapon',
            'effect_value': '15',
            'slot': 'weapon',
            'price': '2000',
            'image': '/static/img/items/steel_sword.png',
            'category': '장비',
            'required_level': '5'
        },
        {
            'id': 'plate_armor',
            'name': '판금 갑옷',
            'description': '방어력이 12 증가합니다.',
            'effect': 'armor',
            'effect_value': '12',
            'slot': 'armor',
            'price': '1500',
            'image': '/static/img/items/plate_armor.png',
            'category': '장비',
            'required_level': '5'
        },
        {
            'id': 'elixir',
            'name': '엘릭서',
            'description': 'HP와 MP를 모두 완전히 회복합니다.',
            'effect': 'full_heal',
            'price': '500',
            'image': '/static/img/items/elixir.png',
            'category': '소모품',
            'required_level': '5'
        }
    ]
    
    # 선택한 아이템 찾기
    selected_item = None
    for item in shop_items:
        if item['id'] == item_id:
            selected_item = item
            break
    
    if not selected_item:
        return jsonify({'success': False, 'message': '유효하지 않은 아이템입니다.'})
    
    # 레벨 요구사항 확인
    character_level = safe_int(character.get('level', '1'))
    required_level = safe_int(selected_item.get('required_level', '1'))
    
    if character_level < required_level:
        return jsonify({
            'success': False,
            'message': f'이 아이템을 구매하기 위해서는 레벨 {required_level}이 필요합니다.'
        })
    
    # 가격 확인
    user_balance =safe_int(g.user.get('balance', '0'))
    item_price =safe_int(selected_item['price'])
    
    if user_balance < item_price:
        return jsonify({
            'success': False,
            'message': f'아이템 구매에 필요한 {item_price} {get_system_config().get("currency_name", "체스머니")}이 부족합니다.'
        })
    
    # 인벤토리 확인
    inventory = character.get('inventory', '').split(',')
    if '' in inventory:
        inventory.remove('')
    
    # 인벤토리 공간 확인 (최대 20개)
    if len(inventory) >= 20:
        return jsonify({
            'success': False,
            'message': '인벤토리가 가득 찼습니다. 아이템을 사용하거나 버려주세요.'
        })
    
    # 비용 차감
    update_user_balance(g.user['id'], -item_price)
    
    # 인벤토리에 아이템 추가
    inventory.append(item_id)
    
    # 캐릭터 정보 업데이트
    for i, c in enumerate(characters):
        if c.get('id') == character['id']:
            c['inventory'] = ','.join(inventory)
            characters[i] = c
            break
    
    update_csv(CSV_FILES['characters'], characters)
    
    # 거래 기록 추가
    add_transaction(g.user['id'], 'system', item_price, 'item_purchase')
    
    # 포인트 지급
    add_points(g.user['id'], 5, "아이템 구매")
    
    return jsonify({
        'success': True,
        'message': f'{selected_item["name"]}을(를) 구매했습니다!',
        'item': selected_item,
        'new_balance': str(user_balance - item_price)
    })

@character_bp.route('/equip_item', methods=['POST'])
def equip_item():
    """장비 아이템 착용"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
    
    item_id = request.form.get('item_id')
    if not item_id:
        return jsonify({'success': False, 'message': '아이템 ID가 필요합니다.'})
    
    # 캐릭터 정보 가져오기
    characters = read_csv(CSV_FILES['characters'])
    character = None
    
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
    
    if not character:
        return jsonify({'success': False, 'message': '캐릭터를 찾을 수 없습니다.'})
    
    # 인벤토리 확인
    inventory = character.get('inventory', '').split(',')
    if '' in inventory:
        inventory.remove('')
    
    if item_id not in inventory:
        return jsonify({'success': False, 'message': '해당 아이템이 인벤토리에 없습니다.'})
    
    # 아이템 정보 (위의 shop_items 목록에서 찾기)
    shop_items = [
        {
            'id': 'potion_small',
            'name': '소형 체력 물약',
            'description': 'HP를 30 회복합니다.',
            'effect': 'heal',
            'effect_value': '30',
            'price': '50',
            'image': '/static/img/items/potion_small.png',
            'category': '소모품'
        },
        {
            'id': 'potion_medium',
            'name': '중형 체력 물약',
            'description': 'HP를 70 회복합니다.',
            'effect': 'heal',
            'effect_value': '70',
            'price': '100',
            'image': '/static/img/items/potion_medium.png',
            'category': '소모품'
        },
        {
            'id': 'potion_large',
            'name': '대형 체력 물약',
            'description': 'HP를 150 회복합니다.',
            'effect': 'heal',
            'effect_value': '150',
            'price': '200',
            'image': '/static/img/items/potion_large.png',
            'category': '소모품'
        },
        {
            'id': 'mana_potion_small',
            'name': '소형 마나 물약',
            'description': 'MP를 20 회복합니다.',
            'effect': 'mp_heal',
            'effect_value': '20',
            'price': '60',
            'image': '/static/img/items/mana_small.png',
            'category': '소모품'
        },
        {
            'id': 'mana_potion_medium',
            'name': '중형 마나 물약',
            'description': 'MP를 50 회복합니다.',
            'effect': 'mp_heal',
            'effect_value': '50',
            'price': '120',
            'image': '/static/img/items/mana_medium.png',
            'category': '소모품'
        },
        {
            'id': 'strength_potion',
            'name': '힘의 물약',
            'description': '10분간 힘이 5 증가합니다.',
            'effect': 'strength_boost',
            'effect_value': '5',
            'duration': '600',
            'price': '300',
            'image': '/static/img/items/strength_potion.png',
            'category': '버프'
        },
        {
            'id': 'agility_potion',
            'name': '민첩의 물약',
            'description': '10분간 민첩이 5 증가합니다.',
            'effect': 'agility_boost',
            'effect_value': '5',
            'duration': '600',
            'price': '300',
            'image': '/static/img/items/agility_potion.png',
            'category': '버프'
        },
        {
            'id': 'intelligence_potion',
            'name': '지능의 물약',
            'description': '10분간 지능이 5 증가합니다.',
            'effect': 'intelligence_boost',
            'effect_value': '5',
            'duration': '600',
            'price': '300',
            'image': '/static/img/items/intelligence_potion.png',
            'category': '버프'
        },
        {
            'id': 'bronze_sword',
            'name': '청동 검',
            'description': '기본 공격력이 5 증가합니다.',
            'effect': 'weapon',
            'effect_value': '5',
            'slot': 'weapon',
            'price': '500',
            'image': '/static/img/items/bronze_sword.png',
            'category': '장비'
        },
        {
            'id': 'leather_armor',
            'name': '가죽 갑옷',
            'description': '방어력이 3 증가합니다.',
            'effect': 'armor',
            'effect_value': '3',
            'slot': 'armor',
            'price': '400',
            'image': '/static/img/items/leather_armor.png',
            'category': '장비'
        },
        {
            'id': 'iron_sword',
            'name': '철 검',
            'description': '기본 공격력이 10 증가합니다.',
            'effect': 'weapon',
            'effect_value': '10',
            'slot': 'weapon',
            'price': '1000',
            'image': '/static/img/items/iron_sword.png',
            'category': '장비',
            'required_level': '3'
        },
        {
            'id': 'chain_mail',
            'name': '사슬 갑옷',
            'description': '방어력이 7 증가합니다.',
            'effect': 'armor',
            'effect_value': '7',
            'slot': 'armor',
            'price': '800',
            'image': '/static/img/items/chain_mail.png',
            'category': '장비',
            'required_level': '3'
        },
        {
            'id': 'steel_sword',
            'name': '강철 검',
            'description': '기본 공격력이 15 증가합니다.',
            'effect': 'weapon',
            'effect_value': '15',
            'slot': 'weapon',
            'price': '2000',
            'image': '/static/img/items/steel_sword.png',
            'category': '장비',
            'required_level': '5'
        },
        {
            'id': 'plate_armor',
            'name': '판금 갑옷',
            'description': '방어력이 12 증가합니다.',
            'effect': 'armor',
            'effect_value': '12',
            'slot': 'armor',
            'price': '1500',
            'image': '/static/img/items/plate_armor.png',
            'category': '장비',
            'required_level': '5'
        },
        {
            'id': 'elixir',
            'name': '엘릭서',
            'description': 'HP와 MP를 모두 완전히 회복합니다.',
            'effect': 'full_heal',
            'price': '500',
            'image': '/static/img/items/elixir.png',
            'category': '소모품',
            'required_level': '5'
        }
    ]
    
    # 선택한 아이템 찾기
    selected_item = None
    for item in shop_items:
        if item['id'] == item_id:
            selected_item = item
            break
    
    if not selected_item:
        return jsonify({'success': False, 'message': '유효하지 않은 아이템입니다.'})
    
    # 장비 아이템인지 확인
    if selected_item.get('category') != '장비':
        return jsonify({'success': False, 'message': '이 아이템은 장비할 수 없습니다.'})
    
    # 장비 슬롯 확인
    slot = selected_item.get('slot')
    if not slot:
        return jsonify({'success': False, 'message': '이 아이템은 장비할 수 없습니다.'})
    
    # 현재 장착 중인 아이템 확인
    equipped_weapon = character.get('equipped_weapon', '')
    equipped_armor = character.get('equipped_armor', '')
    
    # 이미 장착 중인 아이템 해제
    if slot == 'weapon' and equipped_weapon:
        inventory.append(equipped_weapon)
    elif slot == 'armor' and equipped_armor:
        inventory.append(equipped_armor)
    
    # 인벤토리에서 아이템 제거
    inventory.remove(item_id)
    
    # 장비 장착
    for i, c in enumerate(characters):
        if c.get('id') == character['id']:
            c['inventory'] = ','.join(inventory)
            if slot == 'weapon':
                c['equipped_weapon'] = item_id
            elif slot == 'armor':
                c['equipped_armor'] = item_id
            characters[i] = c
            break
    
    update_csv(CSV_FILES['characters'], characters)
    
    return jsonify({
        'success': True,
        'message': f'{selected_item["name"]}을(를) 장착했습니다!',
        'item': selected_item
    })

@character_bp.route('/unequip_item', methods=['POST'])
def unequip_item():
    """장비 아이템 해제"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
    
    slot = request.form.get('slot')
    if slot not in ['weapon', 'armor']:
        return jsonify({'success': False, 'message': '유효하지 않은 슬롯입니다.'})
    
    # 캐릭터 정보 가져오기
    characters = read_csv(CSV_FILES['characters'])
    character = None
    
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
    
    if not character:
        return jsonify({'success': False, 'message': '캐릭터를 찾을 수 없습니다.'})
    
    # 장착 중인 아이템 확인
    equipped_item = character.get(f'equipped_{slot}', '')
    if not equipped_item:
        return jsonify({'success': False, 'message': f'장착 중인 {slot} 아이템이 없습니다.'})
    
    # 인벤토리 확인
    inventory = character.get('inventory', '').split(',')
    if '' in inventory:
        inventory.remove('')
    
    # 인벤토리 공간 확인
    if len(inventory) >= 20:
        return jsonify({
            'success': False,
            'message': '인벤토리가 가득 찼습니다. 아이템을 사용하거나 버려주세요.'
        })
    
    # 장비 해제 및 인벤토리에 추가
    inventory.append(equipped_item)
    
    # 캐릭터 정보 업데이트
    for i, c in enumerate(characters):
        if c.get('id') == character['id']:
            c['inventory'] = ','.join(inventory)
            c[f'equipped_{slot}'] = ''
            characters[i] = c
            break
    
    update_csv(CSV_FILES['characters'], characters)
    
    return jsonify({
        'success': True,
        'message': f'{slot} 아이템을 해제했습니다!'
    })

@character_bp.route('/discard_item', methods=['POST'])
def discard_item():
    """아이템 버리기"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
    
    item_id = request.form.get('item_id')
    if not item_id:
        return jsonify({'success': False, 'message': '아이템 ID가 필요합니다.'})
    
    # 캐릭터 정보 가져오기
    characters = read_csv(CSV_FILES['characters'])
    character = None
    
    for c in characters:
        if c.get('user_id') == g.user['id']:
            character = c
            break
    
    if not character:
        return jsonify({'success': False, 'message': '캐릭터를 찾을 수 없습니다.'})
    
    # 인벤토리 확인
    inventory = character.get('inventory', '').split(',')
    if '' in inventory:
        inventory.remove('')
    
    if item_id not in inventory:
        return jsonify({'success': False, 'message': '해당 아이템이 인벤토리에 없습니다.'})
    
    # 인벤토리에서 아이템 제거
    inventory.remove(item_id)
    
    # 캐릭터 정보 업데이트
    for i, c in enumerate(characters):
        if c.get('id') == character['id']:
            c['inventory'] = ','.join(inventory)
            characters[i] = c
            break
    
    update_csv(CSV_FILES['characters'], characters)
    
    return jsonify({
        'success': True,
        'message': '아이템을 버렸습니다.'
    })

@character_bp.route('/battle/start/<int:opponent_id>')
def battle_start(opponent_id):
    """전투 시작"""
    my_character = get_my_character()
    if not my_character:
        flash('캐릭터가 없습니다.', 'error')
        return redirect(url_for('character.battle'))
        
    opponent = get_character_by_id(opponent_id)
    if not opponent:
        flash('상대 캐릭터를 찾을 수 없습니다.', 'error')
        return redirect(url_for('character.battle'))
        
    # 자신과의 전투 방지
    if str(my_character['id']) == str(opponent_id):
        flash('자신과 전투할 수 없습니다.', 'error')
        return redirect(url_for('character.battle'))
        
    # HP/MP 초기화
    my_character['current_hp'] = int(my_character.get('power', 1)) * 10
    my_character['max_hp'] = my_character['current_hp']
    my_character['current_mp'] = 100
    my_character['max_mp'] = 100
    my_character['defense'] = float(my_character.get('vitality', 0)) * 0.5
    
    opponent['current_hp'] = int(opponent.get('power', 1)) * 10
    opponent['max_hp'] = opponent['current_hp']
    opponent['current_mp'] = 100
    opponent['max_mp'] = 100
    opponent['defense'] = float(opponent.get('vitality', 0)) * 0.5
    
    # 전투 시작 로그 기록
    battle_id = start_new_battle(my_character['id'], opponent_id)
    
    # 세션에 상대 ID와 전투 ID 저장
    session['battle_opponent_id'] = opponent_id
    session['battle_id'] = battle_id
    session['battle_round'] = 0
    # 전투 기록 초기화
    session['battle_rounds'] = []
    
    flash('전투가 시작됐습니다!', 'success')
    return redirect(url_for('character.battle'))

@character_bp.route('/battle/attack', methods=['POST'])
def character_attack():
    """전투 공격 실행"""
    if 'battle_opponent_id' not in session or 'battle_id' not in session:
        flash('전투가 시작되지 않았습니다.', 'error')
        return redirect(url_for('character.battle'))
        
    my_character = get_my_character()
    if not my_character:
        flash('캐릭터가 없습니다.', 'error')
        return redirect(url_for('character.battle'))
        
    # 상대 캐릭터 정보 가져오기
    opponent_id = session.get('battle_opponent_id')
    opponent = get_character_by_id(opponent_id)
    if not opponent:
        flash('상대 캐릭터를 찾을 수 없습니다.', 'error')
        return redirect(url_for('character.battle'))
    
    # 현재 라운드 증가
    current_round = session.get('battle_round', 0) + 1
    session['battle_round'] = current_round
    
    # 스킬 사용
    skill_id = request.form.get('skill_id')
    if skill_id:
        skill = get_skill_by_id(skill_id)
        if not skill:
            flash('존재하지 않는 스킬입니다.', 'error')
            return redirect(url_for('character.battle'))
        result = use_skill(my_character, skill, opponent)
    else:
        # 기본 공격
        basic_attack = {
            'name': '기본 공격',
            'type': 'physical',
            'damage_multiplier': 1.0,
            'mp_cost': 0
        }
        result = use_skill(my_character, basic_attack, opponent)
    
    if not result['success']:
        flash(result['message'], 'error')
        return redirect(url_for('character.battle'))
        
    # 전투 기록 추가
    battle_rounds = session.get('battle_rounds', [])
    battle_rounds.append({
        'attacker_action': result['message'],
        'defender_action': '',
        'is_critical': result.get('is_critical', False),
        'is_dodged': result.get('is_dodged', False)
    })
    session['battle_rounds'] = battle_rounds
    
    # 전투 라운드 로그 추가
    battle_id = session.get('battle_id')
    
    # 내 공격 로그
    log_battle_round(
        battle_id,
        current_round,
        my_character['id'],
        opponent_id,
        {
            'attacker': 'attacker',
            'damage': result.get('damage', 0),
            'attacker_hp': my_character['current_hp'],
            'defender_hp': opponent['current_hp']
        }
    )
    
    # 상대가 죽었는지 체크
    if opponent['current_hp'] <= 0:
        flash(f"{opponent['name']}을(를) 쓰러뜨렸습니다!", 'success')
        give_battle_rewards(my_character['id'])
        # 세션 초기화
        session.pop('battle_opponent_id', None)
        session.pop('battle_id', None)
        session.pop('battle_round', None)
        session.pop('battle_rounds', None)
        return redirect(url_for('character.battle'))
    
    # 상대의 반격
    opponent_skill = choose_random_skill(opponent)
    counter_result = use_skill(opponent, opponent_skill, my_character)
    battle_rounds[-1]['defender_action'] = counter_result['message']
    
    # 상대의 반격 로그
    log_battle_round(
        battle_id,
        current_round,
        opponent_id,
        my_character['id'],
        {
            'attacker': 'defender',
            'damage': counter_result.get('damage', 0),
            'attacker_hp': opponent['current_hp'],
            'defender_hp': my_character['current_hp']
        }
    )
    
    # 내가 죽었는지 체크
    if my_character['current_hp'] <= 0:
        flash(f"{opponent['name']}에게 패배했습니다...", 'error')
        # 패배 횟수 증가
        characters = read_csv(CSV_FILES['characters'])
        for char in characters:
            if char['id'] == str(my_character['id']):
                char['losses'] = str(int(char.get('losses', 0)) + 1)
                break
        update_csv(CSV_FILES['characters'], characters)
        # 세션 초기화
        session.pop('battle_opponent_id', None)
        session.pop('battle_id', None)
        session.pop('battle_round', None)
        session.pop('battle_rounds', None)
        return redirect(url_for('character.battle'))
    
    return redirect(url_for('character.battle'))

@character_bp.route('/battle')
def battle():
    """전투 화면"""
    my_character = get_my_character()
    if not my_character:
        flash('캐릭터가 없습니다.', 'error')
        return redirect(url_for('character.create'))
    
    # 현재 전투 중인지 확인
    opponent_id = session.get('battle_opponent_id')
    opponent = None
    my_skills = None
    
    if opponent_id:
        opponent = get_character_by_id(opponent_id)
        # HP/MP가 없으면 초기화
        if 'current_hp' not in opponent:
            opponent['current_hp'] = int(opponent.get('power', 1)) * 10
            opponent['max_hp'] = opponent['current_hp']
        if 'current_mp' not in opponent:
            opponent['current_mp'] = 100
            opponent['max_mp'] = 100
        # 방어력 계산
        opponent['defense'] = float(opponent.get('vitality', 0)) * 0.5
        
        # 내 스킬 목록 가져오기
        my_skills = get_character_skills(my_character['id'])
    
    # 전투 상대 목록 (전투 중이 아닐 때만)
    available_opponents = []
    if not opponent_id:
        characters = read_csv(CSV_FILES['characters'])
        for char in characters:
            # 자신을 제외한 모든 캐릭터
            if char['user_id'] != str(session.get('user_id')):
                available_opponents.append(char)
    
    return render_template(
        'character_battle.html',
        my_character=my_character,
        opponent=opponent,
        my_skills=my_skills,
        opponents=available_opponents,
        battle_rounds=session.get('battle_rounds', [])
    )

def add_notification(user_id, notification_type, message):
    """사용자에게 알림 추가"""
    notices = read_csv(CSV_FILES['notices'])
    
    new_notice = {
        'id': str(len(notices) + 1),
        'user_id': str(user_id),
        'type': notification_type,
        'message': message,
        'created_at': get_timestamp(),
        'is_read': '0'
    }
    
    notices.append(new_notice)
    update_csv(CSV_FILES['notices'], notices)

def add_event(user_id, event_type, event_data):
    """이벤트 기록 추가"""
    events = read_csv(CSV_FILES['event_attendance'])
    
    new_event = {
        'id': str(len(events) + 1),
        'user_id': str(user_id),
        'type': event_type,
        'data': json.dumps(event_data),
        'created_at': get_timestamp()
    }
    
    events.append(new_event)
    update_csv(CSV_FILES['event_attendance'], events)

def log_battle_round(battle_id, round_num, attacker_id, defender_id, result):
    """전투 라운드 로그 저장"""
    round_logs = read_csv(CSV_FILES['battle_round_logs'])
    battle_logs = read_csv(CSV_FILES['battle_logs'])
    
    # 새 라운드 로그 추가
    new_round_log = {
        'battle_id': battle_id,
        'round': str(round_num),
        'attacker': result['attacker'],
        'damage': str(result['damage']),
        'attacker_hp': str(result['attacker_hp']),
        'defender_hp': str(result['defender_hp']),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    }
    round_logs.append(new_round_log)
    update_csv(CSV_FILES['battle_round_logs'], round_logs)
    
    # 전투가 끝났는지 확인
    if result['defender_hp'] <= 0 or result['attacker_hp'] <= 0:
        winner = attacker_id if result['defender_hp'] <= 0 else defender_id
        
        # 전투 로그 업데이트
        for log in battle_logs:
            if log['id'] == battle_id:
                log['winner'] = 'attacker' if winner == attacker_id else 'defender'
                log['rounds'] = json.dumps([
                    {
                        'round': int(l['round']),
                        'attacker': l['attacker'],
                        'damage': int(l['damage']),
                        'attacker_hp': int(l['attacker_hp']),
                        'defender_hp': int(l['defender_hp'])
                    }
                    for l in round_logs
                    if l['battle_id'] == battle_id
                ])
                break
        update_csv(CSV_FILES['battle_logs'], battle_logs)

def start_new_battle(attacker_id, defender_id):
    """새로운 전투 시작"""
    battle_logs = read_csv(CSV_FILES['battle_logs'])
    
    battle_id = str(uuid.uuid4())  # 고유 ID 생성
    new_battle = {
        'id': battle_id,
        'attacker_id': str(attacker_id),
        'defender_id': str(defender_id),
        'winner': None,
        'rounds': '[]',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    }
    
    battle_logs.append(new_battle)
    update_csv(CSV_FILES['battle_logs'], battle_logs)
    
    return battle_id

@character_bp.route('/history')
def history():
    """캐릭터의 전투 히스토리 조회"""
    if 'user_id' not in session:
        flash('로그인이 필요합니다.', 'error')
        return redirect(url_for('auth.login'))
    
    my_character = get_my_character()
    if not my_character:
        flash('캐릭터가 없습니다.', 'error')
        return redirect(url_for('character.create'))
    
    # 전투 기록 가져오기
    battle_logs = get_battle_logs_by_user_id(session['user_id'])
    
    # 승패 통계 계산
    wins = sum(1 for log in battle_logs if 
        (log['winner'] == 'attacker' and log['attacker_id'] == str(my_character['id'])) or
        (log['winner'] == 'defender' and log['defender_id'] == str(my_character['id'])))
    
    losses = sum(1 for log in battle_logs if 
        (log['winner'] == 'defender' and log['attacker_id'] == str(my_character['id'])) or
        (log['winner'] == 'attacker' and log['defender_id'] == str(my_character['id'])))
    
    draws = sum(1 for log in battle_logs if log['winner'] == 'draw')
    
    # 최근 전투 로그 가져오기 (최대 10개)
    recent_battles = battle_logs[-10:] if battle_logs else []
    
    # 전투 로그에 상대방 정보 추가
    for battle in recent_battles:
        opponent_id = battle['defender_id'] if battle['attacker_id'] == str(my_character['id']) else battle['attacker_id']
        opponent = get_character_by_id(opponent_id)
        battle['opponent'] = opponent['name'] if opponent else '알 수 없음'
        battle['i_was_attacker'] = battle['attacker_id'] == str(my_character['id'])
    
    return render_template('character_history.html',
        character=my_character,
        battle_logs=recent_battles,
        stats={
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'total': len(battle_logs),
            'win_rate': round(wins / len(battle_logs) * 100, 1) if battle_logs else 0
        }
    )

@character_bp.route('/create', methods=['GET', 'POST'])
def create():
    """새 캐릭터 생성"""
    if 'user_id' not in session:
        flash('로그인이 필요합니다.', 'error')
        return redirect(url_for('auth.login'))
        
    # 이미 캐릭터가 있는지 확인
    characters = read_csv(CSV_FILES['characters'])
    for char in characters:
        if char['user_id'] == str(session['user_id']):
            flash('이미 캐릭터가 있습니다.', 'error')
            return redirect(url_for('character.profile'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        char_class = request.form.get('class')
        
        # 입력 검증
        if not name:
            flash('캐릭터 이름을 입력해주세요.', 'error')
            return redirect(url_for('character.create'))
            
        if char_class not in CHARACTER_CLASSES:
            flash('올바른 직업을 선택해주세요.', 'error')
            return redirect(url_for('character.create'))
            
        # 이름 중복 확인
        if any(char['name'].lower() == name.lower() for char in characters):
            flash('이미 사용 중인 이름입니다.', 'error')
            return redirect(url_for('character.create'))
        
        # 직업 보너스 스탯
        class_info = CHARACTER_CLASSES[char_class]
        
        # 새 캐릭터 생성
        new_character = {
            'id': str(len(characters) + 1),
            'user_id': str(session['user_id']),
            'name': name,
            'class': char_class,
            'level': '1',
            'xp': '0',
            'power': str(10 + class_info['str_bonus']),  # 기본 힘 + 직업 보너스
            'vitality': str(10 + class_info['hp_bonus'] // 2),  # 기본 체력 + 직업 보너스
            'agility': str(10 + class_info['agi_bonus']),  # 기본 민첩 + 직업 보너스
            'intelligence': str(10 + class_info['int_bonus']),  # 기본 지능 + 직업 보너스
            'wins': '0',
            'losses': '0',
            'created_at': get_timestamp()
        }
        
        characters.append(new_character)
        update_csv(CSV_FILES['characters'], characters)
        
        flash('캐릭터가 생성되었습니다!', 'success')
        return redirect(url_for('character.profile'))
        
    return render_template('character_create.html',
        classes=CHARACTER_CLASSES
    )

@character_bp.route('/profile')
def profile():
    """캐릭터 프로필 조회"""
    if 'user_id' not in session:
        flash('로그인이 필요합니다.', 'error')
        return redirect(url_for('auth.login'))
    
    my_character = get_my_character()
    if not my_character:
        flash('캐릭터가 없습니다.', 'error')
        return redirect(url_for('character.create'))
    
    # 직업 정보 가져오기
    class_info = CHARACTER_CLASSES.get(my_character.get('class', ''), {
        'name': '무직',
        'icon': 'fas fa-user',
        'description': '직업이 없습니다.'
    })
    
    # 스킬 목록 가져오기
    skills = get_character_skills(my_character['id'])
    
    # 전투 통계
    battle_logs = get_battle_logs_by_user_id(session['user_id'])
    wins = sum(1 for log in battle_logs if 
        (log['winner'] == 'attacker' and log['attacker_id'] == str(my_character['id'])) or
        (log['winner'] == 'defender' and log['defender_id'] == str(my_character['id'])))
    
    losses = sum(1 for log in battle_logs if 
        (log['winner'] == 'defender' and log['attacker_id'] == str(my_character['id'])) or
        (log['winner'] == 'attacker' and log['defender_id'] == str(my_character['id'])))
    
    # 레벨업 필요 경험치
    current_level = int(my_character.get('level', 1))
    current_xp = int(my_character.get('xp', 0))
    xp_needed = current_level * 100
    xp_percentage = min(round(current_xp / xp_needed * 100, 1), 100)
    
    return render_template('character_profile.html',
        character=my_character,
        class_info=class_info,
        skills=skills,
        stats={
            'wins': wins,
            'losses': losses,
            'total': len(battle_logs),
            'win_rate': round(wins / len(battle_logs) * 100, 1) if battle_logs else 0
        },
        level_info={
            'current_level': current_level,
            'current_xp': current_xp,
            'xp_needed': xp_needed,
            'xp_percentage': xp_percentage
        }
    )

def get_my_character():
    """현재 로그인한 사용자의 캐릭터 정보 가져오기"""
    if 'user_id' not in session:
        return None
        
    characters = read_csv(CSV_FILES['characters'])
    for char in characters:
        if char['user_id'] == str(session['user_id']):
            # HP와 MP 계산
            char['max_hp'] = int(char.get('power', 1)) * 10
            char['max_mp'] = 100
            if 'current_hp' not in char:
                char['current_hp'] = char['max_hp']
            if 'current_mp' not in char:
                char['current_mp'] = char['max_mp']
            return char
    return None

def get_character_by_id(character_id):
    """ID로 캐릭터 정보 가져오기"""
    characters = read_csv(CSV_FILES['characters'])
    for char in characters:
        if char['id'] == str(character_id):
            # HP와 MP 계산
            char['max_hp'] = int(char.get('power', 1)) * 10
            char['max_mp'] = 100
            if 'current_hp' not in char:
                char['current_hp'] = char['max_hp']
            if 'current_mp' not in char:
                char['current_mp'] = char['max_mp']
            return char
    return None

def get_character_skills(character_id):
    """캐릭터의 스킬 목록 가져오기"""
    skills = read_csv(CSV_FILES['character_skills'])
    character = get_character_by_id(character_id)
    
    if not character:
        return []
        
    # 캐릭터 직업에 맞는 스킬만 필터링
    character_class = character.get('class', '').lower()
    return [
        {
            'id': skill['id'],
            'name': skill['name'],
            'level': int(skill.get('skill_level', 1)),
            'type': skill.get('skill_type', 'physical'),
            'description': skill.get('skill_description', ''),
            'mp_cost': int(skill.get('mp_cost', 0)),
            'damage_multiplier': float(skill.get('damage_multiplier', 1.0))
        }
        for skill in skills
        if skill.get('character_id') == str(character_id) or skill.get('class', '').lower() == character_class
    ]

def get_battle_logs_by_user_id(user_id):
    """사용자의 전투 기록 가져오기"""
    character = get_character_by_user_id(user_id)
    if not character:
        return []
        
    battle_logs = read_csv(CSV_FILES['battle_logs'])
    character_id = str(character['id'])
    
    # 해당 캐릭터가 참여한 전투만 필터링
    return [
        log for log in battle_logs
        if log['attacker_id'] == character_id or log['defender_id'] == character_id
    ]

def get_skill_by_id(skill_id):
    """ID로 스킬 정보 가져오기"""
    skills = read_csv(CSV_FILES['character_skills'])
    for skill in skills:
        if skill['id'] == str(skill_id):
            return {
                'id': skill['id'],
                'name': skill['name'],
                'level': int(skill.get('skill_level', 1)),
                'type': skill.get('skill_type', 'physical'),
                'description': skill.get('skill_description', ''),
                'mp_cost': int(skill.get('mp_cost', 0)),
                'damage_multiplier': float(skill.get('damage_multiplier', 1.0))
            }
    return None

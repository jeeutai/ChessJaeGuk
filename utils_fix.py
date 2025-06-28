import csv
import os
import time
import random
import string
import logging
from datetime import datetime
from flask import g
import qrcode
import io
import base64

# 시스템 설정 조회
def get_system_config():
    from app import CSV_FILES
    system_config = {}
    
    try:
        with open(CSV_FILES['system_config'], 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                system_config[row['key']] = row['value']
    except Exception as e:
        logging.error(f"시스템 설정을 로드하는 중 오류가 발생했습니다: {e}")
    
    return system_config

# 고유 ID 생성
def generate_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

# 타임스탬프 생성
def get_timestamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# 사용자 조회
def get_user_by_id(user_id):
    from app import CSV_FILES
    
    if not user_id:
        return None
    
    try:
        with open(CSV_FILES['users'], 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for user in reader:
                if user['id'] == user_id:
                    return user
    except Exception as e:
        logging.error(f"사용자 정보를 조회하는 중 오류가 발생했습니다: {e}")
    
    return None

# CSV 파일에 새 행 추가 (개선된 버전)
def append_to_csv(csv_file, row_dict):
    file_exists = os.path.isfile(csv_file)
    
    if file_exists:
        # 파일이 존재하면 헤더 읽기
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames
    else:
        # 파일이 없으면 딕셔너리 키를 헤더로 사용
        fieldnames = list(row_dict.keys())
    
    # 새 행에 필드가 누락된 경우 빈 값 추가
    for field in fieldnames:
        if field not in row_dict:
            row_dict[field] = ''
    
    # CSV 파일에 정의되지 않은 필드 제거 (필드 초과 방지)
    row_dict_copy = row_dict.copy()
    for field in row_dict_copy:
        if fieldnames and field not in fieldnames:
            del row_dict[field]
    
    with open(csv_file, 'a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_dict)

# 사용자 포인트 조회
def get_user_points(user_id):
    from app import CSV_FILES
    
    point_logs = []
    try:
        with open(CSV_FILES['point_logs'], 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['user_id'] == user_id:
                    point_logs.append(row)
    except Exception as e:
        logging.error(f"포인트 로그를 조회하는 중 오류가 발생했습니다: {e}")
        return 0
    
    total_points = 0
    for log in point_logs:
        points = int(log.get('points', 0))
        total_points += points
    
    return total_points

# 사용자 레벨 정보 조회 (개선된 버전)
def get_user_level(user_id):
    from app import CSV_FILES
    
    # 사용자 레벨 데이터 조회
    user_level_data = None
    user_levels = []
    
    try:
        with open(CSV_FILES['user_levels'], 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            user_levels = list(reader)
    except Exception as e:
        logging.error(f"사용자 레벨 정보를 조회하는 중 오류가 발생했습니다: {e}")
    
    for level_data in user_levels:
        if level_data.get('user_id') == user_id:
            user_level_data = level_data
            break
    
    # 레벨 정보가 없으면 기본값 생성
    if not user_level_data:
        # 파일이 존재하는지 확인하고 헤더 가져오기
        file_exists = os.path.isfile(CSV_FILES['user_levels'])
        if file_exists:
            with open(CSV_FILES['user_levels'], 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                fieldnames = reader.fieldnames or ['id', 'user_id', 'level', 'current_points', 'total_points', 'last_updated']
        else:
            fieldnames = ['id', 'user_id', 'level', 'current_points', 'total_points', 'last_updated']
        
        # 기본 레벨 데이터 생성
        user_level_data = {
            'id': generate_id(),
            'user_id': user_id,
            'level': '1',
            'current_points': '0',
            'total_points': '0',
            'last_updated': get_timestamp()
        }
        
        try:
            with open(CSV_FILES['user_levels'], 'a', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                
                # 누락된 필드 빈 값으로 채우기
                row_to_write = {field: '' for field in fieldnames}
                for key, value in user_level_data.items():
                    if key in fieldnames:
                        row_to_write[key] = value
                
                writer.writerow(row_to_write)
        except Exception as e:
            logging.error(f"사용자 레벨 정보를 저장하는 중 오류가 발생했습니다: {e}")
    
    # 레벨 시스템 정보 가져오기
    levels_info = []
    try:
        with open(CSV_FILES['levels'], 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            levels_info = list(reader)
            levels_info.sort(key=lambda x: int(x.get('required_points', 0)))
    except Exception as e:
        logging.error(f"레벨 시스템 정보를 로드하는 중 오류가 발생했습니다: {e}")
        # 기본 레벨 정보 제공
        levels_info = [
            {'level': '1', 'title': '초보자', 'required_points': '0', 'description': '시작 단계'},
            {'level': '2', 'title': '견습생', 'required_points': '1000', 'description': '기본 기능을 익힌 사용자'}
        ]
    
    # 현재 레벨 정보
    current_level_info = None
    for level_info in levels_info:
        if level_info.get('level') == user_level_data.get('level'):
            current_level_info = level_info
            break
    
    if not current_level_info and levels_info:
        current_level_info = levels_info[0]
    
    # 다음 레벨 정보
    next_level_info = None
    current_level = int(user_level_data.get('level', 1))
    
    for level_info in levels_info:
        if int(level_info.get('level', 0)) > current_level:
            next_level_info = level_info
            break
    
    # 현재 포인트
    current_points = int(user_level_data.get('current_points', 0))
    total_points = int(user_level_data.get('total_points', 0))
    
    # 포인트 정보가 없는 경우 point_logs에서 계산
    if current_points == 0 and total_points == 0:
        total_points = get_user_points(user_id)
        
        # 현재 레벨의 필요 포인트
        current_level_required_points = int(current_level_info.get('required_points', 0)) if current_level_info else 0
        
        # 다음 레벨의 필요 포인트
        next_level_required_points = int(next_level_info.get('required_points', 0)) if next_level_info else float('inf')
        
        # 현재 레벨에서의 포인트 계산
        current_points = total_points - current_level_required_points
    
    result = {
        'current': {
            'level': user_level_data.get('level', '1'),
            'name': current_level_info.get('title', '초보자') if current_level_info else '초보자',
            'description': current_level_info.get('description', '') if current_level_info else '',
            'icon_url': current_level_info.get('icon_url', '') if current_level_info else ''
        },
        'next': {
            'level': next_level_info.get('level', '') if next_level_info else None,
            'name': next_level_info.get('title', '') if next_level_info else None,
            'required_points': next_level_info.get('required_points', '') if next_level_info else None,
            'remaining': int(next_level_info.get('required_points', 0)) - total_points if next_level_info else None,
            'icon_url': next_level_info.get('icon_url', '') if next_level_info else None
        },
        'points': {
            'current': current_points,
            'total': total_points
        }
    }
    
    return result
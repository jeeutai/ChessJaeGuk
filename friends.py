from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, jsonify
import os
import csv
from app import CSV_FILES
from utils import read_csv, update_csv, append_to_csv, generate_id, get_timestamp, get_system_config

friends_bp = Blueprint('friends', __name__, url_prefix='/friends')

@friends_bp.route('/')
def index():
    """친구 목록 및 관리 페이지"""
    if not g.user:
        flash('로그인이 필요합니다.', 'warning')
        return redirect(url_for('auth.login'))
    
    # 시스템 설정 가져오기
    system_config = get_system_config()
    
    # 친구 목록 CSV 파일 확인 및 생성
    friends_file = CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv'))
    if not os.path.exists(friends_file):
        with open(friends_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'user_id', 'friend_id', 'status', 'created_at', 'is_favorite'])
    
    # 친구 활동 CSV 파일 확인 및 생성
    friend_activities_file = CSV_FILES.get('friend_activities', os.path.join(os.path.dirname(__file__), 'data', 'friend_activities.csv'))
    if not os.path.exists(friend_activities_file):
        with open(friend_activities_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'user_id', 'friend_id', 'activity_type', 'activity_data', 'timestamp'])
    
    # 친구 목록 가져오기
    friends_data = read_csv(friends_file)
    users_data = read_csv(CSV_FILES['users'])
    
    # 사용자의 친구 목록
    friends = []
    friend_requests = []
    sent_requests = []
    
    # 친구 ID => 사용자 정보 매핑
    user_map = {user['id']: user for user in users_data}
    
    for friendship in friends_data:
        if friendship['user_id'] == g.user['id'] and friendship['status'] == 'accepted':
            # 내가 추가한 친구 (내 ID가 user_id)
            friend_id = friendship['friend_id']
            if friend_id in user_map:
                friend_info = user_map[friend_id].copy()
                friend_info.update({
                    'is_favorite': friendship['is_favorite'] == 'True',
                    'status_message': '온라인' if friend_id in session.get('online_users', []) else '오프라인',
                    'is_online': friend_id in session.get('online_users', []),
                    'mutual_friends': calculate_mutual_friends(g.user['id'], friend_id, friends_data),
                    'friendship_id': friendship['id']
                })
                friends.append(friend_info)
        
        elif friendship['friend_id'] == g.user['id'] and friendship['status'] == 'accepted':
            # 나를 추가한.친구 (내 ID가 friend_id)
            friend_id = friendship['user_id']
            if friend_id in user_map:
                friend_info = user_map[friend_id].copy()
                # 역방향 친구관계에서는 favorite 상태를 확인
                is_favorite = False
                for f in friends_data:
                    if f['user_id'] == g.user['id'] and f['friend_id'] == friend_id and f['status'] == 'accepted':
                        is_favorite = f['is_favorite'] == 'True'
                        break
                
                friend_info.update({
                    'is_favorite': is_favorite,
                    'status_message': '온라인' if friend_id in session.get('online_users', []) else '오프라인',
                    'is_online': friend_id in session.get('online_users', []),
                    'mutual_friends': calculate_mutual_friends(g.user['id'], friend_id, friends_data),
                    'friendship_id': friendship['id']
                })
                # 중복 방지 확인
                if not any(f['id'] == friend_id for f in friends):
                    friends.append(friend_info)
        
        elif friendship['friend_id'] == g.user['id'] and friendship['status'] == 'pending':
            # 받은 친구 요청
            sender_id = friendship['user_id']
            if sender_id in user_map:
                request_info = user_map[sender_id].copy()
                request_info.update({
                    'sent_time': format_time_ago(friendship['created_at']),
                    'request_id': friendship['id']
                })
                friend_requests.append(request_info)
        
        elif friendship['user_id'] == g.user['id'] and friendship['status'] == 'pending':
            # 보낸 친구 요청
            receiver_id = friendship['friend_id']
            if receiver_id in user_map:
                request_info = user_map[receiver_id].copy()
                request_info.update({
                    'sent_time': format_time_ago(friendship['created_at']),
                    'request_id': friendship['id']
                })
                sent_requests.append(request_info)
    
    # 친구 활동 내역
    activities = get_friend_activities(g.user['id'], user_map)
    
    # 친구 추천
    friend_recommendations = get_friend_recommendations(g.user['id'], friends, friends_data, users_data)
    
    return render_template('friends.html', 
                          friends=friends, 
                          friend_requests=friend_requests,
                          sent_requests=sent_requests,
                          activities=activities,
                          friend_recommendations=friend_recommendations,
                          system_config=system_config)

@friends_bp.route('/search', methods=['POST'])
def search():
    """친구 검색"""
    if not g.user:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})
    
    search_term = request.form.get('search_term', '')
    if len(search_term) < 2:
        return jsonify({"success": False, "message": "검색어는 최소 2글자 이상 입력해주세요."})
    
    # 사용자 데이터 가져오기
    users_data = read_csv(CSV_FILES['users'])
    friends_data = read_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')))
    
    search_results = []
    for user in users_data:
        # 자기 자신은 검색 결과에서 제외
        if user['id'] == g.user['id']:
            continue
        
        # ID나 닉네임에 검색어가 포함되는지 확인
        if search_term.lower() in user['id'].lower() or search_term.lower() in user['nickname'].lower():
            # 친구 관계 상태 확인
            status = get_friendship_status(g.user['id'], user['id'], friends_data)
            
            search_results.append({
                'id': user['id'],
                'nickname': user['nickname'],
                'status': status
            })
    
    return jsonify({
        "success": True, 
        "results": search_results
    })

@friends_bp.route('/add', methods=['POST'])
def add_friend():
    """친구 요청 보내기"""
    if not g.user:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})
    
    friend_id = request.form.get('friend_id')
    
    # 자기 자신에게 친구 요청을 보내는 경우
    if friend_id == g.user['id']:
        return jsonify({"success": False, "message": "자기 자신에게 친구 요청을 보낼 수 없습니다."})
    
    # 사용자 존재 여부 확인
    users_data = read_csv(CSV_FILES['users'])
    user_exists = any(user['id'] == friend_id for user in users_data)
    
    if not user_exists:
        return jsonify({"success": False, "message": "존재하지 않는 사용자입니다."})
    
    # 이미 친구인지 또는 요청을 보냈는지 확인
    friends_data = read_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')))
    status = get_friendship_status(g.user['id'], friend_id, friends_data)
    
    if status == 'friend':
        return jsonify({"success": False, "message": "이미 친구인 사용자입니다."})
    elif status == 'sent':
        return jsonify({"success": False, "message": "이미 친구 요청을 보낸 사용자입니다."})
    elif status == 'received':
        return jsonify({"success": False, "message": "이 사용자에게서 친구 요청을 받았습니다. 수락해주세요."})
    
    # 친구 요청 추가
    friendship = {
        'id': generate_id(),
        'user_id': g.user['id'],
        'friend_id': friend_id,
        'status': 'pending',
        'created_at': get_timestamp(),
        'is_favorite': 'False'
    }
    
    append_to_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')), friendship)
    
    # 활동 기록 추가
    add_friend_activity(g.user['id'], friend_id, 'request_sent', {})
    
    return jsonify({
        "success": True, 
        "message": "친구 요청을 보냈습니다."
    })

@friends_bp.route('/accept', methods=['POST'])
def accept_request():
    """친구 요청 수락"""
    if not g.user:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})
    
    request_id = request.form.get('request_id')
    
    # 요청 찾기
    friends_data = read_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')))
    updated_friends = []
    request_found = False
    sender_id = None
    
    for friendship in friends_data:
        if friendship['id'] == request_id and friendship['friend_id'] == g.user['id'] and friendship['status'] == 'pending':
            friendship['status'] = 'accepted'
            request_found = True
            sender_id = friendship['user_id']
        
        updated_friends.append(friendship)
    
    if not request_found:
        return jsonify({"success": False, "message": "요청을 찾을 수 없거나 이미 처리되었습니다."})
    
    # 양방향 친구 관계 추가 (상대방 -> 나 관계는 이미 exists, 나 -> 상대방 관계를 추가)
    new_friendship = {
        'id': generate_id(),
        'user_id': g.user['id'],
        'friend_id': sender_id,
        'status': 'accepted',
        'created_at': get_timestamp(),
        'is_favorite': 'False'
    }
    
    updated_friends.append(new_friendship)
    
    # 친구 관계 업데이트
    update_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')), updated_friends)
    
    # 활동 기록 추가
    add_friend_activity(g.user['id'], sender_id, 'request_accepted', {})
    
    return jsonify({
        "success": True, 
        "message": "친구 요청을 수락했습니다."
    })

@friends_bp.route('/reject', methods=['POST'])
def reject_request():
    """친구 요청 거절"""
    if not g.user:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})
    
    request_id = request.form.get('request_id')
    
    # 요청 찾기
    friends_data = read_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')))
    updated_friends = []
    request_found = False
    sender_id = None
    
    for friendship in friends_data:
        if friendship['id'] == request_id and friendship['friend_id'] == g.user['id'] and friendship['status'] == 'pending':
            # 이 요청은 제외 (삭제)
            request_found = True
            sender_id = friendship['user_id']
            continue
        
        updated_friends.append(friendship)
    
    if not request_found:
        return jsonify({"success": False, "message": "요청을 찾을 수 없거나 이미 처리되었습니다."})
    
    # 친구 관계 업데이트 (요청 삭제)
    update_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')), updated_friends)
    
    # 활동 기록 추가
    add_friend_activity(g.user['id'], sender_id, 'request_rejected', {})
    
    return jsonify({
        "success": True, 
        "message": "친구 요청을 거절했습니다."
    })

@friends_bp.route('/cancel', methods=['POST'])
def cancel_request():
    """친구 요청 취소"""
    if not g.user:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})
    
    request_id = request.form.get('request_id')
    
    # 요청 찾기
    friends_data = read_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')))
    updated_friends = []
    request_found = False
    receiver_id = None
    
    for friendship in friends_data:
        if friendship['id'] == request_id and friendship['user_id'] == g.user['id'] and friendship['status'] == 'pending':
            # 이 요청은 제외 (삭제)
            request_found = True
            receiver_id = friendship['friend_id']
            continue
        
        updated_friends.append(friendship)
    
    if not request_found:
        return jsonify({"success": False, "message": "요청을 찾을 수 없거나 이미 처리되었습니다."})
    
    # 친구 관계 업데이트 (요청 삭제)
    update_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')), updated_friends)
    
    # 활동 기록 추가
    add_friend_activity(g.user['id'], receiver_id, 'request_canceled', {})
    
    return jsonify({
        "success": True, 
        "message": "친구 요청을 취소했습니다."
    })

@friends_bp.route('/remove', methods=['POST'])
def remove_friend():
    """친구 삭제"""
    if not g.user:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})
    
    friend_id = request.form.get('friend_id')
    
    # 친구 관계 찾기
    friends_data = read_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')))
    updated_friends = []
    removed = False
    
    for friendship in friends_data:
        # 양방향 친구 관계 모두 삭제
        if ((friendship['user_id'] == g.user['id'] and friendship['friend_id'] == friend_id) or
            (friendship['user_id'] == friend_id and friendship['friend_id'] == g.user['id'])) and friendship['status'] == 'accepted':
            removed = True
            continue
        
        updated_friends.append(friendship)
    
    if not removed:
        return jsonify({"success": False, "message": "친구 관계를 찾을 수 없습니다."})
    
    # 친구 관계 업데이트 (삭제)
    update_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')), updated_friends)
    
    # 활동 기록 추가
    add_friend_activity(g.user['id'], friend_id, 'friend_removed', {})
    
    return jsonify({
        "success": True, 
        "message": "친구를 삭제했습니다."
    })

@friends_bp.route('/favorite', methods=['POST'])
def toggle_favorite():
    """친구 즐겨찾기 토글"""
    if not g.user:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})
    
    friend_id = request.form.get('friend_id')
    
    # 친구 관계 찾기
    friends_data = read_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')))
    updated_friends = []
    friendship_found = False
    new_status = False
    
    for friendship in friends_data:
        if friendship['user_id'] == g.user['id'] and friendship['friend_id'] == friend_id and friendship['status'] == 'accepted':
            # 즐겨찾기 상태 토글
            friendship_found = True
            new_status = not (friendship['is_favorite'] == 'True')
            friendship['is_favorite'] = str(new_status)
        
        updated_friends.append(friendship)
    
    # 관계가 없으면 새로 생성 (단방향)
    if not friendship_found:
        for friendship in friends_data:
            if friendship['user_id'] == friend_id and friendship['friend_id'] == g.user['id'] and friendship['status'] == 'accepted':
                new_friendship = {
                    'id': generate_id(),
                    'user_id': g.user['id'],
                    'friend_id': friend_id,
                    'status': 'accepted',
                    'created_at': get_timestamp(),
                    'is_favorite': 'True'
                }
                updated_friends.append(new_friendship)
                friendship_found = True
                new_status = True
                break
    
    if not friendship_found:
        return jsonify({"success": False, "message": "친구 관계를 찾을 수 없습니다."})
    
    # 친구 관계 업데이트
    update_csv(CSV_FILES.get('friends', os.path.join(os.path.dirname(__file__), 'data', 'friends.csv')), updated_friends)
    
    # 활동 기록 추가
    if new_status:
        add_friend_activity(g.user['id'], friend_id, 'friend_favorited', {})
    else:
        add_friend_activity(g.user['id'], friend_id, 'friend_unfavorited', {})
    
    return jsonify({
        "success": True, 
        "message": f"친구가 {'즐겨찾기에 추가' if new_status else '즐겨찾기에서 제거'}되었습니다."
    })

# 헬퍼 함수들

def get_friendship_status(user_id, friend_id, friends_data):
    """두 사용자 간의 친구 관계 상태 확인"""
    # 이미 친구인지 확인
    for friendship in friends_data:
        if ((friendship['user_id'] == user_id and friendship['friend_id'] == friend_id) or
            (friendship['user_id'] == friend_id and friendship['friend_id'] == user_id)) and friendship['status'] == 'accepted':
            return 'friend'
    
    # 친구 요청을 보냈는지 확인
    for friendship in friends_data:
        if friendship['user_id'] == user_id and friendship['friend_id'] == friend_id and friendship['status'] == 'pending':
            return 'sent'
    
    # 친구 요청을 받았는지 확인
    for friendship in friends_data:
        if friendship['user_id'] == friend_id and friendship['friend_id'] == user_id and friendship['status'] == 'pending':
            return 'received'
    
    return 'none'

def calculate_mutual_friends(user_id, friend_id, friends_data):
    """두 사용자 간의 공통 친구 수 계산"""
    user_friends = set()
    friend_friends = set()
    
    # 사용자의 친구 목록
    for friendship in friends_data:
        if friendship['user_id'] == user_id and friendship['status'] == 'accepted':
            user_friends.add(friendship['friend_id'])
        elif friendship['friend_id'] == user_id and friendship['status'] == 'accepted':
            user_friends.add(friendship['user_id'])
    
    # 친구의 친구 목록
    for friendship in friends_data:
        if friendship['user_id'] == friend_id and friendship['status'] == 'accepted':
            friend_friends.add(friendship['friend_id'])
        elif friendship['friend_id'] == friend_id and friendship['status'] == 'accepted':
            friend_friends.add(friendship['user_id'])
    
    # 공통 친구 수
    mutual = user_friends.intersection(friend_friends)
    
    # 서로를 제외
    if user_id in mutual:
        mutual.remove(user_id)
    if friend_id in mutual:
        mutual.remove(friend_id)
    
    return len(mutual)

def format_time_ago(timestamp):
    """타임스탬프를 '~전' 형식으로 변환"""
    import datetime
    
    try:
        dt = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        now = datetime.datetime.now()
        diff = now - dt
        
        if diff.days > 30:
            return f"{diff.days // 30}개월 전"
        elif diff.days > 0:
            return f"{diff.days}일 전"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600}시간 전"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60}분 전"
        else:
            return "방금 전"
    except:
        return timestamp

def get_friend_activities(user_id, user_map):
    """사용자의 친구 활동 내역 가져오기"""
    activities_file = CSV_FILES.get('friend_activities', os.path.join(os.path.dirname(__file__), 'data', 'friend_activities.csv'))
    
    if not os.path.exists(activities_file):
        return []
    
    activities_data = read_csv(activities_file)
    activities = []
    
    for activity in activities_data:
        if activity['user_id'] == user_id or activity['friend_id'] == user_id:
            # 활동 정보 구성
            activity_info = {
                'id': activity['id'],
                'timestamp': format_time_ago(activity['timestamp']),
                'type': activity['activity_type']
            }
            
            # 활동 유형에 따른 메시지 구성
            actor_id = activity['user_id']
            target_id = activity['friend_id']
            actor_name = user_map.get(actor_id, {}).get('nickname', actor_id)
            target_name = user_map.get(target_id, {}).get('nickname', target_id)
            
            if activity['activity_type'] == 'request_sent':
                if actor_id == user_id:
                    activity_info['message'] = f"<strong>회원님</strong>이 <strong>{target_name}</strong>님에게 친구 요청을 보냈습니다."
                else:
                    activity_info['message'] = f"<strong>{actor_name}</strong>님이 회원님에게 친구 요청을 보냈습니다."
            elif activity['activity_type'] == 'request_accepted':
                if actor_id == user_id:
                    activity_info['message'] = f"<strong>회원님</strong>이 <strong>{target_name}</strong>님의 친구 요청을 수락했습니다."
                else:
                    activity_info['message'] = f"<strong>{actor_name}</strong>님이 회원님의 친구 요청을 수락했습니다."
            elif activity['activity_type'] == 'request_rejected':
                if actor_id == user_id:
                    activity_info['message'] = f"<strong>회원님</strong>이 <strong>{target_name}</strong>님의 친구 요청을 거절했습니다."
                # 자신의 요청이 거절된 경우는 표시하지 않음
            elif activity['activity_type'] == 'request_canceled':
                if actor_id == user_id:
                    activity_info['message'] = f"<strong>회원님</strong>이 <strong>{target_name}</strong>님에게 보낸 친구 요청을 취소했습니다."
                # 자신에게 보낸 요청이 취소된 경우는 표시하지 않음
            elif activity['activity_type'] == 'friend_removed':
                if actor_id == user_id:
                    activity_info['message'] = f"<strong>회원님</strong>이 <strong>{target_name}</strong>님을 친구 목록에서 삭제했습니다."
                else:
                    activity_info['message'] = f"<strong>{actor_name}</strong>님이 회원님을 친구 목록에서 삭제했습니다."
            elif activity['activity_type'] == 'friend_favorited':
                if actor_id == user_id:
                    activity_info['message'] = f"<strong>회원님</strong>이 <strong>{target_name}</strong>님을 즐겨찾기에 추가했습니다."
                # 다른 사람이 나를 즐겨찾기에 추가한 것은 표시하지 않음
            elif activity['activity_type'] == 'friend_unfavorited':
                if actor_id == user_id:
                    activity_info['message'] = f"<strong>회원님</strong>이 <strong>{target_name}</strong>님을 즐겨찾기에서 제거했습니다."
                # 다른 사람이 나를 즐겨찾기에서 제거한 것은 표시하지 않음
            
            if 'message' in activity_info:
                activities.append(activity_info)
    
    # 최신순 정렬
    activities.sort(key=lambda x: x['id'], reverse=True)
    
    # 최대 20개만 반환
    return activities[:20]

def add_friend_activity(user_id, friend_id, activity_type, activity_data={}):
    """친구 활동 기록 추가"""
    activities_file = CSV_FILES.get('friend_activities', os.path.join(os.path.dirname(__file__), 'data', 'friend_activities.csv'))
    
    # 파일이 없으면 생성
    if not os.path.exists(activities_file):
        with open(activities_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'user_id', 'friend_id', 'activity_type', 'activity_data', 'timestamp'])
    
    # 활동 정보 추가
    activity = {
        'id': generate_id(),
        'user_id': user_id,
        'friend_id': friend_id,
        'activity_type': activity_type,
        'activity_data': str(activity_data),
        'timestamp': get_timestamp()
    }
    
    append_to_csv(activities_file, activity)

def challenge_friend(user_id, friend_id, game_id, bet_amount):
    """친구에게 게임 대결 신청"""
    challenge = {
        'id': generate_id(),
        'challenger_id': user_id,
        'friend_id': friend_id,
        'game_id': game_id,
        'bet_amount': bet_amount,
        'status': 'pending',
        'created_at': get_timestamp()
    }
    append_to_csv(CSV_FILES.get('friend_challenges'), challenge)
    add_friend_activity(user_id, friend_id, 'game_challenge', {'game_id': game_id})
    return True

def send_gift(user_id, friend_id, item_id):
    """친구에게 아이템 선물"""
    gift = {
        'id': generate_id(),
        'sender_id': user_id,
        'receiver_id': friend_id,
        'item_id': item_id,
        'status': 'pending',
        'created_at': get_timestamp()
    }
    append_to_csv(CSV_FILES.get('friend_gifts'), gift)
    add_friend_activity(user_id, friend_id, 'gift_sent', {'item_id': item_id})
    return True

def get_friend_recommendations(user_id, friends, friends_data, users_data):
    """친구 추천 목록 가져오기"""
    recommendations = []
    
    # 친구의 친구를 추천
    friend_ids = [friend['id'] for friend in friends]
    
    # 친구의 친구 목록
    friends_of_friends = set()
    for friendship in friends_data:
        if friendship['status'] != 'accepted':
            continue
        
        if friendship['user_id'] in friend_ids and friendship['friend_id'] != user_id:
            friends_of_friends.add(friendship['friend_id'])
        elif friendship['friend_id'] in friend_ids and friendship['user_id'] != user_id:
            friends_of_friends.add(friendship['user_id'])
    
    # 이미 친구인 사용자와 친구 요청을 주고받은 사용자는 제외
    exclude_ids = set(friend_ids)
    for friendship in friends_data:
        if friendship['user_id'] == user_id:
            exclude_ids.add(friendship['friend_id'])
        elif friendship['friend_id'] == user_id:
            exclude_ids.add(friendship['user_id'])
    
    friends_of_friends = friends_of_friends - exclude_ids
    
    # 추천 목록 구성
    for fof_id in friends_of_friends:
        for user in users_data:
            if user['id'] == fof_id:
                mutual_count = calculate_mutual_friends(user_id, fof_id, friends_data)
                if mutual_count > 0:
                    recommendations.append({
                        'id': user['id'],
                        'nickname': user['nickname'],
                        'mutual_friends': mutual_count
                    })
                break
    
    # 함께 아는 친구 수가 많은 순으로 정렬
    recommendations.sort(key=lambda x: x['mutual_friends'], reverse=True)
    
    # 최대 6명만 추천
    return recommendations[:6]
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from datetime import datetime
from app import CSV_FILES
from utils import get_user_by_id, append_to_csv, get_recent_chat_messages

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

@chat_bp.route('/')
def index():
    if not g.user:
        return redirect(url_for('auth.login'))
    
    # 최근 메시지 가져오기
    messages = get_recent_chat_messages(50)
    
    # 사용자 정보 포함
    messages_with_users = []
    for msg in messages:
        user = get_user_by_id(msg['user_id'])
        username = user['nickname'] if user else msg['user_id']
        is_admin = user['is_admin'] if user else 'False'
        
        messages_with_users.append({
            'id': msg['id'],
            'user_id': msg['user_id'],
            'username': username,
            'is_admin': is_admin,
            'message': msg['message'],
            'timestamp': msg['timestamp'],
            'is_current_user': msg['user_id'] == g.user['id']
        })
    
    # 시간순으로 정렬
    messages_with_users.sort(key=lambda x: x['timestamp'])
    
    return render_template('chat.html', messages=messages_with_users)

@chat_bp.route('/send', methods=['POST'])
def send_message():
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
    
    message = request.form.get('message', '').strip()
    
    if not message:
        return jsonify({'success': False, 'message': '메시지를 입력하세요.'})
    
    # 메시지 추가
    msg = {
        'id': str(datetime.now().timestamp()),
        'user_id': g.user['id'],
        'message': message,
        'timestamp': str(datetime.now())
    }
    
    append_to_csv(CSV_FILES['chat_messages'], msg)
    
    # 사용자 정보 추가
    msg['username'] = g.user['nickname']
    msg['is_admin'] = g.user['is_admin']
    msg['is_current_user'] = True
    
    return jsonify({
        'success': True,
        'message': '메시지가 전송되었습니다.',
        'msg': msg
    })

@chat_bp.route('/update', methods=['GET'])
def update_messages():
    """새 메시지 가져오기"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
    
    last_time = request.args.get('last_time', '0')
    
    # 마지막 확인 시간 이후의 메시지 가져오기
    messages = get_recent_chat_messages(50)
    new_messages = []
    
    for msg in messages:
        if msg['timestamp'] > last_time:
            user = get_user_by_id(msg['user_id'])
            username = user['nickname'] if user else msg['user_id']
            is_admin = user['is_admin'] if user else 'False'
            
            new_messages.append({
                'id': msg['id'],
                'user_id': msg['user_id'],
                'username': username,
                'is_admin': is_admin,
                'message': msg['message'],
                'timestamp': msg['timestamp'],
                'is_current_user': msg['user_id'] == g.user['id']
            })
    
    # 시간순으로 정렬
    new_messages.sort(key=lambda x: x['timestamp'])
    
    return jsonify({
        'success': True,
        'messages': new_messages
    })

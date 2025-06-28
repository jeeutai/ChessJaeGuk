
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from datetime import datetime, timedelta
import csv
from app import CSV_FILES
from utils import read_csv, update_csv, append_to_csv, generate_id, get_timestamp, update_user_balance, award_points_for_action

events_bp = Blueprint('events', __name__, url_prefix='/events')

@events_bp.route('/')
def index():
    """이벤트 목록 페이지"""
    if not g.user:
        return redirect(url_for('auth.login'))
    
    # 이벤트 파일이 없으면 생성
    if not CSV_FILES.get('events'):
        CSV_FILES['events'] = 'data/events.csv'
        with open(CSV_FILES['events'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'title', 'description', 'start_time', 'end_time', 'reward_type', 'reward_amount'])

    if not CSV_FILES.get('event_attendance'):
        CSV_FILES['event_attendance'] = 'data/event_attendance.csv'
        with open(CSV_FILES['event_attendance'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'timestamp'])
    
    events = read_csv(CSV_FILES['events'])
    active_events = [e for e in events if is_event_active(e)]
    
    return render_template('events.html', events=active_events, is_admin=g.user.get('is_admin') == 'True')

@events_bp.route('/admin', methods=['GET', 'POST'])
def admin():
    """이벤트 관리자 페이지"""
    if not g.user or g.user.get('is_admin') != 'True':
        return redirect(url_for('home'))

    if request.method == 'POST':
        new_event = {
            'id': generate_id(),
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'start_time': request.form.get('start_time'),
            'end_time': request.form.get('end_time'),
            'reward_type': request.form.get('reward_type'),
            'reward_amount': request.form.get('reward_amount')
        }
        append_to_csv(CSV_FILES['events'], new_event)
        flash('이벤트가 추가되었습니다.', 'success')
        return redirect(url_for('events.admin'))

    events = read_csv(CSV_FILES['events'])
    return render_template('admin_events.html', events=events)

@events_bp.route('/attend')
def attend():
    """출석 체크"""
    if not g.user:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
    
    # 출석 기록 추가
    attendance = {
        'id': generate_id(),
        'user_id': g.user['id'],
        'timestamp': get_timestamp()
    }
    append_to_csv(CSV_FILES['event_attendance'], attendance)
    
    # 보상 지급
    update_user_balance(g.user['id'], 1000, "add")  # 1000원 지급
    award_points_for_action(g.user['id'], 'attendance', None)
    
    return jsonify({'success': True, 'message': '출석 체크 완료! 1000이 지급되었습니다.'})

def is_event_active(event):
    """이벤트 활성화 여부 확인"""
    try:
        now = datetime.now()
        start_time = datetime.strptime(event['start_time'], '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(event['end_time'], '%Y-%m-%d %H:%M:%S')
        return start_time <= now <= end_time
    except:
        return False

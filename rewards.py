import os
import logging
from flask import Blueprint, render_template, redirect, url_for, request, g, flash, jsonify
from utils import get_user_points, get_user_level, get_reward_items, purchase_reward_item, get_user_achievements, get_achievements
from app import CSV_FILES

# 블루프린트 정의
rewards_bp = Blueprint('rewards', __name__, url_prefix='/rewards')

@rewards_bp.route('/')
def index():
    """포인트 및 보상 메인 페이지"""
    if not g.user:
        return redirect(url_for('auth.login'))
        
    # 보상 아이템 목록 가져오기
    reward_items = get_reward_items()
    
    # 사용자 레벨 정보 가져오기
    user_level_info = get_user_level(g.user['id'])
    
    # 사용자 포인트 가져오기
    user_points = get_user_points(g.user['id'])
    
    # 보상 아이템 카테고리별 분류
    game_boosters = [item for item in reward_items if item.get('type') == 'buff' and item.get('effect') in ['game_reward_boost', 'luck_boost']]
    economy_items = [item for item in reward_items if item.get('effect') in ['waive_transfer_fee', 'stock_fee_discount', 'market_discount', 'money']]
    profile_items = [item for item in reward_items if item.get('type') == 'cosmetic']
    special_items = [item for item in reward_items if item.get('effect') in ['treasure_chest', 'random_reward', 'level_skip', 'vip_membership']]
    
    return render_template('rewards.html',
                          user_points=user_points,
                          user_level=user_level_info,
                          game_boosters=game_boosters,
                          economy_items=economy_items,
                          profile_items=profile_items,
                          special_items=special_items)

@rewards_bp.route('/purchase/<item_id>', methods=['POST'])
def purchase(item_id):
    """보상 아이템 구매"""
    if not g.user:
        return redirect(url_for('auth.login'))
    
    result = purchase_reward_item(g.user['id'], item_id)
    
    if result['success']:
        flash(result['message'], 'success')
        if 'effect' in result:
            flash(result['effect'], 'info')
    else:
        flash(result['message'], 'error')
    
    return redirect(url_for('rewards.index'))

@rewards_bp.route('/achievements')
def achievements():
    """업적 시스템 페이지"""
    if not g.user:
        return redirect(url_for('auth.login'))
    
    # 사용자 업적 정보 가져오기
    user_achievements_data = get_user_achievements(g.user['id'])
    
    # 카테고리별 업적 그룹화
    categories = {}
    for achievement in user_achievements_data:
        category = achievement.get('category', '기타')
        if category not in categories:
            categories[category] = []
        categories[category].append(achievement)
    
    return render_template('achievements.html', 
                          categories=categories,
                          user_points=get_user_points(g.user['id']),
                          user_level=get_user_level(g.user['id']))

@rewards_bp.route('/level')
def level():
    """레벨 시스템 페이지"""
    if not g.user:
        return redirect(url_for('auth.login'))
    
    # 사용자 레벨 정보 가져오기
    user_level_info = get_user_level(g.user['id'])
    
    # 다음 레벨까지 남은 포인트
    next_level_points = 0
    if user_level_info['next']:
        next_level_points = int(user_level_info['next']['points_required']) - user_level_info['points']
    
    # 완료한 업적 수
    completed_achievements = 0
    user_achievements_data = get_user_achievements(g.user['id'])
    for achievement in user_achievements_data:
        if achievement.get('completed', False):
            completed_achievements += 1
    
    return render_template('level.html',
                          user_level=user_level_info,
                          next_level_points=next_level_points,
                          completed_achievements=completed_achievements,
                          total_achievements=len(get_achievements()))

@rewards_bp.route('/points_history')
def points_history():
    """포인트 적립/사용 내역 페이지"""
    if not g.user:
        return redirect(url_for('auth.login'))
    
    # 포인트 로그 가져오기 (최신순)
    points_logs = []
    try:
        import csv
        from datetime import datetime
        
        with open(CSV_FILES['point_logs'], 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for log in reader:
                if log['user_id'] == g.user['id']:
                    points_logs.append(log)
        
        # 날짜 기준 최신순 정렬
        points_logs.sort(key=lambda x: x['timestamp'], reverse=True)
    except Exception as e:
        logging.error(f"포인트 로그를 불러오는 중 오류 발생: {e}")
    
    return render_template('points_history.html', 
                          points_logs=points_logs,
                          user_points=get_user_points(g.user['id']),
                          user_level=get_user_level(g.user['id']))
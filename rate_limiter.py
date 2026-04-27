#!/usr/bin/env python3
"""
AI文案工坊 V3.0 - 使用量控制与速率限制模块

功能:
- 基于角色/套餐的每日使用量检查
- 试用用户（未登录）IP级别限制
- 使用量记录写入 usage_logs 表
- 提供查询剩余次数的接口

依赖: sqlite3, flask.g (可选)
兼容: Python 3.6.8
"""

import os
import sqlite3
import time
import functools
from datetime import datetime, timedelta

from flask import request, jsonify, g


# ==================== 配置 ====================

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wenyan.db')

# 每日限制
DAILY_LIMIT_FREE = 10
DAILY_LIMIT_VIP = 100
DAILY_LIMIT_ENTERPRISE = -1  # -1 表示无限制

# 试用（未登录）限制
TRIAL_DAILY_LIMIT = 3  # 每个IP每天最多3次
TRIAL_MAX_TOPIC_LENGTH = 50  # 试用用户主题长度限制


# ==================== 数据库辅助 ====================

def _get_db():
    """获取数据库连接（优先使用Flask g，否则新建）"""
    if g is not None and 'db' in g:
        return g.db
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _get_today_str():
    """获取今天的日期字符串"""
    return datetime.now().strftime('%Y-%m-%d')


# ==================== 套餐限制映射 ====================

PLAN_LIMITS = {
    'free': DAILY_LIMIT_FREE,
    'vip': DAILY_LIMIT_VIP,
    'enterprise': DAILY_LIMIT_ENTERPRISE,
}


def get_user_daily_limit(user_id):
    """
    获取用户的每日使用限制

    Args:
        user_id: 用户ID

    Returns:
        tuple: (plan_type, daily_limit)
               daily_limit 为 -1 表示无限制
    """
    conn = _get_db()
    try:
        # 先查用户的角色
        user = conn.execute(
            "SELECT role FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        if not user:
            return ('free', DAILY_LIMIT_FREE)

        # 如果是管理员角色，直接无限制
        if user['role'] == 'admin':
            return ('enterprise', DAILY_LIMIT_ENTERPRISE)

        # 查询活跃套餐
        sub = conn.execute('''
            SELECT plan_type, daily_limit
            FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY
                CASE plan_type
                    WHEN 'enterprise' THEN 1
                    WHEN 'vip' THEN 2
                    WHEN 'free' THEN 3
                    ELSE 4
                END
            LIMIT 1
        ''', (user_id,)).fetchone()

        if sub:
            return (sub['plan_type'], sub['daily_limit'])

        # 无套餐记录，按角色判断
        if user['role'] == 'admin':
            return ('enterprise', DAILY_LIMIT_ENTERPRISE)

        return ('free', DAILY_LIMIT_FREE)
    finally:
        # 如果是独立创建的连接（不在Flask请求上下文中），需要关闭
        if g is None or 'db' not in g:
            conn.close()


def get_today_usage(user_id):
    """
    获取用户今日已成功的使用次数

    Args:
        user_id: 用户ID

    Returns:
        int: 今天的使用次数
    """
    conn = _get_db()
    today = _get_today_str()
    try:
        row = conn.execute('''
            SELECT COUNT(*) as count FROM usage_logs
            WHERE user_id = ?
              AND status = 'success'
              AND date(timestamp) = ?
        ''', (user_id, today)).fetchone()
        return row['count'] if row else 0
    finally:
        if g is None or 'db' not in g:
            conn.close()


def get_trial_usage(ip_address):
    """
    获取IP地址今日试用次数

    Args:
        ip_address: 客户端IP

    Returns:
        int: 今日试用次数
    """
    conn = _get_db()
    today = _get_today_str()
    try:
        row = conn.execute('''
            SELECT COUNT(*) as count FROM usage_logs
            WHERE ip_address = ?
              AND user_id IS NULL
              AND status = 'success'
              AND date(timestamp) = ?
        ''', (ip_address, today)).fetchone()
        return row['count'] if row else 0
    finally:
        if g is None or 'db' not in g:
            conn.close()


def log_usage(user_id, model, scene, prompt, response_length,
              response_time, ip_address, status='success',
              error_message=None, tokens_used=0):
    """
    记录一次使用日志到 usage_logs 表

    Args:
        user_id: 用户ID（试用用户为 None）
        model: 使用的AI模型
        scene: 使用场景
        prompt: 提示词
        response_length: 响应长度（字符数）
        response_time: 响应耗时（秒）
        ip_address: 客户端IP
        status: 状态 ('success', 'failed', 'rate_limited')
        error_message: 错误信息
        tokens_used: token使用量
    """
    conn = _get_db()
    try:
        conn.execute('''
            INSERT INTO usage_logs
            (user_id, model, scene, prompt, response_length, tokens_used,
             status, error_message, response_time, ip_address, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            user_id, model, scene, prompt, response_length, tokens_used,
            status, error_message, response_time, ip_address
        ))
        conn.commit()
    finally:
        if g is None or 'db' not in g:
            conn.close()


def get_client_ip():
    """获取客户端真实IP（支持代理）"""
    # 优先使用 X-Forwarded-For（Nginx等反向代理设置）
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        # X-Forwarded-For 可能包含多个IP，取第一个
        return forwarded.split(',')[0].strip()

    # X-Real-IP
    real_ip = request.headers.get('X-Real-IP', '')
    if real_ip:
        return real_ip.strip()

    # 直接连接
    return request.remote_addr or 'unknown'


# ==================== 权限检查核心逻辑 ====================

def check_rate_limit(user_id=None):
    """
    检查使用量限制

    Args:
        user_id: 用户ID（None表示试用用户）

    Returns:
        tuple: (allowed, message, limit, used, remaining)
            - allowed: 是否允许调用
            - message: 提示信息
            - limit: 每日限制（-1表示无限制）
            - used: 已用次数
            - remaining: 剩余次数
    """
    ip_address = get_client_ip()

    if user_id is not None:
        # 已登录用户：检查套餐限制
        plan_type, daily_limit = get_user_daily_limit(user_id)

        if daily_limit == -1:
            # 无限制
            return (True, '无限制', -1, 0, -1)

        used = get_today_usage(user_id)

        if used >= daily_limit:
            return (
                False,
                '今日使用次数已用完（{}/{}），请升级套餐'.format(used, daily_limit),
                daily_limit, used, 0
            )

        remaining = daily_limit - used
        return (True, '', daily_limit, used, remaining)
    else:
        # 试用用户：IP级别限制
        used = get_trial_usage(ip_address)

        if used >= TRIAL_DAILY_LIMIT:
            return (
                False,
                '今日试用次数已用完（{}/{}），请注册账号继续使用'.format(
                    used, TRIAL_DAILY_LIMIT
                ),
                TRIAL_DAILY_LIMIT, used, 0
            )

        remaining = TRIAL_DAILY_LIMIT - used
        return (True, '', TRIAL_DAILY_LIMIT, used, remaining)


# ==================== Flask 装饰器 ====================

def rate_limit(f):
    """
    使用量限制装饰器

    用法：
        @app.route('/api/generate', methods=['POST'])
        @rate_limit
        def generate():
            ...

    说明：
    - 如果请求携带有效的 Authorization: Bearer token，按用户套餐限制
    - 如果没有token或token无效，按试用限制（IP级别）
    - 通过后将 user_id 注入 g 对象
    - 超出限制时自动返回 429 响应
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        # 尝试从认证header获取用户
        user_id = _extract_user_id_from_request()

        allowed, message, limit, used, remaining = check_rate_limit(user_id)

        if not allowed:
            response = jsonify({
                "success": False,
                "error": message,
                "code": "RATE_LIMIT_EXCEEDED",
                "limit": limit,
                "used": used,
                "remaining": 0,
            })
            response.status_code = 429
            return response

        # 注入信息到请求上下文
        g.rate_limit_info = {
            'user_id': user_id,
            'limit': limit,
            'used': used,
            'remaining': remaining,
        }

        return f(*args, **kwargs)

    return decorated


def _extract_user_id_from_request():
    """
    从请求中提取用户ID

    Returns:
        int or None: 用户ID，未认证返回None
    """
    # 方式1: 从 g.current_user 获取（已被 login_required 设置）
    if g is not None and hasattr(g, 'current_user') and g.current_user:
        return g.current_user.get('user_id')

    # 方式2: 从 Authorization header 直接解析
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()
        if token:
            # 复用auth模块的verify_token
            from auth import verify_token
            payload = verify_token(token)
            if payload and payload.get('user_id'):
                return payload['user_id']

    return None


# ==================== 使用后记录装饰器 ====================

def record_usage_after(f):
    """
    在请求完成后记录使用量到 usage_logs

    需要配合 @rate_limit 使用，且被装饰的函数应返回包含
    'content', 'scene', 'model' 键的JSON响应
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        # 执行原始函数
        response = f(*args, **kwargs)

        # 尝试获取使用量信息
        rate_info = getattr(g, 'rate_limit_info', None)
        if rate_info is None:
            return response

        # 解析响应以记录日志
        try:
            # 获取响应内容
            if hasattr(response, 'get_json'):
                resp_data = response.get_json(silent=True) or {}
            elif hasattr(response, 'json'):
                resp_data = response.json or {}
            else:
                resp_data = {}

            content = resp_data.get('content', '')
            scene = resp_data.get('scene', '')
            model = resp_data.get('model', '')
            response_length = len(content) if content else 0
            response_time = resp_data.get('generation_time', 0)
            ip_address = get_client_ip()
            user_id = rate_info.get('user_id')

            # 获取请求体中的 topic 作为 prompt 摘要
            req_data = request.get_json(silent=True) or {}
            topic = req_data.get('topic', '')
            prompt = 'topic: {}'.format(topic) if topic else ''

            log_usage(
                user_id=user_id,
                model=model,
                scene=scene,
                prompt=prompt,
                response_length=response_length,
                response_time=response_time,
                ip_address=ip_address,
                status='success',
            )
        except Exception:
            # 记录失败不影响正常响应
            pass

        return response

    return decorated


# ==================== 组合装饰器 ====================

def generate_guard(f):
    """
    文案生成接口的完整守卫装饰器

    集成了:
    1. 使用量限制检查（@rate_limit）
    2. 使用后自动记录（@record_usage_after）

    用法:
        @app.route('/api/generate', methods=['POST'])
        @generate_guard
        def generate():
            ...
    """
    return record_usage_after(rate_limit(f))


# ==================== API 路由 ====================

def register_rate_limit_routes(app):
    """
    注册使用量相关的查询API路由

    用法:
        from rate_limiter import register_rate_limit_routes
        register_rate_limit_routes(app)
    """

    @app.route('/api/usage/check', methods=['GET'])
    def check_usage():
        """
        查询当前用户/试用者的使用量状态

        支持:
        - 已登录用户: 返回套餐信息和今日使用量
        - 试用用户: 返回IP级别的试用剩余次数
        """
        user_id = _extract_user_id_from_request()
        ip_address = get_client_ip()

        if user_id is not None:
            # 已登录用户
            plan_type, daily_limit = get_user_daily_limit(user_id)
            used = get_today_usage(user_id)

            if daily_limit == -1:
                remaining = -1
            else:
                remaining = max(0, daily_limit - used)

            # 获取用户基本信息
            conn = _get_db()
            user = conn.execute(
                "SELECT username, role FROM users WHERE id = ?", (user_id,)
            ).fetchone()

            return jsonify({
                "success": True,
                "authenticated": True,
                "user_id": user_id,
                "username": user['username'] if user else '',
                "role": user['role'] if user else '',
                "plan_type": plan_type,
                "daily_limit": daily_limit,
                "today_usage": used,
                "remaining": remaining,
            })
        else:
            # 试用用户
            used = get_trial_usage(ip_address)
            remaining = max(0, TRIAL_DAILY_LIMIT - used)

            return jsonify({
                "success": True,
                "authenticated": False,
                "ip_address": ip_address,
                "plan_type": 'trial',
                "daily_limit": TRIAL_DAILY_LIMIT,
                "today_usage": used,
                "remaining": remaining,
            })

    @app.route('/api/usage/history', methods=['GET'])
    def usage_history():
        """
        查询使用历史记录（需要登录）

        参数:
        - days: 查询天数（默认7）
        - page: 页码（默认1）
        - per_page: 每页条数（默认20）
        """
        user_id = _extract_user_id_from_request()
        if user_id is None:
            return jsonify({
                "success": False,
                "error": "需要登录才能查看使用历史",
                "code": "UNAUTHORIZED"
            }), 401

        days = request.args.get('days', 7, type=int)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        # 参数边界
        days = max(1, min(days, 90))
        page = max(1, page)
        per_page = max(1, min(per_page, 100))

        offset = (page - 1) * per_page

        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        conn = _get_db()

        # 总数
        total = conn.execute('''
            SELECT COUNT(*) as c FROM usage_logs
            WHERE user_id = ? AND date(timestamp) >= ?
        ''', (user_id, start_date)).fetchone()['c']

        # 记录
        rows = conn.execute('''
            SELECT id, model, scene, response_length, status,
                   response_time, timestamp
            FROM usage_logs
            WHERE user_id = ? AND date(timestamp) >= ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        ''', (user_id, start_date, per_page, offset)).fetchall()

        records = []
        for row in rows:
            records.append({
                'id': row['id'],
                'model': row['model'],
                'scene': row['scene'],
                'response_length': row['response_length'],
                'status': row['status'],
                'response_time': row['response_time'],
                'timestamp': row['timestamp'],
            })

        return jsonify({
            "success": True,
            "total": total,
            "page": page,
            "per_page": per_page,
            "records": records,
        })

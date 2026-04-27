#!/usr/bin/env python3
"""
AI文案工坊 V3.0 - 用户认证模块

提供：
- POST /api/auth/register  - 用户注册
- POST /api/auth/login     - 用户登录
- POST /api/auth/logout    - 用户登出
- GET  /api/auth/profile   - 获取当前用户信息
- POST /api/auth/change-password - 修改密码
- GET  /api/auth/check-token   - 验证token有效性

依赖：PyJWT 2.4.0（兼容 Python 3.6）
"""

import os
import re
import time
import sqlite3
import functools
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

try:
    import jwt
    PYJWT_AVAILABLE = True
except ImportError:
    PYJWT_AVAILABLE = False

# ==================== 配置 ====================

# JWT密钥（生产环境应使用环境变量）
JWT_SECRET = os.environ.get('JWT_SECRET', 'wenyan-v3-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_HOURS = 24  # token有效期（小时）
JWT_REFRESH_EXPIRE_DAYS = 30  # refresh token有效期（天）

# 密码要求
PASSWORD_MIN_LENGTH = 6
USERNAME_MIN_LENGTH = 2
USERNAME_MAX_LENGTH = 30
EMAIL_MAX_LENGTH = 120

# ==================== 数据库辅助 ====================

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wenyan.db')


def get_db():
    """获取当前请求的数据库连接（复用Flask g对象）"""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    """请求结束时关闭数据库连接"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def get_db_direct():
    """直接获取数据库连接（用于非请求上下文）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ==================== JWT工具 ====================

def generate_token(user_id, username, role='user', token_type='access'):
    """
    生成JWT token

    Args:
        user_id: 用户ID
        username: 用户名
        role: 用户角色
        token_type: 'access' 或 'refresh'

    Returns:
        str: JWT token字符串
    """
    if not PYJWT_AVAILABLE:
        return _generate_simple_token(user_id, username, role, token_type)

    now = datetime.utcnow()

    if token_type == 'refresh':
        expire_delta = timedelta(days=JWT_REFRESH_EXPIRE_DAYS)
    else:
        expire_delta = timedelta(hours=JWT_EXPIRE_HOURS)

    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'type': token_type,
        'iat': now,
        'exp': now + expire_delta,
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    # PyJWT 2.x 返回str，1.x 返回bytes
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    return token


def _generate_simple_token(user_id, username, role='user', token_type='access'):
    """
    降级方案：无PyJWT时使用简单base64 token
    （仅开发/测试环境）
    """
    import base64
    import hashlib

    now = str(int(time.time()))
    raw = "{}:{}:{}:{}".format(user_id, username, role, now)
    signature = hashlib.sha256(
        (raw + JWT_SECRET).encode('utf-8')
    ).hexdigest()[:16]
    encoded = base64.urlsafe_b64encode(
        raw.encode('utf-8')
    ).decode('utf-8')

    return "{}.{}.{}".format(encoded, signature, token_type)


def verify_token(token):
    """
    验证并解析JWT token

    Args:
        token: JWT token字符串

    Returns:
        dict: token payload 或 None
    """
    if not PYJWT_AVAILABLE:
        return _verify_simple_token(token)

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _verify_simple_token(token):
    """验证简单token（降级方案）"""
    import base64
    import hashlib

    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None

        encoded, signature, token_type = parts
        raw = base64.urlsafe_b64decode(encoded.encode('utf-8')).decode('utf-8')
        expected_sig = hashlib.sha256(
            (raw + JWT_SECRET).encode('utf-8')
        ).hexdigest()[:16]

        if signature != expected_sig:
            return None

        parts_raw = raw.split(':')
        if len(parts_raw) != 4:
            return None

        return {
            'user_id': int(parts_raw[0]),
            'username': parts_raw[1],
            'role': parts_raw[2],
            'type': token_type,
        }
    except Exception:
        return None


# ==================== 校验工具 ====================

def validate_username(username):
    """校验用户名格式"""
    if not username or not isinstance(username, str):
        return False, "用户名不能为空"
    if len(username) < USERNAME_MIN_LENGTH:
        return False, "用户名至少需要{}个字符".format(USERNAME_MIN_LENGTH)
    if len(username) > USERNAME_MAX_LENGTH:
        return False, "用户名不能超过{}个字符".format(USERNAME_MAX_LENGTH)
    if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fff]+$', username):
        return False, "用户名只能包含字母、数字、下划线和中文"
    return True, ""


def validate_email(email):
    """校验邮箱格式"""
    if not email or not isinstance(email, str):
        return False, "邮箱不能为空"
    if len(email) > EMAIL_MAX_LENGTH:
        return False, "邮箱地址过长"
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "邮箱格式不正确"
    return True, ""


def validate_password(password):
    """校验密码强度"""
    if not password or not isinstance(password, str):
        return False, "密码不能为空"
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, "密码至少需要{}个字符".format(PASSWORD_MIN_LENGTH)
    return True, ""


# ==================== 认证装饰器 ====================

def login_required(f):
    """
    登录验证装饰器
    从 Authorization header 中提取 Bearer token 并验证
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            return jsonify({
                "success": False,
                "error": "未提供认证token",
                "code": "UNAUTHORIZED"
            }), 401

        token = auth_header[7:].strip()
        if not token:
            return jsonify({
                "success": False,
                "error": "token为空",
                "code": "UNAUTHORIZED"
            }), 401

        payload = verify_token(token)
        if payload is None:
            return jsonify({
                "success": False,
                "error": "token无效或已过期",
                "code": "TOKEN_EXPIRED"
            }), 401

        # 将用户信息注入请求上下文
        g.current_user = {
            'user_id': payload['user_id'],
            'username': payload['username'],
            'role': payload.get('role', 'user'),
        }

        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    """
    管理员权限装饰器
    需要先经过 login_required
    """
    @functools.wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if g.current_user.get('role') != 'admin':
            return jsonify({
                "success": False,
                "error": "需要管理员权限",
                "code": "FORBIDDEN"
            }), 403
        return f(*args, **kwargs)

    return decorated


# ==================== 创建 Blueprint ====================

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


# ==================== API路由 ====================

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    用户注册

    请求体:
    {
        "username": "用户名",
        "email": "user@example.com",
        "password": "密码"
    }

    响应:
    {
        "success": true,
        "user_id": 1,
        "username": "用户名",
        "token": "JWT token",
        "expires_in": 86400
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "success": False,
            "error": "请求体必须是JSON格式"
        }), 400

    username = data.get('username', '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')

    # 校验
    valid, msg = validate_username(username)
    if not valid:
        return jsonify({"success": False, "error": msg}), 400

    valid, msg = validate_email(email)
    if not valid:
        return jsonify({"success": False, "error": msg}), 400

    valid, msg = validate_password(password)
    if not valid:
        return jsonify({"success": False, "error": msg}), 400

    # 密码加密
    password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    conn = get_db()
    try:
        cursor = conn.cursor()

        # 检查用户名是否已存在
        existing = cursor.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return jsonify({
                "success": False,
                "error": "用户名已被注册"
            }), 409

        # 检查邮箱是否已存在
        existing = cursor.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            return jsonify({
                "success": False,
                "error": "邮箱已被注册"
            }), 409

        # 创建用户
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role, created_at)
            VALUES (?, ?, ?, 'user', CURRENT_TIMESTAMP)
        ''', (username, email, password_hash))

        user_id = cursor.lastrowid

        # 创建默认free套餐
        cursor.execute('''
            INSERT INTO subscriptions (user_id, plan_type, daily_limit, monthly_limit)
            VALUES (?, 'free', 10, 300)
        ''', (user_id,))

        conn.commit()

        # 生成token
        token = generate_token(user_id, username, role='user')
        expires_in = JWT_EXPIRE_HOURS * 3600

        return jsonify({
            "success": True,
            "user_id": user_id,
            "username": username,
            "email": email,
            "role": "user",
            "token": token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "message": "注册成功"
        }), 201

    except sqlite3.IntegrityError as e:
        conn.rollback()
        if 'username' in str(e):
            return jsonify({
                "success": False,
                "error": "用户名已被注册"
            }), 409
        elif 'email' in str(e):
            return jsonify({
                "success": False,
                "error": "邮箱已被注册"
            }), 409
        return jsonify({
            "success": False,
            "error": "注册失败: {}".format(str(e))
        }), 500
    except Exception as e:
        conn.rollback()
        return jsonify({
            "success": False,
            "error": "服务器内部错误: {}".format(str(e))
        }), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录

    请求体:
    {
        "username": "用户名或邮箱",
        "password": "密码"
    }

    响应:
    {
        "success": true,
        "user_id": 1,
        "username": "用户名",
        "email": "user@example.com",
        "role": "user",
        "token": "JWT token",
        "refresh_token": "刷新token",
        "expires_in": 86400
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "success": False,
            "error": "请求体必须是JSON格式"
        }), 400

    identifier = (data.get('username') or data.get('email') or '').strip()
    password = data.get('password', '')

    if not identifier:
        return jsonify({
            "success": False,
            "error": "请输入用户名或邮箱"
        }), 400

    if not password:
        return jsonify({
            "success": False,
            "error": "请输入密码"
        }), 400

    conn = get_db()
    try:
        # 支持用户名或邮箱登录
        user = conn.execute('''
            SELECT id, username, email, password_hash, role
            FROM users
            WHERE username = ? OR email = ?
        ''', (identifier, identifier)).fetchone()

        if not user:
            return jsonify({
                "success": False,
                "error": "用户名或密码错误"
            }), 401

        # 验证密码
        if not check_password_hash(user['password_hash'], password):
            return jsonify({
                "success": False,
                "error": "用户名或密码错误"
            }), 401

        # 更新最后登录时间
        conn.execute('''
            UPDATE users SET last_login = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (user['id'],))
        conn.commit()

        # 获取套餐信息
        sub = conn.execute('''
            SELECT plan_type, daily_limit, expires_at, status
            FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY expires_at DESC
            LIMIT 1
        ''', (user['id'],)).fetchone()

        plan_type = sub['plan_type'] if sub else 'free'
        daily_limit = sub['daily_limit'] if sub else 10

        # 生成token
        token = generate_token(user['id'], user['username'], role=user['role'])
        refresh_token = generate_token(
            user['id'], user['username'], role=user['role'], token_type='refresh'
        )

        expires_in = JWT_EXPIRE_HOURS * 3600

        return jsonify({
            "success": True,
            "user_id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "role": user['role'],
            "plan_type": plan_type,
            "daily_limit": daily_limit,
            "token": token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "message": "登录成功"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": "服务器内部错误: {}".format(str(e))
        }), 500


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """
    用户登出（客户端需清除本地token）
    """
    return jsonify({
        "success": True,
        "message": "登出成功，请清除本地token"
    }), 200


@auth_bp.route('/profile', methods=['GET'])
@login_required
def get_profile():
    """
    获取当前用户信息
    """
    user_id = g.current_user['user_id']
    conn = get_db()

    user = conn.execute('''
        SELECT id, username, email, role, created_at, last_login
        FROM users
        WHERE id = ?
    ''', (user_id,)).fetchone()

    if not user:
        return jsonify({
            "success": False,
            "error": "用户不存在"
        }), 404

    # 获取套餐信息
    sub = conn.execute('''
        SELECT plan_type, daily_limit, monthly_limit, expires_at, status
        FROM subscriptions
        WHERE user_id = ? AND status = 'active'
        ORDER BY expires_at DESC
        LIMIT 1
    ''', (user_id,)).fetchone()

    # 获取今日使用次数（使用 SQLite 的 date('now') 保持与时区一致）
    usage = conn.execute('''
        SELECT COUNT(*) as count FROM usage_logs
        WHERE user_id = ? AND date(timestamp) = date('now')
    ''', (user_id,)).fetchone()

    today_count = usage['count'] if usage else 0

    result = {
        "success": True,
        "user": {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "role": user['role'],
            "created_at": user['created_at'],
            "last_login": user['last_login'],
        },
        "subscription": {
            "plan_type": sub['plan_type'] if sub else 'free',
            "daily_limit": sub['daily_limit'] if sub else 10,
            "monthly_limit": sub['monthly_limit'] if sub else 300,
            "expires_at": sub['expires_at'] if sub else None,
            "status": sub['status'] if sub else 'active',
        } if sub else None,
        "usage": {
            "today_count": today_count,
            "remaining": max(0, (sub['daily_limit'] if sub else 10) - today_count),
        }
    }

    return jsonify(result), 200


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    使用 refresh_token 获取新的 access_token

    请求体:
    {
        "refresh_token": "刷新token"
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "success": False,
            "error": "请求体必须是JSON格式"
        }), 400

    refresh_token_str = data.get('refresh_token', '')
    if not refresh_token_str:
        return jsonify({
            "success": False,
            "error": "缺少refresh_token"
        }), 400

    payload = verify_token(refresh_token_str)
    if payload is None:
        return jsonify({
            "success": False,
            "error": "refresh_token无效或已过期"
        }), 401

    if payload.get('type') != 'refresh':
        return jsonify({
            "success": False,
            "error": "这不是一个有效的refresh_token"
        }), 400

    # 生成新的 access_token
    new_token = generate_token(
        payload['user_id'],
        payload['username'],
        role=payload.get('role', 'user')
    )

    return jsonify({
        "success": True,
        "token": new_token,
        "token_type": "Bearer",
        "expires_in": JWT_EXPIRE_HOURS * 3600
    }), 200


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """
    修改密码

    请求体:
    {
        "old_password": "旧密码",
        "new_password": "新密码"
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "success": False,
            "error": "请求体必须是JSON格式"
        }), 400

    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not old_password or not new_password:
        return jsonify({
            "success": False,
            "error": "请提供旧密码和新密码"
        }), 400

    valid, msg = validate_password(new_password)
    if not valid:
        return jsonify({"success": False, "error": msg}), 400

    user_id = g.current_user['user_id']
    conn = get_db()

    user = conn.execute(
        "SELECT password_hash FROM users WHERE id = ?", (user_id,)
    ).fetchone()

    if not user:
        return jsonify({
            "success": False,
            "error": "用户不存在"
        }), 404

    if not check_password_hash(user['password_hash'], old_password):
        return jsonify({
            "success": False,
            "error": "旧密码不正确"
        }), 401

    new_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_hash, user_id)
    )
    conn.commit()

    return jsonify({
        "success": True,
        "message": "密码修改成功"
    }), 200


@auth_bp.route('/check-token', methods=['GET'])
def check_token():
    """
    验证token是否有效

    需要 Authorization: Bearer <token>
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({
            "success": False,
            "valid": False,
            "error": "未提供token"
        }), 401

    token = auth_header[7:].strip()
    payload = verify_token(token)

    if payload is None:
        return jsonify({
            "success": True,
            "valid": False,
            "message": "token已过期或无效"
        }), 200

    return jsonify({
        "success": True,
        "valid": True,
        "user_id": payload.get('user_id'),
        "username": payload.get('username'),
        "role": payload.get('role'),
        "exp": payload.get('exp')
    }), 200


# ==================== 初始化辅助 ====================

def create_default_admin():
    """创建默认管理员账户（仅在管理员不存在时）"""
    conn = get_db_direct()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE role = 'admin'"
        ).fetchone()

        if not existing:
            admin_hash = generate_password_hash(
                'admin123', method='pbkdf2:sha256'
            )
            conn.execute('''
                INSERT INTO users (username, email, password_hash, role, created_at)
                VALUES (?, ?, ?, 'admin', CURRENT_TIMESTAMP)
            ''', ('admin', 'admin@wenyan.ai', admin_hash))

            conn.execute('''
                INSERT INTO subscriptions
                (user_id, plan_type, daily_limit, monthly_limit, expires_at)
                VALUES (?, 'enterprise', 9999, 99999, '2099-12-31')
            ''', (conn.execute("SELECT last_insert_rowid()").fetchone()[0],))

            conn.commit()
            print("  默认管理员账户已创建: admin / admin123")
        else:
            print("  管理员账户已存在，跳过")
    finally:
        conn.close()


def init_auth(app):
    """
    初始化认证模块：注册Blueprint和teardown

    用法：
        from auth import init_auth
        init_auth(app)
    """
    app.register_blueprint(auth_bp)
    app.teardown_appcontext(close_db)

    # 创建默认管理员
    create_default_admin()

    print("  认证模块已初始化")

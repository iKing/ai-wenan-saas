#!/usr/bin/env python3
"""
AI文案工坊 V3.0 - 认证模块测试脚本
测试注册、登录、profile、修改密码等API
"""

import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from auth import auth_bp, init_auth

# ==================== 测试框架 ====================

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name):
        self.passed += 1
        print("  PASS: {}".format(name))

    def fail(self, name, msg=""):
        self.failed += 1
        self.errors.append("{}: {}".format(name, msg))
        print("  FAIL: {} - {}".format(name, msg))


result = TestResult()


def check(name, condition, msg=""):
    if condition:
        result.ok(name)
    else:
        result.fail(name, msg)


# ==================== 创建测试应用 ====================

app = Flask(__name__)
app.config['TESTING'] = True

# 注册认证 Blueprint
app.register_blueprint(auth_bp)
app.teardown_appcontext(lambda exc: None)

# 创建默认管理员
from auth import create_default_admin
create_default_admin()

client = app.test_client()

print("=" * 60)
print("AI文案工坊 V3.0 - 认证模块测试")
print("=" * 60)

# ==================== 测试1: 注册 ====================
print("\n[测试 1] 用户注册")

# 1.1 正常注册
resp = client.post('/api/auth/register',
    data=json.dumps({
        "username": "testuser",
        "email": "test@example.com",
        "password": "test123456"
    }),
    content_type='application/json'
)
check("注册返回201", resp.status_code == 201, "状态码: {}".format(resp.status_code))
data = resp.get_json()
check("注册返回success", data.get('success') == True)
check("注册返回token", 'token' in data)
check("注册返回user_id", 'user_id' in data)
check("注册返回email", data.get('email') == 'test@example.com')
if 'token' in data:
    test_token = data['token']

# 1.2 重复用户名
resp = client.post('/api/auth/register',
    data=json.dumps({
        "username": "testuser",
        "email": "other@example.com",
        "password": "test123456"
    }),
    content_type='application/json'
)
check("重复用户名返回409", resp.status_code == 409, "状态码: {}".format(resp.status_code))

# 1.3 重复邮箱
resp = client.post('/api/auth/register',
    data=json.dumps({
        "username": "otheruser",
        "email": "test@example.com",
        "password": "test123456"
    }),
    content_type='application/json'
)
check("重复邮箱返回409", resp.status_code == 409, "状态码: {}".format(resp.status_code))

# 1.4 缺少字段
resp = client.post('/api/auth/register',
    data=json.dumps({"username": "nouser"}),
    content_type='application/json'
)
check("缺少字段返回400", resp.status_code == 400)

# 1.5 密码太短
resp = client.post('/api/auth/register',
    data=json.dumps({
        "username": "short",
        "email": "short@example.com",
        "password": "123"
    }),
    content_type='application/json'
)
check("密码太短返回400", resp.status_code == 400)

# ==================== 测试2: 登录 ====================
print("\n[测试 2] 用户登录")

# 2.1 用户名登录
resp = client.post('/api/auth/login',
    data=json.dumps({
        "username": "testuser",
        "password": "test123456"
    }),
    content_type='application/json'
)
check("用户名登录返回200", resp.status_code == 200, "状态码: {}".format(resp.status_code))
data = resp.get_json()
check("登录返回token", 'token' in data)
check("登录返回refresh_token", 'refresh_token' in data)
check("登录返回plan_type", data.get('plan_type') == 'free')
if 'token' in data:
    login_token = data['token']
    refresh_token = data['refresh_token']

# 2.2 邮箱登录
resp = client.post('/api/auth/login',
    data=json.dumps({
        "username": "test@example.com",
        "password": "test123456"
    }),
    content_type='application/json'
)
check("邮箱登录返回200", resp.status_code == 200)

# 2.3 错误密码
resp = client.post('/api/auth/login',
    data=json.dumps({
        "username": "testuser",
        "password": "wrongpassword"
    }),
    content_type='application/json'
)
check("错误密码返回401", resp.status_code == 401)

# 2.4 不存在的用户
resp = client.post('/api/auth/login',
    data=json.dumps({
        "username": "nobody",
        "password": "test123456"
    }),
    content_type='application/json'
)
check("不存在用户返回401", resp.status_code == 401)

# ==================== 测试3: 获取Profile ====================
print("\n[测试 3] 获取用户信息")

# 3.1 无token
resp = client.get('/api/auth/profile')
check("无token返回401", resp.status_code == 401)

# 3.2 有token
resp = client.get('/api/auth/profile',
    headers={'Authorization': 'Bearer {}'.format(login_token)}
)
check("有token返回200", resp.status_code == 200, "状态码: {}".format(resp.status_code))
data = resp.get_json()
check("profile返回user", 'user' in data)
check("profile返回subscription", data.get('subscription') is not None)
check("profile返回usage", 'usage' in data)
if 'user' in data:
    check("用户名正确", data['user']['username'] == 'testuser')

# ==================== 测试4: 修改密码 ====================
print("\n[测试 4] 修改密码")

resp = client.post('/api/auth/change-password',
    data=json.dumps({
        "old_password": "test123456",
        "new_password": "newpass789"
    }),
    content_type='application/json',
    headers={'Authorization': 'Bearer {}'.format(login_token)}
)
check("修改密码返回200", resp.status_code == 200, "状态码: {}".format(resp.status_code))

# 用新密码登录
resp = client.post('/api/auth/login',
    data=json.dumps({
        "username": "testuser",
        "password": "newpass789"
    }),
    content_type='application/json'
)
check("新密码登录成功", resp.status_code == 200)

# ==================== 测试5: Token验证 ====================
print("\n[测试 5] Token验证")

resp = client.get('/api/auth/check-token',
    headers={'Authorization': 'Bearer {}'.format(login_token)}
)
check("check-token返回valid=true",
    resp.get_json().get('valid') == True)

# 无效token
resp = client.get('/api/auth/check-token',
    headers={'Authorization': 'Bearer invalidtoken123'}
)
check("无效token返回valid=false",
    resp.get_json().get('valid') == False)

# ==================== 测试6: Refresh Token ====================
print("\n[测试 6] 刷新Token")

resp = client.post('/api/auth/refresh',
    data=json.dumps({"refresh_token": refresh_token}),
    content_type='application/json'
)
check("refresh返回200", resp.status_code == 200, "状态码: {}".format(resp.status_code))
data = resp.get_json()
check("refresh返回新token", 'token' in data)

# ==================== 测试7: 管理员功能 ====================
print("\n[测试 7] 管理员登录")

resp = client.post('/api/auth/login',
    data=json.dumps({
        "username": "admin",
        "password": "admin123"
    }),
    content_type='application/json'
)
check("管理员登录成功", resp.status_code == 200)
data = resp.get_json()
if data.get('success'):
    check("管理员role正确", data.get('role') == 'admin')

# ==================== 汇总 ====================
print("\n" + "=" * 60)
print("测试结果: {} 通过, {} 失败".format(result.passed, result.failed))
if result.failed > 0:
    print("\n失败的测试:")
    for e in result.errors:
        print("  - {}".format(e))
print("=" * 60)

sys.exit(0 if result.failed == 0 else 1)

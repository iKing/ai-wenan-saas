#!/usr/bin/env python3
"""
AI文案工坊 - 后端API服务 V2
集成真实AI模型调用（通义千问 / Claude / OpenAI）
"""

from flask import Flask, request, jsonify, send_from_directory, g
import os
import json
import time
import sqlite3
import re
from datetime import datetime, timedelta
from functools import wraps

# ==================== 导入认证模块 ====================
from auth import init_auth, login_required, admin_required

# ==================== 导入使用量限制模块 ====================
from rate_limiter import (
    generate_guard,
    register_rate_limit_routes,
    get_client_ip,
    log_usage,
    check_rate_limit,
    TRIAL_MAX_TOPIC_LENGTH,
)

# ==================== 自动加载配置 ====================
# 启动时自动读取 Hermes 的环境变量文件
HERMES_ENV = os.path.expanduser('~/.hermes/.env')
if os.path.exists(HERMES_ENV):
    with open(HERMES_ENV, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # 清洗 Key：去掉首尾空格和引号
                value = value.strip().strip('"').strip("'") 
                os.environ.setdefault(key, value)
    print(f"✅ 已自动加载环境变量: {HERMES_ENV}")
else:
    print(f"⚠️ 未找到环境变量文件: {HERMES_ENV}")

app = Flask(__name__, static_folder='/home/admin')

# ==================== CORS 支持 ====================
@app.after_request
def add_cors_headers(response):
    """允许所有来源跨域访问（生产环境应限制域名）"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
    return response

# ==================== 配置 ====================
class Config:
    AI_MODEL = os.getenv('AI_MODEL', 'qwen')  # qwen / claude / openai / deepseek / token-plan
    DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY', '')
    CLAUDE_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', os.getenv('OPENAI_API_KEY', ''))
    DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
    TOKEN_PLAN_API_KEY = os.getenv('TOKEN_PLAN_API_KEY', '')
    TOKEN_PLAN_BASE_URL = os.getenv('TOKEN_PLAN_BASE_URL', '')
    
    # 免费版限制
    FREE_DAILY_LIMIT = 10
    
    # 定价
    PRICES = {
        'pro_monthly': 9.9,
        'pro_yearly': 79,
        'enterprise': 99
    }

# ==================== 数据库 ====================
DB_PATH = os.path.join(os.path.dirname(__file__), 'wenyan.db')

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库"""
    # 先升级users表字段（Python层面处理，避免重复添加）
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for col_name, col_def in [('email', "TEXT DEFAULT ''"), ('role', "TEXT DEFAULT 'user'"), ('last_login', "TIMESTAMP")]:
        try:
            cursor.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_def}')
            print(f'[DB] 添加users.{col_name}列')
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e):
                pass  # 列已存在
            else:
                raise
    conn.commit()
    conn.close()
    
    # 创建其他表
    conn = sqlite3.connect(DB_PATH)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plan TEXT DEFAULT 'free',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            topic TEXT NOT NULL,
            scene TEXT,
            style TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS daily_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- V3.0 新增表
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            scene TEXT,
            prompt TEXT,
            response_length INTEGER DEFAULT 0,
            tokens_used INTEGER DEFAULT 0,
            status TEXT DEFAULT 'success' CHECK(status IN ('success', 'failed', 'rate_limited')),
            error_message TEXT,
            response_time REAL,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_type TEXT NOT NULL DEFAULT 'free' CHECK(plan_type IN ('free', 'vip', 'enterprise')),
            daily_limit INTEGER DEFAULT 10,
            monthly_limit INTEGER DEFAULT 300,
            max_tokens_per_request INTEGER DEFAULT 2000,
            priority INTEGER DEFAULT 0,
            expires_at TIMESTAMP,
            auto_renew INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'expired', 'cancelled')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, plan_type)
        );

        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_logs(user_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_usage_model ON usage_logs(model);
        CREATE INDEX IF NOT EXISTS idx_sub_user ON subscriptions(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_sub_expires ON subscriptions(expires_at);
    ''')
    conn.commit()
    conn.close()
    print('[DB] 数据库初始化完成')

# ==================== 认证中间件 ====================
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({"error": "缺少API Key"}), 401
        # 验证逻辑
        return f(*args, **kwargs)
    return decorated

# ==================== AI调用 ====================
def call_ai_model(prompt, model=None):
    """统一AI调用接口，支持多种模型"""
    model = model or Config.AI_MODEL
    
    if model == 'template':
        return _template_mode(prompt)
    elif model.startswith('token-plan'):
        # Handle different Token Plan models
        if model == 'token-plan-qwen':
            return call_token_plan(prompt, model_name="qwen3.6-plus")
        elif model == 'token-plan-glm':
            return call_token_plan(prompt, model_name="glm-5")
        elif model == 'token-plan-minimax':
            return call_token_plan(prompt, model_name="MiniMax-M2.5")
        else:
            return call_token_plan(prompt, model_name="qwen3.6-plus") # Default fallback
    elif model == 'qwen':
        return call_qwen(prompt)
    elif model == 'claude':
        return call_claude(prompt)
    elif model == 'openai':
        return call_openai(prompt)
    elif model == 'deepseek':
        return call_deepseek(prompt)
    else:
        return call_qwen(prompt)  # 默认通义千问

def _template_mode(prompt):
    """本地模板模式，无需API Key"""
    return "📝 [本地模板模式]\n\n当前服务正在运行，但模板模式仅作演示。\n建议配置 DeepSeek 或 Qwen API Key 以获得最佳效果。\n\n提示词摘要: " + prompt[:100]

def call_token_plan(prompt, model_name="qwen3.6-plus"):
    """Token Plan 调用 (阿里云 MaaS 兼容接口) - 支持 403 容灾切换"""
    try:
        api_key = Config.TOKEN_PLAN_API_KEY
        base_url = Config.TOKEN_PLAN_BASE_URL
        if not api_key or not base_url:
            return "⚠️ 未配置 Token Plan API Key 或 Base URL"
            
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.8
        }
        
        import requests
        url = f"{base_url}/chat/completions"
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        
        # 403 容灾：如果主模型不可用（无权限/欠费），自动切换到 GLM-5
        if response.status_code == 403:
            if model_name != "glm-5":
                print(f"⚠️ 模型 {model_name} 无权限 (403)，正在自动切换到 glm-5...")
                return call_token_plan(prompt, model_name="glm-5")
            else:
                return f"⚠️ Token Plan 权限不足 (403)。请检查 Key 是否已购买该模型服务。"
        
        response.raise_for_status()
        result = response.json()
        
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        return f"Token Plan 调用失败: {str(e)}"

def call_qwen(prompt):
    """通义千问调用 (使用 HTTP API 兼容 Python 3.6)"""
    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        api_key = Config.DASHSCOPE_API_KEY
        
        if not api_key:
            return "⚠️ 未配置 API Key，请在 config.json 中填入 DASHSCOPE_API_KEY"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": "qwen-plus",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.8
        }
        
        import requests
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        return f"AI 调用失败: {str(e)}"

def call_claude(prompt):
    """Claude调用"""
    try:
        import anthropic
        
        client = anthropic.Anthropic(api_key=Config.CLAUDE_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    except ImportError:
        return "[模板模式] anthropic未安装"
    except Exception as e:
        return f"[模板模式] Claude调用异常: {str(e)}"

def call_openai(prompt):
    """OpenAI调用"""
    return _call_openai_compatible(prompt, Config.OPENAI_API_KEY, "https://api.openai.com/v1", "gpt-4o")

def call_deepseek(prompt):
    """DeepSeek调用 (使用 HTTP API 兼容 Python 3.6)"""
    try:
        url = "https://api.deepseek.com/v1/chat/completions"
        api_key = Config.DEEPSEEK_API_KEY
        
        if not api_key:
            return "⚠️ 未配置 DeepSeek API Key"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.8
        }
        
        import requests
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        return f"DeepSeek 调用失败: {str(e)}"

def _call_openai_compatible(prompt, api_key, base_url, model_name):
    """通用OpenAI格式接口调用"""
    try:
        from openai import OpenAI
        if not api_key:
            return f"[未配置Key] 请在环境变量中设置 {api_key.split('_')[0]+'_API_KEY' if '_' in api_key else 'API_KEY'}"
            
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000
        )
        return response.choices[0].message.content
    except ImportError:
        return "[模板模式] openai未安装"
    except Exception as e:
        return f"[模板模式] 调用异常: {str(e)}"

# ==================== 提示词模板 ====================
# 导入医药准入专家模板
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'prompt_templates'))
try:
    from expert_access_strategy import EXPERT_SYSTEM_PROMPT, USER_INPUT_TEMPLATE, SCENE_PROMPTS as EXPERT_SCENE_PROMPTS
    print("✅ 已加载医药准入专家模板")
except ImportError:
    print("⚠️ 医药准入模板未找到")
    EXPERT_SYSTEM_PROMPT = ""
    USER_INPUT_TEMPLATE = ""

PROMPTS = {
    'xiaohongshu': """请写一篇小红书风格的种草文案。
要求：
- 使用emoji和生动的排版
- 语气亲切，像闺蜜分享
- 包含产品亮点和使用感受
- 结尾带相关话题标签
- 字数：200-400字

主题：{topic}
风格：{style}""",

    'pengyouquan': """请写一篇适合朋友圈发布的文案。
要求：
- 简短精炼，100字以内
- 自然不生硬
- 适合配图发布

主题：{topic}
风格：{style}""",

    'dianshang': """请写一篇电商商品描述文案。
要求：
- 突出核心卖点
- 刺激购买欲望
- 包含促销信息
- 适合淘宝/拼多多详情页

主题：{topic}
风格：{style}""",

    'biaoti': """请为以下内容生成10个爆款标题。
要求：
- 覆盖悬念式、数字式、痛点式等多种风格
- 吸引点击
- 适合小红书/公众号/抖音

主题：{topic}
风格：{style}""",

    'gongzhonghao': """请写一篇公众号文章大纲和开头段落。
要求：
- 结构清晰，分5-6个部分
- 每部分有核心观点
- 开头要有吸引力
- 适合深度阅读

主题：{topic}
风格：{style}""",

    'shipin': """请写一个短视频拍摄脚本。
要求：
- 包含分镜描述和台词
- 总时长30-60秒
- 节奏紧凑，前3秒有冲击力
- 包含BGM建议

主题：{topic}
风格：{style}""",

    'yingxiao': """请写一段高转化率的营销话术。
要求：
- 直击用户痛点，给出解决方案
- 语气真诚，强调限时/稀缺性
- 包含明确的行动指令 (CTA)
- 字数：150-300字

主题：{topic}
风格：{style}""" + ("" if not EXPERT_SYSTEM_PROMPT else "\n\n---\n\n[医药准入专家模式已激活]"),

    # 新增：医药准入专家模式
    'expert_access': EXPERT_SYSTEM_PROMPT + "\n\n【任务背景】\n{topic}\n\n【补充信息】\n{style}\n\n请开始分析：",
}

# ==================== API路由 ====================
@app.route('/')
def index():
    """前端页面"""
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')

@app.route('/api/health')
def health():
    return jsonify({
        "status": "ok",
        "model": Config.AI_MODEL,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/generate', methods=['POST'])
@generate_guard
def generate():
    """文案生成接口 - 集成权限检查和用量记录"""
    data = request.json
    if not data or 'topic' not in data:
        return jsonify({"error": "缺少主题参数"}), 400
    
    topic = data['topic'].strip()
    if not topic:
        return jsonify({"error": "主题不能为空"}), 400
    
    # 试用用户主题长度限制
    rate_info = getattr(g, 'rate_limit_info', None)
    if rate_info and rate_info.get('user_id') is None:
        if len(topic) > TRIAL_MAX_TOPIC_LENGTH:
            return jsonify({"error": "试用用户主题不能超过{}字".format(TRIAL_MAX_TOPIC_LENGTH)}), 400
    
    if len(topic) > 200:
        return jsonify({"error": "主题过长（最大200字）"}), 400
    
    scene = data.get('scene', 'xiaohongshu')
    style = data.get('style', '热情种草')
    model = data.get('model', 'deepseek')
    
    # 白名单校验
    valid_scenes = list(PROMPTS.keys())
    if scene not in valid_scenes:
        scene = 'xiaohongshu'
    
    valid_models = ['deepseek', 'qwen', 'claude', 'openai', 'template', 'token-plan-qwen', 'token-plan-glm', 'token-plan-minimax']
    if model not in valid_models:
        model = 'qwen'  # 默认降级
    
    # 构建提示词
    prompt_template = PROMPTS.get(scene, PROMPTS['xiaohongshu'])
    prompt = prompt_template.format(topic=topic, style=style)
    
    # 调用 AI (传入 model 参数)
    start_time = time.time()
    content = call_ai_model(prompt, model=model)
    elapsed = time.time() - start_time
    
    response = jsonify({
        "success": True,
        "content": content,
        "scene": scene,
        "style": style,
        "word_count": len(content),
        "generation_time": round(elapsed, 2),
        "model": model,  # 返回实际使用的模型
        "remaining": max(0, getattr(g, 'rate_limit_info', {}).get('remaining', -1) - 1) if getattr(g, 'rate_limit_info', {}).get('remaining', -1) > 0 else getattr(g, 'rate_limit_info', {}).get('remaining', -1),
    })
    return response

@app.route('/api/user/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "缺少用户名或密码"}), 400
    
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password)  # 实际应使用hash
        )
        conn.commit()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        
        return jsonify({
            "success": True,
            "user_id": user['id'],
            "username": user['username'],
            "plan": user['plan']
        })
    except sqlite3.IntegrityError:
        return jsonify({"error": "用户名已存在"}), 409
    finally:
        conn.close()

@app.route('/api/user/usage', methods=['GET'])
def get_usage():
    """获取今日使用次数"""
    username = request.args.get('username')
    if not username:
        return jsonify({"error": "缺少用户名"}), 400
    
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    usage = conn.execute(
        """SELECT count FROM daily_usage 
           JOIN users ON daily_usage.user_id = users.id
           WHERE users.username = ? AND daily_usage.date = ?""",
        (username, today)
    ).fetchone()
    
    count = usage['count'] if usage else 0
    remaining = max(0, Config.FREE_DAILY_LIMIT - count)
    
    conn.close()
    return jsonify({
        "today_usage": count,
        "remaining": remaining,
        "daily_limit": Config.FREE_DAILY_LIMIT
    })

@app.route('/api/stats')
def stats():
    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
    total_gens = conn.execute("SELECT COUNT(*) as c FROM generations").fetchone()['c']
    conn.close()
    
    return jsonify({
        "total_users": total_users,
        "total_generations": total_gens,
        "model": Config.AI_MODEL
    })

# ==================== 支付模块 ====================
from payment import create_payment, handle_payment_callback

@app.route('/api/payment/wechat', methods=['POST'])
def wechat_pay():
    data = request.json
    if not data:
        return jsonify({"error": "Missing data"}), 400
    result = create_payment(
        user_id=data.get('user_id', 0), 
        product=data.get('product', 'pro_monthly'), 
        method='wechat'
    )
    return jsonify({"success": True, "data": result})

@app.route('/api/payment/alipay', methods=['POST'])
def alipay_pay():
    data = request.json
    if not data:
        return jsonify({"error": "Missing data"}), 400
    result = create_payment(
        user_id=data.get('user_id', 0), 
        product=data.get('product', 'pro_monthly'), 
        method='alipay'
    )
    return jsonify({"success": True, "data": result})

@app.route('/api/payment/notify', methods=['POST'])
def payment_notify():
    data = request.json
    success = handle_payment_callback(data)
    return jsonify({"success": success})

# ==================== 管理后台 API ====================

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    """管理员：获取系统统计"""
    conn = get_db()
    try:
        total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
        total_gens = conn.execute("SELECT COUNT(*) as c FROM usage_logs").fetchone()['c']
        # 模拟收入 (实际应从 orders 表查询)
        total_revenue = 0 
        
        return jsonify({
            "success": True,
            "total_users": total_users,
            "total_generations": total_gens,
            "total_revenue": total_revenue
        })
    finally:
        conn.close()

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_users():
    """管理员：获取用户列表"""
    conn = get_db()
    try:
        users = conn.execute('''
            SELECT u.id, u.username, u.email, u.role, u.created_at, 
                   s.plan_type, s.daily_limit
            FROM users u
            LEFT JOIN subscriptions s ON u.id = s.user_id
            ORDER BY u.created_at DESC
            LIMIT 100
        ''').fetchall()
        
        result = []
        for u in users:
            result.append({
                "id": u['id'],
                "username": u['username'],
                "email": u['email'],
                "role": u['role'],
                "plan_type": u['plan_type'],
                "daily_limit": u['daily_limit'],
                "created_at": u['created_at']
            })
        
        return jsonify({"success": True, "users": result})
    finally:
        conn.close()

@app.route('/api/admin/users/<int:user_id>/quota', methods=['POST'])
@admin_required
def admin_set_quota(user_id):
    """管理员：手动调整用户额度 (通过修改 subscription)"""
    data = request.json
    new_limit = data.get('daily_limit')
    if new_limit is None:
        return jsonify({"error": "Missing daily_limit"}), 400
    
    conn = get_db()
    try:
        conn.execute(
            "UPDATE subscriptions SET daily_limit = ? WHERE user_id = ?",
            (new_limit, user_id)
        )
        conn.commit()
        return jsonify({"success": True, "message": f"User {user_id} quota set to {new_limit}"})
    finally:
        conn.close()

# ==================== 启动 ====================
if __name__ == '__main__':
    init_db()
    
    # 初始化认证模块（注册Blueprint、创建默认管理员）
    init_auth(app)
    
    # 注册使用量查询API路由
    register_rate_limit_routes(app)
    
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 AI文案工坊 V3.0 启动中...")
    print(f"📍 地址: http://localhost:{port}")
    print(f"🤖 AI模型: {Config.AI_MODEL}")
    print(f"🔐 认证模块: 已加载")
    print(f"⏱  使用量限制: 已加载")
    app.run(host='0.0.0.0', port=port, debug=True)

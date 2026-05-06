#!/usr/bin/env python3
"""
AI文案工坊 - 后端API服务 V2
集成真实AI模型调用（通义千问 / Claude / OpenAI）
"""

from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
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

        -- V4.3 报告存档表
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            drug_name TEXT,
            pass_count TEXT,
            current_price TEXT,
            target TEXT,
            content_markdown TEXT,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- V5.0 医药专业数据库：挂网价格表
        CREATE TABLE IF NOT EXISTS drug_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_code TEXT,
            drug_name TEXT,
            dosage_form TEXT,
            manufacturer TEXT,
            spec TEXT,
            conversion_ratio REAL,
            is_shortage_direct TEXT,
            listing_price REAL,
            province TEXT,
            province_count INTEGER,
            listing_date TEXT,
            first_rise_flag TEXT,
            first_rise_date TEXT,
            follow_rise_flag TEXT,
            follow_rise_date TEXT,
            price_diff_flag TEXT,
            color_warning TEXT,
            risk_handling_date TEXT,
            red_list_price REAL,
            yellow_list_price REAL,
            trading_status TEXT,
            price_formation_mode TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_drug_name ON drug_prices(drug_name);
        CREATE INDEX IF NOT EXISTS idx_province ON drug_prices(province);

        -- 创建索引
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

# ==================== 敏感词过滤系统 ====================
BANNED_WORDS = set()
BANNED_FILE = os.path.join(os.path.dirname(__file__), 'banned_words.txt')
if os.path.exists(BANNED_FILE):
    with open(BANNED_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            word = line.strip()
            if word and not word.startswith('#'):
                BANNED_WORDS.add(word)
    print(f"✅ 已加载 {len(BANNED_WORDS)} 个敏感词拦截项")

def check_sensitive_words(text):
    """检查文本是否包含敏感词，返回命中的词列表"""
    if not BANNED_WORDS: return []
    found = [w for w in BANNED_WORDS if w in text]
    return found

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

@app.route('/admin')
def admin_page():
    """管理后台页面"""
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'admin.html')

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
    
    # V3.3 敏感词拦截 (拦截用户输入 + 补充要求)
    requirements = data.get('requirements', '')
    blocked = check_sensitive_words(topic) + check_sensitive_words(requirements)
    if blocked:
        return jsonify({"error": f"输入包含违规/风险词汇: {', '.join(blocked)}，请修改后重试"}), 400
    
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
    
    # ==================== V3.2 历史记录保存 ====================
    try:
        user_id = None
        
        # 1. 优先从 g.current_user 获取 (如果使用了 login_required)
        if hasattr(g, 'current_user') and g.current_user:
            user_id = g.current_user['user_id']
        else:
            # 2. 否则尝试从 Header 解析 Token (匿名/试用用户可能带了 token)
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                from auth import verify_token
                payload = verify_token(auth_header[7:])
                if payload:
                    user_id = payload.get('user_id')

        # 估算成本 (简单模型: 0.01元/千字)
        cost = len(content) * 0.00001 if content else 0
        
        conn = get_db()
        conn.execute('''
            INSERT INTO generations (
                user_id, topic, scene, style, content, model_used, 
                prompt, status, cost_cny, token_count, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, topic, scene, style, content or '', model,
            prompt, 'success', cost, len(content or ''), request.remote_addr
        ))
        conn.commit()
    except Exception as e:
        print(f"Failed to save history: {e}")
    finally:
        if 'conn' in locals(): conn.close()
    # ==========================================================

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
from payment import create_payment, handle_payment_callback, gateway as payment_gateway

@app.route('/api/payment/wechat', methods=['POST'])
@login_required
def wechat_pay():
    """创建微信支付订单"""
    user_id = g.current_user['user_id']
    data = request.json
    product = data.get('product', 'pro_monthly')
    result = create_payment(user_id, product, 'wechat')
    return jsonify({"success": True, "data": result})

@app.route('/api/payment/alipay', methods=['POST'])
@login_required
def alipay_pay():
    """创建支付宝订单"""
    user_id = g.current_user['user_id']
    data = request.json
    product = data.get('product', 'pro_monthly')
    result = create_payment(user_id, product, 'alipay')
    return jsonify({"success": True, "data": result})

@app.route('/api/payment/status', methods=['GET'])
@login_required
def payment_status():
    """查询订单状态 (供前端轮询)"""
    order_no = request.args.get('order_no')
    if not order_no:
        return jsonify({"error": "Missing order_no"}), 400
    
    status = payment_gateway.check_order_status(order_no)
    return jsonify(status)

@app.route('/api/payment/history', methods=['GET'])
@login_required
def payment_history():
    """用户订单历史"""
    user_id = g.current_user['user_id']
    orders = payment_gateway.get_user_orders(user_id)
    return jsonify({"success": True, "orders": orders})

@app.route('/api/payment/simulate', methods=['POST'])
def payment_simulate():
    """
    [内部/测试接口] 模拟支付成功回调
    真实场景下，这是由微信/支付宝服务器调用的 Notify URL
    """
    data = request.json
    order_no = data.get('order_no')
    if not order_no:
        return jsonify({"error": "Missing order_no"}), 400
        
    success = handle_payment_callback({
        "order_no": order_no,
        "transaction_id": "MOCK_" + str(int(time.time()))
    })
    
    if success:
        return jsonify({"success": True, "message": "Payment simulated successfully"})
    return jsonify({"success": False, "error": "Callback failed"}), 400

@app.route('/api/payment/notify', methods=['POST'])
def payment_notify():
    """真实环境的 Webhook 回调接口"""
    data = request.json
    success = handle_payment_callback(data)
    return jsonify({"success": success})

# ==================== 历史记录模块 V3.2 ====================

@app.route('/api/history', methods=['GET'])
@login_required
def get_history():
    """获取当前用户的历史生成记录"""
    user_id = g.current_user['user_id']
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    offset = (page - 1) * limit
    
    # 时间范围过滤 (可选)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = "SELECT id, topic as title, scene, model_used, content, cost_cny, created_at FROM generations WHERE user_id = ?"
    params = [user_id]
    
    if start_date:
        query += " AND created_at >= ?"
        params.append(start_date)
    if end_date:
        query += " AND created_at <= ?"
        params.append(end_date)
        
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    # 查询总数
    count_query = "SELECT count(*) as c FROM generations WHERE user_id = ?"
    count_params = [user_id]
    if start_date:
        count_query += " AND created_at >= ?"
        count_params.append(start_date)
    if end_date:
        count_query += " AND created_at <= ?"
        count_params.append(end_date)

    conn = get_db()
    try:
        rows = conn.execute(query, params).fetchall()
        total = conn.execute(count_query, count_params).fetchone()['c']
        
        items = []
        for r in rows:
            items.append({
                "id": r['id'],
                "title": r['title'],
                "scene": r['scene'],
                "model": r['model_used'],
                "content_preview": r['content'][:100] + "..." if len(r['content']) > 100 else r['content'],
                "content_full": r['content'],
                "cost": round(r['cost_cny'], 4),
                "created_at": r['created_at']
            })
            
        return jsonify({
            "success": True,
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        })
    finally:
        conn.close()

@app.route('/api/history/<int:id>', methods=['DELETE'])
@login_required
def delete_history(id):
    """删除历史记录"""
    user_id = g.current_user['user_id']
    conn = get_db()
    try:
        # Ensure user can only delete their own
        conn.execute("DELETE FROM generations WHERE id = ? AND user_id = ?", (id, user_id))
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

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

# ==================== V4.3 医药顾问 Agent (智能决策引擎) ====================
AGENT_SESSIONS = {}

# 核心业务规则库：基于 20 年集采经验的量化逻辑
VBP_RULES = """
【集采竞争与降价铁律 (内部绝密)】
1. **过评企业数 (N) 定义竞争烈度**:
   - N ≤ 2 家：温和竞争。降幅通常控制在 20%-40%。策略空间大，可保利润。
   - 3 ≤ N ≤ 6 家：中等竞争。降幅通常在 50%-70%。需精细测算，保量保利需取舍。
   - N > 6 家：极度红海。降幅通常 > 80%，极易触发"价格熔断"（如降幅未达标则出局）。
2. **熔断与淘汰机制**:
   - 若报价高于"最高有效申报价"的一定比例（如 1.8 倍），直接淘汰。
   - 若降幅未达到规定阈值（如 50%），可能无法获得拟中选资格。
3. **企业策略建议**:
   - 保份额（走量）：在红海中必须贴近成本线报价，甚至微亏换市场（清洗中小对手）。
   - 保利润（高价）：仅在独家或 N≤2 的蓝海品种中可行。在红海中报高价等于自杀。
"""

def run_vbp_agent_logic(session_data, user_input):
    """
    V5.0 核心逻辑：基于 LLM + 真实数据库的动态意图识别
    """
    import requests
    
    # 定义需要收集的字段
    REQUIRED_FIELDS = {
        "drug_name": "药品通用名",
        "pass_count": "过评企业数量",
        "current_price": "省级挂网价",
        "target": "投标核心目标（保利润/保份额）"
    }
    
    # 【V5.0 新增】自动查库逻辑：当用户提到药品名时，立即查询真实挂网数据
    db_context = ""
    drug_name = session_data.get('drug_name', '')
    
    # 如果已有药品名，或当前输入包含药品名特征，尝试查库
    if drug_name or any(kw in user_input for kw in ['胶囊', '片剂', '颗粒', '注射液']):
        query_name = drug_name if drug_name else user_input
        try:
            # 调用本地数据库 API
            res = requests.post('http://localhost:5000/api/v5/drug_price/query', 
                               json={"drug_name": query_name}, timeout=3)
            if res.status_code == 200:
                data = res.json()
                if data.get('success') and data.get('count', 0) > 0:
                    records = data['data'][:5]  # 取前 5 条
                    # 提取关键信息
                    prices = [r['listing_price'] for r in records if r['listing_price']]
                    min_price = min(prices) if prices else 0
                    max_price = max(prices) if prices else 0
                    avg_price = sum(prices)/len(prices) if prices else 0
                    provinces = list(set([r['province'] for r in records]))
                    
                    db_context = f"""
【📊 真实数据库查询结果】
- 查询品种：{query_name}
- 找到记录：{data['count']} 条
- 价格区间：{min_price:.2f} 元 ~ {max_price:.2f} 元
- 平均挂网价：{avg_price:.2f} 元
- 覆盖省份：{', '.join(provinces[:5])}
- 竞争提示：数据库中已有 {len(records)} 条有效报价记录
"""
                    # 自动填充 session_data
                    if not session_data.get('current_price') and avg_price:
                        session_data['current_price'] = f"{avg_price:.2f}"
        except Exception as e:
            print(f"[DB Query Error] {e}")
            db_context = "【数据库查询失败，使用用户输入数据】"
    
    # 构建 Prompt，注入业务规则 + 真实数据
    prompt = f"""
你是一位拥有 20 年实战经验的中国医药集采策略专家。
你正在引导一位客户完成《集采投标策略报告》的咨询。

【集采铁律 (必须遵守的底层逻辑)】
{VBP_RULES}

{db_context}

【当前已知信息】
{json.dumps(session_data, ensure_ascii=False, indent=2)}

【客户最新输入】
"{user_input}"

【任务要求】
1. **信息提取**：提取 `drug_name`, `pass_count`, `current_price`, `target`。
2. **逻辑校验**：
   - 如果用户输入了 `pass_count` 和 `target`，必须对比上述铁律。
   - 例如：若 `pass_count` > 6 且 `target` 是 "保利润"，必须在 `tip` 中发出**红色预警**："竞争极其惨烈，保利润策略风险极高，极大概率出局！"
3. **下一步决策 (status)**：
   - 4 个字段齐全 -> "REPORT"
   - 缺 `drug_name` -> "ASK_drug_name"
   - 缺 `pass_count` -> "ASK_pass_count"
   - 缺 `current_price` -> "ASK_current_price"
   - 缺 `target` -> "ASK_target"
4. **生成回复**：确认收到信息，提出下一个问题。语气干练、专业。**如果查到了真实数据，必须在回复中引用真实价格区间**。

【输出格式】
严格返回 JSON 格式：
{{
  "updated_data": {{ "pass_count": 5, ... }},
  "reply": "收到，过评数 5 家属于中等竞争...",
  "tip": "逻辑依据：5 家过评通常面临 50%-70% 的降幅压力...",
  "status": "当前状态代码"
}}
"""
    
    try:
        ai_response = call_ai_model(prompt, model='deepseek')
        
        import re
        match = re.search(r'```json\s*(.*?)\s*```', ai_response, re.DOTALL)
        if not match:
            match = re.search(r'(\{.*\})', ai_response, re.DOTALL)
            
        if match:
            result = json.loads(match.group(1))
            new_data = result.get('updated_data', {})
            for k, v in new_data.items():
                if v and v != "null" and v != "":
                    session_data[k] = v
            return result
        else:
            raise ValueError("AI 未返回 JSON")
    except Exception as e:
        print(f"[Agent Error] {e}")
        return {
            "updated_data": {},
            "reply": "收到，请继续。",
            "tip": "系统正在处理中...",
            "status": "CONTINUE"
        }

def get_flowchart_by_status(status):
    """根据状态动态生成流程图 Mermaid 代码"""
    c1 = "#00b894" # done
    c2 = "#6c5ce7" # active
    c3 = "#3a3a4a" # wait
    
    # 默认全灰
    colors = [c3, c3, c3, c3]
    
    if "ASK_pass_count" in status:
        colors = [c1, c2, c3, c3] # 信息收集 done, 竞品分析 active
    elif "ASK_current_price" in status:
        colors = [c1, c1, c2, c3] # 信息+竞品 done, 价格沙盘 active
    elif "ASK_target" in status:
        colors = [c1, c1, c2, c3] # 价格 active
    elif "REPORT" in status:
        colors = [c1, c1, c1, c2] # 全 done, 报告 active
    elif "ASK_drug_name" in status:
        colors = [c2, c3, c3, c3] # 只有信息收集 active
    
    return f"""graph LR
    A[品种定位] --> B[竞品画像]
    B --> C[价格沙盘]
    C --> D[决策报告]
    style A fill:{colors[0]},stroke:#fff,stroke-width:2px
    style B fill:{colors[1]},stroke:#fff,stroke-width:2px
    style C fill:{colors[2]},stroke:#fff,stroke-width:2px
    style D fill:{colors[3]},stroke:#fff,stroke-width:2px"""

def generate_vbp_report_v4(data):
    """V5.0 生成深度报告 - 基于真实数据库 + 铁律"""
    import requests
    
    drug = data.get('drug_name', '未知')
    pass_count = data.get('pass_count', '未提供')
    price = data.get('current_price', '未提供')
    target = data.get('target', '未提供')
    
    # 【V5.0 新增】生成报告前再次查库，确保数据最新
    db_summary = ""
    try:
        res = requests.post('http://localhost:5000/api/v5/drug_price/query', 
                           json={"drug_name": drug}, timeout=3)
        if res.status_code == 200:
            db_data = res.json()
            if db_data.get('success') and db_data.get('count', 0) > 0:
                records = db_data['data']
                prices = [r['listing_price'] for r in records if r['listing_price']]
                db_summary = f"""
【真实数据支撑】
- 数据库中共有 {db_data['count']} 条该品种挂网记录
- 全国价格区间：{min(prices):.2f} 元 ~ {max(prices):.2f} 元
- 建议报价参考：{min(prices)*0.8:.2f} 元 ~ {min(prices)*0.9:.2f} 元（通常集采降幅为挂网价的 10%-20%）
"""
    except:
        db_summary = "【数据库查询超时，基于用户输入数据分析】"
    
    prompt = f"""
作为集采专家，请基于以下核心数据和**真实数据库**生成最终决策报告：
- 品种：{drug}
- 竞争：过评数 {pass_count}
- 价格：{price} 元
- 目标：{target}

{db_summary}

【内部铁律】
{VBP_RULES}

报告要求：
1. **包含 Mermaid 饼图**：分析原研与仿制的市场份额。
2. **竞争格局研判**：必须根据铁律判断当前烈度（如红海/蓝海），并结合铁律给出分析。
3. **报价方案表**：
   - 如果 `pass_count` > 6，必须提示极高风险，建议贴近成本报价。
   - 如果 `pass_count` <= 2，策略空间大。
4. **必须引用真实数据**：如果查到了数据库价格，必须在报告中明确写出"根据数据库，该品种全国挂网价区间为 XX-XX 元"。
5. 输出格式要专业、严谨。
"""
    
    content = call_ai_model(prompt, model='deepseek')
    return f"""
### 📄 {drug} 集采投标策略决策报告 (V5.0 数据增强版)

{content}

---
*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*
*数据来源：医药专业数据库 ({db_data.get('count', 0) if 'db_data' in locals() else 0} 条记录)*
    """

@app.route('/api/vbp_chat', methods=['POST'])
def vbp_chat():
    """V4.3 智能对话接口"""
    data = request.json
    session_id = data.get('session_id', 'default')
    user_input = data.get('user_input', '')
    
    if session_id not in AGENT_SESSIONS:
        AGENT_SESSIONS[session_id] = {"data": {}}
    
    session = AGENT_SESSIONS[session_id]
    
    # 1. 运行 Agent 逻辑 (意图识别 + 数据提取 + 回复生成)
    result = run_vbp_agent_logic(session['data'], user_input)
    
    status = result.get('status', 'CONTINUE')
    reply = result.get('reply', '收到。')
    tip = result.get('tip', '')
    
    # 2. 处理报告生成
    report_content = None
    if status == 'REPORT':
        report_content = generate_vbp_report_v4(session['data'])
        reply += "\n\n**报告已生成，请查看右侧面板。**"
        tip = "所有关键信息已收集完毕，系统正在生成深度决策建议。"
    
    return jsonify({
        "success": True,
        "reply": reply,
        "tip": tip,
        "report": report_content,
        "flowchart": get_flowchart_by_status(status),
        "status_text": "报告生成中" if status == 'REPORT' else "分析中..."
    })

# ==================== V4.3 报告存档与导出 ====================
@app.route('/api/reports/save', methods=['POST'])
def save_report():
    """保存生成的报告到数据库"""
    data = request.json
    report_content = data.get('content')
    drug_name = data.get('drug_name', '未知')
    meta = data.get('meta', {})
    
    if not report_content:
        return jsonify({"error": "报告内容为空"}), 400

    try:
        conn = get_db()
        cursor = conn.execute('''
            INSERT INTO reports (drug_name, pass_count, current_price, target, content_markdown)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            drug_name, 
            meta.get('pass_count'), 
            meta.get('current_price'), 
            meta.get('target'),
            report_content
        ))
        report_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"success": True, "id": report_id, "message": "报告已存档"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reports/list', methods=['GET'])
def list_reports():
    """获取报告历史列表"""
    try:
        conn = get_db()
        rows = conn.execute('SELECT id, drug_name, target, created_at FROM reports ORDER BY created_at DESC').fetchall()
        conn.close()
        
        reports = []
        for r in rows:
            reports.append({
                "id": r['id'],
                "title": f"{r['drug_name']} 集采决策报告",
                "target": r['target'],
                "date": r['created_at']
            })
        return jsonify({"success": True, "reports": reports})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== V5.0 医药专业数据库 API ====================
@app.route('/api/v5/drug_price/query', methods=['POST'])
def query_drug_price():
    """V5.0 核心接口：查询真实挂网价格数据"""
    data = request.json
    drug_name = data.get('drug_name')
    province = data.get('province')
    
    if not drug_name:
        return jsonify({"error": "请提供药品名称"}), 400

    try:
        conn = get_db()
        query = "SELECT * FROM drug_prices WHERE drug_name LIKE ?"
        params = [f"%{drug_name}%"]
        
        if province:
            query += " AND province = ?"
            params.append(province)
            
        query += " ORDER BY listing_price ASC"
        
        rows = conn.execute(query, params).fetchall()
        conn.close()
        
        results = []
        for r in rows:
            results.append({
                "drug_name": r['drug_name'],
                "dosage_form": r['dosage_form'],
                "manufacturer": r['manufacturer'],
                "spec": r['spec'],
                "listing_price": r['listing_price'],
                "province": r['province'],
                "price_diff_flag": r['price_diff_flag'],
                "color_warning": r['color_warning'],
                "trading_status": r['trading_status'],
                "listing_date": r['listing_date']
            })
            
        return jsonify({"success": True, "data": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v5/drug_price/seed', methods=['POST'])
def seed_drug_data():
    """测试接口：注入模拟数据，验证功能"""
    mock_data = [
        ("8697000100001", "阿莫西林胶囊", "胶囊剂", "白云山制药", "0.25g*24s", 1.0, "否", 5.50, "江苏省", 28, "2024-10-01", "是", "2024-09-01", "否", None, "↑", "黄色", "2024-10-05", 8.00, 6.50, "活跃区", "1.国家集采"),
        ("8697000100001", "阿莫西林胶囊", "胶囊剂", "白云山制药", "0.25g*24s", 1.0, "否", 4.80, "浙江省", 28, "2024-10-15", "否", None, "是", "2024-10-10", "↑↑", "红色", "2024-10-16", 8.00, 6.50, "活跃区", "5.普通挂网"),
        ("8697000200002", "阿托伐他汀钙片", "片剂", "辉瑞制药", "20mg*7s", 1.0, "否", 12.50, "广东省", 15, "2023-05-20", "否", None, "否", None, "-", "绿色", None, 15.00, 13.50, "不活跃区", "4.国谈")
    ]
    
    try:
        conn = get_db()
        # 先清空旧测试数据
        conn.execute("DELETE FROM drug_prices WHERE drug_name IN ('阿莫西林胶囊', '阿托伐他汀钙片')")
        
        conn.executemany('''
            INSERT INTO drug_prices (drug_code, drug_name, dosage_form, manufacturer, spec, conversion_ratio, 
                                     is_shortage_direct, listing_price, province, province_count, listing_date, 
                                     first_rise_flag, first_rise_date, follow_rise_flag, follow_rise_date, 
                                     price_diff_flag, color_warning, risk_handling_date, red_list_price, 
                                     yellow_list_price, trading_status, price_formation_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', mock_data)
        
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"已注入 {len(mock_data)} 条测试数据"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== 启动 ====================
if __name__ == '__main__':
    init_db()
    
    # 启用 CORS（允许跨域请求）
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 初始化认证模块（注册 Blueprint、创建默认管理员）
    init_auth(app)
    
    # 注册使用量查询API路由
    register_rate_limit_routes(app)
    
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 AI 文案工坊 V5.0 (医药顾问模式) 启动中...")
    print(f"📍 地址：http://localhost:{port}")
    print(f"🤖 AI 模型：{Config.AI_MODEL}")
    print(f"🔐 认证模块：已加载")
    print(f"⏱  使用量限制：已加载")
    # 关闭 debug 模式，使用稳定的 production 模式
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

#!/usr/bin/env python3
"""
AI文案工坊 - 后端API服务
Flask + AI API集成
"""

from flask import Flask, request, jsonify
import os
import json
import time
from datetime import datetime

app = Flask(__name__)

# 配置
API_KEY = os.getenv('AI_API_KEY', '')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///wenyan.db')

# 模拟用户数据库
users = {}
generation_logs = []

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/api/generate', methods=['POST'])
def generate_copy():
    """AI文案生成接口"""
    data = request.json
    if not data or 'topic' not in data:
        return jsonify({"error": "缺少主题参数"}), 400
    
    topic = data['topic']
    scene = data.get('scene', 'xiaohongshu')
    style = data.get('style', '热情种草')
    length = data.get('length', '中')
    
    # 调用AI模型生成（接入真实API）
    result = call_ai_api(topic, scene, style, length)
    
    # 记录日志
    generation_logs.append({
        "topic": topic,
        "scene": scene,
        "timestamp": datetime.now().isoformat(),
        "length": len(result.get('content', ''))
    })
    
    return jsonify(result)

@app.route('/api/user/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "缺少用户名或密码"}), 400
    
    if username in users:
        return jsonify({"error": "用户名已存在"}), 409
    
    user_id = f"user_{int(time.time())}"
    users[username] = {
        "id": user_id,
        "username": username,
        "plan": "free",  # free / pro
        "free_generations_left": 10,
        "created_at": datetime.now().isoformat()
    }
    
    return jsonify({
        "user_id": user_id,
        "username": username,
        "plan": "free",
        "free_generations_left": 10
    })

@app.route('/api/user/upgrade', methods=['POST'])
def upgrade():
    """升级PRO版"""
    data = request.json
    username = data.get('username')
    payment_token = data.get('payment_token')
    
    if not username:
        return jsonify({"error": "缺少用户名"}), 400
    
    if username not in users:
        return jsonify({"error": "用户不存在"}), 404
    
    # 验证支付（接入真实支付接口）
    if verify_payment(payment_token):
        users[username]['plan'] = 'pro'
        users[username]['free_generations_left'] = -1  # -1 = unlimited
        return jsonify({"status": "upgraded", "plan": "pro"})
    
    return jsonify({"error": "支付验证失败"}), 402

def call_ai_api(topic, scene, style, length):
    """调用AI API生成文案"""
    # 接入真实AI模型（Claude, GPT, 通义千问等）
    # 这里提供接口框架，实际调用时替换
    
    prompt = build_prompt(topic, scene, style, length)
    
    # TODO: 接入真实API
    # headers = {"Authorization": f"Bearer {API_KEY}"}
    # response = requests.post("https://api.openai.com/v1/chat/completions", json={
    #     "model": "gpt-4",
    #     "messages": [{"role": "user", "content": prompt}]
    # })
    
    # 模拟返回
    return {
        "content": f"【{topic}】\n\n这是AI生成的{style}风格文案...\n（接入真实API后替换此处）",
        "scene": scene,
        "style": style,
        "word_count": 150,
        "generation_time": 0.5
    }

def build_prompt(topic, scene, style, length):
    """构建AI提示词"""
    scene_prompts = {
        "xiaohongshu": "写一篇小红书风格的种草文案",
        "pengyouquan": "写一篇朋友圈分享文案",
        "dianshang": "写一篇电商商品描述",
        "biaoti": "生成10个爆款标题",
        "gongzhonghao": "写一篇公众号文章大纲和开头",
        "shipin": "写一个短视频脚本",
        "yingxiao": "写一段营销话术",
        "riji": "写一篇文艺风格的日记"
    }
    
    base_prompt = scene_prompts.get(scene, "写一篇文案")
    return f"{base_prompt}\n主题：{topic}\n风格：{style}\n长度：{length}"

def verify_payment(token):
    """验证支付"""
    # TODO: 接入真实支付验证（微信/支付宝/Stripe）
    return token and token.startswith("pay_")

@app.route('/api/stats', methods=['GET'])
def get_stats():
    return jsonify({
        "total_generations": len(generation_logs),
        "total_users": len(users),
        "pro_users": sum(1 for u in users.values() if u['plan'] == 'pro')
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

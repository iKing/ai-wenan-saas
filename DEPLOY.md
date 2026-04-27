# AI文案工坊 - 部署指南

## 快速启动

### 1. 本地开发
```bash
cd ai-wenan-backend
pip install flask requests
python app.py
# 服务运行在 http://localhost:5000
```

### 2. Docker部署
```bash
docker-compose up -d
```

### 3. 生产部署（推荐）
```bash
# 设置环境变量
export AI_API_KEY="your-api-key"
export DATABASE_URL="postgresql://user:pass@host/db"

# 启动
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## API接口

### 生成文案
```
POST /api/generate
Content-Type: application/json

{
  "topic": "夏日防晒",
  "scene": "xiaohongshu",
  "style": "热情种草",
  "length": "中"
}
```

### 用户注册
```
POST /api/user/register
{
  "username": "user123",
  "password": "pass123"
}
```

### 升级PRO
```
POST /api/user/upgrade
{
  "username": "user123",
  "payment_token": "pay_xxx"
}
```

## 接入AI模型

在 `app.py` 中替换 `call_ai_api` 函数：

### 通义千问
```python
import dashscope
dashscope.api_key = API_KEY
response = dashscope.Generation.call(
    model='qwen-plus',
    prompt=prompt
)
```

### OpenAI
```python
import openai
client = openai.OpenAI(api_key=API_KEY)
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}]
)
```

### Claude
```python
import anthropic
client = anthropic.Anthropic(api_key=API_KEY)
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1000,
    messages=[{"role": "user", "content": prompt}]
)
```

## 部署平台

| 平台 | 命令 | 说明 |
|------|------|------|
| Vercel | `vercel deploy` | 免费，自动HTTPS |
| Render | 连接GitHub自动部署 | 免费额度 |
| Railway | `railway up` | $5/月起 |
| 阿里云 | 宝塔面板部署 | 国内访问快 |

# AI文案工坊 — 系统架构文档

> **版本**: V2 · **最后更新**: 2026-04-28  
> **项目路径**: `/home/admin/ai-wenan-backend/`  
> **维护**: AI文案工坊开发团队

---

## 目录

1. [系统概述](#1-系统概述)
2. [技术栈](#2-技术栈)
3. [系统架构图](#3-系统架构图)
4. [部署拓扑图](#4-部署拓扑图)
5. [组件说明](#5-组件说明)
6. [数据流](#6-数据流)
7. [数据库设计](#7-数据库设计)
8. [API 端点](#8-api-端点)
9. [AI 模型路由](#9-ai-模型路由)
10. [提示词模板](#10-提示词模板)
11. [安全与限流](#11-安全与限流)
12. [支付模块](#12-支付模块)
13. [前端架构](#13-前端架构)
14. [运维与部署](#14-运维与部署)
15. [环境变量](#15-环境变量)
16. [扩展路线图](#16-扩展路线图)

---

## 1. 系统概述

AI文案工坊是一个基于 Flask 的 AI 文案生成服务，支持多种场景（小红书、朋友圈、电商、公众号等）的文案自动生成。用户通过前端页面输入主题、选择场景和风格，后端调用不同 AI 模型（DeepSeek、通义千问、Claude、OpenAI 等）生成文案并返回。

**核心特性**：
- 🤖 **多模型支持** — 一键切换 DeepSeek / Qwen / Claude / GPT-4o / Token Plan 模型
- 📝 **7 种文案场景** — 小红书、朋友圈、电商、标题、公众号、短视频、营销话术
- 🎨 **5 种写作风格** — 热情种草、专业测评、故事分享、干货教程、幽默搞笑
- 💰 **付费体系** — 免费版每日 10 次限制，PRO/Enterprise 解锁无限使用
- 🌐 **公网访问** — Cloudflare Tunnel 穿透内网

---

## 2. 技术栈

| 层级 | 技术 | 版本/说明 |
|------|------|-----------|
| 运行时 | Python | 3.6.8（CentOS 7 系统自带，限制不可升级） |
| Web 框架 | Flask | 2.0.3 |
| HTTP 客户端 | requests | 2.27.1（因 Python 3.6 限制，所有 AI 调用均使用原始 HTTP 请求） |
| 数据库 | SQLite3 | 内置，轻量级文件数据库 |
| 进程管理 | systemd | aiwenan.service，自动重启 |
| 反向代理 | Nginx | 配置文件已就绪（`nginx.conf`） |
| 网络穿透 | Cloudflare Tunnel | 域名 `acrobat-institutional-hosts-email.trycloudflare.com` |
| 前端 | 原生 HTML/CSS/JS | 单文件 SPA，无框架依赖 |

> **Python 3.6 兼容性约束**：无法使用 `openai`、`dashscope` 等新版 SDK（要求 Python ≥ 3.7）。所有 AI 调用通过 `requests.post()` 直接发送 OpenAI 兼容格式的 HTTP 请求。

---

## 3. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            用户浏览器 / 客户端                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  index.html (SPA)                                                   │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │    │
│  │  │ 场景选择  │  │ 风格选择  │  │ 模型选择  │  │ 主题输入 + 提交   │  │    │
│  │  │ (7种场景) │  │ (5种风格) │  │ (8种模型) │  │ topic ≤ 200字符  │  │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────────────────┘  │    │
│  │                                                                     │    │
│  │  ┌────────────────────────────┐  ┌──────────────────────────────┐   │    │
│  │  │ 结果显示区 + 复制/再生成    │  │ 付费会员升级卡片 (¥9.9/¥79) │   │    │
│  │  │ word_count / 响应时间展示   │  │ 免费版每日10次限制提示       │   │    │
│  │  └────────────────────────────┘  └──────────────────────────────┘   │    │
│  │                                                                     │    │
│  │  离线降级: API不可用时自动使用前端硬编码模板                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ HTTP/JSON
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           网络接入层                                          │
│                                                                             │
│  ┌──────────────────────┐    ┌──────────────────────────────────────────┐   │
│  │  Cloudflare Tunnel   │    │  Nginx (可选, nginx.conf 已就绪)          │   │
│  │  acrobat-...         │    │  ai365.vip / www.ai365.vip               │   │
│  │  trycloudflare.com   │    │  反向代理 → localhost:5000               │   │
│  │  (当前主要入口)       │    │  HTTPS 证书待配置                         │   │
│  └──────────┬───────────┘    └──────────────────┬───────────────────────┘   │
│             │                                   │                           │
│             └───────────────┬───────────────────┘                           │
│                             ▼                                               │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │ 0.0.0.0:5000
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Flask 应用 (app_v2.py)                                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  启动阶段                                                            │   │
│  │  1. 自动加载 ~/.hermes/.env 环境变量                                 │   │
│  │  2. 初始化 SQLite3 数据库 (wenyan.db)                                │   │
│  │  3. 启动 Flask Dev Server (host=0.0.0.0, debug=True)                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────────┐    │
│  │  CORS 中间件     │  │  认证中间件       │  │  配置类 Config         │    │
│  │  after_request   │  │  require_api_key │  │  环境变量读取           │    │
│  │  允许所有来源     │  │  (X-API-Key头)   │  │  AI_MODEL / API_KEYs   │    │
│  └────────┬─────────┘  └────────┬─────────┘  └────────────┬───────────┘    │
│           │                     │                         │                 │
│  ┌────────▼─────────────────────▼─────────────────────────▼───────────┐    │
│  │                        API 路由层                                    │    │
│  │                                                                    │    │
│  │  GET  /                    → 返回 index.html                        │    │
│  │  GET  /api/health          → 返回状态 + 当前模型                     │    │
│  │  POST /api/generate        → 文案生成核心接口                        │    │    │
│  │  POST /api/user/register   → 用户注册                               │    │
│  │  GET  /api/user/usage      → 查询当日使用次数                       │    │
│  │  GET  /api/stats           → 全局统计                               │    │
│  │  POST /api/payment/wechat  → 微信支付（桩）                          │    │
│  │  POST /api/payment/alipay  → 支付宝（桩）                            │    │
│  └───────────────────────────┬────────────────────────────────────────┘    │
│                               │                                            │
│  ┌────────────────────────────▼────────────────────────────────────────┐   │
│  │                    提示词模板引擎 (PROMPTS)                           │   │
│  │                                                                    │   │
│  │  xiaohongshu   → 小红书种草文案 (emoji + 闺蜜语气 + 话题标签)         │   │
│  │  pengyouquan   → 朋友圈文案 (100字以内 + 配图友好)                    │   │
│  │  dianshang     → 电商商品描述 (卖点突出 + 促销信息)                    │   │
│  │  biaoti        → 爆款标题生成 (10个 + 多风格覆盖)                     │   │
│  │  gongzhonghao  → 公众号文章大纲 (5-6部分 + 开头段落)                   │   │
│  │  shipin        → 短视频脚本 (30-60秒 + 分镜 + BGM)                    │   │
│  │  yingxiao      → 营销话术 (预热/开售/逼单三阶段)                      │   │
│  └───────────────────────────┬────────────────────────────────────────┘   │
│                               │                                            │
│  ┌────────────────────────────▼────────────────────────────────────────┐   │
│  │                    AI 模型路由 (call_ai_model)                        │   │
│  │                                                                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │   │
│  │  │ deepseek │  │  qwen    │  │ template │  │  token-plan-*      │  │   │
│  │  │ (HTTP)   │  │ (HTTP)   │  │ (本地)   │  │  (阿里云 MaaS)     │  │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────────────────┘  │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                          │   │
│  │  │ claude   │  │ openai   │  │ (SDK调用) │                         │   │
│  │  │ (SDK)    │  │ (SDK)    │  │ fallback │                          │   │
│  │  └──────────┘  └──────────┘  └──────────┘                          │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                            │
│  ┌────────────────────────────▼────────────────────────────────────────┐   │
│  │                    SQLite3 数据层                                    │   │
│  │                                                                    │   │
│  │  wenyan.db                                                         │   │
│  │  ├── users          (用户表: 用户名/密码/会员计划)                   │   │
│  │  ├── generations    (生成记录: 主题/场景/风格/内容/时间)             │   │
│  │  └── daily_usage    (每日用量: 用户ID/日期/次数)                     │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         外部 AI 服务                                          │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────────────┐  │
│  │  DeepSeek       │  │  阿里云 DashScope│  │  阿里云 MaaS (Token Plan)  │  │
│  │  api.deepseek.com│  │  dashscope.aliyunc│  │  自定义 base_url         │  │
│  │  /v1/chat/      │  │  ncs.com/        │  │  /chat/completions         │  │
│  │  completions    │  │  compatible-mode │  │  模型: qwen3.6-plus/       │  │
│  │  模型: deepseek │  │  模型: qwen-plus │  │       glm-5/MiniMax-M2.5   │  │
│  │  -chat          │  │                  │  │                            │  │
│  └─────────────────┘  └─────────────────┘  └────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                                  │
│  │  Anthropic      │  │  OpenAI          │                                  │
│  │  Claude Sonnet 4│  │  api.openai.com │                                  │
│  │  (SDK调用)      │  │  /v1 (SDK调用)  │                                  │
│  │                 │  │  模型: gpt-4o    │                                  │
│  └─────────────────┘  └─────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 部署拓扑图

```
                    ┌─────────────────────┐
                    │    公网用户          │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
     ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
     │ Cloudflare  │  │ Nginx 80     │  │ 直接访问     │
     │ Tunnel      │  │ ai365.vip    │  │ 5000端口     │
     │ (当前主入口) │  │ (待启用)     │  │ (开发调试)   │
     └──────┬──────┘  └──────┬───────┘  └──────┬───────┘
            │                │                 │
            └────────────────┼─────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │    VPS / 云服务器             │
              │    CentOS 7                  │
              │                              │
              │  ┌────────────────────────┐  │
              │  │  aiwenan.service       │  │
              │  │  (systemd)             │  │
              │  │  User: admin           │  │
              │  │  RestartSec: 5s        │  │
              │  │  WorkingDir:           │  │
              │  │   /home/admin/         │  │
              │  │   ai-wenan-backend     │  │
              │  └──────────┬─────────────┘  │
              │             │                │
              │  ┌──────────▼─────────────┐  │
              │  │  venv/                 │  │
              │  │  Python 3.6.8          │  │
              │  │  Flask 2.0.3           │  │
              │  │  requests 2.27.1       │  │
              │  │  urllib3 1.26.20       │  │
              │  └──────────┬─────────────┘  │
              │             │                │
              │  ┌──────────▼─────────────┐  │
              │  │  app_v2.py             │  │
              │  │  端口: 5000            │  │
              │  │  host: 0.0.0.0         │  │
              │  └──────────┬─────────────┘  │
              │             │                │
              │  ┌──────────▼─────────────┐  │
              │  │  wenyan.db (SQLite)    │  │
              │  │  prompt_templates/     │  │
              │  │  index.html            │  │
              │  └────────────────────────┘  │
              │                              │
              │  环境变量: ~/.hermes/.env    │
              └──────────────────────────────┘
```

---

## 5. 组件说明

### 5.1 核心后端文件

| 文件 | 路径 | 职责 |
|------|------|------|
| `app_v2.py` | `/home/admin/ai-wenan-backend/` | 主服务入口，包含 Flask 应用、API 路由、AI 调用、数据库初始化、提示词模板 |
| `payment.py` | 同上 | 支付模块（桩），模拟微信支付/支付宝订单创建与回调 |
| `index.html` | 同上 | 前端单页应用（SPA），所有 UI/JS/CSS 集成在单文件中 |
| `nginx.conf` | 同上 | Nginx 反向代理配置（已就绪，待域名 + SSL 证书） |
| `expert_access_strategy.py` | `prompt_templates/` | 医药准入专家模式专用提示词模板（独立模块） |

### 5.2 辅助组件

| 组件 | 说明 |
|------|------|
| `wenyan.db` | SQLite3 数据库，存储用户、生成记录和每日用量 |
| `venv/` | Python 3.6 虚拟环境，隔离依赖 |
| `aiwenan.service` | systemd 单元文件，保障服务常驻和自动重启 |
| `~/.hermes/.env` | 环境变量文件，包含所有 API Key 和配置 |

### 5.3 Flask 应用结构

```
app_v2.py
├── 自动加载 .env 环境变量
├── Flask 应用初始化 (static_folder='/home/admin')
├── CORS 中间件 (after_request)
├── Config 类 (环境变量驱动配置)
├── 数据库层
│   ├── get_db() — 获取 SQLite 连接
│   ├── init_db() — 创建三张表 (users, generations, daily_usage)
├── 认证中间件
│   └── require_api_key — 装饰器，校验 X-API-Key
├── AI 调用层
│   ├── call_ai_model() — 统一路由
│   ├── _template_mode() — 本地模板兜底
│   ├── call_token_plan() — Token Plan (HTTP)
│   ├── call_qwen() — 通义千问 (HTTP)
│   ├── call_claude() — Claude (SDK)
│   ├── call_openai() — OpenAI (SDK)
│   ├── call_deepseek() — DeepSeek (HTTP)
│   └── _call_openai_compatible() — 通用兼容接口
├── 提示词模板 (PROMPTS dict, 7种场景)
├── API 路由 (6个端点)
└── 启动入口 (__main__)
```

---

## 6. 数据流

### 6.1 文案生成请求流程

```
用户浏览器
    │
    │ 1. 输入主题 "夏日防晒"，选择场景 "xiaohongshu"，风格 "热情种草"，模型 "deepseek"
    │
    ▼
POST /api/generate
    │
    │ 2. 校验: topic 非空、≤200 字符
    │ 3. 白名单: scene ∈ [xiaohongshu, pengyouquan, dianshang, ...]
    │ 4. 白名单: model ∈ [deepseek, qwen, claude, openai, template,
    │                     token-plan-qwen, token-plan-glm, token-plan-minimax]
    │
    ▼
PROMPTS[scene].format(topic, style)
    │
    │ 5. 构建提示词:
    │    "请写一篇小红书风格的种草文案。
    │     要求：使用emoji... 主题：夏日防晒 风格：热情种草"
    │
    ▼
call_ai_model(prompt, model='deepseek')
    │
    │ 6. 模型路由: model == 'deepseek' → call_deepseek(prompt)
    │
    ▼
requests.post(
    url='https://api.deepseek.com/v1/chat/completions',
    headers={'Authorization': 'Bearer <DEEPSEEK_API_KEY>'},
    json={'model': 'deepseek-chat', 'messages': [{'role':'user','content': prompt}]}
)
    │
    │ 7. 等待响应 (timeout=60s)
    │ 8. 解析 result['choices'][0]['message']['content']
    │
    ▼
返回 JSON:
{
    "success": true,
    "content": "🌞 夏日防晒必备...",
    "scene": "xiaohongshu",
    "style": "热情种草",
    "word_count": 285,
    "generation_time": 3.42,
    "model": "deepseek"
}
    │
    ▼
浏览器渲染结果 → 用户看到文案
```

### 6.2 前端离线降级流程

```
用户点击 "AI 生成文案"
    │
    │ fetch('/api/generate') ...
    │
    ├─ 成功 → 显示 AI 生成内容
    │
    └─ 失败 (catch) → 前端硬编码模板兜底
         │
         │ "[离线模式] {topic}\n\n✨ 姐妹们！今天必须给你们安利..."
         │
         ▼
         用户仍然看到可用内容（质量较低，但保证了可用性）
```

### 6.3 健康检查流程

```
GET /api/health
    │
    ▼
返回:
{
    "status": "ok",
    "model": "qwen",       ← Config.AI_MODEL 环境变量值
    "timestamp": "2026-04-28T23:00:00"
}
    │
    ▼
前端更新:
  - apiStatus → 🟢 / 🔴
  - statusBadge → "🟢 在线" / "🔴 离线"
  - modelDisplay → 当前模型名
  - modelSelect → 自动选中对应模型
```

---

## 7. 数据库设计

### 7.1 ER 图

```
┌──────────────────────┐       ┌──────────────────────┐       ┌──────────────────────┐
│       users          │       │     generations      │       │     daily_usage      │
├──────────────────────┤       ├──────────────────────┤       ├──────────────────────┤
│ id (PK, AUTOINC)     │──┐    │ id (PK, AUTOINC)     │       │ id (PK, AUTOINC)     │
│ username (UNIQUE)    │  │    │ user_id (FK→users)   │  ┌────│ user_id (FK→users)   │
│ password_hash        │  └───<│ topic                │  │    │ date                 │
│ plan (default: free) │       │ scene                │  │    │ count (default: 0)   │
│ created_at           │       │ style                │  │    └──────────┬───────────┘
└──────────────────────┘       │ content              │  │              │
                               │ created_at           │  │              │
                               └──────────────────────┘  │              │
                                                          │  一对多       │  一对多
                                                          └──────────────┘
```

### 7.2 表结构详情

**users** — 用户表
| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 用户唯一标识 |
| username | TEXT | UNIQUE, NOT NULL | 登录用户名 |
| password_hash | TEXT | NOT NULL | 密码哈希（当前明文存储，待改进） |
| plan | TEXT | DEFAULT 'free' | 会员计划: free / pro_monthly / pro_yearly / enterprise |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 注册时间 |

**generations** — 文案生成记录
| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录唯一标识 |
| user_id | INTEGER | FK → users(id) | 关联用户 |
| topic | TEXT | NOT NULL | 生成主题 |
| scene | TEXT | | 场景类型 |
| style | TEXT | | 写作风格 |
| content | TEXT | | 生成的文案内容 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 生成时间 |

**daily_usage** — 每日用量统计
| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 记录唯一标识 |
| user_id | INTEGER | FK → users(id) | 关联用户 |
| date | TEXT | NOT NULL | 日期 (YYYY-MM-DD) |
| count | INTEGER | DEFAULT 0 | 当日生成次数 |

---

## 8. API 端点

### 8.1 端点总览

| 方法 | 路径 | 说明 | 认证 | 状态 |
|------|------|------|------|------|
| GET | `/` | 返回前端页面 | 无 | ✅ 生产可用 |
| GET | `/api/health` | 健康检查 | 无 | ✅ 生产可用 |
| POST | `/api/generate` | AI 文案生成 | 无（可选） | ✅ 生产可用 |
| POST | `/api/user/register` | 用户注册 | 无 | ⚠️ 密码明文 |
| GET | `/api/user/usage` | 查询当日用量 | 无 | ✅ 生产可用 |
| GET | `/api/stats` | 全局统计 | 无 | ✅ 生产可用 |
| POST | `/api/payment/wechat` | 微信支付 | 无 | 🔧 桩代码 |
| POST | `/api/payment/alipay` | 支付宝 | 无 | 🔧 桩代码 |

### 8.2 POST /api/generate 详解

**请求体**：
```json
{
    "topic": "夏日防晒",          // 必填, ≤200字符
    "scene": "xiaohongshu",       // 可选, 默认 "xiaohongshu"
    "style": "热情种草",           // 可选, 默认 "热情种草"
    "model": "deepseek"           // 可选, 默认 "qwen"
}
```

**合法 scene 值**：`xiaohongshu`, `pengyouquan`, `dianshang`, `biaoti`, `gongzhonghao`, `shipin`, `yingxiao`

**合法 model 值**：`deepseek`, `qwen`, `claude`, `openai`, `template`, `token-plan-qwen`, `token-plan-glm`, `token-plan-minimax`

**响应体 (成功)**：
```json
{
    "success": true,
    "content": "🌞 夏日防晒必备...",
    "scene": "xiaohongshu",
    "style": "热情种草",
    "word_count": 285,
    "generation_time": 3.42,
    "model": "deepseek"
}
```

**响应体 (失败)**：
```json
{
    "error": "缺少主题参数"
}
```
HTTP 状态码: `400` (参数错误) / `401` (缺少 API Key)

---

## 9. AI 模型路由

### 9.1 路由决策树

```
call_ai_model(prompt, model)
    │
    ├── model == 'template'
    │       └→ _template_mode()
    │              └→ 返回硬编码演示文本
    │
    ├── model.startswith('token-plan')
    │       ├── 'token-plan-qwen'  → call_token_plan(model_name="qwen3.6-plus")
    │       ├── 'token-plan-glm'   → call_token_plan(model_name="glm-5")
    │       ├── 'token-plan-minimax'→ call_token_plan(model_name="MiniMax-M2.5")
    │       └→ 默认                → call_token_plan(model_name="qwen3.6-plus")
    │
    ├── model == 'deepseek'
    │       └→ call_deepseek()
    │              └→ POST https://api.deepseek.com/v1/chat/completions
    │                 model: "deepseek-chat" | timeout: 60s
    │
    ├── model == 'qwen'
    │       └→ call_qwen()
    │              └→ POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
    │                 model: "qwen-plus" | timeout: 30s
    │
    ├── model == 'claude'
    │       └→ call_claude()
    │              └→ anthropic SDK | model: "claude-sonnet-4-20250514"
    │
    ├── model == 'openai'
    │       └→ call_openai()
    │              └→ _call_openai_compatible(url="api.openai.com", model="gpt-4o")
    │
    └── 其他 (包括 'AI_MODEL' 环境变量值)
            └→ 默认 → call_qwen()
```

### 9.2 模型对比

| 模型标识 | 实际模型 | 调用方式 | 超时 | 特点 |
|----------|----------|----------|------|------|
| `deepseek` | deepseek-chat | HTTP (requests) | 60s | 高性价比，推荐默认 |
| `qwen` | qwen-plus | HTTP (requests) | 30s | 通义千问，中文能力强 |
| `token-plan-qwen` | qwen3.6-plus | HTTP (requests) | 120s | 阿里云 MaaS 增强版 |
| `token-plan-glm` | glm-5 | HTTP (requests) | 120s | 智谱 GLM-5 |
| `token-plan-minimax` | MiniMax-M2.5 | HTTP (requests) | 120s | MiniMax 极速模型 |
| `claude` | claude-sonnet-4 | anthropic SDK | - | 高质量，需 SDK |
| `openai` | gpt-4o | openai SDK | - | 多模态，需 SDK |
| `template` | — | 本地 | - | 离线兜底 |

> **注意**：`claude` 和 `openai` 使用 SDK 调用，在 Python 3.6 环境下可能不可用（SDK 最低要求通常 ≥ 3.7），会自动 fallback 到模板模式。

---

## 10. 提示词模板

系统内置 7 种场景模板，每个模板通过 `{topic}` 和 `{style}` 占位符动态注入：

| 场景 Key | 名称 | 模板特点 | 输出要求 |
|----------|------|----------|----------|
| `xiaohongshu` | 小红书文案 | emoji + 闺蜜语气 + 话题标签 | 200-400字 |
| `pengyouquan` | 朋友圈文案 | 简短精炼 | ≤100字，适合配图 |
| `dianshang` | 电商描述 | 卖点突出 + 促销信息 | 淘宝/拼多多风格 |
| `biaoti` | 爆款标题 | 悬念式/数字式/痛点式 | 生成 10 个标题 |
| `gongzhonghao` | 公众号文章 | 分 5-6 个部分 | 大纲 + 开头段落 |
| `shipin` | 短视频脚本 | 分镜 + 台词 + BGM | 30-60秒 |
| `yingxiao` | 营销话术 | 预热/开售/逼单三阶段 | 社群/私域发售 |

---

## 11. 安全与限流

### 11.1 当前安全措施

| 措施 | 状态 | 说明 |
|------|------|------|
| 输入校验 | ✅ 已实现 | topic ≤ 200 字符，非空检查 |
| 白名单过滤 | ✅ 已实现 | scene 和 model 参数白名单校验 |
| CORS | ⚠️ 宽松 | 当前允许所有来源 (`*`)，生产环境应限制域名 |
| API Key 认证 | 🔧 未启用 | `require_api_key` 装饰器已定义但未挂载到路由 |
| 密码哈希 | ❌ 未实现 | 用户注册时密码明文存储 |
| SQL 注入 | ✅ 安全 | 使用参数化查询 (`?` 占位符) |

### 11.2 限流机制

- **免费版限制**：每日 10 次生成（`Config.FREE_DAILY_LIMIT`）
- **实现方式**：通过 `daily_usage` 表记录 + `GET /api/user/usage` 查询
- **缺口**：`/api/generate` 当前未执行限流检查，需要接入

### 11.3 安全改进建议

1. **启用 API Key 认证** — 将 `@require_api_key` 挂载到 `/api/generate` 路由
2. **密码哈希** — 使用 `hashlib` 或 `bcrypt` 对密码进行哈希存储
3. **CORS 收紧** — 将 `Access-Control-Allow-Origin` 限制为特定域名
4. **生成限流** — 在 `/api/generate` 中检查 `daily_usage.count < FREE_DAILY_LIMIT`
5. **Rate Limit** — 考虑使用 `flask-limiter` 防止 API 滥用
6. **HTTPS** — 配置 SSL 证书，启用 Nginx HTTPS

---

## 12. 支付模块

### 12.1 模块结构 (`payment.py`)

```
PaymentGateway 类
├── create_order()        创建支付订单 → 返回支付链接/二维码
├── notify_callback()     处理支付回调 → 更新订单状态 + 激活权益
├── check_status()        查询订单状态
└── _activate_benefit()   支付成功后激活会员（当前仅 print）

全局函数
├── create_payment()      对外接口: 用户ID + 产品 + 支付方式
└── handle_payment_callback()  对外接口: 处理第三方回调数据
```

### 12.2 产品定价

| 产品 ID | 名称 | 价格 | 周期 |
|---------|------|------|------|
| `pro_monthly` | PRO 月度 | ¥9.9 | 月 |
| `pro_yearly` | PRO 年度 | ¥79 | 年（立省 ¥40） |
| `enterprise` | 企业版 | ¥99 | 月 |

### 12.3 当前状态

- ⚠️ **桩代码**：订单存储在内存 (`self.orders` dict)，重启丢失
- ⚠️ **未接入路由**：`/api/payment/*` 路由在 `app_v2.py` 中未挂载
- ⚠️ **无真实支付**：返回模拟的支付链接，未对接真实支付网关
- ⚠️ **权益激活为空**：`_activate_benefit()` 仅 print，未更新数据库

---

## 13. 前端架构

### 13.1 技术选型

- **单文件 SPA** — `index.html` 包含全部 HTML + CSS + JS（约 300 行）
- **无框架依赖** — 纯原生 JavaScript (ES6+)
- **响应式设计** — CSS Grid + Flexbox 布局
- **暗色主题** — CSS 变量驱动的暗色 UI

### 13.2 核心功能模块

| 模块 | 函数/逻辑 | 说明 |
|------|-----------|------|
| API 健康检查 | `checkApi()` | 页面加载时调用，更新状态指示器 |
| 文案生成 | `generate()` | POST `/api/generate`，处理 loading/错误/降级 |
| 模型切换 | `switchModel()` | 下拉选择变更时更新模型名显示 |
| 结果复制 | `copyResult()` | 使用 Clipboard API 复制结果文本 |
| Toast 提示 | `showToast()` | 动态创建/销毁提示气泡 |
| 离线降级 | `generate()` catch | API 失败时使用前端硬编码模板 |
| 本地计数 | `localStorage` | 累计生成次数持久化 |

### 13.3 前端离线降级模板

当 API 不可达时，前端使用硬编码的小红书风格模板：
```
[离线模式] {topic}

✨ 姐妹们！今天必须给你们安利{topic}！
之前试了好多都不满意，直到遇到这个真的惊艳到了！
✅ 性价比超高，闭眼入
✅ 效果肉眼可见的好
✅ 已经回购三次了
#{topic} #好物推荐
```

---

## 14. 运维与部署

### 14.1 Systemd 服务配置

**文件**: `/etc/systemd/system/aiwenan.service`

```ini
[Unit]
Description=AI文案工坊 Backend Service
After=network.target

[Service]
Type=simple
User=admin
WorkingDirectory=/home/admin/ai-wenan-backend
Environment="PATH=/home/admin/ai-wenan-backend/venv/bin:/usr/bin"
EnvironmentFile=/home/admin/.hermes/.env
ExecStart=/home/admin/ai-wenan-backend/venv/bin/python app_v2.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**常用运维命令**：
```bash
systemctl start aiwenan          # 启动服务
systemctl stop aiwenan           # 停止服务
systemctl restart aiwenan        # 重启服务
systemctl status aiwenan         # 查看状态
journalctl -u aiwenan -f         # 查看实时日志
systemctl enable aiwenan         # 开机自启
```

### 14.2 启动流程

```
systemd 启动 aiwenan.service
    │
    ▼
1. 加载 EnvironmentFile: ~/.hermes/.env
2. 设置 PATH: venv/bin:/usr/bin
3. 执行: venv/bin/python app_v2.py
    │
    ▼
app_v2.py 启动:
    1. 读取 ~/.hermes/.env → os.environ
    2. 初始化 SQLite3 (wenyan.db)
    3. 创建三张表 (IF NOT EXISTS)
    4. Flask app.run(host='0.0.0.0', port=5000, debug=True)
    │
    ▼
服务就绪 → 监听 0.0.0.0:5000
```

### 14.3 Nginx 配置

**文件**: `/home/admin/ai-wenan-backend/nginx.conf`

- 监听 80 端口，域名 `ai365.vip` / `www.ai365.vip`
- 反向代理到 `http://127.0.0.1:5000`
- 静态资源缓存 7 天
- HTTPS 配置已写好（待 SSL 证书）

### 14.4 Cloudflare Tunnel

当前主要通过 Cloudflare Tunnel 暴露服务到公网，临时域名：
```
https://acrobat-institutional-hosts-email.trycloudflare.com
```

---

## 15. 环境变量

**文件**: `/home/admin/.hermes/.env`

服务启动时自动加载，`app_v2.py` 第 17-28 行解析逻辑：
- 跳过注释行（`#` 开头）
- 按 `key=value` 分割
- 去除引号包裹
- 使用 `os.environ.setdefault()`（不覆盖已存在的变量）

**关键变量**：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `AI_MODEL` | 默认 AI 模型 | `qwen` |
| `DASHSCOPE_API_KEY` | 通义千问 API Key | `''` |
| `CLAUDE_API_KEY` | Claude API Key | `''` |
| `OPENAI_API_KEY` | OpenAI API Key | `''` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 同 `OPENAI_API_KEY` |
| `DEEPSEEK_BASE_URL` | DeepSeek 基础 URL | `https://api.deepseek.com/v1` |
| `TOKEN_PLAN_API_KEY` | Token Plan API Key | `''` |
| `TOKEN_PLAN_BASE_URL` | Token Plan 基础 URL | `''` |
| `WECHAT_MCH_ID` | 微信商户号 (支付桩) | `1234567890` |
| `ALIPAY_APP_ID` | 支付宝 App ID (支付桩) | `2021001234567890` |
| `PORT` | Flask 监听端口 | `5000` |

---

## 16. 扩展路线图

### Phase 1 — 当前状态 ✅
- [x] Flask 后端 + 多模型 AI 调用
- [x] 7 种文案场景 + 5 种风格
- [x] 前端 SPA + 离线降级
- [x] Systemd 常驻服务
- [x] Cloudflare Tunnel 公网访问

### Phase 2 — 近期计划 🔄
- [ ] 接入真实支付网关（微信/支付宝）
- [ ] 启用 API Key 认证
- [ ] 实现每日用量限制
- [ ] 密码哈希存储
- [ ] Nginx + HTTPS 正式启用

### Phase 3 — 中期规划 📋
- [ ] 流式输出 (Server-Sent Events)
- [ ] 文案历史记录 + 收藏夹
- [ ] 用户登录系统
- [ ] 文案编辑/重写功能
- [ ] 批量生成

### Phase 4 — 长期愿景 🚀
- [ ] 自定义提示词模板（用户创建/管理）
- [ ] API 开放平台（第三方接入）
- [ ] 多租户支持
- [ ] 迁移至 Gunicorn + Nginx 生产部署
- [ ] Python 版本升级 (3.8+ 以支持新版 SDK)

---

## 附录 A: 项目文件清单

```
/home/admin/ai-wenan-backend/
├── app_v2.py                     # 主服务 (483行)
├── payment.py                    # 支付桩 (123行)
├── index.html                    # 前端 SPA (302行)
├── nginx.conf                    # Nginx 配置
├── ARCHITECTURE.md               # 本文档
├── TEST_REPORT.md                # 测试报告
├── wenyan.db                     # SQLite 数据库
├── prompt_templates/
│   └── expert_access_strategy.py # 医药准入专家模板
├── venv/                         # Python 3.6 虚拟环境
│   ├── bin/python
│   └── lib/python3.6/site-packages/
│       ├── Flask==2.0.3
│       ├── requests==2.27.1
│       ├── urllib3==1.26.20
│       └── idna==3.10
└── __pycache__/                  # Python 字节码缓存
```

---

## 附录 B: 快速参考

### 重启服务
```bash
sudo systemctl restart aiwenan
```

### 查看日志
```bash
journalctl -u aiwenan -n 100 --no-pager
```

### 测试 API
```bash
# 健康检查
curl http://localhost:5000/api/health

# 文案生成
curl -X POST http://localhost:5000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"topic":"夏日防晒","scene":"xiaohongshu","style":"热情种草","model":"deepseek"}'
```

### 修改默认模型
编辑 `/home/admin/.hermes/.env`：
```
AI_MODEL=deepseek
```
然后重启服务：
```bash
sudo systemctl restart aiwenan
```

---

*本文档由 AI 辅助生成，基于实际代码分析。如有偏差，请以源码为准。*

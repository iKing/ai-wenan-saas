# AI文案工坊 API 接口文档

> 版本：V2 | 基础地址：`http://localhost:5000` | 协议：HTTP/JSON

---

## 目录

- [1. 概述](#1-概述)
- [2. 认证说明](#2-认证说明)
- [3. 公共参数](#3-公共参数)
- [4. 接口详情](#4-接口详情)
  - [4.1 健康检查](#41-健康检查)
  - [4.2 AI文案生成](#42-文案生成)
  - [4.3 用户注册](#43-用户注册)
  - [4.4 使用量查询](#44-使用量查询)
  - [4.5 系统统计](#45-系统统计)
  - [4.6 微信支付](#46-微信支付)（待接入）
  - [4.7 支付宝](#47-支付宝)（待接入）
- [5. 错误码](#5-错误码)
- [6. 附录](#6-附录)
  - [6.1 场景枚举](#61-场景枚举)
  - [6.2 模型枚举](#62-模型枚举)
  - [6.3 产品套餐](#63-产品套餐)

---

## 1. 概述

AI文案工坊后端基于 **Flask** 构建，提供AI驱动的文案生成服务。当前版本（V2）集成了多种大语言模型，支持小红书、公众号、短视频脚本等多种文案场景。

| 项目 | 说明 |
|------|------|
| 主文件 | `app_v2.py` |
| 支付模块 | `payment.py` |
| 数据库 | SQLite (`wenyan.db`) |
| 跨域 | 支持全源 CORS（生产环境建议限制域名） |
| 默认端口 | `5000` |

---

## 2. 认证说明

> ⚠️ **当前版本无强制认证，所有接口可公开调用。**

框架已预留认证中间件 `require_api_key`，后续可通过在路由上添加装饰器启用：

```python
@app.route('/api/generate', methods=['POST'])
@require_api_key
def generate():
    ...
```

**认证方式**：在请求头中携带 `X-API-Key`

```
X-API-Key: your-api-key-here
```

| 响应码 | 说明 |
|--------|------|
| `401` | 缺少 API Key（启用认证后） |

---

## 3. 公共参数

### 请求头

| 头部字段 | 类型 | 必填 | 说明 |
|----------|------|------|------|
| `Content-Type` | string | 是 | 固定值 `application/json` |
| `X-API-Key` | string | 否 | 当前未启用，预留字段 |

### 响应格式

所有接口统一返回 JSON：

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

错误响应：

```json
{
  "error": "错误描述信息"
}
```

---

## 4. 接口详情

### 4.1 健康检查

检测服务运行状态及当前默认模型。

```
GET /api/health
```

**请求参数**：无

**响应示例**：

```json
{
  "status": "ok",
  "model": "qwen",
  "timestamp": "2025-01-15T10:30:00.123456"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 服务状态，固定 `"ok"` |
| `model` | string | 当前默认AI模型（读取环境变量 `AI_MODEL`） |
| `timestamp` | string | ISO 8601 格式时间戳 |

---

### 4.2 文案生成

核心接口，根据主题、场景和模型生成AI文案。

```
POST /api/generate
```

**请求体**：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `topic` | string | ✅ | — | 文案主题（最大200字） |
| `scene` | string | ❌ | `xiaohongshu` | 文案场景，见[场景枚举](#61-场景枚举) |
| `style` | string | ❌ | `热情种草` | 文案风格 |
| `model` | string | ❌ | `deepseek` | AI模型，见[模型枚举](#62-模型枚举) |

**请求示例**：

```json
{
  "topic": "春季护肤精华推荐",
  "scene": "xiaohongshu",
  "style": "热情种草",
  "model": "deepseek"
}
```

**成功响应（200）**：

```json
{
  "success": true,
  "content": "✨春季护肤必看！...（AI生成的文案内容）",
  "scene": "xiaohongshu",
  "style": "热情种草",
  "word_count": 356,
  "generation_time": 3.42,
  "model": "deepseek"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 固定 `true` |
| `content` | string | AI生成的文案内容 |
| `scene` | string | 实际使用的场景 |
| `style` | string | 实际使用的风格 |
| `word_count` | integer | 文案字数 |
| `generation_time` | number | 生成耗时（秒），保留两位小数 |
| `model` | string | 实际使用的模型 |

**错误响应**：

| 状态码 | 错误信息 | 触发条件 |
|--------|----------|----------|
| `400` | `"缺少主题参数"` | 请求体为空或不含 `topic` 字段 |
| `400` | `"主题不能为空"` | `topic` 为空字符串 |
| `400` | `"主题过长（最大200字）"` | `topic` 长度超过200字符 |

**注意事项**：
- `scene` 不在白名单中时自动降级为 `xiaohongshu`
- `model` 不在白名单中时自动降级为 `qwen`
- 调用超时取决于所选模型的响应时间（30–120秒不等）

---

### 4.3 用户注册

创建新用户账户（当前密码以明文存储，生产环境应使用哈希）。

```
POST /api/user/register
```

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | ✅ | 用户名（唯一） |
| `password` | string | ✅ | 密码 |

**请求示例**：

```json
{
  "username": "testuser",
  "password": "mypassword123"
}
```

**成功响应（200）**：

```json
{
  "success": true,
  "user_id": 1,
  "username": "testuser",
  "plan": "free"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 固定 `true` |
| `user_id` | integer | 用户数据库ID |
| `username` | string | 用户名 |
| `plan` | string | 套餐类型：`free` / `pro_monthly` / `pro_yearly` / `enterprise` |

**错误响应**：

| 状态码 | 错误信息 | 触发条件 |
|--------|----------|----------|
| `400` | `"缺少用户名或密码"` | 缺少 `username` 或 `password` |
| `409` | `"用户名已存在"` | 用户名已被注册 |

---

### 4.4 使用量查询

查询指定用户今日的文案生成次数及剩余配额。

```
GET /api/user/usage?username=testuser
```

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | ✅ | 用户名 |

**成功响应（200）**：

```json
{
  "today_usage": 3,
  "remaining": 7,
  "daily_limit": 10
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `today_usage` | integer | 今日已使用次数 |
| `remaining` | integer | 剩余可用次数（最小为0） |
| `daily_limit` | integer | 每日免费上限（默认10次） |

**错误响应**：

| 状态码 | 错误信息 | 触发条件 |
|--------|----------|----------|
| `400` | `"缺少用户名"` | 未提供 `username` 参数 |

---

### 4.5 系统统计

获取平台总体统计数据。

```
GET /api/stats
```

**请求参数**：无

**成功响应（200）**：

```json
{
  "total_users": 128,
  "total_generations": 1024,
  "model": "qwen"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_users` | integer | 注册用户总数 |
| `total_generations` | integer | 文案生成总次数 |
| `model` | string | 当前默认模型 |

---

### 4.6 微信支付

> 🔧 **待接入**：`payment.py` 模块已实现，但未挂载到 Flask 路由。

```
POST /api/payment/wechat
```

**请求体**（预期）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | integer | ✅ | 用户ID |
| `product` | string | ✅ | 产品标识，见[产品套餐](#63-产品套餐) |

**请求示例**：

```json
{
  "user_id": 1,
  "product": "pro_monthly"
}
```

**预期成功响应（200）**：

```json
{
  "order_id": "ORD1737000000A1B2C3",
  "method": "wechat",
  "pay_url": "weixin://wxpay/bizpayurl?sr=ORD1737000000A1B2C3",
  "qr_code": "https://api.qrserver.com/v1/create-qr-code/?data=weixin://wxpay/bizpayurl?sr=ORD1737000000A1B2C3"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_id` | string | 内部订单号 |
| `method` | string | 支付方式：`wechat` |
| `pay_url` | string | 微信支付跳转链接 |
| `qr_code` | string | 二维码图片URL |

---

### 4.7 支付宝

> 🔧 **待接入**：`payment.py` 模块已实现，但未挂载到 Flask 路由。

```
POST /api/payment/alipay
```

**请求体**（预期）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | integer | ✅ | 用户ID |
| `product` | string | ✅ | 产品标识，见[产品套餐](#63-产品套餐) |

**请求示例**：

```json
{
  "user_id": 1,
  "product": "pro_yearly"
}
```

**预期成功响应（200）**：

```json
{
  "order_id": "ORD1737000000D4E5F6",
  "method": "alipay",
  "pay_url": "https://openapi.alipay.com/gateway.do?out_trade_no=ORD1737000000D4E5F6"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_id` | string | 内部订单号 |
| `method` | string | 支付方式：`alipay` |
| `pay_url` | string | 支付宝支付跳转链接 |

---

## 5. 错误码

| HTTP 状态码 | 含义 | 常见场景 |
|:-----------:|------|----------|
| `200` | 成功 | 正常请求响应 |
| `400` | 请求参数错误 | 缺少必填参数、参数值无效 |
| `401` | 未授权 | 缺少 API Key（启用认证后） |
| `409` | 资源冲突 | 用户名已存在 |
| `500` | 服务器内部错误 | AI模型调用失败、数据库异常 |

---

## 6. 附录

### 6.1 场景枚举

| 场景值 | 说明 | 提示词模板 |
|--------|------|------------|
| `xiaohongshu` | 小红书种草文案 | Emoji排版、闺蜜语气、200-400字 |
| `gongzhonghao` | 公众号文章 | 5-6部分大纲、开头段落 |
| `shipin` | 短视频脚本 | 分镜+台词、30-60秒、含BGM建议 |
| `pengyouquan` | 朋友圈文案 | 100字以内、自然不生硬 |
| `dianshang` | 电商商品描述 | 卖点突出、刺激购买、淘宝/拼多多风格 |
| `biaoti` | 爆款标题 | 10个标题、多风格覆盖 |
| `yingxiao` | 营销话术 | 社群/私域发售、预热+开售+逼单 |

> 不在上述列表中的场景值将自动降级为 `xiaohongshu`。

### 6.2 模型枚举

| 模型值 | 后端映射 | 说明 |
|--------|----------|------|
| `deepseek` | DeepSeek API (`deepseek-chat`) | 需配置 `DEEPSEEK_API_KEY` |
| `qwen` | 通义千问 (`qwen-plus`) | 需配置 `DASHSCOPE_API_KEY` |
| `claude` | Claude (`claude-sonnet-4-20250514`) | 需配置 `CLAUDE_API_KEY` |
| `openai` | OpenAI (`gpt-4o`) | 需配置 `OPENAI_API_KEY` |
| `template` | 本地模板模式 | 无需API Key，仅演示用 |
| `token-plan-qwen` | Token Plan (`qwen3.6-plus`) | 需配置 `TOKEN_PLAN_API_KEY` + `TOKEN_PLAN_BASE_URL` |
| `token-plan-glm` | Token Plan (`glm-5`) | 同上 |
| `token-plan-minimax` | Token Plan (`MiniMax-M2.5`) | 同上 |

> 不在上述列表中的模型值将自动降级为 `qwen`。

### 6.3 产品套餐

| 产品标识 | 说明 | 价格（元） |
|----------|------|:----------:|
| `pro_monthly` | Pro 月卡 | 9.9 |
| `pro_yearly` | Pro 年卡 | 79.0 |
| `enterprise` | 企业版 | 99.0 |

---

## 更新日志

| 版本 | 日期 | 说明 |
|------|------|------|
| V2 | 2025-01 | 初始版本，基于 `app_v2.py` 编写 |

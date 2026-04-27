# ✍️ AI文案工坊 - 智能写作助手

一个面向自媒体、电商运营、营销人员的AI文案生成工具。

## 📦 项目结构

```
ai-wenan-workshop/
├── frontend/
│   └── index.html          # 纯前端版（立即可用）
├── backend/
│   ├── app.py              # Flask后端API
│   ├── requirements.txt    # Python依赖
│   ├── Dockerfile          # 容器化配置
│   ├── docker-compose.yml  # 编排配置
│   └── DEPLOY.md           # 部署指南
└── README.md
```

## 🚀 快速开始

### 前端版（零配置）
直接打开 `frontend/index.html`，浏览器即可使用。

### 完整版（需要服务器）
```bash
cd backend
pip install -r requirements.txt
python app.py
```

## 💰 商业模式

| 版本 | 价格 | 功能 |
|------|------|------|
| 免费版 | ¥0 | 10次/天，基础场景 |
| PRO版 | ¥9.9/月 | 无限次数，全部场景，API接入 |
| 企业版 | ¥99/月 | 团队协作，自定义模板，优先支持 |

## 📊 目标用户

- 自媒体运营（小红书、公众号、抖音）
- 电商卖家（淘宝、拼多多、Shopify）
- 私域运营（社群发售、朋友圈营销）
- 内容创作者（短视频脚本、标题优化）

## 🎯 MVP完成度

- [x] 前端界面（8种场景，5种风格）
- [x] 模板引擎（本地生成）
- [x] 后端API框架
- [x] 部署配置（Docker + 多平台）
- [ ] 接入真实AI API
- [ ] 用户注册/登录系统
- [ ] 支付系统集成
- [ ] 生产环境部署

## 📝 开发计划

### Phase 1（今晚）✅
- 前端MVP完成
- 模板引擎实现
- 基础盈利模式入口

### Phase 2（明天）
- 接入通义千问/Claude API
- 用户系统开发
- 部署到公网

### Phase 3（本周）
- 支付系统接入
- 数据分析面板
- 多语言支持

### Phase 4（下周）
- 批量生成功能
- API开放平台
- 移动端APP

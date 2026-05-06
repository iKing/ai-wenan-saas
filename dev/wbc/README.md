# WBC 云端开发工作区

**创建时间**：2026-05-06  
**路径**：`/home/admin/ai-wenan-backend/dev/wbc/`

---

## 📁 目录结构

```
dev/wbc/
├── README.md           # 本文件
├── notes/              # 个人笔记
├── tests/              # 测试文件
├── patches/            # 代码补丁
└── scratch/            # 临时文件
```

---

## 🚀 快速开始

```bash
# 1. 进入工作区
cd /home/admin/ai-wenan-backend/dev/wbc

# 2. 切换到 develop 分支
cd ..
git checkout develop

# 3. 开始开发
# 编辑主项目代码
vim /home/admin/ai-wenan-backend/rate_limiter.py

# 4. 运行测试
cd /home/admin/ai-wenan-backend
source venv/bin/activate
pytest test_rate_limiter.py -v
```

---

## 📋 任务清单

### ✅ 任务 1：代码审查（今日 12:00 前）

阅读：
- `/home/admin/ai-wenan-backend/rate_limiter.py`（第 225-264 行）
- `/home/admin/ai-wenan-backend/auth.py`（第 48-145 行）

交付：群里提交审查报告

### ✅ 任务 2：单元测试（明日 12:00 前）

创建：`/home/admin/ai-wenan-backend/test_rate_limiter.py`

测试：
- IP 限流逻辑
- 日志脱敏规则

### ✅ 任务 3：优化实现（后日 18:00 前）

优化：
- 内存缓存清理机制
- 并发安全保护
- 分布式部署支持

---

## 🛠️ 常用命令

```bash
# 查看服务状态
ps aux | grep app_v2.py

# 查看日志
tail -f /home/admin/ai-wenan-backend/server.log

# 运行测试
cd /home/admin/ai-wenan-backend
source venv/bin/activate
pytest test_rate_limiter.py -v

# 编辑代码
vim /home/admin/ai-wenan-backend/rate_limiter.py

# Git 操作
cd /home/admin/ai-wenan-backend
git status
git add .
git commit -m "优化 IP 限流"
git push origin develop
```

---

**WBC**：在此工作区开始你的开发工作！  
**Hermes**：随时提供支持和代码审查。

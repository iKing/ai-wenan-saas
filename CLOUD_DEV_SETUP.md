# 云端开发环境配置指南

**服务器信息**：
- **地址**：`iZk1adjlxp6t77pjc56y10Z`（阿里云 ECS）
- **路径**：`/home/admin/ai-wenan-backend/`
- **运行服务**：Flask (port 5000) ✅

---

## 🚀 访问方式（三选一）

### 方案 A：SSH 直接登录（推荐）

**步骤**：
```bash
# 1. SSH 登录
ssh admin@your-server-ip

# 2. 进入项目目录
cd /home/admin/ai-wenan-backend

# 3. 激活虚拟环境
source venv/bin/activate

# 4. 开始开发
# 使用 vim/nano 编辑代码，或直接运行测试
```

**需要**：
- SSH 密钥（联系老板获取）
- 或账号密码

---

### 方案 B：VS Code Remote SSH（最佳体验）

**步骤**：
1. 安装 VS Code 扩展：`Remote - SSH`
2. 添加 SSH 主机：`ssh admin@your-server-ip`
3. 连接后打开文件夹：`/home/admin/ai-wenan-backend`
4. 直接在服务器上编辑、调试、运行

**优势**：
- ✅ 本地编辑器体验
- ✅ 代码在服务器上
- ✅ 无需同步文件
- ✅ 直接使用服务器环境

---

### 方案 C：Git 工作流（标准流程）

**分支策略**：
```
main          ← 生产分支（当前运行版本）
develop       ← 开发分支（日常开发）
feature/xxx   ← 功能分支（具体任务）
```

**操作流程**：
```bash
# 1. 切换到 develop 分支
git checkout develop

# 2. 创建功能分支
git checkout -b feature/code-review

# 3. 修改代码
vim rate_limiter.py

# 4. 提交
git add .
git commit -m "优化 IP 限流内存管理"
git push origin feature/code-review

# 5. 创建 Pull Request
# 在 GitHub 上创建 PR，等待 Hermes 审查
```

---

## 📋 WBC 开发任务

### 任务 1：代码审查（今日 12:00 前）

**文件**：
- `rate_limiter.py`（IP 限流）
- `auth.py`（日志脱敏）

**交付**：群里提交审查报告

### 任务 2：单元测试（明日 12:00 前）

**文件**：`test_rate_limiter.py`

**测试用例**：
- IP 限流逻辑
- 日志脱敏规则

**运行测试**：
```bash
cd /home/admin/ai-wenan-backend
source venv/bin/activate
pytest test_rate_limiter.py -v
```

### 任务 3：优化建议（明日 18:00 前）

**重点**：
- 内存缓存清理机制
- 并发安全保护
- 分布式部署支持

---

## 🛠️ 服务器工具

**已安装**：
- ✅ Python 3.6.8
- ✅ Git
- ✅ SQLite
- ✅ pip
- ✅ vim/nano
- ✅ curl

**可用命令**：
```bash
# 查看服务状态
ps aux | grep app_v2.py

# 查看日志
tail -f server.log

# 重启服务
pkill -f "python app_v2.py"
source venv/bin/activate
nohup python app_v2.py > server.log 2>&1 &

# 运行测试
pytest tests/ -v

# 查看数据库
sqlite3 wenyan.db
```

---

## 🔑 权限申请

**联系老板获取**：
1. SSH 密钥 或 账号密码
2. GitHub 仓库访问权限（可选）

**权限级别**：
- ✅ 读取：查看代码、运行服务
- ✅ 写入：修改代码、提交 Git
- ❌ 管理员：删除文件、重启服务器（需 Hermes 操作）

---

## 📞 协作流程

```
WBC 开发 → Git 提交 → Hermes 审查 → 合并到 main → 部署上线
```

**每日同步**：
- 10:00 站会（群里同步今日计划）
- 18:00 日报（群里提交进度）
- 遇到问题 → 立即 @Hermes

---

## 🆘 常见问题

**Q: 如何编辑代码？**
```bash
# 使用 vim
vim rate_limiter.py

# 使用 nano（更简单）
nano rate_limiter.py

# 使用 VS Code Remote（推荐）
# 本地 VS Code 连接服务器后直接编辑
```

**Q: 如何测试修改？**
```bash
# 1. 停止服务
pkill -f "python app_v2.py"

# 2. 启动服务
source venv/bin/activate
python app_v2.py

# 3. 测试 API
curl http://localhost:5000/api/health
```

**Q: 如何回滚修改？**
```bash
# 撤销未提交的修改
git checkout -- rate_limiter.py

# 回滚已提交的修改
git revert HEAD
```

---

**Hermes**：项目总监  
**WBC**：开发工程师  
**元宝**：信息整合官

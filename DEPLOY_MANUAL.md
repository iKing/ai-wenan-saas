# AI文案工坊 — 部署与运维手册

> **项目版本**: V2 · **主程序**: `app_v2.py`  
> **服务器**: 阿里云雅加达 · CentOS 7 · Python 3.6.8  
> **服务IP**: `147.139.214.217` · **监听端口**: `5000`

---

## 目录

1. [系统架构概览](#1-系统架构概览)
2. [环境准备](#2-环境准备)
3. [服务部署步骤](#3-服务部署步骤)
4. [Cloudflare 隧道配置](#4-cloudflare-隧道配置)
5. [日常运维命令](#5-日常运维命令)
6. [故障排查指南](#6-故障排查指南)
7. [备份与恢复](#7-备份与恢复)
8. [附录：关键路径速查](#8-附录关键路径速查)

---

## 1. 系统架构概览

```
用户请求
   │
   ▼
┌─────────────────┐      ┌──────────────────┐
│  Cloudflare隧道 │ ───▶ │  Nginx (可选)    │
│  (公网入口)     │      │  端口5000反向代理 │
└─────────────────┘      └────────┬─────────┘
                                 │
                          ┌──────▼─────────┐
                          │  Systemd 服务   │
                          │  aiwenan.service│
                          └──────┬─────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Python 3.6.8 虚拟环境  │
                    │  venv/                  │
                    │                         │
                    │  Flask app_v2.py        │
                    │  │  SQLite (wenyan.db)  │
                    │  │  AI模型调用          │
                    │  └── Qwen / DeepSeek /  │
                    │      Claude / OpenAI    │
                    └─────────────────────────┘
```

### 技术栈

| 组件 | 版本/说明 |
|------|-----------|
| 操作系统 | CentOS 7 |
| Python | 3.6.8 |
| Web框架 | Flask |
| WSGI服务器 | Gunicorn (可选) |
| 数据库 | SQLite 3 (wenyan.db) |
| 进程管理 | Systemd |
| 公网穿透 | Cloudflare Tunnel |
| 虚拟环境 | Python venv |

---

## 2. 环境准备

### 2.1 检查 Python 环境

```bash
# 检查系统Python版本（应为3.6.8）
python3 --version
# 输出: Python 3.6.8

# 检查pip
pip3 --version
# 输出: pip 9.0.3

# 如果Python 3.6未安装，请执行：
sudo yum install -y python3 python3-devel python3-pip
```

### 2.2 创建项目目录并拉取代码

```bash
# 创建项目目录
mkdir -p /home/admin/ai-wenan-backend
cd /home/admin/ai-wenan-backend

# 克隆或复制项目文件（根据实际情况选择）
# 方式1: 从Git仓库克隆
# git clone <repo-url> /home/admin/ai-wenan-backend

# 方式2: 直接上传文件到该目录
```

### 2.3 创建Python虚拟环境

```bash
cd /home/admin/ai-wenan-backend

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 验证
which python
# 输出: /home/admin/ai-wenan-backend/venv/bin/python

python --version
# 输出: Python 3.6.8
```

### 2.4 安装依赖

```bash
source venv/bin/activate

# 安装核心依赖
pip install --upgrade pip setuptools wheel

# 安装项目依赖
pip install flask==2.0.3 requests==2.27.1 gunicorn==20.1.0

# 注意: Python 3.6 兼容性问题
# Python 3.6 不支持最新版 Flask (>=3.0)、requests (>=2.31)、gunicorn (>=21.2)
# 请使用以下兼容版本：

# 方案A: 仅使用 Flask + requests (基础运行)
pip install 'flask>=1.1,<2.1' 'requests>=2.25,<2.28' 'gunicorn>=19.0,<20.2'

# 方案B: 如需 AI 模型调用，安装对应SDK（注意版本兼容）
pip install 'dashscope>=1.14'  # 通义千问
# pip install 'openai>=0.27,<1.0'   # OpenAI (v1.x 需要Python 3.7+)
# pip install 'anthropic>=0.3,<0.18' # Claude (注意兼容版本)

# 验证安装
pip list | grep -iE 'flask|requests|gunicorn|dashscope'
```

### 2.5 初始化数据库

```bash
cd /home/admin/ai-wenan-backend
source venv/bin/activate

# 首次启动会自动创建数据库表，也可手动初始化：
python -c "
import os, sqlite3
os.chdir('/home/admin/ai-wenan-backend')
from app_v2 import init_db
init_db()
print('数据库初始化完成')
"

# 检查数据库文件
ls -la wenyan.db
```

---

## 3. 服务部署步骤

### 3.1 配置环境变量

环境变量文件位于 `~/.hermes/.env`，需确保包含以下变量：

```bash
# 编辑环境变量文件
nano /home/admin/.hermes/.env

# 确保包含以下AI文案工坊相关配置（已有）:
DASHSCOPE_API_KEY=sk-sp-...9YBk
DEEPSEEK_API_KEY=***
TOKEN_PLAN_API_KEY="sk-sp-...9YBk"
TOKEN_PLAN_BASE_URL="https://.../v1"

# 保存后验证
grep -E 'DASHSCOPE|DEEPSEEK|TOKEN_PLAN|AI_MODEL' /home/admin/.hermes/.env
```

### 3.2 配置 Systemd 服务

Systemd服务文件路径：`/etc/systemd/system/aiwenan.service`

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

**部署服务文件：**

```bash
# 创建/更新service文件
sudo tee /etc/systemd/system/aiwenan.service > /dev/null << 'EOF'
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
EOF

# 重新加载systemd配置
sudo systemctl daemon-reload

# 设置开机自启
sudo systemctl enable aiwenan.service

# 启动服务
sudo systemctl start aiwenan.service

# 检查服务状态
sudo systemctl status aiwenan.service
```

### 3.3 验证服务运行

```bash
# 检查进程是否运行
ps aux | grep app_v2.py

# 检查5000端口监听
ss -tlnp | grep 5000
# 或
netstat -tlnp | grep 5000

# 测试本地健康检查
curl http://localhost:5000/api/health
# 预期输出: {"status":"ok","model":"qwen","timestamp":"..."}
```

### 3.4 防火墙配置（如需）

```bash
# 检查防火墙状态
sudo firewall-cmd --state

# 如需开放5000端口（Cloudflare隧道方式通常不需要）
# sudo firewall-cmd --zone=public --add-port=5000/tcp --permanent
# sudo firewall-cmd --reload
```

---

## 4. Cloudflare 隧道配置

### 4.1 安装 cloudflared

```bash
# cloudflared 已安装在 /tmp/cloudflared
# 如未安装或需要更新：
sudo yum install -y wget

# 下载 cloudflared（x86_64 Linux）
wget -O /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x /tmp/cloudflared

# 验证
/tmp/cloudflared --version
```

### 4.2 启动隧道

```bash
# 方式1: Quick Tunnel（临时，每次重启会换域名）
/tmp/cloudflared tunnel --url http://localhost:5000

# 方式2: 后台运行（使用nohup）
nohup /tmp/cloudflared tunnel --url http://localhost:5000 > /home/admin/ai-wenan-backend/logs/cloudflared.log 2>&1 &
echo $! > /home/admin/ai-wenan-backend/logs/cloudflared.pid

# 查看隧道分配的公网URL
cat /home/admin/ai-wenan-backend/logs/cloudflared.log | grep -o 'https://.*trycloudflare.com'
```

### 4.3 配置永久隧道（可选，推荐生产环境）

```bash
# 1. 登录Cloudflare
/tmp/cloudflared tunnel login

# 2. 创建命名隧道
/tmp/cloudflared tunnel create aiwenan

# 3. 配置路由
cat > ~/.cloudflared/config.yml << EOF
tunnel: aiwenan
credentials-file: /home/admin/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: wenyan.yourdomain.com
    service: http://localhost:5000
  - service: http_status:404
EOF

# 4. 添加DNS记录
/tmp/cloudflared tunnel route dns aiwenan wenyan.yourdomain.com

# 5. 启动隧道
/tmp/cloudflared tunnel --config ~/.cloudflared/config.yml run aiwenan

# 6. 后台运行
nohup /tmp/cloudflared tunnel --config ~/.cloudflared/config.yml run aiwenan \
  > /home/admin/ai-wenan-backend/logs/cloudflared.log 2>&1 &
```

### 4.4 Cloudflare 隧道健康检查

```bash
# 检查隧道进程
ps aux | grep cloudflared

# 查看隧道日志
tail -f /home/admin/ai-wenan-backend/logs/cloudflared.log

# 测试公网访问（替换为实际域名）
curl -I https://<your-tunnel-domain>.trycloudflare.com/api/health
```

---

## 5. 日常运维命令

### 5.1 服务管理

```bash
# ━━━ 启动服务 ━━━
sudo systemctl start aiwenan.service

# ━━━ 停止服务 ━━━
sudo systemctl stop aiwenan.service

# ━━━ 重启服务 ━━━
sudo systemctl restart aiwenan.service

# ━━━ 查看服务状态 ━━━
sudo systemctl status aiwenan.service

# ━━━ 查看详细运行信息 ━━━
sudo systemctl show aiwenan.service

# ━━━ 开机自启/禁用 ━━━
sudo systemctl enable aiwenan.service    # 启用开机自启
sudo systemctl disable aiwenan.service   # 禁用开机自启
```

### 5.2 日志查看

```bash
# ━━━ Systemd 服务日志 ━━━
# 查看实时日志（跟踪模式）
sudo journalctl -u aiwenan.service -f

# 查看最近100行日志
sudo journalctl -u aiwenan.service -n 100

# 查看今天的所有日志
sudo journalctl -u aiwenan.service --since today

# 查看最近1小时的日志
sudo journalctl -u aiwenan.service --since "1 hour ago"

# 查看错误日志
sudo journalctl -u aiwenan.service -p err

# 查看特定时间段日志
sudo journalctl -u aiwenan.service --since "2024-01-01 00:00:00" --until "2024-01-01 23:59:59"

# ━━━ Cloudflare 隧道日志 ━━━
tail -f /home/admin/ai-wenan-backend/logs/cloudflared.log

# ━━━ 进程日志 ━━━
# 如果直接用nohup运行：
tail -f /home/admin/ai-wenan-backend/nohup.out
```

### 5.3 性能监控

```bash
# ━━━ 进程状态 ━━━
ps aux | grep -E 'app_v2|cloudflared' | grep -v grep

# ━━━ 端口监听 ━━━
ss -tlnp | grep 5000

# ━━━ 内存使用 ━━━
ps -p $(pgrep -f app_v2.py) -o pid,vsz,rss,pcpu,pmem,cmd

# ━━━ 磁盘使用 ━━━
df -h /home/admin
du -sh /home/admin/ai-wenan-backend/

# ━━━ 数据库大小 ━━━
du -h /home/admin/ai-wenan-backend/wenyan.db

# ━━━ 系统负载 ━━━
uptime
top -bn1 | head -5
```

### 5.4 数据库维护

```bash
cd /home/admin/ai-wenan-backend

# ━━━ 查看用户统计 ━━━
sqlite3 wenyan.db "SELECT plan, COUNT(*) as count FROM users GROUP BY plan;"

# ━━━ 查看总生成次数 ━━━
sqlite3 wenyan.db "SELECT COUNT(*) as total FROM generations;"

# ━━━ 查看最近生成记录 ━━━
sqlite3 wenyan.db "SELECT id, topic, scene, created_at FROM generations ORDER BY created_at DESC LIMIT 10;"

# ━━━ 清理过期数据（可选） ━━━
# 清理30天前的使用记录
sqlite3 wenyan.db "DELETE FROM daily_usage WHERE date < date('now', '-30 days');"

# ━━━ 数据库完整性检查 ━━━
sqlite3 wenyan.db "PRAGMA integrity_check;"

# ━━━ 数据库VACUUM（回收空间） ━━━
sqlite3 wenyan.db "VACUUM;"
```

### 5.5 依赖更新

```bash
cd /home/admin/ai-wenan-backend
source venv/bin/activate

# 查看已安装包
pip list

# 更新特定包（注意Python 3.6兼容性）
pip install --upgrade flask requests

# 重新安装所有依赖
pip install -r requirements.txt
```

---

## 6. 故障排查指南

### 6.1 服务无法启动

```bash
# 1. 查看详细错误
sudo journalctl -u aiwenan.service -n 50 --no-pager

# 2. 检查环境变量文件是否存在且可读
ls -la /home/admin/.hermes/.env
cat /home/admin/.hermes/.env | head -5

# 3. 检查虚拟环境
ls -la /home/admin/ai-wenan-backend/venv/bin/python

# 4. 手动启动排查
cd /home/admin/ai-wenan-backend
source venv/bin/activate
python app_v2.py
# 观察终端输出中的错误信息
```

**常见原因及解决：**

| 症状 | 可能原因 | 解决方案 |
|------|----------|----------|
| `ModuleNotFoundError: No module named 'flask'` | 虚拟环境未激活或依赖未安装 | `source venv/bin/activate && pip install flask` |
| `OSError: [Errno 98] Address already in use` | 端口5000被占用 | `fuser -k 5000/tcp` 或修改端口 |
| `Permission denied` | 文件权限不足 | `chown -R admin:admin /home/admin/ai-wenan-backend` |
| `Failed at step EXEC` | ExecStart路径错误 | 检查service文件中Python路径是否正确 |
| 启动后秒退 | 环境变量缺失 | 检查 `.env` 文件是否存在及格式 |
| `Python 3.6 syntax error` | 依赖包版本不兼容 | 使用兼容版本（见2.4节） |

### 6.2 API调用失败

```bash
# 1. 检查健康端点
curl http://localhost:5000/api/health

# 2. 检查当前AI模型配置
curl -s http://localhost:5000/api/health | python -m json.tool

# 3. 测试文案生成
curl -X POST http://localhost:5000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"topic":"测试主题","scene":"xiaohongshu","model":"template"}'

# 4. 检查API Key是否配置
grep -E 'DASHSCOPE_API_KEY|DEEPSEEK_API_KEY|TOKEN_PLAN' /home/admin/.hermes/.env
```

**AI模型调用问题排查：**

| 错误 | 解决方案 |
|------|----------|
| `⚠️ 未配置 API Key` | 检查 `.env` 中对应 API Key 是否正确填写 |
| `调用超时` | 检查网络连接：`curl -I https://dashscope.aliyuncs.com` |
| `模型返回异常` | 尝试切换到 `template` 模式测试 |
| `Token Plan 调用失败` | 检查 `TOKEN_PLAN_API_KEY` 和 `TOKEN_PLAN_BASE_URL` |

### 6.3 Cloudflare 隧道问题

```bash
# 1. 检查隧道进程
ps aux | grep cloudflared | grep -v grep

# 2. 如果进程不存在，重启隧道
/tmp/cloudflared tunnel --url http://localhost:5000 &

# 3. 检查隧道日志
cat /home/admin/ai-wenan-backend/logs/cloudflared.log | tail -20

# 4. 测试隧道连通性
curl -I https://<tunnel-domain>.trycloudflare.com

# 5. 检查本地服务是否在运行
curl http://localhost:5000/api/health
```

### 6.4 数据库问题

```bash
# 1. 检查数据库文件权限
ls -la /home/admin/ai-wenan-backend/wenyan.db

# 2. 检查数据库完整性
sqlite3 wenyan.db "PRAGMA integrity_check;"

# 3. 如果数据库损坏，从备份恢复（见第7节）

# 4. 检查表结构
sqlite3 wenyan.db ".schema"

# 5. 检查数据量
sqlite3 wenyan.db "SELECT 'users', COUNT(*) FROM users UNION ALL SELECT 'generations', COUNT(*) FROM generations;"
```

### 6.5 磁盘空间不足

```bash
# 1. 检查磁盘使用
df -h

# 2. 查找大文件
du -sh /home/admin/ai-wenan-backend/* | sort -rh

# 3. 清理systemd日志
sudo journalctl --vacuum-size=50M

# 4. 清理临时文件
rm -rf /tmp/__pycache__ /home/admin/ai-wenan-backend/__pycache__

# 5. 清理pip缓存
pip cache purge
```

### 6.6 快速恢复流程

```bash
# 当服务异常时的标准恢复流程：

# 1. 停止服务
sudo systemctl stop aiwenan.service

# 2. 检查状态
sudo systemctl status aiwenan.service

# 3. 修复问题后重启
sudo systemctl start aiwenan.service

# 4. 验证
curl http://localhost:5000/api/health

# 5. 如果仍失败，尝试手动运行排查
cd /home/admin/ai-wenan-backend && source venv/bin/activate && python app_v2.py
```

---

## 7. 备份与恢复

### 7.1 备份策略

```bash
# ━━━ 创建备份目录 ━━━
mkdir -p /home/admin/ai-wenan-backups

# ━━━ 全量备份脚本 ━━━
cat > /home/admin/ai-wenan-backend/backup.sh << 'SCRIPT'
#!/bin/bash
# AI文案工坊 备份脚本
BACKUP_DIR="/home/admin/ai-wenan-backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/aiwenan_backup_${DATE}.tar.gz"

echo "📦 开始备份 AI文案工坊..."

# 停止服务确保数据一致性
sudo systemctl stop aiwenan.service

# 创建备份（排除虚拟环境和缓存）
tar czf "$BACKUP_FILE" \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='.git' \
  -C /home/admin \
  ai-wenan-backend/wenyan.db \
  ai-wenan-backend/app_v2.py \
  ai-wenan-backend/app.py \
  ai-wenan-backend/index.html \
  ai-wenan-backend/requirements.txt \
  ai-wenan-backend/nginx.conf \
  ai-wenan-backend/docker-compose.yml \
  ai-wenan-backend/Dockerfile \
  ai-wenan-backend/deploy.sh \
  ai-wenan-backend/prompt_templates/ \
  ai-wenan-backend/API_DOCS.md \
  ai-wenan-backend/ARCHITECTURE.md \
  ai-wenan-backend/README.md \
  ai-wenan-backend/TEST_REPORT.md \
  ai-wenan-backend/V3_ROADMAP.md

# 重新启动服务
sudo systemctl start aiwenan.service

# 保留最近7天的备份
find "$BACKUP_DIR" -name "aiwenan_backup_*.tar.gz" -mtime +7 -delete

echo "✅ 备份完成: $BACKUP_FILE"
echo "📊 备份大小: $(du -h "$BACKUP_FILE" | cut -f1)"
SCRIPT

chmod +x /home/admin/ai-wenan-backend/backup.sh

# ━━━ 执行备份 ━━━
sudo /home/admin/ai-wenan-backend/backup.sh
```

### 7.2 数据库专项备份

```bash
# ━━━ 手动备份数据库 ━━━
cp /home/admin/ai-wenan-backend/wenyan.db \
   /home/admin/ai-wenan-backups/wenyan_db_$(date +%Y%m%d_%H%M%S).bak

# ━━━ 导出SQL（推荐，更便携） ━━━
sqlite3 /home/admin/ai-wenan-backend/wenyan.db ".dump" \
  > /home/admin/ai-wenan-backups/wenyan_sql_$(date +%Y%m%d_%H%M%S).sql

# ━━━ 设置定时备份（crontab） ━━━
# 编辑crontab:
crontab -e

# 添加以下行（每天凌晨3点备份）:
0 3 * * * /home/admin/ai-wenan-backend/backup.sh >> /home/admin/ai-wenan-backups/backup.log 2>&1
```

### 7.3 恢复流程

```bash
# ━━━ 从备份恢复 ━━━

# 1. 停止服务
sudo systemctl stop aiwenan.service

# 2. 查看可用备份
ls -lt /home/admin/ai-wenan-backups/

# 3. 解压备份
BACKUP_FILE="/home/admin/ai-wenan-backups/aiwenan_backup_YYYYMMDD_HHMMSS.tar.gz"
tar xzf "$BACKUP_FILE" -C /home/admin

# 4. 恢复数据库
cp /home/admin/ai-wenan-backups/wenyan_db_YYYYMMDD_HHMMSS.bak \
   /home/admin/ai-wenan-backend/wenyan.db

# 或使用SQL导入：
# rm /home/admin/ai-wenan-backend/wenyan.db
# sqlite3 /home/admin/ai-wenan-backend/wenyan.db < /home/admin/ai-wenan-backups/wenyan_sql_YYYYMMDD_HHMMSS.sql

# 5. 检查文件权限
chown -R admin:admin /home/admin/ai-wenan-backend

# 6. 启动服务
sudo systemctl start aiwenan.service

# 7. 验证
curl http://localhost:5000/api/health
curl http://localhost:5000/api/stats
```

---

## 8. 附录：关键路径速查

| 项目 | 路径 |
|------|------|
| **项目根目录** | `/home/admin/ai-wenan-backend/` |
| **主程序** | `/home/admin/ai-wenan-backend/app_v2.py` |
| **前端页面** | `/home/admin/ai-wenan-backend/index.html` |
| **Python虚拟环境** | `/home/admin/ai-wenan-backend/venv/` |
| **Python可执行文件** | `/home/admin/ai-wenan-backend/venv/bin/python` |
| **SQLite数据库** | `/home/admin/ai-wenan-backend/wenyan.db` |
| **环境变量文件** | `/home/admin/.hermes/.env` |
| **Systemd服务** | `/etc/systemd/system/aiwenan.service` |
| **Cloudflare隧道** | `/tmp/cloudflared` |
| **Nginx配置** | `/home/admin/ai-wenan-backend/nginx.conf` |
| **备份目录** | `/home/admin/ai-wenan-backups/` |
| **依赖列表** | `/home/admin/ai-wenan-backend/requirements.txt` |

### API端点速查

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端页面 |
| `/api/health` | GET | 健康检查 |
| `/api/generate` | POST | 生成文案 |
| `/api/user/register` | POST | 用户注册 |
| `/api/user/usage` | GET | 查询使用量 |
| `/api/stats` | GET | 系统统计 |

### 支持的AI模型

| 模型标识 | 说明 | 环境变量 |
|----------|------|----------|
| `qwen` | 通义千问 (默认) | `DASHSCOPE_API_KEY` |
| `deepseek` | DeepSeek | `DEEPSEEK_API_KEY` |
| `claude` | Claude | `CLAUDE_API_KEY` |
| `openai` | OpenAI | `OPENAI_API_KEY` |
| `template` | 本地模板模式 | 无需API Key |
| `token-plan-qwen` | Token Plan Qwen | `TOKEN_PLAN_API_KEY` |
| `token-plan-glm` | Token Plan GLM | `TOKEN_PLAN_API_KEY` |
| `token-plan-minimax` | Token Plan MiniMax | `TOKEN_PLAN_API_KEY` |

---

> **文档版本**: v1.0  
> **最后更新**: 2026-04-27  
> **维护者**: AI文案工坊运维团队

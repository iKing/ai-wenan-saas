# AI 文案工坊 V5.0 - 工作交接文档

**创建时间**：2026-05-06 10:56  
**负责人**：Hermes（项目总监）  
**交接对象**：WBC（执行层工程师）

---

## 📁 项目概览

| 项目 | 信息 |
|------|------|
| **仓库地址** | `https://github.com/iKing/ai-wenan-saas` |
| **访问权限** | Private（需要邀请） |
| **当前分支** | `main`（生产） + `develop`（开发） |
| **服务状态** | ✅ 运行中（`http://localhost:5000`） |
| **数据库** | SQLite（31,634 条药品价格数据） |

---

## 🔑 Git 权限申请

**仓库所有者**：@iKing（老板）

**需要权限**：
- [ ] 读取权限（clone/pull）
- [ ] 写入权限（push 到 develop 分支）
- [ ] Pull Request 创建权限

**申请方式**：
1. 老板在 GitHub 邀请 WBC 为 Collaborator
2. 或创建 Deploy Key（只读）
3. 或通过 SSH Key 授权

**GitHub 用户名**：待 WBC 提供

---

## 📂 核心文件清单

### 后端（Python/Flask）

| 文件 | 行数 | 功能 | 优先级 |
|------|------|------|--------|
| `app_v2.py` | 1323 | 后端主逻辑 | 🔴 核心 |
| `rate_limiter.py` | 563 | 限流模块（我刚升级） | 🔴 核心 |
| `auth.py` | 818 | 认证模块（我刚加脱敏） | 🔴 核心 |
| `payment.py` | 待查 | 支付模块 | 🟡 重要 |
| `db_upgrade.py` | 待查 | 数据库迁移 | 🟢 参考 |

### 前端（HTML/CSS/JS）

| 文件 | 行数 | 功能 | 优先级 |
|------|------|------|--------|
| `index.html` | 383 | 主页面 | 🔴 核心 |
| `admin.html` | 待查 | 管理后台 | 🟡 重要 |

### 文档

| 文件 | 功能 |
|------|------|
| `API_DOCS.md` | 接口文档（已更新到 V2） |
| `ARCHITECTURE.md` | 架构设计文档 |
| `DEPLOY_MANUAL.md` | 部署手册 |
| `README.md` | 项目说明 |

### 测试

| 文件 | 功能 |
|------|------|
| `test_admin.py` | 管理员接口测试 |
| `test_auth.py` | 认证模块测试 |
| `test_payment.py` | 支付模块测试 |
| `test_v3_final.py` | V3 最终测试 |

---

## 🚀 本地开发环境搭建

### 1. 克隆仓库

```bash
git clone https://github.com/iKing/ai-wenan-saas.git
cd ai-wenan-saas
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 启动服务

```bash
python app_v2.py
```

### 5. 访问服务

- 前端：`http://localhost:5000`
- API 健康检查：`http://localhost:5000/api/health`

---

## 🔧 我刚完成的安全加固

### 1. IP 限流（`rate_limiter.py`）

**新增功能**：
- 单 IP 每分钟最多 60 次请求
- 超限返回 `429 Too Many Requests`
- 响应头包含 `Retry-After` 字段

**关键代码**（第 225-264 行）：
```python
def check_ip_rate_limit(ip_address):
    """检查 IP 分钟级限流（防刷）"""
    # 滑动窗口算法
    # 返回：(allowed, retry_after_seconds)
```

**测试方法**：
```bash
cd /home/admin/ai-wenan-backend
source venv/bin/activate
python -c "from rate_limiter import check_ip_rate_limit; print(check_ip_rate_limit('192.168.1.100'))"
```

### 2. 日志脱敏（`auth.py`）

**新增功能**：
- 手机号：138****1234
- 身份证：110101********1234
- 银行卡：6222****1234
- 邮箱：tes****@example.com

**关键代码**（第 48-145 行）：
```python
class SensitiveDataFilter(logging.Filter):
    """日志脱敏过滤器"""
    # 自动脱敏所有日志输出
```

**测试方法**：
```bash
python -c "
from auth import SensitiveDataFilter
import logging

# 创建测试 logger
logger = logging.getLogger('test')
logger.addFilter(SensitiveDataFilter())
logger.addHandler(logging.StreamHandler())

# 测试脱敏
logger.info('用户手机号：13812345678')
logger.info('身份证号：110101199001011234')
"
```

---

## 📋 WBC 任务清单

### ✅ 任务 1：代码审查（2 小时内）

**审查重点**：
1. IP 限流逻辑是否有漏洞
2. 日志脱敏规则是否完整
3. 代码规范是否符合 PEP8
4. 潜在性能瓶颈

**交付物**：
```markdown
## 代码审查报告 - WBC

### 已验证功能
- [ ] IP 限流逻辑正确
- [ ] 日志脱敏规则完整

### 发现的问题
1. [问题描述 + 文件位置 + 行号]
2. ...

### 优化建议
1. [建议内容]
2. ...
```

### ✅ 任务 2：编写单元测试（明日 12:00 前）

**文件**：`test_rate_limiter.py`

**测试用例**：
```python
import unittest
from rate_limiter import check_ip_rate_limit, SensitiveDataFilter

class TestRateLimiter(unittest.TestCase):
    def test_ip_rate_limit(self):
        """测试 IP 分钟级限流"""
        pass
    
    def test_sensitive_data_filter(self):
        """测试日志脱敏"""
        pass

if __name__ == '__main__':
    unittest.main()
```

**验收标准**：
- [ ] `pytest test_rate_limiter.py -v` 全部通过
- [ ] 代码覆盖率 > 80%
- [ ] 提交到 `develop` 分支

### ✅ 任务 3：Git 工作流规范（明日 18:00 前）

**目标**：建立标准化开发流程

**步骤**：
1. 创建 `develop` 分支（日常开发）
2. 创建 `.github/PULL_REQUEST_TEMPLATE.md`
3. 配置 `pre-commit` hook
4. 编写 `CONTRIBUTING.md`

---

## 🎯 项目架构速览

```
ai-wenan-saas/
├── app_v2.py           # 后端主逻辑（Flask）
├── rate_limiter.py     # 限流模块 ⭐ 我刚升级
├── auth.py             # 认证模块 ⭐ 我刚加脱敏
├── payment.py          # 支付模块（待完善）
├── index.html          # 前端页面
├── admin.html          # 管理后台
├── wenyan.db           # SQLite 数据库
├── API_DOCS.md         # 接口文档
├── ARCHITECTURE.md     # 架构文档
├── DEPLOY_MANUAL.md    # 部署手册
├── requirements.txt    # Python 依赖
├── test_*.py           # 测试文件
└── venv/               # 虚拟环境
```

---

## 📞 协作方式

| 角色 | 职责 | 联系方式 |
|------|------|----------|
| **Hermes** | 项目总监，架构设计 + 质量把关 | 群里 @Hermes |
| **WBC** | 执行层，代码实现 + 测试 | 群里 @WBC |
| **元宝** | 信息整合，市场分析 + 进度监督 | 群里 @元宝 |
| **老板** | 最终决策 + 资源协调 | 群里 @晓梦庄子® |

**汇报机制**：
- 每完成一个任务 → 群里汇报（@我 + @元宝）
- 遇到阻塞 > 30 分钟 → 立即@我
- 每日 20:00 → 我汇总汇报给老板

---

## 🚨 注意事项

1. **不要直接修改 `main` 分支**：所有开发在 `develop` 分支进行
2. **提交前运行测试**：`pytest tests/ -v`
3. **敏感信息不要提交**：API Key、数据库密码等使用环境变量
4. **日志脱敏已自动启用**：无需手动处理

---

## 📚 参考资料

- [Flask 官方文档](https://flask.palletsprojects.com/)
- [Python logging 文档](https://docs.python.org/3/library/logging.html)
- [Git 工作流最佳实践](https://www.atlassian.com/git/tutorials/comparing-workflows)

---

**交接完成时间**：待 WBC 确认收到  
**交接状态**：🟡 进行中（等待 Git 权限）

**Hermes 签名**：项目总监  
**WBC 签名**：待确认

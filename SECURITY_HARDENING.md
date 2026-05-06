# 🔐 安全加固方案 V3.1

## 📋 安全检查清单

### ✅ 已实现

| 安全项 | 状态 | 说明 |
|--------|------|------|
| 密码哈希 | ✅ | bcrypt + salt |
| JWT 认证 | ✅ | HS256 签名 |
| SQL 参数化 | ✅ | 防止注入 |
| HTTPS | ⏳ | 待部署 |
| 限流保护 | ✅ | 滑动窗口算法 |
| 敏感词过滤 | ✅ | 14 个敏感词 |

---

### ⚠️ 待修复（WBC 审查重点）

| 安全项 | 优先级 | 风险等级 | 负责人 |
|--------|--------|----------|--------|
| JWT 密钥硬编码 | P0 | 🔴 高危 | Hermes |
| 默认管理员密码 | P0 | 🔴 高危 | Hermes |
| CSRF 防护 | P1 | 🟡 中危 | WBC |
| XSS 防护 | P1 | 🟡 中危 | WBC |
| 安全头配置 | P2 | 🟢 低危 | Hermes |
| 审计日志 | P1 | 🟡 中危 | WBC |

---

## 🔧 立即修复项

### 1. JWT 密钥硬编码（P0）

#### 问题
```python
# ❌ 错误示例
JWT_SECRET = "my-secret-key-123"
```

#### 修复
```python
# ✅ 正确做法
import os
from dotenv import load_dotenv

load_dotenv()
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    raise ValueError("JWT_SECRET not configured")
```

#### 环境变量
```bash
# .env
JWT_SECRET=随机生成的 32 位密钥
```

---

### 2. 默认管理员密码（P0）

#### 问题
```python
# ❌ 错误示例
DEFAULT_ADMIN_PASSWORD = "admin123"
```

#### 修复
```python
# ✅ 正确做法
import secrets
import bcrypt

# 首次启动时生成随机密码
def generate_admin_password():
    password = secrets.token_urlsafe(16)
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    return password.decode(), hashed.decode()

# 密码打印到日志（仅首次启动）
print(f"⚠️  管理员初始密码：{password}")
print("⚠️  请立即修改密码！")
```

---

### 3. CSRF 防护（P1）

#### 实现
```python
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)

# 表单中添加 CSRF token
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
</form>
```

---

### 4. 安全头配置（P2）

#### Nginx 配置
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Content-Security-Policy "default-src 'self'" always;
add_header Strict-Transport-Security "max-age=31536000" always;
```

---

## 📊 审计日志方案

### 日志内容
```json
{
    "timestamp": "2026-04-29T17:00:00Z",
    "user_id": "123",
    "action": "login",
    "ip": "192.168.1.100",
    "user_agent": "Mozilla/5.0...",
    "status": "success",
    "details": {...}
}
```

### 记录事件
- 登录/登出
- 密码修改
- 权限变更
- 敏感操作（删除、导出）
- 异常行为（频繁失败）

---

## 🎯 验收标准

- [ ] 无硬编码密钥
- [ ] 无默认密码
- [ ] CSRF 防护启用
- [ ] 安全头配置完整
- [ ] 审计日志完整
- [ ] 通过 OWASP Top 10 检查

---

**版本**: V3.1  
**创建时间**: 2026-04-29 17:00  
**状态**: 待实施

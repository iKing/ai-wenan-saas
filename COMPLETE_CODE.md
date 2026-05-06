# AI 文案工坊 - 完整代码文档

**创建时间**：2026-05-06  
**用途**：WBC 代码审查和单元测试参考

---

## 📁 项目结构

```
/home/admin/ai-wenan-backend/
├── app_v2.py           # 主逻辑 (1323 行)
├── rate_limiter.py     # 限流模块 (626 行) ⭐
├── auth.py             # 认证模块 (929 行) ⭐
├── payment.py          # 支付模块
├── index.html          # 前端页面
├── wenyan.db           # 数据库 (31,634 条)
└── test_*.py           # 测试文件
```

---

## 🔹 代码 1：IP 限流（rate_limiter.py）

### 配置部分（第 34-39 行）

```python
# IP 分钟级限流（防刷）
IP_RATE_LIMIT = 60  # 单 IP 每分钟最多 60 次请求
IP_RATE_WINDOW = 60  # 时间窗口（秒）

# 内存缓存：{ip_address: [timestamp1, timestamp2, ...]}
_ip_request_cache = {}
```

### 限流函数（第 228-265 行）

```python
def check_ip_rate_limit(ip_address):
    """
    检查 IP 分钟级限流（防刷）
    
    Args:
        ip_address: 客户端 IP
        
    Returns:
        tuple: (allowed, retry_after_seconds)
            - allowed: 是否允许调用
            - retry_after_seconds: 重试等待时间（秒），允许时为 0
    """
    import time
    
    current_time = time.time()
    window_start = current_time - IP_RATE_WINDOW
    
    # 清理过期缓存
    if ip_address in _ip_request_cache:
        _ip_request_cache[ip_address] = [
            ts for ts in _ip_request_cache[ip_address]
            if ts > window_start
        ]
    else:
        _ip_request_cache[ip_address] = []
    
    # 检查是否超限
    request_count = len(_ip_request_cache[ip_address])
    
    if request_count >= IP_RATE_LIMIT:
        # 计算最早请求的时间
        oldest_request = min(_ip_request_cache[ip_address])
        retry_after = int(oldest_request + IP_RATE_WINDOW - current_time) + 1
        return (False, max(1, retry_after))
    
    # 记录当前请求
    _ip_request_cache[ip_address].append(current_time)
    return (True, 0)
```

### 审查要点（WBC 已发现）

| 问题 | 严重性 | 建议修复 |
|------|--------|----------|
| 内存缓存无上限 | 🟡 中 | 添加 LRU 淘汰机制 |
| 无锁保护 | 🟡 中 | 添加 threading.Lock |
| 不支持分布式 | 🟡 中 | 改用 Redis |

---

## 🔹 代码 2：日志脱敏（auth.py）

### 脱敏类（第 50-139 行）

```python
import logging
import re

class SensitiveDataFilter(logging.Filter):
    """
    日志脱敏过滤器
    
    脱敏规则：
    - 手机号：138****1234
    - 身份证：110101********1234
    - 银行卡：6222****1234
    - 邮箱：abc****@example.com
    """
    
    @staticmethod
    def mask_phone(match):
        phone = match.group(0)
        return phone[:3] + '****' + phone[-4:]
    
    @staticmethod
    def mask_id_card(match):
        id_card = match.group(0)
        return id_card[:6] + '********' + id_card[-4:]
    
    @staticmethod
    def mask_bank_card(match):
        bank_card = match.group(0)
        return bank_card[:4] + '****' + bank_card[-4:]
    
    @staticmethod
    def mask_email(match):
        email = match.group(0)
        parts = email.split('@')
        if len(parts) == 2:
            username = parts[0]
            domain = parts[1]
            if len(username) >= 3:
                masked_username = username[:3] + '****'
            else:
                masked_username = username[0] + '***'
            return masked_username + '@' + domain
        return email
    
    def filter(self, record):
        """脱敏日志消息"""
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            # 手机号脱敏
            record.msg = re.sub(r'1[3-9]\d{9}', self.mask_phone, record.msg)
            # 身份证脱敏
            record.msg = re.sub(r'\d{17}[\dXx]', self.mask_id_card, record.msg)
            # 银行卡脱敏
            record.msg = re.sub(r'\b\d{16,19}\b', self.mask_bank_card, record.msg)
            # 邮箱脱敏
            record.msg = re.sub(r'\b[\w.-]+@[\w.-]+\.\w+\b', self.mask_email, record.msg)
        
        # 处理 args
        if hasattr(record, 'args') and record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(self._mask_value(arg) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: self._mask_value(v) for k, v in record.args.items()}
        
        return True
    
    def _mask_value(self, value):
        """递归脱敏值"""
        if isinstance(value, str):
            value = re.sub(r'1[3-9]\d{9}', self.mask_phone, value)
            value = re.sub(r'\d{17}[\dXx]', self.mask_id_card, value)
            value = re.sub(r'\b\d{16,19}\b', self.mask_bank_card, value)
            value = re.sub(r'\b[\w.-]+@[\w.-]+\.\w+\b', self.mask_email, value)
        return value


# 配置全局日志脱敏（第 142-153 行）
def setup_sensitive_logging():
    """为所有 logger 添加脱敏过滤器"""
    sensitive_filter = SensitiveDataFilter()
    logging.getLogger().addFilter(sensitive_filter)
    logging.getLogger('werkzeug').addFilter(sensitive_filter)

setup_sensitive_logging()
```

### 审查要点（WBC 已发现）

| 问题 | 严重性 | 建议修复 |
|------|--------|----------|
| 医疗字段遗漏 | 🔴 高 | 补充患者姓名/病历号/医保卡 |
| 正则未预编译 | 🟡 中 | 类级别预编译 |
| 身份证正则不严谨 | 🟡 中 | 升级正则表达式 |

---

## 📝 单元测试模板（WBC 直接写）

### test_rate_limiter.py

```python
#!/usr/bin/env python3
"""
IP 限流和日志脱敏单元测试
"""

import unittest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rate_limiter import check_ip_rate_limit, _ip_request_cache
from auth import SensitiveDataFilter


class TestIPRateLimit(unittest.TestCase):
    """IP 限流测试"""
    
    def setUp(self):
        """每个测试前清空缓存"""
        _ip_request_cache.clear()
    
    def test_60_requests_allowed(self):
        """测试 60 次内允许通过"""
        for i in range(60):
            allowed, retry_after = check_ip_rate_limit('192.168.1.100')
            self.assertTrue(allowed, f"第{i+1}次请求应该允许")
            self.assertEqual(retry_after, 0)
    
    def test_61st_request_blocked(self):
        """测试第 61 次被限流"""
        # 先请求 60 次
        for i in range(60):
            allowed, _ = check_ip_rate_limit('192.168.1.101')
            self.assertTrue(allowed)
        
        # 第 61 次应该被拒绝
        allowed, retry_after = check_ip_rate_limit('192.168.1.101')
        self.assertFalse(allowed, "第 61 次请求应该被拒绝")
        self.assertGreater(retry_after, 0, "应该返回重试时间")
    
    def test_different_ips_independent(self):
        """测试不同 IP 独立计数"""
        # IP1 请求 60 次
        for i in range(60):
            check_ip_rate_limit('192.168.1.102')
        
        # IP2 应该还能请求
        allowed, _ = check_ip_rate_limit('192.168.1.103')
        self.assertTrue(allowed, "不同 IP 应该独立计数")


class TestSensitiveDataFilter(unittest.TestCase):
    """日志脱敏测试"""
    
    def test_phone_masking(self):
        """测试手机号脱敏"""
        filter = SensitiveDataFilter()
        
        # 创建测试记录
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='用户手机号：13812345678',
            args=(),
            exc_info=None
        )
        
        # 应用过滤器
        filter.filter(record)
        
        # 验证脱敏结果
        self.assertEqual(record.msg, '用户手机号：138****5678')
    
    def test_id_card_masking(self):
        """测试身份证脱敏"""
        filter = SensitiveDataFilter()
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='身份证号：110101199001011234',
            args=(),
            exc_info=None
        )
        
        filter.filter(record)
        self.assertEqual(record.msg, '身份证号：110101********1234')
    
    def test_bank_card_masking(self):
        """测试银行卡脱敏"""
        filter = SensitiveDataFilter()
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='银行卡号：6222021234567890123',
            args=(),
            exc_info=None
        )
        
        filter.filter(record)
        self.assertEqual(record.msg, '银行卡号：6222****0123')
    
    def test_email_masking(self):
        """测试邮箱脱敏"""
        filter = SensitiveDataFilter()
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='邮箱：test@example.com',
            args=(),
            exc_info=None
        )
        
        filter.filter(record)
        self.assertEqual(record.msg, '邮箱：tes****@example.com')


if __name__ == '__main__':
    unittest.main(verbosity=2)
```

---

## 🚀 WBC 执行步骤

### 步骤 1：保存私钥

```bash
mkdir -p ~/.ssh
# 把私钥内容粘贴到 ~/.ssh/wbc_key
chmod 600 ~/.ssh/wbc_key
```

### 步骤 2：登录服务器

```bash
ssh -i ~/.ssh/wbc_key wbc@172.19.55.128
cd /home/admin/ai-wenan-backend
```

### 步骤 3：创建测试文件

```bash
cat > test_rate_limiter.py << 'EOF'
# 粘贴上面的测试代码
EOF
```

### 步骤 4：运行测试

```bash
source venv/bin/activate
python -m pytest test_rate_limiter.py -v
```

---

## ⏰ 时间节点

| 时间 | 任务 | 状态 |
|------|------|------|
| 现在 | SSH 登录 | ⏳ 立即执行 |
| 30 分钟内 | 创建测试文件 | ⏳ 立即执行 |
| 1 小时内 | 运行测试 | ⏳ 立即执行 |
| 今日 18:00 | 提交测试报告 | ⏳ 待完成 |

---

**@WBC 别等了，现在就干！** 🚀

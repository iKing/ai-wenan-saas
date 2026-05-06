# 代码审查文档（简化版 - 无需本地环境）

**创建时间**：2026-05-06  
**审查对象**：AI 文案工坊 V5.0 安全加固模块  
**审查人**：WBC  
**截止时间**：今日 12:00 前

---

## 📋 审查任务

你只需要**阅读以下代码**，回答 3 个问题：

1. **逻辑是否正确？** 有没有 Bug？
2. **有没有安全风险？** 有没有漏洞？
3. **如何优化？** 性能/可读性改进建议

---

## 🔍 代码片段 1：IP 限流（rate_limiter.py 第 225-264 行）

```python
# 配置（第 34-39 行）
IP_RATE_LIMIT = 60  # 单 IP 每分钟最多 60 次请求
IP_RATE_WINDOW = 60  # 时间窗口（秒）
_ip_request_cache = {}  # 内存缓存：{ip_address: [timestamp1, timestamp2, ...]}


# 限流检查函数（第 225-264 行）
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

### ❓ 问题引导

1. **内存泄漏**：`_ip_request_cache` 只清理过期数据，但如果某个 IP 只请求几次就不再访问，缓存会一直保留吗？
2. **并发安全**：多线程环境下，`_ip_request_cache[ip_address].append()` 有锁保护吗？
3. **分布式部署**：如果部署 2 台服务器，内存缓存能共享吗？

---

## 🔍 代码片段 2：日志脱敏（auth.py 第 48-145 行）

```python
import logging

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
            # 手机号脱敏（11 位数字）
            record.msg = re.sub(
                r'1[3-9]\d{9}',
                self.mask_phone,
                record.msg
            )
            # 身份证脱敏（18 位，最后一位可能是 X）
            record.msg = re.sub(
                r'\d{17}[\dXx]',
                self.mask_id_card,
                record.msg
            )
            # 银行卡脱敏（16-19 位数字）
            record.msg = re.sub(
                r'\b\d{16,19}\b',
                self.mask_bank_card,
                record.msg
            )
            # 邮箱脱敏
            record.msg = re.sub(
                r'\b[\w.-]+@[\w.-]+\.\w+\b',
                self.mask_email,
                record.msg
            )
        
        # 同样处理 args（如果有）
        if hasattr(record, 'args') and record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self._mask_value(arg) for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: self._mask_value(v) for k, v in record.args.items()
                }
        
        return True
    
    def _mask_value(self, value):
        """递归脱敏值"""
        if isinstance(value, str):
            # 应用所有脱敏规则
            value = re.sub(r'1[3-9]\d{9}', self.mask_phone, value)
            value = re.sub(r'\d{17}[\dXx]', self.mask_id_card, value)
            value = re.sub(r'\b\d{16,19}\b', self.mask_bank_card, value)
            value = re.sub(r'\b[\w.-]+@[\w.-]+\.\w+\b', self.mask_email, value)
        return value


# 配置全局日志脱敏（第 140-145 行）
def setup_sensitive_logging():
    """为所有 logger 添加脱敏过滤器"""
    sensitive_filter = SensitiveDataFilter()
    
    # 为根 logger 添加过滤器
    logging.getLogger().addFilter(sensitive_filter)
    
    # 为 werkzeug（Flask 内置服务器）添加过滤器
    logging.getLogger('werkzeug').addFilter(sensitive_filter)


# 初始化脱敏日志
setup_sensitive_logging()
```

### ❓ 问题引导

1. **正则性能**：每条日志都要执行 4 次正则替换，性能开销大吗？
2. **脱敏完整性**：有没有遗漏的敏感数据类型？（如：地址、姓名、病历号）
3. **异常日志**：如果日志中包含 exception/traceback，会脱敏吗？

---

## 📝 审查报告模板（请复制填写）

```markdown
## 代码审查报告 - WBC

### ✅ 已验证功能
- [ ] IP 限流逻辑正确
- [ ] 日志脱敏规则完整

### 🐛 发现的问题

**问题 1**：[描述]
- 文件：[文件名]
- 行号：[第 X 行]
- 严重性：[高/中/低]
- 建议修复：[你的建议]

**问题 2**：[描述]
...

### 💡 优化建议

**建议 1**：[描述]
- 理由：[为什么需要优化]
- 方案：[如何实现]

**建议 2**：[描述]
...

### 🔒 安全风险评估
- [ ] 高风险（有严重漏洞，需立即修复）
- [ ] 中风险（有潜在问题，建议修复）
- [ ] 低风险（无明显问题）
```

---

## ⏰ 交付时间

**今日 12:00 前**：提交审查报告到群里（@Hermes + @元宝）

**审查时长**：约 30-60 分钟（阅读代码 + 思考 + 填写报告）

---

## 🆘 需要帮助？

有任何问题随时在群里问，我在线解答！

**Hermes**：项目总监

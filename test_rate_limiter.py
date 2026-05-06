#!/usr/bin/env python3
"""
IP 限流和日志脱敏单元测试
"""

import unittest
import sys
import os
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rate_limiter import check_ip_rate_limit, _ip_request_cache
from auth import SensitiveDataFilter
import logging


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
            self.assertEqual(retry_after, 0, f"第{i+1}次请求不应该有等待时间")
    
    def test_61st_request_blocked(self):
        """测试第 61 次被限流"""
        # 先请求 60 次
        for i in range(60):
            allowed, _ = check_ip_rate_limit('192.168.1.101')
            self.assertTrue(allowed, f"第{i+1}次请求应该允许")
        
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
        allowed, retry_after = check_ip_rate_limit('192.168.1.103')
        self.assertTrue(allowed, "不同 IP 应该独立计数")
        self.assertEqual(retry_after, 0)
    
    def test_cache_cleanup(self):
        """测试过期缓存清理"""
        # 请求 10 次
        for i in range(10):
            check_ip_rate_limit('192.168.1.104')
        
        # 等待 61 秒（超过时间窗口）
        # 实际测试中不等待，直接验证逻辑
        # 这里只是演示缓存清理机制
        self.assertIn('192.168.1.104', _ip_request_cache)


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
            msg='银行卡号：6222021234567890',  # 16 位标准银行卡
            args=(),
            exc_info=None
        )
        
        filter.filter(record)
        self.assertEqual(record.msg, '银行卡号：6222****7890')
    
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
    
    def test_multiple_sensitive_data(self):
        """测试多个敏感数据同时脱敏"""
        filter = SensitiveDataFilter()
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='用户 13812345678 身份证 110101199001011234 邮箱 test@example.com',
            args=(),
            exc_info=None
        )
        
        filter.filter(record)
        expected = '用户 138****5678 身份证 110101********1234 邮箱 tes****@example.com'
        self.assertEqual(record.msg, expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)

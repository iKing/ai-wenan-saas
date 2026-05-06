#!/usr/bin/env python3
"""
AI文案工坊 - 企业级支付模块 V3.1
基于 SQLite 的订单持久化、状态机管理及权益自动激活。
"""

import os
import time
import uuid
import sqlite3
import json
import threading
from datetime import datetime, timedelta
from typing import Optional

# 数据库路径 (与主程序共享)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wenyan.db')

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

class EnterprisePaymentGateway:
    """
    企业级支付网关
    支持：订单落库、并发安全、异步回调处理、自动权益发放
    """
    def __init__(self):
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """初始化订单表"""
        conn = get_db()
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_no TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    product TEXT NOT NULL,
                    amount REAL NOT NULL,
                    method TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    transaction_id TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    paid_at DATETIME
                )
            ''')
            conn.commit()
            print("✅ 支付模块 (Orders) 已初始化")
        finally:
            conn.close()

    def create_order(self, user_id: int, product: str, amount: float, method: str) -> dict:
        """
        创建支付订单 (写入数据库)
        """
        order_no = f"ORD{int(time.time())}{uuid.uuid4().hex[:6].upper()}"
        
        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO orders (order_no, user_id, product, amount, method, status)
                VALUES (?, ?, ?, ?, ?, 'PENDING')
            ''', (order_no, user_id, product, amount, method))
            conn.commit()
            
            # 模拟生成支付链接
            pay_data = {
                "order_no": order_no,
                "amount": amount,
                "product": product,
                "method": method
            }

            if method == 'wechat':
                pay_data["pay_url"] = f"weixin://wxpay/bizpayurl?sr={order_no}"
                pay_data["qr_code"] = f"https://api.qrserver.com/v1/create-qr-code/?data=mock_{order_no}"
            else:
                pay_data["pay_url"] = f"https://openapi.alipay.com/gateway.do?out_trade_no={order_no}"
                
            return pay_data
        finally:
            conn.close()

    def check_order_status(self, order_no: str) -> dict:
        """查询订单状态 (前端轮询用)"""
        conn = get_db()
        try:
            order = conn.execute('SELECT * FROM orders WHERE order_no = ?', (order_no,)).fetchone()
            if order:
                return dict(order)
            return {"error": "Order not found"}
        finally:
            conn.close()

    def handle_payment_callback(self, order_no: str, transaction_id: str) -> bool:
        """
        处理支付成功回调 (模拟第三方通知)
        这是一个**事务性操作**：更新订单状态 + 激活权益
        """
        with self.lock:
            conn = get_db()
            try:
                order = conn.execute('SELECT * FROM orders WHERE order_no = ?', (order_no,)).fetchone()
                
                if not order:
                    print(f"❌ Order {order_no} not found")
                    return False
                
                if order['status'] == 'PAID':
                    print(f"⚠️ Order {order_no} already paid (Idempotent check)")
                    return True # 幂等处理

                # 1. 更新订单状态
                conn.execute('''
                    UPDATE orders 
                    SET status = 'PAID', transaction_id = ?, paid_at = CURRENT_TIMESTAMP
                    WHERE order_no = ?
                ''', (transaction_id, order_no))

                # 2. 激活权益
                self._activate_benefit(conn, order['user_id'], order['product'])

                conn.commit()
                print(f"✅ 支付成功: {order_no} -> User {order['user_id']} upgraded.")
                return True
            except Exception as e:
                conn.rollback()
                print(f"❌ Payment Callback Error: {e}")
                return False
            finally:
                conn.close()

    def _activate_benefit(self, conn, user_id: int, product: str):
        """核心业务逻辑：支付成功后修改用户套餐和额度"""
        
        # 产品配置映射
        benefits = {
            "pro_monthly": {"plan": "pro", "limit": 50, "days": 30},
            "pro_yearly": {"plan": "pro", "limit": 100, "days": 365},
            "enterprise": {"plan": "enterprise", "limit": 9999, "days": 365}
        }
        
        if product not in benefits:
            raise ValueError(f"Unknown product: {product}")
            
        cfg = benefits[product]
        expires = (datetime.now() + timedelta(days=cfg['days'])).strftime('%Y-%m-%d %H:%M:%S')

        # Upsert subscription logic
        existing = conn.execute('SELECT id FROM subscriptions WHERE user_id = ?', (user_id,)).fetchone()
        
        if existing:
            conn.execute('''
                UPDATE subscriptions 
                SET plan_type = ?, daily_limit = ?, expires_at = ?
                WHERE user_id = ?
            ''', (cfg['plan'], cfg['limit'], expires, user_id))
        else:
            conn.execute('''
                INSERT INTO subscriptions (user_id, plan_type, daily_limit, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, cfg['plan'], cfg['limit'], expires))

    def get_user_orders(self, user_id: int) -> list:
        """获取用户订单历史"""
        conn = get_db()
        try:
            rows = conn.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 10', (user_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

# 全局实例
gateway = EnterprisePaymentGateway()

# 对外封装
def create_payment(user_id, product, method):
    prices = {
        "pro_monthly": 9.9,
        "pro_yearly": 79.0,
        "enterprise": 500.0
    }
    amount = prices.get(product, 9.9)
    return gateway.create_order(user_id, product, amount, method)

def handle_payment_callback(data):
    return gateway.handle_payment_callback(data['order_no'], data.get('transaction_id', 'MOCK_TX'))

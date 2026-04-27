#!/usr/bin/env python3
"""
AI文案工坊 - 支付模块
模拟接入微信支付和支付宝
"""

import os
import time
import uuid
import json
from datetime import datetime
from typing import Optional

class PaymentGateway:
    def __init__(self):
        self.mch_id = os.getenv('WECHAT_MCH_ID', '1234567890')
        self.alipay_app_id = os.getenv('ALIPAY_APP_ID', '2021001234567890')
        # Mock order storage
        self.orders = {}

    def create_order(self, user_id: int, product: str, amount: float, method: str) -> dict:
        """
        创建支付订单
        :param user_id: 用户ID
        :param product: 产品名称 (pro_monthly, pro_yearly)
        :param amount: 金额
        :param method: 支付方式 (wechat, alipay)
        :return: 订单信息（包含支付链接/二维码）
        """
        order_id = f"ORD{int(time.time())}{uuid.uuid4().hex[:6].upper()}"
        
        # 记录订单
        self.orders[order_id] = {
            "user_id": user_id,
            "product": product,
            "amount": amount,
            "method": method,
            "status": "PENDING",
            "created_at": datetime.now().isoformat(),
            "paid_at": None
        }
        
        # 模拟返回支付凭证
        if method == 'wechat':
            pay_url = f"weixin://wxpay/bizpayurl?sr={order_id}"
            return {
                "order_id": order_id,
                "method": "wechat",
                "pay_url": pay_url,
                "qr_code": f"https://api.qrserver.com/v1/create-qr-code/?data={pay_url}"
            }
        elif method == 'alipay':
            pay_url = f"https://openapi.alipay.com/gateway.do?out_trade_no={order_id}"
            return {
                "order_id": order_id,
                "method": "alipay",
                "pay_url": pay_url
            }
        else:
            raise ValueError(f"Unsupported payment method: {method}")

    def notify_callback(self, order_id: str, transaction_id: str, status: str) -> bool:
        """
        处理支付回调通知
        :param order_id: 内部订单号
        :param transaction_id: 第三方交易号
        :param status: SUCCESS / FAILED
        :return: 是否处理成功
        """
        if order_id not in self.orders:
            print(f"Order {order_id} not found")
            return False
            
        order = self.orders[order_id]
        
        if status == "SUCCESS":
            order["status"] = "PAID"
            order["paid_at"] = datetime.now().isoformat()
            order["transaction_id"] = transaction_id
            
            # 触发业务逻辑（如开通会员）
            self._activate_benefit(order["user_id"], order["product"])
            
            print(f"Payment success: {order_id}")
            return True
        else:
            order["status"] = "FAILED"
            print(f"Payment failed: {order_id}")
            return False

    def check_status(self, order_id: str) -> dict:
        """查询订单状态"""
        if order_id in self.orders:
            return self.orders[order_id]
        return {"error": "Order not found"}

    def _activate_benefit(self, user_id: int, product: str):
        """
        支付成功后激活权益
        实际应调用数据库更新用户状态
        """
        print(f"🎉 Activating {product} for User {user_id}")
        # 模拟数据库更新
        # db.execute("UPDATE users SET plan = ?, plan_expires = ? WHERE id = ?", 
        #            (product, datetime.now() + timedelta(days=30), user_id))

# 全局实例
gateway = PaymentGateway()

# 对外接口函数
def create_payment(user_id, product, method):
    prices = {
        "pro_monthly": 9.9,
        "pro_yearly": 79.0
    }
    if product not in prices:
        return {"error": "Invalid product"}
    
    return gateway.create_order(user_id, product, prices[product], method)

def handle_payment_callback(data):
    """处理第三方回调"""
    return gateway.notify_callback(data["order_id"], data["transaction_id"], data["status"])

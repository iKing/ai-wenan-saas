#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Payment Flow V3.1
"""
import requests
import json
import time

BASE = "http://127.0.0.1:5000"

def test_payment_flow():
    # 1. Register/Login User
    u = f"user_pay_{int(time.time())}"
    e = f"{u}@test.com"
    r = requests.post(f"{BASE}/api/auth/register", json={"username": u, "email": e, "password": "Test123456"})
    assert r.status_code == 201
    token = r.json()['token']
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[OK] User {u} created")

    # 2. Check Initial Quota
    r = requests.get(f"{BASE}/api/auth/profile", headers=headers)
    quota_before = r.json()['subscription']['daily_limit']
    print(f"[INFO] Quota before: {quota_before}")
    
    # 3. Create Order
    r = requests.post(f"{BASE}/api/payment/wechat", json={"product": "pro_monthly"}, headers=headers)
    assert r.status_code == 200
    order_data = r.json()['data']
    order_no = order_data['order_no']
    print(f"[OK] Order created: {order_no}")

    # 4. Simulate Payment Callback
    r = requests.post(f"{BASE}/api/payment/simulate", json={"order_no": order_no})
    assert r.status_code == 200
    assert r.json()['success'] == True
    print(f"[OK] Callback simulated")

    # 5. Verify Quota
    r = requests.get(f"{BASE}/api/auth/profile", headers=headers)
    quota_after = r.json()['subscription']['daily_limit']
    plan = r.json()['subscription']['plan_type']
    print(f"[INFO] Quota after: {quota_after} (Plan: {plan})")

    if quota_after == 50:
        print("\n[RESULT] PAYMENT FLOW SUCCESS! Quota updated correctly.")
    else:
        print(f"\n[ERROR] Quota mismatch! Expected 50, got {quota_after}")

if __name__ == "__main__":
    test_payment_flow()

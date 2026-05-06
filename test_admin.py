#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Admin API
"""
import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def log(msg):
    print(f"[TEST] {msg}")

def test_admin():
    # 1. Login as admin
    log("1. Logging in as admin...")
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert r.status_code == 200, f"Admin Login failed ({r.status_code}): {r.text}"
    data = r.json()
    assert data["success"]
    token = data["token"]
    headers = {"Authorization": f"Bearer {token}"}
    log(f" -> OK")

    # 2. Get Stats
    log("2. Fetching Admin Stats...")
    r = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)
    assert r.status_code == 200, f"Stats failed ({r.status_code})"
    stats = r.json()
    log(f" -> Users: {stats['total_users']}, Gens: {stats['total_generations']}")

    # 3. List Users
    log("3. Fetching User List...")
    r = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
    assert r.status_code == 200, f"Users list failed ({r.status_code})"
    users_data = r.json()
    users = users_data.get("users", [])
    log(f" -> Found {len(users)} users. Top user: {users[0]['username'] if users else 'None'}")

    # 4. Modify Quota
    if users:
        user_id = users[0]['id']
        log(f"4. Modifying quota for user {user_id}...")
        r = requests.post(f"{BASE_URL}/api/admin/users/{user_id}/quota", 
                          json={"daily_limit": 99}, headers=headers)
        log(f" -> Status: {r.status_code}, Resp: {r.text}")

    print("\n[RESULT] Admin API Test Success!")

if __name__ == "__main__":
    try:
        test_admin()
    except Exception as e:
        print(f"\n[ERROR] {e}")

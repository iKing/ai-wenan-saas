#!/usr/bin/env python3
"""
AI文案工坊 V3.0 - 数据库升级脚本
将 V2 数据库升级至 V3.0 用户认证系统架构

新增/修改内容：
- users表：添加 email, role, last_login 字段
- usage_logs表：新建，记录每次AI调用的详细使用情况
- subscriptions表：新建，管理用户套餐和用量限制

兼容：Python 3.6.8 + SQLite
"""

import os
import sqlite3
import sys


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wenyan.db')


def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_existing_columns(conn, table_name):
    """获取表中已有的列名"""
    cursor = conn.execute("PRAGMA table_info({})".format(table_name))
    return [row['name'] for row in cursor.fetchall()]


def upgrade_users_table(conn):
    """升级 users 表：添加 email, role, last_login 字段"""
    existing = get_existing_columns(conn, 'users')
    cursor = conn.cursor()

    additions = [
        ('email', 'TEXT'),  # UNIQUE约束通过触发器/应用层保证（SQLite限制）
        ('role', "TEXT DEFAULT 'user' CHECK(role IN ('user', 'admin'))"),
        ('last_login', 'TIMESTAMP'),
    ]

    for col_name, col_def in additions:
        if col_name not in existing:
            sql = "ALTER TABLE users ADD COLUMN {} {}".format(col_name, col_def)
            cursor.execute(sql)
            print("  [users] 添加列: {} ({})".format(col_name, col_def))
        else:
            print("  [users] 列 {} 已存在，跳过".format(col_name))

    # 确保 role 列有默认值更新已有数据
    cursor.execute("UPDATE users SET role = 'user' WHERE role IS NULL")

    # 处理已有的NULL email
    cursor.execute("UPDATE users SET email = '' WHERE email IS NULL")

    conn.commit()


def create_usage_logs_table(conn):
    """创建 usage_logs 表 - 记录每次AI调用详情"""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            scene TEXT,
            prompt TEXT,
            response_length INTEGER DEFAULT 0,
            tokens_used INTEGER DEFAULT 0,
            status TEXT DEFAULT 'success' CHECK(status IN ('success', 'failed', 'rate_limited')),
            error_message TEXT,
            response_time REAL,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    print("  [usage_logs] 表创建成功（或已存在）")

    # 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_logs(user_id, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_model ON usage_logs(model)")
    conn.commit()
    print("  [usage_logs] 索引创建完成")


def create_subscriptions_table(conn):
    """创建 subscriptions 表 - 管理用户套餐"""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_type TEXT NOT NULL DEFAULT 'free' CHECK(plan_type IN ('free', 'vip', 'enterprise')),
            daily_limit INTEGER DEFAULT 10,
            monthly_limit INTEGER DEFAULT 300,
            max_tokens_per_request INTEGER DEFAULT 2000,
            priority INTEGER DEFAULT 0,
            expires_at TIMESTAMP,
            auto_renew INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'expired', 'cancelled')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, plan_type)
        )
    ''')
    conn.commit()
    print("  [subscriptions] 表创建成功（或已存在）")

    # 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_user ON subscriptions(user_id, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_expires ON subscriptions(expires_at)")
    conn.commit()
    print("  [subscriptions] 索引创建完成")


def seed_default_subscriptions(conn):
    """为所有现有用户创建默认 free 套餐记录"""
    cursor = conn.cursor()

    # 获取还没有 subscription 记录的 user
    cursor.execute('''
        SELECT u.id FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM subscriptions s
            WHERE s.user_id = u.id AND s.plan_type = 'free'
        )
    ''')
    users_without_sub = cursor.fetchall()

    if users_without_sub:
        for user in users_without_sub:
            cursor.execute('''
                INSERT INTO subscriptions (user_id, plan_type, daily_limit, monthly_limit)
                VALUES (?, 'free', 10, 300)
            ''', (user['id'],))
        conn.commit()
        print("  为 {} 个用户创建了默认 free 套餐".format(len(users_without_sub)))
    else:
        print("  所有用户已有默认套餐，跳过")


def run_upgrade():
    """执行完整的数据库升级流程"""
    print("=" * 60)
    print("AI文案工坊 V3.0 - 数据库升级")
    print("=" * 60)
    print("数据库路径: {}".format(DB_PATH))
    print()

    if not os.path.exists(DB_PATH):
        print("错误: 数据库文件不存在: {}".format(DB_PATH))
        sys.exit(1)

    conn = get_connection()
    try:
        print("[1/4] 升级 users 表...")
        upgrade_users_table(conn)
        print()

        print("[2/4] 创建 usage_logs 表...")
        create_usage_logs_table(conn)
        print()

        print("[3/4] 创建 subscriptions 表...")
        create_subscriptions_table(conn)
        print()

        print("[4/4] 初始化默认套餐...")
        seed_default_subscriptions(conn)
        print()

        # 验证
        print("-" * 40)
        print("验证升级结果:")
        for table in ['users', 'usage_logs', 'subscriptions']:
            cols = get_existing_columns(conn, table)
            count = conn.execute("SELECT COUNT(*) as c FROM {}".format(table)).fetchone()['c']
            print("  {}: {} 列 ({} 条记录)".format(table, ', '.join(cols), count))

        print()
        print("=" * 60)
        print("数据库升级完成！")
        print("=" * 60)

    except Exception as e:
        print()
        print("升级失败: {}".format(str(e)))
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    run_upgrade()

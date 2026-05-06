#!/bin/bash
# AI 文案工坊 V3.1 - 安全部署脚本

set -e

echo "======================================"
echo "AI 文案工坊 V3.1 安全部署"
echo "======================================"

BACKEND_DIR="/home/admin/ai-wenan-backend"
cd "$BACKEND_DIR"

# 1. 检查 .env 文件
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  未找到 .env 文件，正在创建..."
    cp .env.example .env
    
    # 生成随机 JWT_SECRET
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    # 更新 .env 文件
    sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
    sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")/" .env
    
    echo "✅ .env 文件已创建，JWT_SECRET 已随机生成"
    echo ""
    echo "⚠️  请检查 .env 文件并配置以下必填项："
    echo "   - JWT_SECRET（已自动生成）"
    echo "   - SECRET_KEY（已自动生成）"
    echo "   - 支付配置（如启用支付功能）"
    echo ""
else
    echo "✅ .env 文件已存在"
fi

# 2. 检查 JWT_SECRET 是否已修改
if grep -q "JWT_SECRET=你的 JWT 密钥" .env; then
    echo ""
    echo "🚨 警告：JWT_SECRET 仍为默认值，存在安全风险！"
    echo "正在重新生成..."
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
    echo "✅ JWT_SECRET 已重新生成"
fi

# 3. 安装依赖
echo ""
echo "📦 检查依赖..."
pip install -q -r requirements.txt
echo "✅ 依赖已安装"

# 4. 数据库迁移（如有）
if [ -f db_upgrade.py ]; then
    echo ""
    echo "🗄️  执行数据库迁移..."
    python3 db_upgrade.py
    echo "✅ 数据库迁移完成"
fi

# 5. 停止旧进程
echo ""
echo "🛑 停止旧进程..."
pkill -f "python.*app_v2.py" || true
sleep 2

# 6. 启动新进程
echo ""
echo "🚀 启动服务..."
nohup python3 app_v2.py > server.log 2>&1 &
sleep 3

# 7. 健康检查
echo ""
echo "🏥 健康检查..."
if curl -s http://localhost:5000/ > /dev/null 2>&1; then
    echo "✅ 服务启动成功！"
    echo ""
    echo "======================================"
    echo "📍 访问地址：http://localhost:5000"
    echo "📍 管理后台：http://localhost:5000/admin"
    echo "======================================"
    echo ""
    echo "⚠️  管理员密码已打印到 server.log，请立即查看并修改！"
    echo "   查看命令：tail -50 server.log | grep '密码'"
    echo ""
else
    echo "🚨 服务启动失败，请检查 server.log"
    tail -50 server.log
    exit 1
fi

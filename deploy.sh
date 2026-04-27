#!/bin/bash
# AI文案工坊 - 一键部署脚本
# 用法：bash deploy.sh

echo "🚀 AI文案工坊 部署脚本"
echo "======================"

# 检查环境
echo "📋 检查环境..."
command -v python3 >/dev/null 2>&1 || { echo "❌ 需要Python3"; exit 1; }
command -v pip3 >/dev/null 2>&1 || { echo "❌ 需要pip3"; exit 1; }

# 创建虚拟环境
echo "📦 创建虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 安装依赖
echo "📥 安装依赖..."
pip install -r requirements.txt

# 检查API Key
if [ -z "$AI_API_KEY" ]; then
    echo "⚠️  未设置AI_API_KEY，将使用模板模式"
    echo "   设置方式：export AI_API_KEY='your-key'"
fi

# 启动服务
echo "🌐 启动服务..."
echo "   访问地址：http://localhost:5000"
echo "   API文档：http://localhost:5000/api/health"
gunicorn -w 4 -b 0.0.0.0:5000 app:app

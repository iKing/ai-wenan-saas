# AI 文案工坊 - Windows 开发环境一键安装脚本
# 使用方法：在 PowerShell 中运行 .\setup-windows.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI 文案工坊 - 开发环境一键安装" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "⚠️  需要管理员权限，请以管理员身份运行 PowerShell" -ForegroundColor Yellow
    Write-Host "   右键 PowerShell → '以管理员身份运行'" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "正在尝试以管理员身份重新启动..." -ForegroundColor Yellow
    
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

Write-Host "✅ 管理员权限确认" -ForegroundColor Green
Write-Host ""

# 步骤 1: 检查 winget
Write-Host "📦 步骤 1/3: 检查 winget..." -ForegroundColor Cyan
try {
    $wingetVersion = winget --version
    Write-Host "✅ winget 已安装 (版本：$wingetVersion)" -ForegroundColor Green
} catch {
    Write-Host "❌ winget 未安装，尝试启用..." -ForegroundColor Yellow
    
    # 尝试启用 App Installer
    try {
        Get-AppxPackage -Name Microsoft.DesktopAppInstaller | Select-Object Name, Version
        Write-Host "✅ App Installer 已安装，winget 应该可用" -ForegroundColor Green
    } catch {
        Write-Host "❌ App Installer 未安装" -ForegroundColor Red
        Write-Host "   请打开 Microsoft Store 搜索 'App Installer' 并安装" -ForegroundColor Yellow
        Write-Host "   或者访问：https://aka.ms/getwinget" -ForegroundColor Yellow
        exit 1
    }
}
Write-Host ""

# 步骤 2: 安装 Python
Write-Host "🐍 步骤 2/3: 安装 Python 3.11..." -ForegroundColor Cyan
try {
    $pythonCheck = python --version 2>&1
    Write-Host "✅ Python 已安装 ($pythonCheck)" -ForegroundColor Green
    
    $upgrade = Read-Host "   是否升级到 Python 3.11? (y/n)"
    if ($upgrade -eq 'y') {
        winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
        Write-Host "✅ Python 3.11 安装完成" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠️  Python 未安装，开始安装..." -ForegroundColor Yellow
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    Write-Host "✅ Python 3.11 安装完成" -ForegroundColor Green
}
Write-Host ""

# 步骤 3: 安装 Git
Write-Host "🔧 步骤 3/3: 安装 Git..." -ForegroundColor Cyan
try {
    $gitCheck = git --version 2>&1
    Write-Host "✅ Git 已安装 ($gitCheck)" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Git 未安装，开始安装..." -ForegroundColor Yellow
    winget install Git.Git --silent --accept-package-agreements --accept-source-agreements
    Write-Host "✅ Git 安装完成" -ForegroundColor Green
}
Write-Host ""

# 验证安装
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  环境验证" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "📊 已安装工具:" -ForegroundColor Cyan
python --version
pip --version
git --version

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ 环境安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "1. 关闭此窗口，重新打开 PowerShell（刷新环境变量）" -ForegroundColor White
Write-Host "2. 运行：python --version 和 git --version 验证" -ForegroundColor White
Write-Host "3. 联系 Hermes 获取代码包" -ForegroundColor White
Write-Host ""

# 询问是否继续安装 VS Code 扩展
$installVscode = Read-Host "是否安装 VS Code 扩展？(y/n)"
if ($installVscode -eq 'y') {
    Write-Host ""
    Write-Host "📦 安装 VS Code 扩展..." -ForegroundColor Cyan
    
    # 检查 VS Code 是否安装
    try {
        $codeVersion = code --version 2>&1
        Write-Host "✅ VS Code 已安装" -ForegroundColor Green
        
        # 安装推荐扩展
        Write-Host "   安装 Python 扩展..." -ForegroundColor White
        code --install-extension ms-python.python --force
        
        Write-Host "   安装 SQLite 扩展..." -ForegroundColor White
        code --install-extension florinpatan.sqltools --force
        
        Write-Host "✅ VS Code 扩展安装完成" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  VS Code 未安装，跳过扩展安装" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "🎉 全部完成！" -ForegroundColor Green
Write-Host ""

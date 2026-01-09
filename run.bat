@echo off
REM ==========================================
REM Flask API 服务器快速启动脚本
REM ==========================================
REM 功能：启动 S_of_p_information_python 项目下的 Flask 应用
REM 用法：在项目目录下双击运行或在命令行执行

echo.
echo ==========================================
echo  Flask API Server Startup
echo ==========================================
echo.

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 验证 Python 安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python 环境
    echo 请确保 Python 已安装并添加到 PATH 环境变量
    pause
    exit /b 1
)

echo [✓] Python 环境已检测
echo.

REM 启动 Flask 应用
echo [启动] Flask 开发服务器...
echo [信息] 访问地址: http://127.0.0.1:5000
echo [信息] API 文档: http://127.0.0.1:5000/api/public/notice/types
echo.

python -u app.py

REM 如果 Flask 应用退出，暂停窗口以便查看错误信息
echo.
echo 应用已退出，按任意键关闭窗口...
pause

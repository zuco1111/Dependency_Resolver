@echo off
echo 正在创建虚拟环境 venv...
python -m venv venv

if %errorlevel% neq 0 (
    echo 创建虚拟环境失败，请检查Python是否正确安装
    pause
    exit /b 1
)

echo 激活虚拟环境...
call venv\Scripts\activate.bat

echo 正在安装依赖
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo 依赖安装失败，请检查 requirements.txt 是否存在
    pause
    exit /b 1
)

echo 操作完成！
echo 按任意键退出...
pause >nul
@echo off
echo ���ڴ������⻷�� venv...
python -m venv venv

if %errorlevel% neq 0 (
    echo �������⻷��ʧ�ܣ�����Python�Ƿ���ȷ��װ
    pause
    exit /b 1
)

echo �������⻷��...
call venv\Scripts\activate.bat

echo ���ڰ�װ����
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ������װʧ�ܣ����� requirements.txt �Ƿ����
    pause
    exit /b 1
)

echo ������ɣ�
echo ��������˳�...
pause >nul
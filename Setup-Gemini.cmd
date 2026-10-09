@echo off
setlocal
cd /d "%~dp0"
if not exist ".env" (
  echo Chua co file .env. Sao chep .env.example thanh .env va dien cau hinh truoc.
  pause
  exit /b 1
)
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
python -m ai_company.application.provider_setup_cli --approve --approved-by local-owner
if errorlevel 1 (
  echo.
  echo Khong phe duyet duoc cau hinh. Xem loi phia tren; khong gui API key qua chat.
  pause
  exit /b 1
)
echo.
echo Da ghi policy, model assignment va budget bat bien vao database cuc bo.
pause

@echo off
setlocal
cd /d "%~dp0"
if not exist ".env" (
  echo Chua co file .env. Sao chep .env.example thanh .env va dien key truoc.
  pause
  exit /b 1
)
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
python -m ai_company.application.provider_check_cli
if errorlevel 1 (
  echo.
  echo Kiem tra that bai. Khong gui API key qua chat; sua .env tren may roi thu lai.
  pause
  exit /b 1
)
echo.
echo Key va model da san sang. Ban co the chay Setup-AI-Agents.cmd.
pause

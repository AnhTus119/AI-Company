@echo off
setlocal
cd /d "%~dp0"
python --version >nul 2>nul
if errorlevel 1 (
  echo Can cai Python 3.12 tro len va chon "Add Python to PATH" khi cai dat.
  echo Sau do nhap dup file nay lan nua.
  pause
  exit /b 1
)
python launch_local.py
if errorlevel 1 (
  echo.
  echo Khong khoi dong duoc. Gui anh loi trong cua so nay de duoc ho tro.
  pause
)

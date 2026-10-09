@echo off
setlocal
cd /d "%~dp0"
python launch_local.py
if errorlevel 1 (
  echo.
  echo Khong khoi dong duoc. Gui anh loi trong cua so nay de duoc ho tro.
  pause
)

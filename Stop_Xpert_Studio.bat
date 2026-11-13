@echo off
rem Emergency/Quick stop script for Xpert Structural Design Studio
taskkill /F /FI "WINDOWTITLE eq Xpert Structural Design Studio*" /T >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
echo [Xpert Studio] Application closed successfully.
pause

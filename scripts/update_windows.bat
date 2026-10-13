@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set PYTHONUTF8=1
py -m pip install -r requirements.txt || goto fail
py tools\sync_cards.py --limit 20 --delay 6 || goto fail
py tools\validate_database.py || goto fail
echo.
echo 数据已保存到 data\cards，确认后使用 git add / commit / push 上传。
pause
exit /b 0
:fail
echo 更新暂停；请检查网络或错误提示，之前已保存的进度不会丢失。
pause
exit /b 1

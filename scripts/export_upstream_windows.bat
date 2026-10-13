@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set PYTHONUTF8=1
py tools\export_upstream.py || goto fail
echo 官方汉化补丁位置：dist\upstream\zh-CN.patch
pause
exit /b 0
:fail
echo 导出失败。请检查 GitHub 网络和翻译键。
pause
exit /b 1

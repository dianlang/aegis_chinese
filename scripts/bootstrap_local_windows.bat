@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where py >nul 2>nul
if not errorlevel 1 (
  set "PYCMD=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 goto no_python
  set "PYCMD=python"
)
%PYCMD% -c "import sys; assert sys.version_info >= (3,9), 'Python 3.9 or later is required'"
if errorlevel 1 goto fail
%PYCMD% -c "import bs4" >nul 2>nul
if errorlevel 1 (
  echo Installing beautifulsoup4 for first use...
  %PYCMD% -m pip install -r requirements.txt
  if errorlevel 1 goto fail
)
echo.
echo Running locally with on-disk checkpoints. Close other active DigiCamoe scrapers.
echo You can press Ctrl+C; progress from previous checkpoints stays on disk.
echo.
%PYCMD% -u tools\local_bootstrap.py --minutes 110 --workers 2 --min-interval 2 --repair-404
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo Finished current local batch. Data is still LOCAL until uploaded to GitHub.
) else (
  echo Stopped or failed with exit code %RESULT%.
  echo Saved data remains in data\ and details in logs\.
  echo Do NOT restart immediately after upstream 429 or persistent 5xx errors.
)
pause
exit /b %RESULT%
:no_python
echo Python not found. Install Python 3.9 or later, then run this file again.
goto fail
:fail
echo Initialization failed. Review the text above.
pause
exit /b 1

@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
set PYTHONUTF8=1
where py >nul 2>nul
if not errorlevel 1 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python not found. Install Python 3.9 or above.
    pause
    exit /b 1
  )
  set "PY=python"
)
%PY% -c "import sys; assert sys.version_info >= (3,9)"
if errorlevel 1 goto failed
%PY% -c "import playwright" >nul 2>nul
if errorlevel 1 (
  echo First-run setup: installing the Playwright Python package.
  echo Existing Microsoft Edge will be used; no Chromium download required.
  %PY% -m pip install "playwright>=1.45,<2"
  if errorlevel 1 goto failed
)
echo.
echo This opens the official CN card database in Microsoft Edge.
echo Search for a card or use pagination in the open browser.
echo The program captures card JSON responses; it does NOT collect cookies.
echo Default collection window: 120 seconds.
echo.
%PY% -u tools\capture_official_browser.py --seconds 120
if errorlevel 1 goto failed
echo.
echo Generating exact 3-way Japanese - Official CN - Aegis ID map...
%PY% -u tools\align_official_cards.py --official-json local_data\official_cn_capture.json
if errorlevel 1 goto failed
echo.
echo Done. Check local_data\official_alignment.csv and official_cn_capture_endpoints.json.
echo Original official response records stay in local_data and are NOT committed to GitHub.
pause
exit /b 0
:failed
echo.
echo Official card sample capture or mapping failed.
echo If card count is zero, send the endpoint diagnostic file without tokens or cookies.
pause
exit /b 1

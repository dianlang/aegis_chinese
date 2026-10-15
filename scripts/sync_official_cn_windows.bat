@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where py >nul 2>nul
if not errorlevel 1 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 goto no_python
  set "PY=python"
)
%PY% -c "import sys; assert sys.version_info >= (3,9)"
if errorlevel 1 goto failed
%PY% -c "import bs4" >nul 2>nul
if errorlevel 1 (
  echo Installing database dependencies...
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
echo.
echo Official Simplified Chinese DTCG API -> local card database
echo Real backend: dtcgweb-api.digimoncard.cn
echo Printed card number model = Aegis ID, product pack cardGroup is NOT the card ID.
echo.
echo 1. Quick test, 3 pages, 120 card entries maximum
echo 2. Full official card list, approximately 189 pages, with safe resume
echo.
choice /c 12 /n /m "Choose mode [1/2]: "
if errorlevel 2 goto full
if errorlevel 1 goto small
goto failed
:small
echo Running limited sample...
%PY% -u tools\sync_official_cn.py --max-pages 3 --interval 4 --time-budget-minutes 10
goto done
:full
echo Running full LOCAL-only official card snapshot.
echo Be considerate of website traffic: minimum 4 seconds between requests.
echo Stop on HTTP 429/5xx and resume later after the site recovers.
%PY% -u tools\sync_official_cn.py --full --interval 4 --time-budget-minutes 60
goto done
:done
set "CODE=%ERRORLEVEL%"
echo.
echo Saved pages: local_data\official_cn_pages\
echo Raw records: local_data\official_cn_capture.json
echo 3-way mapping: local_data\official_alignment.csv
echo NO official card texts were automatically committed to GitHub.
if not "%CODE%"=="0" echo The task stopped early. Saved pages remain available.
pause
exit /b %CODE%
:no_python
echo Python 3.9 or later is needed.
:failed
pause
exit /b 1

@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" not found. Please install Python 3.9+.
  pause
  exit /b 1
)
py -3 -c "import sys; assert sys.version_info >= (3,9)"
if errorlevel 1 (
  echo Python 3.9 or newer is required.
  pause
  exit /b 1
)
py -3 -c "import playwright" >nul 2>nul
if errorlevel 1 (
  echo Installing optional Playwright browser driver...
  py -3 -m pip install playwright
  if errorlevel 1 goto fail
)
echo.
echo Installing Chromium for normal website navigation if needed...
py -3 -m playwright install chromium
if errorlevel 1 goto fail
echo.
echo Official site will open. Search cards and change pages using the website UI.
echo Press Enter in the console after finishing your sample searches.
echo This captures only public card JSON responses; do not log in.
echo.
py -3 tools\official_cn_capture.py
if errorlevel 1 goto fail
echo.
echo Captured public Chinese card records to local_data\official_cn_capture.json
echo The next step downloads Aegis' public catalog and compares 3 card identifiers.
py -3 tools\official_cn_align.py --fetch-aegis
if errorlevel 1 goto fail
echo.
echo DONE. Inspect local_data\official_cn_review.csv and official_cn_alignment.json.
echo No data was added to public GitHub JSON. Unmatched cards require manual review.
pause
exit /b 0
:fail
echo.
echo Capture or alignment failed. Check the preceding messages.
echo All existing public card files remain unchanged.
pause
exit /b 1

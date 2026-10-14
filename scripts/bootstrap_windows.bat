@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set PYTHONUTF8=1
echo Aegis DTCG first-time bulk bootstrap (maximum about two hours).
echo Globally <=1 request/second; <=4 simultaneous network waits.
echo If the upstream throttles, the job stops and saves current progress.
py -m pip install -r requirements.txt || goto fail
echo [1/3] Discover remaining packages (maximum 3 minutes)...
py tools\index_packages.py --limit 175 --delay 1 --time-budget-seconds 180 || goto fail
echo [2/3] Import all known card texts with a 110-minute cap...
py tools\fast_bootstrap.py --max-cards 6000 --workers 4 --min-interval 1 --time-budget-minutes 110 || goto fail
echo [3/3] Validate and record completion status...
py tools\validate_database.py || goto fail
py tools\check_bootstrap.py || goto fail
echo.
echo Finished within time budget. Review data/ and run git add/commit/push to publish.
echo A full 100 percent coverage result depends on DigiCamoe availability.
pause
exit /b 0
:fail
echo Stopped due to error or upstream limit. Any saved checkpoints remain in data/.
echo Do not rapidly rerun after an HTTP 429.
pause
exit /b 1

@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set PYTHONUTF8=1
echo Aegis DTCG: initial bulk Chinese card database bootstrap.
echo Requests are single-threaded with at least 6 seconds between requests.
echo Stop with Ctrl+C; progress already written to data files is retained.
py -m pip install -r requirements.txt || goto fail
echo [1/3] Discover existing card packages and card numbers...
py tools\index_packages.py --limit 175 --delay 6 || goto fail
py tools\index_packages.py --limit 175 --delay 6 || goto fail
echo [2/3] Pull Chinese card details in resumable groups...
for /L %%G in (1,1,12) do (
  echo Running batch %%G / 12 ...
  py tools\sync_cards.py --limit 600 --delay 6 --time-budget-minutes 100
  if errorlevel 1 goto fail
  py tools\validate_database.py
  if errorlevel 1 goto fail
)
echo [3/3] Evaluate transition to 20-card daily maintenance...
py tools\check_bootstrap.py || goto fail
echo.
echo Results saved in data\cards. Review, then commit/push to GitHub.
echo Do NOT commit cookies or authentication data.
pause
exit /b 0
:fail
echo Paused because of a network/rate-limit/parsing error.
echo Already-saved progress is preserved. Avoid immediate reruns if rate-limited.
pause
exit /b 1

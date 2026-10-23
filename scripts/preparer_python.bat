@echo off
rem ==== A double-cliquer UNE FOIS : prepare Python portable dans ce dossier (aucune installation sur le PC) ====
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0preparer_python.ps1"
echo.
if errorlevel 1 (echo ECHEC - voir le message ci-dessus) else (echo Termine.)
pause

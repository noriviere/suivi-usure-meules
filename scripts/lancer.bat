@echo off
rem ==== Lanceur : a double-cliquer sur n'importe quel PC (le dossier peut etre sur le reseau) ====
rem  1. si le serveur habituel repond : ouvre simplement la page
rem  2. sinon : demarre un serveur temporaire sur CE PC (arret auto apres 30 min sans utilisation)
setlocal
pushd "%~dp0.."
set "SERVEUR=localhost:8000"
if exist "config\serveur.txt" set /p SERVEUR=<"config\serveur.txt"

call :tester %SERVEUR%
if "%OK%"=="1" goto ouvrir_serveur

echo Le serveur (%SERVEUR%) ne repond pas.
echo Demarrage d'un serveur temporaire sur ce PC, patientez...
start "Serveur meules (temporaire)" /min "%~dp0serveur_temporaire.bat"
set N=0
:attente
call :tester localhost:8000
if "%OK%"=="1" goto ouvrir_local
set /a N+=1
if %N% GEQ 40 goto echec
timeout /t 1 /nobreak >nul
goto attente

:ouvrir_serveur
start "" "http://%SERVEUR%/"
exit /b 0

:ouvrir_local
start "" "http://localhost:8000/"
exit /b 0

:echec
echo Le serveur n'a pas demarre. Regardez la fenetre "Serveur meules (temporaire)" ou lancez scripts\preparer_python.bat.
pause
exit /b 1

:tester
set OK=0
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://%1/sante).StatusCode } catch { 0 }" | findstr /b 200 >nul && set OK=1
exit /b 0

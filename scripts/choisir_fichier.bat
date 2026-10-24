@echo off
rem ==== Indique le classeur Excel de PRODUCTION (ecrit config\chemin_fichier.txt) ====
pushd "%~dp0.."
if not exist config mkdir config
if exist config\chemin_fichier.txt (
  echo Chemin actuel :
  type config\chemin_fichier.txt
  echo.
)
echo Collez le chemin complet du classeur (ex. D:\Meulage\suivi.xlsx ou \\SERVEUR\Partage\suivi.xlsx)
set /p "CHEMIN=Chemin : "
set "CHEMIN=%CHEMIN:"=%"
if "%CHEMIN%"=="" ( echo Rien saisi, inchange. & pause & exit /b 1 )
if not exist "%CHEMIN%" ( echo ATTENTION : ce fichier est introuvable. Verifiez le chemin. & pause & exit /b 1 )
powershell -NoProfile -Command "[IO.File]::WriteAllText((Join-Path (Get-Location) 'config\chemin_fichier.txt'), $env:CHEMIN, (New-Object Text.UTF8Encoding $false))"
echo Enregistre. Redemarrez le serveur pour appliquer.
pause

@echo off
rem ==== Met a jour le code depuis GitHub (donnees et reglages conserves) ====
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0mettre_a_jour.ps1"
if errorlevel 1 echo La mise a jour a echoue : rien n a ete supprime sans sauvegarde.
pause

@echo off
rem ==== Lance les tests unitaires du backend (aucun fichier de production n'est touche) ====
pushd "%~dp0.."
set "PY=python_portable\python.exe"
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -m unittest discover -s tests -t . -v
pause

@echo off
rem ==== Lance l application en mode DEMO (fausses donnees, sans Excel) ====
setlocal
pushd "%~dp0.."
set "PY=python_portable\python.exe"
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set MEULES_DEMO=1
echo Demo : http://localhost:8000   (compte du back-office : demo / demo-meules)
start "" http://localhost:8000
"%PY%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause

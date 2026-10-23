@echo off
rem Lance par lancer.bat quand le serveur habituel est eteint. Se ferme tout seul apres 30 min sans utilisation.
pushd "%~dp0.."
set "PY=python_portable\python.exe"
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set ARRET_INACTIF_MIN=30
title Serveur meules (temporaire)
"%PY%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause

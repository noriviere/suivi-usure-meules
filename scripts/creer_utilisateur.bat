@echo off
rem ==== Cree le premier compte du back-office (ou change un mot de passe oublie) ====
pushd "%~dp0.."
set "PY=python_portable\python.exe"
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" scripts\creer_utilisateur.py
pause

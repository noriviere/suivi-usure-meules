@echo off
rem ==== Lance l'analyse statique puis les tests unitaires du backend (aucun fichier de production n'est touche) ====
pushd "%~dp0.."
set "PY=python_portable\python.exe"
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -m pyflakes --version >nul 2>&1
if errorlevel 1 (
  echo pyflakes absent : analyse statique sautee. Pour l'activer : "%PY%" -m pip install pyflakes
) else (
  echo Analyse statique : noms non definis, imports oublies...
  "%PY%" -m pyflakes backend outils tests scripts
  if errorlevel 1 echo ATTENTION : pyflakes signale des erreurs ci-dessus.
)
"%PY%" -m unittest discover -s tests -t . -v
pause

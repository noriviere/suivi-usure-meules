@echo off
rem ==== Serveur permanent (PC serveur) ====
rem A mettre dans le dossier Demarrage de Windows (Win+R, taper shell:startup, y glisser un RACCOURCI de ce fichier,
rem proprietes du raccourci > Executer : Reduite). Il redemarre tout seul si le serveur s'arrete.
rem Fonctionne aussi si le dossier est sur le reseau (\\serveur\partage\...).
pushd "%~dp0.."
set "PY=python_portable\python.exe"
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
title Serveur saisie meules - NE PAS FERMER
echo Nom de ce PC : %COMPUTERNAME%  (les autres PC ouvrent http://%COMPUTERNAME%:8000)
if not exist data mkdir data
:boucle
echo [%date% %time%] demarrage >> data\serveur_prod.log
"%PY%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 >> data\serveur_prod.log 2>&1
echo [%date% %time%] arret, redemarrage dans 5 s >> data\serveur_prod.log
timeout /t 5 /nobreak >nul
goto boucle

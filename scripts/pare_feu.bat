@echo off
rem ==== A lancer UNE FOIS sur le PC serveur : clic droit > Executer en tant qu'administrateur ====
net session >nul 2>&1
if errorlevel 1 (
  echo Ce fichier doit etre lance en administrateur : clic droit, "Executer en tant qu'administrateur".
  pause
  exit /b 1
)
netsh advfirewall firewall delete rule name="Saisie meules" >nul 2>&1
netsh advfirewall firewall add rule name="Saisie meules" dir=in action=allow protocol=TCP localport=8000 profile=private,domain
echo.
echo Port 8000 ouvert pour le reseau de l'entreprise.
echo Nom de ce PC : %COMPUTERNAME%
echo Adresse(s) IP :
ipconfig | findstr /i "IPv4"
echo.
echo Sur les autres PC, ecrivez  %COMPUTERNAME%:8000  dans le fichier config\serveur.txt
pause

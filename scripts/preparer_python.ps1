# Prepare un Python PORTABLE dans le dossier "python_portable" (rien n'est installe sur le PC, pas besoin d'etre administrateur).
# A lancer UNE FOIS via preparer_python.bat. Necessite internet, SAUF si le dossier "installeurs" contient deja les fichiers
# (python-...-embed-amd64.zip, get-pip.py et le dossier wheels) : dans ce cas tout se fait hors ligne.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ver   = "3.12.8"
$court = "312"
$racine = Split-Path -Parent $PSScriptRoot      # dossier mon-app (ce script est dans scripts)
$dest   = Join-Path $racine "python_portable"
$inst   = Join-Path $racine "installeurs"
$wheels = Join-Path $inst "wheels"
$paquets = @("fastapi", "uvicorn", "openpyxl", "pywin32")
New-Item -ItemType Directory -Force $inst | Out-Null

function Telecharger($url, $fichier) {
    if (Test-Path $fichier) { Write-Host "  deja present : $fichier"; return }
    Write-Host "  telechargement : $url"
    Invoke-WebRequest -Uri $url -OutFile $fichier -UseBasicParsing
}

Write-Host "1/5  Python $ver portable"
$zip = Join-Path $inst "python-$ver-embed-amd64.zip"
if (-not (Test-Path (Join-Path $dest "python.exe"))) {
    Telecharger "https://www.python.org/ftp/python/$ver/python-$ver-embed-amd64.zip" $zip
    Expand-Archive -Path $zip -DestinationPath $dest -Force
}
$py = Join-Path $dest "python.exe"

Write-Host "2/5  Configuration (fichier ._pth)"
$pth = Join-Path $dest "python$court._pth"
@("python$court.zip", ".", "Lib\site-packages", "Lib\site-packages\win32", "Lib\site-packages\win32\lib",
  "Lib\site-packages\Pythonwin", "..", "import site") | Set-Content -Path $pth -Encoding ASCII

Write-Host "3/5  pip"
$getpip = Join-Path $inst "get-pip.py"
if (-not (Test-Path (Join-Path $dest "Lib\site-packages\pip"))) {
    Telecharger "https://bootstrap.pypa.io/get-pip.py" $getpip
    & $py $getpip --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw "get-pip a echoue" }
}

Write-Host "4/5  Paquets : $($paquets -join ', ')"
if ((Test-Path $wheels) -and (Get-ChildItem $wheels -Filter *.whl -ErrorAction SilentlyContinue)) {
    Write-Host "  mode hors ligne (dossier installeurs\wheels)"
    & $py -m pip install --no-index --find-links $wheels --no-warn-script-location @paquets
} else {
    & $py -m pip install --no-warn-script-location @paquets
    if ($LASTEXITCODE -eq 0) {
        New-Item -ItemType Directory -Force $wheels | Out-Null           # copie pour une future installation hors ligne
        & $py -m pip download -d $wheels @paquets 2>$null | Out-Null
    }
}
if ($LASTEXITCODE -ne 0) { throw "L'installation des paquets a echoue" }

Write-Host "5/5  Pilotage d'Excel (pywin32)"
$dll = Join-Path $dest "Lib\site-packages\pywin32_system32"
if (Test-Path $dll) { Copy-Item (Join-Path $dll "*.dll") $dest -Force }

Write-Host "Verification..."
& $py -c "import fastapi, uvicorn, openpyxl, pythoncom, win32com.client; print('Tout est OK')"
if ($LASTEXITCODE -ne 0) { throw "La verification a echoue : envoyez ce message a Claude" }

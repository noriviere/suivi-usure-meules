# Met a jour le code depuis GitHub sans toucher aux donnees (data\, chemin_fichier.txt, serveur.txt, Python portable).
$ErrorActionPreference = "Stop"
$racine = Split-Path -Parent $PSScriptRoot
$depot = "https://github.com/noriviere/suivi-usure-meules/archive/refs/heads/main.zip"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Le serveur doit etre arrete (sinon des fichiers sont verrouilles)
$ecoute = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($ecoute) { Write-Host "Le serveur tourne encore (port 8000). Arretez-le puis relancez cette mise a jour." -ForegroundColor Red; exit 1 }

$temp = Join-Path $env:TEMP ("meules_maj_" + (Get-Date -Format "yyyyMMddHHmmss"))
New-Item -ItemType Directory -Path $temp | Out-Null
try {
  Write-Host "Telechargement depuis GitHub..."
  Invoke-WebRequest -Uri $depot -OutFile (Join-Path $temp "depot.zip") -UseBasicParsing
  Expand-Archive -Path (Join-Path $temp "depot.zip") -DestinationPath $temp
  $source = Get-ChildItem $temp -Directory | Select-Object -First 1
  if (-not (Test-Path (Join-Path $source.FullName "backend\main.py"))) { throw "Archive inattendue : backend\main.py absent." }

  # Sauvegarde de l'ancien code
  $archive = Join-Path $racine ("archive_" + (Get-Date -Format "yyyyMMdd_HHmm"))
  New-Item -ItemType Directory -Path $archive | Out-Null
  $elements = @("backend", "frontend", "outils", "tests", "scripts", "config\champs.json", "requirements.txt", "README.md")
  foreach ($element in $elements) {
    $ancien = Join-Path $racine $element
    if (Test-Path $ancien) {
      $cible = Join-Path $archive $element
      New-Item -ItemType Directory -Path (Split-Path -Parent $cible) -Force | Out-Null
      Copy-Item $ancien $cible -Recurse -Force
    }
  }
  Write-Host "Ancien code sauvegarde dans $archive"

  # Nouveau code (les dossiers sont remplaces ; data, config\chemin_fichier.txt et serveur.txt ne sont pas touches)
  foreach ($dossier in @("backend", "frontend", "outils", "tests")) {
    $cible = Join-Path $racine $dossier
    if (Test-Path $cible) { Remove-Item $cible -Recurse -Force }
    Copy-Item (Join-Path $source.FullName $dossier) $cible -Recurse
  }
  New-Item -ItemType Directory -Path (Join-Path $racine "config") -Force | Out-Null
  Copy-Item (Join-Path $source.FullName "config\champs.json") (Join-Path $racine "config\champs.json") -Force
  foreach ($fichier in @("requirements.txt", "README.md", "CONTRIBUTING.md")) {
    Copy-Item (Join-Path $source.FullName $fichier) (Join-Path $racine $fichier) -Force
  }
  # scripts : tout sauf cette mise a jour en cours d'execution
  New-Item -ItemType Directory -Path (Join-Path $racine "scripts") -Force | Out-Null
  Get-ChildItem (Join-Path $source.FullName "scripts") -File | Where-Object { $_.Name -notlike "mettre_a_jour.*" } |
    ForEach-Object { Copy-Item $_.FullName (Join-Path $racine "scripts") -Force }
  Write-Host ""
  Write-Host "Mise a jour terminee. Relancez le serveur (scripts\serveur_prod.bat)." -ForegroundColor Green
  Write-Host "Si le fichier requirements.txt a change, relancez aussi scripts\preparer_python.bat."
} finally {
  Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
}

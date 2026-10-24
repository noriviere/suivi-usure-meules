#!/usr/bin/env sh
# Lance l'application en mode DEMO (fausses données, sans Excel) : Linux, macOS, Codespaces.
cd "$(dirname "$0")/.." || exit 1
export MEULES_DEMO=1
if [ ! -d .venv-demo ]; then python3 -m venv .venv-demo || { echo "Impossible de creer l'environnement Python (paquet python3-venv ?)"; exit 1; }; fi
. .venv-demo/bin/activate || exit 1
pip install --quiet fastapi uvicorn openpyxl || { echo "Installation des dependances impossible"; exit 1; }
echo "Demo : http://localhost:8000   (compte du back-office : demo / demo-meules)"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

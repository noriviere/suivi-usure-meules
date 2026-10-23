#!/usr/bin/env sh
# Lance l'application en mode DEMO (fausses données, sans Excel) : Linux, macOS, Codespaces.
cd "$(dirname "$0")/.." || exit 1
export MEULES_DEMO=1
python3 -m pip install --quiet fastapi uvicorn openpyxl
echo "Demo : http://localhost:8000   (compte du back-office : demo / demo-meules)"
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

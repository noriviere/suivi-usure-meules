#!/bin/bash
# Démarrage d'une session Claude Code dans le cloud : dépendances des tests et hook pre-commit (pyflakes + tests).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Dépendances de l'application (pywin32 est ignoré hors Windows) et de l'analyse statique.
# pip installe dans le Python du système : rien à mettre en cache, pip ne refait rien si tout est déjà là.
python3 -m pip install --quiet --disable-pip-version-check --root-user-action=ignore -r requirements.txt pyflakes

# Chaque session repart d'une copie neuve du dépôt : on réactive les hooks Git versionnés (.githooks).
git config core.hooksPath .githooks

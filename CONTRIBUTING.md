# Contribuer

## Règle d'or : aucune donnée réelle dans le dépôt

Ni classeur Excel, ni base SQLite, ni journal de saisie, ni chemin de serveur, ni matricule ou nom de personne réel.
Le `.gitignore` et la CI bloquent les cas courants, mais la vérification finale est la vôtre. Pour tester, utilisez le mode
démo (`MEULES_DEMO=1`, voir le README) ou une **copie** du classeur, jamais le fichier de production.

## Déroulement

1. Créer une branche à partir de `main` : `git switch -c ma-modification`.
2. Modifier, puis lancer les tests : `python -m unittest discover -s tests -t .`
3. Si la page web ou les règles de saisie ont changé : `python -m outils.construire_demo_web`, puis commiter `docs/`.
4. Ouvrir une demande de fusion (pull request) vers `main`. Le modèle de description rappelle les vérifications.
5. La CI (GitHub Actions) doit être verte. Une relecture est demandée avant la fusion.

## Conventions

- Code et noms en français, comme le reste du projet ; noms de variables explicites (pas de lettres seules).
- Logique métier dans `backend/services/` (testée) ; les routes restent fines.
- Toute écriture passe par `ecriture.ajouter_ligne`, qui porte le déroulé (verrou, copie de sécurité, onglet Data défaut, contrôle des colonnes).
  Le classeur est manipulé par un adapter : Excel (COM, `classeur_excel.py`) en production, openpyxl (`classeur_openpyxl.py`) **uniquement** en mode démo et dans les tests.
- Les fichiers `.bat` sont en ASCII avec fins de ligne CRLF.
- Toute règle de saisie ajoutée côté Python (`valider.py`, `regles.py`) doit être reportée dans `demo_web/demo-api.js` ;
  `tests/test_demo_web.py` signale les écarts (Node.js requis pour ce test).

## Signaler un problème

Ouvrir une « issue » en décrivant ce qui est attendu, ce qui se passe, et comment le reproduire avec la démo si possible.
Ne joindre aucune capture ni extrait montrant des données réelles.

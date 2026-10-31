# Suivi d'usure des meules

Application web interne pour saisir et consulter le suivi d'usure des meules d'un atelier de meulage.
Elle lit et écrit dans un classeur Excel existant, qui reste la seule source des données métier.

*Python 3.12 · FastAPI · HTML/CSS/JavaScript · SQLite · Excel (COM) · Windows*

**Démo en ligne (données entièrement inventées) : https://noriviere.github.io/suivi-usure-meules/**
Aucune donnée réelle n'est dans ce dépôt : ni classeur, ni base, ni journal, ni matricule.

## Essayer l'application sans Excel (démo)

| Façon | Comment |
| --- | --- |
| Dans le navigateur, sans rien installer | Ouvrir la démo en ligne ci-dessus. Les contrôles de saisie, la barre de chargement et la consultation fonctionnent ; rien n'est enregistré. |
| Sur un PC (Windows, Linux, macOS) | `scripts\lancer_demo.bat` ou `sh scripts/lancer_demo.sh`, puis http://localhost:8000. Le vrai serveur tourne, avec un classeur fictif créé dans `data/demo/`. Compte du back-office : `demo` / `demo-meules`. |
| Dans le cloud | Bouton **Code → Codespaces** du dépôt : l'environnement démarre tout seul en mode démo (`.devcontainer/`). |

Le mode démo est activé par la variable d'environnement `MEULES_DEMO=1`. Il n'utilise jamais Excel ni le vrai classeur :
les écritures passent par l'adapter `backend/services/classeur_openpyxl.py` sur le classeur fictif de `outils/donnees_fictives.py`.

La démo en ligne (`docs/`) est un site statique : `demo_web/demo-api.js` rejoue dans le navigateur les contrôles du serveur.
Après une modification de la page ou des règles, la régénérer avec `python -m outils.construire_demo_web` et commiter `docs/`
(`--check` vérifie que `docs/` est à jour sans rien écrire, et la CI le lance ; et `tests/test_demo_web.py` compare les verdicts JavaScript et Python).

## Structure du projet

```
mon-app/
├── backend/                 Serveur FastAPI
│   ├── main.py              Point d'entrée (pages, fichiers statiques, arrêt automatique)
│   ├── config.py            Chemins et réglages généraux
│   ├── routes/              Routes HTTP, fines : saisie.py, consultation.py, admin.py
│   ├── services/            Logique métier (testée) : validation, règles, lecture et écriture Excel, contrôle qualité
│   └── auth/                Comptes, mots de passe, sessions, base SQLite
├── frontend/
│   ├── html/                Pages : index.html (saisie), consultation.html, admin.html
│   ├── css/                 Styles
│   ├── js/                  saisie.js, consultation.js, admin.js, commun.js
│   └── img/                 Images (étiquettes des meules)
├── config/
│   ├── champs.json          Champs du formulaire et valeurs d'origine des règles
│   ├── chemin_fichier.txt   Chemin du classeur Excel (à créer, une ligne)
│   └── serveur.txt          Adresse du serveur, pour scripts\lancer.bat
├── data/                    Base SQLite, journal des saisies (créés au lancement)
├── tests/                   Tests unitaires du backend (et parité démo JavaScript / Python)
├── demo_web/                demo-api.js : faux serveur JavaScript de la démo en ligne
├── docs/                    Démo en ligne générée (GitHub Pages) : ne pas modifier à la main
├── scripts/                 Lancement, installation de Python portable, création d'un compte, tests
├── outils/                  nettoyage.py (nettoyage du classeur, à la main), donnees_fictives.py, construire_demo_web.py
└── requirements.txt
```

## Fonctionnalités

**Saisie** (ouverte à tous les postes de l'atelier, sans connexion)

- Formulaire guidé en deux parties (monteur, démonteur), listes et valeurs déduites du classeur.
- Contrôles bloquants (limites, cohérence des compteurs et des hauteurs) et avertissements non bloquants
  (valeur inhabituelle, doublon, matricule inconnu, meule ou machine non prévue).
- Écriture dans Excel (COM) : formules et mise en forme de la ligne précédente recopiées. Avant chaque écriture, le classeur est copié dans `data/sauvegardes` (les 30 dernières copies sont gardées) ; si la copie échoue, la saisie continue et l'erreur s'affiche dans la fenêtre du serveur.
- Une meule cassée et non finie est aussi copiée dans l'onglet « Data défaut ».

**Consultation** (lecture seule, sans connexion)

- Contenu du classeur, statistiques par référence avec évolution de la médiane, contrôle qualité exportable en CSV.

**Back-office** (`/admin`, réservé aux comptes enregistrés)

- Section *Comptes* : créer et supprimer des comptes, réinitialiser un mot de passe, changer son propre nom
  d'utilisateur et son propre mot de passe. Un seul type de compte : tous les comptes ont les mêmes droits.
- Section *Règles métier* : interrupteur et valeurs de chaque règle de vérification (seuil de meule non finie,
  limites, coefficients, prix d'une meule moyenne). Chaque changement est noté dans un historique.
- Section *Affichage* : interrupteur « messages humoristiques » pour la barre de chargement de l'enregistrement.
  Pendant l'enregistrement, la page de saisie est bloquée et une barre indique l'étape en cours.
  Les durées de chaque étape sont notées dans `data/journal_chrono.csv` (une ligne par saisie, en secondes).

## Installation

Prérequis : un PC Windows avec Excel et une session ouverte (Excel est piloté par COM). Aucune installation de Python
n'est nécessaire.

1. Copier le dossier (sur le PC serveur ou sur un partage réseau).
2. Lancer `scripts\preparer_python.bat` une seule fois (Python portable dans le dossier ; doit finir par « Tout est OK »).
3. Indiquer le classeur de production : `scripts\choisir_fichier.bat` (demande le chemin complet, y compris un partage réseau, et l'écrit dans `config\chemin_fichier.txt`). Sans cela, l'application prend `data\classeur_meules.xlsx`, ou à défaut le `.xlsx` le plus récent du dossier `data`.
4. Créer le premier compte du back-office : `scripts\creer_utilisateur.bat`.
5. Sur le PC serveur, lancer `scripts\pare_feu.bat` en administrateur (ouvre le port TCP 8000).
6. Tester avec `scripts\serveur_prod.bat` puis ouvrir `http://localhost:8000`. Pour un démarrage automatique,
   placer un raccourci vers `scripts\serveur_prod.bat` dans `shell:startup`.

Avec un Python déjà installé : `pip install -r requirements.txt`, puis
`python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000` depuis ce dossier.

## Mise à jour

Arrêter le serveur, puis lancer `scripts\mettre_a_jour.bat` : il télécharge la dernière version depuis GitHub, sauvegarde l'ancien code dans `archive_AAAAMMJJ_HHMM` et remplace le code. Le dossier `data` (base, journaux, classeur), `config\chemin_fichier.txt` et `config\serveur.txt` ne sont pas touchés. Sont remplacés : `backend`, `frontend` (y compris `frontend\img`), `outils`, `tests`, `scripts` (sauf `mettre_a_jour.*`), `config\champs.json` : toute personnalisation locale de ces fichiers est écrasée, mais retrouvable dans l'archive. Si `requirements.txt` a changé, relancer `scripts\preparer_python.bat`.

## Utilisation

| Adresse | Page |
| --- | --- |
| `http://<serveur>:8000/` | Saisie d'une meule |
| `http://<serveur>:8000/consultation` | Consultation et statistiques |
| `http://<serveur>:8000/admin` | Back-office (connexion requise) |

`scripts\lancer.bat` ouvre la page du serveur indiqué dans `config\serveur.txt`. Si ce serveur est éteint, il démarre
un serveur temporaire sur le PC courant, qui s'arrête seul après 30 minutes sans utilisation.

## Tests

Les tests couvrent uniquement la logique du backend (comptes et mots de passe, sessions, règles métier, validation,
lecture du classeur, contrôle qualité). Ils travaillent sur une base et un classeur temporaires, jamais sur les vraies données.

```
python -m unittest discover -s tests -t . -v
```

ou `scripts\tests.bat`. Seul `openpyxl` est nécessaire (`pip install openpyxl`) ; le test de la démo en ligne utilise Node.js s'il est présent.

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md) : branche + demande de fusion (pull request), tests obligatoires, aucune donnée réelle.

## Sécurité

- Les mots de passe sont hachés avec scrypt (bibliothèque standard) ; ils ne sont jamais stockés ni renvoyés en clair.
- La session est un cookie signé, `HttpOnly` et `SameSite=Strict`, valable 8 heures. Changer ou réinitialiser un mot de passe
  ferme les sessions ouvertes du compte concerné.
- Cinq échecs de connexion bloquent le nom d'utilisateur et le poste pendant cinq minutes.
- Aucune inscription par le web : les comptes sont créés depuis le back-office, le premier par `scripts\creer_utilisateur.bat`.
  Le même script sert à changer un mot de passe oublié.
- La communication se fait en HTTP, sans chiffrement : à réserver au réseau interne. Placer l'application derrière un
  proxy HTTPS (et passer `secure=True` sur le cookie dans `backend/routes/admin.py`) si l'accès sort du réseau de l'entreprise.
- Limites assumées : le blocage après 5 échecs est mémorisé en mémoire (il repart à zéro quand le serveur redémarre) et porte sur le nom et sur le poste : derrière une même adresse, un essai répété peut bloquer d'autres postes pendant 5 minutes. « Se déconnecter » ferme toutes les sessions du compte, sur tous les postes.
- Chaque saisie lance Excel côté serveur : les pages de saisie étant ouvertes à tout le réseau interne, ne pas exposer le port 8000 hors de l'entreprise.
- Les pages de saisie et de consultation restent ouvertes, comme avant. Seuls les comptes et les règles métier sont protégés.

## Limites connues

- Une seule écriture dans Excel à la fois ; si le classeur est ouvert et verrouillé, la saisie est refusée avec un message
  et peut être renvoyée.
- Le serveur doit tourner sur un PC Windows avec Excel et une session ouverte.
- Les règles modifiées dans le back-office remplacent les valeurs de `config/champs.json` ; le bouton
  « Revenir aux valeurs d'origine » les remet.

## Dépannage

| Symptôme | Piste |
| --- | --- |
| « Fichier occupé » | Le classeur est ouvert : fermer Excel puis réessayer |
| « Colonnes introuvables » | Un en-tête du classeur a été renommé : voir `config/champs.json` |
| Page inaccessible depuis un autre poste | Serveur éteint, pare-feu (port 8000) ou nom du serveur dans `config\serveur.txt` |
| « Aucun compte n'existe encore » sur `/admin` | Lancer `scripts\creer_utilisateur.bat` |
| Mot de passe oublié | Relancer `scripts\creer_utilisateur.bat` avec le même nom d'utilisateur |

# Suivi d'usure des meules

Application d'atelier qui recueille les fiches de montage et de démontage des meules et les reporte dans le classeur Excel de l'atelier, pour suivre leur usure.

## Langage

### Classeur

**Classeur** :
Le fichier Excel de référence de l'atelier, où chaque saisie devient une ligne.
_À éviter_ : fichier, base, Excel

**Onglet Data** :
L'onglet du classeur qui reçoit toutes les saisies.

**Onglet Data défaut** :
L'onglet du classeur où l'on copie aussi les saisies d'une meule défectueuse.
_À éviter_ : onglet défaut, onglet des défauts

**Colonnes calculées** :
Les colonnes du classeur remplies par ses formules (usure, faces par mm...), jamais saisies.

### Saisie

**Saisie** :
Une fiche de montage ou de démontage d'une meule, envoyée depuis un poste de l'atelier.
_À éviter_ : entrée, ligne, enregistrement

**Meule défectueuse** :
Une meule démontée avant usure totale dont le commentaire signale « Meule cassée ou fissurée ».
_À éviter_ : défaut, meule en défaut

### Démo

**Démo en ligne** :
Le site public qui montre l'application avec des données entièrement inventées ; les saisies y sont contrôlées comme en vrai mais ne sont enregistrées nulle part.
_À éviter_ : démo web, site de démo, GitHub Pages

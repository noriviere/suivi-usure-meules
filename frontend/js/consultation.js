"use strict";
/* ---------- utilitaires (h() est dans commun.js) ---------- */
const norm = texte => String(texte ?? "").trim().toLowerCase().replace(/\s+/g, " ");
const fmt = (nombre, decimales = 2) => nombre == null || !Number.isFinite(nombre) ? "—" : nombre.toLocaleString("fr-FR", { maximumFractionDigits: decimales });
const isNum = valeur => typeof valeur === "number" && Number.isFinite(valeur);
const SVGNS = "http://www.w3.org/2000/svg";
const sv = (tag, attrs = {}, ...enf) => {
  const element = document.createElementNS(SVGNS, tag);
  for (const [cle, valeur] of Object.entries(attrs)) element.setAttribute(cle, valeur);
  element.append(...enf);
  return element;
};

let TABLEAU, CFG, IDX = {}, LIGNES = [];
let LIBMAT = {};

/* ---------- statistiques ---------- */
function quantile(tri, proportion) {                    // méthode « inclusive » (comme Excel QUARTILE.INC)
  if (!tri.length) return null;
  const pos = (tri.length - 1) * proportion, indice_bas = Math.floor(pos), fraction = pos - indice_bas;
  return indice_bas + 1 < tri.length ? tri[indice_bas] + fraction * (tri[indice_bas + 1] - tri[indice_bas]) : tri[indice_bas];
}
function stats(valeurs) {
  const tri = valeurs.filter(isNum).sort((premier, deuxieme) => premier - deuxieme), effectif = tri.length;
  if (!effectif) return { effectif: 0 };
  const moy = tri.reduce((somme, valeur) => somme + valeur, 0) / effectif;
  const sd = effectif > 1 ? Math.sqrt(tri.reduce((somme, valeur) => somme + (valeur - moy) ** 2, 0) / (effectif - 1)) : null;
  return { effectif, moy, sd, med: quantile(tri, .5), q1: quantile(tri, .25), q3: quantile(tri, .75), min: tri[0], max: tri[effectif - 1] };
}
function fiabilite(effectif) {
  if (effectif < 5) return ["trop peu de données", "bas"];
  if (effectif < 20) return ["indicatif", "moyen"];
  return ["fiable", "haut"];
}

/* ---------- chargement ---------- */
async function getJSON(url) { const reponse = await fetch(url); if (!reponse.ok) throw new Error(url + " " + reponse.status); return reponse.json(); }

async function init() {
  try {
    [TABLEAU, CFG] = await Promise.all([getJSON("/api/donnees"), getJSON("/api/champs")]);
  } catch (erreur) {
    document.getElementById("p-donnees").replaceChildren(creerElement("p", { class: "vide", text: "Impossible de lire le fichier. Il est peut‑être occupé : réessayez dans un instant." }));
    return;
  }
  TABLEAU.cles.forEach((cle, position) => IDX[cle] = position + 1);               // +1 : colonne 0 = n° de ligne Excel
  const mat = CFG.champs.find(champ => champ.nom === "Matière");
  LIBMAT = (mat && mat.affichage_valeurs) || {};
  LIGNES = TABLEAU.lignes;
  construireDonnees(); construireStats();
  document.querySelectorAll(".onglet").forEach(onglet => onglet.addEventListener("click", () => {
    document.querySelectorAll(".onglet").forEach(onglet => onglet.setAttribute("aria-selected", String(onglet === onglet)));
    for (const panneau of ["donnees", "stats", "qualite"]) document.getElementById("p-" + panneau).hidden = panneau !== onglet.dataset.panneau;
    if (onglet.dataset.panneau === "qualite" && !qualiteChargee) construireQualite();
  }));
}

/* ======================================================================
   1. Contenu du fichier
   ====================================================================== */
function construireDonnees() {
  const racine = document.getElementById("p-donnees");
  let filtre = "", tri = { col: 0, sens: -1 }, page = 0;
  const TAILLE = 50;
  const recherche = creerElement("input", { type: "search", placeholder: "Rechercher (meule, machine, matricule, commentaire…)" });
  const compte = creerElement("span", { class: "petit" });
  const corps = creerElement("tbody"), entete = creerElement("tr");
  const pagePrec = creerElement("button", { type: "button", class: "bouton secondaire petit-b", text: "← Précédent" });
  const pageSuiv = creerElement("button", { type: "button", class: "bouton secondaire petit-b", text: "Suivant →" });
  const info = creerElement("span", { class: "petit" });

  ["Ligne", ...TABLEAU.entetes].forEach((titre_colonne, position) => {
    const th = creerElement("th", { text: titre_colonne, title: "Trier" });
    th.addEventListener("click", () => { tri = { col: position, sens: tri.col === position ? -tri.sens : 1 }; page = 0; rendre(); });
    entete.append(th);
  });

  function lignesFiltrees() {
    let selection = LIGNES;
    if (filtre) {
      const recherche = norm(filtre);
      selection = selection.filter(ligne => ligne.some(valeur => valeur != null && norm(valeur).includes(recherche)));
    }
    const colonne = tri.col;
    return [...selection].sort((premiere, seconde) => {
      const valeur_premiere = premiere[colonne], valeur_seconde = seconde[colonne];
      if (valeur_premiere == null) return 1; if (valeur_seconde == null) return -1;
      return (isNum(valeur_premiere) && isNum(valeur_seconde) ? valeur_premiere - valeur_seconde : String(valeur_premiere).localeCompare(String(valeur_seconde), "fr", { numeric: true })) * tri.sens;
    });
  }
  function rendre() {
    const selection = lignesFiltrees(), pages = Math.max(1, Math.ceil(selection.length / TAILLE));
    page = Math.min(page, pages - 1);
    corps.replaceChildren(...selection.slice(page * TAILLE, (page + 1) * TAILLE).map(ligne =>
      creerElement("tr", {}, ...ligne.map((valeur, position) => creerElement("td", { class: isNum(valeur) ? "n" : "", text: valeur == null ? "" : isNum(valeur) ? fmt(valeur, 3) : (position === IDX["matière"] ? (LIBMAT[valeur] || valeur) : String(valeur)) })))));
    compte.textContent = `${selection.length.toLocaleString("fr-FR")} ligne(s)` + (filtre ? " correspondant à la recherche" : "") + " sur " + LIGNES.length.toLocaleString("fr-FR");
    info.textContent = `Page ${page + 1} / ${pages}`;
    pagePrec.disabled = page === 0; pageSuiv.disabled = page >= pages - 1;
  }
  recherche.addEventListener("input", () => { filtre = recherche.value; page = 0; rendre(); });
  pagePrec.addEventListener("click", () => { page--; rendre(); });
  pageSuiv.addEventListener("click", () => { page++; rendre(); });

  racine.append(
    creerElement("div", { class: "barre" }, creerElement("label", {}, "Recherche", recherche)),
    compte,
    creerElement("div", { class: "defile" }, creerElement("table", { class: "t" }, creerElement("thead", {}, entete), corps)),
    creerElement("div", { class: "pages" }, pagePrec, info, pageSuiv),
    creerElement("p", { class: "petit", text: "Lecture seule : cette page ne modifie jamais le fichier. Cliquez sur un titre de colonne pour trier. « Ligne » = numéro de ligne dans Excel." }));
  rendre();
}

/* ======================================================================
   2. Statistiques
   ====================================================================== */
const annee = ligne => { const date = ligne[IDX["date montage"]]; return typeof date === "string" && date[4] === "-" ? +date.slice(0, 4) : null; };
const moisNum = ligne => { const date = ligne[IDX["date montage"]]; return typeof date === "string" && date[4] === "-" ? +date.slice(5, 7) : null; };
const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

function construireStats() {
  const racine = document.getElementById("p-stats");
  const DIMS = [
    { id: "format", lab: "Format", get: ligne => ligne[IDX["format"]] },
    { id: "matiere", lab: "Matière", get: ligne => ligne[IDX["matière"]], aff: valeur => LIBMAT[valeur] || valeur },
    { id: "machine", lab: "Machine", get: ligne => ligne[IDX["n° de machine"]] },
    { id: "article", lab: "N° article meule", get: ligne => ligne[IDX["n° article meule"]] },
    { id: "face", lab: "Face", get: ligne => ligne[IDX["face"]] },
    { id: "fournisseur", lab: "Fournisseur", get: ligne => ligne[IDX["fournisseur"]] },
    { id: "annee", lab: "Année", get: annee },
    { id: "mois", lab: "Mois", get: moisNum, aff: numero => MOIS[numero - 1] },
  ].filter(dimension => dimension.id === "annee" || dimension.id === "mois" ? IDX["date montage"] : true);
  const METRIQUES = [
    ["nb faces/meule de 89 mm", "Nb de faces par meule de 89 mm"],
    ["ht usée par face, mm", "Hauteur usée par face (mm)"],
    ["nb faces/mm", "Nb de faces par mm"],
    ["compteur fin", "Compteur fin"],
    ["ht.usée, mm", "Hauteur usée totale (mm)"],
  ].filter(metrique => IDX[metrique[0]]);

  const etat = { filtres: {}, groupe: "", metrique: METRIQUES[0][0], minN: 5, inclureNonFinies: true, ecarter: false, pas: "mois" };
  const selects = {};

  const valeursDe = dimension => [...new Set(LIGNES.map(dimension.get).filter(valeur => valeur != null && valeur !== ""))]
    .sort((premier, deuxieme) => isNum(premier) && isNum(deuxieme) ? premier - deuxieme : String(premier).localeCompare(String(deuxieme), "fr", { numeric: true }));

  const barreFiltres = creerElement("div", { class: "barre" });
  for (const dimension of DIMS) {
    const selecteur = creerElement("select", {}, creerElement("option", { value: "", text: "Tous" }),
      ...valeursDe(dimension).map(valeur => creerElement("option", { value: String(valeur), text: dimension.aff ? dimension.aff(valeur) : String(valeur) })));
    selecteur.addEventListener("change", () => { etat.filtres[dimension.id] = selecteur.value; maj(); });
    selects[dimension.id] = selecteur;
    barreFiltres.append(creerElement("label", {}, dimension.lab, selecteur));
  }
  const barreOptions = creerElement("div", { class: "barre" });
  const sMetrique = creerElement("select", {}, ...METRIQUES.map(metrique => creerElement("option", { value: metrique[0], text: metrique[1] })));
  sMetrique.addEventListener("change", () => { etat.metrique = sMetrique.value; maj(); });
  const sGroupe = creerElement("select", {}, creerElement("option", { value: "", text: "Aucun (ensemble)" }), ...DIMS.map(dimension => creerElement("option", { value: dimension.id, text: dimension.lab })));
  sGroupe.addEventListener("change", () => { etat.groupe = sGroupe.value; maj(); });
  const sPas = creerElement("select", {}, creerElement("option", { value: "mois", text: "Mois" }), creerElement("option", { value: "trimestre", text: "Trimestre" }), creerElement("option", { value: "annee", text: "Année" }));
  sPas.addEventListener("change", () => { etat.pas = sPas.value; maj(); });
  const iMin = creerElement("input", { type: "number", min: "1", max: "100", value: "5", style: "min-width:70px;width:80px" });
  iMin.addEventListener("input", () => { etat.minN = Math.max(1, +iMin.value || 1); maj(); });
  const cX = creerElement("input", { type: "checkbox", checked: true });
  cX.addEventListener("change", () => { etat.inclureNonFinies = cX.checked; maj(); });
  const cE = creerElement("input", { type: "checkbox" });
  cE.addEventListener("change", () => { etat.ecarter = cE.checked; maj(); });
  const raz = creerElement("button", { type: "button", class: "bouton secondaire petit-b", text: "Tout réinitialiser" });
  raz.addEventListener("click", () => { for (const selecteur of Object.values(selects)) selecteur.value = ""; etat.filtres = {}; sGroupe.value = ""; etat.groupe = ""; maj(); });
  barreOptions.append(
    creerElement("label", {}, "Grandeur étudiée", sMetrique),
    creerElement("label", {}, "Détailler par", sGroupe),
    creerElement("label", {}, "Évolution par", sPas),
    creerElement("label", {}, "Seuil de fiabilité (n min.)", iMin),
    creerElement("label", { class: "coche" }, cX, "Inclure les meules démontées avant usure (X)"),
    creerElement("label", { class: "coche" }, cE, "Écarter les valeurs très éloignées"),
    raz);

  const resume = creerElement("div"), detail = creerElement("div"), evolution = creerElement("div");
  racine.append(
    creerElement("p", { class: "petit", text: "Choisissez un ou plusieurs critères : seules les lignes qui respectent TOUS les critères sont prises en compte. Ex. Format 8 seul = tout le format 8 ; Format 8 + Machine s2 + Année 2026 = uniquement ces lignes." }),
    barreFiltres, barreOptions, resume,
    creerElement("h2", { class: "sec", text: "Détail par référence" }), detail,
    creerElement("h2", { class: "sec", text: "Évolution de la médiane dans le temps" }), evolution);

  function lignesActives() {
    const actifs = DIMS.filter(dimension => etat.filtres[dimension.id]);
    return LIGNES.filter(ligne => actifs.every(dimension => String(dimension.get(ligne)) === etat.filtres[dimension.id])
      && (etat.inclureNonFinies || ligne[IDX["meule démontée avant usure totale"]] !== "X"));
  }
  const val = ligne => { const valeur = ligne[IDX[etat.metrique]]; return isNum(valeur) ? valeur : null; };

  function ecartees(paires) {                       // zone de Tukey ×3 sur le groupe affiché
    const valeurs = paires.map(paire => paire.valeur).sort((premier, deuxieme) => premier - deuxieme);
    if (valeurs.length < 8) return paires;
    const q1 = quantile(valeurs, .25), q3 = quantile(valeurs, .75), ecart = q3 - q1;
    return paires.filter(paire => paire.valeur >= q1 - 3 * ecart && paire.valeur <= q3 + 3 * ecart);
  }
  const paires = rows => rows.map(ligne => ({ ligne, valeur: val(ligne) })).filter(paire => paire.valeur != null);

  function carte(titre, valeur, sous) { return creerElement("div", { class: "kpi" }, creerElement("small", { text: titre }), creerElement("strong", { text: valeur }), sous ? creerElement("small", { text: sous }) : null); }

  function maj() {
    const rows = lignesActives();
    let selection = paires(rows);
    const avant = selection.length;
    if (etat.ecarter) selection = ecartees(selection);
    const resume_stats = stats(selection.map(paire => paire.valeur));
    const [lib, cls] = fiabilite(resume_stats.effectif);

    resume.replaceChildren(
      creerElement("div", { class: "cartes" },
        carte("Lignes retenues", fmt(rows.length, 0), `${fmt(avant, 0)} avec une valeur`),
        carte("Valeurs utilisées (n)", fmt(resume_stats.effectif, 0), etat.ecarter && avant !== resume_stats.effectif ? `${avant - resume_stats.effectif} écartée(s)` : null),
        carte("Médiane", fmt(resume_stats.med)), carte("Moyenne", fmt(resume_stats.moy)), carte("Écart type", fmt(resume_stats.sd)),
        carte("Min – Max", resume_stats.effectif ? `${fmt(resume_stats.min)} – ${fmt(resume_stats.max)}` : "—"),
        carte("Q1 – Q3", resume_stats.effectif ? `${fmt(resume_stats.q1)} – ${fmt(resume_stats.q3)}` : "—", "50 % des valeurs")),
      creerElement("p", { class: "petit" }, "Fiabilité : ", creerElement("span", { class: "puce-f " + cls, text: lib }),
        "  (moins de 5 valeurs = trop peu ; 5 à 19 = indicatif ; 20 et plus = fiable)"));

    /* détail par référence */
    if (!etat.groupe) {
      detail.replaceChildren(creerElement("p", { class: "vide", text: "Choisissez « Détailler par » (format, article, machine…) pour comparer les références." }));
    } else {
      const dimension = DIMS.find(dimension => dimension.id === etat.groupe), groupes = new Map();
      for (const ligne of rows) { const cle = dimension.get(ligne); if (cle == null || cle === "") continue; if (!groupes.has(cle)) groupes.set(cle, []); groupes.get(cle).push(ligne); }
      const lignes = [...groupes.entries()].map(([cle, rs]) => {
        let pp = paires(rs); if (etat.ecarter) pp = ecartees(pp);
        return { cle, resume: stats(pp.map(paire => paire.valeur)) };
      }).filter(entree => entree.resume.effectif > 0).sort((premiere, seconde) => seconde.resume.effectif - premiere.resume.effectif);
      detail.replaceChildren(
        creerElement("div", { class: "defile" }, creerElement("table", { class: "t" },
          creerElement("thead", {}, creerElement("tr", {}, ...[dimension.lab, "n", "Médiane", "Moyenne", "Écart type", "Min", "Max", "Fiabilité"].map((titre, position) => creerElement("th", { class: position && position < 7 ? "n" : "", text: titre })))),
          creerElement("tbody", {}, ...lignes.map(({ cle, resume }) => {
            const [libelle, classe] = fiabilite(resume.effectif);
            const tr = creerElement("tr", { class: "cliquable", title: "Cliquer pour filtrer sur cette référence" },
              creerElement("td", { text: dimension.aff ? dimension.aff(cle) : String(cle) }),
              ...[fmt(resume.effectif, 0), fmt(resume.med), fmt(resume.moy), fmt(resume.sd), fmt(resume.min), fmt(resume.max)].map(texte => creerElement("td", { class: "n", text: texte })),
              creerElement("td", {}, creerElement("span", { class: "puce-f " + classe, text: libelle })));
            tr.addEventListener("click", () => { selects[dimension.id].value = String(cle); etat.filtres[dimension.id] = String(cle); sGroupe.value = ""; etat.groupe = ""; maj(); });
            return tr;
          })))),
        creerElement("p", { class: "petit", text: `${lignes.length} référence(s). Cliquez sur une ligne pour filtrer dessus.` }));
    }
    dessiner(rows);
  }

  /* évolution de la médiane */
  function periode(ligne) {
    const annee_lue = annee(ligne), mois_lu = moisNum(ligne);
    if (annee_lue == null) return null;
    if (etat.pas === "annee") return annee_lue * 12;
    if (etat.pas === "trimestre") return annee_lue * 12 + Math.floor((mois_lu - 1) / 3) * 3;
    return annee_lue * 12 + (mois_lu - 1);
  }
  const libPeriode = rang => {
    const annee_lue = Math.floor(rang / 12), mois_lu = rang % 12;
    return etat.pas === "annee" ? String(annee_lue) : etat.pas === "trimestre" ? `T${mois_lu / 3 + 1} ${annee_lue}` : `${MOIS[mois_lu]} ${annee_lue}`;
  };
  function dessiner(rows) {
    const groupes = new Map();
    for (const { ligne, valeur } of paires(rows)) { const cle_periode = periode(ligne); if (cle_periode == null) continue; if (!groupes.has(cle_periode)) groupes.set(cle_periode, []); groupes.get(cle_periode).push(valeur); }
    let pts = [...groupes.entries()].sort((premiere, seconde) => premiere[0] - seconde[0]).map(([periode, vs]) => {
      if (etat.ecarter && vs.length >= 8) {
        const tries = [...vs].sort((premier, deuxieme) => premier - deuxieme), q1 = quantile(tries, .25), q3 = quantile(tries, .75), ecart = q3 - q1;
        vs = vs.filter(valeur => valeur >= q1 - 3 * ecart && valeur <= q3 + 3 * ecart);
      }
      return { periode, ...stats(vs) };
    }).filter(point => point.effectif > 0);
    if (!pts.length) { evolution.replaceChildren(creerElement("p", { class: "vide", text: "Aucune donnée datée pour ces critères." })); return; }

    const LARGEUR = 1000, HAUTEUR = 340, ml = 54, mr = 16, mt = 14, mb = 64, hb = 46;
    const pmin = pts[0].periode, pmax = pts[pts.length - 1].periode, span = Math.max(1, pmax - pmin);
    const positionX = periode => ml + (pts.length === 1 ? (LARGEUR - ml - mr) / 2 : (periode - pmin) / span * (LARGEUR - ml - mr));
    const ymaxData = Math.max(...pts.map(point => Math.max(point.q3, point.med)));
    const yminData = Math.min(...pts.map(point => Math.min(point.q1, point.med)));
    const y0 = Math.min(0, yminData), y1 = ymaxData * 1.08 || 1;
    const hauteurCourbe = HAUTEUR - mt - mb - hb;
    const positionY = valeur => mt + (1 - (valeur - y0) / (y1 - y0)) * hauteurCourbe;
    const nmax = Math.max(...pts.map(point => point.effectif));
    const svg = sv("svg", { class: "graphe", viewBox: `0 0 ${LARGEUR} ${HAUTEUR}`, role: "img", "aria-label": "Évolution de la médiane" });

    for (let graduation = 0; graduation <= 4; graduation++) {                    // grille + axe Y
      const valeur_axe = y0 + (y1 - y0) * graduation / 4, position_y = positionY(valeur_axe);
      svg.append(sv("line", { class: "grille", x1: ml, x2: LARGEUR - mr, y1: position_y, y2: position_y }),
        sv("text", { x: ml - 8, y: position_y + 4, "text-anchor": "end" }, fmt(valeur_axe, 1)));
    }
    const fiables = pts.filter(point => point.effectif >= etat.minN);
    if (fiables.length > 1) {                          // bande Q1–Q3 (périodes fiables)
      const haut = fiables.map(point => `${positionX(point.periode)},${positionY(point.q3)}`), bas = [...fiables].reverse().map(point => `${positionX(point.periode)},${positionY(point.q1)}`);
      svg.append(sv("polygon", { class: "bande", points: [...haut, ...bas].join(" ") }));
    }
    if (pts.length > 1) {                              // ligne : pleine entre périodes fiables, pointillée sinon
      for (let rang = 1; rang < pts.length; rang++) {
        const precedent = pts[rang - 1], courant = pts[rang], ok = precedent.effectif >= etat.minN && courant.effectif >= etat.minN;
        svg.append(sv("line", { class: "ligne" + (ok ? "" : " pointille"), x1: positionX(precedent.periode), y1: positionY(precedent.med), x2: positionX(courant.periode), y2: positionY(courant.med) }));
      }
    }
    const yb = HAUTEUR - mb;                                 // barres : nombre de valeurs
    let derniereX = -1e9, derniereN = -1e9;               // étiquettes espacées d'au moins quelques pixels
    pts.forEach((point, rang) => {
      const bh = (point.effectif / nmax) * (hb - 12), bx = positionX(point.periode);
      svg.append(sv("rect", { class: "barre-n", x: bx - 6, y: yb + hb - 4 - bh - 14, width: 12, height: bh }));
      const pt = sv("circle", { class: "pt" + (point.effectif >= etat.minN ? "" : " faible"), cx: bx, cy: positionY(point.med), r: 5 },
        sv("title", {}, `${libPeriode(point.periode)} : médiane ${fmt(point.med)} (n = ${point.effectif}${point.effectif >= etat.minN ? "" : ", peu fiable"}) — Q1 ${fmt(point.q1)} / Q3 ${fmt(point.q3)}`));
      svg.append(pt);
      if (bx - derniereX >= 62) {
        derniereX = bx;
        svg.append(sv("text", { x: bx, y: HAUTEUR - 6, "text-anchor": "middle" }, libPeriode(point.periode)));
      }
      if (bx - derniereN >= 44) {
        derniereN = bx;
        svg.append(sv("text", { x: bx, y: yb + hb - 18 - (point.effectif / nmax) * (hb - 12), "text-anchor": "middle" }, "n=" + point.effectif));
      }
    });
    evolution.replaceChildren(svg, creerElement("div", { class: "legende" },
      creerElement("span", { text: "● point plein : au moins " + etat.minN + " valeurs" }),
      creerElement("span", { text: "○ point creux / ligne pointillée : trop peu de valeurs pour conclure" }),
      creerElement("span", { text: "bande bleue : 50 % des valeurs (Q1–Q3)" }),
      creerElement("span", { text: "barres grises : nombre de valeurs par période" })));
  }
  maj();
}

/* ======================================================================
   3. Contrôle qualité
   ====================================================================== */
let qualiteChargee = false;
async function construireQualite() {
  qualiteChargee = true;
  const racine = document.getElementById("p-qualite");
  racine.replaceChildren(creerElement("p", { class: "vide", text: "Analyse en cours…" }));
  let reponse;
  try { reponse = await getJSON("/api/anomalies"); } catch (erreur) { racine.replaceChildren(creerElement("p", { class: "vide", text: "Analyse impossible (fichier occupé ?)." })); qualiteChargee = false; return; }
  const liste_anomalies = reponse.anomalies;
  const comptes = gravite => liste_anomalies.filter(anomalie => anomalie.gravite === gravite).length;
  let grav = "", texte = "";
  const sG = creerElement("select", {}, creerElement("option", { value: "", text: "Toutes" }),
    ...["probable erreur", "à vérifier", "mineur"].map(gravite => creerElement("option", { value: gravite, text: `${gravite} (${comptes(gravite)})` })));
  const iT = creerElement("input", { type: "search", placeholder: "Colonne, motif, valeur…" });
  const corps = creerElement("tbody"), compte = creerElement("p", { class: "petit" });
  const tout = creerElement("button", { type: "button", class: "bouton secondaire petit-b", text: "Tout afficher" });
  let limite = 300;
  function rendre() {
    const recherche = norm(texte);
    const selection = liste_anomalies.filter(anomalie => (!grav || anomalie.gravite === grav) && (!recherche || norm(anomalie.colonne + " " + anomalie.motif + " " + anomalie.valeur).includes(recherche)));
    corps.replaceChildren(...selection.slice(0, limite).map(anomalie => creerElement("tr", {},
      creerElement("td", { class: "n", text: anomalie.ligne }), creerElement("td", { text: anomalie.colonne }), creerElement("td", { text: anomalie.valeur }), creerElement("td", { text: anomalie.motif }),
      creerElement("td", {}, creerElement("span", { class: "puce-f " + (anomalie.gravite === "probable erreur" ? "bas" : anomalie.gravite === "à vérifier" ? "moyen" : "mineur"), text: anomalie.gravite })))));
    compte.textContent = `${selection.length.toLocaleString("fr-FR")} point(s) à contrôler` + (selection.length > limite ? ` — ${limite} affichés` : "");
    tout.hidden = selection.length <= limite;
    racine._liste = selection;
  }
  sG.addEventListener("change", () => { grav = sG.value; limite = 300; rendre(); });
  iT.addEventListener("input", () => { texte = iT.value; limite = 300; rendre(); });
  tout.addEventListener("click", () => { limite = 1e9; rendre(); });
  const exp = creerElement("button", { type: "button", class: "bouton secondaire petit-b", text: "Exporter en CSV (Excel)" });
  exp.addEventListener("click", () => {
    const entre_guillemets = valeur => `"${String(valeur).replace(/"/g, '""')}"`;
    const csv = "Ligne;Colonne;Valeur;Motif;Gravité\r\n" + racine._liste.map(anomalie => [anomalie.ligne, anomalie.colonne, anomalie.valeur, anomalie.motif, anomalie.gravite].map(entre_guillemets).join(";")).join("\r\n");
    const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
    creerElement("a", { href: url, download: "controle_qualite.csv" }).click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  });
  racine.replaceChildren(
    creerElement("p", { class: "petit", text: `${reponse.nb_lignes.toLocaleString("fr-FR")} lignes analysées. Cette analyse ne modifie rien : elle liste ce qui semble absurde (limites dépassées, compteurs incohérents, dates en texte, erreurs Excel, valeurs hors liste, doublons, durées de vie très éloignées…). « Ligne » = numéro dans Excel : vous corrigez à la main, ou vous me transmettez la liste.` }),
    creerElement("div", { class: "barre" }, creerElement("label", {}, "Gravité", sG), creerElement("label", {}, "Recherche", iT), exp),
    compte,
    creerElement("div", { class: "defile" }, creerElement("table", { class: "t" },
      creerElement("thead", {}, creerElement("tr", {}, ...["Ligne", "Colonne", "Valeur", "Motif", "Gravité"].map((titre, position) => creerElement("th", { class: position === 0 ? "n" : "", text: titre })))), corps)),
    creerElement("div", { class: "pages" }, tout));
  rendre();
}

init();

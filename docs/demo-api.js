/* Démo en ligne : remplace le serveur Python par du JavaScript dans la page.
   Les données viennent de demo_data.json (classeur de FAUSSES données, voir outils/construire_demo_web.py).
   Les règles ci-dessous reprennent backend/services/valider.py et regles.py ; rien n'est écrit nulle part.
   Si vous modifiez ces règles côté Python, reportez-les ici (tests/test_demo_web.py compare les deux). */
(function () {
  "use strict";
  const vraiFetch = window.fetch.bind(window);
  let D = null, ROWS = null, enChargement = null;

  /* ---------- utilitaires (équivalents de donnees.py / valider.py) ---------- */
  const norm = s => (s === null || s === undefined) ? "" : String(s).split(/\s+/).filter(Boolean).join(" ").toLowerCase();
  const txt = v => (v === null || v === undefined) ? "" : String(v).trim();
  const estNb = v => typeof v === "number" && isFinite(v);
  const g = x => {                                                         // format Python {:g} (6 chiffres, notation exponentielle hors de 1e-4..1e6)
    x = Number(x); if (x === 0 || !isFinite(x)) return String(x);
    const [mantisse, exposant] = x.toExponential(5).split("e"), exp = Number(exposant);
    if (exp < -4 || exp >= 6) return String(parseFloat(mantisse)) + "e" + (exp < 0 ? "-" : "+") + String(Math.abs(exp)).padStart(2, "0");
    return String(parseFloat(x.toPrecision(6)));
  };
  const arrondi = x => { const r = Math.round(x); return (Math.abs(x % 1) === 0.5 && r % 2 !== 0) ? r - 1 : r; };  // arrondi « pair » comme Python
  const jour = v => String(v === null || v === undefined ? "" : v).slice(0, 10);
  const mediane = a => { const s = [...a].sort((x, y) => x - y), n = s.length; return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2; };
  function quartiles(vals) {                                              // statistics.quantiles(n=4, "inclusive")
    const s = [...vals].sort((a, b) => a - b), m = s.length - 1, q = [];
    for (let i = 1; i <= 3; i++) { const j = Math.floor(i * m / 4), d = (i * m) % 4; q.push(d === 0 ? s[j] : (s[j] * (4 - d) + s[j + 1] * d) / 4); }
    return [q[0], q[2]];
  }
  function nombre(brut) {
    if (typeof brut === "boolean") throw 0;
    const t = String(brut).trim().replace(",", ".");
    if (t === "" || !isFinite(Number(t))) throw 0;
    return Number(t);
  }

  const R = id => !D.champs.regles || D.champs.regles[id] !== false;      // règle active ? (champs.regles = interrupteurs)

  function preparer() {
    const cles = D.donnees.cles;
    ROWS = D.donnees.lignes.map(l => { const o = {}; cles.forEach((c, i) => o[c] = l[i + 1]); return o; });
  }
  const matricules = () => {
    const c = new Map();
    for (const l of ROWS) for (const [k, v0] of Object.entries(l)) {
      if (!k.startsWith("matricule") || v0 === null || v0 === "") continue;
      let s = String(v0).trim(); if (/^\d+$/.test(s)) s = s.padStart(4, "0");
      c.set(s, (c.get(s) || 0) + 1);
    }
    return [...c.entries()].sort((a, b) => b[1] - a[1]).map(e => e[0]);
  };
  const ligneFormat = (f, m) => { const cle = norm(txt(f) + txt(m)); return D.formats.find(x => x.cle === cle) || null; };

  /* ---------- valider.py ---------- */
  function valider(donnees, listes) {
    const propres = {}, erreurs = [], avert = [];
    for (const ch of D.champs.champs) {
      const nom = ch.nom, type = ch.type;
      if (type === "affichage") continue;
      const unite = ch.unite ? " " + ch.unite : "";
      const brut = donnees[nom];
      if (brut === null || brut === undefined || String(brut).trim() === "") {
        if (ch.obligatoire && !("auto_depuis" in ch)) erreurs.push(`${nom} : champ obligatoire`);
        propres[nom] = null; continue;
      }
      let valeur;
      try {
        if (type === "entier") { const x = nombre(brut); if (!Number.isInteger(x)) throw 0; valeur = x; }
        else if (type === "decimal") valeur = nombre(brut);
        else if (type === "date") {
          const t = String(brut).slice(0, 10);
          if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) throw 0;
          const d = new Date(Date.UTC(+t.slice(0, 4), +t.slice(5, 7) - 1, +t.slice(8, 10)));
          if (isNaN(d) || d.toISOString().slice(0, 10) !== t) throw 0;
          valeur = t;
        } else valeur = String(brut).trim();
      } catch (e) { erreurs.push(`${nom} : valeur invalide`); continue; }

      if ("min" in ch && (type === "entier" || type === "decimal") && valeur < ch.min) erreurs.push(`${nom} : doit être supérieur ou égal à ${ch.min}${unite}`);
      if ("max" in ch && (type === "entier" || type === "decimal") && valeur > ch.max) erreurs.push(`${nom} : ne doit pas dépasser ${ch.max}${unite}`);
      if ("longueur" in ch && String(valeur).length !== ch.longueur) erreurs.push(`${nom} : doit contenir exactement ${ch.longueur} caractères`);
      if (type === "date" && R("date_futur") && valeur > new Date().toLocaleDateString("sv-SE")) avert.push(`${nom} : la date est dans le futur`);
      if (type === "liste") {
        const aut = ch.valeurs || listes[nom];
        if (aut && !aut.includes(valeur) && ch.hors_liste !== "ignorer") {
          if (ch.hors_liste === "avertir_et_commentaire") {
            avert.push(`${nom} : « ${valeur} » n'est pas prévu pour ce format`);
            if (!String(donnees.Commentaire || "").trim()) erreurs.push(`Commentaire obligatoire : expliquez pourquoi ${nom} « ${valeur} » n'est pas prévu pour ce format`);
          } else erreurs.push(`${nom} : « ${valeur} » n'est pas une valeur autorisée`);
        }
      }
      propres[nom] = valeur;
    }
    const deb = propres["Compteur début"], fin = propres["Compteur fin"];
    if (deb != null && fin != null && fin < deb) erreurs.push("Compteur fin : doit être supérieur ou égal au compteur début");
    const hi = propres["Hauteur meule initiale, mm"], hf = propres["Hauteur meule finale, mm"];
    if (hi != null && hf != null && hf > hi) erreurs.push("Hauteur finale : ne peut pas dépasser la hauteur initiale");
    return [propres, erreurs, avert];
  }

  /* ---------- regles.py ---------- */
  function horsHabitude(propres, seulement) {
    const cfg = D.champs.controle_habituel || {}, k = cfg.coefficient ?? 1.5, mini = cfg.minimum_cas ?? 20, avert = [];
    for (const nom of (seulement || cfg.champs || [])) {
      const v = propres[nom]; if (v === null || v === undefined) continue;
      let base = ROWS, portee = "toutes les saisies", miniChamp = mini;
      if (nom === "Compteur fin") {
        const art = propres["N° article meule"], mat = propres["Matière"];
        base = ROWS.filter(l => String(l["n° article meule"] ?? "").trim() === String(art) && norm(l["matière"]) === norm(mat));
        portee = `la meule ${art} (matière ${mat})`; miniChamp = Math.min(mini, 8);
      }
      let vals = base.map(l => l[norm(nom)]).filter(estNb);
      if (nom === "Pression d'arrosage") { if (v === 0) continue; vals = vals.filter(x => x !== 0); }
      if (vals.length < miniChamp) continue;
      const [q1, q3] = quartiles(vals), e = q3 - q1, bas = q1 - k * e, haut = q3 + k * e;
      if (v < bas || v > haut) avert.push(`${nom} : ${g(v)} est inhabituel (la plupart des valeurs de ${portee} sont entre ${g(q1)} et ${g(q3)}). Vérifiez la saisie.`);
    }
    return avert;
  }
  function doublon(p) {
    const c = { art: String(p["N° article meule"] ?? ""), mach: String(p["N° de Machine"] ?? ""), face: String(p["Face"] ?? ""),
      date: jour(p["Date montage"]), fin: p["Compteur fin"] };
    if ([c.art, c.mach, c.face, c.date, c.fin].some(v => v === null || v === undefined || v === "")) return null;
    for (const l of ROWS) {
      if (String(l["n° article meule"] ?? "").trim() === c.art && norm(l["n° de machine"]) === norm(c.mach) && norm(l["face"]) === norm(c.face)
        && jour(l["date montage"]) === c.date && estNb(l["compteur fin"]) && Number(l["compteur fin"]) === Number(c.fin))
        return `Une saisie identique existe déjà dans le fichier (meule ${c.art}, face ${c.face}, machine ${c.mach}, montage du ${c.date.slice(8, 10)}/${c.date.slice(5, 7)}/${c.date.slice(0, 4)}, compteur fin ${g(c.fin)}). Est-ce un doublon ?`;
    }
    return null;
  }
  function traiter(donnees) {
    const d = { ...donnees }, listes = { ...D.listes }, erreurs = [], avert = [];
    const champsMat = D.champs.champs.filter(c => c.type === "matricule");
    for (const c of champsMat) if (d[c.nom] !== null && d[c.nom] !== undefined && d[c.nom] !== "") {
      let v = String(d[c.nom]).trim(); if (/^\d+$/.test(v) && v.length < (c.longueur || 4)) v = v.padStart(c.longueur || 4, "0"); d[c.nom] = v;
    }
    let ref = null;
    if (d["Format"] && d["Matière"]) {
      ref = ligneFormat(d["Format"], d["Matière"]);
      if (!ref) erreurs.push("Format + Matière : combinaison absente de l'onglet « Formats & matière »");
      else {
        listes["N° de Machine"] = ref.machines.length ? ref.machines : null;
        const ma5 = norm(ref.ma5), cap = s => s.charAt(0).toUpperCase() + s.slice(1);
        if (ma5 === "oui" || ma5 === "non") d["MA5"] = cap(ma5);
        else if (["oui", "non"].includes(norm(d["MA5"]))) d["MA5"] = cap(norm(d["MA5"]));
        else erreurs.push("MA5 : la table indique « Peut-être », choisissez Oui ou Non");
      }
    }
    listes["MA5"] = ["Oui", "Non"];
    const cf = String(d["Compteur fin"] ?? "").trim();
    if (cf !== "" && Number(cf.replace(",", ".")) === 0) { d["Compteur fin"] = 1; avert.push("Compteur fin : 0 a été remplacé par 1 pour ne pas casser les formules Excel."); }
    const [propres, e, a] = valider(d, listes); erreurs.push(...e); avert.push(...a);

    const article = propres["N° article meule"];
    if (R("meule_non_prevue") && ref && ref.meules.length && article && !ref.meules.includes(article))
      avert.push(`N° article meule : ${article} n'est pas la meule prévue pour ce format et cette matière (${ref.meules.join(" / ")})`);
    const connus = new Set(R("matricule_inconnu") ? matricules() : []);
    if (connus.size) for (const c of champsMat) { const m = propres[c.nom]; if (m && !connus.has(m)) avert.push(`${c.nom} : ${m} n'a encore jamais été utilisé dans le fichier`); }
    const seuil = D.champs.seuil_demontee_avant_usure_mm, hf = propres["Hauteur meule finale, mm"];
    if (R("non_fini") && seuil != null && hf != null && hf > seuil && !String(d["Commentaire"] || "").trim())
      erreurs.push(`Commentaire obligatoire : la meule est démontée avant usure totale (il reste ${g(hf)} mm). Pourquoi ?`);
    avert.push(...horsHabitude(propres));
    const dbl = R("doublon_saisie") ? doublon(propres) : null; if (dbl) avert.push(dbl);
    return [propres, erreurs, avert];
  }
  function versDefaut(p) {
    const cfg = D.champs.defaut, seuil = D.champs.seuil_demontee_avant_usure_mm, h = p["Hauteur meule finale, mm"];
    return !!(cfg && seuil != null && h != null && h > seuil && String(p["Commentaire"] || "").includes(cfg.theme));
  }
  function verifierChamp(nom, valeur, article, matiere) {
    const t = String(valeur ?? "").trim().replace(",", ".");
    if (t === "" || !isFinite(Number(t))) return "";
    if (!((D.champs.controle_habituel || {}).champs || []).includes(nom)) return "";
    const r = horsHabitude({ [nom]: Number(t), "N° article meule": article, "Matière": matiere }, [nom]);
    return r[0] || "";
  }
  function perte() {
    const annee = new Date().getFullYear(), prix = D.champs.prix_meule_moyenne_eur ?? 150; let total = 0, nb = 0;
    for (const l of ROWS) {
      const dm = l["date montage"];
      if (typeof dm !== "string" || !/^\d{4}-\d{2}-\d{2}/.test(dm) || +dm.slice(0, 4) !== annee) continue;
      const hi = l["hauteur meule initiale, mm"], hf = l["hauteur meule finale, mm"];
      if (estNb(hi) && estNb(hf) && hi > 0 && hf > 0) { total += Math.min(hf, hi) / hi * prix; nb++; }
    }
    return { annee, total: Math.round(total * 100) / 100, nb, prix };
  }
  function medianeFaces(article, machine, matiere) {
    const niveaux = [["article + machine + matière", { "n° article meule": article, "n° de machine": machine, "matière": matiere }],
      ["article + matière", { "n° article meule": article, "matière": matiere }], ["article seul", { "n° article meule": article }]];
    const res = {};
    for (const face of ["A", "B"]) {
      res[face] = null; let repli = null, trouve = false;
      for (const [nom, crit] of niveaux) {
        const vals = ROWS.filter(l => norm(l["face"]) === norm(face) && Object.entries(crit).every(([c, v]) => norm(l[c]) === norm(v))
          && estNb(l["nb faces/meule de 89 mm"])).map(l => l["nb faces/meule de 89 mm"]);
        if (!vals.length) continue;
        const info = { mediane: arrondi(mediane(vals)), nb_cas: vals.length, critere: nom, fiable: vals.length >= 5 };
        if (info.fiable) { res[face] = info; trouve = true; break; }
        repli = repli || info;
      }
      if (!trouve) res[face] = repli;
    }
    return res;
  }

  /* ---------- faux serveur ---------- */
  /* État de la démo gardé le temps de la session du navigateur (comptes, règles, humour) : rien n'est envoyé nulle part. */
  let ETAT = null;
  const lireSession = () => { try { return JSON.parse(sessionStorage.getItem("meules_demo") || "null"); } catch (e) { return null; } };
  const ecrireSession = () => { try { sessionStorage.setItem("meules_demo", JSON.stringify(ETAT)); } catch (e) { /* stockage indisponible : l'état reste en mémoire */ } };
  const maintenant = () => new Date().toISOString().slice(0, 19);
  const copie = x => JSON.parse(JSON.stringify(x));

  /* Reprend la logique de backend/services/reglages.py (_construire) : les règles modifiées changent vraiment les contrôles de la démo. */
  function appliquerReglages() {
    const c = D.champs, base = D.champs_base, v = {};
    for (const r of ETAT.reglages.regles) v[r.id] = { actif: r.actif, p: Object.fromEntries(r.params.map(q => [q.cle, Number(q.valeur)])) };
    c.regles = Object.fromEntries(ETAT.reglages.regles.map(r => [r.id, r.actif]));
    c.seuil_demontee_avant_usure_mm = v.non_fini.p.seuil;
    for (const [id, nom] of [["rotation_max", "Vitesse de rotation"], ["avance_max", "V.Avance"], ["hauteur_init_max", "Hauteur meule initiale, mm"]]) {
      const champ = c.champs.find(x => x.nom === nom);
      if (v[id].actif) champ.max = v[id].p.valeur; else delete champ.max;
    }
    c.controle_habituel.coefficient = v.hors_habitude.p.coefficient;
    c.controle_habituel.minimum_cas = v.hors_habitude.p.minimum_cas;
    c.controle_habituel.champs = v.hors_habitude.actif ? copie(base.controle_habituel.champs) : [];
    c.champs.find(x => x.nom === "N° de Machine").hors_liste = v.machine_non_prevue.actif ? base.champs.find(x => x.nom === "N° de Machine").hors_liste : "ignorer";
    c.controle_qualite.coefficient_eloigne = v.controle_eloigne.p.coefficient;
    c.prix_meule_moyenne_eur = v.prix_meule.p.valeur;
  }

  /* La démo est construite à une date donnée ; au chargement, toutes les dates du classeur fictif sont décalées pour que
     la dernière saisie reste « d'hier » quel que soit le jour où l'on ouvre la démo : plus besoin de la reconstruire. */
  function decalerDates(donnees, depuis) {
    const ajd = new Date().toLocaleDateString("sv-SE"), jours = (a, b) => Math.round((Date.UTC(+a.slice(0, 4), +a.slice(5, 7) - 1, +a.slice(8, 10)) - Date.UTC(+b.slice(0, 4), +b.slice(5, 7) - 1, +b.slice(8, 10))) / 864e5);
    const delta = depuis ? jours(ajd, depuis) : 0;
    if (!delta) return;
    for (const ligne of donnees.lignes) for (let i = 1; i < ligne.length; i++) {
      const v = ligne[i];
      if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)) {
        const d = new Date(Date.UTC(+v.slice(0, 4), +v.slice(5, 7) - 1, +v.slice(8, 10) + delta));
        ligne[i] = d.toISOString().slice(0, 10);
      }
    }
  }

  async function charger() {
    if (!enChargement) enChargement = vraiFetch("demo_data.json").then(r => r.json()).then(j => {
      D = j; D.champs_base = copie(D.champs); decalerDates(D.donnees, D.date_construction); preparer();
      ETAT = lireSession() || {
        humour: true, reglages: copie(D.reglages), reglages_origine: copie(D.reglages), historique: [],
        comptes: [{ id: 1, nom: "demo", cree_le: maintenant(), derniere_connexion: maintenant() },
                  { id: 2, nom: "chef.atelier", cree_le: maintenant(), derniere_connexion: null }], suivant: 3, connecte: true,
      };
      appliquerReglages();
    });
    return enChargement;
  }
  const rep = (corps, statut) => new Response(JSON.stringify(corps), { status: statut || 200, headers: { "Content-Type": "application/json" } });
  const pause = ms => new Promise(resoudre => setTimeout(resoudre, ms));

  /* Enregistrement simulé : mêmes étapes que le vrai serveur, pour montrer la barre de chargement. */
  const ETAPES = ["attente", "lancement_excel", "ouverture", "ajout_ligne", "formules", "formats", "valeurs", "calcul", "sauvegarde", "fermeture"];
  const TRAVAUX = new Map();
  function lancerTravail(propres, avertissements) {
    const id = "demo" + Math.random().toString(36).slice(2, 10), t = { etape: "attente", fini: false, statut: null, corps: null };
    TRAVAUX.set(id, t);
    (async () => {
      for (const e of ETAPES) { t.etape = e; await pause(e === "attente" ? 150 : 380); }
      const defaut = versDefaut(propres), objet = {};
      for (const [k, v] of Object.entries(propres)) objet[norm(k)] = v;
      const ligne = Math.max(1, ...D.donnees.lignes.map(l => l[0])) + 1 + (ROWS.length - D.donnees.lignes.length);
      ROWS.push(objet);                                // en mémoire seulement : sert à détecter un doublon pendant la démo
      t.etape = "termine"; t.fini = true; t.statut = 200;
      t.corps = { ok: true, ligne, calcules: {}, avertissements,
        defaut: defaut ? { onglet: D.champs.defaut.onglet, ligne: "—", colonnes_absentes: [] } : null };
    })();
    return id;
  }

  /* Back-office simulé : tout est accepté, rien n'est durable. */
  const MOI = () => ({ id: 1, nom: ETAT.comptes[0].nom });
  const NON_CONNECTE = () => rep({ detail: "Connexion requise." }, 401);
  function adminReponse(route, methode, corps) {
    if (route === "etat") return rep({ aucun_compte: false, compte_demo: { nom: "demo", mot_de_passe: "n'importe lequel : aucun mot de passe n'est vérifié dans la démo" } });
    if (route === "connexion") { ETAT.connecte = true; ecrireSession(); return rep(MOI()); }
    if (route === "deconnexion") { ETAT.connecte = false; ecrireSession(); return rep({ ok: true }); }
    if (!ETAT.connecte) return NON_CONNECTE();
    if (route === "moi") return rep(MOI());
    if (route === "utilisateurs") {
      if (methode === "POST") {
        const nom = String(corps.nom || "").trim();
        if (!nom) return rep({ detail: "Le nom d'utilisateur est obligatoire." }, 422);
        if (ETAT.comptes.some(c => c.nom.toLowerCase() === nom.toLowerCase())) return rep({ detail: "Ce nom d'utilisateur existe déjà." }, 422);
        if (String(corps.mot_de_passe || "").length < 8) return rep({ detail: "Le mot de passe doit contenir au moins 8 caractères." }, 422);
        ETAT.comptes.push({ id: ETAT.suivant++, nom, cree_le: maintenant(), derniere_connexion: null });
      }
      ecrireSession(); return rep(ETAT.comptes);
    }
    let m = route.match(/^utilisateurs\/(\d+)(\/mot-de-passe)?$/);
    if (m) {
      const id = Number(m[1]);
      if (methode === "DELETE") {
        if (id === 1) return rep({ detail: "Vous ne pouvez pas supprimer votre propre compte." }, 422);
        ETAT.comptes = ETAT.comptes.filter(c => c.id !== id);
      } else if (String(corps.mot_de_passe || "").length < 8) return rep({ detail: "Le mot de passe doit contenir au moins 8 caractères." }, 422);
      ecrireSession(); return rep({ ok: true });
    }
    if (route === "moi/nom") {
      const nom = String(corps.nom || "").trim();
      if (!nom) return rep({ detail: "Le nom d'utilisateur est obligatoire." }, 422);
      ETAT.comptes[0].nom = nom; ecrireSession(); return rep(MOI());
    }
    if (route === "moi/mot-de-passe") {
      if (String(corps.nouveau || "").length < 8) return rep({ detail: "Le nouveau mot de passe doit contenir au moins 8 caractères." }, 422);
      return rep({ ok: true });
    }
    if (route === "affichage") {
      if (methode === "POST") {
        const humour = !!corps.humour;
        if (humour !== ETAT.humour) ETAT.historique.unshift({ date: maintenant(), utilisateur: ETAT.comptes[0].nom, regle: "Messages humoristiques à l'enregistrement", avant: ETAT.humour ? "oui" : "non", apres: humour ? "oui" : "non" });
        ETAT.humour = humour; ecrireSession();
      }
      return rep({ humour: ETAT.humour });
    }
    if (route === "reglages") {
      if (methode === "POST") {
        if (corps.reinitialiser) {
          ETAT.reglages = copie(ETAT.reglages_origine);
          ETAT.historique.unshift({ date: maintenant(), utilisateur: ETAT.comptes[0].nom, regle: "Toutes les règles", avant: "", apres: "valeurs d'origine" });
        } else {
          for (const regle of ETAT.reglages.regles) {
            const demande = (corps.regles || {})[regle.id]; if (!demande) continue;
            const avant = (regle.actif ? "actif" : "désactivé") + regle.params.map(q => ` · ${q.cle}=${g(q.valeur)}`).join("");
            if (regle.switch) regle.actif = !!demande.actif;
            for (const q of regle.params) {
              const brut = (demande.params || {})[q.cle]; if (brut === undefined) continue;
              const x = Number(String(brut).replace(",", "."));
              if (!isFinite(x) || x < q.min || x > q.max) return rep({ detail: [`${regle.titre} (${q.libelle}) : entre ${g(q.min)} et ${g(q.max)} ${q.unite}`.trim()] }, 422);
              q.valeur = x;
            }
            const apres = (regle.actif ? "actif" : "désactivé") + regle.params.map(q => ` · ${q.cle}=${g(q.valeur)}`).join("");
            if (avant !== apres) ETAT.historique.unshift({ date: maintenant(), utilisateur: ETAT.comptes[0].nom, regle: regle.titre, avant, apres });
          }
        }
        ETAT.reglages.modifie = JSON.stringify(ETAT.reglages.regles) !== JSON.stringify(ETAT.reglages_origine.regles);
        appliquerReglages(); ecrireSession();
      }
      return rep({ ...ETAT.reglages, historique: ETAT.historique.slice(0, 30) });
    }
    return rep({ erreurs: ["Route inconnue"] }, 404);
  }

  window.fetch = async function (url, opts) {
    const u = new URL(typeof url === "string" ? url : url.url, location.href);
    const i = u.pathname.lastIndexOf("/api/");
    if (i < 0) return vraiFetch(url, opts);
    await charger();
    const route = u.pathname.slice(i + 5), corps = (opts && opts.body) ? JSON.parse(opts.body) : {};
    if (route.startsWith("admin/")) return adminReponse(route.slice(6), ((opts && opts.method) || "GET").toUpperCase(), corps);
    if (route.startsWith("ajout/")) {
      const t = TRAVAUX.get(route.slice(6));
      return t ? rep({ etape: t.etape, fini: t.fini, statut: t.statut, corps: t.corps }) : rep({ erreurs: ["Enregistrement inconnu."] }, 404);
    }
    switch (route) {
      case "etat": return rep(D.etat);
      case "champs": return rep(D.champs);
      case "listes": return rep(D.listes);
      case "formats": return rep(D.formats);
      case "meules": return rep(D.meules);
      case "donnees": return rep(D.donnees);
      case "anomalies": return rep(D.anomalies);
      case "perte": return rep(perte());
      case "affichage": return rep({ humour: ETAT.humour });
      case "mediane": return rep(medianeFaces(u.searchParams.get("article"), u.searchParams.get("machine"), u.searchParams.get("matiere")));
      case "habitude": return rep({ message: verifierChamp(corps.nom || "", corps.valeur, corps.article, corps.matiere) });
      case "verifier": { const [, erreurs, avertissements] = traiter(corps); return rep({ erreurs, avertissements }); }
      case "ajout": {
        const [propres, erreurs, avertissements] = traiter(corps);
        if (erreurs.length) return rep({ erreurs, avertissements }, 422);
        return rep({ travail: lancerTravail(propres, avertissements) }, 202);
      }
    }
    return rep({ erreurs: ["Route inconnue"] }, 404);
  };

  document.addEventListener("DOMContentLoaded", () => {
    const admin = /admin(\.html)?$/.test(location.pathname);
    if (!admin && document.getElementById("bandeau-demo")) return;       // la page de saisie a déjà son bandeau
    const b = document.createElement("p");
    b.className = "bandeau-test";
    b.style.cssText = "margin:0;border-radius:0;text-align:center;position:sticky;top:0;z-index:50";
    b.textContent = admin
      ? "DÉMO EN LIGNE : dans la vraie version, cette page demande un nom d'utilisateur et un mot de passe (comptes créés sur le PC serveur, mots de passe chiffrés, blocage après 5 échecs). Ici l'accès est libre, rien n'est enregistré durablement et aucun mot de passe n'est vérifié."
      : "DÉMO EN LIGNE : données entièrement inventées. Les saisies sont contrôlées comme en vrai mais ne sont enregistrées nulle part. ";
    if (!admin) { const a = document.createElement("a"); a.href = "admin.html"; a.textContent = "⚙ Voir l'administration"; a.style.color = "inherit"; b.append(a); }
    document.body.prepend(b);
  });
})();

"use strict";
/* Barre de chargement de l'enregistrement : bloque la page, affiche l'avancement réel (étape envoyée par le serveur)
   et un texte qui change. Le mode « humour » se règle dans l'administration (onglet Affichage). */
const Chargement = (() => {
  /* Début de chaque étape sur la barre (en %). Les durées viennent de journal_chrono.csv : la fermeture d'Excel est longue. */
  const ETAPES = [
    ["verification", 0], ["envoi", 3], ["attente", 5], ["lancement_excel", 7], ["ouverture", 16], ["ajout_ligne", 28],
    ["formules", 31], ["formats", 33], ["valeurs", 56], ["calcul", 69], ["sauvegarde", 71], ["fermeture", 77],
  ];
  const DEBUT = Object.fromEntries(ETAPES);
  const SUITE = Object.fromEntries(ETAPES.map(([id], rang) => [id, rang + 1 < ETAPES.length ? ETAPES[rang + 1][1] : 100]));

  const NORMAL = {
    verification: "Vérification de la saisie…",
    envoi: "Envoi de la saisie au serveur…",
    attente: "Un autre enregistrement est en cours : vous passez juste après…",
    lancement_excel: "Démarrage d'Excel…",
    ouverture: "Ouverture du classeur…",
    ajout_ligne: "Ajout d'une ligne dans le tableau…",
    formules: "Recopie des formules…",
    formats: "Mise en forme de la nouvelle ligne…",
    valeurs: "Écriture de vos valeurs…",
    calcul: "Calcul des colonnes automatiques…",
    sauvegarde: "Enregistrement du fichier…",
    fermeture: "Fermeture d'Excel…",
    termine: "Terminé ✔",
  };

  const HUMOUR = {
    verification: ["Relecture de votre saisie avec un air suspicieux…", "On vérifie que 2 + 2 fait toujours 4…"],
    envoi: ["Envoi par pigeon voyageur (version rapide)…", "Votre saisie prend le couloir de gauche…"],
    attente: ["Vous êtes dans la file d'attente. Pas de doublage sauvage.", "Un collègue enregistre juste avant vous : ambiance salle d'attente…"],
    lancement_excel: ["Chargement de la gravité… ✔", "Réveil d'Excel (il fait semblant de dormir)…", "Chauffage des cellules à température ambiante…", "Gonflage des pixels…"],
    ouverture: ["Ouverture du classeur sans le froisser…", "Comptage des lignes… on en est à 3 millions de moutons.", "Test de la patience de l'utilisateur : excellent résultat.", "Dépoussiérage des feuilles de calcul…"],
    ajout_ligne: ["Fabrication d'une ligne neuve, garantie sans bavure…", "Alignement des pixels au micron près…"],
    formules: ["Dressage des formules, elles mordent parfois…", "Les formules font leur échauffement…"],
    formats: ["Habillage de la ligne : fond, police et petit nœud papillon…", "Polissage de la meule virtuelle…", "Calibrage des bordures au dixième de millimètre…", "Lustrage de la cellule, ça brille…"],
    valeurs: ["Dictée de vos chiffres à Excel…", "Ajustement du diamètre de la meule imaginaire…", "Recomptage des tours de meule sur ses doigts…", "Chaque chiffre est invité à prendre sa place…"],
    calcul: ["Surchauffe des calculatrices…", "Excel demande confirmation à un comptable…"],
    sauvegarde: ["On appuie très fort sur Ctrl+S…", "Signature en trois exemplaires…", "Sauvegarde dans le coffre-fort, code à six chiffres…"],
    fermeture: ["Excel range ses affaires…", "Extinction des feux, ne bougez plus…", "Excel ne veut jamais partir, on insiste poliment…", "Rangement du stylo derrière l'oreille…", "Le plus long, c'est de dire au revoir…"],
  };
  const COMMUN = [
    "Vérification de la gravité : elle est toujours là.", "Test de la patience de l'utilisateur : 98 %…",
    "Rinçage du liquide de refroidissement imaginaire…", "Un électron est parti chercher un café…",
    "Réglage de la météo dans le classeur…", "Calcul de la vitesse d'une meule qui n'existe pas…",
    "Dépoussiérage des octets…", "Mise en veille des hamsters de l'ordinateur… ils se réveillent.",
    "Négociation avec le disque dur…", "Réchauffement du serveur à la main…",
  ];

  function el(tag, attrs = {}, ...enfants) {
    const element = document.createElement(tag);
    for (const [cle, valeur] of Object.entries(attrs)) {
      if (valeur === false || valeur == null) continue;
      if (cle === "class") element.className = valeur;
      else if (cle === "text") element.textContent = valeur;
      else element.setAttribute(cle, valeur === true ? "" : valeur);
    }
    element.append(...enfants.flat().filter(enfant => enfant != null));
    return element;
  }

  let humour = false, noeud = null, ouvert = false;
  let etape = "verification", pct = 0, debut = 0, derniereChange = 0, iBarre = null, iTexte = null, iTemps = null;
  let dernierTexte = "", fenetreEchec = null;
  const reduit = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function creer() {
    const barre = el("div", { class: "chg-barre", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": "0", "aria-label": "Avancement de l'enregistrement" },
      el("div", { class: "chg-rempli", id: "chg-rempli" }));
    noeud = el("div", { class: "chargement", id: "chargement", hidden: true, role: "alertdialog", "aria-modal": "true", "aria-labelledby": "chg-titre", "aria-describedby": "chg-pied" },
      el("div", { class: "chg-carte", tabindex: "-1", id: "chg-carte" },
        el("h2", { id: "chg-titre", text: "Enregistrement en cours" }),
        barre,
        el("div", { class: "chg-ligne" }, el("span", { id: "chg-pct", text: "0 %" }), el("span", { id: "chg-temps", class: "petit" })),
        el("p", { class: "chg-texte", id: "chg-texte" }),
        el("p", { class: "petit", id: "chg-pied", text: "Ne fermez pas la page et ne touchez à rien : la saisie est en train d'être écrite dans Excel." })));
    document.body.append(noeud);
    // pas de Tab vers le formulaire caché derrière (en plus de l'attribut inert)
    noeud.addEventListener("keydown", evenement => { if (evenement.key === "Tab" || evenement.key === "Escape") evenement.preventDefault(); });
  }

  function choisirTexte(changementEtape = false) {
    if (!humour) return NORMAL[etape] || NORMAL.envoi;
    // Texte de l'étape en cours (toujours à l'arrivée dans l'étape, ensuite 2 fois sur 3), sinon une blague générale.
    const propres = HUMOUR[etape] || [];
    const liste = propres.length && (changementEtape || Math.random() < 0.67) ? propres : COMMUN;
    let texte, essais = 0;
    do { texte = liste[Math.floor(Math.random() * liste.length)]; } while (texte === dernierTexte && liste.length > 1 && ++essais < 6);
    return texte;
  }
  function afficherTexte(texte) {
    dernierTexte = texte;
    const zone = document.getElementById("chg-texte");
    zone.textContent = texte;
    document.getElementById("chg-carte").querySelector("[role=progressbar]").setAttribute("aria-valuetext", NORMAL[etape] || texte);
  }
  function majBarre() {
    // Avance vers la fin de l'étape sans jamais l'atteindre : la barre bouge même si l'étape est longue.
    const plafond = Math.max(pct, (SUITE[etape] ?? 100) - 1);
    pct += (plafond - pct) * 0.05;
    dessiner();
  }
  function dessiner() {
    const pourcentage = Math.max(0, Math.min(100, pct));
    document.getElementById("chg-rempli").style.width = pourcentage.toFixed(1) + "%";
    document.getElementById("chg-pct").textContent = Math.floor(pourcentage) + " %";
    noeud.querySelector("[role=progressbar]").setAttribute("aria-valuenow", String(Math.floor(pourcentage)));
  }
  function avantFermeture(evenement) { evenement.preventDefault(); evenement.returnValue = ""; }

  return {
    set humour(valeur) { humour = !!valeur; },
    get ouvert() { return ouvert; },

    ouvrir(premiere = "verification") {
      if (ouvert) { this.etape(premiere); return; }
      if (!noeud) creer();
      ouvert = true; etape = premiere; pct = DEBUT[premiere] || 0; debut = Date.now();
      noeud.hidden = false;
      const principal = document.querySelector("main");
      if (principal) { principal.inert = true; principal.setAttribute("aria-hidden", "true"); }
      document.getElementById("chg-carte").focus();
      afficherTexte(choisirTexte(true));
      dessiner();
      iBarre = setInterval(majBarre, 100);
      iTexte = setInterval(() => { if (humour) afficherTexte(choisirTexte()); }, 2600);
      iTemps = setInterval(() => {
        const secondes = Math.round((Date.now() - debut) / 1000);
        document.getElementById("chg-temps").textContent = secondes >= 3 ? "Écoulé : " + secondes + " s" : "";
      }, 500);
      window.addEventListener("beforeunload", avantFermeture);
    },

    etape(id) {
      if (!ouvert || id === etape) return;
      etape = id;
      if (id in DEBUT) pct = Math.max(pct, DEBUT[id]);       // la barre ne recule jamais
      afficherTexte(choisirTexte(true));
      dessiner();
    },

    /** Barre à 100 %, courte pause pour le voir, puis fermeture. */
    async terminer() {
      if (!ouvert) return;
      etape = "termine"; pct = 100;
      afficherTexte(NORMAL.termine);
      dessiner();
      await new Promise(resoudre => setTimeout(resoudre, reduit ? 150 : 550));
      this.fermer();
    },

    fermer() {
      if (!ouvert) return;
      ouvert = false;
      clearInterval(iBarre); clearInterval(iTexte); clearInterval(iTemps);
      noeud.hidden = true;
      const principal = document.querySelector("main");
      if (principal) { principal.inert = false; principal.removeAttribute("aria-hidden"); }
      window.removeEventListener("beforeunload", avantFermeture);
      const bouton_enregistrer = document.getElementById("bouton");
      if (bouton_enregistrer && !bouton_enregistrer.disabled) bouton_enregistrer.focus({ preventScroll: true });
    },

    /** Lit le réglage « humour » du back-office (sans bloquer la page si le serveur ne répond pas). */
    async chargerReglage() {
      try {
        const reponse = await fetch("/api/affichage");
        if (reponse.ok) humour = !!(await reponse.json()).humour;
      } catch (erreur) { /* on garde la valeur actuelle */ }
    },
  };
})();
Chargement.chargerReglage();

    "use strict";

    /* ======================================================================
       Noms des colonnes utilisées par les dépendances entre champs.
       (ils doivent correspondre à « nom » dans champs.json)
       ====================================================================== */
    const NOMS = {
      format: "Format", matiere: "Matière", article: "N° article meule",
      machine: "N° de Machine", ma5: "MA5", face: "Face",
      debut: "Compteur début", fin: "Compteur fin",
      hInit: "Hauteur meule initiale, mm", hFin: "Hauteur meule finale, mm",
    };

    /* ---------- Utilitaires ---------- */
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
    async function getJSON(url) {
      const reponse = await fetch(url);
      if (!reponse.ok) throw new Error(url + " : " + reponse.status);
      return reponse.json();
    }
    async function post(url, donnees) {
      const reponse = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(donnees),
      });
      let corps = {};
      try { corps = await reponse.json(); } catch (erreur) {}
      return { statut: reponse.status, corps };
    }
    const regleActive = id => (CFG.regles || {})[id] !== false;          // règle activée dans l'onglet « Règles » de la consultation
    const libVal = (ch, valeur) => (ch.affichage_valeurs || {})[valeur] || valeur;      // I -> Inox (affichage seulement)
    const norm = texte => String(texte ?? "").trim().toLowerCase();
    const fmt = nombre => String(Math.round(nombre * 100) / 100).replace(".", ",");
    const aujourdhui = () => new Date().toLocaleDateString("sv-SE");        // AAAA-MM-JJ
    const reduit = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const comparer = (premier, deuxieme) => String(premier).localeCompare(String(deuxieme), "fr", { numeric: true });

    /* ---------- État ---------- */
    let CFG, LISTES, FORMATS, MEULES, PERTE = null;
    const euro = montant => montant.toLocaleString("fr-FR", { maximumFractionDigits: montant < 10 ? 1 : 0 }) + " €";
    const ordre = [];            // contrôleurs de champs, dans l'ordre d'affichage
    const parNom = {};           // nom de colonne -> contrôleur
    const sections = {};         // id de section -> { racine, corps, ctrls, ... }
    let compteurId = 0;
    let envoiEnCours = false;
    let cleMediane = "";

    const formulaire = document.getElementById("formulaire");
    const zoneMessages = document.getElementById("messages");
    const bouton = document.getElementById("bouton");
    const manque = document.getElementById("manque");

    const texteDe = nom => (parNom[nom] ? parNom[nom].texte() : "");
    const nombreDe = nom => {
      const texte = texteDe(nom);
      if (texte === "") return null;
      const nombre = Number(texte.replace(",", "."));
      return Number.isFinite(nombre) ? nombre : null;
    };
    function refFormat() {
      const format = texteDe(NOMS.format), matiere = texteDe(NOMS.matiere);
      if (!format || !matiere) return null;
      return FORMATS.find(reference => reference.format === format && reference.matiere === matiere) || null;
    }

    function setOptions(select, groupes, placeholder) {
      const avant = select.value;
      select.replaceChildren(new Option(placeholder, ""));
      for (const groupe of groupes) {
        const parent = groupe.titre ? el("optgroup", { label: groupe.titre }) : select;
        for (const option of groupe.options) parent.append(new Option(option.label, option.value));
        if (groupe.titre) select.append(parent);
      }
      select.value = [...select.options].some(option => option.value === avant) ? avant : "";
    }

    /* ======================================================================
       Champs : un « contrôleur » par champ de champs.json
       ====================================================================== */
    function creerControleur(champ) {
      const controleur = {
        champ, nom: champ.nom, id: "f" + (compteurId++),
        revele: false,           // le champ est apparu (il reste affiché ensuite)
        confirme: false,         // l'utilisateur a validé la valeur (Tab, Entrée, choix...)
        auto: false,             // validé dès que la valeur est complète
        nePasFocaliser: false,   // ne pas donner le focus à l'apparition
        applicable: () => true,
        texte: () => "", valeur: () => "", complet: () => false,
        erreur: () => "", info: () => null,
        rafraichir: () => {}, initial: () => {},
        focusEl: null,
        focaliser: opts => controleur.focusEl && controleur.focusEl.focus(opts),
      };
      controleur.el = el("div", { class: "champ", "data-nom": champ.nom, hidden: true });
      controleur.aide = el("small", { class: "aide" });
      controleur.etiquette = el("label", { for: controleur.id },
        el("span", { class: "libelle", text: champ.libelle || champ.nom }),
        champ.obligatoire && !champ.auto_depuis && champ.type !== "affichage"
          ? el("span", { class: "requis", text: " *", "aria-hidden": "true" }) : null);

      switch (champ.type) {
        case "matricule": case "texte": champTexte(controleur); break;
        case "liste": champListe(controleur); break;
        case "date": champDate(controleur); break;
        case "entier": case "decimal": champNombre(controleur); break;
        case "affichage": champAffichage(controleur); break;
        case "commentaire": champRetour(controleur); break;
      }
      if (champ.manometre) champManometre(controleur);
      switch (champ.nom) {
        case NOMS.matiere: specialiserMatiere(controleur); break;
        case NOMS.article: specialiserArticle(controleur); break;
        case NOMS.machine: specialiserMachine(controleur); break;
        case NOMS.ma5: specialiserMa5(controleur); break;
      }
      ajouterPopup(controleur);
      controleur.initial();
      return controleur;
    }

    /* Bulle d'aide « i » (survol, clavier ou clic) */
    function ajouterPopup(controleur) {
      const contenu_popup = controleur.champ.popup;
      if (!contenu_popup || controleur.etiquette.parentNode !== controleur.el) return;
      const corps = el("div", { class: "popup-corps" });
      const popup = el("div", { class: "popup", role: "tooltip", id: controleur.id + "-pop" }, corps);
      const bouton = el("button", { type: "button", class: "info", "aria-label": "Aide sur « " + (controleur.champ.libelle || controleur.nom) + " »", "aria-describedby": controleur.id + "-pop", text: "i" });
      const wrap = el("span", { class: "info-wrap" }, bouton, popup);
      const ligne = el("div", { class: "etiquette-ligne" });
      controleur.el.replaceChild(ligne, controleur.etiquette);
      ligne.append(controleur.etiquette, wrap);
      bouton.addEventListener("click", evenement => {
        evenement.stopPropagation();
        document.querySelectorAll(".info-wrap.ouvert").forEach(enveloppe => { if (enveloppe !== wrap) enveloppe.classList.remove("ouvert"); });
        wrap.classList.toggle("ouvert");
      });
      controleur.popupMaj = () => {
        const enfants = [el("h4", { text: contenu_popup.titre })];
        for (const texte of contenu_popup.texte || []) enfants.push(el("p", { text: texte }));
        if (contenu_popup.dynamique === "perte") enfants.push(...contenuPerte());
        if (contenu_popup.images) enfants.push(el("div", { class: "popup-images" }, contenu_popup.images.map(image =>
          el("figure", {}, el("img", { src: image.src, alt: image.legende }), el("figcaption", { text: image.legende })))));
        corps.replaceChildren(...enfants);
      };
      controleur.popupMaj();
    }
    document.addEventListener("click", () => document.querySelectorAll(".info-wrap.ouvert").forEach(enveloppe => enveloppe.classList.remove("ouvert")));
    document.addEventListener("keydown", evenement => { if (evenement.key === "Escape") document.querySelectorAll(".info-wrap.ouvert").forEach(enveloppe => enveloppe.classList.remove("ouvert")); });

    function perteEuros() {
      const hauteur = nombreDe(NOMS.hFin), hi = nombreDe(NOMS.hInit), prix = CFG.prix_meule_moyenne_eur || 150;
      return hauteur !== null && hauteur > 0 && hi > 0 ? Math.min(hauteur, hi) / hi * prix : null;
    }
    function contenuPerte() {
      const prix = CFG.prix_meule_moyenne_eur || 150, hauteur = nombreDe(NOMS.hFin), hi = nombreDe(NOMS.hInit), perte = perteEuros();
      const paragraphes = [el("p", { text: "La meule doit être usée jusqu'au bout : chaque millimètre restant est de la meule payée et jetée." })];
      if (perte !== null) paragraphes.push(el("p", { class: "popup-perte", text: `Ici : ${fmt(hauteur)} mm restants sur ${fmt(hi)} mm ≈ ${euro(perte)} perdus (calcul sur une meule moyenne à ${prix} €).` }));
      else paragraphes.push(el("p", { text: `Repère : une meule moyenne coûte ${prix} €, donc environ ${euro(prix / 90)} par mm pour une meule de 90 mm.` }));
      if (PERTE) paragraphes.push(el("p", { text: `Cumul ${PERTE.annee} des meules non finies : ${euro(PERTE.total)} (${PERTE.nb} meules)` + (perte !== null ? `, ${euro(PERTE.total + perte)} avec celle-ci.` : ".") }));
      return paragraphes;
    }

    function champTexte(controleur) {
      const ch = controleur.champ;
      const input = el("input", {
        id: controleur.id, type: "text", name: ch.nom, autocomplete: "off",
        maxlength: ch.longueur, list: ch.type === "matricule" ? "dl-matricules" : null,
      });
      controleur.input = controleur.focusEl = input;
      controleur.texte = controleur.valeur = () => input.value.trim();
      controleur.complet = () => ch.longueur ? input.value.trim().length === ch.longueur : input.value.trim() !== "";
      controleur.auto = !!ch.longueur;                          // validé dès que la longueur est atteinte
      controleur.normaliser = () => {                           // « 534 » -> « 0534 »
        const valeur = input.value.trim();
        if (ch.type === "matricule" && /^\d+$/.test(valeur) && valeur.length < ch.longueur) input.value = valeur.padStart(ch.longueur, "0");
      };
      controleur.info = () => {
        const connus = LISTES.matricules || [];
        if (ch.type === "matricule" && controleur.complet() && connus.length && !connus.includes(input.value.trim()))
          return { texte: "⚠ Ce matricule n'a encore jamais été utilisé dans le fichier : vérifiez", niveau: "alerte" };
        return ch.aide ? { texte: ch.aide } : null;
      };
      controleur.initial = () => { input.value = ""; controleur.confirme = false; };
      controleur.el.append(controleur.etiquette, input, controleur.aide);
    }

    function champListe(controleur) {
      const ch = controleur.champ;
      const select = el("select", { id: controleur.id, name: ch.nom });
      controleur.select = controleur.input = controleur.focusEl = select;
      controleur.texte = controleur.valeur = () => select.value;
      controleur.complet = () => select.value !== "";
      controleur.auto = true;
      const base = ch.auto_depuis ? ["Oui", "Non"] : (ch.valeurs || LISTES[ch.nom] || []);
      setOptions(select, [{ options: base.map(valeur => ({ value: valeur, label: libVal(ch, valeur) })) }], "Choisir…");
      controleur.initial = () => { select.value = ""; controleur.confirme = false; };
      controleur.info = () => ch.aide ? { texte: ch.aide } : null;
      controleur.el.append(controleur.etiquette, select, controleur.aide);
    }

    function champDate(controleur) {
      const input = el("input", { id: controleur.id, type: "date", name: controleur.champ.nom });
      controleur.input = controleur.focusEl = input;
      controleur.nePasFocaliser = true;
      controleur.texte = controleur.valeur = () => input.value;
      controleur.complet = () => /^\d{4}-\d{2}-\d{2}$/.test(input.value);
      controleur.initial = () => { input.value = aujourdhui(); controleur.confirme = true; };     // prérempli : déjà validé
      controleur.info = () => input.value > aujourdhui()
        ? { texte: "⚠ Date dans le futur", niveau: "alerte" }
        : (controleur.champ.aide ? { texte: controleur.champ.aide } : null);
      controleur.el.append(controleur.etiquette, input, controleur.aide);
    }

    function champNombre(controleur) {
      const ch = controleur.champ, entier = ch.type === "entier";
      const input = el("input", {
        id: controleur.id, type: "number", name: ch.nom, step: entier ? "1" : "any",
        min: ch.min, max: ch.max, inputmode: entier ? "numeric" : "decimal",
      });
      controleur.input = controleur.focusEl = input;
      controleur.texte = () => input.value.trim();
      controleur.valeur = () => (input.value.trim() === "" ? "" : Number(input.value));
      controleur.regle = () => "";                               // règle supplémentaire entre champs (voir plus bas)
      const unite = ch.unite ? " " + ch.unite : "";
      controleur.erreur = () => {
        const texte = controleur.texte();
        if (texte === "") return "";
        const nombre = Number(texte);
        if (!Number.isFinite(nombre)) return "Valeur invalide";
        if (entier && !Number.isInteger(nombre)) return "Nombre entier attendu";
        if (ch.min != null && nombre < ch.min) return "Minimum : " + ch.min + unite;
        if (ch.max != null && nombre > ch.max) return "Maximum : " + ch.max + unite;
        return controleur.regle(nombre);
      };
      controleur.complet = () => controleur.texte() !== "" && controleur.erreur() === "";
      controleur.initial = () => { input.value = ch.defaut != null ? String(ch.defaut) : ""; controleur.confirme = false; };
      controleur.info = () => ch.aide ? { texte: ch.aide } : null;
      const saisie = ch.unite ? el("div", { class: "saisie" }, input, el("span", { class: "unite", text: ch.unite })) : input;
      controleur.el.append(controleur.etiquette, saisie, controleur.aide);
    }

    /* Pression d'arrosage : proposée à 6, avec la question du manomètre */
    function champManometre(controleur) {
      const defaut = String(controleur.champ.defaut ?? "");
      controleur.mano = null;                                    // null : pas encore répondu
      controleur.derniere = defaut;
      const bOui = el("button", { type: "button", class: "seg mini", "data-v": "oui", "aria-pressed": "false", text: "Oui" });
      const bNon = el("button", { type: "button", class: "seg mini", "data-v": "non", "aria-pressed": "false", text: "Non" });
      const question = el("div", { class: "question-inline" },
        el("span", { text: "Le manomètre fonctionne-t-il ?" }),
        el("div", { class: "segment" }, bOui, bNon));
      controleur.el.insertBefore(question, controleur.aide);

      const choisir = ok => {
        if (ok === false) {
          if (controleur.mano !== false) controleur.derniere = controleur.input.value || defaut;
          controleur.input.value = "0";
        } else if (controleur.mano === false) {
          controleur.input.value = controleur.derniere;                   // on rend la valeur proposée
        }
        controleur.mano = ok;
        controleur.confirme = controleur.complet();
        majTout();
      };
      bOui.addEventListener("click", () => choisir(true));
      bNon.addEventListener("click", () => choisir(false));

      const completDeBase = controleur.complet;
      controleur.complet = () => controleur.mano !== null && completDeBase();
      controleur.rafraichir = () => {
        if (controleur.mano !== false) controleur.derniere = controleur.input.value;
        controleur.input.readOnly = controleur.mano === false;
        bOui.setAttribute("aria-pressed", String(controleur.mano === true));
        bNon.setAttribute("aria-pressed", String(controleur.mano === false));
      };
      controleur.info = () => controleur.mano === false
        ? { texte: "Pression notée à 0 : manomètre hors service", niveau: "alerte" }
        : { texte: "Valeur proposée : " + defaut + " (modifiable). Répondez à la question du manomètre." };
      const initialDeBase = controleur.initial;
      controleur.initial = () => { initialDeBase(); controleur.mano = null; controleur.derniere = defaut; controleur.input.readOnly = false; };
    }

    function champAffichage(controleur) {
      const input = el("input", { id: controleur.id, type: "text", class: "lecture", readonly: true, tabindex: "-1" });
      controleur.input = input;
      controleur.nePasFocaliser = true;
      controleur.applicable = () => !!refFormat();
      controleur.texte = () => input.value;
      controleur.complet = () => true;
      controleur.rafraichir = () => { const reference = refFormat(); input.value = reference ? (reference.code || "—") : ""; };
      controleur.info = () => ({ texte: controleur.champ.aide || "" });
      controleur.initial = () => { input.value = ""; controleur.confirme = true; };
      controleur.el.append(controleur.etiquette, input, controleur.aide);
    }

    /* ---------- Champs qui dépendent du format et de la matière ---------- */
    function specialiserMatiere(controleur) {
      controleur.cleOptions = null;
      controleur.seule = false;
      controleur.rafraichir = () => {
        const format = texteDe(NOMS.format);
        if (format === controleur.cleOptions) return;
        controleur.cleOptions = format;
        const dispo = [...new Set(FORMATS.filter(reference => !format || reference.format === format).map(reference => reference.matiere))];
        const avant = controleur.select.value;
        setOptions(controleur.select, [{ options: dispo.map(valeur => ({ value: valeur, label: libVal(controleur.champ, valeur) })) }], "Choisir…");
        controleur.seule = !!format && dispo.length === 1;
        if (controleur.select.value === "" && controleur.seule) { controleur.select.value = dispo[0]; controleur.confirme = true; }
        else if (avant !== "" && controleur.select.value === "") controleur.confirme = false;
      };
      controleur.info = () => (controleur.seule ? { texte: "Seule matière possible pour ce format" } : null);
      const initialDeBase = controleur.initial;
      controleur.initial = () => { initialDeBase(); controleur.cleOptions = null; controleur.seule = false; };
    }

    function specialiserArticle(controleur) {
      controleur.cleRef = null;
      const detail = code => MEULES.find(meule => meule.code === code);
      const description = code => {
        const meule = detail(code);
        return meule ? [meule.fournisseur, meule.diametre ? "Ø " + meule.diametre + " mm" : ""].filter(Boolean).join(" · ") : "";
      };
      const libelle = code => {
        const meule = detail(code);
        if (!meule) return code;
        const etat = meule.etat && norm(meule.etat) !== "prod" ? " (" + meule.etat + ")" : "";
        return code + " — " + description(code) + etat;
      };
      controleur.rafraichir = () => {
        const reference = refFormat();
        const cle = reference ? reference.cle : "";
        if (cle === controleur.cleRef) return;
        controleur.cleRef = cle;
        const prevues = reference ? reference.meules : [];
        const autres = MEULES.map(meule => meule.code).filter(code => !prevues.includes(code));
        const groupes = [];
        if (prevues.length) groupes.push({ titre: "Meule prévue pour ce format", options: prevues.map(valeur => ({ value: valeur, label: libelle(valeur) })) });
        groupes.push({ titre: prevues.length ? "Autres meules (avertissement)" : "Meules référencées", options: autres.map(valeur => ({ value: valeur, label: libelle(valeur) })) });
        setOptions(controleur.select, groupes, "Choisir…");
        // une seule meule prévue : elle est proposée d'office (modifiable)
        controleur.select.value = prevues.length === 1 ? prevues[0] : "";
        controleur.confirme = prevues.length === 1;
      };
      controleur.info = () => {
        const reference = refFormat(), valeur = controleur.select.value;
        if (!reference) return null;
        const det = description(valeur);
        if (!valeur) return { texte: reference.meules.length ? "Choisissez la meule utilisée" : "Aucune meule prévue pour ce format : choisissez dans la liste" };
        if (!reference.meules.length) return { texte: det };
        if (reference.meules.includes(valeur)) return { texte: "✔ Meule prévue pour ce format" + (det ? " · " + det : ""), niveau: "ok" };
        return { texte: "⚠ Ce n'est pas la meule prévue (" + reference.meules.join(" / ") + ") — une confirmation sera demandée" + (det ? " · " + det : ""), niveau: "alerte" };
      };
      const initialDeBase = controleur.initial;
      controleur.initial = () => { initialDeBase(); controleur.cleRef = null; };
    }

    function specialiserMachine(controleur) {
      controleur.cleRef = null;
      controleur.prevues = () => { const reference = refFormat(); return reference ? reference.machines : []; };
      controleur.horsListe = () => { const prevues = controleur.prevues(), valeur = controleur.select.value; return !!(regleActive("machine_non_prevue") && valeur && prevues.length && !prevues.includes(valeur)); };
      controleur.rafraichir = () => {
        const reference = refFormat();
        const cle = reference ? reference.cle : "";
        if (cle === controleur.cleRef) return;
        controleur.cleRef = cle;
        const toutes = [...new Set([...(controleur.champ.options || []), ...(LISTES[NOMS.machine] || [])])].sort(comparer);
        const prevues = reference ? reference.machines : [];
        const opt = valeur => ({ value: valeur, label: valeur });
        const groupes = prevues.length
          ? [{ titre: "Prévues pour ce format", options: prevues.map(opt) },
             { titre: "Autres machines (avertissement)", options: toutes.filter(valeur => !prevues.includes(valeur)).map(opt) }]
          : [{ options: toutes.map(opt) }];
        setOptions(controleur.select, groupes, "Choisir…");
        if (controleur.select.value === "") controleur.confirme = false;
      };
      controleur.info = () => {
        const prevues = controleur.prevues(), valeur = controleur.select.value;
        if (!valeur || !prevues.length || !regleActive("machine_non_prevue")) return null;
        return controleur.horsListe()
          ? { texte: "⚠ Machine non prévue pour ce format (prévues : " + prevues.join(", ") + "). Une explication sera demandée.", niveau: "alerte" }
          : { texte: "✔ Machine prévue pour ce format", niveau: "ok" };
      };
      const initialDeBase = controleur.initial;
      controleur.initial = () => { initialDeBase(); controleur.cleRef = null; };
    }

    function specialiserMa5(controleur) {
      controleur.applicable = () => !!refFormat();
      const automatique = () => {
        const reference = refFormat(), valeur = reference ? norm(reference.ma5) : "";
        return valeur === "oui" || valeur === "non" ? valeur : null;
      };
      controleur.rafraichir = () => {
        const valeur_auto = automatique();
        if (valeur_auto) {
          controleur.select.value = valeur_auto === "oui" ? "Oui" : "Non";
          controleur.select.disabled = true;
          controleur.confirme = true;
        } else {
          if (controleur.select.disabled) { controleur.select.value = ""; controleur.confirme = false; }
          controleur.select.disabled = false;
        }
      };
      controleur.info = () => automatique()
        ? { texte: "Déterminé automatiquement d'après le format et la matière" }
        : { texte: "À choisir : ce format peut être MA5 ou non" };
      const initialDeBase = controleur.initial;
      controleur.initial = () => { initialDeBase(); controleur.select.disabled = false; };
    }

    /* ======================================================================
       Retour sur le démontage (commentaire guidé)
       ====================================================================== */
    function questionsContexte() {
      const questions = [];
      const cm = parNom[NOMS.machine];
      if (cm && cm.horsListe()) {
        questions.push(`La machine ${cm.select.value} n'est pas prévue pour ce format (prévues : ${cm.prevues().join(", ")}). Pourquoi l'avez-vous utilisée ?`);
      }
      const hauteur = nombreDe(NOMS.hFin);
      if (regleActive("non_fini") && hauteur !== null && hauteur > CFG.seuil_demontee_avant_usure_mm) {
        questions.push(`Il reste ${fmt(hauteur)} mm de meule : elle est démontée avant usure totale. Pourquoi ?`);
      }
      return questions;
    }

    function versDefaut() {
      const commentaire = ordre.find(controleur => controleur.champ.type === "commentaire");
      const hauteur = nombreDe(NOMS.hFin), defaut = CFG.defaut;
      return !!(commentaire && defaut && commentaire.choix === "non" && commentaire.puces.has(defaut.theme) && hauteur !== null && hauteur > CFG.seuil_demontee_avant_usure_mm);
    }

    function champRetour(controleur) {
      const retour = CFG.retour || {};
      const autre = retour.autre || "Autre";
      controleur.choix = null;                                   // "oui" | "non" | null
      controleur.puces = new Set();
      controleur.aide = null;
      controleur.el.classList.add("large");

      const question = el("p", { class: "retour-question", text: retour.question || "Tout s'est-il bien passé ?" });
      const bOui = el("button", { type: "button", class: "seg", "data-v": "oui", "aria-pressed": "false", text: retour.oui || "Oui, rien à signaler" });
      const bNon = el("button", { type: "button", class: "seg", "data-v": "non", "aria-pressed": "false", text: retour.non || "Non, j'ai une remarque" });
      const contextes = el("div", { class: "contextes" });
      const noteDefaut = el("p", { class: "contexte info", hidden: true });

      const boutonsPuces = {};
      const puces = el("div", { class: "puces" });
      for (const theme of retour.themes || []) {
        const bouton_theme = el("button", { type: "button", class: "puce", "aria-pressed": "false", text: theme });
        bouton_theme.addEventListener("click", () => { controleur.puces.has(theme) ? controleur.puces.delete(theme) : controleur.puces.add(theme); majTout(); });
        boutonsPuces[theme] = bouton_theme;
        puces.append(bouton_theme);
      }
      const zone = el("textarea", { id: controleur.id, name: controleur.champ.nom, rows: "3", placeholder: "Décrivez ce qui s'est passé, en quelques mots…" });
      const amorces = el("div", { class: "amorces" });
      for (const amorce of retour.aide || []) {
        const bouton_amorce = el("button", { type: "button", class: "amorce", text: amorce.question });
        bouton_amorce.addEventListener("click", () => {
          zone.value += (zone.value && !zone.value.endsWith("\n") ? "\n" : "") + amorce.amorce;
          zone.focus();
          majTout();
        });
        amorces.append(bouton_amorce);
      }
      const detail = el("div", { class: "retour-detail", hidden: true },
        contextes, noteDefaut,
        el("p", { class: "sous-titre", text: retour.question_theme || "Qu'est-ce qui a posé problème ?" }),
        puces, zone,
        el("p", { class: "sous-titre", text: "Pour vous aider à décrire :" }),
        amorces);
      controleur.el.append(question, el("div", { class: "segment" }, bOui, bNon), detail);

      bOui.addEventListener("click", () => { if (!bOui.disabled) { controleur.choix = "oui"; majTout(); } });
      bNon.addEventListener("click", () => { controleur.choix = "non"; majTout(); });

      controleur.commentaire = () => {
        const texte = zone.value.trim(), puces = [...controleur.puces].join(" ; ");
        return puces && texte ? puces + " — " + texte : (puces || texte);
      };
      controleur.rafraichir = () => {
        const questions = questionsContexte();
        contextes.replaceChildren(...questions.map(question => el("p", { class: "contexte", text: "❓ " + question })));
        bOui.disabled = questions.length > 0;                   // une explication est exigée : « Oui » impossible
        if (questions.length && controleur.choix !== "non") controleur.choix = "non";
        bOui.setAttribute("aria-pressed", String(controleur.choix === "oui"));
        bNon.setAttribute("aria-pressed", String(controleur.choix === "non"));
        detail.hidden = controleur.choix !== "non";
        const dest = versDefaut();
        noteDefaut.hidden = !dest;
        noteDefaut.textContent = dest ? "📋 Cette meule sera aussi enregistrée dans l'onglet « " + CFG.defaut.onglet + " » (meules défectueuses)." : "";
        for (const [theme, bouton_theme] of Object.entries(boutonsPuces)) bouton_theme.setAttribute("aria-pressed", String(controleur.puces.has(theme)));
      };
      controleur.complet = () => {
        if (controleur.choix === null) return false;
        if (controleur.choix === "oui") return questionsContexte().length === 0;
        const texte = zone.value.trim(), puces = [...controleur.puces];
        if (!texte && puces.length === 0) return false;
        if (!texte && puces.every(puce => puce === autre)) return false;       // « Autre » seul ne dit rien
        return true;
      };
      controleur.valeur = () => (controleur.choix === "oui" && questionsContexte().length === 0 ? "" : controleur.commentaire());
      controleur.texte = controleur.valeur;
      controleur.libelleCourt = "Retour sur le démontage";
      controleur.focusEl = bOui;
      controleur.focaliser = opts => (bOui.disabled ? bNon : bOui).focus(opts);
      controleur.initial = () => { controleur.choix = null; controleur.puces.clear(); zone.value = ""; controleur.confirme = true; };
    }

    /* ---------- Médiane (information, ne bloque rien) ---------- */
    function champMediane() {
      const controleur = creerControleurVide({ nom: "__mediane", libelle: "Médiane", type: "info", section: "monteur" });
      controleur.el = el("div", { class: "champ large mediane-champ", hidden: true });
      const faces = el("div", { class: "faces" });
      controleur.el.append(el("div", { class: "titre", text: "Médiane de faces par meule de 89 mm (à titre indicatif)" }), faces);
      controleur.aide = null;
      controleur.nePasFocaliser = true;
      controleur.applicable = () => !!(texteDe(NOMS.article) && texteDe(NOMS.machine) && texteDe(NOMS.matiere));
      controleur.complet = () => true;
      controleur.rafraichir = () => {
        if (!controleur.applicable()) return;
        const cle = [texteDe(NOMS.article), texteDe(NOMS.machine), texteDe(NOMS.matiere)].join("|");
        if (cle === cleMediane) return;
        cleMediane = cle;
        const url = "/api/mediane?article=" + encodeURIComponent(texteDe(NOMS.article))
                  + "&machine=" + encodeURIComponent(texteDe(NOMS.machine))
                  + "&matiere=" + encodeURIComponent(texteDe(NOMS.matiere));
        getJSON(url).then(medianes => {
          if (cle !== cleMediane) return;
          faces.replaceChildren(...["A", "B"].map(face => {
            const mediane_face = medianes[face];
            return el("div", { class: "face" },
              el("small", { text: "Face " + face }),
              el("strong", { text: mediane_face ? String(mediane_face.mediane) : "—" }),
              el("small", { text: mediane_face ? `${mediane_face.nb_cas} cas · ${mediane_face.critere}${mediane_face.fiable ? "" : " · peu fiable"}` : "pas de données" }));
          }));
        }).catch(() => faces.replaceChildren(el("small", { text: "Médiane indisponible" })));
      };
      controleur.initial = () => { cleMediane = ""; faces.replaceChildren(); controleur.confirme = true; };
      controleur.initial();
      return controleur;
    }
    function creerControleurVide(champ) {
      return {
        champ, nom: champ.nom, id: "f" + (compteurId++), revele: false, confirme: true, auto: false,
        nePasFocaliser: true, applicable: () => true, texte: () => "", valeur: () => "", complet: () => true,
        erreur: () => "", info: () => null, rafraichir: () => {}, initial: () => {}, focusEl: null, focaliser: () => {},
      };
    }

    /* ======================================================================
       Apparition progressive, sections, bouton
       ====================================================================== */
    function sectionDe(controleur) { return sections[controleur.champ.section]; }

    function majVisibilite() {
      let ok = true;
      const nouveaux = [];
      for (const controleur of ordre) {
        const app = controleur.applicable();
        if (app && ok && !controleur.revele) { controleur.revele = true; nouveaux.push(controleur); }
        controleur.el.hidden = !(app && controleur.revele);
        if (app) ok = ok && controleur.confirme && controleur.complet();
      }
      for (const controleur of nouveaux) {
        controleur.el.classList.add("nouveau");
        setTimeout(() => controleur.el.classList.remove("nouveau"), 1500);
      }
      focaliser(nouveaux);
    }

    function focaliser(nouveaux) {
      const cible = [...nouveaux].reverse().find(controleur => controleur.focusEl && !controleur.nePasFocaliser);
      if (!cible) return;
      const section = sectionDe(cible);
      const debutDeSection = section && section.ctrls[0] === cible && section !== sections[CFG.sections[0].id];
      cible.focaliser({ preventScroll: debutDeSection });
      if (debutDeSection && section.passage) {
        section.passage.scrollIntoView({ behavior: reduit ? "auto" : "smooth", block: "start" });
      }
    }

    function focusSuivant(controleur) {
      const position = ordre.indexOf(controleur);
      const suivant = ordre.slice(position + 1).find(candidat => candidat.applicable() && !candidat.el.hidden && candidat.focusEl && !candidat.nePasFocaliser);
      if (suivant) suivant.focaliser();
    }

    function majSections() {
      const liste = CFG.sections.map(cfg => sections[cfg.id]);
      const etat = liste.map(section => {
        const app = section.ctrls.filter(controleur => controleur.applicable());
        return { visible: app.some(controleur => controleur.revele), complete: app.every(controleur => controleur.complet()) };
      });
      let actif = etat.findIndex(statut => !(statut.visible && statut.complete));
      if (actif === -1) actif = liste.length - 1;
      liste.forEach((section, position) => {
        const statut = etat[position];
        if (statut.visible && section.racine.hidden) {
          section.racine.hidden = false;
          if (section.passage) section.passage.hidden = false;
        } else if (!statut.visible && !section.racine.hidden) {
          section.racine.hidden = true;
          if (section.passage) section.passage.hidden = true;
        }
        const fini = statut.visible && statut.complete;
        section.racine.classList.toggle("terminee", fini);
        section.badge.hidden = !fini;
        section.li.classList.toggle("fait", fini);
        section.li.classList.toggle("actif", position === actif && !fini);
        section.pastille.textContent = fini ? "✔" : String(section.cfg.numero);
      });
    }

    function majAffichageChamps() {
      for (const controleur of ordre) {
        if (!controleur.aide) continue;
        const erreur = controleur.erreur() || controleur.erreurServeur || "";
        const hab = controleur.alerteHab ? { texte: "⚠ " + controleur.alerteHab, niveau: "alerte" } : null;
        const srv = controleur.alerteServeur ? { texte: "⚠ " + controleur.alerteServeur, niveau: "alerte" } : null;
        const info = erreur ? { texte: erreur, niveau: "erreur" } : (hab || srv || controleur.info());
        controleur.aide.textContent = info && info.texte ? info.texte : "";
        controleur.aide.className = "aide" + (info && info.niveau ? " " + info.niveau : "");
        controleur.el.classList.toggle("invalide", !!erreur);
        controleur.el.classList.toggle("alerte", !erreur && !!info && info.niveau === "alerte");      // bordure de la couleur de l'avertissement
        if (controleur.popupMaj && controleur.champ.popup.dynamique) controleur.popupMaj();
      }
    }

    function majBouton() {
      const manquants = ordre
        .filter(controleur => controleur.applicable() && !controleur.complet())
        .map(controleur => controleur.libelleCourt || controleur.champ.libelle || controleur.nom);
      bouton.disabled = envoiEnCours || manquants.length > 0;
      manque.textContent = manquants.length
        ? "Il reste à renseigner : " + manquants.slice(0, 3).join(", ") + (manquants.length > 3 ? " … (+" + (manquants.length - 3) + ")" : "")
        : "Tout est prêt : vérifiez, puis enregistrez.";
    }

    function majTout() {
      for (const controleur of ordre) controleur.rafraichir();
      majAffichageChamps();
      majVisibilite();
      majSections();
      majBouton();
    }

    /* ---------- Événements ---------- */
    const controleurDe = cible => {
      const champ = cible.closest && cible.closest(".champ");
      return champ ? parNom[champ.dataset.nom] : null;
    };

    formulaire.addEventListener("input", evenement => {
      const controleur = controleurDe(evenement.target);
      if (!controleur) return;
      effacerMessages();
      controleur.alerteServeur = controleur.erreurServeur = null;
      if (controleur.auto && controleur.complet()) controleur.confirme = true;
      else if (!controleur.complet()) controleur.confirme = false;
      majTout();
      verifHabitude(controleur);
    });
    const timersHab = {};
    function verifHabitude(controleur) {                         // « valeur inhabituelle » : question posée au serveur
      if (!((CFG.controle_habituel || {}).champs || []).includes(controleur.nom)) return;
      clearTimeout(timersHab[controleur.nom]);
      const texte = controleur.texte();
      if (texte === "" || controleur.erreur()) { controleur.alerteHab = ""; return; }
      timersHab[controleur.nom] = setTimeout(async () => {
        try {
          const reponse = await post("/api/habitude", { nom: controleur.nom, valeur: texte, article: texteDe(NOMS.article), matiere: texteDe(NOMS.matiere) });
          if (controleur.texte() !== texte) return;
          const message = (reponse.corps && reponse.corps.message) || "";
          controleur.alerteHab = message.startsWith(controleur.nom + " : ") ? message.slice(controleur.nom.length + 3) : message;
          majAffichageChamps();
        } catch (erreur) {}
      }, 350);
    }
    formulaire.addEventListener("change", evenement => {
      const controleur = controleurDe(evenement.target);
      if (!controleur) return;
      if (controleur.normaliser) controleur.normaliser();
      controleur.confirme = controleur.complet();
      majTout();
    });
    formulaire.addEventListener("keydown", evenement => {
      if (evenement.key !== "Enter" || evenement.target.tagName === "TEXTAREA" || evenement.target.tagName === "BUTTON") return;
      evenement.preventDefault();                               // Entrée = passer au champ suivant
      const controleur = controleurDe(evenement.target);
      if (!controleur) return;
      if (controleur.normaliser) controleur.normaliser();
      if (controleur.complet()) controleur.confirme = true;
      const avant = document.activeElement;
      majTout();
      if (document.activeElement === avant) focusSuivant(controleur);
    });

    /* ======================================================================
       Messages et enregistrement
       ====================================================================== */
    function marquerChamps(messages, propriete) {       // « Nom du champ : message » -> bordure sur ce champ
      for (const message of messages) {
        const controleur = ordre.find(controleur => message.startsWith(controleur.nom + " : "));
        if (controleur) controleur[propriete] = message.slice(controleur.nom.length + 3);
      }
      majAffichageChamps();
    }

    function effacerMessages() { zoneMessages.textContent = ""; }

    function afficher(titre, lignes, classe) {
      if (!lignes || lignes.length === 0) return;
      const ul = el("ul", {}, lignes.map(ligne => el("li", { text: ligne })));
      zoneMessages.append(el("div", { class: "message " + classe }, el("strong", { text: titre }), ul));
      zoneMessages.scrollIntoView({ block: "nearest", behavior: reduit ? "auto" : "smooth" });
    }

    function collecter() {
      const donnees = {};
      for (const controleur of ordre) {
        if (!controleur.applicable() || controleur.champ.type === "affichage" || controleur.nom.startsWith("__")) continue;
        donnees[controleur.nom] = controleur.valeur();
      }
      return donnees;
    }

    function demanderConfirmation(donnees) {
      const ok = el("button", { type: "button", class: "bouton", text: "Enregistrer malgré les avertissements" });
      ok.addEventListener("click", async () => { effacerMessages(); await enregistrer(donnees); });
      const non = el("button", { type: "button", class: "bouton secondaire", text: "Corriger la saisie" });
      non.addEventListener("click", effacerMessages);
      zoneMessages.append(el("div", { class: "actions" }, ok, non));
    }

    function reinitialiser() {
      for (const controleur of ordre) { controleur.revele = false; controleur.alerteHab = controleur.alerteServeur = controleur.erreurServeur = null; controleur.initial(); }
      majTout();
      getJSON("/api/perte").then(perte => { PERTE = perte; majAffichageChamps(); }).catch(() => {});
    }

    const pause = ms => new Promise(resoudre => setTimeout(resoudre, ms));

    /** Lance l'enregistrement puis suit son avancement (étape par étape) jusqu'au résultat. */
    async function suivreEnregistrement(donnees) {
      const demarrage = await post("/api/ajout", donnees);
      if (demarrage.statut !== 202) return demarrage;                         // refus immédiat (erreurs de saisie...)
      const id = demarrage.corps.travail;
      let echecs = 0;
      for (;;) {
        await pause(350);
        try {
          const rep = await fetch("/api/ajout/" + id);
          const contenu = await rep.json();
          echecs = 0;
          if (rep.status === 404) return { statut: 404, corps: contenu };
          if (contenu.fini) return { statut: contenu.statut, corps: contenu.corps };
          Chargement.etape(contenu.etape);
        } catch (erreur) {
          if (++echecs > 20) { const err = new Error("connexion perdue"); err.perdue = true; throw err; }
        }
      }
    }

    async function enregistrer(donnees) {
      envoiEnCours = true;
      bouton.textContent = "Enregistrement…";
      majBouton();
      Chargement.ouvrir("envoi");
      try {
        const resultat = await suivreEnregistrement(donnees);
        if (resultat.statut === 200 && resultat.corps.ok) {
          await Chargement.terminer();
          effacerMessages();
          reinitialiser();
          zoneMessages.append(el("div", { class: "message succes" },
            el("strong", { text: "✔ Saisie enregistrée (ligne " + resultat.corps.ligne + ")" }),
            el("p", { text: `Meule ${donnees[NOMS.article]} · face ${donnees[NOMS.face]} · machine ${donnees[NOMS.machine]}` }),
            resultat.corps.defaut ? el("p", { text: "📋 Également enregistrée dans l'onglet « " + resultat.corps.defaut.onglet + " »." }) : null));
          if (resultat.corps.defaut && resultat.corps.defaut.colonnes_absentes.length) {
            afficher("Onglet défaut : colonnes absentes, non remplies :", resultat.corps.defaut.colonnes_absentes, "avertissements");
          }
          window.scrollTo({ top: 0, behavior: reduit ? "auto" : "smooth" });
        } else {
          afficher("Erreurs :", resultat.corps.erreurs || ["Erreur serveur (" + resultat.statut + ")"], "erreurs");
          afficher("Avertissements :", resultat.corps.avertissements, "avertissements");
          if (resultat.statut === 409) {                       // fichier occupé : proposer de réessayer
            const bouton_reessayer = el("button", { type: "button", class: "bouton", text: "Réessayer" });
            bouton_reessayer.addEventListener("click", async () => { effacerMessages(); await enregistrer(donnees); });
            zoneMessages.append(el("div", { class: "actions" }, bouton_reessayer));
          }
        }
      } catch (erreur) {
        Chargement.fermer();
        afficher("Erreurs :", erreur.perdue
          ? ["Connexion perdue pendant l'enregistrement. La saisie a peut-être été enregistrée : vérifiez dans la consultation avant de recommencer."]
          : ["Impossible de joindre le serveur."], "erreurs");
      } finally {
        Chargement.fermer();
        Chargement.chargerReglage();                       // prend en compte un changement fait dans l'administration
        envoiEnCours = false;
        bouton.textContent = "Enregistrer";
        majBouton();
      }
    }

    formulaire.addEventListener("submit", async evenement => {
      evenement.preventDefault();
      if (bouton.disabled) return;
      effacerMessages();
      const donnees = collecter();
      envoiEnCours = true;
      majBouton();
      Chargement.ouvrir("verification");
      try {
        const verification = await post("/api/verifier", donnees);
        const erreurs = verification.corps.erreurs || (verification.statut >= 400 ? ["Erreur serveur (" + verification.statut + ")"] : []);
        marquerChamps(erreurs, "erreurServeur");
        marquerChamps(verification.corps.avertissements || [], "alerteServeur");
        if (erreurs.length) {
          afficher("Erreurs :", erreurs, "erreurs");
          afficher("Avertissements :", verification.corps.avertissements, "avertissements");
          return;
        }
        const avertissements = verification.corps.avertissements || [];
        if (avertissements.length) {
          afficher("Avertissements :", avertissements, "avertissements");
          demanderConfirmation(donnees);
          return;
        }
        envoiEnCours = false;
        await enregistrer(donnees);
      } catch (err) {
        afficher("Erreurs :", ["Impossible de joindre le serveur."], "erreurs");
      } finally {
        Chargement.fermer();
        envoiEnCours = false;
        majBouton();
      }
    });

    /* ======================================================================
       Démarrage
       ====================================================================== */
    function construireSections() {
      const zone = document.getElementById("sections");
      const etapes = document.getElementById("etapes");
      for (const cfg of CFG.sections) {
        const badge = el("span", { class: "badge-ok", hidden: true, text: "✔ Complète" });
        const corps = el("div", { class: "champs" });
        const racine = el("section", { class: "section", "data-section": cfg.id, hidden: true },
          el("header", { class: "section-entete" },
            el("span", { class: "num", text: String(cfg.numero) }),
            el("div", {}, el("h2", { text: cfg.titre }), el("p", { text: cfg.sous_titre || "" })),
            badge),
          corps);
        const passage = cfg.passage ? el("div", { class: "passage", hidden: true }, el("span", { text: cfg.passage })) : null;
        if (passage) zone.append(passage);
        zone.append(racine);
        const pastille = el("span", { class: "pastille", text: String(cfg.numero) });
        const li = el("li", { "data-section": cfg.id }, pastille, cfg.titre);
        etapes.append(li);
        sections[cfg.id] = { cfg, racine, corps, badge, passage, li, pastille, ctrls: [] };
      }
    }

    async function init() {
      try {
        getJSON("/api/perte").then(perte => { PERTE = perte; if (ordre.length) majAffichageChamps(); }).catch(() => {});
        [CFG, LISTES, FORMATS, MEULES] = await Promise.all([
          getJSON("/api/champs"), getJSON("/api/listes"), getJSON("/api/formats"), getJSON("/api/meules"),
        ]);
      } catch (erreur) {
        afficher("Erreurs :", ["Impossible de charger les données du serveur. Vérifiez que le serveur est lancé."], "erreurs");
        return;
      }
      document.getElementById("dl-matricules").append(
        ...(LISTES.matricules || []).map(matricule => el("option", { value: matricule })));
      construireSections();

      const liste = CFG.champs.map(creerControleur);
      const iMachine = liste.findIndex(controleur => controleur.nom === NOMS.machine);
      liste.splice(iMachine + 1, 0, champMediane());           // la médiane s'affiche juste après la machine

      // règles qui font intervenir plusieurs champs
      const regle = (nom, fonction) => { if (parNom[nom]) parNom[nom].regle = fonction; };
      for (const controleur of liste) { parNom[controleur.nom] = controleur; }
      regle(NOMS.fin, nombre => {
        const debut = nombreDe(NOMS.debut);
        if (debut !== null && nombre < debut) return "Doit être supérieur ou égal au compteur début (" + debut + ")";
        return "";
      });
      regle(NOMS.hFin, nombre => {
        const hauteur_initiale = nombreDe(NOMS.hInit);
        return hauteur_initiale !== null && nombre > hauteur_initiale ? "Ne peut pas dépasser la hauteur initiale (" + fmt(hauteur_initiale) + " mm)" : "";
      });
      if (parNom[NOMS.fin]) {
        parNom[NOMS.fin].info = () => nombreDe(NOMS.fin) === 0
          ? { texte: "⚠ 0 sera enregistré comme 1, pour ne pas casser les formules Excel", niveau: "alerte" } : null;
      }
      if (parNom[NOMS.hFin]) {
        const base = parNom[NOMS.hFin];
        base.info = () => {
          const hauteur = nombreDe(NOMS.hFin), perte = perteEuros();
          if (hauteur === null || hauteur <= 0) return null;
          let texte = `💶 ${fmt(hauteur)} mm non utilisés` + (perte !== null ? ` ≈ ${euro(perte)} perdus (meule moyenne à ${CFG.prix_meule_moyenne_eur || 150} €)` : "");
          if (PERTE) texte += ` · cumul ${PERTE.annee} : ${euro(PERTE.total + (perte || 0))}`;
          if (hauteur > CFG.seuil_demontee_avant_usure_mm) texte += " · ⚠ meule marquée « démontée avant usure totale » (X)";
          return { texte: texte, niveau: "alerte" };
        };
      }

      for (const controleur of liste) {
        ordre.push(controleur);
        const section = sections[controleur.champ.section];
        section.ctrls.push(controleur);
        section.corps.append(controleur.el);
      }
      majTout();
    }
    init();
    getJSON("/api/etat").then(etat => {
      if (etat.test) document.getElementById("bandeau-test").hidden = false;
      if (etat.demo) document.getElementById("bandeau-demo").hidden = false;
      if (!etat.existe) afficher("Erreurs :", ["Le fichier Excel est introuvable (" + etat.fichier + "). Vérifiez chemin_fichier.txt."], "erreurs");
    }).catch(() => {});

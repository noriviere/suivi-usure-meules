"use strict";
/* Back-office : connexion, section « Comptes », section « Règles métier ». */
const racine = document.getElementById("racine");
let MOI = null;

/* ---------- appels au serveur ---------- */
async function api(url, methode = "GET", corps = null) {
  const reponse = await fetch(url, {
    method: methode,
    headers: corps ? { "Content-Type": "application/json" } : {},
    body: corps ? JSON.stringify(corps) : undefined,
  });
  let contenu = {};
  try { contenu = await reponse.json(); } catch (erreur) { /* réponse vide */ }
  if (reponse.status === 401 && url !== "/api/admin/connexion") { MOI = null; afficherConnexion(); throw new Error("deconnecte"); }
  return { ok: reponse.ok, statut: reponse.status, corps: contenu };
}
const messagesDe = reponse => [].concat(reponse.corps.detail || reponse.corps.erreurs || ["Erreur (" + reponse.statut + ")"]).map(message => typeof message === "string" ? message : JSON.stringify(message));
const boite = (type, titre, lignes = []) => creerElement("div", { class: "message " + type }, creerElement("strong", { text: titre }),
  lignes.length ? creerElement("ul", {}, ...lignes.map(texte => creerElement("li", { text: texte }))) : null);
const afficher = (zone, type, titre, lignes) => zone.replaceChildren(boite(type, titre, lignes));
const champ = (libelle, attrs) => { const entree = creerElement("input", attrs); return [creerElement("label", {}, libelle, entree), entree]; };

/* ---------- connexion ---------- */
async function afficherConnexion() {
  const [lNom, nom] = champ("Nom d'utilisateur", { type: "text", id: "c-nom", autocomplete: "username" });
  const [lMdp, mdp] = champ("Mot de passe", { type: "password", id: "c-mdp", autocomplete: "current-password" });
  const msg = creerElement("div", { "aria-live": "polite" });
  const aide = creerElement("p", { class: "petit" });
  const form = creerElement("form", { class: "formulaire-admin" }, lNom, lMdp, creerElement("button", { type: "submit", class: "bouton", text: "Se connecter" }), msg);
  form.addEventListener("submit", async evenement => {
    evenement.preventDefault();
    const reponse = await api("/api/admin/connexion", "POST", { nom: nom.value, mot_de_passe: mdp.value });
    if (!reponse.ok) { afficher(msg, "erreurs", messagesDe(reponse)[0]); mdp.value = ""; return; }
    MOI = reponse.corps; afficherAdmin();
  });
  racine.replaceChildren(creerElement("div", { class: "panneau connexion" }, creerElement("h1", { text: "Administration" }), form, aide,
    creerElement("p", { class: "petit" }, creerElement("a", { class: "lien", href: "index.html", text: "← Retour à la saisie" }))));
  const etat = await fetch("/api/admin/etat").then(reponse => reponse.json()).catch(() => ({}));
  if (etat.compte_demo) aide.textContent = "Démonstration : connectez-vous avec le compte « " + etat.compte_demo.nom + " », mot de passe « " + etat.compte_demo.mot_de_passe + " ».";
  else if (etat.aucun_compte) aide.textContent = "Aucun compte n'existe encore. Lancez scripts\\creer_utilisateur.bat sur le PC serveur pour créer le premier.";
  nom.focus();
}

/* ---------- page principale ---------- */
const SECTIONS = [["comptes", "Comptes"], ["regles", "Règles métier"], ["affichage", "Affichage"]];
function afficherAdmin(section = "comptes") {
  const corps = creerElement("section", { class: "panneau" });
  const onglets = creerElement("div", { class: "onglets", role: "tablist" }, ...SECTIONS.map(([id, titre]) =>
    creerElement("button", { class: "onglet", role: "tab", "aria-selected": String(id === section), text: titre, onclick: () => afficherAdmin(id) })));
  const deco = creerElement("button", { type: "button", class: "bouton secondaire", text: "Se déconnecter", onclick: async () => { await api("/api/admin/deconnexion", "POST"); MOI = null; afficherConnexion(); } });
  racine.replaceChildren(
    creerElement("div", { class: "entete-page" }, creerElement("h1", { text: "Administration" }),
      creerElement("span", { class: "liens" }, creerElement("span", { class: "petit", id: "nom-connecte", text: "Connecté : " + MOI.nom }), creerElement("a", { class: "lien", href: "consultation.html", text: "Consultation" }),
        creerElement("a", { class: "lien", href: "index.html", text: "Saisie" }), deco)),
    onglets, corps);
  ({ comptes: sectionComptes, regles: sectionRegles, affichage: sectionAffichage }[section])(corps);
}

/* ---------- section 1 : comptes ---------- */
async function sectionComptes(zone) {
  let comptes = (await api("/api/admin/utilisateurs")).corps;
  let aSupprimer = null, aReinitialiser = null;
  const msgMoi = creerElement("div", { "aria-live": "polite" }), msgListe = creerElement("div", { "aria-live": "polite" });
  const liste = creerElement("div", {});

  async function recharger() { comptes = (await api("/api/admin/utilisateurs")).corps; aSupprimer = aReinitialiser = null; dessinerListe(); }

  function dessinerListe() {
    liste.replaceChildren(...comptes.map(compte => {
      const ligne = creerElement("div", { class: "ligne-compte" },
        creerElement("span", { class: "nom", text: compte.nom + (compte.id === MOI.id ? " (vous)" : "") }),
        creerElement("span", { class: "derniere", text: compte.derniere_connexion ? "Dernière connexion : " + compte.derniere_connexion.replace("T", " ") : "Jamais connecté" }));
      if (aReinitialiser === compte.id) {
        const [lR, rMdp] = champ("Nouveau mot de passe", { type: "password", id: "r-mdp", autocomplete: "new-password" });
        ligne.append(lR,
          creerElement("button", { type: "button", class: "bouton", text: "Enregistrer", onclick: async () => {
            const rr = await api(`/api/admin/utilisateurs/${compte.id}/mot-de-passe`, "POST", { mot_de_passe: rMdp.value });
            if (!rr.ok) return afficher(msgListe, "erreurs", messagesDe(rr)[0]);
            await recharger(); afficher(msgListe, "succes", `✔ Mot de passe de ${compte.nom} changé. Ses sessions ouvertes sont fermées.`); } }),
          creerElement("button", { type: "button", class: "bouton secondaire", text: "Annuler", onclick: () => { aReinitialiser = null; dessinerListe(); } }));
      } else {
        ligne.append(creerElement("button", { type: "button", class: "bouton secondaire", text: "Nouveau mot de passe", onclick: () => { aReinitialiser = compte.id; aSupprimer = null; dessinerListe(); } }));
      }
      if (compte.id !== MOI.id) {
        ligne.append(aSupprimer === compte.id
          ? creerElement("button", { type: "button", class: "bouton secondaire danger", text: "Confirmer la suppression", onclick: async () => {
              const rr = await api("/api/admin/utilisateurs/" + compte.id, "DELETE");
              if (!rr.ok) return afficher(msgListe, "erreurs", messagesDe(rr)[0]);
              await recharger(); afficher(msgListe, "succes", `✔ Compte ${compte.nom} supprimé.`); } })
          : creerElement("button", { type: "button", class: "bouton secondaire danger", text: "Supprimer", onclick: () => { aSupprimer = compte.id; aReinitialiser = null; dessinerListe(); } }));
      }
      return ligne;
    }));
  }

  // Mon nom d'utilisateur
  const [lN, nNom] = champ("Nouveau nom d'utilisateur", { type: "text", id: "m-nom", value: MOI.nom, autocomplete: "username" });
  const [lP, nMdp] = champ("Mot de passe actuel (pour confirmer)", { type: "password", id: "m-nom-mdp", autocomplete: "current-password" });
  const formNom = creerElement("form", { class: "formulaire-admin" }, lN, lP, creerElement("button", { class: "bouton", type: "submit", text: "Changer mon nom" }));
  formNom.addEventListener("submit", async evenement => {
    evenement.preventDefault();
    const rr = await api("/api/admin/moi/nom", "POST", { nom: nNom.value, mot_de_passe: nMdp.value });
    if (!rr.ok) return afficher(msgMoi, "erreurs", messagesDe(rr)[0]);
    MOI.nom = nNom.value.trim(); nMdp.value = "";
    document.getElementById("nom-connecte").textContent = "Connecté : " + MOI.nom;
    await recharger(); afficher(msgMoi, "succes", "✔ Nom d'utilisateur changé : " + MOI.nom);
  });

  // Mon mot de passe
  const [lA, aMdp] = champ("Mot de passe actuel", { type: "password", id: "m-ancien", autocomplete: "current-password" });
  const [lB, bMdp] = champ("Nouveau mot de passe (8 caractères minimum)", { type: "password", id: "m-nouveau", autocomplete: "new-password" });
  const [lC, cMdp] = champ("Nouveau mot de passe, encore une fois", { type: "password", id: "m-confirme", autocomplete: "new-password" });
  const formMdp = creerElement("form", { class: "formulaire-admin" }, lA, lB, lC, creerElement("button", { class: "bouton", type: "submit", text: "Changer mon mot de passe" }));
  formMdp.addEventListener("submit", async evenement => {
    evenement.preventDefault();
    if (bMdp.value !== cMdp.value) return afficher(msgMoi, "erreurs", "Les deux nouveaux mots de passe sont différents.");
    const rr = await api("/api/admin/moi/mot-de-passe", "POST", { ancien: aMdp.value, nouveau: bMdp.value });
    if (!rr.ok) return afficher(msgMoi, "erreurs", messagesDe(rr)[0]);
    [aMdp, bMdp, cMdp].forEach(entree => entree.value = "");
    afficher(msgMoi, "succes", "✔ Mot de passe changé.");
  });

  // Nouveau compte
  const [lU, uNom] = champ("Nom d'utilisateur", { type: "text", id: "n-nom", autocomplete: "off" });
  const [lW, uMdp] = champ("Mot de passe initial (8 caractères minimum)", { type: "password", id: "n-mdp", autocomplete: "new-password" });
  const formNouveau = creerElement("form", { class: "formulaire-admin" }, lU, lW, creerElement("button", { class: "bouton", type: "submit", text: "Créer le compte" }));
  formNouveau.addEventListener("submit", async evenement => {
    evenement.preventDefault();
    const rr = await api("/api/admin/utilisateurs", "POST", { nom: uNom.value, mot_de_passe: uMdp.value });
    if (!rr.ok) return afficher(msgListe, "erreurs", messagesDe(rr)[0]);
    const nom = uNom.value.trim(); uNom.value = uMdp.value = "";
    await recharger(); afficher(msgListe, "succes", `✔ Compte ${nom} créé.`);
  });

  dessinerListe();
  zone.replaceChildren(
    creerElement("div", { class: "grille-admin" },
      creerElement("div", { class: "carte-admin" }, creerElement("h3", { text: "Mon nom d'utilisateur" }), formNom),
      creerElement("div", { class: "carte-admin" }, creerElement("h3", { text: "Mon mot de passe" }), formMdp)),
    msgMoi,
    creerElement("h3", { text: "Comptes" }),
    creerElement("p", { class: "petit", text: "Tous les comptes ont les mêmes droits : gérer les comptes et modifier les règles métier." }),
    liste, msgListe,
    creerElement("div", { class: "carte-admin", style: "margin-top:16px;max-width:420px" }, creerElement("h3", { text: "Nouveau compte" }), formNouveau));
}

/* ---------- section 2 : règles métier ---------- */
async function sectionRegles(zone) {
  const reponse = await api("/api/admin/reglages");
  const etat_regles = reponse.corps;
  const saisies = {};                                  // id -> { actif: input|null, params: { cle: input } }
  const msg = creerElement("div", { class: "msg-admin", "aria-live": "polite" });
  const groupes = [...new Set(etat_regles.regles.map(regle => regle.groupe))];
  const blocs = groupes.map(groupe => creerElement("section", { class: "groupe-regles" }, creerElement("h3", { text: groupe }),
    ...etat_regles.regles.filter(regle => regle.groupe === groupe).map(regle => {
      const champs_regle = { actif: null, params: {} }; saisies[regle.id] = champs_regle;
      const ligne = creerElement("div", { class: "regle" + (regle.actif ? "" : " inactive") });
      if (regle.switch) {
        champs_regle.actif = creerElement("input", { type: "checkbox", role: "switch", "aria-label": regle.titre });
        champs_regle.actif.checked = regle.actif;
        champs_regle.actif.addEventListener("change", () => ligne.classList.toggle("inactive", !champs_regle.actif.checked));
      }
      const params = regle.params.map(parametre => {
        const entree = creerElement("input", { type: "number", step: parametre.pas, min: parametre.min, max: parametre.max, value: parametre.valeur });
        champs_regle.params[parametre.cle] = entree;
        return creerElement("label", { class: "param" }, parametre.libelle, creerElement("span", { class: "saisie-u" }, entree, parametre.unite ? creerElement("span", { text: parametre.unite }) : null));
      });
      ligne.append(
        regle.switch ? creerElement("label", { class: "interrupteur" }, champs_regle.actif, creerElement("span", { class: "piste" })) : creerElement("span", { class: "interrupteur vide-i" }),
        creerElement("div", { class: "texte-regle" }, creerElement("strong", { text: regle.titre }), regle.aide ? creerElement("p", { class: "petit", text: regle.aide }) : null),
        creerElement("div", { class: "params" }, ...params));
      return ligne;
    })));

  const collecte = () => Object.fromEntries(Object.entries(saisies).map(([id, champs_regle]) => [id, {
    actif: champs_regle.actif ? champs_regle.actif.checked : true,
    params: Object.fromEntries(Object.entries(champs_regle.params).map(([cle, entree]) => [cle, entree.value])) }]));
  async function envoyer(corps, question) {
    if (!confirm(question)) return;
    const rr = await api("/api/admin/reglages", "POST", corps);
    if (!rr.ok) return afficher(msg, "erreurs", "Non enregistré :", messagesDe(rr));
    await sectionRegles(zone);
    zone.prepend(boite("succes", "✔ Règles enregistrées.", []));
  }
  const bEnr = creerElement("button", { type: "button", class: "bouton", text: "Enregistrer les règles", onclick: () => envoyer({ regles: collecte() }, "Enregistrer ces règles ? Elles changent les vérifications pour tous les postes de saisie.") });
  const bRaz = creerElement("button", { type: "button", class: "bouton secondaire", text: "Revenir aux valeurs d'origine", onclick: () => envoyer({ reinitialiser: true }, "Remettre toutes les règles aux valeurs d'origine ?") });

  const histo = etat_regles.historique.length
    ? creerElement("div", { class: "defile", style: "max-height:260px" }, creerElement("table", { class: "t" },
        creerElement("thead", {}, creerElement("tr", {}, ...["Date", "Compte", "Règle", "Avant", "Après"].map(titre => creerElement("th", { text: titre })))),
        creerElement("tbody", {}, ...etat_regles.historique.map(ligne => creerElement("tr", {}, ...[ligne.date.replace("T", " "), ligne.utilisateur, ligne.regle, ligne.avant, ligne.apres].map(texte => creerElement("td", { text: texte })))))))
    : creerElement("p", { class: "petit", text: "Aucun changement enregistré." });

  zone.replaceChildren(...[
    creerElement("p", { class: "petit", text: "Chaque interrupteur active ou désactive une vérification ; les valeurs se règlent à droite. Les changements s'appliquent à tous les postes de saisie et sont notés dans l'historique ci-dessous. Les données déjà enregistrées dans Excel ne sont pas modifiées." }),
    etat_regles.modifie ? creerElement("p", { class: "petit", text: "⚙ Des règles ont été modifiées par rapport aux valeurs d'origine (config/champs.json)." }) : null,
    ...blocs,
    creerElement("p", { class: "petit", text: "Non modifiables (protègent le fichier Excel) : champs obligatoires, compteur fin ≥ compteur début, hauteur finale ≤ hauteur initiale, compteur fin 0 remplacé par 1, cohérence format / matière / MA5." }),
    creerElement("div", { class: "actions" }, bEnr, bRaz), msg,
    creerElement("h3", { text: "Historique des changements", style: "margin-top:24px" }), histo].filter(element => element != null));   // replaceChildren(null) écrirait « null » dans la page
}

/* ---------- section 3 : affichage de la page de saisie ---------- */
async function sectionAffichage(zone) {
  const reponse = await api("/api/admin/affichage");
  const msg = creerElement("div", { class: "msg-admin", "aria-live": "polite" });
  const humour = creerElement("input", { type: "checkbox", role: "switch", "aria-label": "Messages humoristiques pendant l'enregistrement" });
  humour.checked = !!reponse.corps.humour;
  humour.addEventListener("change", async () => {
    const rr = await api("/api/admin/affichage", "POST", { humour: humour.checked });
    if (!rr.ok) { humour.checked = !humour.checked; return afficher(msg, "erreurs", "Non enregistré :", messagesDe(rr)); }
    afficher(msg, "succes", humour.checked ? "✔ Messages humoristiques activés." : "✔ Messages normaux rétablis.");
  });
  zone.replaceChildren(
    creerElement("p", { class: "petit", text: "Pendant l'enregistrement dans Excel, la page de saisie est bloquée et affiche une barre de chargement. Ce réglage change seulement les textes sous la barre ; il s'applique à tous les postes, au prochain enregistrement." }),
    creerElement("div", { class: "regle" },
      creerElement("label", { class: "interrupteur" }, humour, creerElement("span", { class: "piste" })),
      creerElement("div", { class: "texte-regle" }, creerElement("strong", { text: "Messages humoristiques" }),
        creerElement("p", { class: "petit", text: "Désactivé : « Mise en forme de la nouvelle ligne… ». Activé : « Chargement de la gravité… ✔ », « Test de la patience de l'utilisateur… »" })),
      creerElement("span")),
    msg);
}

/* ---------- démarrage ---------- */
(async () => {
  const reponse = await fetch("/api/admin/moi");
  if (reponse.ok) { MOI = await reponse.json(); afficherAdmin(); } else afficherConnexion();
})();

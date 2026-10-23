"use strict";
/* Outils communs aux pages de consultation et d'administration. */

/** Crée un élément HTML : h("div", { class: "x", onclick: fn }, enfants...). Le texte passe par textContent (jamais en HTML). */
function creerElement(tag, attrs = {}, ...enfants) {
  const element = document.createElement(tag);
  for (const [cle, valeur] of Object.entries(attrs)) {
    if (valeur === false || valeur == null) continue;
    if (cle === "class") element.className = valeur;
    else if (cle === "text") element.textContent = valeur;
    else if (cle.startsWith("on")) element.addEventListener(cle.slice(2), valeur);
    else element.setAttribute(cle, valeur === true ? "" : valeur);
  }
  element.append(...enfants.flat().filter(enfant => enfant != null));
  return element;
}

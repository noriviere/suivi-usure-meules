// Lance demo-api.js dans Node avec un faux navigateur et rejoue des saisies : lit/écrit du JSON sur stdin/stdout.
const fs = require("fs");
const [, , fichierDemo, fichierSaisies] = process.argv;
const donnees = fs.readFileSync(fichierDemo, "utf8");
global.window = { fetch: async () => new Response(donnees) };
global.document = { addEventListener() {}, getElementById() { return null; } };
global.location = { href: "http://localhost/index.html" };
require("../demo_web/demo-api.js");
(async () => {
  const saisies = JSON.parse(fs.readFileSync(fichierSaisies, "utf8")), sortie = [];
  for (const saisie of saisies) {
    const reponse = await window.fetch("/api/verifier", { method: "POST", body: JSON.stringify(saisie) });
    sortie.push(await reponse.json());
  }
  console.log(JSON.stringify(sortie));
})();

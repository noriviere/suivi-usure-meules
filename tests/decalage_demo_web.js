// Charge demo-api.js avec un instantané « construit » à une autre date et affiche les dates vues par la page.
const fs = require("fs");
const donnees = fs.readFileSync(process.argv[2], "utf8");
global.window = { fetch: async () => new Response(donnees) };
global.document = { addEventListener() {}, getElementById() { return null; } };
global.location = { href: "http://localhost/index.html" };
require("../demo_web/demo-api.js");
(async () => {
  const table = await (await window.fetch("/api/donnees")).json();
  const colonne = table.entetes.indexOf("Date montage") + 1;
  console.log(JSON.stringify(table.lignes.map(ligne => ligne[colonne])));
})();

// Filtres et fiche du rapport bitumap. Script fixe : son empreinte SHA-256 est autorisée par
// la politique de sécurité (CSP) des réponses de l'API. Les données sont lues dans le bloc JSON.
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("donnees").textContent);
  var parId = {};
  D.points.forEach(function (p) { parId[p.id] = p; });
  var filtres = { priorite: "tous", type: "tous", route: "tous" };
  var liste = document.getElementById("liste");
  var fiche = document.getElementById("fiche");

  function texte(el, valeur) { el.textContent = valeur === null || valeur === undefined ? "—" : valeur; }

  function visible(p) {
    return (filtres.priorite === "tous" || p.priorite === filtres.priorite || p.groupe === filtres.priorite) &&
      (filtres.type === "tous" || p.type === filtres.type) &&
      (filtres.route === "tous" || p.route.classement === filtres.route);
  }

  function appliquer() {
    var n = 0;
    document.querySelectorAll("[data-point]").forEach(function (el) {
      var ok = visible(parId[el.getAttribute("data-point")]);
      el.hidden = !ok;
      if (ok && el.tagName === "LI") { n += 1; }
    });
    texte(document.getElementById("compte"), n + " point(s)");
  }

  function montrer(id) {
    var p = parId[id];
    if (!p) { return; }
    document.querySelectorAll(".sel").forEach(function (el) { el.classList.remove("sel"); });
    document.querySelectorAll('[data-point="' + id + '"]').forEach(function (el) {
      el.classList.add("sel");
      // Point de la carte au premier plan : jamais masqué par ses voisins.
      if (el.classList.contains("pt")) { el.parentNode.appendChild(el); }
    });
    var gabarit = document.getElementById("gabarit-fiche").content.cloneNode(true);
    texte(gabarit.querySelector(".f-titre"), p.designation);
    texte(gabarit.querySelector(".f-sous"), p.type_libelle + " · " + p.identifiant);
    texte(gabarit.querySelector(".f-rang"), "Rang " + p.rang + " · " + p.groupe_libelle + " · score " + p.score);
    var route = p.route.libelle + (p.route.numero ? " " + p.route.numero : "") +
      (p.route.gestionnaire ? " — gestionnaire : " + p.route.gestionnaire : "") +
      (p.route.statut === "a_verifier" ? " (à vérifier)" : "");
    texte(gabarit.querySelector(".f-route"), route);
    texte(gabarit.querySelector(".f-bus"), Math.round(p.bus_jour) + " bus/jour" +
      (p.pointe_h ? " · " + Math.round(p.pointe_h) + " bus/h en pointe" : ""));
    texte(gabarit.querySelector(".f-lignes"), p.lignes.join(", "));
    var ul = gabarit.querySelector(".f-facteurs");
    p.facteurs.forEach(function (f) {
      var li = document.createElement("li");
      var etiquette = f.statut === "a_confirmer" ? " [IA, à confirmer]" : (f.statut === "non_evalue" ? " [non évalué]" : "");
      li.textContent = f.explication + " — ×" + f.effet.toFixed(2) + etiquette;
      ul.appendChild(li);
    });
    var photo = gabarit.querySelector(".f-photo");
    if (p.panoramax) {
      var a = document.createElement("a");
      a.href = p.panoramax.url; a.rel = "noopener noreferrer"; a.target = "_blank";
      a.textContent = "Photo de rue du " + p.panoramax.date + " (" + p.panoramax.licence + ", " + p.panoramax.distance_m + " m)";
      photo.appendChild(a);
    } else { photo.textContent = "Aucune photo de rue récente à moins de 30 m."; }
    fiche.replaceChildren(gabarit);
  }

  document.querySelectorAll("[data-filtre]").forEach(function (sel) {
    sel.addEventListener("change", function () { filtres[sel.getAttribute("data-filtre")] = sel.value; appliquer(); });
  });
  document.addEventListener("click", function (e) {
    var cible = e.target.closest("[data-point]");
    if (cible) { montrer(cible.getAttribute("data-point")); }
  });
  document.addEventListener("keydown", function (e) {
    var cible = e.target.closest && e.target.closest("[data-point]");
    if (cible && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); montrer(cible.getAttribute("data-point")); }
  });
  appliquer();
  if (D.points.length) { montrer(D.points[0].id); }
})();

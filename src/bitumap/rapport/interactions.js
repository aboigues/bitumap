// Filtres et fiche du rapport bitumap. Script fixe : son empreinte SHA-256 est autorisée par
// la politique de sécurité (CSP) des réponses de l'API. Les données sont lues dans le bloc JSON.
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("donnees").textContent);
  // Constaté (003) : relevés insérés par l'API à la consultation ; absent d'un rapport ancien.
  var blocReleves = document.getElementById("releves");
  var R = blocReleves ? JSON.parse(blocReleves.textContent) : {};
  // Méthode 2.0 : classement corrigé par le terrain (004 R9), inséré par l'API ; absent
  // d'un rapport 1.x ou d'une page sans relevé de réfection confirmée.
  var blocCorrige = document.getElementById("classement-terrain");
  var C = blocCorrige ? JSON.parse(blocCorrige.textContent) : null;
  var NIVEAUX = { absent: "absent", leger: "léger", marque: "marqué", grave: "grave" };
  var SOURCES = { constatee: "constatée", services_techniques: "services techniques", estimee_agent: "estimée par l'agent" };
  var INSEE = location.pathname.split("/")[2] || "";
  var parId = {};
  D.points.forEach(function (p) { parId[p.id] = p; });
  var filtres = { priorite: "tous", type: "tous", route: "tous", constate: "tous" };
  var liste = document.getElementById("liste");
  var fiche = document.getElementById("fiche");

  function texte(el, valeur) { el.textContent = valeur === null || valeur === undefined ? "—" : valeur; }

  function visible(p) {
    return (filtres.priorite === "tous" || p.priorite === filtres.priorite || p.groupe === filtres.priorite) &&
      (filtres.type === "tous" || p.type === filtres.type) &&
      (filtres.route === "tous" || p.route.classement === filtres.route) &&
      constatVisible(R[p.id]);
  }

  function constatVisible(r) {
    var f = filtres.constate;
    if (f === "tous") { return true; }
    if (f === "releves") { return Boolean(r); }
    if (f === "non_releves") { return !r; }
    if (f === "marque_grave") { return Boolean(r) && (r.niveau === "marque" || r.niveau === "grave"); }
    return Boolean(r) && r.niveau === f;
  }

  function remplirConstat(zone, id) {
    var r = R[id];
    var lien = document.createElement("a");
    lien.href = "/terrain/" + INSEE + "/" + id;
    if (!r) {
      zone.textContent = "Non relevé. ";
      lien.textContent = "Saisir un relevé";
      zone.appendChild(lien);
      return;
    }
    var lignes = [
      NIVEAUX[r.niveau] + (r.profondeur_mm !== null ? " · " + r.profondeur_mm + " mm (" + r.instrument + ")" : ""),
      r.cree_le.slice(0, 10) + " · " + r.auteur + (r.position_eloignee ? " · position éloignée" : ""),
    ];
    if (r.annee_refection) { lignes.push("Réfection " + r.annee_refection + " (" + (SOURCES[r.source_refection] || r.source_refection) + ")"); }
    if (r.observation) { lignes.push(r.observation); }
    if (r.nb_photos) { lignes.push(r.nb_photos + " photo(s), visibles par leur auteur"); }
    zone.textContent = "";
    lignes.forEach(function (l) { var d = document.createElement("div"); d.textContent = l; zone.appendChild(d); });
    lien.textContent = r.nb_releves > 1 ? "Historique (" + r.nb_releves + " relevés)" : "Historique et nouveau relevé";
    zone.appendChild(lien);
  }

  function syntheseConstat() {
    var ids = Object.keys(R).filter(function (id) { return parId[id]; });
    var section = document.getElementById("synthese-constate");
    if (!section || !ids.length) { return; }
    section.hidden = false;
    var groupes = {};
    D.points.forEach(function (p) { groupes[p.groupe] = p.groupe_libelle; });
    var tableau = document.getElementById("constate-tableau");
    Object.keys(groupes).sort().forEach(function (g) {
      var tr = document.createElement("tr");
      var th = document.createElement("td"); th.textContent = groupes[g]; tr.appendChild(th);
      ["absent", "leger", "marque", "grave"].forEach(function (n) {
        var td = document.createElement("td");
        td.textContent = ids.filter(function (id) { return parId[id].groupe === g && R[id].niveau === n; }).length;
        tr.appendChild(td);
      });
      tableau.appendChild(tr);
    });
    texte(document.getElementById("constate-resume"), ids.length + " point(s) relevé(s) sur " + D.points.length + ".");
    document.querySelectorAll("li[data-point]").forEach(function (li) {
      var r = R[li.getAttribute("data-point")];
      if (!r) { return; }
      var marque = document.createElement("span");
      marque.className = "releve-marque";
      marque.textContent = "relevé : " + NIVEAUX[r.niveau];
      li.querySelector("strong").after(marque);
    });
  }

  var LIBELLES = {};
  D.points.forEach(function (p) { LIBELLES[p.groupe] = p.groupe_libelle; });
  var corrigeParId = {};
  if (C) { C.classement.forEach(function (c) { corrigeParId[c.id] = c; }); }

  function effetTexte(e) { return "×" + e.toFixed(2).replace(".", ","); }

  function remplirCorrige(zone, p) {
    var c = C && C.points[p.id];
    if (!zone || !c) { return; }
    var detail = c.annule ? c.motif :
      "réfection de " + c.annee_refection + ", " + (SOURCES[c.source_refection] || c.source_refection) + " : " + effetTexte(c.effet);
    texte(zone, "Estimé : rang " + p.rang + ", " + p.groupe_libelle + " · Corrigé par le terrain : rang " +
      c.rang + ", " + (LIBELLES[c.groupe] || c.groupe) + " (" + detail + ")");
    zone.hidden = false;
  }

  function syntheseCorrige() {
    var zone = document.getElementById("synthese-terrain");
    var choix = document.getElementById("choix-classement");
    if (!C || !Object.keys(C.points).length) { return; }
    if (zone) {
      texte(zone, C.nb_points_corriges + " point(s) corrigé(s) par une réfection confirmée.");
      zone.hidden = false;
      document.getElementById("synthese-constate").hidden = false;
    }
    if (choix) { choix.hidden = false; }
  }

  function classer(mode) {
    var ol = document.querySelector("ol.liste");
    var lis = Array.prototype.slice.call(ol.querySelectorAll("li[data-point]"));
    lis.forEach(function (li) {
      var p = parId[li.getAttribute("data-point")];
      var c = mode === "corrige" ? corrigeParId[p.id] || p : p;
      li.querySelector(".rang").textContent = c.rang;
      var pastille = li.querySelector(".pastille");
      pastille.className = "pastille " + c.groupe;
      pastille.textContent = LIBELLES[c.groupe] || c.groupe;
      li.setAttribute("data-rang", c.rang);
    });
    lis.sort(function (a, b) { return a.getAttribute("data-rang") - b.getAttribute("data-rang"); });
    lis.forEach(function (li) { ol.appendChild(li); });
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
    remplirConstat(gabarit.querySelector(".f-constate"), id);
    texte(gabarit.querySelector(".f-sous"), p.type_libelle + " · " + p.identifiant);
    texte(gabarit.querySelector(".f-rang"), "Rang " + p.rang + " · " + p.groupe_libelle + " · score " + p.score);
    // Méthode 2.0 : niveau en 1.2 et raison principale du changement (004 R6).
    var changement = gabarit.querySelector(".f-changement");
    if (changement && p.raison_changement) {
      texte(changement, "v1 : " + p.niveau_v1_libelle + " — raison : " + p.raison_changement);
      changement.hidden = false;
    }
    remplirCorrige(gabarit.querySelector(".f-corrige"), p);
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
    // Réfection ou réaménagement récent : visible en comparant les photos aériennes (IGN).
    var aerien = gabarit.querySelector(".f-aerien");
    if (aerien && p.photos_aeriennes) {
      var lien = document.createElement("a");
      lien.href = p.photos_aeriennes; lien.rel = "noopener noreferrer"; lien.target = "_blank";
      lien.textContent = "Comparer aujourd'hui et 2016-2020 (IGN, Remonter le temps)";
      aerien.appendChild(lien);
    }
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
  var choixClassement = document.querySelector("[data-classement]");
  if (choixClassement) {
    choixClassement.addEventListener("change", function () { classer(choixClassement.value); });
  }
  syntheseConstat();
  syntheseCorrige();
  appliquer();
  if (D.points.length) { montrer(D.points[0].id); }
})();

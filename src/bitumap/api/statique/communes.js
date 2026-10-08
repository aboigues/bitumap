// Propositions de communes pendant la frappe (008 US1, contracts/http-api.md). Sans dépendance.
// La correspondance est faite par l'API sur la liste intégrée ; sans ce script, le formulaire
// GET fonctionne seul. Texte inséré par textContent uniquement (jamais innerHTML).

const ATTENTE_MS = 150;
const MINIMUM = 2; // l'API ne propose qu'un nom exact sous 3 lettres (« us » ⇒ Us, FR-016)

function brancher(champ) {
  const liste = document.getElementById(champ.getAttribute("aria-controls"));
  const etat = champ.form.querySelector("[data-etat-recherche]");
  const destination = champ.dataset.destination;
  let minuterie = null;
  let enCours = null;
  let communes = [];
  let active = -1;

  function fermer() {
    liste.hidden = true;
    liste.replaceChildren();
    champ.setAttribute("aria-expanded", "false");
    champ.removeAttribute("aria-activedescendant");
    communes = [];
    active = -1;
  }

  function choisir(commune) {
    location.assign(destination + encodeURIComponent(commune.insee));
  }

  function activer(indice) {
    const options = liste.querySelectorAll("[role=option]");
    options.forEach((o, i) => o.setAttribute("aria-selected", String(i === indice)));
    active = indice;
    if (indice >= 0) {
      champ.setAttribute("aria-activedescendant", options[indice].id);
      options[indice].scrollIntoView({ block: "nearest" });
    } else {
      champ.removeAttribute("aria-activedescendant");
    }
  }

  function afficher(resultats) {
    fermer();
    communes = resultats;
    if (!resultats.length) {
      etat.textContent = champ.value.trim().length >= 3
        ? "Aucune commune d'Île-de-France ne correspond."
        : "";
      return;
    }
    resultats.forEach((commune, i) => {
      const option = document.createElement("li");
      option.id = `${liste.id}-${i}`;
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", "false");
      option.textContent = `${commune.nom} (${commune.departement})`;
      option.addEventListener("mousedown", (e) => e.preventDefault()); // garde le focus
      option.addEventListener("click", () => choisir(commune));
      liste.append(option);
    });
    liste.hidden = false;
    champ.setAttribute("aria-expanded", "true");
    etat.textContent = `${resultats.length} commune${resultats.length > 1 ? "s" : ""} proposée${resultats.length > 1 ? "s" : ""}.`;
  }

  async function chercher() {
    const q = champ.value.trim();
    if (enCours) enCours.abort();
    if (q.length < MINIMUM || /^\d+$/.test(q)) { // code postal : formulaire, comme avant
      fermer();
      etat.textContent = "";
      return;
    }
    enCours = new AbortController();
    try {
      const reponse = await fetch(`/communes/recherche?q=${encodeURIComponent(q)}`, {
        credentials: "same-origin",
        headers: { accept: "application/json" },
        signal: enCours.signal,
      });
      if (!reponse.ok) return fermer(); // session expirée… : le formulaire reste utilisable
      afficher(await reponse.json());
    } catch (e) {
      if (e.name !== "AbortError") fermer();
    }
  }

  champ.addEventListener("input", () => {
    clearTimeout(minuterie);
    minuterie = setTimeout(chercher, ATTENTE_MS);
  });
  champ.addEventListener("keydown", (e) => {
    if (liste.hidden || !communes.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activer((active + 1) % communes.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activer(active <= 0 ? communes.length - 1 : active - 1);
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      choisir(communes[active]);
    } else if (e.key === "Escape") {
      fermer();
    }
  });
  champ.addEventListener("blur", () => setTimeout(fermer, 150));
}

document.querySelectorAll("input[data-recherche-communes]").forEach(brancher);

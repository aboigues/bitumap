// Saisie des relevés terrain (003 : R3, R4, R9, R11). Sans dépendance.
// Chaque relevé et chaque photo reçoit son identifiant ici ; tout est gardé dans IndexedDB
// jusqu'à confirmation du serveur ; les envois sont idempotents (réenvoi sans doublon).

const BASE = "bitumap-terrain";
const MAGASIN = "envois";
const TROIS_JOURS_MS = 3 * 24 * 3600 * 1000;
const COTE_MAX = 2048;

function ouvrirBase() {
  return new Promise((resoudre, rejeter) => {
    const demande = indexedDB.open(BASE, 1);
    demande.onupgradeneeded = () => demande.result.createObjectStore(MAGASIN, { keyPath: "id" });
    demande.onsuccess = () => resoudre(demande.result);
    demande.onerror = () => rejeter(demande.error);
  });
}

async function magasin(mode, action) {
  const base = await ouvrirBase();
  return new Promise((resoudre, rejeter) => {
    const transaction = base.transaction(MAGASIN, mode);
    const resultat = action(transaction.objectStore(MAGASIN));
    transaction.oncomplete = () => resoudre(resultat && resultat.result);
    transaction.onerror = () => rejeter(transaction.error);
  });
}

const tousLesEnvois = () => magasin("readonly", (m) => m.getAll());
const garder = (envoi) => magasin("readwrite", (m) => m.put(envoi));
const oublier = (id) => magasin("readwrite", (m) => m.delete(id));

// --- Repères des niveaux (FR-005b), même règle que le serveur --------------------------

function niveauSelonProfondeur(mm) {
  if (mm < 10) return "leger";
  return mm <= 20 ? "marque" : "grave";
}

export function incoherence(niveau, mm) {
  if (mm === null || Number.isNaN(mm)) return null;
  const suggere = niveauSelonProfondeur(mm);
  if (niveau === "absent") return mm >= 10 ? suggere : null;
  return suggere !== niveau ? suggere : null;
}

const LIBELLES = { absent: "absent", leger: "léger", marque: "marqué", grave: "grave" };

// --- Position et photos ------------------------------------------------------------------

function position() {
  if (!("geolocation" in navigator)) return Promise.resolve(null);
  return new Promise((resoudre) => {
    navigator.geolocation.getCurrentPosition(
      (p) => resoudre({ lon: p.coords.longitude, lat: p.coords.latitude }),
      () => resoudre(null),
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
    );
  });
}

async function reduire(fichier) {
  // Réencodage en JPEG ≤ 2 048 px : fichier léger, métadonnées d'origine perdues (R4).
  const image = await createImageBitmap(fichier);
  const echelle = Math.min(1, COTE_MAX / Math.max(image.width, image.height));
  const toile = document.createElement("canvas");
  toile.width = Math.round(image.width * echelle);
  toile.height = Math.round(image.height * echelle);
  toile.getContext("2d").drawImage(image, 0, 0, toile.width, toile.height);
  return new Promise((resoudre) => toile.toBlob(resoudre, "image/jpeg", 0.85));
}

// --- Envoi ---------------------------------------------------------------------------------

class ErreurDefinitive extends Error {}

async function appeler(methode, url, corps) {
  const reponse = await fetch(url, {
    method: methode,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(corps),
    credentials: "same-origin",
  });
  const donnees = await reponse.json().catch(() => ({}));
  if (reponse.ok) return donnees;
  if (reponse.status >= 500 || reponse.status === 429) throw new Error(donnees.message || "réessayer");
  throw new ErreurDefinitive(donnees.message || "Envoi refusé.");
}

async function envoyer(envoi) {
  if (!envoi.releveEnvoye) {
    await appeler("PUT", `/terrain/releves/${envoi.id}`, { ...envoi.donnees, csrf: envoi.csrf });
    envoi.releveEnvoye = true;
    await garder(envoi);
  }
  for (const photo of envoi.photos) {
    if (photo.envoyee) continue;
    const base = `/terrain/releves/${envoi.id}/photos/${photo.id}`;
    const formulaire = await appeler("POST", `${base}/formulaire`, {
      csrf: envoi.csrf, octets: photo.blob.size, type: photo.blob.type,
    });
    const donnees = new FormData();
    Object.entries(formulaire.champs).forEach(([cle, valeur]) => donnees.append(cle, valeur));
    donnees.append("file", photo.blob);
    const depot = await fetch(formulaire.url, { method: "POST", body: donnees });
    if (!depot.ok) throw new Error("dépôt de la photo refusé");
    await appeler("POST", `${base}/confirmation`, {
      csrf: envoi.csrf, lon: photo.lon, lat: photo.lat, prise_le: photo.prise_le,
    });
    photo.envoyee = true;
    await garder(envoi);
  }
  await oublier(envoi.id);
}

let enCours = false;

export async function synchroniser() {
  if (enCours || !navigator.onLine) return afficherAttente();
  enCours = true;
  try {
    for (const envoi of await tousLesEnvois()) {
      if (envoi.erreur) continue;
      try {
        await envoyer(envoi);
      } catch (erreur) {
        if (erreur instanceof ErreurDefinitive) {
          envoi.erreur = erreur.message;
          await garder(envoi);
        }
        // sinon : erreur passagère (réseau, serveur) ; nouvel essai plus tard
      }
    }
  } finally {
    enCours = false;
    await afficherAttente();
  }
}

async function afficherAttente() {
  const zone = document.getElementById("attente");
  if (!zone) return;
  const envois = await tousLesEnvois();
  zone.hidden = envois.length === 0;
  document.getElementById("attente-nombre").textContent = String(envois.length);
  const ancien = envois.some((e) => Date.now() - Date.parse(e.donnees.cree_le) > TROIS_JOURS_MS);
  document.getElementById("attente-alerte").hidden = !ancien;
  const refuses = envois.filter((e) => e.erreur);
  document.getElementById("attente-refus").textContent = refuses.length
    ? ` — ${refuses.length} refusé(s) : ${refuses[0].erreur}`
    : "";
}

// --- Formulaire de saisie -------------------------------------------------------------------

function lireFormulaire(formulaire) {
  const f = new FormData(formulaire);
  const entier = (nom) => (f.get(nom) === "" || f.get(nom) === null ? null : Number(f.get(nom)));
  const texte = (nom) => (f.get(nom) || "").trim() || null;
  return {
    commune_insee: formulaire.dataset.insee,
    point_id: formulaire.dataset.point,
    cree_le: new Date().toISOString(),
    niveau: f.get("niveau"),
    profondeur_mm: entier("profondeur_mm"),
    instrument: texte("instrument"),
    observation: texte("observation"),
    annee_refection: entier("annee_refection"),
    source_refection: texte("source_refection"),
    confirme_malgre_incoherence: false,
  };
}

function initialiserSaisie(formulaire) {
  const avertissement = document.getElementById("avertissement");
  const erreur = document.getElementById("erreur");
  const confirmer = document.getElementById("confirmer");
  const confirmation = document.getElementById("confirmation");

  async function enregistrer(confirme) {
    erreur.hidden = true;
    const donnees = lireFormulaire(formulaire);
    if (!donnees.niveau) {
      erreur.textContent = "Choisissez le niveau d'orniérage constaté : c'est le seul champ obligatoire.";
      erreur.hidden = false;
      return;
    }
    const suggere = incoherence(donnees.niveau, donnees.profondeur_mm);
    if (suggere && !confirme) {
      avertissement.textContent = `${donnees.profondeur_mm} mm correspond au niveau « ${LIBELLES[suggere]} » : corrigez le niveau ou confirmez votre choix.`;
      avertissement.hidden = false;
      confirmer.hidden = false;
      return;
    }
    donnees.confirme_malgre_incoherence = Boolean(suggere);
    const ici = await position();
    if (ici) Object.assign(donnees, ici);
    const fichiers = [...formulaire.querySelector("#photos").files].slice(0, 5);
    const photos = [];
    for (const fichier of fichiers) {
      photos.push({
        id: crypto.randomUUID(), blob: await reduire(fichier),
        lon: ici && ici.lon, lat: ici && ici.lat, prise_le: new Date().toISOString(),
      });
    }
    await garder({ id: crypto.randomUUID(), csrf: formulaire.dataset.csrf, donnees, photos });
    formulaire.reset();
    avertissement.hidden = true;
    confirmer.hidden = true;
    confirmation.textContent = navigator.onLine
      ? "Relevé enregistré ; envoi en cours."
      : "Relevé enregistré sur le téléphone ; il sera envoyé au retour du réseau.";
    confirmation.hidden = false;
    await synchroniser();
  }

  formulaire.addEventListener("submit", (e) => { e.preventDefault(); enregistrer(false); });
  confirmer.addEventListener("click", () => enregistrer(true));
}

function initialiserRecherche(champ) {
  champ.addEventListener("input", () => {
    const texte = champ.value.trim().toLowerCase();
    document.querySelectorAll("[data-texte]").forEach((li) => {
      li.hidden = texte !== "" && !li.dataset.texte.includes(texte);
    });
  });
}

async function demarrer() {
  if (navigator.storage && navigator.storage.persist) {
    navigator.storage.persist().catch(() => {});
  }
  const formulaire = document.getElementById("releve");
  if (formulaire) initialiserSaisie(formulaire);
  const recherche = document.querySelector("[data-filtre-points]");
  if (recherche) initialiserRecherche(recherche);
  window.addEventListener("online", synchroniser);
  await synchroniser();
}

demarrer();

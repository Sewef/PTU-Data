// === Citronnades – Unified Classes Viewer =============================
// Affichage dynamique du JSON unifié :
//   Classe → { category, source, branches:[ { name, features:[…] } ] }
// ---------------------------------------------------------------------------
// EXIGENCES PARTICULIÈRES
//   • « General » : toujours lien direct en tête de sidebar. Chaque Feature
//     arbore un badge Source.
//   • Sidebar : Catégorie ▼ Classe ▼ Branche sauf si la classe n'a qu'une
//     unique branche nommée « Default » (dans ce cas, lien direct).
//   • Filtre Source appliqué AU NIVEAU DES BRANCHES (une classe reste visible
//     si ≥1 branche correspond). Le badge de chaque lien reprend la source de
//     la branche.
//   • **NOUVEAU** : dans le panneau central, **une carte = une Feature**.
//     Quand un objet contient des sous‑features, on ne rend PAS une « carte
//     mère » englobante. Toutes les leaves (features feuilles) sont rendues
//     au même niveau.
// ---------------------------------------------------------------------------
// Dépendances : Bootstrap 5 (collapse). Facultatif : CSS pour .triangle-toggle.
// ---------------------------------------------------------------------------

// ------------------------- VARIABLES GLOBALES ------------------------------
let classesData = {};
let activeSources = new Set();
let currentLink = null;

// ------------------------- CHARGEMENT JSON ---------------------------------
function loadClasses(path) {
  fetch(path)
    .then(r => r.json())
    .then(json => {
      classesData = json;
      buildSidebar();
      const firstCls = classesData.General ? "General" : Object.keys(classesData)[0];
      const firstBr = classesData[firstCls].branches[0].name;
      renderSection(firstCls, firstBr);
      const l = document.querySelector(`[data-section="${firstCls}"][data-branch="${firstBr}"]`);
      if (l) setActiveLink(l);
    })
    .catch(err => console.error("JSON load error:", err));
}

// ------------------------- SIDEBAR -----------------------------------------
function buildSidebar() {
  const sb = document.getElementById("sidebar");
  sb.innerHTML = `
    <div class="mb-3">
      <input type="text" id="sidebar-search" class="form-control" placeholder="Rechercher…">
    </div>`;
  document.getElementById("sidebar-search").addEventListener("input", renderSidebar);

  // -- filtres Source -------------------------------------------------------
  const sourcesSet = new Set();
  Object.values(classesData).forEach(cls => {
    if (cls.source) sourcesSet.add(cls.source);
    cls.branches.forEach(br => {
      const src = branchSource(br, cls.source);
      if (src) sourcesSet.add(src);
    });
  });

  const fWrap = document.createElement("div");
  fWrap.className = "mb-3";
  fWrap.innerHTML = `<label class="form-label">Filter by Source:</label>`;
  sb.appendChild(fWrap);
  [...sourcesSet].sort().forEach(src => {
    const id = `filter-src-${src}`;
    fWrap.insertAdjacentHTML("beforeend", `
      <div class="form-check">
        <input class="form-check-input" type="checkbox" id="${id}" checked>
        <label class="form-check-label" for="${id}">${src}</label>
      </div>`);
  });
  fWrap.querySelectorAll("input").forEach(cb =>
    cb.addEventListener("change", () => {
      renderSidebar();                                   // ← sidebar mise à jour
      if (currentLink && currentLink.dataset.section === "General") {
        // on recharge la section General pour appliquer le nouveau filtre
        renderSection("General", "Default");
        // (l’appel conserve scrollTo et la recherche locale déjà en place)
      }
    })
  );


  sb.insertAdjacentHTML("beforeend", `<div id="sidebar-links"></div>`);
  renderSidebar();
}

// ------------- Source d'une branche ---------------------------------------
function branchSource(branch, fallback) {
  const featWithSrc = branch.features.find(f => f.Source || f.source);
  return featWithSrc ? (featWithSrc.Source || featWithSrc.source) : fallback || "Unknown";
}

// ------------- Rendu Sidebar ----------------------------------------------
function renderSidebar() {
  const box = document.getElementById("sidebar-links");
  box.innerHTML = "";

  activeSources.clear();
  document.querySelectorAll('[id^="filter-src-"]:checked').forEach(cb => activeSources.add(cb.id.replace("filter-src-", "")));

  const q = document.getElementById("sidebar-search").value.trim().toLowerCase();

  // ----- GENERAL -----------------------------------------------------------
  if (classesData.General) {
    const genVisible = classesData.General.branches[0].features.some(f => activeSources.has(f.Source || f.source || classesData.General.source));
    if (genVisible && (!q || "general".includes(q))) {
      box.appendChild(makeLink("General", classesData.General.source, { section: "General", branch: "Default" }, 3));
    }
  }

  // ----- CATÉGORIES --------------------------------------------------------
  const cats = {};
  Object.entries(classesData).forEach(([clsName, cls]) => {
    if (clsName === "General") return;
    if (q && !clsName.toLowerCase().includes(q)) return;

    const visibleBranches = cls.branches.filter(br => activeSources.has(branchSource(br, cls.source)));
    if (visibleBranches.length === 0) return;

    (cats[cls.category || "Other"] ??= []).push([clsName, cls, visibleBranches]);
  });

  Object.keys(cats).sort().forEach(cat => {
    const catId = `collapse-cat-${cat.replace(/\s+/g, "-")}`;
    box.insertAdjacentHTML("beforeend", `
      <button class="btn btn-sm btn-light w-100 text-start collapse-toggle mb-1" data-bs-toggle="collapse" data-bs-target="#${catId}">📁 ${cat}</button>`);
    const catCol = document.createElement("div");
    catCol.className = "collapse mb-2";
    catCol.id = catId;
    box.appendChild(catCol);

    cats[cat].sort(([a], [b]) => a.localeCompare(b)).forEach(([clsName, cls, branches]) => {
      const singleDefault = branches.length === 1 && branches[0].name === "Default";
      if (singleDefault) {
        catCol.appendChild(makeLink(clsName, branchSource(branches[0], cls.source), { section: clsName, branch: "Default" }, 4));
      } else {
        const clsId = `collapse-cls-${clsName.replace(/\s+/g, "-")}`;
        catCol.insertAdjacentHTML("beforeend", `
          <a href="#" class="list-group-item list-group-item-action ps-3 d-flex justify-content-between align-items-center collapse-toggle" data-bs-toggle="collapse" data-bs-target="#${clsId}">
            <span>${clsName}</span>
            <span class="badge bg-light text-muted ms-auto text-truncate" style="max-width:10rem" title="${cls.source}">${cls.source}</span>
            <span class="triangle-toggle ms-2"></span>
          </a>`);
        const brWrap = document.createElement("div");
        brWrap.className = "collapse";
        brWrap.id = clsId;
        catCol.appendChild(brWrap);
        branches.forEach(br => brWrap.appendChild(makeLink(br.name, branchSource(br, cls.source), { section: clsName, branch: br.name }, 5)));
      }
    });
  });
}

// ------------- Helper : Création de lien ----------------------------------
function makeLink(label, src, data = {}, pad = 3) {
  const a = document.createElement("a");
  a.href = "#";
  a.className = `list-group-item list-group-item-action ps-${pad} d-flex justify-content-between align-items-center`;
  a.innerHTML = `
    <span>${label}</span>
    <span class="badge bg-light text-muted ms-auto text-truncate" style="max-width:10rem" title="${src}">${src}</span>`;
  Object.entries(data).forEach(([k, v]) => a.dataset[k] = v);
  a.addEventListener("click", e => {
    e.preventDefault();
    renderSection(data.section, data.branch);
    setActiveLink(a);
  });
  return a;
}
function setActiveLink(el) {
  if (currentLink) currentLink.classList.remove("active");
  el.classList.add("active");
  currentLink = el;
}

function featureSource(feat, fallback) {
  return feat.Source || feat.source || fallback || "Unknown";
}


// ------------------------- SECTION MAIN -----------------------------------
function renderSection(clsName, branchName = "Default") {
  const pane = document.getElementById("cards-container");
  pane.innerHTML = "";
  const cls = classesData[clsName];
  if (!cls) return;

  const branches = cls.branches.filter(b => b.name === branchName);
  const title = (cls.branches.length === 1 && branchName === "Default")
    ? clsName
    : `${clsName} – ${branchName}`;
  pane.insertAdjacentHTML("afterbegin", `<h2 class="mt-3 mb-4">${title}</h2>`);
  pane.insertAdjacentHTML("beforeend",
    `<div class="mb-3"><input type="text" id="features-search" class="form-control" placeholder="Search features…"></div>`);

  const row = document.createElement("div");
  row.className = "row g-3";
  pane.appendChild(row);

  if (clsName === "General") {
    // --- FLUX PRINCIPAL ----------------------------------------------------
    let cardIndex = 0;                                   // pour 1ʳᵉ-carte badge
    branches.forEach(br => {
      br.features.forEach(feat => {
        // → si on est dans General ET la Source de la Feature n’est pas cochée,
        //   on saute entièrement cette Feature (et donc ses sous-features)
        if (clsName === "General" &&
          !activeSources.has(featureSource(feat, cls.source))) {
          return;                                        // on zappe
        }
        row.appendChild(createCard(
          feat,
          cls,
          cardIndex++ === 0,                            // 1ʳᵉ carte ?
          clsName === "General"
        ));
      });
    });
  } else {
    // ---- comportement précédent : flatten complet
    const leafs = [];
    branches.forEach(br => br.features.forEach(f => leafs.push(...collectLeafFeatures(f))));
    leafs.forEach((leaf, idx) =>
      row.appendChild(createCard(leaf, cls, idx === 0, false, /* embedSubs = */ false))
    );
  }

  document.getElementById("features-search").addEventListener("input", e => {
    const q = e.target.value.toLowerCase();
    row.querySelectorAll(".card").forEach(c =>
      c.closest(".col-md-12").style.display =
      c.dataset.title.toLowerCase().includes(q) ? "" : "none"
    );
  });

  window.scrollTo({ top: 0, behavior: "smooth" });
}


// --------- Collecte récursive des Features (carte-mère + feuilles) --------
const LEAF_KEYS = ["Effect", "Frequency", "Tags", "Trigger", "Target",
  "Prerequisites",            // ← utile pour vos données
  "effect", "frequency", "tags", "trigger", "target"];

function isLeaf(obj) {
  return LEAF_KEYS.some(k => k in obj);
}

/**
 * Retourne un tableau plat contenant :
 *   – la Feature courante si elle porte au moins un des LEAF_KEYS ;
 *   – toutes les sous-features profondes trouvées dans ses propriétés
 *     objet ou dans son éventuel tableau `children`.
 *
 * @param {Object} featObj    L’objet Feature à explorer
 * @param {string} [nameOverride] Nom forcé pour la carte (clé-propriété par ex.)
 * @returns {Object[]}        Tableau de Features prêtes pour `createCard`
 */
function collectLeafFeatures(featObj, nameOverride) {
  const list = [];
  const name = nameOverride || featObj.name || "(unnamed)";

  // 1) Si l’objet possède des champs « leaf », on pousse la carte-mère.
  if (isLeaf(featObj)) {
    list.push({ ...featObj, name });
  }

  // 2) Exploration des propriétés qui sont elles-mêmes des objets Feature.
  Object.entries(featObj).forEach(([k, v]) => {
    if (
      v && typeof v === "object" && !Array.isArray(v) &&
      // on ignore les simples métadonnées
      !["Source", "source"].includes(k)
    ) {
      list.push(...collectLeafFeatures(v, k));   // nom = clé-propriété
    }
  });

  // 3) Exploration d’un éventuel tableau children[].
  if (Array.isArray(featObj.children)) {
    featObj.children.forEach(ch => list.push(...collectLeafFeatures(ch)));
  }

  return list;
}



/* ------------------------------------------------------------------ *
 * 1. createCard() – rend une carte et, récursivement, ses sous-cartes
 * ------------------------------------------------------------------ */
function createCard(feat, clsMeta, firstInBranch, isGeneral, nested = false) {

  /* ----- conteneur colonne (pas de colonne Bootstrap quand imbriqué) */
  const col = document.createElement("div");
  if (!nested) col.className = "col-md-12";

  /* ----- carte ------------------------------------------------------ */
  const card = document.createElement("div");
  card.className = `card ${nested ? "mb-2" : "h-100"} bg-white border shadow-sm`;
  card.dataset.title = feat.name || "(unnamed)";

  const body = document.createElement("div");
  body.className = "card-body bg-light";

  /* ---------- badges ------------------------------------------------ */
  // Règle d’affichage :
  //   • Dans « General » : TOUS les badges, même imbriqués.
  //   • Ailleurs        : badges UNIQUEMENT sur la 1ʳᵉ carte racine (firstInBranch).
  const showBadges = isGeneral ? true : (!nested && firstInBranch);

  const catBadge = isGeneral
    ? (feat.Category || null)        // badge individuel
    : (showBadges ? clsMeta.category : null);   // badge de la classe

  const srcBadge = (isGeneral || showBadges)
    ? (feat.Source || feat.source || clsMeta.source)
    : null;

  let titleHTML = feat.name || "(unnamed)";
  if (catBadge) titleHTML += ` <span class="badge bg-secondary">${catBadge}</span>`;
  if (srcBadge) titleHTML += ` <span class="badge bg-info">${srcBadge}</span>`;

  body.insertAdjacentHTML("afterbegin", `<h5 class="card-title">${titleHTML}</h5>`);

  /* ---------- champs simples --------------------------------------- */
  Object.entries(feat).forEach(([k, v]) => {
    if (["name", "children", "Source", "source", "Category"].includes(k)) return;
    if (v == null || typeof v === "object") return;

    // ────────── si c’est l’Effect et qu’il contient du HTML ──────────
    if (k === "Effect" && /<\s*table/i.test(v)) {
      body.insertAdjacentHTML(
        "beforeend",
        `<div class="mb-2"><strong>Effect:</strong><br>${v}</div>` // v directement en HTML
      );
    } else {
      body.insertAdjacentHTML(
        "beforeend",
        `<p><strong>${k}:</strong> ${v.toString().replaceAll("\n", "<br>")}</p>`
      );
    }
  });


  /* ---------- sous-features imbriquées ----------------------------- */
  addSubFeatures(feat, clsMeta, body, isGeneral);

  card.appendChild(body);
  col.appendChild(card);
  return col;
}

/* ------------------------------------------------------------------ *
 * 2. addSubFeatures() – collecte et rend toutes les feuilles enfants
 * ------------------------------------------------------------------ */
function addSubFeatures(obj, clsMeta, container, isGeneral) {
  Object.entries(obj).forEach(([key, val]) => {
    if (!val || typeof val !== "object") return;

    // a) si c’est déjà une feuille -> carte enfant
    if (isLeaf(val)) {
      container.appendChild(
        createCard({ ...val, name: key }, clsMeta, false, isGeneral, true)
      );
      return;
    }

    // b) si c’est un tableau d’objets -> on descend
    if (Array.isArray(val)) {
      val.forEach(el => addSubFeatures(el, clsMeta, container, isGeneral));
      return;
    }

    // c) sinon, on continue la récursion (profondément imbriqué)
    addSubFeatures(val, clsMeta, container, isGeneral);
  });
}

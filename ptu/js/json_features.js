// === Citronnades – Unified Classes Viewer =============================
// Schéma JSON unifié :
//   {
//     "ClassName": {
//       "category": "Battling",
//       "source":   "Core",
//       "branches": [
//         { "name": "Attack", "features": [ … ] },
//         ...
//       ]
//     }
//   }
// ---------------------------------------------------------------------------
// UI PRINCIPES
//   • Sidebar
//       – Lien direct « General » toujours en tête (hors dossiers)
//       – Catégorie ▼ Classe ▼ Branche
//       – Si une classe n’a qu’une unique branche nommée « Default », on supprime
//         un niveau : la classe devient un lien direct (pas de sous‑branche).
//       – Les **filtres Source** sont évalués AU NIVEAU DES BRANCHES : une classe
//         reste visible tant qu’au moins une de ses branches correspond à une
//         source cochée, même si sa `source` principale est décochée.
//   • Paneau central
//       – Affiche les cartes des Features de la branche sélectionnée.
//       – Pour la classe « General », chaque carte montre un badge Source.
// ---------------------------------------------------------------------------
// Dépendances : Bootstrap 5 (collapse). Ajouter du CSS pour `.triangle-toggle`
//               si vous souhaitez l’icône qui pivote.
// ---------------------------------------------------------------------------

// ------------------------- VARIABLES GLOBALES ------------------------------
let classesData  = {};
let activeSources = new Set();
let currentLink   = null;

// ------------------------- CHARGEMENT JSON ---------------------------------
function loadClasses(path) {
  fetch(path)
    .then(r => r.json())
    .then(json => {
      classesData = json;
      buildSidebar();
      // Sélection : General sinon première classe visible
      const firstCls = classesData.General ? "General" : Object.keys(classesData)[0];
      const firstBranch = classesData[firstCls].branches[0]?.name || "Default";
      renderSection(firstCls, firstBranch);
      const l = document.querySelector(`[data-section="${firstCls}"][data-branch="${firstBranch}"]`);
      if (l) setActiveLink(l);
    })
    .catch(err => console.error("JSON load error:", err));
}

// ------------------------- SIDEBAR -----------------------------------------
function buildSidebar() {
  const sb = document.getElementById("sidebar");
  sb.innerHTML = "";

  sb.insertAdjacentHTML("beforeend", `
    <div class="mb-3">
      <input type="text" id="sidebar-search" class="form-control" placeholder="Rechercher…">
    </div>`);
  document.getElementById("sidebar-search").addEventListener("input", renderSidebar);

  // liste complète des sources (classe & branche) pour les filtres
  const allSources = new Set();
  Object.values(classesData).forEach(cls => {
    if (cls.source) allSources.add(cls.source);
    cls.branches.forEach(br => {
      const src = branchSource(br, cls.source);
      if (src) allSources.add(src);
    });
  });

  const filterWrap = document.createElement("div");
  filterWrap.className = "mb-3";
  filterWrap.innerHTML = `<label class="form-label">Filter by Source:</label>`;
  sb.appendChild(filterWrap);

  [...allSources].sort().forEach(src => {
    const id = `filter-src-${src}`;
    filterWrap.insertAdjacentHTML("beforeend", `
      <div class="form-check">
        <input class="form-check-input" type="checkbox" id="${id}" checked>
        <label class="form-check-label" for="${id}">${src}</label>
      </div>`);
  });
  filterWrap.querySelectorAll("input").forEach(cb => cb.addEventListener("change", renderSidebar));

  sb.insertAdjacentHTML("beforeend", `<div id="sidebar-links"></div>`);
  renderSidebar();
}

// ---------- Source dominante d’une branche ---------------------------------
function branchSource(branch, fallback) {
  const f = branch.features.find(fe => fe.Source || fe.source);
  return f ? (f.Source || f.source) : fallback || "Unknown";
}

// ---------- Render Sidebar -------------------------------------------------
function renderSidebar() {
  const box = document.getElementById("sidebar-links");
  box.innerHTML = "";

  // maj activeSources depuis les checkboxes
  activeSources.clear();
  document.querySelectorAll('[id^="filter-src-"]:checked').forEach(cb => activeSources.add(cb.id.replace("filter-src-", "")));

  const query = document.getElementById("sidebar-search").value.trim().toLowerCase();

  // ========== GENERAL ======================================================
  if (classesData.General) {
    // General visible si au moins une Feature a une source cochée
    const genVisible = classesData.General.branches[0].features.some(f => activeSources.has(f.Source || f.source || classesData.General.source));
    if (genVisible && (!query || "general".includes(query))) {
      box.appendChild(makeLink("General", classesData.General.source, { section: "General", branch: "Default" }, 3));
    }
  }

  // ========== PAR CATÉGORIE ===============================================
  const byCat = {};

  Object.entries(classesData).forEach(([clsName, cls]) => {
    if (clsName === "General") return;

    // Filtre texte au niveau classe
    if (query && !clsName.toLowerCase().includes(query)) return;

    // Conserver seulement les branches dont la source est active
    const visibleBranches = cls.branches.filter(br => activeSources.has(branchSource(br, cls.source)));
    if (visibleBranches.length === 0) return; // rien à montrer si aucune branche autorisée

    const cat = cls.category || "Other";
    (byCat[cat] ??= []).push([clsName, cls, visibleBranches]);
  });

  Object.keys(byCat).sort().forEach(cat => {
    const catId = `collapse-cat-${cat.replace(/\s+/g, "-")}`;
    box.insertAdjacentHTML("beforeend", `
      <button class="btn btn-sm btn-light w-100 text-start collapse-toggle mb-1" data-bs-toggle="collapse" data-bs-target="#${catId}">📁 ${cat}</button>`);
    const catCol = document.createElement("div");
    catCol.className = "collapse mb-2";
    catCol.id = catId;
    box.appendChild(catCol);

    byCat[cat].sort(([a], [b]) => a.localeCompare(b)).forEach(([clsName, cls, branches]) => {
      const singleDefault = branches.length === 1 && branches[0].name === "Default";
      if (singleDefault) {
        const src = branchSource(branches[0], cls.source);
        catCol.appendChild(makeLink(clsName, src, { section: clsName, branch: "Default" }, 4));
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
        branches.forEach(br => brWrap.appendChild(
          makeLink(br.name, branchSource(br, cls.source), { section: clsName, branch: br.name }, 5)
        ));
      }
    });
  });
}

// ---------- Helper : crée un lien -----------------------------------------
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

// ------------------------- SECTION MAIN -----------------------------------
function renderSection(clsName, branchName = "Default") {
  const pane = document.getElementById("cards-container");
  pane.innerHTML = "";
  const cls = classesData[clsName];
  if (!cls) return;

  const multiBranch = !(cls.branches.length === 1 && branchName === "Default");
  pane.insertAdjacentHTML("beforeend", `<h2 class="mt-3 mb-4">${multiBranch ? clsName + " – " + branchName : clsName}</h2>`);
  pane.insertAdjacentHTML("beforeend", `<div class="mb-3"><input type="text" id="features-search" class="form-control" placeholder="Search features…"></div>`);

  const row = document.createElement("div");
  row.className = "row g-3";
  pane.appendChild(row);

  const branches = cls.branches.filter(b => b.name === branchName);
  branches.forEach(br => br.features.forEach((feat, idx) => row.appendChild(createCard(feat, cls, idx === 0, clsName === "General"))));

  document.getElementById("features-search").addEventListener("input", e => {
    const q = e.target.value.toLowerCase();
    row.querySelectorAll(".card").forEach(c => c.parentElement.style.display = c.dataset.title.toLowerCase().includes(q) ? "" : "none");
  });

  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ------------------------- CARTE -----------------------------------------
function createCard(feat, clsMeta, firstInBranch, forceBadges) {
  const col = document.createElement("div");
  col.className = "col-md-12";

  const card = document.createElement("div");
  card.className = "card h-100 bg-white border shadow-sm";
  card.dataset.title = feat.name || "(unnamed)";

  const body = document.createElement("div");
  body.className = "card-body bg-light";

  const badgeSrc = feat.Source || feat.source || clsMeta.source;
  let titleHTML = feat.name || "(unnamed)";
  if (forceBadges || firstInBranch) {
    if (clsMeta.category) titleHTML += ` <span class="badge bg-secondary">${clsMeta.category}</span>`;
    if (badgeSrc)         titleHTML += ` <span class="badge bg-info">${badgeSrc}</span>`;
  }
  body.insertAdjacentHTML("beforeend", `<h5 class="card-title">${titleHTML}</h5>`);

  Object.entries(feat).forEach(([k, v]) => {
    if (["name", "children", "Source", "source"].includes(k)) return;
    if (v == null || v === "") return;

    if (typeof v === "object") {
      const sub = createCard({ name: k, ...v }, clsMeta, false, forceBadges);
      sub.querySelector(".card").classList.add("ms-3");
      body.appendChild(sub);
    } else {
      body.insertAdjacentHTML("beforeend", `<p><strong>${k}:</strong> ${v.toString().replaceAll("\n", "<br>")}</p>`);
    }
  });

  if (Array.isArray(feat.children)) feat.children.forEach(ch => {
    const sub = createCard(ch, clsMeta, false, forceBadges);
    sub.querySelector(".card").classList.add("ms-3");
    body.appendChild(sub);
  });

  card.appendChild(body);
  col.appendChild(card);
  return col;
}

// ----------------------- INIT --------------------------------------------
loadClasses("/ptu/data/features/features_core.json");
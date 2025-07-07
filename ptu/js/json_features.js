// === Citronnades – Unified Classes Viewer =============================
// JSON unifié :
//   "ClassName" → { category, source, branches:[ { name, features:[…] } ] }
// ---------------------------------------------------------------------------
// UI
// ─ Sidebar
//     • Lien direct « General » (hors dossier, toujours en tête)
//     • Catégorie ▼ Classe ▼ Branche (Bootstrap collapse)
// ─ Paneau central
//     • Affiche les Features de la branche sélectionnée
//     • Cartes Bootstrap récursives (une carte par Feature – sous‑Features incluses)
//     • Pour *General*, chaque carte affiche un badge *Source*
//     • La propriété "Source" n'est plus répétée en bas du contenu ; seules les
//       pastilles servent d’indicateur.
// ---------------------------------------------------------------------------
// Dépendances : Bootstrap 5 (CSS + JS). Ajoute en CSS une règle `.triangle-toggle`
// si tu veux faire pivoter une icône ▼▲ sur l’attribut `[aria-expanded]`.
// ---------------------------------------------------------------------------

// ----------------------- VARIABLES GLOBALES --------------------------------
let classesData = {};          // contiendra tout le JSON
let activeSources = new Set(); // filtres source
let currentLink   = null;      // lien actif dans la sidebar

// ----------------------- CHARGEMENT DU JSON --------------------------------
function loadClasses(file) {
  fetch(file)
    .then(r => r.json())
    .then(json => {
      classesData = json;
      buildSidebar();
      // affichage par défaut : General si dispo
      if (classesData.General) {
        renderSection("General");
        const g = document.querySelector('[data-section="General"]');
        if (g) setActiveLink(g);
      }
    })
    .catch(err => console.error("JSON load error:", err));
}

// ----------------------- SIDEBAR : construction ---------------------------
function buildSidebar() {
  const sb = document.getElementById("sidebar");
  sb.innerHTML = "";

  // --- recherche globale ---
  sb.insertAdjacentHTML("beforeend", `
    <div class="mb-3">
      <input type="text" id="sidebar-search" class="form-control" placeholder="Rechercher…">
    </div>`);
  document.getElementById("sidebar-search").addEventListener("input", renderSidebarLinks);

  // --- filtres Source ---
  const sources = Array.from(new Set(Object.values(classesData).map(c => c.source || "Unknown"))).sort();
  activeSources = new Set(sources);

  const fWrap = document.createElement("div");
  fWrap.className = "mb-3";
  fWrap.innerHTML = `<label class="form-label">Filter by Source:</label>`;
  sb.appendChild(fWrap);
  sources.forEach(src => {
    const id = `filter-src-${src}`;
    fWrap.insertAdjacentHTML("beforeend", `
      <div class="form-check">
        <input class="form-check-input" type="checkbox" id="${id}" checked>
        <label class="form-check-label" for="${id}">${src}</label>
      </div>`);
  });
  fWrap.querySelectorAll("input").forEach(cb => cb.addEventListener("change", renderSidebarLinks));

  // conteneur de liens
  sb.insertAdjacentHTML("beforeend", `<div id="sidebar-links"></div>`);
  renderSidebarLinks();
}

// ----------------------- SIDEBAR : liens ----------------------------------
function renderSidebarLinks() {
  const box = document.getElementById("sidebar-links");
  box.innerHTML = "";

  // MAJ Source actives
  activeSources.clear();
  document.querySelectorAll('[id^="filter-src-"]:checked').forEach(cb => {
    activeSources.add(cb.id.replace("filter-src-", ""));
  });

  const q = document.getElementById("sidebar-search").value.trim().toLowerCase();

  // ----- 1) lien GENERAL ---------------------------------------------------
  if (classesData.General && activeSources.has(classesData.General.source)) {
    if (!q || "general".includes(q)) {
      box.appendChild(makeLink("General", classesData.General.source, { section: "General" }));
    }
  }

  // ----- 2) classes regroupées par catégorie ------------------------------
  const byCat = {};
  Object.entries(classesData).forEach(([name, cls]) => {
    if (name === "General") return;
    if (!activeSources.has(cls.source)) return;
    if (q && !name.toLowerCase().includes(q)) return;
    const cat = cls.category || "Other";
    if (!byCat[cat]) byCat[cat] = [];
    byCat[cat].push([name, cls]);
  });

  Object.keys(byCat).sort().forEach(cat => {
    const catId = `collapse-cat-${cat.replace(/\s+/g, "-")}`;
    box.insertAdjacentHTML("beforeend", `
      <button class="btn btn-sm btn-light w-100 text-start collapse-toggle mb-1" data-bs-toggle="collapse" data-bs-target="#${catId}">
        📁 ${cat}
      </button>`);
    const catCol = document.createElement("div");
    catCol.className = "collapse mb-2";
    catCol.id = catId;
    box.appendChild(catCol);

    byCat[cat].sort(([a], [b]) => a.localeCompare(b)).forEach(([clsName, cls]) => {
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

      if (cls.branches.length === 1 && cls.branches[0].name === "Default") {
        brWrap.appendChild(makeLink(clsName, cls.source, { section: clsName, branch: "Default" }, 4));
      } else {
        cls.branches.forEach(br => {
          brWrap.appendChild(makeLink(br.name, cls.source, { section: clsName, branch: br.name }, 4));
        });
      }
    });
  });
}

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

function setActiveLink(link) {
  if (currentLink) currentLink.classList.remove("active");
  link.classList.add("active");
  currentLink = link;
}

// ----------------------- SECTION (branche) ---------------------------------
function renderSection(className, branchName = null) {
  const pane = document.getElementById("cards-container");
  pane.innerHTML = "";

  const cls = classesData[className];
  if (!cls) return;

  const title = branchName && branchName !== "Default" ? `${className} – ${branchName}` : className;
  pane.insertAdjacentHTML("beforeend", `<h2 class="mt-3 mb-4">${title}</h2>`);
  pane.insertAdjacentHTML("beforeend", `<div class="mb-3"><input type="text" id="features-search" class="form-control" placeholder="Search features…"></div>`);

  const row = document.createElement("div");
  row.className = "row g-3";
  pane.appendChild(row);

  const branches = branchName ? cls.branches.filter(b => b.name === branchName) : cls.branches;

  branches.forEach(br => {
    br.features.forEach((feat, idx) => {
      row.appendChild(createCard(feat, cls, idx === 0, className === "General"));
    });
  });

  document.getElementById("features-search").addEventListener("input", e => {
    const q = e.target.value.toLowerCase();
    row.querySelectorAll(".card").forEach(cd => {
      const t = cd.dataset.title.toLowerCase();
      cd.parentElement.style.display = t.includes(q) ? "" : "none";
    });
  });

  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ----------------------- CARTE : récursif ----------------------------------
function createCard(feat, clsMeta, firstInBranch, forceBadges) {
  const col = document.createElement("div");
  col.className = "col-md-12";

  const card = document.createElement("div");
  card.className = "card h-100 bg-white border shadow-sm";
  card.dataset.title = feat.name || "(unnamed)";

  const body = document.createElement("div");
  body.className = "card-body bg-light";

  // ---------- titre + badges ----------
  const h5 = document.createElement("h5");
  h5.className = "card-title";

  const badgeSrc = feat.Source || feat.source || clsMeta.source;
  let html = feat.name || "(unnamed)";
  if (forceBadges || firstInBranch) {
    if (clsMeta.category) html += ` <span class="badge bg-secondary">${clsMeta.category}</span>`;
    if (badgeSrc)         html += ` <span class="badge bg-info">${badgeSrc}</span>`;
  }
  h5.innerHTML = html;
  body.appendChild(h5);

  // ---------- contenu clé/valeur ----------
  Object.entries(feat).forEach(([k, v]) => {
    if (["name", "children", "Source", "source"].includes(k)) return; // on masque Source (voyant déjà en badge)
    if (v == null || v === "") return;

    if (typeof v === "object") {
      // sous‑Feature → carte enfant indentée
      const sub = createCard({ name: k, ...v }, clsMeta, false, forceBadges);
      sub.querySelector(".card").classList.add("ms-3");
      body.appendChild(sub);
    } else {
      const p = document.createElement("p");
      p.innerHTML = `<strong>${k}:</strong> ${v.toString().replaceAll("\n", "<br>")}`;
      body.appendChild(p);
    }
  });

  // ---------- children explicites ----------
  if (Array.isArray(feat.children)) {
    feat.children.forEach(child => {
      const sub = createCard(child, clsMeta, false, forceBadges);
      sub.querySelector(".card").classList.add("ms-3");
      body.appendChild(sub);
    });
  }

  card.appendChild(body);
  col.appendChild(card);
  return col;
}

// ---------------------------------------------------------------------------
// Lance le chargement  (⚠️ adapter le chemin vers votre JSON)
// ---------------------------------------------------------------------------
loadClasses("/ptu/data/features/features_core.json");

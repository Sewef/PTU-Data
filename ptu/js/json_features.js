// === Citronnades – Unified Classes Viewer =============================
// JSON unifié → { className: { category, source, branches:[{ name, features }] } }
// ---------------------------------------------------------------------------
// UI
//   • Sidebar
//       – Lien direct « General » (hors dossier, toujours en tête)
//       – Catégorie ▼ Classe (si la classe possède ≥2 branches OU une branche nommée ≠ "Default")
//       – Catégorie ▸ Classe (lien direct) si la classe n'a qu'une seule branche "Default"
//       – Chaque branche affiche désormais la bonne Source (celle de la Feature dominante)
//   • Paneau central : Cartes des Features de la branche sélectionnée
//   • Pour la classe « General », toutes les cartes affichent un badge Source
// ---------------------------------------------------------------------------
// Dépendances : Bootstrap 5 pour les collapse. Ajoute un .triangle-toggle en CSS si besoin.
// ---------------------------------------------------------------------------

// ----------------------- VARIABLES GLOBALES --------------------------------
let classesData = {};
let activeSources = new Set();
let currentLink   = null;

// ----------------------- CHARGEMENT DU JSON --------------------------------
function loadClasses(file) {
  fetch(file)
    .then(r => r.json())
    .then(data => {
      classesData = data;
      buildSidebar();
      const first = classesData.General ? "General" : Object.keys(classesData)[0];
      renderSection(first, classesData[first].branches[0]?.name || "Default");
      const l = document.querySelector(`[data-section="${first}"]`);
      if (l) setActiveLink(l);
    })
    .catch(err => console.error("JSON load error:", err));
}

// ----------------------- SIDEBAR ------------------------------------------
function buildSidebar() {
  const sb = document.getElementById("sidebar");
  sb.innerHTML = "";

  sb.insertAdjacentHTML("beforeend", `
    <div class="mb-3">
      <input type="text" id="sidebar-search" class="form-control" placeholder="Rechercher…">
    </div>`);
  document.getElementById("sidebar-search").addEventListener("input", renderSidebarLinks);

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

  sb.insertAdjacentHTML("beforeend", `<div id="sidebar-links"></div>`);
  renderSidebarLinks();
}

// Helper: trouve la Source dominante d'une branche (première Feature qui en a une)
function branchSource(branch, fallback) {
  const f = branch.features.find(fe => fe.Source || fe.source);
  return f ? (f.Source || fe.source) : fallback;
}

function renderSidebarLinks() {
  const box = document.getElementById("sidebar-links");
  box.innerHTML = "";

  activeSources.clear();
  document.querySelectorAll('[id^="filter-src-"]:checked').forEach(cb => activeSources.add(cb.id.replace("filter-src-", "")));

  const q = document.getElementById("sidebar-search").value.trim().toLowerCase();

  // ----------- General en tête -------------------------------------------
  if (classesData.General && activeSources.has(classesData.General.source)) {
    if (!q || "general".includes(q)) {
      box.appendChild(makeLink("General", classesData.General.source, { section: "General", branch: "Default" }, 3));
    }
  }

  // ----------- Regroupement par catégorie --------------------------------
  const byCat = {};
  Object.entries(classesData).forEach(([name, cls]) => {
    if (name === "General") return;
    if (!activeSources.has(cls.source)) return;
    if (q && !name.toLowerCase().includes(q)) return;
    const cat = cls.category || "Other";
    (byCat[cat] ??= []).push([name, cls]);
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
      const singleDefault = cls.branches.length === 1 && cls.branches[0].name === "Default";

      if (singleDefault) {
        const src = branchSource(cls.branches[0], cls.source);
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
        cls.branches.forEach(br => brWrap.appendChild(
          makeLink(br.name, branchSource(br, cls.source), { section: clsName, branch: br.name }, 5)
        ));
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

// ----------------------- SECTION -----------------------------------------
function renderSection(className, branchName = "Default") {
  const pane = document.getElementById("cards-container");
  pane.innerHTML = "";
  const cls = classesData[className];
  if (!cls) return;

  const showTitle = branchName && !(cls.branches.length === 1 && branchName === "Default");
  pane.insertAdjacentHTML("beforeend", `<h2 class="mt-3 mb-4">${showTitle ? className + " – " + branchName : className}</h2>`);
  pane.insertAdjacentHTML("beforeend", `<div class="mb-3"><input type="text" id="features-search" class="form-control" placeholder="Search features…"></div>`);

  const row = document.createElement("div");
  row.className = "row g-3";
  pane.appendChild(row);

  const branches = cls.branches.filter(b => !branchName || b.name === branchName);
  branches.forEach(br => br.features.forEach((feat, i) => row.appendChild(createCard(feat, cls, i === 0, className === "General"))));

  document.getElementById("features-search").addEventListener("input", e => {
    const q = e.target.value.toLowerCase();
    row.querySelectorAll(".card").forEach(c => c.parentElement.style.display = c.dataset.title.toLowerCase().includes(q) ? "" : "none");
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ----------------------- CARTE -------------------------------------------
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
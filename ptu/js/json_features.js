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

      const params = new URLSearchParams(window.location.search);
      const section = params.get("section");
      const branch = params.get("branch");

      let clsName = section && classesData[section] ? section : (classesData.General ? "General" : Object.keys(classesData)[0]);
      let brName = branch || classesData[clsName].branches[0].Name;

      renderSection(clsName, brName);

      const l = document.querySelector(`[data-section="${clsName}"][data-branch="${brName}"]`);
      if (l) {
        setActiveLink(l);

        // Expand the sidebar folder for the selected class
        const parentCollapse = l.closest(".collapse");
        if (parentCollapse) {
          new bootstrap.Collapse(parentCollapse, { toggle: true });
        }
      }
    })
    .catch(err => console.error("JSON load error:", err));
}

// ------------------------- SIDEBAR -----------------------------------------
function buildSidebar() {
  const sb = document.getElementById("sidebar");
  sb.innerHTML = `
    <div class="mb-3">
      <input type="text" id="sidebar-search" class="form-control" placeholder="Search classes...">
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
      // Store the state of the collapsible elements
      const expandedCategories = new Set();
      document.querySelectorAll('.collapse.show').forEach(el => {
        expandedCategories.add(el.id);
      });

      renderSidebar();                                   // ← sidebar mise à jour

      // Restore the state of the collapsible elements
      expandedCategories.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
          new bootstrap.Collapse(el, { toggle: true }); // Manually show the collapsed element
        }
      });

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
  const feats = Array.isArray(branch?.features) ? branch.features : [];
  const featWithSrc = feats.find(f => f && (f.Source || f.source));
  return featWithSrc ? (featWithSrc.Source || featWithSrc.source) : (fallback || "Unknown");
}

// ------------- Icones Catégories ------------------------------------------
const categoryIcons = {
  "Introductory": "🌱",
  "Battling": "⚔️",
  "Specialist Team": "🛡️",
  "Professional": "💼",
  "Fighter": "👊",
  "Supernatural": "👻",
  "Uncategorized": "❓",
  "Game of Throhs": "👑",
  "Do Porygon Dream of Mareep": "🤖",
};

// ------------- Rendu Sidebar ----------------------------------------------
function getCategoryIcon(category) {
  return categoryIcons[category] || "📁";
}
function renderSidebar() {
  const box = document.getElementById("sidebar-links");
  box.innerHTML = "";

  activeSources.clear();
  document.querySelectorAll('[id^="filter-src-"]:checked').forEach(cb => activeSources.add(cb.id.replace("filter-src-", "")));

  const q = document.getElementById("sidebar-search").value.trim().toLowerCase();

  // ----- GENERAL -----------------------------------------------------------
  if (classesData.General) {
    const g = classesData.General;
    const br0 = (Array.isArray(g.branches) && g.branches[0]) ? g.branches[0] : null;
    const feats = Array.isArray(br0?.features) ? br0.features : [];
    const genVisible = feats.some(f => activeSources.has((f && (f.Source || f.source)) || g.source));
    if (genVisible && (!q || "general".includes(q))) {
      box.appendChild(makeLink("General", g.source || "Unknown", { section: "General", branch: "Default" }, 3));
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

  const orderedCats = Object.keys(cats);

  orderedCats.forEach(cat => {
    const catId = `collapse-cat-${cat.replace(/\s+/g, "-")}`;
    box.insertAdjacentHTML("beforeend", `
      <button class="btn btn-sm btn-light w-100 text-start collapse-toggle mb-1" data-bs-toggle="collapse" data-bs-target="#${catId}">${getCategoryIcon(cat)} ${cat}</button>`);

    const catCol = document.createElement("div");
    catCol.className = "collapse mb-2";
    catCol.id = catId;
    box.appendChild(catCol);

    cats[cat].sort(([a], [b]) => a.localeCompare(b)).forEach(([clsName, cls, branches]) => {
      const singleDefault = branches.length === 1 && branches[0].Name === "Default";
      if (singleDefault) {
        catCol.appendChild(makeLink(clsName, branchSource(branches[0], cls.source), { section: clsName, branch: "Default" }, 4));
      } else {
        const clsId = `collapse-cls-${clsName.replace(/\s+/g, "-")}`;
        catCol.insertAdjacentHTML("beforeend", `
          <a href="#" class="list-group-item list-group-item-action ps-4 d-flex justify-content-between align-items-center collapse-toggle" data-bs-toggle="collapse" data-bs-target="#${clsId}">
            <span>${clsName}</span>
            <span class="badge bg-light text-muted ms-auto text-truncate" style="max-width:10rem" title="${cls.source}">${cls.source}</span>
            <span class="triangle-toggle ms-2"></span>
          </a>`);
        const brWrap = document.createElement("div");
        brWrap.className = "collapse";
        brWrap.id = clsId;
        catCol.appendChild(brWrap);
        branches.forEach(br => {
          const src = branchSource(br, cls.source);
          brWrap.appendChild(makeLink(br.Name, src, { section: clsName, branch: br.Name }, 5));
        });
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

  const section = el.dataset.section;
  const branch = el.dataset.branch;
  const url = new URL(window.location);
  const prev = url.searchParams.get("section") + "|" + url.searchParams.get("branch");
  const next = section + "|" + branch;

  url.searchParams.set("section", section);
  url.searchParams.set("branch", branch);
  if (prev === next) {
    window.history.replaceState({}, "", url);
  } else {
    window.history.pushState({}, "", url);
  }
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

  let branches = cls.branches.filter(b => b.Name === branchName);
  if (branches.length === 0) branches = [cls.branches[0]]; // fallback gracieux
  branchName = branches[0].Name;
  const title = (cls.branches.length === 1 && branchName === "Default")
    ? clsName
    : `${clsName} – ${branchName}`;
  pane.insertAdjacentHTML("afterbegin", `<h2 class="mt-3 mb-4">${title}</h2>`);
  pane.insertAdjacentHTML("beforeend",
    `<div class="mb-3"><input type="text" id="features-search" class="form-control" placeholder="Search features..."></div>`);

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
        const leafs = collectLeafFeatures(feat);
        leafs.forEach((leaf, idx) =>
          row.appendChild(createCard(leaf, cls, cardIndex++ === 0, true))
        );
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
    // cibler uniquement les cartes top-level :
    row.querySelectorAll(':scope > .col-md-12 > .card').forEach(card => {
      const match = (card.dataset.title || "").toLowerCase().includes(q);
      card.parentElement.style.display = match ? "" : "none";
    });
  });

  window.scrollTo({ top: 0, behavior: "smooth" });
}


// --------- Collecte récursive des Features (carte-mère + feuilles) --------
function collectLeafFeatures(featObj, nameOverride = null, embedOnly = false) {
  const list = [];
  const isSimpleTextMap = obj =>
    obj && typeof obj === "object" &&
    !Array.isArray(obj) &&
    Object.values(obj).every(v => typeof v === "string");

  const hasAnyContent = obj =>
    Object.entries(obj).some(([, v]) =>
      typeof v === "string" || isSimpleTextMap(v)
    );

  const cleaned = { ...featObj, Name: featObj.Name || nameOverride || "(unnamed)" };
  const subCards = [];

  // Recherche de tableaux de sous-features
  for (const [key, val] of Object.entries(featObj)) {
    if (
      Array.isArray(val) &&
      val.every(v => typeof v === "object" && (v.Name || v.Effect))
    ) {
      val.forEach(sub => {
        const child = { ...sub, Name: sub.Name || `(${key})` };
        subCards.push(...collectLeafFeatures(child, child.Name, true));
      });
    }
  }

  // Si l’objet principal contient du contenu, on le garde
  if (hasAnyContent(cleaned)) {
    if (subCards.length > 0) {
      cleaned.__children = subCards;
    }
    if (!embedOnly) list.push(cleaned);
    else return [cleaned];
  } else if (embedOnly && subCards.length > 0) {
    return subCards;
  }

  return list;
}


/* ------------------------------------------------------------------ *
 * 1. createCard() – rend une carte et, récursivement, ses sous-cartes
 * ------------------------------------------------------------------ */
function createCard(feat, clsMeta, firstInBranch, isGeneral, nested = false) {
  // ----- conteneur colonne (pas de colonne Bootstrap quand imbriqué)
  const col = document.createElement("div");
  if (!nested) col.className = "col-md-12";

  // ----- carte principale
  const card = document.createElement("div");
  card.className = `card ${nested ? "mb-2" : "h-100"} bg-white border shadow-sm`;
  card.dataset.title = feat.Name || "(unnamed)";

  const body = document.createElement("div");
  body.className = "card-body bg-light";

  // ----- badges
  const showBadges = isGeneral ? true : (!nested && firstInBranch);

  const catBadge = isGeneral
    ? (feat.Category || null)
    : (showBadges ? clsMeta.category : null);

  const srcBadge = (isGeneral || showBadges)
    ? (feat.Source || feat.source || clsMeta.source)
    : null;

  let titleHTML = feat.Name || "(unnamed)";
  if (catBadge) titleHTML += ` <span class="badge bg-secondary">${catBadge}</span>`;
  if (srcBadge) titleHTML += ` <span class="badge bg-info">${srcBadge}</span>`;

  body.insertAdjacentHTML("afterbegin", `<h5 class="card-title">${titleHTML}</h5>`);

  // ----- champs simples
  Object.entries(feat).forEach(([k, v]) => {
    if (["Name", "Source", "source", "Category", "__children"].includes(k)) return;
    if (v == null || typeof v === "object") return;

    if (k === "Effect" && /<\s*table/i.test(v)) {
      body.insertAdjacentHTML(
        "beforeend",
        `<div class="mb-2"><strong>Effect:</strong><br>${v}</div>`
      );
    } else {
      body.insertAdjacentHTML(
        "beforeend",
        `<p><strong>${k}:</strong> ${v.toString().replaceAll("\n", "<br>")}</p>`
      );
    }
  });

  // ----- enfants imbriqués uniquement ici
  if (feat.__children && Array.isArray(feat.__children)) {
    feat.__children.forEach(child => {
      body.appendChild(createCard(child, clsMeta, false, isGeneral, true));
    });
  }

  card.appendChild(body);
  col.appendChild(card);
  return col;
}

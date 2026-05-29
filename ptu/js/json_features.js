// ----------------------- GLOBAL VARIABLES -----------------------------------
let classesData = {};
let activeSources = new Set();
let currentLink = null;
let _cachedHashParams = null;
let _lastHashTime = 0;
let _currentViewClass = null; // Currently displayed class
let _currentViewBranch = null; // Currently displayed branch
let _searchTimeout = null; // Global timer for search

// Compiled regex constants
const COLUMN_GROUP_REGEX = /^(.*?)(?:_(\d+))$/;
const WHITESPACE_REGEX = /\s+/g;

// Parse hash parameters with cache (format: #key=value&key=value)
function getHashParams() {
  const hash = window.location.hash;
  // Cache to avoid recreating URLSearchParams object on each call
  if (_cachedHashParams && _lastHashTime === hash) {
    return _cachedHashParams;
  }
  _cachedHashParams = new URLSearchParams(hash.slice(1));
  _lastHashTime = hash;
  return _cachedHashParams;
}

function setHashParams(obj) {
  const params = new URLSearchParams(obj);
  const newHash = params.toString();
  const oldHash = window.location.hash.slice(1);
  
  if (oldHash === newHash) {
    return; // No change
  }
  
  _cachedHashParams = null; // Invalidate cache
  window.history.pushState({}, "", `#${newHash}`);
}

// --------- Global search setup ------------------------------------------
function setupGlobalSearch() {
  const searchEl = document.getElementById("features-search");
  if (!searchEl) return;

  searchEl.addEventListener("input", e => {
    clearTimeout(_searchTimeout);
    const q = e.target.value.toLowerCase();

    _searchTimeout = setTimeout(() => {
      if (!q.trim()) {
        // Empty search: redisplay current class
        renderSection(_currentViewClass, _currentViewBranch);
      } else {
        // Global search
        const results = globalFeatureSearch(q);
        if (results) {
          renderGlobalSearchResults(results);
        } else {
          // No results found
          const pane = document.getElementById("cards-container");
          pane.innerHTML = `<div class="alert alert-info">No features match "<strong>${escapeHTML(q)}</strong>"</div>`;
        }
      }
    }, 200); // 200ms debounce
  });
}

// ----------------------- JSON LOADING -----------------------------------
export function loadClasses(path) {
  fetch(path)
    .then(r => r.json())
    .then(json => {
      classesData = json;
      buildSidebar();

      const params = getHashParams();
      const section = params.get("section");
      const branch = params.get("branch");

      let clsName = section && classesData[section] ? section : (classesData.General ? "General" : Object.keys(classesData)[0]);
      let brName = branch || classesData[clsName].branches[0].Name;

      // Store current view
      _currentViewClass = clsName;
      _currentViewBranch = brName;

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

      // Setup global search (once only)
      setupGlobalSearch();
    })
    .catch(err => console.error("JSON load error:", err));
}

// ----------------------- SIDEBAR -----------------------------------------------
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

      renderSidebar();                                   // ← sidebar updated

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
        // (call preserves scrollTo and local search already in place)
      }
    })
  );


  sb.insertAdjacentHTML("beforeend", `<div id="sidebar-links"></div>`);
  renderSidebar();
}

// --------- Branch source helper --------------------------------
function branchSource(branch, fallback) {
  const feats = Array.isArray(branch?.features) ? branch.features : [];
  const featWithSrc = feats.find(f => f && (f.Source || f.source));
  return featWithSrc ? (featWithSrc.Source || featWithSrc.source) : (fallback || "Unknown");
}

// --------- Category icons ------------------------------------------------
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

  // ----- GENERAL ---------------------------------------------------------
  if (classesData.General) {
    const g = classesData.General;
    const br0 = (Array.isArray(g.branches) && g.branches[0]) ? g.branches[0] : null;
    const feats = Array.isArray(br0?.features) ? br0.features : [];
    const genVisible = feats.some(f => activeSources.has((f && (f.Source || f.source)) || g.source));
    if (genVisible && (!q || "general".includes(q))) {
      box.appendChild(makeLink("General", g.source || "Unknown", { section: "General", branch: "Default" }, 3));
    }
  }

  // ----- CATEGORIES ---------------------------------------------------
  const cats = {};
  const lowerQ = q.toLowerCase(); // Cache lowercase conversion
  Object.entries(classesData).forEach(([clsName, cls]) => {
    if (clsName === "General") return;
    if (q && !clsName.toLowerCase().includes(lowerQ)) return;

    const visibleBranches = cls.branches.filter(br => activeSources.has(branchSource(br, cls.source)));
    if (visibleBranches.length === 0) return;

    (cats[cls.category || "Other"] ??= []).push([clsName, cls, visibleBranches]);
  });

  const orderedCats = Object.keys(cats);

  orderedCats.forEach((cat, index) => {
    const catId = "cat_" + cat.replace(/\s+/g, "_");

    const catTgl = document.createElement("a");
    catTgl.href = "#";
    catTgl.className =
      "list-group-item list-group-item-action d-flex align-items-center collapse-toggle collapsed mb-1 ps-3";

    // Add spacing above first category
    if (index === 0) {
      const sep = document.createElement("div");
      sep.className = "border-top my-2"; // grey line + margin
      box.appendChild(sep);
    }

    catTgl.dataset.bsToggle = "collapse";
    catTgl.dataset.bsTarget = `#${catId}`;
    catTgl.innerHTML = `
    <span class="me-2">${getCategoryIcon(cat)}</span>
    <span class="flex-grow-1">${cat}</span>
    <span class="triangle-toggle ms-2"></span>`;
    catTgl.onclick = () => false; // Preferred to addEventListener to prevent default
    box.appendChild(catTgl);

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
        // Escape values to prevent XSS
    catCol.insertAdjacentHTML("beforeend", `
          <a href="#" class="list-group-item list-group-item-action ps-4 d-flex justify-content-between align-items-center collapse-toggle collapsed" data-bs-toggle="collapse" data-bs-target="#${clsId}">
            <span>${escapeHTML(clsName)}</span>
            <span class="badge bg-secondary-subtle ms-auto text-truncate" style="max-width:10rem" title="${escapeHTML(cls.source)}">${escapeHTML(cls.source)}</span>
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


// --------- Link creation helper -----------------------------------------
function makeLink(label, src, data = {}, pad = 3) {
  const a = document.createElement("a");
  a.href = "#";
  a.className = `list-group-item list-group-item-action ps-${pad} d-flex justify-content-between align-items-center`;
  // Escape HTML values to prevent XSS
  const escapedLabel = escapeHTML(label);
  const escapedSrc = escapeHTML(src);
  a.innerHTML = `
    <span>${escapedLabel}</span>
    <span class="badge bg-secondary-subtle ms-auto text-truncate" style="max-width:10rem" title="${escapedSrc}">${escapedSrc}</span>`;
  Object.entries(data).forEach(([k, v]) => a.dataset[k] = v);
  a.onclick = () => {
    renderSection(data.section, data.branch);
    setActiveLink(a);
    return false;
  };
  return a;
}

function setActiveLink(el) {
  if (currentLink) currentLink.classList.remove("active");
  el.classList.add("active");
  currentLink = el;

  const section = el.dataset.section;
  const branch = el.dataset.branch;
  
  const oldParams = getHashParams();
  const prev = oldParams.get("section") + "|" + oldParams.get("branch");
  const next = section + "|" + branch;

  const newParams = new URLSearchParams();
  newParams.set("section", section);
  newParams.set("branch", branch);
  
  if (prev === next) {
    window.history.replaceState({}, "", `#${newParams.toString()}`);
  } else {
    window.history.pushState({}, "", `#${newParams.toString()}`);
  }
}

function featureSource(feat, fallback) {
  return feat.Source || feat.source || fallback || "Unknown";
}

// --------- Global feature search -----------------------------------
function globalFeatureSearch(query) {
  if (!query) return null;
  
  const q = query.toLowerCase();
  const results = {}; // { className: { branchName: [features] } }
  
  Object.entries(classesData).forEach(([clsName, cls]) => {
    cls.branches?.forEach(br => {
      const matchedFeatures = [];
      
      br.features?.forEach(feat => {
        // Recursively collect all matching features
        const collectMatches = (f) => {
          const matched = [];
          if (!f) return matched;
          
          const name = (f.Name || "").toLowerCase();
          if (name.includes(q)) {
            matched.push(f);
          }
          
          // Search in sub-features (arrays of features)
          if (Array.isArray(f.features)) {
            f.features.forEach(sub => {
              matched.push(...collectMatches(sub));
            });
          }
          
          return matched;
        };
        
        matchedFeatures.push(...collectMatches(feat));
      });
      
      if (matchedFeatures.length > 0) {
        if (!results[clsName]) results[clsName] = {};
        results[clsName][br.Name] = matchedFeatures;
      }
    });
  });
  
  return Object.keys(results).length > 0 ? results : null;
}

// --------- Render global search results --------------------------------
function renderGlobalSearchResults(results) {
  const pane = document.getElementById("cards-container");
  pane.innerHTML = "";
  
  // Title
  pane.insertAdjacentHTML("afterbegin", 
    `<h2 class="mb-1" style="font-size:1.5rem;">Search Results</h2>`
  );
  
  const row = document.createElement("div");
  row.className = "row g-3 mt-2";
  
  // Iterate through results and display features
  Object.entries(results).forEach(([clsName, branches]) => {
    Object.entries(branches).forEach(([brName, features]) => {
      const cls = classesData[clsName];
      
      features.forEach(feat => {
        // collectLeafFeatures now fully clones, no need to clean
        const leafs = collectLeafFeatures(feat);
        leafs.forEach(leaf => {
          // Create a wrapper for the card with source badge
          const wrapper = document.createElement("div");
          wrapper.className = "col-md-12";
          
          // Source badge
          const badge = document.createElement("div");
          badge.className = "mb-2";
          badge.innerHTML = `
            <small class="text-muted">
              From <strong>${escapeHTML(clsName)}</strong> 
              ${brName !== "Default" ? `› ${escapeHTML(brName)}` : ""}
              ${cls.category ? ` • ${escapeHTML(cls.category)}` : ""}
            </small>
          `;
          wrapper.appendChild(badge);
          
          // Create the card
          const cardCol = createCard(leaf, cls, clsName === "General", false);
          // createCard already returns a column, so just extract the card
          const card = cardCol.querySelector(".card");
          if (card) {
            wrapper.appendChild(card);
          }
          
          row.appendChild(wrapper);
        });
      });
    });
  });
  
  pane.appendChild(row);
}


// ------------------------- SECTION MAIN -----------------------------------
function makeGaugeBar(value) {
  const v = Math.max(0, Math.min(5, Number(value) || 0));
  const percent = (v / 5) * 100;

  // progress bar with Bootstrap classes
  return `
    <div class="progress" style="height: 6px; width: 100%; min-width: 170px">
      <div class="progress-bar bg-primary" role="progressbar" style="width:${percent}%"></div>
    </div>
  `;
}


function renderSection(clsName, branchName = "Default") {
  // Update current view
  _currentViewClass = clsName;
  _currentViewBranch = branchName;

  const pane = document.getElementById("cards-container");
  pane.innerHTML = "";
  const cls = classesData[clsName];
  if (!cls) return;

  let branches = cls.branches.filter(b => b.Name === branchName);
  if (branches.length === 0) branches = [cls.branches[0]]; // graceful fallback
  branchName = branches[0].Name;

  const title = (cls.branches.length === 1 && branchName === "Default")
    ? clsName
    : `${clsName} – ${branchName}`;
  let supportInline = "";
  const stats = cls.Stats;

  if (clsName !== "General" && stats && typeof stats === "object") {

    // Build each column (one per stat)
    const cols = Object.entries(stats)
      .map(([label, value]) => `
      <span class="d-flex flex-column align-items-start" style="line-height:2.25;">
        <span class="fw-semibold text-muted">${label}</span>
        ${makeGaugeBar(value)}
      </span>
    `)
      .join("");

    supportInline = `
    <span class="ms-4 d-flex flex-wrap align-items-end" 
          style="font-size:0.9rem; gap:2rem;">
      ${cols}
    </span>
  `;
  }

  let imgBase = clsName.replace(/\(.*?\)/g, "").trim();
  const imgPath = `/ptu/img/features/${imgBase}.png`;

  const portraitHTML = `
  <img src="${imgPath}"
       onerror="this.style.display='none'"
       class="me-3 rounded-circle"
       style="width:60px; height:60px; object-fit:cover;">
`;

  // --- Class badges (category + source if present)
  const classBadges = [];

  if (clsName !== "General") {
    const currentBranch = branches[0];
    const currentSource = branchSource(currentBranch, cls.source);
    if (cls.category) {
      classBadges.push(`<span class="badge bg-secondary me-1">${cls.category}</span>`);
    }
    if (currentSource) {
      classBadges.push(`<span class="badge bg-info me-1">${currentSource}</span>`);
    }
  }

  const badgesHTML = `<span class="class-badges">${classBadges.join("")}</span>`;

  // --- Final : header complet ---
  pane.insertAdjacentHTML(
    "afterbegin",
    `
  <div class="mb-3" style="font-size:1rem;">
    <h2 class="d-flex align-items-center flex-wrap mb-1" style="gap:1rem; font-size:1.5rem;">
      ${portraitHTML}
      <span class="d-flex flex-column">
        <span class="d-flex align-items-center" style="gap:0.5rem;">
          <span>${title}</span>
          <span>${classBadges.join("")}</span>
        </span>
        ${supportInline}
      </span>
    </h2>
  </div>
  `
  );

  const row = document.createElement("div");
  row.className = "row g-3 mt-1";
  pane.appendChild(row);

  if (clsName === "General") {
    // --- MAIN FLOW -------------------------------------------------------
    let cardIndex = 0;                                   // for first-card badge
    branches.forEach(br => {
      br.features.forEach(feat => {
        // → if in General AND the Feature Source is not checked,
        //   skip this Feature entirely (and thus its sub-features)
        if (clsName === "General" &&
          !activeSources.has(featureSource(feat, cls.source))) {
          return;                                        // skip
        }
        const leafs = collectLeafFeatures(feat);
        leafs.forEach((leaf, idx) =>
          row.appendChild(createCard(leaf, cls, true))
        );
      });
    });
  } else {
    // ---- Previous behavior: complete flatten
    const leafs = [];
    branches.forEach(br => br.features.forEach(f => leafs.push(...collectLeafFeatures(f))));
    leafs.forEach((leaf, idx) =>
      row.appendChild(createCard(leaf, cls, false, /* embedSubs = */ false))
    );
  }

}


// --------- Recursive feature collection (robust version) --------
/**
 * Prépare une feature pour l'affichage en clonant et en collectant les enfants.
 * Toujours cloner pour éviter de muterer les originaux du JSON.
 */
function prepareFeatureForDisplay(featObj, nameOverride = null) {
  // Complete clone to avoid any mutation of originals
  const cleaned = JSON.parse(JSON.stringify(featObj));
  
  // Apply name override if provided
  if (nameOverride) {
    cleaned.Name = nameOverride;
  }
  if (!cleaned.Name) {
    cleaned.Name = "(unnamed)";
  }

  // Collect children from arrays of sub-features
  const children = [];
  const displayMeta = cleaned._display || {};

  for (const [key, val] of Object.entries(cleaned)) {
    if (!Array.isArray(val)) continue;
    
    // Check if it's an array of features
    if (!val.every(v => typeof v === "object")) continue;

    // Respect display type (tables vs cards)
    const meta = normalizeDisplayMeta(displayMeta[key]);
    if (meta.type === "table") continue; // Tables stay in object

    // It's an array of sub-features, transform them into children
    if (val.some(v => v.Name || v.Effect)) {
      val.forEach(sub => {
        children.push(prepareFeatureForDisplay(sub));
      });
    }
  }

  if (children.length > 0) {
    cleaned._children = children;
  }

  return cleaned;
}

/**
 * Collects "leaf" features (displayable) from a feature hierarchy.
 */
function collectLeafFeatures(featObj, nameOverride = null) {
  const feature = prepareFeatureForDisplay(featObj, nameOverride);
  
  // If feature has content, return it
  const hasContent = Object.entries(feature).some(([k, v]) => {
    if (k.startsWith('_') || k === 'Name') return false; // Ignore meta
    return v != null;
  });

  if (hasContent) {
    return [feature];
  }

  // Otherwise, return its children (if any)
  return feature._children || [];
}

/* ------------------------------------------------------------------ *
 * Create card - renders a card and recursively its sub-cards
 * ------------------------------------------------------------------ */
function createCard(feat, clsMeta, isGeneral, nested = false) {
  // ----- column container (no Bootstrap column when nested)
  const col = document.createElement("div");
  if (!nested) col.className = "col-md-12";

  // ----- main card
  const card = document.createElement("div");
  card.className = `card ${nested ? "mb-2" : ""} bg-body border shadow-sm overflow-hidden rounded-3`;
  card.dataset.title = feat.Name || "(unnamed)";

  const body = document.createElement("div");
  body.className = "card-body bg-body-secondary";

  // ----- badges
  const showBadges = isGeneral;

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

  // ----- simple fields
  Object.entries(feat).forEach(([k, v]) => {
    if (["Name", "Source", "source", "Category", "_children"].includes(k)) return;
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

  // ----- arrays declared as "table" via _display -----
  const disp = feat._display || {};
  Object.entries(feat).forEach(([k, v]) => {
    if (k.startsWith("_")) return; // Skip metadata keys
    
    // NEW: Handle hierarchical table structure (moveTable, abilityTable, etc.)
    if (typeof v === "object" && v !== null && !Array.isArray(v) && v.groups && Array.isArray(v.groups)) {
      const searchInput = document.getElementById("features-search");
      const q = searchInput ? (searchInput.value || "") : "";
      renderHierarchicalTable(v, k, q, body);
      return;
    }
    
    // LEGACY: Handle flat array tables
    if (!Array.isArray(v)) return;
    const meta = normalizeDisplayMeta(disp[k]);
    if (meta.type !== "table") return;

    // local search applied (same Search input for cards)
    const rootRow = body.closest(".row");
    const searchInput = document.getElementById("features-search");
    const q = searchInput ? (searchInput.value || "") : "";

    renderAsTable(v, k, meta, q, body);
  });

  // ----- nested children only here
  if (feat._children && Array.isArray(feat._children)) {
    feat._children.forEach(child => {
      body.appendChild(createCard(child, clsMeta, isGeneral, true));
    });
  }

  card.appendChild(body);
  col.appendChild(card);
  return col;
}

/* ========== TABLE RENDERING HELPERS ===================================== */

/**
 * Renders a hierarchical table structure with groups (new format)
 * Structure: { columns: [...], groups: [ { label: "...", rows: [...] }, ... ] }
 */
function renderHierarchicalTable(tableObj, title, q, parentEl) {
  if (!tableObj.groups || !Array.isArray(tableObj.groups) || tableObj.groups.length === 0) {
    return;
  }

  // Card + body
  const card = document.createElement("div");
  card.className = "card h-100 bg-body border shadow-sm mb-2 overflow-hidden rounded-3";
  const body = document.createElement("div");
  body.className = "card-body bg-body-secondary";

  // Responsive wrapper
  const wrap = document.createElement("div");
  wrap.className = "table-responsive";

  // Table
  const table = document.createElement("table");
  table.className = "table table-sm table-striped mb-0 items-table";

  const columns = tableObj.columns || [];
  
  // Colgroup with widths
  if (columns.length > 0) {
    const cg = document.createElement("colgroup");
    columns.forEach(() => {
      cg.appendChild(document.createElement("col"));
    });
    table.appendChild(cg);
  }

  // Build table body with groups as sections
  const tbody = document.createElement("tbody");

  tableObj.groups.forEach((group) => {
    const groupLabel = group.label || "Group";
    const groupRows = group.rows || [];

    // Add group label row (spanning all columns)
    const labelRow = document.createElement("tr");
    labelRow.className = "table-group-header";
    const labelCell = document.createElement("td");
    labelCell.colSpan = columns.length || groupRows[0]?.length || 1;
    labelCell.className = "fw-bold bg-light text-muted";
    labelCell.textContent = groupLabel;
    labelRow.appendChild(labelCell);
    tbody.appendChild(labelRow);

    // Add data rows for this group
    groupRows.forEach((rowObj) => {
      // Apply search filter
      if (q) {
        const hay = Object.values(rowObj || {})
          .map(v => (v == null ? "" : String(v).toLowerCase()))
          .join(" ");
        if (!hay.includes(String(q).toLowerCase())) {
          return; // Skip this row
        }
      }

      const tr = document.createElement("tr");
      columns.forEach(colName => {
        const td = document.createElement("td");
        const v = rowObj[colName];
        td.innerHTML = v == null ? "—" : escapeHTML(String(v));
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  });

  table.appendChild(tbody);
  wrap.appendChild(table);
  body.appendChild(wrap);
  card.appendChild(body);
  parentEl.appendChild(card);
}

// Generic detection of best idField if not provided (most distinctive key)
function resolveIdField(preferred, entries) {
  if (preferred && entries.some(e => e && (preferred in e))) return preferred;
  const keyCounts = {};
  entries.forEach(e => {
    if (!e || typeof e !== "object") return;
    Object.keys(e).forEach(k => {
      (keyCounts[k] ??= new Set()).add(e[k]);
    });
  });
  let best = null, maxDistinct = 0;
  Object.entries(keyCounts).forEach(([k, set]) => {
    if (set.size > maxDistinct) { best = k; maxDistinct = set.size; }
  });
  return best;
}

// Normalize display metadata
function normalizeDisplayMeta(raw) {
  if (raw === "table") return { type: "table", rowPerField: true, noheader: false };
  if (raw && typeof raw === "object") {
    return {
      type: raw.type === "table" ? "table" : "cards",
      rowPerField: raw.rowPerField === true,
      idField: raw.idField,
      columns: Array.isArray(raw.columns) ? raw.columns : undefined,
      columnLabels: (raw.columnLabels && typeof raw.columnLabels === "object") ? raw.columnLabels : undefined,
      columnWidths: Array.isArray(raw.columnWidths) ? raw.columnWidths : undefined,
      mergeColumns: raw.mergeColumns === true,
      columnGroupRegex: raw.columnGroupRegex || "^(.*?)(?:_(\\d+))$",
      groupLabels: (raw.groupLabels && typeof raw.groupLabels === "object") ? raw.groupLabels : undefined,
      subHeaders: raw.subHeaders === true,
      noheader: raw.noheader === true            // <--- NOUVEAU
    };
  }
  return { type: "cards" };
}



// Small HTML escape utility (same rules as existing code)
function escapeHTML(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function computeColumnGroups(cols, meta) {
  const rx = new RegExp(meta.columnGroupRegex || COLUMN_GROUP_REGEX.source);
  const groups = [];
  let i = 0;
  while (i < cols.length) {
    const m = String(cols[i]).match(rx);
    const base = (m ? m[1] : cols[i]).trim();
    let span = 1, j = i + 1;
    while (j < cols.length) {
      const m2 = String(cols[j]).match(rx);
      const base2 = (m2 ? m2[1] : cols[j]).trim();
      if (base2 !== base) break;
      span++; j++;
    }
    const label = (meta.groupLabels && meta.groupLabels[base]) || base;
    groups.push({ label, span });
    i = j;
  }
  return groups;
}

function renderAsTable(entries, title, meta, q, parentEl) {
  // Note: computeColumnGroups is defined at global level to avoid duplication

  // Text filtering
  const filtered = entries.filter(obj => {
    if (!q) return true;
    const hay = Object.values(obj || {}).map(v => (v == null ? "" : String(v).toLowerCase())).join(" ");
    return hay.includes(String(q).toLowerCase());
  });
  if (filtered.length === 0) return;

  // Card + body
  const card = document.createElement("div");
  card.className = "card h-100 bg-body border shadow-sm mb-2 overflow-hidden rounded-3";
  const body = document.createElement("div");
  body.className = "card-body bg-body-secondary";

  // Responsive wrapper
  const wrap = document.createElement("div");
  wrap.className = "table-responsive";

  // Table
  const table = document.createElement("table");
  table.className = "table table-sm table-striped mb-0 items-table";
  if (meta.rowPerField) table.classList.add("items-table--transposed");

  // ======================= COLUMNS MODE (rows = items) ==================
  if (!meta.rowPerField) {
    // Determine columns
    let cols;
    if (Array.isArray(meta.columns)) {
      cols = meta.columns.filter(k => filtered.some(e => Object.prototype.hasOwnProperty.call(e, k)));
      // complete with missing keys at end
      const union = new Set();
      filtered.forEach(e => Object.keys(e).forEach(k => union.add(k)));
      [...union].forEach(k => { if (!cols.includes(k)) cols.push(k); });
    } else {
      const union = new Set();
      filtered.forEach(e => Object.keys(e).forEach(k => union.add(k)));
      cols = [...union];
    }

    // Colgroup (optional widths)
    if (Array.isArray(meta.columnWidths) && meta.columnWidths.length) {
      const cg = document.createElement("colgroup");
      cols.forEach((_, i) => {
        const c = document.createElement("col");
        const w = meta.columnWidths[i] || meta.columnWidths[meta.columnWidths.length - 1];
        if (w) c.style.width = w; // ex. '8ch', '120px', '20%'
        cg.appendChild(c);
      });
      table.appendChild(cg);
    }

    // Headers (if not noheader)
    if (!meta.noheader) {
      const thead = document.createElement("thead");

      // Merge headers if requested
      if (meta.mergeColumns) {
        // Row 1: merged groups
        const top = document.createElement("tr");
        computeColumnGroups(cols, meta).forEach(g => {
          const th = document.createElement("th");
          th.textContent = g.label;
          if (g.span > 1) th.colSpan = g.span;
          th.className = "text-center";
          top.appendChild(th);
        });
        thead.appendChild(top);

        // Row 2: sub-headers (optional)
        if (meta.subHeaders) {
          const rx = new RegExp(meta.columnGroupRegex || "^(.*?)(?:_(\\d+))$");
          const sub = document.createElement("tr");
          cols.forEach(k => {
            const th = document.createElement("th");
            const m = String(k).match(rx);
            const label = (meta.columnLabels && meta.columnLabels[k]) || (m && m[2] ? m[2] : k);
            th.textContent = label;
            sub.appendChild(th);
          });
          thead.appendChild(sub);
        }
      } else {
        // Simple header
        const headRow = document.createElement("tr");
        cols.forEach(k => {
          const th = document.createElement("th");
          th.textContent = (meta.columnLabels && meta.columnLabels[k]) || k;
          headRow.appendChild(th);
        });
        thead.appendChild(headRow);
      }
      table.appendChild(thead);
    }

    // Body
    const tbody = document.createElement("tbody");
    filtered.forEach(obj => {
      const tr = document.createElement("tr");
      cols.forEach(k => {
        const td = document.createElement("td");
        const v = obj[k];
        td.innerHTML = v == null ? "—" : escapeHTML(String(v));
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    wrap.appendChild(table);
    body.appendChild(wrap);
    card.appendChild(body);
    parentEl.appendChild(card);
    return;
  }

  // ================== TRANSPOSE MODE (rows = fields, columns = items) ====
  const idField = resolveIdField(meta.idField, filtered);

  // Rows = union of keys (except idField)
  const rowKeys = [];
  const seen = new Set();
  filtered.forEach(e => {
    Object.keys(e).forEach(k => {
      if (k === idField) return;
      if (!seen.has(k)) { seen.add(k); rowKeys.push(k); }
    });
  });

  // Colgroup: first column (labels) wider
  const cg = document.createElement("colgroup");
  const c0 = document.createElement("col"); c0.style.width = "18ch"; cg.appendChild(c0);
  filtered.forEach(() => cg.appendChild(document.createElement("col")));
  table.appendChild(cg);

  // Header (if not noheader)
  if (!meta.noheader) {
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    headRow.appendChild(document.createElement("th")); // empty corner
    filtered.forEach((obj, idx) => {
      const th = document.createElement("th");
      const label = idField && obj[idField] != null ? String(obj[idField]) : `#${idx + 1}`;
      th.textContent = label;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);
  }

  // Body
  const tbody = document.createElement("tbody");
  rowKeys.forEach(k => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.textContent = k;
    tr.appendChild(th);

    filtered.forEach(obj => {
      const td = document.createElement("td");
      const v = obj[k];
      td.innerHTML = v == null ? "—" : escapeHTML(String(v));
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  wrap.appendChild(table);
  body.appendChild(wrap);
  card.appendChild(body);
  parentEl.appendChild(card);
}



// Minimal styles for homogeneous columns + wrap (to put in your global CSS)
(function ensureTableCSS() {
  if (document.getElementById("items-table-css")) return;
  const css = `
  .items-table{table-layout:fixed;width:100%}
  .items-table th,.items-table td{white-space:normal;word-break:break-word;overflow-wrap:anywhere;hyphens:auto;vertical-align:middle}
  .items-table--transposed thead th:first-child,.items-table--transposed tbody th:first-child{width:18ch}
  .items-table tbody tr.table-group-header:hover{background-color:inherit !important}
  .items-table tbody tr.table-group-header td{padding:0.75rem !important}`;
  const style = document.createElement("style");
  style.id = "items-table-css";
  style.textContent = css;
  document.head.appendChild(style);
})();

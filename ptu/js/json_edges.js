// === Edges Viewer — Category-based navigation with dynamic options =====
// Displays categories as clickable buttons. Column and container adjustable.

let edgesData = {};
let activeCategory = null;
let selectedSources = new Set();
let edgeColSize = 4;
let edgeContainer = null;
let _edgeSearchTimeout = null;

export function loadEdges(path, container = document.getElementById("cards-container"), col = 3) {
  fetch(path)
    .then(r => r.json())
    .then(json => {
      edgesData = json;
      edgeContainer = container;
      edgeColSize = Math.floor(12 / col);
      buildCategoryMenu();
      setupGlobalEdgeSearch();
      const defaultCat = "Skill";
      const defaultBtn = [...document.querySelectorAll("#sidebar .list-group-item")].find(btn => btn.textContent === defaultCat);
      if (defaultBtn) {
        defaultBtn.classList.add("active");
        activeCategory = defaultCat;
        renderCategory(defaultCat);
      }
    })
    .catch(err => console.error("JSON load error:", err));
}

// --------- Global edge search setup ------------------------------------------
function setupGlobalEdgeSearch() {
  const searchEl = document.getElementById("filter-search");
  if (!searchEl) return;

  searchEl.addEventListener("input", e => {
    clearTimeout(_edgeSearchTimeout);
    const q = e.target.value.toLowerCase();

    _edgeSearchTimeout = setTimeout(() => {
      if (!q.trim()) {
        // Empty search: redisplay active category
        if (activeCategory) renderCategory(activeCategory);
      } else {
        // Global search
        const results = globalEdgeSearch(q);
        if (results && Object.keys(results).length > 0) {
          renderGlobalEdgeSearchResults(results);
        } else {
          // No results found
          const pane = edgeContainer;
          pane.innerHTML = `<div class="alert alert-info">No edges match "<strong>${escapeHTML(q)}</strong>"</div>`;
        }
      }
    }, 200); // 200ms debounce
  });
}

// --------- Global edge search -----------------------------------
function globalEdgeSearch(query) {
  if (!query) return null;
  
  const q = query.toLowerCase();
  const results = {}; // { category: [edges] }
  
  Object.entries(edgesData).forEach(([edgeName, edge]) => {
    // Check if source is selected
    if (!selectedSources.has(edge.Source || "Unknown")) return;
    
    // Search in name and fields
    const nameMatch = edgeName.toLowerCase().includes(q);
    const descMatch = edge.Description && edge.Description.toLowerCase().includes(q);
    const effectMatch = edge.Effect && edge.Effect.toLowerCase().includes(q);
    
    if (nameMatch || descMatch || effectMatch) {
      const cat = edge.Category || "Misc";
      if (!results[cat]) results[cat] = [];
      results[cat].push({ name: edgeName, ...edge });
    }
  });
  
  return Object.keys(results).length > 0 ? results : null;
}

// --------- Render global search results --------------------------------
function renderGlobalEdgeSearchResults(results) {
  const pane = edgeContainer;
  pane.innerHTML = "";
  
  // Title
  pane.insertAdjacentHTML("afterbegin", 
    `<h2 class="mb-3" style="font-size:1.5rem;">Search Results</h2>`
  );
  
  const row = document.createElement("div");
  row.className = "row g-3";
  pane.appendChild(row);
  
  // Iterate through results and display edges
  Object.entries(results).forEach(([cat, edges]) => {
    edges.forEach(edge => {
      // Wrapper column for context badge + card
      const wrapper = document.createElement("div");
      wrapper.className = `col-12 col-md-${edgeColSize} d-flex flex-column`;
      
      // Source context badge
      const contextBadge = document.createElement("div");
      contextBadge.className = "mb-2";
      contextBadge.innerHTML = `
        <small class="text-muted">
          From <strong>${escapeHTML(cat)}</strong>
          ${edge.Source ? ` • ${escapeHTML(edge.Source)}` : ""}
        </small>
      `;
      wrapper.appendChild(contextBadge);
      
      // Create the card
      const card = document.createElement("div");
      card.className = "card flex-grow-1 bg-body border shadow-sm overflow-hidden rounded-3";
      const body = document.createElement("div");
      body.className = "card-body bg-body-secondary";
      
      // Title with badges
      body.insertAdjacentHTML("beforeend", `
        <h5 class="card-title">
          ${escapeHTML(edge.name)}
          <span class="badge bg-secondary">${escapeHTML(cat)}</span>
          <span class="badge bg-info">${escapeHTML(edge.Source || "Unknown")}</span>
        </h5>
      `);
      
      // All other fields
      Object.entries(edge).forEach(([k, v]) => {
        if (["name", "Category", "Source"].includes(k)) return;
        body.insertAdjacentHTML("beforeend", `<p><strong>${k}:</strong> ${escapeHTML(v.toString()).replaceAll("\n", "<br>")}</p>`);
      });
      
      card.appendChild(body);
      wrapper.appendChild(card);
      row.appendChild(wrapper);
    });
  });
}

// Small HTML escape utility
function escapeHTML(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function buildCategoryMenu() {
  const sb = document.getElementById("sidebar");
  sb.innerHTML = "";

  const categories = new Set();
  const sources = new Set();

  Object.values(edgesData).forEach(e => {
    categories.add(e.Category || "Misc");
    sources.add(e.Source || "Unknown");
  });

  const sourceWrap = document.createElement("div");
  sourceWrap.className = "mb-3";
  sourceWrap.innerHTML = `<label class="form-label">Filter by Source:</label>`;
  [...sources].sort().forEach(src => {
    const id = `filter-src-${src}`;
    sourceWrap.insertAdjacentHTML("beforeend", `
      <div class="form-check">
        <input class="form-check-input" type="checkbox" id="${id}" checked>
        <label class="form-check-label" for="${id}">${escapeHTML(src)}</label>
      </div>`);
    selectedSources.add(src);
  });
  sb.appendChild(sourceWrap);
  sourceWrap.querySelectorAll("input").forEach(cb =>
    cb.addEventListener("change", () => {
      selectedSources.clear();
      sourceWrap.querySelectorAll("input:checked").forEach(cb => selectedSources.add(cb.labels[0].innerText));
      if (activeCategory) renderCategory(activeCategory);
    })
  );

  sb.insertAdjacentHTML("beforeend", `<label class="form-label">Categories:</label>`);
  const catWrap = document.createElement("div");
  catWrap.className = "sidebar-cats";
  sb.appendChild(catWrap);

  [...categories].sort((a, b) => {
    const order = ["Skill", "Crafting", "Pokémon Training", "Combat", "Other"];
    const ai = order.indexOf(a), bi = order.indexOf(b);
    if (ai !== -1 && bi !== -1) return ai - bi;
    if (ai !== -1) return -1;
    if (bi !== -1) return 1;
    return a.localeCompare(b);
  }).forEach(cat => {
    const btn = document.createElement("button");
    btn.className = "list-group-item list-group-item-action";
    btn.textContent = cat;
    btn.addEventListener("click", () => {
      activeCategory = cat;
      document.querySelectorAll("#sidebar .sidebar-cats .list-group-item").forEach(e => e.classList.remove("active"));
      btn.classList.add("active");
      // Clear search when switching categories
      const searchEl = document.getElementById("filter-search");
      if (searchEl) searchEl.value = "";
      renderCategory(cat);
    });
    catWrap.appendChild(btn);
  });
}

function renderCategory(cat) {
  const pane = edgeContainer;
  pane.innerHTML = "";

  const row = document.createElement("div");
  row.className = "row g-3";
  pane.appendChild(row);

  const queryInput = document.getElementById("filter-search");
  const update = () => {
    row.innerHTML = "";
    const q = queryInput.value.toLowerCase();
    Object.entries(edgesData).forEach(([name, e]) => {
      if (e.Category !== cat) return;
      if (!selectedSources.has(e.Source || "Unknown")) return;
      if (
        q &&
        !name.toLowerCase().includes(q) &&
        !(e.Description && e.Description.toLowerCase().includes(q)) &&
        !(e.Effect && e.Effect.toLowerCase().includes(q))
      ) return;

      const col = document.createElement("div");
      col.className = `col-12 col-md-${edgeColSize}`;
      const card = document.createElement("div");
      card.className = "card h-100 bg-body border shadow-sm overflow-hidden rounded-3";
      const body = document.createElement("div");
      body.className = "card-body bg-body-secondary";
      body.insertAdjacentHTML("beforeend", `<h5 class="card-title">${escapeHTML(name)} <span class="badge bg-secondary">${escapeHTML(e.Category)}</span> <span class="badge bg-info">${escapeHTML(e.Source || "Unknown")}</span></h5>`);
      Object.entries(e).forEach(([k, v]) => {
        if (["Category", "Source"].includes(k)) return;
        body.insertAdjacentHTML("beforeend", `<p><strong>${k}:</strong> ${escapeHTML(v.toString()).replaceAll("\n", "<br>")}</p>`);
      });
      card.appendChild(body);
      col.appendChild(card);
      row.appendChild(col);
    });
  };

  if (queryInput) queryInput.addEventListener("input", update);
  update();

  window.scrollTo({ top: 0, behavior: "smooth" });
}

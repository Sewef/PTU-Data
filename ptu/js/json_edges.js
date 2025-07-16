// === Edges Viewer — Mode filtres directs ============================
// Remplace l’arborescence par une simple liste filtrable par Source ou Catégorie

let edgesData = {};
let selectedSources = new Set();
let selectedCategories = new Set();

function loadEdges(path) {
  fetch(path)
    .then(r => r.json())
    .then(json => {
      edgesData = json;
      buildEdgeFilters();
      renderFilteredEdges();
    })
    .catch(err => console.error("JSON load error:", err));
}

function buildEdgeFilters() {
  const sb = document.getElementById("sidebar");
  sb.innerHTML = `<div class="mb-3">
    <input type="text" id="filter-search" class="form-control" placeholder="Search…">
  </div>`;

  document.getElementById("filter-search").addEventListener("input", renderFilteredEdges);

  const sourceSet = new Set();
  const categorySet = new Set();

  Object.values(edgesData).forEach(e => {
    sourceSet.add(e.Source || "Unknown");
    categorySet.add(e.Category || "Misc");
  });

  const addCheckboxFilter = (container, label, prefix, values, stateSet) => {
    const wrap = document.createElement("div");
    wrap.className = "mb-3";
    wrap.innerHTML = `<label class="form-label">${label}:</label>`;
    values.sort().forEach(val => {
      const id = `${prefix}-${val}`;
      wrap.insertAdjacentHTML("beforeend", `
        <div class="form-check">
          <input class="form-check-input" type="checkbox" id="${id}" checked>
          <label class="form-check-label" for="${id}">${val}</label>
        </div>`);
      stateSet.add(val);
    });
    sb.appendChild(wrap);
    wrap.querySelectorAll("input").forEach(cb =>
      cb.addEventListener("change", () => {
        stateSet.clear();
        wrap.querySelectorAll("input:checked").forEach(cb => stateSet.add(cb.labels[0].innerText));
        renderFilteredEdges();
      })
    );
  };

  addCheckboxFilter(sb, "Filter by Source", "src", [...sourceSet], selectedSources);
  addCheckboxFilter(sb, "Filter by Category", "cat", [...categorySet], selectedCategories);
}

function renderFilteredEdges() {
  const pane = document.getElementById("cards-container");
  pane.innerHTML = "";
  const row = document.createElement("div");
  row.className = "row g-3";
  pane.appendChild(row);

  const query = document.getElementById("filter-search").value.toLowerCase();

  Object.entries(edgesData).forEach(([name, e]) => {
    if (!selectedSources.has(e.Source)) return;
    if (!selectedCategories.has(e.Category)) return;
    if (query && !name.toLowerCase().includes(query) && !e.Description.toLowerCase().includes(query)) return;

    const col = document.createElement("div");
    col.className = "col-12 col-md-4";
    const card = document.createElement("div");
    card.className = "card h-100 bg-white border shadow-sm";
    const body = document.createElement("div");
    body.className = "card-body bg-light";
    body.insertAdjacentHTML("beforeend", `<h5 class="card-title">${name} <span class="badge bg-secondary">${e.Category}</span> <span class="badge bg-info">${e.Source}</span></h5>`);
    Object.entries(e).forEach(([k, v]) => {
      if (["Category", "Source"].includes(k)) return;
      body.insertAdjacentHTML("beforeend", `<p><strong>${k}:</strong> ${v.toString().replaceAll("\n", "<br>")}</p>`);
    });
    card.appendChild(body);
    col.appendChild(card);
    row.appendChild(col);
  });

  window.scrollTo({ top: 0, behavior: "smooth" });
}
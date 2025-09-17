// === Edges Viewer — Navigation par catégorie avec options dynamiques ========
// Affiche les catégories comme boutons cliquables. Colonne et container réglables.

let edgesData = {};
let activeCategory = null;
let selectedSources = new Set();
let edgeColSize = 4;
let edgeContainer = null;

function loadEdges(path, container = document.getElementById("cards-container"), col = 3) {
  fetch(path)
    .then(r => r.json())
    .then(json => {
      edgesData = json;
      edgeContainer = container;
      edgeColSize = Math.floor(12 / col);
      buildCategoryMenu();
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
        <label class="form-check-label" for="${id}">${src}</label>
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
  const catList = document.createElement("div");
  catList.className = "list-group";
  [...categories].sort((a, b) => {
    const order = ["Skill", "Crafting", "Pokémon Training", "Combat", "Other"];
    const ai = order.indexOf(a);
    const bi = order.indexOf(b);
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
      document.querySelectorAll("#sidebar .list-group-item").forEach(e => e.classList.remove("active"));
      btn.classList.add("active");
      renderCategory(cat);
    });
    catList.appendChild(btn);
  });
  sb.appendChild(catList);
}

function renderCategory(cat) {
  const pane = edgeContainer;
  pane.innerHTML = "";

  const searchBox = document.createElement("div");
  searchBox.className = "mb-3";
  searchBox.innerHTML = `<input type="text" id="filter-search" class="form-control" placeholder="Search...">`;
  pane.appendChild(searchBox);

  const row = document.createElement("div");
  row.className = "row g-3";
  pane.appendChild(row);

  const queryInput = document.getElementById("filter-search");
  const update = () => {
    row.innerHTML = "";
    const q = queryInput.value.toLowerCase();
    Object.entries(edgesData).forEach(([name, e]) => {
      if (e.Category !== cat) return;
      if (!selectedSources.has(e.Source)) return;
      if (
        q &&
        !name.toLowerCase().includes(q) &&
        !(e.Description && e.Description.toLowerCase().includes(q)) &&
        !(e.Effect && e.Effect.toLowerCase().includes(q))
      ) return;

      const col = document.createElement("div");
      col.className = `col-12 col-md-${edgeColSize}`;
      const card = document.createElement("div");
      card.className = "card h-100 bg-white border shadow-sm overflow-hidden rounded-3";
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
  };

  queryInput.addEventListener("input", update);
  update();

  window.scrollTo({ top: 0, behavior: "smooth" });
}

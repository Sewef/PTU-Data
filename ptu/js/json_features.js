function renderData(data, container, depth = 0) {
    const skipFields = new Set(["Source", "Category"]);

    for (const key in data) {
        if (!data.hasOwnProperty(key)) continue;
        const value = data[key];

        if (skipFields.has(key)) continue;

        if (typeof value === "object" && value !== null) {
            if (!Array.isArray(value)) {
                // Choose heading size based on depth (h5, h6, small)
                const label = document.createElement(depth < 2 ? `h${5 + depth}` : "div");
                label.className = `text-muted mb-2 ${depth >= 2 ? "small fs-6" : ""}`;
                label.textContent = key;
                container.appendChild(label);
            }
            renderData(value, container, depth + 1);
        } else {
            const p = document.createElement("p");
            p.innerHTML = `<strong>${key}:</strong> ${value.replaceAll("\n", "<br>")}`;
            container.appendChild(p);
        }
    }
}

function createCard(title, data, meta) {
    const col = document.createElement("div");
    col.className = "col-md-12 mb-3";

    const card = document.createElement("div");
    card.className = "card h-100";

    const cardBody = document.createElement("div");
    cardBody.className = "card-body";

    const cardTitle = document.createElement("h4");
    cardTitle.className = "card-title";

    const actualCategory = meta?.Category ?? "Unknown";
    const actualSource = data?.Source ?? meta?.Source ?? "Unknown";
    console.log(`Creating card for ${title} with category ${actualCategory} and source ${actualSource}`);

    cardTitle.innerHTML = `${title} 
        <span class="badge bg-secondary">${actualCategory}</span> 
        <span class="badge bg-info">${actualSource}</span>`;

    cardBody.appendChild(cardTitle);
    renderData(data, cardBody);
    card.appendChild(cardBody);
    col.appendChild(card);
    return col;
}

let fullData = {};
let activeSources = new Set();
let activeCategories = new Set();
let currentActiveLink = null;

function loadFeatures(file) {
  fetch(file)
    .then(res => res.json())
    .then(data => {
      fullData = data;
      buildSidebar(fullData);
      // Affiche la première section visible
      const firstVisibleClass = Object.entries(fullData).find(([name, cls]) =>
        activeSources.has(cls.Source || "Unknown") &&
        activeCategories.has(cls.Category || "Other")
      );
      if (firstVisibleClass) {
        const [firstKey] = firstVisibleClass;
        renderSection(firstKey);
        const link = document.querySelector(`[data-section="${firstKey}"]:not([data-subsection])`);
        if (link) setActiveLink(link);
      }
    })
    .catch(err => console.error("Error loading JSON:", err));
}

function buildSidebar(data) {
  const sidebar = document.getElementById("sidebar");
  sidebar.innerHTML = "";

  // === BARRE DE RECHERCHE ===
  const searchInput = document.createElement("input");
  searchInput.type = "text";
  searchInput.className = "form-control mb-2";
  searchInput.placeholder = "Search classes…";
  sidebar.appendChild(searchInput);

  // Collecte des sources et catégories
  const sources = Array.from(new Set(Object.values(data).map(c => c.Source || "Unknown"))).sort();
  const categories = Array.from(new Set(Object.values(data).map(c => c.Category || "Other"))).sort();
  activeSources = new Set(sources);
  activeCategories = new Set(categories);

  // === FILTRES SOURCES ===
  const srcLabel = document.createElement("label");
  srcLabel.className = "form-label mt-2";
  srcLabel.textContent = "Filter by Source:";
  sidebar.appendChild(srcLabel);

  const srcGroup = document.createElement("div");
  srcGroup.className = "d-flex flex-column gap-1 mb-3";
  sources.forEach(src => {
    const id = `filter-source-${src}`;
    const wrapper = document.createElement("div");
    wrapper.className = "form-check";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "form-check-input";
    input.id = id;
    input.checked = true;
    input.addEventListener("change", () => {
      input.checked ? activeSources.add(src) : activeSources.delete(src);
      renderSidebarLinks();
    });

    const label = document.createElement("label");
    label.className = "form-check-label";
    label.htmlFor = id;
    label.textContent = src;

    wrapper.append(input, label);
    srcGroup.appendChild(wrapper);
  });
  sidebar.appendChild(srcGroup);

  // === FILTRES CATÉGORIES ===
  const catLabel = document.createElement("label");
  catLabel.className = "form-label mt-2";
  catLabel.textContent = "Filter by Category:";
  sidebar.appendChild(catLabel);

  const catGroup = document.createElement("div");
  catGroup.className = "d-flex flex-column gap-1 mb-3";
  categories.forEach(cat => {
    const id = `filter-cat-${cat}`;
    const wrapper = document.createElement("div");
    wrapper.className = "form-check";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "form-check-input";
    input.id = id;
    input.checked = true;
    input.addEventListener("change", () => {
      input.checked ? activeCategories.add(cat) : activeCategories.delete(cat);
      renderSidebarLinks();
    });

    const label = document.createElement("label");
    label.className = "form-check-label";
    label.htmlFor = id;
    label.textContent = cat;

    wrapper.append(input, label);
    catGroup.appendChild(wrapper);
  });
  sidebar.appendChild(catGroup);

  // Container pour les liens
  const linkContainer = document.createElement("div");
  sidebar.appendChild(linkContainer);

  // Fonction d’affichage des liens
  function renderSidebarLinks() {
    linkContainer.innerHTML = "";

    // Prépare le grouping
    const byCategory = {};
    let general = null;
    Object.entries(data)
      .sort(([a], [b]) => a === "General" ? -1 : b === "General" ? 1 : a.localeCompare(b))
      .forEach(([name, cls]) => {
        const src = cls.Source || "Unknown";
        const cat = cls.Category || "Other";
        if (name === "General") {
          general = { name, src };
        } else {
          if (!byCategory[cat]) byCategory[cat] = [];
          byCategory[cat].push({ name, src });
        }
      });

    // Affiche General en premier
    if (general && activeSources.has(general.src)) {
      const a = document.createElement("a");
      a.href = "#";
      a.className = "list-group-item list-group-item-action mb-2 d-flex justify-content-between align-items-center";
      a.dataset.section = "General";
      a.innerHTML = `<span>General</span><span class="badge bg-light text-muted">${general.src}</span>`;
      a.addEventListener("click", e => {
        e.preventDefault();
        renderSection("General");
        setActiveLink(a);
      });
      linkContainer.appendChild(a);
    }

    // Pour chaque catégorie
    Object.entries(byCategory).forEach(([cat, list]) => {
      const collapseId = `collapse-${cat.replace(/\s+/g, "-")}`;
      const wrapper = document.createElement("div");
      wrapper.className = "mb-2";

      // Bouton de catégorie
      const btn = document.createElement("button");
      btn.className = "btn btn-sm btn-light w-100 text-start collapsed";
      btn.setAttribute("data-bs-toggle", "collapse");
      btn.setAttribute("data-bs-target", `#${collapseId}`);
      btn.textContent = `📁 ${cat}`;
      wrapper.appendChild(btn);

      // Contenu repliable
      const collapse = document.createElement("div");
      collapse.className = "collapse";
      collapse.id = collapseId;

      list.sort((a, b) => a.name.localeCompare(b.name)).forEach(({ name, src }) => {
        if (!activeSources.has(src) || !activeCategories.has(cat)) return;
        const link = document.createElement("a");
        link.href = "#";
        link.className = "list-group-item list-group-item-action ps-3 d-flex justify-content-between align-items-center";
        link.dataset.section = name;
        link.innerHTML = `<span>${name}</span><span class="badge bg-light text-muted">${src}</span>`;
        link.addEventListener("click", e => {
          e.preventDefault();
          renderSection(name);
          setActiveLink(link);
        });
        collapse.appendChild(link);
      });

      wrapper.appendChild(collapse);
      linkContainer.appendChild(wrapper);
    });

    // Init collapse toggles (Bootstrap)
    setTimeout(() => {
      document.querySelectorAll('[data-bs-toggle="collapse"]').forEach(toggle => {
        const target = document.querySelector(toggle.getAttribute("data-bs-target"));
        const tri = toggle.querySelector(".triangle-toggle");
        if (!target) return;
        const inst = bootstrap.Collapse.getOrCreateInstance(target, { toggle: false });
        // Synchronise l’état du triangle si vous l’utilisez
        if (tri) {
          tri.classList.toggle("open", target.classList.contains("show"));
          target.addEventListener("show.bs.collapse", () => tri.classList.add("open"));
          target.addEventListener("hide.bs.collapse", () => tri.classList.remove("open"));
        }
      });
    }, 0);
  }

  // Recherche texte
  searchInput.addEventListener("input", () => {
    const q = searchInput.value.toLowerCase();
    document.querySelectorAll("#sidebar a.list-group-item").forEach(a => {
      a.style.display = a.textContent.toLowerCase().includes(q) ? "" : "none";
    });
  });

  // Premier rendu
  renderSidebarLinks();
}


// ───── RENDER SECTION ─────
function renderSection(sectionTitle, subSection = null) {
    const container = document.getElementById("cards-container");
    container.innerHTML = "";

    const section = fullData[sectionTitle];
    if (!section || !section.Features) return;

    // Titre
    const heading = document.createElement("h2");
    heading.className = "mb-4 mt-3";
    heading.textContent = subSection || sectionTitle;
    container.appendChild(heading);

    // Search bar
    const searchDiv = document.createElement("div");
    searchDiv.className = "mb-3";
    const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.placeholder = "Search features…";
    searchInput.className = "form-control";
    searchDiv.appendChild(searchInput);
    container.appendChild(searchDiv);

    // Row container
    const row = document.createElement("div");
    row.className = "row g-3";
    container.appendChild(row);

    const alwaysBadges = sectionTitle === "General";
    let firstBadge = true;

    const features = subSection
        ? { [subSection]: section.Features[subSection] }
        : section.Features;

    Object.entries(features).forEach(([featKey, featVal]) => {
        // Cas « branché » : on a un objet dont la clé sectionTitle contient les sous-features
        if (featVal[sectionTitle] && typeof featVal[sectionTitle] === "object") {
            const branchData = featVal[sectionTitle];

            // *** On NE crée PLUS la carte principale pour les sections à une seule branche ***
            const isSingleBranchSection =
                Object.keys(section.Features).length === 1;

            // Parcours des sous-features
            Object.entries(branchData).forEach(([subKey, subVal]) => {
                if (typeof subVal === "object") {
                    // injecte Source/Category si manquants
                    const data = { ...subVal };
                    if (!data.Source) data.Source = featVal.Source || section.Source;
                    if (!data.Category) data.Category = section.Category;

                    // badge uniquement sur la première ou toujours si General
                    const showBadge = alwaysBadges || firstBadge;
                    row.appendChild(createCard(subKey, data, section, showBadge));
                    firstBadge = false;
                }
            });
        } else {
            // feature simple (pas de branche)
            const showBadge = alwaysBadges || firstBadge;
            row.appendChild(createCard(featKey, featVal, section, showBadge));
            firstBadge = false;
        }
    });

    // Recherche
    searchInput.addEventListener("input", () => {
        const q = searchInput.value.toLowerCase();
        row.childNodes.forEach(col => {
            const title = col.querySelector(".card-title")?.textContent.toLowerCase() || "";
            col.style.display = title.includes(q) ? "" : "none";
        });
    });

    window.scrollTo({ top: 0, behavior: "smooth" });
}



// ───── CREATE CARD ─────
function createCard(title, data, meta, showBadges) {
    const col = document.createElement("div");
    col.className = "col-md-12 mb-3";

    const card = document.createElement("div");
    card.className = "card h-100";

    const body = document.createElement("div");
    body.className = "card-body";

    // titre + badges
    const h4 = document.createElement("h4");
    h4.className = "card-title";
    let html = title;
    if (showBadges) {
        const cat = data.Category || meta.Category;
        const src = data.Source || meta.Source;
        if (cat && cat !== "Unknown") html += ` <span class="badge bg-secondary">${cat}</span>`;
        if (src) html += ` <span class="badge bg-info">${src}</span>`;
    }
    h4.innerHTML = html;
    body.appendChild(h4);

    // contenu
    renderData(data, body, 0);

    card.appendChild(body);
    col.appendChild(card);
    return col;
}

function setActiveLink(link) {
    if (currentActiveLink) {
        currentActiveLink.classList.remove("active");
    }
    link.classList.add("active");
    currentActiveLink = link;
}
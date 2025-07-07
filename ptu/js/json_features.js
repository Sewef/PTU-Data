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

// en haut de ton script
let sidebarData = {};      // contiendra les features
let activeSources = new Set();
let linkContainer = null;  // on le créera dans buildSidebar
let fullData = {};
let currentActiveLink = null;
let activeCategories = new Set();

function loadFeatures(file) {
    fetch(file)
        .then(response => response.json())
        .then(jsonData => {
            fullData = jsonData;

            buildSidebar(jsonData);
            // Render first visible section
            // Trouver la première classe dont la source ET la catégorie sont visibles
            const firstVisibleClass = Object.entries(jsonData).find(([className, cls]) =>
                activeSources.has(cls.Source ?? "Unknown") &&
                activeCategories.has(cls.Category ?? "Other")
            );

            const firstKey = firstVisibleClass?.[0];
            if (firstKey) {
                renderSection(firstKey);
                const sidebarLink = document.querySelector(`[data-section="${firstKey}"]:not([data-subsection])`);
                if (sidebarLink) setActiveLink(sidebarLink);
            }

        })
        .catch(err => console.error("Error loading JSON:", err));
}


function buildSidebar(data) {
    // on « globalise » data
    sidebarData = data;

    const sidebar = document.getElementById("sidebar");
    sidebar.innerHTML = "";

    // === CHAMP DE RECHERCHE ===
    const searchWrapper = document.createElement("div");
    searchWrapper.className = "mb-3";
    searchWrapper.innerHTML = `
      <input
        type="text"
        id="sidebar-search"
        class="form-control"
        placeholder="Rechercher..."
      >
    `;
    sidebar.appendChild(searchWrapper);

    const searchInput = document.getElementById("sidebar-search");
    // on rafraîchit à chaque frappe
    searchInput.addEventListener("input", renderSidebarLinks);

    // === SOURCE FILTERS ===
    const sources = Array.from(
        new Set(Object.values(sidebarData).map(e => e.Source || "Unknown"))
    ).sort();
    activeSources = new Set(sources);

    const srcTitle = document.createElement("label");
    srcTitle.className = "form-label mt-2";
    srcTitle.textContent = "Filter by Source:";
    sidebar.appendChild(srcTitle);

    const srcFilterGroup = document.createElement("div");
    srcFilterGroup.className = "mb-3 d-flex flex-column gap-1";
    sidebar.appendChild(srcFilterGroup);

    sources.forEach(src => {
        const id = `filter-source-${src}`;
        srcFilterGroup.innerHTML += `
            <div class="form-check">
              <input class="form-check-input" type="checkbox" id="${id}" checked>
              <label class="form-check-label" for="${id}">${src}</label>
            </div>`;
    });

    // Re-bind des filtres source
    sidebar.querySelectorAll('input[type="checkbox"]').forEach(cb =>
        cb.addEventListener("change", () => {
          // 1) met à jour la sidebar
          renderSidebarLinks();
          // 2) si on a déjà une section active, on la rerender
          if (currentActiveLink) {
            const sec = currentActiveLink.dataset.section;
            const sub = currentActiveLink.dataset.subsection || null;
            renderSection(sec, sub);
          }
        })
      );

    // création du conteneur de liens
    linkContainer = document.createElement("div");
    sidebar.appendChild(linkContainer);

    // première passe
    renderSidebarLinks();
}

function renderSidebarLinks() {
    // 1) Mise à jour des sources cochées
    activeSources.clear();
    document.querySelectorAll('input[type="checkbox"][id^="filter-source-"]')
        .forEach(cb => {
            if (cb.checked) {
                activeSources.add(cb.id.replace("filter-source-", ""));
            }
        });

    // 2) Texte de recherche
    const searchQuery = document
        .getElementById("sidebar-search")
        .value
        .trim()
        .toLowerCase();

    // 3) Sauvegarde des panels ouverts
    const openCatIds = Array.from(
        document.querySelectorAll('.collapse.show')
    ).map(el => el.id);

    // 4) Vide le container de liens
    linkContainer.innerHTML = "";

    // 5) Regroupement & ordre (General + catégories)
    const classesByCategory = {};
    let generalEntry = null;
    const orderedEntries = Object.entries(sidebarData).sort(([a], [b]) => {
        if (a === "General") return -1;
        if (b === "General") return 1;
        return a.localeCompare(b);
    });

    orderedEntries.forEach(([className, cls]) => {
        const src = cls.Source || "Unknown";
        const cat = cls.Category || "Other";
        if (className === "General") {
            generalEntry = { className, cls, source: src };
        } else {
            if (!classesByCategory[cat]) classesByCategory[cat] = [];
            classesByCategory[cat].push({ className, cls, source: src });
        }
    });

    // 6) Afficher « General » si ok
    linkContainer.appendChild(
        createLinkItem(
            generalEntry.className,
            generalEntry.source,
            3,                          // indentation de niveau 3 (comme les autres)
            { section: generalEntry.className }  // <-- on passe bien section="General"
        )
    );


    // 7) Parcours des catégories
    Object.entries(classesByCategory).forEach(([category, list]) => {
        const collapseId = `collapse-cat-${category.replace(/\s+/g, "-")}`;
        const wrapper = document.createElement("div");
        wrapper.className = "mb-2";

        // bouton category
        const catBtn = document.createElement("button");
        catBtn.className = "btn btn-sm btn-light w-100 text-start collapse-toggle collapsed";
        catBtn.setAttribute("data-bs-toggle", "collapse");
        catBtn.setAttribute("data-bs-target", `#${collapseId}`);
        catBtn.setAttribute("aria-expanded", "false");
        catBtn.textContent = `📁 ${category}`;
        wrapper.appendChild(catBtn);

        const catCollapse = document.createElement("div");
        catCollapse.className = "collapse";
        catCollapse.id = collapseId;

        list.sort((a, b) => a.className.localeCompare(b.className))
            .forEach(({ className, cls, source }) => {

                const featureKeys = Object.keys(cls.Features);
                const hasBranches = featureKeys.some(k =>
                    typeof cls.Features[k] === "object" &&
                    cls.Features[k][className]
                );

                if (hasBranches) {
                    // parent + branches
                    const branchWrapper = document.createElement("div");
                    branchWrapper.className = "list-group";

                    // toggle parent
                    const parentToggle = document.createElement("a");
                    parentToggle.href = "#";
                    parentToggle.className = "list-group-item list-group-item-action ps-3 d-flex justify-content-between align-items-center";
                    parentToggle.dataset.bsToggle = "collapse";
                    parentToggle.dataset.bsTarget = `#collapse-${className.replace(/\s+/g, "-")}`;
                    parentToggle.setAttribute("aria-expanded", "false");

                    const labelSpan = document.createElement("span");
                    labelSpan.className = "d-flex justify-content-between align-items-center w-100";
                    labelSpan.innerHTML = `
                  <span>${className}</span>
                  <span class="badge bg-light text-muted ms-auto">${source}</span>
                `;
                    const triangleSpan = document.createElement("span");
                    triangleSpan.className = "triangle-toggle ms-auto";

                    parentToggle.append(labelSpan, triangleSpan);

                    const branchCollapse = document.createElement("div");
                    branchCollapse.className = "collapse";
                    branchCollapse.id = `collapse-${className.replace(/\s+/g, "-")}`;

                    let visibleBranches = 0;
                    featureKeys.forEach(branch => {
                        const branchObj = cls.Features[branch];
                        if (
                            typeof branchObj === "object" &&
                            branchObj[className]
                        ) {
                            const branchData = branchObj[className];
                            const branchSource = branchData.Source || source;
                            const txt = branch.toLowerCase();

                            if (
                                activeSources.has(branchSource) &&
                                (!searchQuery ||
                                    txt.includes(searchQuery) ||
                                    className.toLowerCase().includes(searchQuery))
                            ) {
                                visibleBranches++;
                                const link = createLinkItem(
                                    branch,
                                    branchSource,
                                    4,
                                    { section: className, subsection: branch }
                                );
                                branchCollapse.appendChild(link);
                            }
                        }
                    });

                    if (visibleBranches > 0) {
                        branchWrapper.append(parentToggle, branchCollapse);
                        catCollapse.appendChild(branchWrapper);
                    }

                } else {
                    // classe simple
                    const txt = className.toLowerCase();
                    if (
                        activeSources.has(source) &&
                        (!searchQuery || txt.includes(searchQuery))
                    ) {
                        const link = createLinkItem(
                            className,
                            source,
                            3,
                            { section: className }
                        );
                        catCollapse.appendChild(link);
                    }
                }
            });

        // **NOUVEAU** : n'appendre wrapper que si on a des liens à l’intérieur
        if (catCollapse.children.length > 0) {
            wrapper.appendChild(catCollapse);
            linkContainer.appendChild(wrapper);
        }
    });

    // 8) Sync Bootstrap et réouverture
    setTimeout(syncCollapses, 0);
}

function createLinkItem(label, src, psLevel = 3, data = {}) {
    if (!data.section) data.section = label;
    const link = document.createElement("a");
    link.href = "#";
    link.className = `list-group-item list-group-item-action ps-${psLevel} d-flex justify-content-between align-items-center`;
    link.innerHTML = `
      <span>${label}</span>
      <!-- badge avec text-truncate et tooltip -->
      <span
        class="badge bg-light text-muted ms-auto text-truncate"
        style="max-width: 10rem;"
        title="${src}"
      >
        ${src}
      </span>
    `;
    Object.entries(data).forEach(([k, v]) => link.dataset[k] = v);
    link.addEventListener("click", e => {
        e.preventDefault();
        renderSection(data.section, data.subsection);
        setActiveLink(link);
    });
    return link;
}


function syncCollapses() {
    const openCatIds = Array.from(
        document.querySelectorAll('.collapse.show')
    ).map(el => el.id);
    document.querySelectorAll('[data-bs-toggle="collapse"]').forEach(toggle => {
        const target = document.querySelector(toggle.dataset.bsTarget);
        const triangle = toggle.querySelector(".triangle-toggle");
        if (!target || !triangle) return;
        const inst = bootstrap.Collapse.getOrCreateInstance(target, { toggle: false });
        triangle.classList.toggle("open", target.classList.contains("show"));
        target.addEventListener("show.bs.collapse", () => triangle.classList.add("open"));
        target.addEventListener("hide.bs.collapse", () => triangle.classList.remove("open"));
    });
    openCatIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) bootstrap.Collapse.getOrCreateInstance(el).show();
    });
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
        // ------> récupération de la source effective de la feature
        const featSource = featVal.Source || section.Source;
        // si cette source n'est pas active dans la sidebar, on skip
        if (!activeSources.has(featSource)) return;

        // Cas « branché » : on a un objet dont la clé sectionTitle contient les sous-features
        if (featVal[sectionTitle] && typeof featVal[sectionTitle] === "object") {
            const branchData = featVal[sectionTitle];

            // *** On NE crée PLUS la carte principale pour les sections à une seule branche ***
            const isSingleBranchSection =
                Object.keys(section.Features).length === 1;

            // Parcours des sous-features
            Object.entries(branchData).forEach(([subKey, subVal]) => {
                const subSource = subVal.Source || featVal.Source || section.Source;
                if (!activeSources.has(subSource)) return;
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
function createCard(title, data, meta, showBadges = true) {
    const col = document.createElement("div");
    col.className = "col-md-12 mb-3";

    const card = document.createElement("div");
    card.className = "card h-100 bg-white border shadow-sm";

    const body = document.createElement("div");
    body.className = "card-body bg-light";

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
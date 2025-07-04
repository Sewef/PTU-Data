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
let currentActiveLink = null;
let activeSources = new Set();
let activeCategories = new Set();

function loadFeatures(file) {
    fetch(file)
        .then(response => response.json())
        .then(jsonData => {
            fullData = jsonData;

            const sidebar = document.getElementById("sidebar");
            sidebar.innerHTML = "";

            // === SEARCH BAR ===
            /* const searchInput = document.createElement("input");
            searchInput.type = "text";
            searchInput.className = "form-control mb-2";
            searchInput.placeholder = "Search classes...";
            sidebar.appendChild(searchInput); */

            // === FILTERS ===
            const sources = new Set();
            const categories = new Set();
            for (const cls of Object.values(jsonData)) {
                sources.add(cls.Source ?? "Unknown");
                categories.add(cls.Category ?? "Other");
            }

            activeSources = new Set(sources);
            activeCategories = new Set(categories);

            const filterContainer = document.createElement("div");
            filterContainer.className = "mb-3";

            filterContainer.innerHTML = `
              <label class="form-label">Filter by Source:</label>
              <div class="d-flex flex-wrap gap-2 mb-2" id="source-filters"></div>
              <label class="form-label mt-2">Filter by Category:</label>
              <div class="d-flex flex-wrap gap-2" id="category-filters"></div>
            `;
            sidebar.appendChild(filterContainer);

            // Source Filters
            const srcDiv = filterContainer.querySelector("#source-filters");
            sources.forEach(src => {
                const id = `filter-src-${src}`;
                srcDiv.innerHTML += `
                  <div class="form-check">
                    <input class="form-check-input" type="checkbox" id="${id}" checked>
                    <label class="form-check-label" for="${id}">${src}</label>
                  </div>`;
            });

            // Category Filters
            const catDiv = filterContainer.querySelector("#category-filters");
            categories.forEach(cat => {
                const id = `filter-cat-${cat}`;
                catDiv.innerHTML += `
                  <div class="form-check">
                    <input class="form-check-input" type="checkbox" id="${id}" checked>
                    <label class="form-check-label" for="${id}">${cat}</label>
                  </div>`;
            });

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
    const sidebar = document.getElementById("sidebar");
    sidebar.innerHTML = "";

    // === SEARCH BAR ===
    /* const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.className = "form-control mb-2";
    searchInput.placeholder = "Search classes...";
    sidebar.appendChild(searchInput); */

    // === SOURCE FILTERS ===
    const sources = Array.from(new Set(Object.values(data).map(e => e.Source || "Unknown"))).sort();
    activeSources = new Set(sources);

    const srcTitle = document.createElement("label");
    srcTitle.className = "form-label mt-2";
    srcTitle.textContent = "Filter by Source:";
    sidebar.appendChild(srcTitle);

    const srcFilterGroup = document.createElement("div");
    srcFilterGroup.className = "mb-3 d-flex flex-column gap-1";
    sources.forEach(src => {
        const id = `filter-source-${src}`;
        const wrapper = document.createElement("div");
        wrapper.className = "form-check";

        const input = document.createElement("input");
        input.type = "checkbox";
        input.className = "form-check-input";
        input.id = id;
        input.checked = true;

        const label = document.createElement("label");
        label.className = "form-check-label";
        label.htmlFor = id;
        label.textContent = src;

        input.addEventListener("change", () => {
            if (input.checked) activeSources.add(src);
            else activeSources.delete(src);
            renderSidebarLinks();
        });

        wrapper.appendChild(input);
        wrapper.appendChild(label);
        srcFilterGroup.appendChild(wrapper);
    });
    sidebar.appendChild(srcFilterGroup);

    const linkContainer = document.createElement("div");
    sidebar.appendChild(linkContainer);

    function renderSidebarLinks() {

        // SECTION SPÉCIALE POUR LA CLASSE "General"

        // Grouper les classes par catégorie
        const classesByCategory = {};
        let generalEntry = null;

        // Trier les classes, General d'abord
        const orderedEntries = Object.entries(data).sort(([aName], [bName]) => {
            if (aName === "General") return -1;
            if (bName === "General") return 1;
            return aName.localeCompare(bName);
        });

        for (const [className, cls] of orderedEntries) {
            const source = cls.Source || "Unknown";
            const category = cls.Category || "Other";

            if (className === "General") {
                generalEntry = { className, cls, source };
                continue;
            }

            if (!classesByCategory[category]) classesByCategory[category] = [];
            classesByCategory[category].push({ className, cls, source });
        }
        if (generalEntry && activeSources.has(generalEntry.source)) {
            const link = document.createElement("a");
            link.href = "#";
            link.className = "list-group-item list-group-item-action ps-3 mb-2 d-flex justify-content-between align-items-center";
            link.dataset.section = generalEntry.className;
            link.innerHTML = `
                <span>${generalEntry.className}</span>
                <span class="badge bg-light text-muted ms-auto">${generalEntry.source}</span>
            `;
            link.addEventListener("click", e => {
                e.preventDefault();
                renderSection(generalEntry.className);
                setActiveLink(link);
            });
            linkContainer.appendChild(link);
        }


        // Pour chaque catégorie
        for (const [category, classList] of Object.entries(classesByCategory)) {
            const collapseId = `collapse-cat-${category.replace(/\s+/g, "-")}`;

            const wrapper = document.createElement("div");
            wrapper.className = "mb-2";

            // === Titre de la catégorie (cliquable)
            const catBtn = document.createElement("button");
            catBtn.className = "btn btn-sm btn-light w-100 text-start collapse-toggle collapsed";
            catBtn.setAttribute("data-bs-toggle", "collapse");
            catBtn.setAttribute("data-bs-target", `#${collapseId}`);
            catBtn.setAttribute("aria-expanded", "false");
            catBtn.innerHTML = `📁 ${category}`;
            wrapper.appendChild(catBtn);

            // === Contenu repliable
            const catCollapse = document.createElement("div");
            catCollapse.className = "collapse";
            catCollapse.id = collapseId;

            // === Pour chaque classe de cette catégorie
            classList.sort((a, b) => a.className.localeCompare(b.className)).forEach(({ className, cls, source }) => {
                if (!activeSources.has(source)) return;

                const featureKeys = Object.keys(cls.Features);
                const hasBranches = featureKeys.some(k =>
                    typeof cls.Features[k] === "object" &&
                    cls.Features[k][className]
                );

                if (hasBranches) {
                    const collapseId = `collapse-${className.replace(/\s+/g, "-")}`;
                    const branchWrapper = document.createElement("div");
                    branchWrapper.className = "list-group"; // pour éviter un espacement supplémentaire


                    const parentToggle = document.createElement("a");
                    parentToggle.href = "#";
                    parentToggle.className = "list-group-item list-group-item-action ps-3 d-flex justify-content-between align-items-center";
                    parentToggle.dataset.section = className;
                    parentToggle.dataset.bsToggle = "collapse";
                    parentToggle.dataset.bsTarget = `#${collapseId}`;
                    parentToggle.setAttribute("aria-expanded", "false");
                    parentToggle.setAttribute("aria-controls", collapseId);

                    const labelSpan = document.createElement("span");
                    labelSpan.innerHTML = `
                    <span>${className}</span>
                    <span class="badge bg-light text-muted ms-auto">${source}</span>
                    `;
                    labelSpan.className = "d-flex justify-content-between align-items-center w-100";


                    const triangleSpan = document.createElement("span");
                    triangleSpan.className = "triangle-toggle ms-auto"; // ms-auto pour le pousser à droite
                    parentToggle.appendChild(triangleSpan);


                    parentToggle.appendChild(labelSpan);
                    parentToggle.appendChild(triangleSpan);

                    parentToggle.addEventListener("click", e => {
                        // Ne pas empêcher le collapse natif de Bootstrap
                        if (!e.target.closest("span:first-child")) return;
                        e.preventDefault();
                        renderSection(className);
                        setActiveLink(parentToggle);
                    });


                    parentToggle.addEventListener("click", e => {
                        if (!e.target.closest("span:first-child")) return;
                        e.preventDefault();
                        renderSection(className);
                        setActiveLink(parentToggle);
                    });

                    const collapse = document.createElement("div");
                    collapse.className = "collapse";
                    collapse.id = collapseId;

                    for (const branch of featureKeys) {
                        const branchObj = cls.Features[branch];
                        if (
                            typeof branchObj === "object" &&
                            branchObj[className]
                        ) {
                            const link = document.createElement("a");
                            link.href = "#";
                            link.className = "list-group-item list-group-item-action ps-4";
                            const branchData = branchObj[className];
                            const branchSource = branchData?.Source || source; // fallback sur classe
                            link.innerHTML = `
                            <span>${branch}</span>
                            <span class="badge bg-light text-muted ms-auto">${branchSource}</span>
                            `;
                            link.classList.add("d-flex", "justify-content-between", "align-items-center");

                            link.dataset.section = className;
                            link.dataset.subsection = branch;

                            link.addEventListener("click", e => {
                                e.preventDefault();
                                renderSection(className, branch);
                                setActiveLink(link);
                            });

                            collapse.appendChild(link);
                        }
                    }

                    branchWrapper.appendChild(parentToggle);
                    branchWrapper.appendChild(collapse);
                    catCollapse.appendChild(branchWrapper);

                } else {
                    // Classe simple
                    const link = document.createElement("a");
                    link.href = "#";
                    link.className = "list-group-item list-group-item-action ps-3";
                    link.innerHTML = `
                    <span>${className}</span>
                    <span class="badge bg-light text-muted ms-auto">${source}</span>
                    `;
                    link.classList.add("d-flex", "justify-content-between", "align-items-center");
                    link.dataset.section = className;
                    link.addEventListener("click", e => {
                        e.preventDefault();
                        renderSection(className);
                        setActiveLink(link);
                    });
                    catCollapse.appendChild(link);
                }
            });

            wrapper.appendChild(catCollapse);
            linkContainer.appendChild(wrapper);
        }

        setTimeout(() => {
            document.querySelectorAll('[data-bs-toggle="collapse"]').forEach(toggle => {
                const targetSelector = toggle.getAttribute("data-bs-target") || toggle.getAttribute("href");
                const target = document.querySelector(targetSelector);
                const triangle = toggle.querySelector(".triangle-toggle");

                if (!target || !triangle) return;

                const collapse = bootstrap.Collapse.getOrCreateInstance(target, { toggle: false });

                // Synchroniser l’état initial
                triangle.classList.toggle("open", target.classList.contains("show"));

                // Gérer les événements Bootstrap
                target.addEventListener("show.bs.collapse", () => triangle.classList.add("open"));
                target.addEventListener("hide.bs.collapse", () => triangle.classList.remove("open"));
            });
        }, 0);


    }

    // === RECHERCHE ===
    /* searchInput.addEventListener("input", () => {
        const query = searchInput.value.toLowerCase();
        const links = linkContainer.querySelectorAll("a.list-group-item");
        links.forEach(link => {
            const text = link.textContent.toLowerCase();
            link.style.display = text.includes(query) ? "" : "none";
        });
    }); */

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
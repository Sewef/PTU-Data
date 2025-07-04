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

    // === SOURCE FILTERS ===
    const sources = Array.from(new Set(Object.values(data).map(e => e.Source || "Unknown"))).sort();
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

    // === CATEGORY FILTERS ===
    /* const categories = Array.from(new Set(Object.values(data).map(e => e.Category || "Other"))).sort();
    activeCategories = new Set(categories);

    const catTitle = document.createElement("label");
    catTitle.className = "form-label mt-2";
    catTitle.textContent = "Filter by Category:";
    sidebar.appendChild(catTitle);

    const catFilterGroup = document.createElement("div");
    catFilterGroup.className = "mb-3 d-flex flex-column gap-1";
    sidebar.appendChild(catFilterGroup);

    categories.forEach(cat => {
        const id = `filter-cat-${cat}`;
        catFilterGroup.innerHTML += `
            <div class="form-check">
              <input class="form-check-input" type="checkbox" id="${id}" checked>
              <label class="form-check-label" for="${id}">${cat}</label>
            </div>`;
    }); */

    const linkContainer = document.createElement("div");
    sidebar.appendChild(linkContainer);

    // on rattache renderSidebarLinks à TOUTES les cases
    sidebar.querySelectorAll('input[type="checkbox"]').forEach(input => {
        input.addEventListener("change", renderSidebarLinks);
    });

    function renderSidebarLinks() {
        // Récupérer et mettre à jour les sources actives
        activeSources.clear();
        sources.forEach(src => {
            const cb = document.getElementById(`filter-source-${src}`);
            if (cb && cb.checked) activeSources.add(src);
        });
    
        // Sauvegarder les catégories ouvertes pour les réouvrir après
        const openCatIds = Array.from(
            document.querySelectorAll('.collapse.show')
        ).map(el => el.id);
    
        // Vider le conteneur de liens
        linkContainer.innerHTML = "";
    
        // Grouper les classes par catégorie, en isolant "General"
        const classesByCategory = {};
        let generalEntry = null;
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
            } else {
                if (!classesByCategory[category]) classesByCategory[category] = [];
                classesByCategory[category].push({ className, cls, source });
            }
        }
    
        // Afficher "General" en premier, si coché
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
    
        // Parcourir chaque catégorie
        for (const [category, classList] of Object.entries(classesByCategory)) {
            const collapseId = `collapse-cat-${category.replace(/\s+/g, "-")}`;
            const wrapper = document.createElement("div");
            wrapper.className = "mb-2";
    
            // Bouton pour ouvrir/fermer la catégorie
            const catBtn = document.createElement("button");
            catBtn.className = "btn btn-sm btn-light w-100 text-start collapse-toggle collapsed";
            catBtn.setAttribute("data-bs-toggle", "collapse");
            catBtn.setAttribute("data-bs-target", `#${collapseId}`);
            catBtn.setAttribute("aria-expanded", "false");
            catBtn.innerHTML = `📁 ${category}`;
            wrapper.appendChild(catBtn);
    
            // Conteneur repliable
            const catCollapse = document.createElement("div");
            catCollapse.className = "collapse";
            catCollapse.id = collapseId;
    
            // Pour chaque classe de la catégorie
            classList
                .sort((a, b) => a.className.localeCompare(b.className))
                .forEach(({ className, cls, source }) => {
                    // Si la classe parent n'est pas cochée, on peut tout de même checker ses branches
                    const featureKeys = Object.keys(cls.Features);
                    const hasBranches = featureKeys.some(k =>
                        typeof cls.Features[k] === "object" &&
                        cls.Features[k][className]
                    );
    
                    if (hasBranches) {
                        // On va construire les branches visibles
                        const branchWrapper = document.createElement("div");
                        branchWrapper.className = "list-group";
    
                        // Toggle du parent
                        const parentToggle = document.createElement("a");
                        parentToggle.href = "#";
                        parentToggle.className = "list-group-item list-group-item-action ps-3 d-flex justify-content-between align-items-center";
                        parentToggle.dataset.bsToggle = "collapse";
                        parentToggle.dataset.bsTarget = `#collapse-${className.replace(/\s+/g, "-")}`;
                        parentToggle.setAttribute("aria-expanded", "false");
    
                        const labelSpan = document.createElement("span");
                        labelSpan.innerHTML = `
                            <span>${className}</span>
                            <span class="badge bg-light text-muted ms-auto">${source}</span>
                        `;
                        labelSpan.className = "d-flex justify-content-between align-items-center w-100";
    
                        const triangleSpan = document.createElement("span");
                        triangleSpan.className = "triangle-toggle ms-auto";
    
                        parentToggle.appendChild(labelSpan);
                        parentToggle.appendChild(triangleSpan);
    
                        // Conteneur repliable des branches
                        const collapse = document.createElement("div");
                        collapse.className = "collapse";
                        collapse.id = `collapse-${className.replace(/\s+/g, "-")}`;
    
                        let visibleBranchCount = 0;
                        // Pour chaque branche de la classe
                        featureKeys.forEach(branch => {
                            const branchObj = cls.Features[branch];
                            if (
                                typeof branchObj === "object" &&
                                branchObj[className]
                            ) {
                                const branchData = branchObj[className];
                                const branchSource = branchData.Source || source;
                                // Filtrer la branche selon sa source
                                if (!activeSources.has(branchSource)) return;
                                visibleBranchCount++;
    
                                const link = document.createElement("a");
                                link.href = "#";
                                link.className = "list-group-item list-group-item-action ps-4 d-flex justify-content-between align-items-center";
                                link.dataset.section = className;
                                link.dataset.subsection = branch;
                                link.innerHTML = `
                                    <span>${branch}</span>
                                    <span class="badge bg-light text-muted ms-auto">${branchSource}</span>
                                `;
                                link.addEventListener("click", e => {
                                    e.preventDefault();
                                    renderSection(className, branch);
                                    setActiveLink(link);
                                });
                                collapse.appendChild(link);
                            }
                        });
    
                        // N'ajouter l'ensemble que si au moins une branche est visible
                        if (visibleBranchCount > 0) {
                            branchWrapper.appendChild(parentToggle);
                            branchWrapper.appendChild(collapse);
                            catCollapse.appendChild(branchWrapper);
                        }
                    } else {
                        // Classe sans branches
                        if (!activeSources.has(source)) return;
                        const link = document.createElement("a");
                        link.href = "#";
                        link.className = "list-group-item list-group-item-action ps-3 d-flex justify-content-between align-items-center";
                        link.dataset.section = className;
                        link.innerHTML = `
                            <span>${className}</span>
                            <span class="badge bg-light text-muted ms-auto">${source}</span>
                        `;
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
    
        // Après insertion, synchroniser les toggles Bootstrap et réouvrir les catégories précédemment ouvertes
        setTimeout(() => {
            document.querySelectorAll('[data-bs-toggle="collapse"]').forEach(toggle => {
                const targetSelector = toggle.getAttribute("data-bs-target");
                const target = document.querySelector(targetSelector);
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
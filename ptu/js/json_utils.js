function loadJsonAsCard(file, container, cols = 3) {
    $.getJSON(file, function (data) {
        if (typeof data !== 'object' || Object.keys(data).length === 0) {
            alert(`Error: no data found in ${file}`);
            return;
        }

        // Déclare allItems localement
        const allItems = Object.entries(data).map(([name, value]) => {
            if (typeof value === "string") {
                return { Name: name, Description: value };
            } else {
                return { Name: name, ...value };
            }
        });

        renderFilteredCards(allItems, container, cols);

        // Supprime ancien listener s'il existe (évite multi écouteurs)
        const searchInput = document.getElementById("dex-search");
        if (searchInput) {
            searchInput.oninput = function () {
                const query = this.value.toLowerCase();
                const filtered = allItems.filter(item => {
                    const nameMatches = item.Name?.toLowerCase().includes(query);

                    const otherMatches = Object.entries(item)
                        .filter(([key]) => key !== 'Name')
                        .some(([key, value]) =>
                            typeof value === "string" && value.toLowerCase().includes(query)
                        );

                    return nameMatches || otherMatches;
                });

                // Et ajoute le tri (priorité au nom)
                filtered.sort((a, b) => {
                    const an = a.Name?.toLowerCase() || "";
                    const bn = b.Name?.toLowerCase() || "";

                    const aHit = an.includes(query);
                    const bHit = bn.includes(query);

                    if (aHit !== bHit) return aHit ? -1 : 1;
                    return an.localeCompare(bn);
                });

                renderFilteredCards(filtered, container, cols);
            };
        }
    });
}


function renderFilteredCards(data, container, cols) {
    container.innerHTML = "";

    // Calcule la classe bootstrap en fonction du nombre de colonnes
    // Exemple : cols=3 → col-md-4 (12/3=4), cols=2 → col-md-6, cols=4 → col-md-3
    const colSize = Math.floor(12 / cols);
    const colClass = `col-12 col-md-${colSize}`;

    data.forEach(item => {
        const cardHTML = renderItemAsCard(item);
        const cardDiv = document.createElement("div");
        cardDiv.className = colClass;
        cardDiv.innerHTML = `<div class="card h-100"><div class="card-body bg-light overflow-hidden rounded-3">${cardHTML}</div></div>`;
        container.appendChild(cardDiv);
    });
}

function renderItemAsCard(item, depth = 0) {
    let str = '';

    Object.keys(item).forEach(key => {
        const value = item[key];

        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            const headingLevel = Math.min(4 + depth, 6);
            const nestedHTML = renderItemAsCard(value, depth + 1);
            str += `
                <div class="mt-3">
                    <h${headingLevel} class="text-muted">${key}</h${headingLevel}>
                    <div class="card mt-1">
                        <div class="card-body">
                            ${nestedHTML}
                        </div>
                    </div>
                </div>`;
        } else if (key === "Name") {
            str += `<h3>${value ?? ""}</h3>`;
        } else {
            const safeValue = (value ?? "").toString().replace(/\n/g, "<br>");

            // --- CAS SPÉCIAL DAMAGE BASE ---
            if (key === "Damage Base") {
                // On met en gras tout ce qui est avant le premier ":"
                const [beforeColon, ...afterParts] = safeValue.split(':');
                const afterText = afterParts.length ? afterParts.join(':') : "";
                str += `<strong>${beforeColon}</strong>: ${afterText}<br>`;
            } else {
                // Rendu normal pour tous les autres champs
                str += `<strong>${key}</strong>: ${safeValue}<br>`;
            }
        }

    });

    return str;
}

// Used in statuses, structure name is Section name


function loadJsonAsCard_2(file, container, searchInputId) {
    $.getJSON(file, function (data) {
        if (typeof data !== 'object' || Object.keys(data).length === 0) {
            alert(`Error: no data found in ${file}`);
            return;
        }

        function render(dataToRender) {
            container.innerHTML = "";
            Object.entries(dataToRender).forEach(([sectionTitle, entries]) => {
                const header = document.createElement("h2");
                header.textContent = sectionTitle;
                container.appendChild(header);

                const row = document.createElement("div");
                row.className = "row g-3";

                Object.entries(entries).forEach(([name, description]) => {
                    const cardHTML = renderItemAsCard({
                        Name: name,
                        Description: description
                    });
                    const cardDiv = document.createElement("div");
                    cardDiv.className = "col-12 col-md-4";
                    cardDiv.innerHTML = `<div class="card h-100 overflow-hidden rounded-3"><div class="card-body bg-light">${cardHTML}</div></div>`;
                    row.appendChild(cardDiv);
                });

                container.appendChild(row);
            });
        }

        // Initial render
        render(data);

        // Setup search filtering
        if (searchInputId) {
            const searchInput = document.getElementById(searchInputId);
            if (searchInput) {
                searchInput.addEventListener("input", function () {
                    const query = this.value.toLowerCase();

                    const filteredData = {};

                    Object.entries(data).forEach(([sectionTitle, entries]) => {
                        // Priorité : le Nom d'abord
                        let filteredEntries = Object.entries(entries).filter(([name, desc]) => {
                            const nameMatches = name.toLowerCase().includes(query);
                            const descMatches = typeof desc === "string" && desc.toLowerCase().includes(query);
                            return nameMatches || descMatches;
                        });

                        // Tri : résultats dont le nom match en premier
                        filteredEntries.sort((a, b) => {
                            const [nameA, descA] = a;
                            const [nameB, descB] = b;

                            const aHit = nameA.toLowerCase().includes(query);
                            const bHit = nameB.toLowerCase().includes(query);

                            if (aHit !== bHit) return aHit ? -1 : 1;
                            return nameA.localeCompare(nameB);
                        });

                        if (filteredEntries.length > 0) {
                            filteredData[sectionTitle] = Object.fromEntries(filteredEntries);
                        }
                    });

                    render(filteredData);
                });
            }
        }
    });
}

function renderFilteredCards_2(data, container) {
    container.innerHTML = "";
    data.forEach(item => {
        const cardHTML = renderItemAsCard(item);
        const cardDiv = document.createElement("div");
        cardDiv.className = "col-12 col-md-4 overflow-hidden rounded-3";
        cardDiv.innerHTML = `<div class="card h-100 "><div class="card-body bg-light">${cardHTML}</div></div>`;
        container.appendChild(cardDiv);
    });
}

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
        const searchInput = document.getElementById("card-search");
        if (searchInput) {
            searchInput.oninput = function () {
                const query = this.value.toLowerCase();
                const filtered = allItems.filter(item =>
                    Object.values(item).some(value =>
                        typeof value === "string" && value.toLowerCase().includes(query)
                    )
                );
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
        cardDiv.innerHTML = `<div class="card h-100"><div class="card-body">${cardHTML}</div></div>`;
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
                    cardDiv.innerHTML = `<div class="card h-100"><div class="card-body">${cardHTML}</div></div>`;
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
                        const filteredEntries = Object.entries(entries).filter(([name, desc]) =>
                            name.toLowerCase().includes(query) || desc.toLowerCase().includes(query)
                        );

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
        cardDiv.className = "col-12 col-md-4";
        cardDiv.innerHTML = `<div class="card h-100"><div class="card-body">${cardHTML}</div></div>`;
        container.appendChild(cardDiv);
    });
}

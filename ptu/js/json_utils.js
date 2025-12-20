/* ============================================================
   PTU — JSON UTILS
   Version nettoyée, unifiée et sans duplication
   Style homogène avec json_items.js
   ============================================================ */

/* =======================
   0.   Utils généraux
   ======================= */

function ptuNormalizeEntries(data) {
    return Object.entries(data).map(([name, value]) =>
        typeof value === "string"
            ? { Name: name, Description: value }
            : { Name: name, ...value }
    );
}

function ptuFilter(list, query) {
    const q = query.toLowerCase();

    const filtered = list.filter(item => {
        const nameMatches = item.Name?.toLowerCase().includes(q);

        const otherMatches = Object.entries(item)
            .filter(([key]) => key !== "Name")
            .some(([key, value]) =>
                typeof value === "string" && value.toLowerCase().includes(q)
            );

        return nameMatches || otherMatches;
    });

    return ptuSort(filtered, q);
}

function ptuSort(list, query) {
    return list.sort((a, b) => {
        const an = a.Name?.toLowerCase() || "";
        const bn = b.Name?.toLowerCase() || "";

        const aHit = an.includes(query);
        const bHit = bn.includes(query);

        if (aHit !== bHit) return aHit ? -1 : 1;
        return an.localeCompare(bn);
    });
}

/* =======================
   1.   Rendu principal
   ======================= */

function renderPTUCard(item, depth = 0, showRootTitle = true) {
    let html = "";

    // Titre
    if (item.Name) {
        if (depth === 0 && showRootTitle) {
            html += `<h5 class="card-title">${item.Name}</h5>`;
        } else if (depth > 0) {
            html += `<h6 class="text-muted">${item.Name}</h6>`;
        }
    }

    // Champs
    for (const [key, value] of Object.entries(item)) {
        if (key === "Name") continue;

        // TABLE interne
        if (Array.isArray(value) && value.length && typeof value[0] === "object") {
            const cols = Object.keys(value[0]);
            html += `<p><strong>${key}:</strong></p>`;
            html += `<div class="table-responsive mt-2">
                <table class="table table-sm table-striped mb-0">
                    <thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead>
                    <tbody>
                        ${value.map(row => `
                            <tr>${cols.map(c => `<td>${row[c] ?? "—"}</td>`).join("")}</tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>`;
            continue;
        }

        // Objet simple → récursion
        if (typeof value === "object" && value !== null) {
            html += `<p><strong>${key}:</strong></p>`;
            html += `<div class="ms-3">${renderPTUCard(value, depth + 1)}</div>`;
            continue;
        }

        // Valeur simple
        let displayValue = value;
        if (key === "Description" && typeof value === "string") {
            displayValue = value.replace(/\n/g, "<br>");
        }
        html += `<p><strong>${key}:</strong> ${displayValue ?? ""}</p>`;
    }

    return html;
}

function renderPTUCards(list, container, cols = 3) {
    container.innerHTML = "";
    const colSize = Math.floor(12 / cols);

    list.forEach(item => {
        const col = document.createElement("div");
        col.className = `col-12 col-md-${colSize}`;

        const typeClass = item.Type ? `card-type-${item.Type}` : "";

        const card = document.createElement("div");
        card.className = "card h-100 bg-white border shadow-sm overflow-hidden rounded-3";

        const body = document.createElement("div");
        body.className = `card-body bg-light ${typeClass}`;
        body.innerHTML = renderPTUCardWithBadges(item);

        card.appendChild(body);
        col.appendChild(card);
        container.appendChild(col);
    });
}

function renderPTUCardWithBadges(item) {
    let html = "";

    // Badges : Category, Source, Type
    let title = item.Name || "";

    if (item.Category)
        title += ` <span class="badge bg-secondary">${item.Category}</span>`;

    if (item.Source)
        title += ` <span class="badge bg-info">${item.Source}</span>`;

    if (item.Type)
        title += ` <span class="badge bg-warning text-dark">${item.Type}</span>`;

    html += `<h5 class="card-title">${title}</h5>`;

    // Suite classique
    html += renderPTUCard(item, 0, false);

    return html;
}


/* =======================
   2.   Loader standard
   ======================= */

export function loadJsonAsCard(file, container, cols = 3) {
    $.getJSON(file, data => {
        if (!data || typeof data !== "object") {
            alert(`Error: no data found in ${file}`);
            return;
        }

        const allItems = ptuNormalizeEntries(data);
        renderPTUCards(allItems, container, cols);

        const searchInput = document.getElementById("dex-search");
        if (!searchInput) return;

        searchInput.oninput = () => {
            const filtered = ptuFilter(allItems, searchInput.value);
            renderPTUCards(filtered, container, cols);
        };
    });
}

/* =======================
   3.   Loader Sectionné
        (statuses, keywords, etc.)
   ======================= */

export function loadJsonAsCard_2(file, container, searchInputId) {
    $.getJSON(file, data => {
        if (!data || typeof data !== "object") {
            alert(`Error: no data found in ${file}`);
            return;
        }

        function renderSections(struct) {
            container.innerHTML = "";

            for (const [sectionName, entries] of Object.entries(struct)) {
                const h = document.createElement("h2");
                h.textContent = sectionName;
                container.appendChild(h);

                const row = document.createElement("div");
                row.className = "row g-3";
                container.appendChild(row);

                for (const [name, desc] of Object.entries(entries)) {
                    const col = document.createElement("div");
                    col.className = "col-12 col-md-4";

                    const card = document.createElement("div");
                    card.className = "card h-100 bg-white border shadow-sm overflow-hidden rounded-3";

                    const body = document.createElement("div");
                    body.className = "card-body bg-light";
                    body.innerHTML = renderPTUCard({ Name: name, Description: desc });

                    card.appendChild(body);
                    col.appendChild(card);
                    row.appendChild(col);
                }
            }
        }

        // initial
        renderSections(data);

        if (!searchInputId) return;

        const searchInput = document.getElementById(searchInputId);
        if (!searchInput) return;

        searchInput.addEventListener("input", () => {
            const q = searchInput.value.toLowerCase();
            const filtered = {};

            for (const [sectionName, entries] of Object.entries(data)) {
                let arr = Object.entries(entries);

                arr = arr.filter(([name, desc]) =>
                    name.toLowerCase().includes(q) ||
                    (typeof desc === "string" && desc.toLowerCase().includes(q))
                );

                arr = ptuSort(arr, q);

                if (arr.length)
                    filtered[sectionName] = Object.fromEntries(arr);
            }

            renderSections(filtered);
        });
    });
}

/* =======================
   4.   Rendu simple (array → cards)
        utilisé dans certains contextes
   ======================= */

function renderFilteredCards_2(list, container) {
    renderPTUCards(list, container, 3);
}

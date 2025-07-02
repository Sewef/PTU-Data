let allItems = [];

function loadJsonAsCard(file, container) {
    $.getJSON(file, function (data) {
        if (typeof data !== 'object' || Object.keys(data).length === 0) {
            alert(`Error: no data found in ${file}`);
            return;
        }

        // Convert object into array of {name, ...fields}
        allItems = Object.entries(data).map(([name, fields]) => ({
            Name: name,
            ...fields
        }));

        renderFilteredCards(allItems, container);

        const searchInput = document.getElementById("card-search");
        if (searchInput) {
            searchInput.addEventListener("input", function () {
                const query = this.value.toLowerCase();
                const filtered = allItems.filter(item =>
                    Object.values(item).some(value =>
                        typeof value === "string" && value.toLowerCase().includes(query)
                    )
                );
                renderFilteredCards(filtered, container);
            });
        }
    });
}

function renderFilteredCards(data, container) {
    container.innerHTML = "";
    data.forEach(item => {
        const cardHTML = renderItemAsCard(item);
        const cardDiv = document.createElement("div");
        cardDiv.className = "col-12 col-md-4";
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
            str += `<strong>${key}</strong>: ${value ?? ""}<br>`;
        }
    });

    return str;
}

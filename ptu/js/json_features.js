
function renderData(data, container, depth = 0) {
    for (const key in data) {
        if (!data.hasOwnProperty(key)) continue;
        const value = data[key];

        if (typeof value === "object" && value !== null) {
            // Only create a label for non-array objects to avoid duplicate labels for array elements
            if (!Array.isArray(value) && depth <= 1) {
                const label = document.createElement("h4");
                label.className = "card-subtitle mb-2 text-muted";
                label.textContent = key;
                container.appendChild(label);
            }
            // Recursively render nested objects, incrementing depth
            renderData(value, container, depth + 1);
        } else {
            const p = document.createElement("p");
            p.innerHTML = `<strong>${key}:</strong> ${value}`;
            container.appendChild(p);
        }
    }
}


// Création card Bootstrap
function createCard(title, data) {
    const card = document.createElement("div");
    card.className = "card mb-3";

    const cardBody = document.createElement("div");
    cardBody.className = "card-body";

    const cardTitle = document.createElement("h3");
    cardTitle.className = "card-title";
    cardTitle.textContent = title;

    cardBody.appendChild(cardTitle);

    // Start recursive rendering with depth 0, paragraphLevel 2 (à adapter)
    renderData(data, cardBody);

    card.appendChild(cardBody);
    return card;
}
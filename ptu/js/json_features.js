function renderData(data, container, depth = 0) {
    for (const key in data) {
        if (!data.hasOwnProperty(key)) continue;
        const value = data[key];

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


function createCard(title, data) {
    // Create the column wrapper
    const col = document.createElement("div");
    col.className = "col-md-12 mb-3";

    const card = document.createElement("div");
    card.className = "card h-100";

    const cardBody = document.createElement("div");
    cardBody.className = "card-body";

    const cardTitle = document.createElement("h4");
    cardTitle.className = "card-title";
    cardTitle.textContent = title;

    cardBody.appendChild(cardTitle);
    renderData(data, cardBody);
    card.appendChild(cardBody);
    col.appendChild(card);

    return col;
}

function loadFeatures(file) {
	fetch(file)
		.then(response => {
			if (!response.ok) throw new Error("Failed to load JSON");
			return response.json();
		})
		.then(jsonData => {
			const container = document.getElementById("cards-container");

			for (const sectionTitle in jsonData) {
				const section = jsonData[sectionTitle];

				const header = document.createElement("h2");
				header.className = "my-4";
				header.textContent = sectionTitle;
				container.appendChild(header);

				const row = document.createElement("div");
				row.className = "row";

				for (const cardTitle in section) {
					const card = createCard(cardTitle, section[cardTitle]);
					row.appendChild(card);
				}

				container.appendChild(row); // Add the row after the section header
			}
			
		})
		.catch(error => {
			console.error("Error loading JSON:", error);
		});
}
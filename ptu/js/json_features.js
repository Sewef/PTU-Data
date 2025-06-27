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
let fullData = {};
let currentActiveLink = null;

function loadFeatures(file) {
    fetch(file)
        .then(response => {
            if (!response.ok) throw new Error("Failed to load JSON");
            return response.json();
        })
        .then(jsonData => {
            fullData = jsonData;
            const sidebar = document.getElementById("sidebar");

            Object.keys(jsonData).forEach((sectionTitle, index) => {
                const link = document.createElement("a");
                link.href = "#";
                link.className = "list-group-item list-group-item-action";
                link.textContent = sectionTitle;
                link.dataset.section = sectionTitle;

                link.addEventListener("click", (e) => {
                    e.preventDefault();
                    renderSection(sectionTitle);
                    setActiveLink(link);
                });

                sidebar.appendChild(link);

                // Automatically load the first section
                if (index === 0) {
                    renderSection(sectionTitle);
                    setActiveLink(link);
                }
            });
        })
        .catch(error => {
            console.error("Error loading JSON:", error);
        });
}
function renderSection(sectionTitle) {
    const container = document.getElementById("cards-container");
    container.innerHTML = "";

    const section = fullData[sectionTitle];
    if (!section) return;

    const row = document.createElement("div");
    row.className = "row";

    for (const cardTitle in section) {
        const card = createCard(cardTitle, section[cardTitle]);
        row.appendChild(card);
    }

    container.appendChild(row);

    // Scroll to just below the header
    const header = document.querySelector('div[w3-include-html="header.html"]') || document.querySelector("header");
    const headerHeight = header ? header.offsetHeight : 0;

    const scrollTop = container.offsetTop - headerHeight - 16; // add padding
}


function setActiveLink(link) {
    if (currentActiveLink) {
        currentActiveLink.classList.remove("active");
    }
    link.classList.add("active");
    currentActiveLink = link;
}

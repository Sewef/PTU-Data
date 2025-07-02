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
            sidebar.innerHTML = ""; // Clear existing

            // Create search input
            const searchInput = document.createElement("input");
            searchInput.type = "text";
            searchInput.className = "form-control mb-2";
            searchInput.placeholder = "Search classes...";
            sidebar.appendChild(searchInput);

            // Container for links
            const linkContainer = document.createElement("div");
            linkContainer.className = "list-group";
            sidebar.appendChild(linkContainer);

            // Map of sectionTitle → link element
            const linkMap = {};

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

                linkMap[sectionTitle] = link;
                linkContainer.appendChild(link);

                if (index === 0) {
                    renderSection(sectionTitle);
                    setActiveLink(link);
                }
            });

            // Filter sidebar links
            searchInput.addEventListener("input", () => {
                const query = searchInput.value.toLowerCase();
                linkContainer.innerHTML = ""; // Clear links
                for (const title in linkMap) {
                    if (title.toLowerCase().includes(query)) {
                        linkContainer.appendChild(linkMap[title]);
                    }
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

    // Add section title heading
    const sectionHeading = document.createElement("h2");
    sectionHeading.textContent = sectionTitle;
    sectionHeading.className = "mb-4 mt-3";
    container.appendChild(sectionHeading);

    // Create and insert search input
    const searchDiv = document.createElement("div");
    searchDiv.className = "mb-3";

    const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.placeholder = "Search features...";
    searchInput.className = "form-control";
    searchInput.id = "search-input";

    searchDiv.appendChild(searchInput);
    container.appendChild(searchDiv);

    const row = document.createElement("div");
    row.className = "row g-3";  // ensure proper spacing between cards
    row.id = "feature-row";

    const cardMap = {};

    for (const cardTitle in section) {
        const card = createCard(cardTitle, section[cardTitle]);
        card.dataset.title = cardTitle.toLowerCase(); // for filtering
        cardMap[cardTitle] = card;
        row.appendChild(card);
    }

    container.appendChild(row);

    // Filter logic
    searchInput.addEventListener("input", () => {
        const query = searchInput.value.toLowerCase();
        row.innerHTML = "";

        for (const title in cardMap) {
            if (title.toLowerCase().includes(query)) {
                row.appendChild(cardMap[title]);
            }
        }
    });

    // Optional scroll behavior
    window.scrollTo({ top: 0, behavior: "smooth" }); // Uncomment if needed
}



function setActiveLink(link) {
    if (currentActiveLink) {
        currentActiveLink.classList.remove("active");
    }
    link.classList.add("active");
    currentActiveLink = link;
}

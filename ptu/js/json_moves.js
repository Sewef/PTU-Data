function buildTypeSidebar(moves) {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;

  const types = [...new Set(moves.map(m => m.Type).filter(Boolean))].sort();
  sidebar.innerHTML = `
  <div class="mb-3">
    <input type="text" id="sidebar-search" class="form-control mb-2" placeholder="Filter types...">
    <button id="toggle-all-types" class="btn btn-sm btn-secondary w-100 mb-2">Select/Deselect all</button>
  </div>
  <div id="type-filters" class="list-group">
    ${types.map(type => `
      <label class="list-group-item">
        <input class="form-check-input me-1" type="checkbox" value="${type}">
        ${type}
      </label>
    `).join("")}
  </div>
`;


  // Listeners
  sidebar.querySelectorAll("input").forEach(input =>
    input.addEventListener("change", () => filterAndRender(moves))
  );

  const sidebarSearch = document.getElementById("sidebar-search");
  if (sidebarSearch) {
    sidebarSearch.addEventListener("input", () => {
      const q = sidebarSearch.value.toLowerCase();
      document.querySelectorAll("#type-filters label").forEach(label => {
        const text = label.textContent.toLowerCase();
        label.style.display = text.includes(q) ? "" : "none";
      });
    });
  }


  // Bouton tout cocher / décocher
  const toggleBtn = document.getElementById("toggle-all-types");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const checkboxes = document.querySelectorAll("#type-filters input[type='checkbox']");
      const allChecked = Array.from(checkboxes).every(cb => cb.checked);
      checkboxes.forEach(cb => cb.checked = !allChecked);
      filterAndRender(moves);
    });
  }
}


function getActiveTypes() {
  return Array.from(document.querySelectorAll('#type-filters input:checked'))
    .map(el => el.value);
}

function filterAndRender(allItems) {
  const query = document.getElementById("card-search")?.value.toLowerCase() || "";
  const activeTypes = getActiveTypes();

  const filtered = allItems.filter(item => {
    const matchesQuery = Object.values(item).some(value =>
      typeof value === "string" && value.toLowerCase().includes(query)
    );

    const matchesType = activeTypes.length === 0 || activeTypes.includes(item.Type);
    return matchesQuery && matchesType;
  });

  renderFilteredCards(filtered, document.getElementById("moves-container"), 3);
}


function loadMovesAsCard(file, container, cols = 3) {
  $.getJSON(file, function (data) {
    if (typeof data !== 'object' || Object.keys(data).length === 0) {
      alert(`Error: no data found in ${file}`);
      return;
    }

    const allItems = Object.entries(data).map(([name, value]) => {
      if (typeof value === "string") {
        return { Name: name, Description: value };
      } else {
        return { Name: name, ...value };
      }
    });

    buildTypeSidebar(allItems);
    filterAndRender(allItems);

    const searchInput = document.getElementById("card-search");
    if (searchInput) {
      searchInput.oninput = () => filterAndRender(allItems);
    }
  });
}

function loadKeywordsAsCard(file, container, cols = 3) {
  $.getJSON(file, function (data) {
    if (typeof data !== 'object' || Object.keys(data).length === 0) {
      alert(`Error: no data found in ${file}`);
      return;
    }

    const allItems = Object.entries(data).map(([name, value]) => {
      if (typeof value === "string") {
        return { Name: name, Description: value };
      } else {
        return { Name: name, ...value };
      }
    });

    renderFilteredCards(allItems, container, cols);

    // 🎯 Ajout du filtre texte
    const searchInput = document.getElementById("keyword-search");
    if (searchInput) {
      searchInput.addEventListener("input", function () {
        const q = this.value.toLowerCase();
        container.querySelectorAll(".card").forEach(card => {
          const content = card.textContent.toLowerCase();
          card.closest(".col-12, .col-md-6, .col-md-4")?.style.setProperty("display",
            content.includes(q) ? "" : "none"
          );
        });
      });
    }
  });
}


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
    cardDiv.innerHTML = `<div class="card h-100"><div class="card-body bg-light">${cardHTML}</div></div>`;
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
                        <div class="card-body bg-light">
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

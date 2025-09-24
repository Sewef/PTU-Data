function debounce(fn, delay = 150) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), delay); } }

function jsonToItems(obj){
  return Object.entries(obj).map(([name, value]) =>
    typeof value === "string" ? { Name: name, Description: value } : { Name: name, ...value }
  );
}

function buildTypeSidebar(moves, container, cols) {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;

  const types = [...new Set(moves.map(m => m.Type).filter(Boolean))].sort();
  sidebar.innerHTML = `
  <div class="mb-3">
    <input type="text" id="sidebar-search" class="form-control form-control-sm mb-2" placeholder="Filter types...">
    <button id="toggle-all-types" class="btn btn-sm btn-primary w-100 mb-2">Select/Deselect all</button>
  </div>
  <div id="type-filters" class="list-group">
    ${types.map(type => `
      <label class="list-group-item card-type-${type}">
        <input class="form-check-input me-1" type="checkbox" value="${type}">
        ${type}
      </label>
    `).join("")}
  </div>
`;


  // Listeners
  sidebar.querySelectorAll("#type-filters input[type='checkbox']").forEach(input => {
    input.addEventListener("change", () => filterAndRender(moves, container, cols));
  });

  const sidebarSearch = document.getElementById("sidebar-search");
  if (sidebarSearch) {
    sidebarSearch.addEventListener("input", debounce(() => {
      const q = sidebarSearch.value.toLowerCase();
      document.querySelectorAll("#type-filters label").forEach(label => {
        const text = label.textContent.toLowerCase();
        label.style.display = text.includes(q) ? "" : "none";
      });
    }), 150);
  }


  // Bouton tout cocher / décocher
  const toggleBtn = document.getElementById("toggle-all-types");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const typeFilters = document.getElementById("type-filters");
      const checkboxes = typeFilters.querySelectorAll('input[type="checkbox"]');
      const allChecked = Array.from(checkboxes).every(cb => cb.checked);
      checkboxes.forEach(cb => cb.checked = !allChecked);
      filterAndRender(moves, container, cols);
    });
  }
}


function getActiveTypes() {
  return Array.from(document.querySelectorAll('#type-filters input:checked'))
    .map(el => el.value);
}

function filterAndRender(allItems, container, cols = 3) {
  const query = document.getElementById("card-search")?.value.toLowerCase() || "";
  const activeTypes = getActiveTypes();

  const filtered = allItems.filter(item => {
    const nameMatches = item.Name?.toLowerCase().includes(query);
    const otherMatches = Object.entries(item)
      .filter(([key]) => key !== 'Name')
      .some(([key, value]) => typeof value === "string" && value.toLowerCase().includes(query));

    const matchesType = activeTypes.length === 0 || activeTypes.includes(item.Type);

    return (nameMatches || otherMatches) && matchesType;
  });

  filtered.sort((a, b) => {
    const qa = query, an = a.Name?.toLowerCase() || "", bn = b.Name?.toLowerCase() || "";
    const aHit = an.includes(qa), bHit = bn.includes(qa);
    if (aHit !== bHit) return aHit ? -1 : 1;
    return an.localeCompare(bn);
  });

  renderFilteredCards(filtered, container, cols);
}


function loadMovesAsCard(file, container, cols = 3) {
  $.getJSON(file, function (data) {
    if (typeof data !== 'object' || Object.keys(data).length === 0) {
      alert(`Error: no data found in ${file}`);
      return;
    }

    const allItems = jsonToItems(data);

    buildTypeSidebar(allItems, container, cols);
    filterAndRender(allItems, container, cols);

    const searchInput = document.getElementById("card-search");
    if (searchInput) {
      searchInput.oninput = debounce(() => filterAndRender(allItems, container, cols), 150);
    }
  });
}

function loadKeywordsAsCard(file, container, cols = 3) {
  $.getJSON(file, function (data) {
    if (typeof data !== 'object' || Object.keys(data).length === 0) {
      alert(`Error: no data found in ${file}`);
      return;
    }

    const allItems = jsonToItems(data);

    renderFilteredCards(allItems, container, cols);

    // 🎯 Ajout du filtre texte
    const searchInput = document.getElementById("keyword-search");
    if (searchInput) {
      searchInput.addEventListener("input", function () {
        const q = this.value.toLowerCase();
        container.querySelectorAll(".card").forEach(card => {
          const content = card.textContent.toLowerCase();
          card.closest('[class*="col-"]')?.style.setProperty("display", content.includes(q) ? "" : "none");
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
    const allItems = jsonToItems(data);

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

function renderFilteredCards(data, container, cols){
  container.innerHTML = "";
  const colSize = Math.floor(12/cols);
  const colClass = `col-12 col-md-${colSize}`;
  const frag = document.createDocumentFragment();

  data.forEach(item=>{
    const wrapper = document.createElement("div");
    wrapper.className = colClass;

    const typeClass = item.Type ? `card-type-${item.Type}` : "";
    const card = document.createElement("div");
    card.className = "card h-100 overflow-hidden rounded-3";
    const body = document.createElement("div");
    body.className = `card-body ${typeClass} bg-light`;
    body.innerHTML = renderItemAsCard(item);

    card.appendChild(body);
    wrapper.appendChild(card);
    frag.appendChild(wrapper);
  });

  container.appendChild(frag);
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

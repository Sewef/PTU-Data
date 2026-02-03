import {
  debounce,
  jsonToItems,
  buildPillSection,
  getSelectedPills,
  filterText,
  filterByTypes,
  filterByClasses
} from "/ptu/js/helpers.js";

export const DAMAGE_BASE_TABLE = {
  1: { dmg: '1d6+1', min: 2, avg: 5, max: 7 },
  2: { dmg: '1d6+3', min: 4, avg: 7, max: 9 },
  3: { dmg: '1d6+5', min: 6, avg: 9, max: 11 },
  4: { dmg: '1d8+6', min: 7, avg: 11, max: 14 },
  5: { dmg: '1d8+8', min: 9, avg: 13, max: 16 },
  6: { dmg: '2d6+8', min: 10, avg: 15, max: 20 },
  7: { dmg: '2d6+10', min: 12, avg: 17, max: 22 },
  8: { dmg: '2d8+10', min: 12, avg: 19, max: 26 },
  9: { dmg: '2d10+10', min: 12, avg: 21, max: 30 },
  10: { dmg: '3d8+10', min: 13, avg: 24, max: 34 },
  11: { dmg: '3d10+10', min: 13, avg: 27, max: 40 },
  12: { dmg: '3d12+10', min: 13, avg: 30, max: 46 },
  13: { dmg: '4d10+10', min: 14, avg: 35, max: 50 },
  14: { dmg: '4d10+15', min: 19, avg: 40, max: 55 },
  15: { dmg: '4d10+20', min: 24, avg: 45, max: 60 },
  16: { dmg: '5d10+20', min: 25, avg: 50, max: 70 },
  17: { dmg: '5d12+25', min: 30, avg: 60, max: 85 },
  18: { dmg: '6d12+25', min: 31, avg: 65, max: 97 },
  19: { dmg: '6d12+30', min: 36, avg: 70, max: 102 },
  20: { dmg: '6d12+35', min: 41, avg: 75, max: 107 },
  21: { dmg: '6d12+40', min: 46, avg: 80, max: 112 },
  22: { dmg: '6d12+45', min: 51, avg: 85, max: 117 },
  23: { dmg: '6d12+50', min: 56, avg: 90, max: 122 },
  24: { dmg: '6d12+55', min: 61, avg: 95, max: 127 },
  25: { dmg: '6d12+60', min: 66, avg: 100, max: 132 },
  26: { dmg: '7d12+65', min: 72, avg: 110, max: 149 },
  27: { dmg: '8d12+70', min: 78, avg: 120, max: 166 },
  28: { dmg: '8d12+80', min: 88, avg: 130, max: 176 }
};

function formatDamageBaseValue(raw) {
  if (raw == null || raw === "") return "";

  const match = String(raw).match(/\d+/);
  if (!match) return String(raw);

  const value = Number.parseInt(match[0], 10);
  if (!Number.isFinite(value)) return String(raw);

  const info = DAMAGE_BASE_TABLE[value];
  if (!info) return String(value);

  return `${value} (${info.dmg} / ${info.avg})`;
}

function buildSidebarMoves(allItems, container, cols) {
  const sidebar = document.getElementById("sidebar");
  sidebar.innerHTML = "";

  // ====================
  // Types
  // ====================
  const moveTypes = [...new Set(allItems.map(m => m.Type).filter(Boolean))].sort();

  const typesGroup = document.createElement("div");
  typesGroup.className = "mb-3";

  const typesLabel = document.createElement("label");
  typesLabel.className = "form-label";
  typesLabel.textContent = "Types";
  typesGroup.appendChild(typesLabel);

  // Les pills sont insérées DANS ce group
  buildPillSection(typesGroup, "type-filters", moveTypes, {
    attr: "data-type",
    onChange: () => refreshMoves(allItems, container, cols)
  });

  sidebar.appendChild(typesGroup);

  // ====================
  // Class
  // ====================
  const classGroup = document.createElement("div");
  classGroup.className = "mt-3";

  const classLabel = document.createElement("label");
  classLabel.className = "form-label";
  classLabel.textContent = "Class";
  classGroup.appendChild(classLabel);

  buildPillSection(classGroup, "class-filters", ["Physical", "Special", "Status"], {
    attr: "data-class",
    onChange: () => refreshMoves(allItems, container, cols)
  });

  sidebar.appendChild(classGroup);
}


function refreshMoves(allItems, container, cols) {
  const query = document.getElementById("card-search")?.value.toLowerCase() || "";

  const types = getSelectedPills(document, "type-filters", "data-type");
  const classes = getSelectedPills(document, "class-filters", "data-class");

  const filtered = allItems
    .filter(item => filterText(query, item))
    .filter(item => filterByTypes(item, types))
    .filter(item => filterByClasses(item, classes));

  renderFilteredCards(filtered, container, cols);
}

export function loadMovesAsCard(file, container, cols = 3) {
  $.getJSON(file, function (data) {
    if (typeof data !== 'object' || Object.keys(data).length === 0) {
      alert(`Error: no data found in ${file}`);
      return;
    }

    const allItems = jsonToItems(data);

    buildSidebarMoves(allItems, container, cols);
    refreshMoves(allItems, container, cols);

    const searchInput = document.getElementById("card-search");
    if (searchInput) {
      searchInput.oninput = debounce(() => refreshMoves(allItems, container, cols), 150);
    }
  });
}

export function loadKeywordsAsCard(file, container, cols = 3) {
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

function renderFilteredCards(data, container, cols) {
  container.innerHTML = "";
  const colSize = Math.floor(12 / cols);
  const frag = document.createDocumentFragment();

  data.forEach(item => {
    const wrapper = document.createElement("div");
    wrapper.className = `col-12 col-md-${colSize}`;

    const typeClass = item.Type ? `card-type-${item.Type}` : "";

    const card = document.createElement("div");
    card.className = "card h-100 bg-white border shadow-sm overflow-hidden rounded-3";

    const body = document.createElement("div");
    body.className = `card-body bg-light ${typeClass} lh-1`;
    body.innerHTML = renderMoveCard(item);

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
        const formatted = formatDamageBaseValue(value);
        str += `<strong>Damage Base</strong>: ${formatted}<br>`;
      } else {
        // Rendu normal pour tous les autres champs
        str += `<strong>${key}</strong>: ${safeValue}<br>`;
      }
    }

  });

  return str;
}

function renderMoveCard(item) {
  let html = "";

  // ----- TITRE AVEC BADGES -----
  let title = item.Name || "";

  // Badge coloré du type
  if (item.Type)
    title += ` <span class="badge badge-type">${item.Type}</span>`;

  // Badges complémentaires
  if (item.Frequency)
    title += ` <span class="badge bg-secondary">${item.Frequency}</span>`;

  // Badge physique/spéciale/status basé sur Class
  // Badge de classe (Physical / Special / Status)
  if (item.Class) {
    const cls = item.Class.toLowerCase();
    let classTag = "Status";  // default

    if (cls.includes("physical")) classTag = "Physical";
    else if (cls.includes("special")) classTag = "Special";
    else if (cls.includes("status")) classTag = "Status";

    // Le badge utilise la couleur définie par .card-type-XXX
    title += ` <span class="badge badge-type card-type-${classTag}">${item.Class}</span>`;
  }

  html += `<h5 class="card-title">${title}</h5>`;

  // ----- Best-PTU rendering -----
  for (const [key, value] of Object.entries(item)) {
    if (["Name", "Type"].includes(key)) continue;

    // Sous-objet
    if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      html += `<p><strong>${key}:</strong></p>`;
      html += `<div class="ms-3">${renderMoveCard(value)}</div>`;
      continue;
    }

    // ----- DAMAGE BASE : afficher valeur + table -----
    if (key === "Damage Base") {
      const formatted = formatDamageBaseValue(value ?? "");
      html += `<p><strong>Damage Base:</strong> ${formatted}</p>`;
      continue;
    }


    // Valeur simple
    const safeValue = (value ?? "").toString().replace(/\n/g, "<br>");
    html += `<p><strong>${key}:</strong> ${safeValue}</p>`;
  }


  return html;
}


import {
  debounce,
  jsonToItems,
  buildPillSection,
  getSelectedPills,
  filterText,
  filterByTypes,
  filterByClasses,
  filterByDamageBase,
  filterByEffect,
  filterByContestType,
  filterByContestEffect,
  filterByRangeDistance,
  filterByRangeKeyword,
  filterByTargeting
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

  // ====================
  // Damage Base
  // ====================
  const damageBases = [...new Set(
    allItems
      .map(m => {
        const db = m["Damage Base"];
        if (!db) return null;
        const match = String(db).match(/\d+/);
        return match ? match[0] : null;
      })
      .filter(Boolean)
  )].sort((a, b) => Number(a) - Number(b));

  if (damageBases.length > 0) {
    const damageBaseGroup = document.createElement("div");
    damageBaseGroup.className = "mt-3";

    const damageBaseLabel = document.createElement("label");
    damageBaseLabel.className = "form-label";
    damageBaseLabel.textContent = "Damage Base";
    damageBaseGroup.appendChild(damageBaseLabel);

    buildPillSection(damageBaseGroup, "damage-base-filters", damageBases, {
      attr: "data-damage-base",
      onChange: () => refreshMoves(allItems, container, cols)
    });

    sidebar.appendChild(damageBaseGroup);
  }

  // ====================
  // Has Effect
  // ====================
  const effectGroup = document.createElement("div");
  effectGroup.className = "mt-3";

  const effectLabel = document.createElement("label");
  effectLabel.className = "form-label";
  effectLabel.textContent = "Effects";
  effectGroup.appendChild(effectLabel);

  buildPillSection(effectGroup, "effect-filters", ["With Effect", "No Effect"], {
    attr: "data-effect",
    onChange: () => refreshMoves(allItems, container, cols)
  });

  sidebar.appendChild(effectGroup);

  // ====================
  // Range Distance
  // ====================
  const rangeDistances = new Set();
  allItems.forEach(m => {
    const range = m.Range || "";
    // Split by "; or " to separate variants
    const variants = range.split(/;\s*or\s+/i).map(v => v.trim());
    
    variants.forEach(variant => {
      const parts = variant.split(',').map(p => p.trim());
      
      parts.forEach(part => {
        // Melee
        if (part.toLowerCase().includes('melee')) {
          rangeDistances.add('Melee');
        }
        // Nombre isolé
        const match = part.match(/^(\d+)$/);
        if (match) {
          rangeDistances.add(match[1]);
        }
        // Nombres dans "Cone 2", "Line 6", etc.
        const keywordMatch = part.match(/^(?:Cone|Line|Burst|Close Blast|Blast)\s+(\d+)$/i);
        if (keywordMatch) {
          rangeDistances.add(keywordMatch[1]);
        }
      });
    });
  });

  const sortedDistances = [...rangeDistances].sort((a, b) => {
    if (a === 'Melee') return -1;
    if (b === 'Melee') return 1;
    return Number(a) - Number(b);
  });

  if (sortedDistances.length > 0) {
    const rangeDistanceGroup = document.createElement("div");
    rangeDistanceGroup.className = "mt-3";

    const rangeDistanceLabel = document.createElement("label");
    rangeDistanceLabel.className = "form-label";
    rangeDistanceLabel.textContent = "Range Distance";
    rangeDistanceGroup.appendChild(rangeDistanceLabel);

    buildPillSection(rangeDistanceGroup, "range-distance-filters", sortedDistances, {
      attr: "data-range-distance",
      onChange: () => refreshMoves(allItems, container, cols),
      useTypeClass: false
    });

    sidebar.appendChild(rangeDistanceGroup);
  }

  // ====================
  // Range Keywords
  // ====================
  const rangeKeywords = new Set();
  allItems.forEach(m => {
    const range = m.Range || "";
    // Split by "; or " to separate variants
    const variants = range.split(/;\s*or\s+/i).map(v => v.trim());
    
    variants.forEach(variant => {
      const parts = variant.split(',').map(p => p.trim());
      
      parts.forEach(part => {
        // Supprimer le contenu entre parenthèses (ex: "(see Effect)")
        part = part.replace(/\s*\([^)]*\)/g, '').trim();
        
        // Ignorer les nombres seuls
        if (/^\d+$/.test(part)) return;
        
        // Gérer les patterns "X or Y" (ex: "Burst 1 or Close Blast 2")
        const orParts = part.split(/\s+or\s+/i);
        
        orParts.forEach(subPart => {
          subPart = subPart.trim();
          
          // Pattern "Recoil 1/3", "Recoil 1/2", etc. -> garder seulement "Recoil"
          const recoilMatch = subPart.match(/^Recoil\s+\d+\/\d+$/i);
          if (recoilMatch) {
            rangeKeywords.add('Recoil');
            return;
          }
          
          // Pattern "Burst 1*", "Cone 2*", etc. -> garder seulement le mot-clé
          const asteriskMatch = subPart.match(/^(Cone|Line|Burst|Close Blast|Blast)\s+\d+\*$/i);
          if (asteriskMatch) {
            rangeKeywords.add(asteriskMatch[1]);
            return;
          }
          
          // Pattern "Cone 2", "Line 6", etc.
          const keywordMatch = subPart.match(/^(Cone|Line|Burst|Close Blast|Blast)\s+\d+$/i);
          if (keywordMatch) {
            rangeKeywords.add(keywordMatch[1]);
            return;
          }
          
          // Autres mots en enlevant les nombres
          const cleaned = subPart.replace(/\d+/g, '').trim();
          // Exclure 'melee', 'target' et 'targets' (gérés par d'autres filtres)
          const lowerCleaned = cleaned.toLowerCase();
          if (cleaned && lowerCleaned !== 'melee' && lowerCleaned !== 'target' && lowerCleaned !== 'targets') {
            rangeKeywords.add(cleaned);
          }
        });
      });
    });
  });

  const sortedKeywords = [...rangeKeywords].sort();

  if (sortedKeywords.length > 0) {
    const rangeKeywordGroup = document.createElement("div");
    rangeKeywordGroup.className = "mt-3";

    const rangeKeywordLabel = document.createElement("label");
    rangeKeywordLabel.className = "form-label";
    rangeKeywordLabel.textContent = "Range Keywords";
    rangeKeywordGroup.appendChild(rangeKeywordLabel);

    buildPillSection(rangeKeywordGroup, "range-keyword-filters", sortedKeywords, {
      attr: "data-range-keyword",
      onChange: () => refreshMoves(allItems, container, cols),
      useTypeClass: false
    });

    sidebar.appendChild(rangeKeywordGroup);
  }

  // ====================
  // Targeting (Single vs Multi)
  // ====================
  const targetingGroup = document.createElement("div");
  targetingGroup.className = "mt-3";

  const targetingLabel = document.createElement("label");
  targetingLabel.className = "form-label";
  targetingLabel.textContent = "Targeting";
  targetingGroup.appendChild(targetingLabel);

  buildPillSection(targetingGroup, "targeting-filters", ["Single Target", "Multi Target"], {
    attr: "data-targeting",
    onChange: () => refreshMoves(allItems, container, cols),
    useTypeClass: false
  });

  sidebar.appendChild(targetingGroup);

  // ====================
  // Contest Type
  // ====================
  const contestTypes = [...new Set(
    allItems
      .map(m => m["Contest Type"])
      .filter(Boolean)
  )].sort();

  if (contestTypes.length > 0) {
    const contestTypeGroup = document.createElement("div");
    contestTypeGroup.className = "mt-3";

    const contestTypeLabel = document.createElement("label");
    contestTypeLabel.className = "form-label";
    contestTypeLabel.textContent = "Contest Type";
    contestTypeGroup.appendChild(contestTypeLabel);

    buildPillSection(contestTypeGroup, "contest-type-filters", contestTypes, {
      attr: "data-contest-type",
      onChange: () => refreshMoves(allItems, container, cols),
      useTypeClass: false
    });

    sidebar.appendChild(contestTypeGroup);
  }

  // ====================
  // Contest Effect
  // ====================
  const contestEffects = [...new Set(
    allItems
      .map(m => m["Contest Effect"])
      .filter(Boolean)
  )].sort();

  if (contestEffects.length > 0) {
    const contestEffectGroup = document.createElement("div");
    contestEffectGroup.className = "mt-3";

    const contestEffectLabel = document.createElement("label");
    contestEffectLabel.className = "form-label";
    contestEffectLabel.textContent = "Contest Effect";
    contestEffectGroup.appendChild(contestEffectLabel);

    buildPillSection(contestEffectGroup, "contest-effect-filters", contestEffects, {
      attr: "data-contest-effect",
      onChange: () => refreshMoves(allItems, container, cols),
      useTypeClass: false
    });

    sidebar.appendChild(contestEffectGroup);
  }
}


function refreshMoves(allItems, container, cols) {
  const query = document.getElementById("card-search")?.value.toLowerCase() || "";

  const types = getSelectedPills(document, "type-filters", "data-type");
  const classes = getSelectedPills(document, "class-filters", "data-class");
  const damageBases = getSelectedPills(document, "damage-base-filters", "data-damage-base");
  const effects = getSelectedPills(document, "effect-filters", "data-effect");
  const rangeDistances = getSelectedPills(document, "range-distance-filters", "data-range-distance");
  const rangeKeywords = getSelectedPills(document, "range-keyword-filters", "data-range-keyword");
  const targeting = getSelectedPills(document, "targeting-filters", "data-targeting");
  const contestTypes = getSelectedPills(document, "contest-type-filters", "data-contest-type");
  const contestEffects = getSelectedPills(document, "contest-effect-filters", "data-contest-effect");

  const filtered = allItems
    .filter(item => filterText(query, item))
    .filter(item => filterByTypes(item, types))
    .filter(item => filterByClasses(item, classes))
    .filter(item => filterByDamageBase(item, damageBases))
    .filter(item => filterByEffect(item, effects))
    .filter(item => filterByRangeDistance(item, rangeDistances))
    .filter(item => filterByRangeKeyword(item, rangeKeywords))
    .filter(item => filterByTargeting(item, targeting))
    .filter(item => filterByContestType(item, contestTypes))
    .filter(item => filterByContestEffect(item, contestEffects));

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
    card.className = "card h-100 bg-body border shadow-sm overflow-hidden rounded-3";

    const body = document.createElement("div");
    body.className = `card-body bg-body-secondary ${typeClass} lh-1`;
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
                        <div class="card-body bg-body-secondary">
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


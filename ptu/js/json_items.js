// === Items Viewer — adapté pour items_core.json + affichage tableau =========
// Catégories = clés de premier niveau (ex: "Poké Ball", "Medicines", ...).
// Sous-catégories = clés contenant des Arrays (ex: "Items", "Tiers", "Yields"...).
// Option JSON : dans chaque catégorie, un objet facultatif "_display" permet
// d'indiquer l'affichage des sous-catégories, ex.:
// "_display": { "Tiers": { type: "table", rowPerField: true, idField: "Tier" } }

let itemsData = {};
let activeCategory = null;
let edgeColSize = 4;
let edgeContainer = null;

function loadItems(path, container = document.getElementById("cards-container"), col = 3) {
  fetch(path)
    .then(r => r.json())
    .then(json => {
      itemsData = json;
      edgeContainer = container;
      edgeColSize = Math.floor(12 / col);
      buildCategoryMenu();
      const firstCat = Object.keys(itemsData)[0];
      if (firstCat) {
        activeCategory = firstCat;
        renderCategory(firstCat);
        const defaultBtn = [...document.querySelectorAll("#sidebar .list-group-item")]
          .find(btn => btn.textContent === firstCat);
        if (defaultBtn) defaultBtn.classList.add("active");
      }
    })
    .catch(err => console.error("JSON load error:", err));
}

function buildCategoryMenu() {
  const sb = document.getElementById("sidebar");
  sb.innerHTML = "";

  sb.insertAdjacentHTML("beforeend", `<label class="form-label">Catégories :</label>`);
  const catList = document.createElement("div");
  catList.className = "list-group";

  Object.keys(itemsData).forEach(cat => {
    const btn = document.createElement("button");
    btn.className = "list-group-item list-group-item-action";
    btn.textContent = cat;
    btn.addEventListener("click", () => {
      activeCategory = cat;
      document.querySelectorAll("#sidebar .list-group-item").forEach(e => e.classList.remove("active"));
      btn.classList.add("active");
      renderCategory(cat);
    });
    catList.appendChild(btn);
  });
  sb.appendChild(catList);
}

function renderCategory(cat) {
  const pane = edgeContainer;
  pane.innerHTML = "";

  const searchBox = document.createElement("div");
  searchBox.className = "mb-3";
  searchBox.innerHTML = `<input type="text" id="filter-search" class="form-control" placeholder="Rechercher...">`;
  pane.appendChild(searchBox);

  const row = document.createElement("div");
  row.className = "row g-3";
  pane.appendChild(row);

  const queryInput = document.getElementById("filter-search");

  const update = () => {
    row.innerHTML = "";
    const q = (queryInput.value || "").toLowerCase();

    const categoryData = itemsData[cat];
    if (!categoryData || typeof categoryData !== "object") return;

    const displayConfig = categoryData._display || {}; // map { subcat: { type, rowPerField, idField } }

    // Affiche chaque sous-catégorie qui est un Array
    Object.entries(categoryData).forEach(([subcat, entries]) => {
      if (subcat === "_display") return; // méta, pas de rendu direct

      if (Array.isArray(entries)) {
        const meta = normalizeDisplayMeta(displayConfig[subcat]);

        if (meta.type === "table") {
          renderAsTable(entries, subcat, meta, q, row);
        } else {
          renderAsCards(entries, subcat, q, row);
        }
      }
      // les autres clés (objets non-array) ne sont pas rendues (typiquement: sous-containers)
    });
  };

  queryInput.addEventListener("input", update);
  update();

  window.scrollTo({ top: 0, behavior: "smooth" });
}

// -- Helpers -----------------------------------------------------------------

function normalizeDisplayMeta(raw) {
  if (raw === "table") return { type: "table", rowPerField: true, idField: undefined, columns: undefined, columnLabels: undefined };
  if (typeof raw === "object" && raw) {
    return {
      type: raw.type === "table" ? "table" : "cards",
      rowPerField: raw.rowPerField === true,
      idField: raw.idField,
      columns: Array.isArray(raw.columns) ? raw.columns : undefined,        // ordre/filtre colonnes (mode colonne)
      columnLabels: raw.columnLabels && typeof raw.columnLabels === "object" ? raw.columnLabels : undefined // { key: "Label" }
    };
  }
  return { type: "cards" };
}

function renderAsCards(entries, subcat, q, rowEl) {
  entries.forEach(obj => {
    if (typeof obj !== "object" || !obj) return;

    const name = obj.Item || obj["Ball Name"] || obj["Herb Type"] || obj["Apricorn Type"] || obj["Tier"] || "???";

    if (
      q &&
      !name.toLowerCase().includes(q) &&
      !Object.values(obj).some(v => v && v.toString().toLowerCase().includes(q))
    ) return;

    const col = document.createElement("div");
    col.className = `col-12 col-md-${edgeColSize}`;

    const card = document.createElement("div");
    card.className = "card h-100 bg-white border shadow-sm";

    const body = document.createElement("div");
    body.className = "card-body bg-light";

    body.insertAdjacentHTML(
      "beforeend",
      `<h5 class="card-title">${escapeHTML(name)} <span class="badge bg-secondary">${escapeHTML(subcat)}</span></h5>`
    );

    Object.entries(obj).forEach(([k, v]) => {
      if (["Item", "Ball Name", "Herb Type", "Apricorn Type", "Tier"].includes(k)) return;
      body.insertAdjacentHTML("beforeend", `<p><strong>${escapeHTML(k)}:</strong> ${escapeHTML(String(v))}</p>`);
    });

    card.appendChild(body);
    col.appendChild(card);
    rowEl.appendChild(col);
  });
}

function renderAsTable(entries, subcat, meta, q, rowEl) {
  const filtered = entries.filter(obj => {
    if (!q) return true;
    const hay = Object.values(obj).map(v => (v == null ? "" : String(v).toLowerCase())).join(" ");
    return hay.includes(q);
  });
  if (filtered.length === 0) return;

  const col = document.createElement("div");
  col.className = "col-12";

  const card = document.createElement("div");
  card.className = "card h-100 bg-white border shadow-sm";

  const body = document.createElement("div");
  body.className = "card-body bg-light";
  body.insertAdjacentHTML(
    "afterbegin",
    `<h5 class="card-title">${escapeHTML(subcat)} <span class="badge bg-info">Table</span></h5>`
  );

  /* --- wrapper responsive pour scroll horizontal si nécessaire --- */
  const wrap = document.createElement("div");
  wrap.className = "table-responsive";

  const table = document.createElement("table");
  table.className = "table table-sm table-striped mb-0 items-table";
  if (meta.rowPerField) table.classList.add("items-table--transposed");

  /* === MODE COLONNE ====================================================== */
  if (!meta.rowPerField) {
    let cols;
    if (meta.columns) {
      cols = meta.columns.filter(k => filtered.some(e => Object.prototype.hasOwnProperty.call(e, k)));
      const union = new Set();
      filtered.forEach(e => Object.keys(e).forEach(k => union.add(k)));
      [...union].forEach(k => { if (!cols.includes(k)) cols.push(k); });
    } else {
      const union = new Set();
      filtered.forEach(e => Object.keys(e).forEach(k => union.add(k)));
      cols = [...union];
    }

    /* --- (NOUVEAU) pilotage optionnel des largeurs via meta.columnWidths --- */
    if (Array.isArray(meta.columnWidths) && meta.columnWidths.length) {
      const cg = document.createElement("colgroup");
      cols.forEach((_, i) => {
        const c = document.createElement("col");
        const w = meta.columnWidths[i] || meta.columnWidths[meta.columnWidths.length - 1];
        if (w) c.style.width = w;          // ex. '8ch', '12rem', '120px', '20%'
        cg.appendChild(c);
      });
      table.appendChild(cg);
    }

    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    cols.forEach(k => {
      const th = document.createElement("th");
      const label = (meta.columnLabels && meta.columnLabels[k]) || k;
      th.textContent = label;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    filtered.forEach(obj => {
      const tr = document.createElement("tr");
      cols.forEach(k => {
        const td = document.createElement("td");
        const v = obj[k];
        td.innerHTML = v == null ? "—" : escapeHTML(String(v));
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    wrap.appendChild(table);
    body.appendChild(wrap);
    card.appendChild(body);
    col.appendChild(card);
    rowEl.appendChild(col);
    return;
  }

  /* === MODE TRANSPOSE (lignes = champs) ================================== */
  const idField = resolveIdField(meta.idField, filtered);
  const rowKeysOrdered = collectRowKeys(filtered, idField);

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");

  // (NOUVEAU) colgroup avec largeur fixe pour la première colonne (labels)
  const cg = document.createElement("colgroup");
  const colLabel = document.createElement("col");
  colLabel.style.width = "18ch";
  cg.appendChild(colLabel);

  filtered.forEach(() => {
    const c = document.createElement("col");
    cg.appendChild(c);
  });
  table.appendChild(cg);

  headRow.appendChild(document.createElement("th"));
  filtered.forEach((obj, idx) => {
    const hdr = document.createElement("th");
    const label = idField && obj[idField] != null ? String(obj[idField]) : `#${idx + 1}`;
    hdr.textContent = label;
    headRow.appendChild(hdr);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  rowKeysOrdered.forEach(k => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.textContent = k;
    tr.appendChild(th);

    filtered.forEach(obj => {
      const td = document.createElement("td");
      const val = obj[k];
      td.innerHTML = val == null ? "—" : escapeHTML(String(val));
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  wrap.appendChild(table);
  body.appendChild(wrap);
  card.appendChild(body);
  col.appendChild(card);
  rowEl.appendChild(col);
}


function resolveIdField(preferred, entries) {
  if (preferred && entries.some(e => preferred in e)) return preferred;

  // Trouver la clé qui a le plus de valeurs distinctes
  const keyCounts = {};
  entries.forEach(e => {
    Object.keys(e).forEach(k => {
      keyCounts[k] = keyCounts[k] || new Set();
      keyCounts[k].add(e[k]);
    });
  });

  let best = null;
  let maxDistinct = 0;
  for (const [k, set] of Object.entries(keyCounts)) {
    if (set.size > maxDistinct) {
      best = k;
      maxDistinct = set.size;
    }
  }
  return best; // null si rien trouvé
}


function collectRowKeys(entries, idField) {
  const seen = new Set();
  const out = [];
  const push = k => { if (!seen.has(k)) { seen.add(k); out.push(k); } };

  // ordre stable : clés du premier, puis union des suivantes
  entries.forEach(e => {
    Object.keys(e).forEach(k => {
      if (k === idField) return;
      push(k);
    });
  });
  return out;
}

function escapeHTML(str) {
  return str
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

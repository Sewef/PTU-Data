(function () {
  const CFG = {
    // NEW — libellés → URL (tu peux en ajouter/retirer)
    sources: {
      "Core (Gen 1-6)":      "/ptu/data/pokedex/pokedex_core.json",
      "AlolaDex (Gen 7)":  "/ptu/data/pokedex/pokedex_7g.json",
      "GalarDex (Gen 8)":  "/ptu/data/pokedex/pokedex_8g.json",
      "HisuiDex (Gen 8.5)":  "/ptu/data/pokedex/pokedex_8g_hisui.json",
      "PaldeaDex (Gen 9, Homebrew)": "/ptu/data/pokedex/pokedex_9g.json",
    },
    // NEW — patterns d’icônes inchangés
    iconPatterns: [
      (base, num) => `${base}/${num}.png`
    ]
  };

    // NEW — état UI/cache
  const selectedSources = new Set(Object.keys(CFG.sources));   // par défaut: tout coché
  const _jsonCache = new Map(); // url -> Promise(data[])

  let dexModalInstance = null;

  function getDexModalInstance() {
    const el = document.getElementById('dexModal');
    if (!el) return null;
    // Réutilise l’instance existante si présente
    dexModalInstance = bootstrap.Modal.getOrCreateInstance(el, {
      backdrop: true,
      focus: true,
      keyboard: true
    });
    return dexModalInstance;
  }


  function isDexModalShown() {
    const el = document.getElementById('dexModal');
    return !!el && el.classList.contains('show');
  }


  // Utilities
  const pad3 = n => String(n).padStart(3, '0');
  const slugify = s => (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  const $ = (sel) => document.querySelector(sel);

  // ===== Types helpers (handle array OR per-form object) =====
  function debounce(fn, delay = 150) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), delay); } }
  const jsStr = s => JSON.stringify(String(s ?? ''));

    // NEW — charge 1 source avec cache
  async function fetchSource(url) {
    if (_jsonCache.has(url)) return _jsonCache.get(url);
    const prom = fetch(url, { cache: "no-store" })
      .then(r => { if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.json(); })
      .then(data => Array.isArray(data) ? data : (Array.isArray(data?.Pokedex) ? data.Pokedex : []))
      .catch(e => { console.warn("Load error", url, e); return []; });
    _jsonCache.set(url, prom);
    return prom;
  }


  // Load JSON with graceful fallbacks
  async function loadPokedex() {
    const urls = [...selectedSources].map(lbl => CFG.sources[lbl]).filter(Boolean);
    const arrays = await Promise.all(urls.map(fetchSource));

    const merged = arrays.flat();
    const byKey = new Map();
    for (const p of merged) {
      const key = `${p.Number ?? ''}::${String(p.Species ?? '').toLowerCase()}`;
      byKey.set(key, { ...(byKey.get(key) || {}), ...p });
    }
    const out = Array.from(byKey.values());
    if (!out.length) throw new Error("Aucune entrée trouvée pour les sources sélectionnées.");
    return out;
  }

  
  // NEW — bloc “Sources” au-dessus des filtres (même esprit que Edges)
  function buildSourceMenu(onChange) {
    const sb = document.getElementById('sidebar');
    if (!sb) return;
    // Conteneur dédié (on le régénère, puis on laissera buildTypeSidebar ajouter ses filtres en dessous)
    const wrap = document.createElement('div');
    wrap.className = 'mb-3';
    wrap.innerHTML = `<label class="form-label">Sources :</label>`;
    Object.keys(CFG.sources).forEach(label => {
      const id = `src-${label}`;
      const checked = selectedSources.has(label) ? 'checked' : '';
      wrap.insertAdjacentHTML('beforeend', `
        <div class="form-check">
          <input class="form-check-input" type="checkbox" id="${id}" ${checked}>
          <label class="form-check-label" for="${id}">${label}</label>
        </div>`);
    });

    // Si un bloc “sources” existe déjà, remplace-le ; sinon, insère en haut
    const existing = sb.querySelector('[data-role="source-menu"]');
    if (existing) existing.remove();
    wrap.setAttribute('data-role', 'source-menu');
    sb.prepend(wrap);

    wrap.querySelectorAll('input[type="checkbox"]').forEach(cb => {
      cb.addEventListener('change', async () => {
        // maj état
        selectedSources.clear();
        wrap.querySelectorAll('input:checked').forEach(x => {
          const lbl = x.nextElementSibling?.innerText?.trim();
          if (lbl) selectedSources.add(lbl);
        });

        // recharge les données puis reconstruit filtres + grid
        try {
          const data = await loadPokedex();
          window.__POKEDEX = data;
          // reconstruit les filtres de types en dessous (en gardant layout)
          buildTypeSidebar(data, () => renderGrid(filterRows(data)));
          renderGrid(filterRows(data));
        } catch (e) {
          console.error(e);
          document.getElementById('dex-grid').innerHTML =
            `<div class="alert alert-warning">Aucune donnée pour les sources sélectionnées.</div>`;
        }
        if (typeof onChange === 'function') onChange();
      });
    });
  }

  // Cherche un Pokémon par son nom complet et ouvre la modale
  async function openModalBySpecies(speciesName) {
    // Charger le Pokédex si ce n’est pas déjà fait
    const data = await loadPokedex();

    // Trouver l’objet correspondant
    const found = data.find(p =>
      (p.Species || '').toLowerCase() === speciesName.toLowerCase()
    );

    if (found) {
      openDetail(found);
    } else {
      alert(`Aucun Pokémon trouvé avec le nom "${speciesName}"`);
    }
  }



  // Derive flat list of distinct types present + robust form handling
  function extractTypes(p) {
    const t = p?.['Basic Information']?.Type;
    if (Array.isArray(t)) {
      // cas 1: ["Electric", "Fire"]
      if (t.length && typeof t[0] === 'string') return t;
      // cas 2: [ { "Heat Rotom": ["Electric","Fire"], ... } ]
      if (t.length && typeof t[0] === 'object') {
        const vals = Object.values(t[0]).flatMap(v => Array.isArray(v) ? v : []);
        return Array.from(new Set(vals));
      }
      return [];
    }
    if (t && typeof t === 'object') {
      const vals = Object.values(t).flatMap(v => Array.isArray(v) ? v : []);
      return Array.from(new Set(vals));
    }
    return [];
  }


  function wrapTypes(t) {
    if (!t) return '';
    if (typeof t === 'string') return t;    // déjà formaté → renvoyer tel quel
    if (!Array.isArray(t)) t = [t];         // sécurise si jamais
    return t.map(x => `<span class="type-pill card-type-${x}">${x}</span>`).join('');
  }

  function renderFormType(val) {
    if (!val) return '';
    if (typeof val === 'string') return val;   // déjà formaté
    if (Array.isArray(val)) return wrapTypes(val);
    if (typeof val === 'object') {
      return Object.entries(val).map(([form, types]) =>
        `<div class="mb-1"><span class="fw-semibold">${form}</span> : ${wrapTypes(types)}</div>`
      ).join('');
    }
    return String(val ?? '');
  }

  function collectTypes(rows) {
    const set = new Set();
    rows.forEach(r => extractTypes(r).forEach(t => set.add(t)));
    return Array.from(set).sort();
  }

  // Sidebar builder (mirrors your moves sidebar UX)
  // Seule petite adaptation: buildTypeSidebar ne doit plus effacer tout le #sidebar
  // mais compléter sous le bloc “Sources”. On remplace son début :
  function buildTypeSidebar(all, onChange) {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    // NEW — supprime juste l’ancien bloc types s’il existe
    const oldTypes = sidebar.querySelector('[data-role="type-filters"]');
    if (oldTypes) oldTypes.remove();

    const typesBox = document.createElement('div');
    typesBox.setAttribute('data-role', 'type-filters');
    const types = collectTypes(all);
    typesBox.innerHTML = `
      <label class="form-label mt-2">Types :</label>
      <div class="mb-2">
        <input id="sidebar-search" class="form-control form-control-sm mb-2" placeholder="Filter types..."/>
        <button id="toggle-all-types" class="btn btn-sm btn-primary w-100 mb-2">Select/Deselect all</button>
      </div>
      <div id="type-filters" class="list-group">
        ${types.map(type => `
          <label class="list-group-item card-type-${type}">
            <input class="form-check-input me-1" type="checkbox" value="${type}">
            ${type}
          </label>
        `).join('')}
      </div>`;

    // NEW — insère sous le menu des sources
    const srcMenu = sidebar.querySelector('[data-role="source-menu"]');
    if (srcMenu) srcMenu.insertAdjacentElement('afterend', typesBox);
    else sidebar.prepend(typesBox);

    // (le reste de la fonction inchangé)
    typesBox.querySelectorAll("#type-filters input[type='checkbox']").forEach(input => {
      input.addEventListener('change', onChange);
    });

    const sb = document.getElementById('sidebar-search');
    if (sb) sb.addEventListener('input', debounce(() => {
      const q = sb.value.toLowerCase();
      typesBox.querySelectorAll('#type-filters label').forEach(label => {
        label.style.display = label.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    }, 150));

    const toggle = document.getElementById('toggle-all-types');
    if (toggle) toggle.addEventListener('click', () => {
      const boxes = typesBox.querySelectorAll("#type-filters input[type='checkbox']");
      const allChecked = Array.from(boxes).every(cb => cb.checked);
      boxes.forEach(cb => cb.checked = !allChecked);
      onChange();
    });
  }

  function activeTypes() {
    return Array.from(document.querySelectorAll('#type-filters input:checked')).map(el => el.value);
  }

  // Build the grid of small badges
  function renderGrid(rows) {
    const grid = document.getElementById('dex-grid');
    grid.innerHTML = '';
    const frag = document.createDocumentFragment();

    rows.forEach(p => {
      const name = p.Species || 'Unknown';
      const num = pad3(p.Number ?? '0');
      const types = extractTypes(p);

      const li = document.createElement('div');
      li.className = 'dex-badge';
      li.dataset.types = types.join(','); // ← on garde les types pour plus tard

      // icône
      const iconWrap = document.createElement('div');
      iconWrap.className = 'icon dark-background';
      const img = document.createElement('img');
      setupIcon(img, p.Icon || p.Number, name, "icon");
      iconWrap.appendChild(img);
      li.appendChild(iconWrap);

      const numBadge = document.createElement('div');
      numBadge.className = 'dex-num-badge';
      numBadge.textContent = `#${num}`;
      li.appendChild(numBadge);

      const label = document.createElement('div');
      label.className = 'dex-label';
      label.textContent = name;
      li.appendChild(label);

      li.addEventListener('click', () => openDetail(p));
      frag.appendChild(li);
    });

    grid.appendChild(frag);

    // Laisse le browser attacher/calculer, puis applique les styles
    requestAnimationFrame(() => {
      grid.querySelectorAll('.dex-badge').forEach(el => {
        const types = el.dataset.types ? el.dataset.types.split(',') : [];
        applyBadgeBackground(el, types);
      });
    });
  }

  // Background mono or bi-color based on types
  function applyBadgeBackground(el, types) {
    if (!types || types.length === 0) {
      el.style.background = '#151922';
      return;
    }

    if (types.length === 1) {
      el.classList.add(`card-type-${types[0]}`);
      el.style.background = `var(--type-color)`;
      el.style.color = '#0f1115';
      el.style.borderColor = 'rgba(255,255,255,.15)';
    } else {
      // Couleur 1
      el.classList.add(`card-type-${types[0]}`);
      const c1 = getComputedStyle(el).getPropertyValue('--type-color')?.trim() || '#333';
      el.classList.remove(`card-type-${types[0]}`);

      // Couleur 2
      el.classList.add(`card-type-${types[1]}`);
      const c2 = getComputedStyle(el).getPropertyValue('--type-color')?.trim() || '#444';
      el.classList.remove(`card-type-${types[1]}`);

      // Deux moitiés nettes, pas de mélange
      el.style.background = `linear-gradient(90deg, ${c1} 50%, ${c2} 50%)`;
      el.style.borderColor = 'rgba(255,255,255,.15)';
    }
  }

  function setupIcon(img, num, name, mode = "icon") {
    // mode = "icon" ou "full"
    const slug = slugify(name || '');
    const base = mode === "full" ? "/ptu/img/pokemon/full" : "/ptu/img/pokemon/icons";

    img.src = CFG.iconPatterns.map(fn => fn(base, num, slug));
  }



  function openDetail(p) {
    const body = document.getElementById('dexModalBody');
    const title = document.getElementById('dexModalLabel');
    const num = String(p.Number ?? '0').padStart(3, '0');
    const species = p.Species || 'Unknown';

    const typesHTML = wrapTypes(extractTypes(p)) || '';

    title.innerHTML = `
    <div class="d-flex align-items-start gap-3 w-100">
      <img id="dexModalIcon" class="dex-title-icon rounded dark-background p-1" width="64" height="64" alt="${species}">
      <div class="flex-grow-1">
        <div class="d-flex flex-wrap align-items-baseline gap-2">
          <span class="h5 mb-0">#${num} — ${species}</span>
        </div>
        <div class="dex-title-types mt-1">${typesHTML}</div>
      </div>
    </div>
  `;

    const safe = (typeof structuredClone === 'function')
      ? structuredClone(p)
      : JSON.parse(JSON.stringify(p));
    body.innerHTML = renderObject(safe);

    const img = document.getElementById('dexModalIcon');
    if (img) setupIcon(img, p.Icon || p.Number, species, "full");

    // 👉 Réutiliser l’instance, et ne montrer que si fermée
    const inst = getDexModalInstance();
    if (inst && !isDexModalShown()) {
      inst.show();
    } else if (inst) {
      inst.handleUpdate(); // ajuste le scroll/position, sans recréer de backdrop
    }
  }




  // --- helpers ---
  function renderLevelUpMoves(moves) {
    if (!Array.isArray(moves) || !moves.length) return '';
    return `
    <ul class="list-unstyled mb-0">
      ${moves.map(m => `
        <li class="d-flex align-items-center mb-1">
          <span class="text-muted" style="width:50px;">Lv.${m.Level}</span>
          <span class="fw-semibold flex-grow-1">${m.Move}</span>
          ${wrapTypes([m.Type])}
        </li>
      `).join('')}
    </ul>`;
  }
  function renderStringList(title, arr) {
    if (!Array.isArray(arr) || !arr.length) return '';
    return `
    <div class="mt-3">
      <h5 class="text-muted">${title}</h5>
      <ul class="list-unstyled mb-0">
        ${arr.join(', ')}
      </ul>
    </div>`;
  }

  function renderCapabilities(raw, depth = 0) {
    // Normalise toute source vers { rated:[{key,value}], simple:[string] }
    const parsed = parseCapabilities(raw);
    if (!parsed.rated.length && !parsed.simple.length) return '';

    const h = Math.min(4 + depth, 6);

    // Cartes "numériques"
    const rated = parsed.rated.map(({ key, value }) => {
      return `
      <div class="cap-item">
        <div class="cap-head">
          <span class="cap-key">${key}</span>
        </div>
        <div class="cap-val">${value}</div>
      </div>
    `;
    }).join('');

    // Chips "simples"
    const simple = parsed.simple.map(k => {
      return `<span class="cap-chip"><span>${k}</span></span>`;
    }).join('');

    return `
    <div class="mt-3">
      <h${h} class="text-muted">Capabilities</h${h}>
      <div class="card accent">
        <div class="card-body">
          ${parsed.rated.length ? `<div class="cap-grid">${rated}</div>` : ''}
          ${parsed.simple.length ? `<div class="cap-chips">${simple}</div>` : ''}
        </div>
      </div>
    </div>
  `;
  }

  function parseCapabilities(raw) {
    const rated = [];
    const simple = [];

    const pushPair = (k, v) => {
      const key = String(k).trim();
      const val = Number(v);
      if (key && Number.isFinite(val)) rated.push({ key: key, value: val });
      else if (key) simple.push(key);
    };

    const fromString = (s) => {
      const str = String(s).trim();
      if (!str) return;
      // "Overland 5" / "Sky 2" / "Long Jump 2" / "Swim 3" …
      const m = str.match(/^(.+?)\s+(-?\d+(?:\.\d+)?)\s*$/);
      if (m) pushPair(m[1], m[2]);
      else simple.push(str);
    };

    if (Array.isArray(raw)) {
      raw.forEach(item => {
        if (item == null) return;
        if (typeof item === 'string') fromString(item);
        else if (typeof item === 'object') {
          Object.entries(item).forEach(([k, v]) => pushPair(k, v));
        } else fromString(item);
      });
    } else if (typeof raw === 'object' && raw) {
      Object.entries(raw).forEach(([k, v]) => {
        if (Array.isArray(v)) v.forEach(x => (typeof x === 'string' ? fromString(`${k} ${x}`) : pushPair(k, x)));
        else if (typeof v === 'string') fromString(`${k} ${v}`);
        else pushPair(k, v);
      });
    } else if (raw != null) {
      fromString(raw);
    }

    // Regrouper les doublons (somme si mêmes clés numériques)
    const acc = new Map();
    rated.forEach(({ key, value }) => acc.set(key, (acc.get(key) ?? 0) + value));
    const ratedMerged = [...acc.entries()].map(([key, value]) => ({ key, value }));

    // Nettoyage chips
    const simpleClean = [...new Set(simple.filter(Boolean))];

    return { rated: ratedMerged, simple: simpleClean };
  }
  function renderBaseStats(stats, depth = 0) {
    const order = ["HP", "Attack", "Defense", "Special Attack", "Special Defense", "Speed"];

    // Cas simple
    if (!("Small" in stats)) {
      const total = order.reduce((s, k) => s + (stats?.[k] ?? 0), 0);
      const rows = order.map(k => `
      <tr>
        <td class="text-start">${k}</td>
        <td class="text-end">${stats?.[k] ?? 0}</td>
      </tr>
    `).join("");
      return `
      <div class="mt-3">
        <h${Math.min(4 + depth, 6)} class="text-muted">Base Stats</h${Math.min(4 + depth, 6)}>
        <table class="table table-sm align-middle">
          <tbody>
            ${rows}
            <tr class="fw-semibold">
              <td class="text-start">Total</td>
              <td class="text-end">${total}</td>
            </tr>
          </tbody>
        </table>
      </div>
    `;
    }

    // Cas multi-tailles
    const forms = {
      "Small": "S",
      "Average": "M",
      "Large": "L",
      "Super Size": "XL"
    };
    const totals = {};
    Object.keys(forms).forEach(f => {
      totals[f] = order.reduce((s, k) => s + (stats[f]?.[k] ?? 0), 0);
    });

    const rows = order.map(k => `
    <tr>
      <td class="text-start">${k}</td>
      ${Object.keys(forms).map(f => `<td class="text-center">${stats[f]?.[k] ?? 0}</td>`).join("")}
    </tr>
  `).join("");

    return `
    <div class="mt-3">
      <h${Math.min(4 + depth, 6)} class="text-muted">Base Stats</h${Math.min(4 + depth, 6)}>
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th class="text-start"></th>
            ${Object.values(forms).map(lbl => `<th class="text-center">${lbl}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${rows}
          <tr class="fw-semibold">
            <td class="text-start">Total</td>
            ${Object.keys(forms).map(f => `<td class="text-center">${totals[f]}</td>`).join("")}
          </tr>
        </tbody>
      </table>
    </div>
  `;
  }


  function renderSkills(skills, depth = 0) {
    // skills est supposé être un objet { "Acrobatics": 2, "Combat": 3, ... }

    const entries = Object.entries(skills || {});
    const rows = entries.map(([k, v]) => `
    <li class="list-group-item d-flex justify-content-between align-items-center">
      <span class="skill-key">${k}</span>
      <span class="skill-val">${v}</span>
    </li>
  `).join("");

    const h = Math.min(4 + depth, 6);
    return `
    <div class="mt-3">
      <h${h} class="text-muted">Skills</h${h}>
      <div class="card accent skills-card">
        <ul class="list-group list-group-flush skills-list">
          ${rows}
        </ul>
      </div>
    </div>
  `;
  }
  function renderEvolutionList(evos, depth = 0) {
    // evos attendu: [{ Stade, Species, Condition }]
    if (!Array.isArray(evos) || evos.length === 0) return '';

    const items = evos.map(e => {
      const stade = e?.Stade ?? '';
      const species = e?.Species ?? '';
      const cond = (e?.Condition ?? '').trim();
      const label = `${stade} - <a href="#" onclick='openModalBySpecies(${jsStr(species)}); return false;'>${escapeHtml(species)}</a>${cond ? ` (${escapeHtml(cond)})` : ''}`;
      return `
      <li class="list-group-item d-flex align-items-center">
        <span class="flex-grow-1">${label}</span>
      </li>`;
    }).join('');

    const h = Math.min(4 + depth, 6);
    return `
    <div class="mt-3">
      <h${h} class="text-muted">Evolution</h${h}>
      <div class="card accent skills-card">
        <ul class="list-group list-group-flush skills-list">
          ${items}
        </ul>
      </div>
    </div>`;
  }


  function renderBattleOnlyForms(forms, base) {
    if (!forms || typeof forms !== "object") return "";
    const pNum = base?.Number ?? "", pName = base?.Species ?? "Unknown";

    return Object.entries(forms).map(([label, f]) => {
      const src = (() => {
        const t = document.createElement("img");
        console.log(f);
        setupIcon(t, f?.Icon ?? pNum, `${pName} — ${label}`, "full");
        return t.src;
      })();


      const types = wrapTypes(f?.Type || []);
      const line = k => f?.[k] ? `<div class="small text-muted">${k}: <span class="text-body">${Array.isArray(f[k]) ? f[k].join(", ")
        : (typeof f[k] === "object" ? Object.keys(f[k]).join(", ") : String(f[k]))
        }</span></div>` : "";

      const stats = f?.Stats ? Object.entries(f.Stats)
        .map(([k, v]) => `<div class="d-flex justify-content-between small border-bottom">
        <span class="text-muted">${k}</span><span class="fw-semibold">${v}</span>
      </div>`).join("") : "";

      return `
      <div class="card accent w-100 mb-2"><div class="card-body">
        <div class="d-flex align-items-start gap-3">
          <div class="rounded dark-background p-1">
            <img class="dex-title-icon" src="${src}">
          </div>
          <div class="flex-grow-1">
            <div class="d-flex flex-wrap align-items-baseline gap-2">
              <span class="fw-semibold">${label}</span><span class="ms-1">${types}</span>
            </div>
            ${line("Ability")}${line("Adv Ability 1")}${line("Adv Ability 2")}${line("Capabilities")}
            ${stats ? `<div class="mt-2">${stats}</div>` : ""}
          </div>
        </div>
      </div></div>`;
    }).join("");
  }


  function renderObject(obj, depth = 0) {
    // Dispatch: left column for “main” sections
    const leftSections = new Set([
      "Base Stats", "Basic Information", "Evolution", "Other Information", "Battle-Only Forms"
    ]);

    // null/undefined → nothing
    if (obj == null) return '';

    // Arrays
    if (Array.isArray(obj)) {
      if (obj.length === 0) return ''; // skip empty array
      // Render each item; keep only non-empty items
      const items = obj.map(v => {
        if (typeof v === 'object') {
          const inner = renderObject(v, depth + 1);
          return inner.trim() ? `<li>${inner}</li>` : '';
        }
        return `<li>${escapeHtml(String(v))}</li>`;
      }).filter(Boolean);
      if (items.length === 0) return ''; // all items were empty
      return `<ul>${items.join('')}</ul>`;
    }

    // Objects
    if (typeof obj === 'object') {
      // ROOT: build two columns
      if (depth === 0) {
        let col1 = '';
        let col2 = '';
        for (const [k, v] of Object.entries(obj)) {
          if (["Species", "Number", "Icon"].includes(k)) continue; // already shown elsewhere

          // --- special cases / skips you control ---
          // Render Type
          if (k === 'Basic Information' && v?.Type) {
            const t = v.Type;
            if (Array.isArray(t)) {
              if (t.length && typeof t[0] === 'string') {
                v.Type = wrapTypes(t); // ex: ["Electric","Fire"]
              } else if (t.length && typeof t[0] === 'object') {
                v.Type = renderFormType(t[0]); // ex: [ { Form: [types], ... } ]
              } else {
                v.Type = '';
              }
            } else {
              v.Type = renderFormType(t); // compat: objet simple { Form: [...] }
            }
          }

          // --- Base Stats en grille 2x3 ---
          if (k === "Base Stats" && v && typeof v === "object") {
            const block = renderBaseStats(v, depth);
            (leftSections.has(k) ? (col1 += block) : (col2 += block));
            continue;
          }

          // --- Evolution -> liste cliquable ---
          if (k === "Evolution" && Array.isArray(v)) {
            const block = renderEvolutionList(v, depth);
            (leftSections.has(k) ? (col1 += block) : (col2 += block));
            continue;
          }

          // --- Capabilities (layout spécial) ---
          if (k === "Capabilities" && v) {
            const block = renderCapabilities(v, depth);
            if (block.trim()) {
              (leftSections.has(k) ? (col1 += block) : (col2 += block));
            }
            continue;
          }

          // --- Skills ---
          if (k === "Skills" && v && typeof v === "object") {
            const block = renderSkills(v, depth);
            (leftSections.has(k) ? (col1 += block) : (col2 += block));
            continue;
          }


          // Render Level Up Move List
          if (k === "Moves" && v) {
            let blocks = '';
            blocks += v["Level Up Move List"] ? `
            <div class="mt-3">
              <h5 class="text-muted">Level-Up Moves</h5>
              ${renderLevelUpMoves(v["Level Up Move List"])}
            </div>` : '';
            blocks += renderStringList('TM/HM Moves', v["TM/HM Move List"]);
            blocks += renderStringList('Egg Moves', v["Egg Move List"]);
            blocks += renderStringList('Tutor Moves', v["Tutor Move List"]);
            blocks += renderStringList('TM/Tutor Moves', v["TM/Tutor Moves List"]);

            if (blocks.trim()) {
              const h = Math.min(4 + depth, 6);
              const card = `
              <div class="mt-3">
                <h${h} class="text-muted">Moves</h${h}>
                <div class="card accent" style="--accent-color: rgba(255,255,255,.08);">
                  <div class="card-body">${blocks}</div>
                </div>
              </div>`;
              (leftSections.has(k) ? (col1 += card) : (col2 += card));
            }
            continue;
          }

          // --- Battle-Only Forms : micro-fiches pleine largeur ---
          if (k === "Battle-Only Forms" && v && typeof v === "object") {
            const html = renderBattleOnlyForms(v, obj);
            if (html.trim()) {
              const h = Math.min(4 + depth, 6);
              const card = `
              <div class="mt-3">
                <h${h} class="text-muted">Battle-Only Forms</h${h}>
                <div class="card accent" style="--accent-color: rgba(255,255,255,.08);">
                  <div class="card-body">
                    ${html}
                  </div>
                </div>
              </div>`;
              (leftSections.has(k) ? (col1 += card) : (col2 += card));
            }
            continue;
          }
          // Add more hand-written exclusions here as needed
          // ----------------------------------------

          //console.log({ k, v });
          // Build block
          let block = '';
          if (typeof v === 'object' && v !== null) {
            const inner = renderObject(v, depth + 1);
            if (!inner.trim()) continue; // child had nothing → skip whole section
            const h = Math.min(4 + depth, 6);
            block = `
            <div class="mt-3">
              <h${h} class="text-muted">${k}</h${h}>
              <div class="card accent" style="--accent-color: rgba(255,255,255,.08);">
                <div class="card-body">
                  ${inner}
                </div>
              </div>
            </div>`;
          } else {
            // scalar
            block = `
            <div class="row border-bottom py-1">
              <div class="col-4 fw-semibold">${k}</div>
              <div class="col-8">${v}</div>
            </div>`;
          }

          (leftSections.has(k) ? (col1 += block) : (col2 += block));
        }

        // If both columns empty, return empty (lets parent skip the wrapper)
        const hasAny = (col1.trim() || col2.trim());
        if (!hasAny) return '';

        return `
        <div class="row">
          <div class="col-md-6">${col1}</div>
          <div class="col-md-6">${col2}</div>
        </div>`;
      }

      // NESTED (depth > 0): render as a single column, skipping empties
      let html = '';
      for (const [k, v] of Object.entries(obj)) {
        // generic skip of empty arrays/objects
        if (Array.isArray(v) && v.length === 0) continue;
        if (v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === 0) continue;

        if (typeof v === 'object' && v !== null) {
          const inner = renderObject(v, depth + 1);
          if (!inner.trim()) continue; // child had nothing
          const h = Math.min(4 + depth, 6);
          html += `
          <div class="mt-3">
            <h${h} class="text-muted">${k}</h${h}>
            <div class="card accent" style="--accent-color: rgba(255,255,255,.08);">
              <div class="card-body">
                ${inner}
              </div>
            </div>
          </div>`;
        } else {
          html += `
          <div class="row border-bottom py-1">
            <div class="col-4 fw-semibold">${k}</div>
            <div class="col-8">${v}</div>
          </div>`;
        }
      }
      return html;
    }

    // Fallback for primitives (shouldn’t really hit here)
    return escapeHtml(String(obj));
  }

  function escapeHtml(s) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return s.replace(/[&<>"']/g, c => map[c]);
  }

  // Filter logic (text + type chips)
  function filterRows(rows) {
    const q = (document.getElementById('dex-search')?.value || '').trim().toLowerCase();
    const types = activeTypes();
    return rows.filter(p => {
      const name = (p.Species || '').toLowerCase();
      const num = String(p.Number || '');
      const hasQ = !q || name.includes(q) || num.includes(q);
      const pTypes = extractTypes(p);
      const typeOk = types.length === 0 || pTypes.some(t => types.includes(t));
      return hasQ && typeOk;
    }).sort((a, b) => (a.Number || 0) - (b.Number || 0));
  }

  function wireSearch(all) {
    const inp = document.getElementById('dex-search');
    if (inp) inp.addEventListener('input', debounce(() => renderGrid(filterRows(all)), 120));

    document.getElementById('clear-filters')?.addEventListener('click', () => {
      inp.value = '';
      document.querySelectorAll("#type-filters input[type='checkbox']").forEach(cb => cb.checked = false);
      renderGrid(filterRows(all));
    });
  }

  // Boot

    document.addEventListener("DOMContentLoaded", async () => {
    // NEW — construit le menu des sources *avant* de charger
    buildSourceMenu();

    const data = await loadPokedex();
    window.__POKEDEX = data;

    window.openModalBySpecies = (speciesName) => {
      const found = (window.__POKEDEX || []).find(
        p => String(p.Species || '').toLowerCase() === String(speciesName || '').toLowerCase()
      );
      if (found) { openDetail(found); }
    };

    const params = new URLSearchParams(window.location.search);
    const s = params.get("species");
    if (s) openModalBySpecies(s);

    buildTypeSidebar(data, () => renderGrid(filterRows(data)));
    wireSearch(data);
    renderGrid(filterRows(data));
  });
  document.addEventListener('DOMContentLoaded', () => {
    const modalEl = document.getElementById('dexModal');
    if (modalEl) {
      modalEl.addEventListener('hidden.bs.modal', () => {
        // Si jamais Bootstrap ne l’a pas retiré (plugins, CSS custom, etc.)
        document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('paddingRight');
      });
    }
  });

  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[data-dex-number], a[data-dex-species]');
    if (!a) return;

    e.preventDefault();
    const number = a.getAttribute('data-dex-number');
    const species = a.getAttribute('data-dex-species');

    // Récupère ton Pokémon dans tes données (à adapter selon où tu stockes 'data')
    // Exemple si tu as gardé 'data' dans une variable globale/module :
    const target = window.__pokedexData?.find(p =>
      (number && String(p.Number) === String(number)) ||
      (species && String(p.Species).toLowerCase() === String(species).toLowerCase())
    );
    if (target) openDetail(target); // ← met à jour la modale sans réempiler de backdrop
  });
})();

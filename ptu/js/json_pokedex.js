(function () {
  const CFG = {
    // Primary JSON location (mirror your moves.html convention)
    jsonUrls: [
      '/ptu/data/pokedex/pokedex_core.json',
      // '/ptu/data/pokedex/pokedex_7g.json',
      // '/ptu/data/pokedex/pokedex_8g.json',
      // '/ptu/data/pokedex/pokedex_8g_hisui.json',
      '/ptu/data/pokedex/pokedex_9g.json',
    ],
    // Try a few sprite/icon path patterns. Override easily.
    iconPatterns: [
      num => `/ptu/img/pokemon/icons/${num}.png`,              // e.g. 001.png
      num => `/ptu/img/pokemon/icons/${num}.webp`,
      (num, name) => `/ptu/img/pokemon/icons/${slugify(name)}.png`,
      (num, name) => `/ptu/img/pokemon/icons/${slugify(name)}.webp`,
    ],
  };

  // Utilities
  const pad3 = n => String(n).padStart(3, '0');
  const slugify = s => (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  const $ = (sel) => document.querySelector(sel);

  // ===== Types helpers (handle array OR per-form object) =====
  function debounce(fn, delay = 150) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), delay); } }

  // Load JSON with graceful fallbacks
  async function loadPokedex() {
    // 1) Tenter de charger toutes les URLs en parallèle
    const results = await Promise.allSettled(
      CFG.jsonUrls.map(u =>
        fetch(u, { cache: 'no-store' }).then(r => {
          if (!r.ok) throw new Error(`${u}: HTTP ${r.status}`);
          return r.json();
        })
      )
    );

    // 2) Récupérer toutes les arrays trouvées, garder les erreurs pour debug
    const arrays = [];
    const errors = [];
    results.forEach((res, i) => {
      if (res.status === 'fulfilled') {
        const data = res.value;
        if (Array.isArray(data)) {
          arrays.push(data);
        } else if (data && Array.isArray(data.Pokedex)) {
          // au cas où la structure serait { Pokedex: [...] }
          arrays.push(data.Pokedex);
        } else {
          console.warn(`JSON pas au format array pour ${CFG.jsonUrls[i]}`, data);
        }
      } else {
        errors.push(`${CFG.jsonUrls[i]} → ${res.reason}`);
      }
    });

    // 3) Fusion + dédoublonnage (par Number + Species insensible à la casse)
    const merged = arrays.flat();
    const byKey = new Map();
    for (const p of merged) {
      const key = `${p.Number ?? ''}::${String(p.Species ?? '').toLowerCase()}`;
      if (!byKey.has(key)) {
        byKey.set(key, p);
      } else {
        // merge superficiel : les champs du dernier JSON écrasent les précédents
        byKey.set(key, { ...byKey.get(key), ...p });
      }
    }

    const out = Array.from(byKey.values());
    if (out.length === 0) {
      throw new Error(
        'Impossible de charger le Pokédex depuis les URLs configurées.\n' +
        (errors.length ? `Détails:\n- ${errors.join('\n- ')}` : '')
      );
    }

    return out;
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
    console.log(val);
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
  function buildTypeSidebar(all, onChange) {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    const types = collectTypes(all);
    sidebar.innerHTML = `
      <div class="mb-3">
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

    sidebar.querySelectorAll("#type-filters input[type='checkbox']").forEach(input => {
      input.addEventListener('change', onChange);
    });

    const sb = document.getElementById('sidebar-search');
    if (sb) sb.addEventListener('input', debounce(() => {
      const q = sb.value.toLowerCase();
      sidebar.querySelectorAll('#type-filters label').forEach(label => {
        label.style.display = label.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    }, 150));

    const toggle = document.getElementById('toggle-all-types');
    if (toggle) toggle.addEventListener('click', () => {
      const boxes = sidebar.querySelectorAll("#type-filters input[type='checkbox']");
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
      iconWrap.className = 'icon';
      const img = document.createElement('img');
      setupIcon(img, p.Icon || p.Number, name);
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

  // Try multiple icon patterns, fall back to generated SVG initials
  function setupIcon(img, num, name) {
    const tryUrls = CFG.iconPatterns.map(fn => { try { return fn(num, name); } catch { return null; } }).filter(Boolean);
    let idx = 0;

    const fallback = () => {
      const initials = name.replace(/[^A-Z0-9]/gi, ' ').trim().split(/\s+/).slice(0, 2).map(s => s[0]).join('').toUpperCase() || '?';
      const svg = encodeURIComponent(`<?xml version='1.0' encoding='UTF-8'?>\n<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80'>\n  <rect width='100%' height='100%' fill='#0b0d12'/>\n  <text x='50%' y='56%' text-anchor='middle' font-family='Inter,Arial,Helvetica,sans-serif' font-size='34' fill='#eaeef5' opacity='0.8'>${initials}</text>\n</svg>`);
      img.src = `data:image/svg+xml;charset=UTF-8,${svg}`;
    };

    img.addEventListener('error', () => { if (idx < tryUrls.length) img.src = tryUrls[idx++]; else fallback(); });

    img.addEventListener('load', () => {
      const n = Math.max(img.naturalWidth || 0, img.naturalHeight || 0);
      if (n > 64) img.classList.add('is-oversize'); // seulement les 96x96 (ou +) seront réduites
    });

    if (tryUrls.length) img.src = tryUrls[idx++]; else fallback();
  }


  // Detail renderer (generic recursive pretty-printer + a nicer header)
  function openDetail(p) {
    const body = document.getElementById('dexModalBody');
    const title = document.getElementById('dexModalLabel');
    const num = pad3(p.Number ?? '0');

    // header types (reste identique)
    const header = (() => {
      const types = wrapTypes(extractTypes(p));
      return `<div class="mb-3">${types || '<em>—</em>'}</div>`;
    })();
    title.innerHTML = `#${num} — ${p.Species || 'Unknown'}` + header;

    // ⬇️ clone profond pour éviter toute mutation du dataset
    const safe = (typeof structuredClone === 'function')
      ? structuredClone(p)
      : JSON.parse(JSON.stringify(p));

    body.innerHTML = renderObject(safe); // ← on rend le clone
    const modal = new bootstrap.Modal(document.getElementById('dexModal'));
    modal.show();
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


  function renderObject(obj, depth = 0) {
    // Dispatch: left column for “main” sections
    const leftSections = new Set([
      "Base Stats", "Basic Information", "Evolution", "Other Information"
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
              <div class="col-4 fw-bold">${k}</div>
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
            <div class="col-4 fw-bold">${k}</div>
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
  document.addEventListener('DOMContentLoaded', async () => {
    try {
      const data = await loadPokedex(); // Expecting an array of objects
      if (!Array.isArray(data) || !data.length) throw new Error('pokedex_core.json is empty or not an array.');

      buildTypeSidebar(data, () => renderGrid(filterRows(data)));
      wireSearch(data);
      renderGrid(filterRows(data));
    } catch (err) {
      console.error(err);
      const grid = document.getElementById('dex-grid');
      grid.innerHTML = `<div class=\"alert alert-danger\">${escapeHtml(err.message)}</div>`;
    }
  });
})();

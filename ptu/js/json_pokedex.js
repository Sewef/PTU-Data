(function () {
  const CFG = {
    // Primary JSON location (mirror your moves.html convention)
    jsonUrls: [
      '/ptu/data/pokedex/pokedex_core.json', // expected in your project
      './pokedex_core.json',                 // fallback next to page
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
    for (const url of CFG.jsonUrls) {
      try {
        const res = await fetch(url, { cache: 'no-store' });
        if (res.ok) { return res.json(); }
      } catch (e) { /* continue */ }
    }
    throw new Error('Unable to load pokedex_core.json from configured locations');
  }

  // Derive flat list of distinct types present + robust form handling
  function extractTypes(p) {
    const t = p?.['Basic Information']?.Type;
    if (Array.isArray(t)) return t;
    if (t && typeof t === 'object') {
      const vals = Object.values(t).flatMap(v => Array.isArray(v) ? v : []);
      return Array.from(new Set(vals));
    }
    return [];
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
    const tryUrls = CFG.iconPatterns.map(fn => {
      try { return fn(num, name); } catch { return null; }
    }).filter(Boolean);

    let idx = 0;
    const fallback = () => {
      const initials = name.replace(/[^A-Z0-9]/gi, ' ').trim().split(/\s+/).slice(0, 2).map(s => s[0]).join('').toUpperCase() || '?';
      const svg = encodeURIComponent(`<?xml version='1.0' encoding='UTF-8'?>\n<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80'>\n  <rect width='100%' height='100%' fill='#0b0d12'/>\n  <text x='50%' y='56%' text-anchor='middle' font-family='Inter,Arial,Helvetica,sans-serif' font-size='34' fill='#eaeef5' opacity='0.8'>${initials}</text>\n</svg>`);
      img.src = `data:image/svg+xml;charset=UTF-8,${svg}`;
    };

    img.addEventListener('error', () => {
      if (idx < tryUrls.length) { img.src = tryUrls[idx++]; } else fallback();
    }, { once: false });

    // kick off
    if (tryUrls.length) { img.src = tryUrls[idx++]; } else { fallback(); }
  }

  // Detail renderer (generic recursive pretty-printer + a nicer header)
  function openDetail(p) {
    const body = document.getElementById('dexModalBody');
    const title = document.getElementById('dexModalLabel');
    const num = pad3(p.Number ?? '0');

    const header = (() => {
      const types = extractTypes(p);
      const wraps = types.map(t => `<span class=\"type-pill card-type-${t}\">${t}</span>`).join('');
      return `<div class=\"mb-3\">${wraps || '<em>—</em>'}</div>`;
    })();

    title.innerHTML = `#${num} — ${p.Species || 'Unknown'}` + header;

    body.innerHTML = renderObject(p);
    const modal = new bootstrap.Modal(document.getElementById('dexModal'));
    modal.show();
  }

  function renderObject(obj, depth = 0) {
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
          //if (k === 'Basic Information' && v?.Type && Array.isArray(v.Type)) continue; // types are shown in header
          // Add more hand-written exclusions here as needed
          // ----------------------------------------

          console.log({ k, v });
          // Build block
          let block = '';
          if (typeof v === 'object' && v !== null) {
            const inner = renderObject(v, depth + 1);
            if (!inner.trim()) continue; // child had nothing → skip whole section
            const h = Math.min(4 + depth, 6);
            block = `
            <div class="mt-3">
              <h${h} class="text-muted">${escapeHtml(k)}</h${h}>
              <div class="card accent" style="--accent-color: rgba(255,255,255,.08);">
                <div class="card-body">
                  ${inner}
                </div>
              </div>
            </div>`;
          } else {
            // scalar
            const safe = escapeHtml(String(v ?? ''));
            if (!safe) continue; // empty string → skip
            block = `
            <div class="row border-bottom py-1">
              <div class="col-4 fw-bold">${escapeHtml(k)}</div>
              <div class="col-8">${safe}</div>
            </div>`;
          }

          // Dispatch: left column for “main” sections
          const leftSections = new Set([
            "Base Stats", "Basic Information", "Evolution",
            "Size Information", "Breeding Information", "Diet", "Habitat"
          ]);
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
            <h${h} class="text-muted">${escapeHtml(k)}</h${h}>
            <div class="card accent" style="--accent-color: rgba(255,255,255,.08);">
              <div class="card-body">
                ${inner}
              </div>
            </div>
          </div>`;
        } else {
          const safe = escapeHtml(String(v ?? ''));
          if (!safe) continue;
          html += `
          <div class="row border-bottom py-1">
            <div class="col-4 fw-bold">${escapeHtml(k)}</div>
            <div class="col-8">${safe}</div>
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


(function () {
  // =========================
  // Config
  // =========================
  const CFG = {
    iconPatterns: [(base, num) => `${base}/${num}.png`],
    showMethodLabel: false
  };

  // =========================
  // Constants
  // =========================
  const DATASET_BASE = "/ptu/data/pokedex";
  const PRESET_DIRS = { Core: "core", Community: "community", Homebrew: "homebrew" };

  const FILES_BY_LABEL = {
    "Core": "pokedex_core.json",
    "AlolaDex": "pokedex_7g.json",
    "GalarDex": "pokedex_8g.json",
    "HisuiDex": "pokedex_8g_hisui.json",
    "Core (Updated)": "pokedex_core.json",
    "AlolaDex (Updated)": "pokedex_7g.json",
    "GalarDex (Updated)": "pokedex_8g.json",
    "HisuiDex (Updated)": "pokedex_8g_hisui.json",
    "Core (Community Homebrew)": "pokedex_core.json",
    "AlolaDex (Community Homebrew)": "pokedex_7g.json",
    "GalarDex (Community Homebrew)": "pokedex_8g.json",
    "HisuiDex (Community Homebrew)": "pokedex_8g_hisui.json",
    "PaldeaDex (Community Homebrew)": "pokedex_9g.json",
  };

  const PRESETS = {
    Core: ["Core", "AlolaDex", "GalarDex", "HisuiDex"],
    Community: [
      "Core (Community Homebrew)",
      "AlolaDex (Community Homebrew)",
      "GalarDex (Community Homebrew)",
      "HisuiDex (Community Homebrew)",
      "PaldeaDex (Community Homebrew)",
    ],
    Homebrew: [
      "Core (Updated)",
      "AlolaDex (Updated)",
      "GalarDex (Updated)",
      "HisuiDex (Updated)",
      "PaldeaDex (Community Homebrew)",
    ],
  };

  const MOVES_BASE = "/ptu/data/moves";
  const ABILITIES_BASE = "/ptu/data/abilities";

  const MOVES_FILE_BY_PRESET = {
    Core: `${MOVES_BASE}/moves_core.json`,
    Community: `${MOVES_BASE}/moves_9g.json`,
    Homebrew: `${MOVES_BASE}/moves_homebrew.json`
  };
  const ABILITIES_FILE_BY_PRESET = {
    Core: `${ABILITIES_BASE}/abilities_core.json`,
    Community: `${ABILITIES_BASE}/abilities_9g.json`,
    Homebrew: `${ABILITIES_BASE}/abilities_homebrew.json`
  };

  let selectedPreset = window.selectedPreset || "Core";
  let selectedLabels = new Set(PRESETS[selectedPreset] || []);

  // =========================
  // Caches & Utilities
  // =========================
  const _fetchCache = new Map(); // url -> Promise(json)
  const _indexCache = new Map(); // url -> Promise(Map)
  const pad3 = (n) => String(n).padStart(3, "0");
  const slugify = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  const $ = (sel) => document.querySelector(sel);
  const debounce = (fn, delay = 150) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), delay); } };

  const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));

  async function fetchJson(url, { strict = true, cache = "no-store" } = {}) {
    if (!url) return strict ? Promise.reject(new Error("No URL")) : [];
    if (_fetchCache.has(url)) return _fetchCache.get(url);
    const p = fetch(url, { cache })
      .then((r) => {
        if (strict && !r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
        return r.ok ? r.json() : [];
      })
      .catch((e) => {
        console.warn("[fetchJson] skip", url, e.message || e);
        return [];
      });
    _fetchCache.set(url, p);
    return p;
  }

  function urlsForPreset(presetName, onlyLabels) {
    const dir = PRESET_DIRS[presetName];
    const labels = (onlyLabels && onlyLabels.length ? onlyLabels : (PRESETS[presetName] || []));
    return labels.map(lbl => ({
      label: lbl,
      url: `${DATASET_BASE}${DATASET_BASE.endsWith("/") ? "" : "/"}${dir}/${FILES_BY_LABEL[lbl]}`
    }));
  }

  async function loadPokedex() {
    const sources = urlsForPreset(selectedPreset, Array.from(selectedLabels || []));
    if (!sources.length) throw new Error(`No sources for preset ${selectedPreset}`);

    const results = await Promise.all(sources.map(async ({ url }) => {
      const data = await fetchJson(url, { strict: true });
      if (Array.isArray(data)) return data;
      // accept { key: obj } maps
      return data && typeof data === "object" ? Object.values(data) : [];
    }));

    // merge with de-dup (Number::Species)
    const merged = [];
    const seen = new Set();
    for (const arr of results) {
      for (const row of arr) {
        const num = row?.Number ?? row?.number ?? "";
        const sp = row?.Species ?? row?.species ?? "";
        const key = `${num}::${sp}`;
        if (seen.has(key)) continue;
        seen.add(key);
        merged.push(row);
      }
    }
    return merged;
  }

  async function loadIndex(url, nameField) {
    if (_indexCache.has(url)) return _indexCache.get(url);
    const p = fetchJson(url, { strict: false }).then(raw => {
      const idx = new Map();
      if (raw && typeof raw === "object" && !Array.isArray(raw)) {
        // map { "Name": {...}, ... }
        for (const [key, obj] of Object.entries(raw)) {
          if (!obj || typeof obj !== "object") continue;
          const k = key.trim().toLowerCase();
          obj.__displayName = key;
          idx.set(k, obj);
        }
        return idx;
      }
      const arr = Array.isArray(raw) ? raw : [];
      for (const it of arr) {
        const name = (it?.[nameField] || it?.Move || it?.Name || "").trim();
        if (name) {
          it.__displayName = name;
          idx.set(name.toLowerCase(), it);
        }
      }
      return idx;
    });
    _indexCache.set(url, p);
    return p;
  }

  function getMovesUrlForPreset() {
    return MOVES_FILE_BY_PRESET[selectedPreset] || MOVES_FILE_BY_PRESET.Core;
  }
  function getAbilitiesUrlForPreset() {
    return ABILITIES_FILE_BY_PRESET[selectedPreset] || ABILITIES_FILE_BY_PRESET.Core;
  }
  function loadMoveIndex() { return loadIndex(getMovesUrlForPreset(), "Move"); }
  function loadAbilityIndex() { return loadIndex(getAbilitiesUrlForPreset(), "Name"); }

  // =========================
  // Modal helpers
  // =========================
  let dexModalInstance = null;
  function getDexModalInstance() {
    const el = $("#dexModal");
    if (!el) return null;
    dexModalInstance = bootstrap.Modal.getOrCreateInstance(el, { backdrop: true, focus: true, keyboard: true });
    return dexModalInstance;
  }
  function isDexModalShown() {
    const el = $("#dexModal");
    return !!el && el.classList.contains("show");
  }

  // =========================
  // Types & Badges helpers
  // =========================
  function extractTypes(p) {
    const t = p?.["Basic Information"]?.Type;
    if (Array.isArray(t)) {
      if (t.length && typeof t[0] === "string") return t;
      if (t.length && typeof t[0] === "object") {
        const vals = Object.values(t[0]).flatMap(v => Array.isArray(v) ? v : []);
        return Array.from(new Set(vals));
      }
      return [];
    }
    if (t && typeof t === "object") {
      const vals = Object.values(t).flatMap(v => Array.isArray(v) ? v : []);
      return Array.from(new Set(vals));
    }
    return [];
  }

  function wrapTypes(t) {
    if (!t) return "";
    if (typeof t === "string") return t;
    if (!Array.isArray(t)) t = [t];
    return t.map(x => `<span class="type-pill card-type-${x}">${x}</span>`).join("");
  }

  function renderFormType(val) {
    if (!val) return "";
    if (typeof val === "string") return val;
    if (Array.isArray(val)) return wrapTypes(val);
    if (typeof val === "object") {
      return Object.entries(val).map(([form, types]) =>
        `<div class="mb-1"><span class="fw-semibold">${form}</span> : ${wrapTypes(types)}</div>`
      ).join("");
    }
    return String(val ?? "");
  }

  function collectTypes(rows) {
    const set = new Set();
    rows.forEach(r => extractTypes(r).forEach(t => set.add(t)));
    return Array.from(set).sort();
  }

  // =========================
  // Rendering: grid
  // =========================
  function setupIcon(img, num, name, mode = "icon") {
    const slug = slugify(name || "");
    const base = mode === "full" ? "/ptu/img/pokemon/full" : "/ptu/img/pokemon/icons";
    // Use the first pattern (others could be tried if you add more)
    img.src = CFG.iconPatterns[0](base, num, slug);
  }

  function applyBadgeBackground(el, types) {
    if (!types || types.length === 0) {
      el.style.background = "#151922";
      return;
    }
    if (types.length === 1) {
      el.classList.add(`card-type-${types[0]}`);
      el.style.background = `var(--type-color)`;
      el.style.color = "#0f1115";
      el.style.borderColor = "rgba(255,255,255,.15)";
    } else {
      el.classList.add(`card-type-${types[0]}`);
      const c1 = getComputedStyle(el).getPropertyValue("--type-color")?.trim() || "#333";
      el.classList.remove(`card-type-${types[0]}`);
      el.classList.add(`card-type-${types[1]}`);
      const c2 = getComputedStyle(el).getPropertyValue("--type-color")?.trim() || "#444";
      el.classList.remove(`card-type-${types[1]}`);
      el.style.background = `linear-gradient(90deg, ${c1} 50%, ${c2} 50%)`;
      el.style.borderColor = "rgba(255,255,255,.15)";
    }
  }

  function renderGrid(rows) {
    const grid = $("#dex-grid");
    grid.innerHTML = "";
    const frag = document.createDocumentFragment();
    rows.forEach(p => {
      const name = p.Species || "Unknown";
      const num = pad3(p.Number ?? "0");
      const types = extractTypes(p);

      const li = document.createElement("div");
      li.className = "dex-badge";
      li.dataset.types = types.join(",");

      const iconWrap = document.createElement("div");
      iconWrap.className = "icon dark-background";
      const img = document.createElement("img");
      setupIcon(img, p.Icon || p.Number, name, "icon");
      iconWrap.appendChild(img);
      li.appendChild(iconWrap);

      const numBadge = document.createElement("div");
      numBadge.className = "dex-num-badge";
      numBadge.textContent = `#${num}`;
      li.appendChild(numBadge);

      const label = document.createElement("div");
      label.className = "dex-label";
      label.textContent = name;
      li.appendChild(label);

      li.addEventListener("click", () => openDetail(p));
      frag.appendChild(li);
    });
    grid.appendChild(frag);

    requestAnimationFrame(() => {
      grid.querySelectorAll(".dex-badge").forEach(el => {
        const types = el.dataset.types ? el.dataset.types.split(",") : [];
        applyBadgeBackground(el, types);
      });
    });
  }

  // =========================
  // Rendering: details modal
  // =========================
  function transformBasicInformation(v) {
    if (!v || typeof v !== "object") return v;
    if (v?.Type) {
      const t = v.Type;
      if (Array.isArray(t)) {
        if (t.length && typeof t[0] === "string") {
          v.Type = wrapTypes(t);
        } else if (t.length && typeof t[0] === "object") {
          v.Type = renderFormType(t[0]);
        } else {
          v.Type = "";
        }
      } else {
        v.Type = renderFormType(t);
      }
    }
    for (const [bk, bv] of Object.entries(v)) {
      if (typeof bv === "string" && /ability/i.test(bk) && !/capabilit/i.test(bk) && bv.trim()) {
        v[bk] = `<a href="#" class="js-ability-link" data-ability="${escapeHtml(bv)}">${escapeHtml(bv)}</a>`;
      }
    }
    return v;
  }

  function renderBaseStats(stats, depth = 0) {
    const order = ["HP", "Attack", "Defense", "Special Attack", "Special Defense", "Speed"];
    const h = Math.min(4 + depth, 6);

    // Single form
    if (!("Small" in (stats || {}))) {
      const total = order.reduce((s, k) => s + (stats?.[k] ?? 0), 0);
      const rows = order.map(k => `
        <tr><td class="text-start">${k}</td><td class="text-end">${stats?.[k] ?? 0}</td></tr>
      `).join("");
      return `
        <div class="mt-3">
          <h${h} class="text-muted">Base Stats</h${h}>
          <table class="table table-sm align-middle"><tbody>
            ${rows}
            <tr class="fw-semibold"><td class="text-start">Total</td><td class="text-end">${total}</td></tr>
          </tbody></table>
        </div>`;
    }

    // Multi-size
    const forms = { "Small": "S", "Average": "M", "Large": "L", "Super Size": "XL" };
    const totals = {};
    Object.keys(forms).forEach(f => totals[f] = order.reduce((s, k) => s + (stats[f]?.[k] ?? 0), 0));

    const rows = order.map(k => `
      <tr><td class="text-start">${k}</td>${Object.keys(forms).map(f => `<td class="text-center">${stats[f]?.[k] ?? 0}</td>`).join("")}</tr>
    `).join("");

    return `
      <div class="mt-3">
        <h${h} class="text-muted">Base Stats</h${h}>
        <table class="table table-sm align-middle">
          <thead><tr><th class="text-start"></th>${Object.values(forms).map(lbl => `<th class="text-center">${lbl}</th>`).join("")}</tr></thead>
          <tbody>
            ${rows}
            <tr class="fw-semibold"><td class="text-start">Total</td>${Object.keys(forms).map(f => `<td class="text-center">${totals[f]}</td>`).join("")}</tr>
          </tbody>
        </table>
      </div>`;
  }

  function renderSkills(skills, depth = 0) {
    const h = Math.min(4 + depth, 6);
    const rows = Object.entries(skills || {}).map(([k, v]) => `
      <li class="list-group-item d-flex justify-content-between align-items-center">
        <span class="skill-key">${k}</span><span class="skill-val">${v}</span>
      </li>`).join("");
    return rows ? `
      <div class="mt-3">
        <h${h} class="text-muted">Skills</h${h}>
        <div class="card accent skills-card"><ul class="list-group list-group-flush skills-list">${rows}</ul></div>
      </div>` : "";
  }

  function renderEvolutionList(evos, depth = 0) {
    if (!Array.isArray(evos) || !evos.length) return "";
    const h = Math.min(4 + depth, 6);
    const items = evos.map(e => {
      const stade = e?.Stade ?? "";
      const species = e?.Species ?? "";
      const level = (e?.["Minimum Level"] ?? "").trim();
      const cond = (e?.Condition ?? "").trim();
      const label = `${stade} - <a href="#" onclick='openModalBySpecies(${JSON.stringify(String(species))}); return false;'>${escapeHtml(species)}</a>` +
        `${level ? ` [${escapeHtml(level)}]` : ""}` + `${cond ? ` (${escapeHtml(cond)})` : ""}`;
      return `<li class="list-group-item d-flex align-items-center"><span class="flex-grow-1">${label}</span></li>`;
    }).join("");
    return `
      <div class="mt-3">
        <h${h} class="text-muted">Evolution</h${h}>
        <div class="card accent skills-card"><ul class="list-group list-group-flush skills-list">${items}</ul></div>
      </div>`;
  }

  function renderBattleOnlyForms(forms, base) {
    if (!forms || typeof forms !== "object") return "";
    const pNum = base?.Number ?? "", pName = base?.Species ?? "Unknown";
    return Object.entries(forms).map(([label, f]) => {
      const t = document.createElement("img");
      setupIcon(t, f?.Icon ?? pNum, `${pName} — ${label}`, "full");
      const src = t.src;
      const types = wrapTypes(f?.Type || []);
      const line = k => f?.[k] ? `<div class="small text-muted">${k}: <span class="text-body">${Array.isArray(f[k]) ? f[k].join(", ") : (typeof f[k] === "object" ? Object.keys(f[k]).join(", ") : String(f[k]))}</span></div>` : "";
      const stats = f?.Stats ? Object.entries(f.Stats).map(([k, v]) => `<div class="d-flex justify-content-between small border-bottom"><span class="text-muted">${k}</span><span class="fw-semibold">${v}</span></div>`).join("") : "";
      return `
        <div class="card accent w-100 mb-2"><div class="card-body">
          <div class="d-flex align-items-start gap-3">
            <div class="rounded dark-background p-1"><img class="dex-title-icon" src="${src}"></div>
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

  function renderTmTutorMovesComma(arr, title = "TM/Tutor Moves") {
    if (!Array.isArray(arr) || arr.length === 0) return "";
    const parts = arr.map(it => {
      if (typeof it === "string") return `<span class="small text-muted">${escapeHtml(it)}</span>`;
      const raw = it?.Move ?? "";
      const move = raw ? `<a href="#" class="js-move-link" data-move="${escapeHtml(raw)}">${escapeHtml(raw)}</a>` : "";
      const tagsSup = Array.isArray(it?.Tags) && it.Tags.length ? `<sup class="smaller text-uppercase text-muted">${escapeHtml(it.Tags.join(" "))}</sup>` : "";
      let method = it?.Method || "";
      if (method === "Machine") method = "TM";
      const methodSup = method && method !== "Level-Up" ? `<sup class="smaller text-uppercase text-muted">${escapeHtml(method)}</sup>` : "";
      return `<span>${move}${tagsSup}${CFG.showMethodLabel ? methodSup : ""}</span>`;
    });
    return `<div class="mt-3"><h6 class="text-muted">${title}</h6><p class="mb-0">${parts.join(", ")}</p></div>`;
  }

  function renderLevelUpMoves(moves) {
    if (!Array.isArray(moves) || !moves.length) return "";
    return `
      <ul class="list-unstyled mb-0">
        ${moves.map(m => {
      const tagsSup = Array.isArray(m.Tags) && m.Tags.length ? `<sup class="smaller text-uppercase text-muted ms-1">${escapeHtml(m.Tags.join(" "))}</sup>` : "";
      const nameHtml = `<a href="#" class="js-move-link" data-move="${escapeHtml(m.Move)}">${escapeHtml(m.Move)}</a>`;
      return `<li class="d-flex align-items-center mb-1">
            <span class="text-muted" style="width:50px;">Lv.${m.Level}</span>
            <span class="fw-semibold flex-grow-1">${nameHtml}${tagsSup}</span>
            ${wrapTypes([m.Type])}
          </li>`;
    }).join("")}
      </ul>`;
  }

  function formatDamageBase(mv) {
    // Normalize the "Damage Base 4: 1d8+6 / 11" line
    const raw = mv?.["Damage Base"] || mv?.DB || "";
    if (!raw) return "";
    const s = String(raw);
    // if already "Damage Base X: ...", keep label part normalized
    const m = s.match(/(?:Damage\s*Base\s*)?(\d+)\s*:\s*(.+)$/i);
    if (m) {
      const rank = m[1];
      const detail = m[2];
      return `<div><span class="text-muted">Damage Base ${escapeHtml(rank)}:</span> ${escapeHtml(detail)}</div>`;
    }
    // fallback (raw may contain "4: 1d8+6 / 11" or just "1d8+6 / 11")
    const m2 = s.match(/(\d+)\s*:\s*(.+)/);
    if (m2) {
      return `<div><span class="text-muted">Damage Base ${escapeHtml(m2[1])}:</span> ${escapeHtml(m2[2])}</div>`;
    }
    return `<div><span class="text-muted">Damage Base:</span> ${escapeHtml(s)}</div>`;
  }

  function renderMoveDetails(mv) {
    if (!mv) return '<p class="text-muted mb-0">Cannot find move.</p>';

    const row = (k, v) =>
      v ? `<div><span class="text-muted">${k}:</span> ${escapeHtml(String(v))}</div>` : "";

    const tags = Array.isArray(mv.Tags) && mv.Tags.length
      ? mv.Tags.join(", ")
      : (mv.Keywords || mv.Keyword || "");

    const isBlank = (val) => {
      if (val == null) return true;
      const s = String(val).trim();
      return !s || /^none$/i.test(s);
    };

    const ignoreFields = new Set(["Contest Type", "Contest Effect"]);
    const extraSections = [];

    // Tous les champs contenant "Effect", sauf ceux ignorés
    const effectKeys = Object.keys(mv).filter(
      k => /effect/i.test(k) && !ignoreFields.has(k)
    );

    for (const k of effectKeys) {
      const v = mv[k];
      if (isBlank(v)) continue;

      if (/^effect$/i.test(k)) {
        // Cas particulier : "Effect" → sans label
        extraSections.push(
          `<div style="white-space:pre-wrap">${escapeHtml(String(v))}</div>`
        );
      } else {
        // Autres effets → avec label
        extraSections.push(
          `<div style="white-space:pre-wrap"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(v))}</div>`
        );
      }
    }

    const extraHtml = extraSections.length
      ? `<hr class="my-2">${extraSections.join("")}`
      : "";

    return `
    ${row("Frequency", mv.Frequency)}
    ${row("AC", mv.AC)}
    ${formatDamageBase(mv)}
    ${row("Class", mv.Class)}
    ${row("Range", mv.Range)}
    ${row("Keywords", tags)}
    ${row("Target", mv.Target)}
    ${row("Trigger", mv.Trigger)}
    ${extraHtml}
  `;
  }

  function renderAbilityDetails(ab) {
    if (!ab) return '<p class="text-muted mb-0">Ability introuvable.</p>';

    const row = (k, v) => v ? `<div><span class="text-muted">${k}:</span> ${escapeHtml(String(v))}</div>` : "";
    const isBlank = (val) => {
      if (val == null) return true;
      const s = String(val).trim();
      return !s || /^none$/i.test(s);
    };

    // Champs principaux (toujours au-dessus)
    const header =
      row("Frequency", ab.Frequency) +
      row("Target", ab.Target) +
      row("Trigger", ab.Trigger);

    // Sections “effets” flexibles : Effect (sans label), Bonus/Special et
    // tout autre champ contenant "Effect" (avec label), s’ils ne sont pas vides.
    const keys = Object.keys(ab);
    const effectishKeys = keys.filter(k => /(effect|bonus|special)/i.test(k));

    const sections = [];
    for (const k of effectishKeys) {
      const v = ab[k];
      if (isBlank(v)) continue;

      if (/^effect$/i.test(k)) {
        // "Effect" tout seul → sans label
        sections.push(
          `<div style="white-space:pre-wrap">${escapeHtml(String(v))}</div>`
        );
      } else {
        // Bonus, Special, ou tout autre champ contenant "Effect" → avec label
        sections.push(
          `<div style="white-space:pre-wrap"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(v))}</div>`
        );
      }
    }

    const extras = sections.length ? `<hr class="my-2">${sections.join("")}` : "";

    return `${header}${extras}`;
  }


  function renderObject(obj, depth = 0) {
    const leftSections = new Set(["Base Stats", "Basic Information", "Evolution", "Other Information", "Battle-Only Forms"]);
    if (obj == null) return "";

    if (Array.isArray(obj)) {
      if (!obj.length) return "";
      const items = obj.map(v => {
        if (typeof v === "object") {
          const inner = renderObject(v, depth + 1);
          return inner.trim() ? `<li>${inner}</li>` : "";
        }
        return `<li>${escapeHtml(String(v))}</li>`;
      }).filter(Boolean);
      return items.length ? `<ul>${items.join("")}</ul>` : "";
    }

    if (typeof obj === "object") {
      if (depth === 0) {
        let col1 = "", col2 = "";
        for (const [k, v0] of Object.entries(obj)) {
          if (["Species", "Number", "Icon"].includes(k)) continue;

          let v = v0;
          if (k === "Basic Information") v = transformBasicInformation({ ...(v || {}) });

          // Base Stats
          if (k === "Base Stats" && v && typeof v === "object") {
            const block = renderBaseStats(v, depth);
            (leftSections.has(k) ? (col1 += block) : (col2 += block));
            continue;
          }
          // Evolution
          if (k === "Evolution" && Array.isArray(v)) {
            const block = renderEvolutionList(v, depth);
            (leftSections.has(k) ? (col1 += block) : (col2 += block));
            continue;
          }
          // Capabilities
          if (k === "Capabilities" && v) {
            const block = renderCapabilities(v, depth);
            if (block.trim()) (leftSections.has(k) ? (col1 += block) : (col2 += block));
            continue;
          }
          // Skills
          if (k === "Skills" && v && typeof v === "object") {
            const block = renderSkills(v, depth);
            (leftSections.has(k) ? (col1 += block) : (col2 += block));
            continue;
          }
          // Moves
          if (k === "Moves" && v) {
            let blocks = "";
            if (v["Level Up Move List"]) {
              blocks += `<div class="mt-3"><h5 class="text-muted">Level-Up Moves</h5>${renderLevelUpMoves(v["Level Up Move List"])}</div>`;
            }
            blocks += renderTmTutorMovesComma(v["TM/HM Move List"], "TM/HM Moves");
            blocks += renderTmTutorMovesComma(v["Egg Move List"], "Egg Moves");
            blocks += renderTmTutorMovesComma(v["Tutor Move List"], "Tutor Moves");
            blocks += renderTmTutorMovesComma(v["TM/Tutor Moves List"]);
            if (blocks.trim()) {
              const h = Math.min(4 + depth, 6);
              const card = `<div class="mt-3"><h${h} class="text-muted">Moves</h${h}><div class="card accent"><div class="card-body">${blocks}</div></div></div>`;
              (leftSections.has(k) ? (col1 += card) : (col2 += card));
            }
            continue;
          }
          // Battle-Only Forms
          if (k === "Battle-Only Forms" && v && typeof v === "object") {
            const html = renderBattleOnlyForms(v, obj);
            if (html.trim()) {
              const h = Math.min(4 + depth, 6);
              const card = `<div class="mt-3"><h${h} class="text-muted">Battle-Only Forms</h${h}><div class="card accent"><div class="card-body">${html}</div></div></div>`;
              (leftSections.has(k) ? (col1 += card) : (col2 += card));
            }
            continue;
          }

          // generic object/scalar
          let block = "";
          if (typeof v === "object" && v !== null) {
            const inner = renderObject(v, depth + 1);
            if (!inner.trim()) continue;
            const h = Math.min(4 + depth, 6);
            block = `<div class="mt-3"><h${h} class="text-muted">${k}</h${h}><div class="card accent"><div class="card-body">${inner}</div></div></div>`;
          } else {
            block = `<div class="row border-bottom py-1"><div class="col-4 fw-semibold">${k}</div><div class="col-8">${v}</div></div>`;
          }
          (leftSections.has(k) ? (col1 += block) : (col2 += block));
        }
        const hasAny = (col1.trim() || col2.trim());
        return hasAny ? `<div class="row"><div class="col-md-6">${col1}</div><div class="col-md-6">${col2}</div></div>` : "";
      }

      // nested
      let html = "";
      for (const [k, v] of Object.entries(obj)) {
        if (Array.isArray(v) && v.length === 0) continue;
        if (v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0) continue;
        if (typeof v === "object" && v !== null) {
          const inner = renderObject(v, depth + 1);
          if (!inner.trim()) continue;
          const h = Math.min(4 + depth, 6);
          html += `<div class="mt-3"><h${h} class="text-muted">${k}</h${h}><div class="card accent"><div class="card-body">${inner}</div></div></div>`;
        } else {
          html += `<div class="row border-bottom py-1"><div class="col-4 fw-semibold">${k}</div><div class="col-8">${v}</div></div>`;
        }
      }
      return html;
    }
    return escapeHtml(String(obj));
  }

  // Capabilities parsing + render (unchanged logic, cleaned)
  function parseCapabilities(raw) {
    const rated = [], simple = [];
    const pushPair = (k, v) => {
      const key = String(k).trim();
      if (!key) return;
      let value = v;
      if (typeof value === "string") {
        const s = value.trim();
        if (s.includes("/")) value = s;
        else {
          const n = Number(s);
          value = Number.isNaN(n) ? s : n;
        }
      }
      if (typeof value === "number" || (typeof value === "string" && value)) rated.push({ key, value });
      else simple.push(key);
    };
    const fromString = (s) => {
      const str = String(s).trim();
      if (!str) return;
      const m = str.match(/^(.+?)\s+(-?\d+(?:\.\d+)?(?:\/\d+(?:\.\d+)?)?)\s*$/);
      if (m) pushPair(m[1], m[2]);
      else simple.push(str);
    };
    if (Array.isArray(raw)) {
      raw.forEach(item => {
        if (item == null) return;
        if (typeof item === "string") fromString(item);
        else if (typeof item === "object") Object.entries(item).forEach(([k, v]) => pushPair(k, v));
        else fromString(item);
      });
    } else if (typeof raw === "object" && raw) {
      Object.entries(raw).forEach(([k, v]) => {
        if (Array.isArray(v)) v.forEach(x => (typeof x === "string" ? fromString(`${k} ${x}`) : pushPair(k, x)));
        else if (typeof v === "string") fromString(`${k} ${v}`);
        else pushPair(k, v);
      });
    } else if (raw != null) fromString(raw);
    return { rated, simple };
  }

  function renderCapabilities(raw, depth = 0) {
    const parsed = parseCapabilities(raw);
    if (!parsed.rated.length && !parsed.simple.length) return "";
    const h = Math.min(4 + depth, 6);
    const rated = parsed.rated.map(({ key, value }) => `
      <div class="cap-item"><div class="cap-head"><span class="cap-key">${key}</span></div><div class="cap-val">${value}</div></div>
    `).join("");
    const simple = parsed.simple.map(k => `<span class="cap-chip"><span>${k}</span></span>`).join("");
    return `
      <div class="mt-3">
        <h${h} class="text-muted">Capabilities</h${h}>
        <div class="card accent"><div class="card-body">
          ${parsed.rated.length ? `<div class="cap-grid">${rated}</div>` : ""}
          ${parsed.simple.length ? `<div class="cap-chips">${simple}</div>` : ""}
        </div></div>
      </div>`;
  }

  // =========================
  // Sidebar
  // =========================
  function buildReadmeModalIfMissing() {
    if ($("#readmeModal")) return;
    const el = document.createElement("div");
    el.className = "modal fade";
    el.id = "readmeModal";
    el.tabIndex = -1;
    el.setAttribute("aria-hidden", "true");
    el.innerHTML = `
      <div class="modal-dialog modal-lg modal-dialog-scrollable"><div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Datasets — Readme</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <p><strong>Core</strong> — What are in the officials Dexes. Very small changes for a reliable base, see changelog.</p>
          <p><strong>Community</strong> — Based on Core dataset, some abilities pools are updated according to the Gen 9 Dex.</p>
          <p><strong>Homebrew</strong>  — Based on Community dataset, updated all mons stats and movepools from Gen 1 to 8.5.</p>
          <hr/>
          <h5>Q&A</h5>
          <h6>Homebrew: what are "Deleted" moves?</h6>
          <p>Those are moves that have been removed in Gen 8. When updating, those have been reinjected from the Core Dex. Feel free to keep them or not.</p>
          <hr/>
          <h5>Changelog</h5>
          <h6>Core</h6>
          <ul>
            <li>Following Pokémons have now a minimum evolution level of 20: Shellder, Exeggcute, Eevee.<br>Other Gen-1 Pokémons with Stone Evolution have this condition. Probable oversight.</li>
            <li>Rotom have now one entry per form.</li>
            <li>According to the Gen 8 References document, Koffing and Weezing have their new Abilities set.</li>
            <li>Additional Note: The dex formatting follows the Gen 9 Community Homebrew Dex guidelines, but (hopefully) no data has been scrapped.</li>
          </ul>
          <h6>Community</h6>
          <p>According to the document, some Pokémon have their Abilities set updated: Gastly, Haunter, Gengar, Lapras, Spinarak, Ariados, Phanpy, Donphan, Spheal, Shiftry, Piplup, Prinplup, Gallade, Gible, Gabite, Whirlipede, Pawniard, Bisharp, Cobalion, Terrakion, Virizion, Keldeo, Skiddo, Gogoat, Honedge, Doublade, Aegislash, Kartana, Samurott Hisuian, Kleavor</p>
          <h6>Homebrew</h6>
          <p>
            All Pokémons from Gen 1 to 8.5 has been updated using the newest game generation available and following PTU standard, using Gen 9 Community Homebrew guidelines. Here is the process:<br>
            <ul>
            <li>Extract Base Stats, Moves, Evolutionary Stage from PokeAPI</li>
            <li>Transform stats for PTU format: base_stat / 10, rounded up from .5.</li>
            <li>Split moves into categories:
              <ul>
                <li>"Level Up Move List": sorted by level (with "Evo" first).</li>
                <li>"TM/Tutor Move List": names only, sorted alphabetically.</li>
                <li>If stage > 0: all level:1 moves → moved into TM/Tutor (with (N) suffix).</li>
              </ul>
            <li>Special stone-evolution logic:
              <ul>
                <li>If evolved by stone and has <10 level-up moves → inherit level-up moves from previous stage.</li>
                <li>Moves below minimum evolution level → shifted to TM/Tutor list with (N).</li>
              </ul>
            <li>Deduplication rules:
              <ul>
                <li>No duplicates in TM/Tutor list; if both normal and (N) exist, keep only (N).</li>
                <li>If a move also exists in Level-Up, remove it from TM/Tutor.</li>
              </ul>
          </p>
        </div>
        <div class="modal-footer"><button class="btn btn-primary" data-bs-dismiss="modal">OK</button></div>
      </div></div>`;
    document.body.appendChild(el);
  }

  function buildTypeSidebar(all, onChange) {
    const sidebar = $("#sidebar");
    if (!sidebar) return;
    const old = sidebar.querySelector('[data-role="type-filters"]');
    if (old) old.remove();

    const typesBox = document.createElement("div");
    typesBox.setAttribute("data-role", "type-filters");
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
            <input class="form-check-input me-1" type="checkbox" value="${type}">${type}
          </label>`).join("")}
      </div>`;

    const srcMenu = sidebar.querySelector('[data-role="source-menu"]');
    if (srcMenu) srcMenu.insertAdjacentElement("afterend", typesBox);
    else sidebar.prepend(typesBox);

    typesBox.querySelectorAll("#type-filters input[type='checkbox']").forEach(input => input.addEventListener("change", onChange));

    const sb = $("#sidebar-search");
    if (sb) sb.addEventListener("input", debounce(() => {
      const q = sb.value.toLowerCase();
      typesBox.querySelectorAll("#type-filters label").forEach(label => {
        label.style.display = label.textContent.toLowerCase().includes(q) ? "" : "none";
      });
    }, 150));

    const toggle = $("#toggle-all-types");
    if (toggle) toggle.addEventListener("click", () => {
      const boxes = typesBox.querySelectorAll("#type-filters input[type='checkbox']");
      const allChecked = Array.from(boxes).every(cb => cb.checked);
      boxes.forEach(cb => cb.checked = !allChecked);
      onChange();
    });
  }

  function activeTypes() {
    return Array.from(document.querySelectorAll("#type-filters input:checked")).map(el => el.value);
  }

  function filterRows(rows) {
    const q = ($("#dex-search")?.value || "").trim().toLowerCase();
    const types = activeTypes();
    return rows.filter(p => {
      const name = (p.Species || "").toLowerCase();
      const num = String(p.Number || "");
      const hasQ = !q || name.includes(q) || num.includes(q);
      const pTypes = extractTypes(p);
      const typeOk = types.length === 0 || pTypes.some(t => types.includes(t));
      return hasQ && typeOk;
    }).sort((a, b) => (a.Number || 0) - (b.Number || 0));
  }

  function wireSearch(all) {
    const inp = $("#dex-search");
    if (inp) inp.addEventListener("input", debounce(() => renderGrid(filterRows(all)), 120));
    $("#clear-filters")?.addEventListener("click", () => {
      inp.value = "";
      document.querySelectorAll("#type-filters input[type='checkbox']").forEach(cb => cb.checked = false);
      renderGrid(filterRows(all));
    });
  }

  // =========================
  // Source menu / presets
  // =========================
  function buildSourceMenu(onChange) {
    const sb = $("#sidebar");
    if (!sb) return;
    buildReadmeModalIfMissing();

    const wrap = document.createElement("div");
    wrap.className = "mb-3 d-flex flex-column gap-2";
    wrap.setAttribute("data-role", "source-menu");
    wrap.innerHTML = `
      <div class="d-flex align-items-center justify-content-between">
        <label class="form-label mb-0">Dataset</label>
        <button type="button" class="btn btn-primary" style="font-size:.75rem; padding:.1rem .25rem; min-width:unset; width:auto;" id="btn-readme">Readme</button>
      </div>
      <div class="d-flex flex-wrap gap-1 w-100 mb-2" role="group" aria-label="Dataset presets">
        ${["Core", "Community", "Homebrew"].map(p => `
          <input type="radio" class="btn-check" name="preset" id="preset-${p.toLowerCase()}" ${selectedPreset === p ? "checked" : ""}>
          <label class="btn btn-outline-primary d-flex justify-content-center align-items-center flex-grow-1" style="flex-basis:0; min-width:90px;" for="preset-${p.toLowerCase()}">${p}</label>
        `).join("")}
      </div>
      <div id="preset-files-box" class="border rounded p-2 small">
        <div class="fw-semibold mb-1">Included Pokédex</div>
        <div id="preset-files-list"></div>
      </div>`;

    sb.querySelector('[data-role="source-menu"]')?.remove();
    sb.prepend(wrap);

    function renderPresetFiles() {
      const box = wrap.querySelector("#preset-files-list");
      const lbls = PRESETS[selectedPreset] || [];
      box.innerHTML = lbls.map(lbl => {
        const id = `pdx-file-${lbl.replace(/[^a-z0-9]+/gi, "-")}`;
        const checked = (selectedLabels.size === 0 || selectedLabels.has(lbl)) ? "checked" : "";
        return `<div class="form-check">
          <input class="form-check-input" type="checkbox" id="${id}" data-label="${lbl}" ${checked}>
          <label class="form-check-label" for="${id}">${lbl}</label>
        </div>`;
      }).join("");
      box.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.addEventListener("change", () => {
          selectedLabels.clear();
          box.querySelectorAll('input[type="checkbox"]:checked').forEach(c => selectedLabels.add(c.getAttribute("data-label")));
          reload();
        });
      });
    }

    async function reload() {
      try {
        const data = await loadPokedex();
        window.__POKEDEX = data;
        buildTypeSidebar(data, () => renderGrid(filterRows(data)));
        renderGrid(filterRows(data));
      } catch (e) {
        console.error(e);
        $("#dex-grid").innerHTML = `<div class="alert alert-warning">Aucune donnée pour le preset « ${selectedPreset} ».</div>`;
      }
      onChange?.();
    }

    wrap.querySelector("#btn-readme")?.addEventListener("click", () => {
      bootstrap.Modal.getOrCreateInstance($("#readmeModal")).show();
    });

    // single handler for radios
    wrap.addEventListener("change", (ev) => {
      const tgt = ev.target;
      if (!(tgt instanceof HTMLInputElement)) return;
      if (tgt.name !== "preset" || !tgt.checked) return;
      const id = tgt.id;
      if (id.endsWith("core")) selectedPreset = "Core";
      else if (id.endsWith("community")) selectedPreset = "Community";
      else if (id.endsWith("homebrew")) selectedPreset = "Homebrew";
      selectedLabels = new Set(PRESETS[selectedPreset] || []);
      renderPresetFiles();
      reload();
    });

    renderPresetFiles();
  }

  // =========================
  // Open detail modal
  // =========================
  function openDetail(p) {
    const body = $("#dexModalBody");
    const title = $("#dexModalLabel");
    const num = pad3(p.Number ?? "0");
    const species = p.Species || "Unknown";
    const typesHTML = wrapTypes(extractTypes(p)) || "";

    title.innerHTML = `
      <div class="d-flex align-items-start gap-3 w-100">
        <img id="dexModalIcon" class="dex-title-icon rounded dark-background p-1" width="64" height="64" alt="${species}">
        <div class="flex-grow-1">
          <div class="d-flex flex-wrap align-items-baseline gap-2">
            <span class="h5 mb-0">#${num} — ${species}</span>
          </div>
          <div class="dex-title-types mt-1">${typesHTML}</div>
        </div>
      </div>`;

    const safe = (typeof structuredClone === "function") ? structuredClone(p) : JSON.parse(JSON.stringify(p));
    body.innerHTML = renderObject(safe);

    const img = $("#dexModalIcon");
    if (img) setupIcon(img, p.Icon || p.Number, species, "full");

    const inst = getDexModalInstance();
    if (inst && !isDexModalShown()) inst.show();
    else if (inst) inst.handleUpdate();
  }

  async function openModalBySpecies(speciesName) {
    const data = await loadPokedex();
    const found = data.find(p => (p.Species || "").toLowerCase() === String(speciesName || "").toLowerCase());
    if (found) openDetail(found);
    else alert(`Aucun Pokémon trouvé avec le nom "${speciesName}"`);
  }

  // =========================
  // Move & Ability modal
  // =========================
  let _moveAbilityModal;
  function ensureMoveAbilityModal() {
    if (_moveAbilityModal) return _moveAbilityModal;
    const el = $("#moveAbilityModal");
    if (!el) return null;
    _moveAbilityModal = new bootstrap.Modal(el, { backdrop: true });
    return _moveAbilityModal;
  }

  async function openMoveModalByName(moveName) {
    const name = String(moveName || "").trim().toLowerCase();
    if (!name) return;
    const idx = await loadMoveIndex();
    const mv = idx.get(name) || idx.get(name.replace(/[-–—]/g, " ")) || null;
    const display = mv?.Move || mv?.Name || mv?.__displayName || moveName;
    const labelEl = $("#moveAbilityModalLabel");
    const typeHtml = mv?.Type ? wrapTypes([mv.Type]) : "";
    labelEl.innerHTML = `<div><div class="fw-semibold">Move — ${escapeHtml(display)}</div><div class="mt-1">${typeHtml}</div></div>`;
    $("#moveAbilityModalBody").innerHTML = renderMoveDetails(mv);
    ensureMoveAbilityModal()?.show();
  }

  async function openAbilityModalByName(abilityName) {
    const name = String(abilityName || "").trim().toLowerCase();
    if (!name) return;
    const idx = await loadAbilityIndex();
    const ab = idx.get(name) || null;
    const display = ab?.Name || ab?.__displayName || abilityName;
    $("#moveAbilityModalLabel").textContent = `Ability — ${display}`;
    $("#moveAbilityModalBody").innerHTML = renderAbilityDetails(ab);
    ensureMoveAbilityModal()?.show();
  }

  document.addEventListener("click", (ev) => {
    const a = ev.target.closest("a.js-move-link, a.js-ability-link");
    if (!a) return;
    ev.preventDefault();
    const move = a.dataset.move;
    const ability = a.dataset.ability;
    if (move) openMoveModalByName(move);
    if (ability) openAbilityModalByName(ability);
  });

  // =========================
  // Boot
  // =========================
  document.addEventListener("DOMContentLoaded", async () => {
    selectedLabels = new Set(PRESETS[selectedPreset] || []);
    buildSourceMenu();

    const data = await loadPokedex();
    window.__POKEDEX = data;

    window.openModalBySpecies = (speciesName) => {
      const found = (window.__POKEDEX || []).find(
        p => String(p.Species || "").toLowerCase() === String(speciesName || "").toLowerCase()
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

  // Backdrop/padding-right fix on hide (avoids layout shift on grid)
  document.addEventListener("DOMContentLoaded", () => {
    const modalEl = $("#dexModal");
    if (!modalEl) return;
    modalEl.addEventListener("hidden.bs.modal", () => {
      document.querySelectorAll(".modal-backdrop").forEach(b => b.remove());
      document.body.classList.remove("modal-open");
      document.body.style.removeProperty("paddingRight");
      document.body.style.removeProperty("padding-right");
    });
  });

  // Delegated open via data attributes
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-dex-number], a[data-dex-species]");
    if (!a) return;
    e.preventDefault();
    const number = a.getAttribute("data-dex-number");
    const species = a.getAttribute("data-dex-species");
    const target = window.__pokedexData?.find(p =>
      (number && String(p.Number) === String(number)) ||
      (species && String(p.Species).toLowerCase() === String(species).toLowerCase())
    );
    if (target) openDetail(target);
  });
})();

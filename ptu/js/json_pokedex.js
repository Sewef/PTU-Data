import {
  debounce,
  buildPillSection,
  getSelectedPills
} from "/ptu/js/helpers.js";

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
  "Core": "pokedex_core.min.json",
  "AlolaDex": "pokedex_7g.min.json",
  "GalarDex": "pokedex_8g.min.json",
  "HisuiDex": "pokedex_8g_hisui.min.json",
  "Core (Homebrew)": "pokedex_core.min.json",
  "AlolaDex (Homebrew)": "pokedex_7g.min.json",
  "GalarDex (Homebrew)": "pokedex_8g.min.json",
  "HisuiDex (Homebrew)": "pokedex_8g_hisui.min.json",
  "Core (Community Homebrew)": "pokedex_core.min.json",
  "AlolaDex (Community Homebrew)": "pokedex_7g.min.json",
  "GalarDex (Community Homebrew)": "pokedex_8g.min.json",
  "HisuiDex (Community Homebrew)": "pokedex_8g_hisui.min.json",
  "PaldeaDex (Community Homebrew)": "pokedex_9g.min.json",
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
    "Core (Homebrew)",
    "AlolaDex (Homebrew)",
    "GalarDex (Homebrew)",
    "HisuiDex (Homebrew)",
    "PaldeaDex (Community Homebrew)",
  ],
};

const MOVES_BASE = "/ptu/data/moves";
const ABILITIES_BASE = "/ptu/data/abilities";
const CAPABILITIES_BASE = "/ptu/data/capabilities";

const MOVES_FILE_BY_PRESET = {
  Core: `${MOVES_BASE}/moves_core.min.json`,
  Community: `${MOVES_BASE}/moves_9g.min.json`,
  Homebrew: `${MOVES_BASE}/moves_homebrew.min.json`
};
const ABILITIES_FILE_BY_PRESET = {
  Core: `${ABILITIES_BASE}/abilities_core.min.json`,
  Community: `${ABILITIES_BASE}/abilities_9g.min.json`,
  Homebrew: `${ABILITIES_BASE}/abilities_homebrew.min.json`
};

const CAPABILITIES_FILE_BY_PRESET = {
  Core: `${CAPABILITIES_BASE}/capabilities_core.min.json`,
  Community: `${CAPABILITIES_BASE}/capabilities_9G.min.json`,
  Homebrew: `${CAPABILITIES_BASE}/capabilities_9G.min.json`
};

const POKESHEETS_FILE_BY_PRESET = {
  Core: {
    dex: "/ptu/data/pokesheets/pokedex_core.min.json",
    moves: "/ptu/data/pokesheets/moves_core.min.json",
  },
  Community: {
    dex: "/ptu/data/pokesheets/pokedex_community.min.json",
    moves: "/ptu/data/pokesheets/moves_community.min.json",
  },
  Homebrew: {
    dex: "/ptu/data/pokesheets/pokedex_homebrew.min.json",
    moves: "/ptu/data/pokesheets/moves_homebrew.min.json",
  }
};


const SHOWN_TAGS = new Set(["N", "Stab"]);

let selectedPreset = window.selectedPreset || "Core";
let selectedLabels = new Set(PRESETS[selectedPreset] || []);


// =========================
// Filtering / Performance
// =========================
let TYPE_MATCH_MODE = 'any'; // 'any' (OR) || 'all' (AND) for type matching
const GRID_CHUNK_SIZE = 60; // smaller batch to speed up first paint
let __RENDER_SEQ = 0;
const __TYPE_CACHE__ = new WeakMap(); // cache pokemon -> types[]
// =========================
// Caches & Utilities

// --- Wildcard helpers (normalize + glob '*' anywhere) ---
function __normalizeToken(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/[\u2013\u2014\-_]/g, "-")  // normalize dashes
    .replace(/\s+/g, " ")                // collapse spaces
    .trim();
}
function __makeWildcardMatcher(queryRaw) {
  const q = __normalizeToken(queryRaw || "");
  if (!q) return () => true;
  // escape regex specials then expand '*' to '.*'
  const esc = q.replace(/[.+?^${}()|[\]\\]/g, "\\$&");
  const glob = esc.replace(/\*/g, ".*");
  const rx = new RegExp("^" + glob + "$");
  return (s) => rx.test(__normalizeToken(s));
}
// =========================
const _fetchCache = new Map(); // url -> Promise(json)
const _indexCache = new Map(); // url -> Promise(Map)
const pad3 = (n) => String(n).padStart(3, "0");
const slugify = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
const $ = (sel) => document.querySelector(sel);

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
      for (const [key, obj] of Object.entries(raw)) {

        // Cas capabilities : la valeur est un STRING
        if (typeof obj === "string") {
          idx.set(key.trim().toLowerCase(), {
            Name: key,
            Effect: obj,
            __displayName: key
          });
          continue;
        }

        // Cas normal : objet JSON structuré
        if (obj && typeof obj === "object") {
          const k = key.trim().toLowerCase();
          obj.__displayName = key;
          idx.set(k, obj);
        }
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
function getCapabilitiesUrlForPreset() {
  return CAPABILITIES_FILE_BY_PRESET[selectedPreset] || CAPABILITIES_FILE_BY_PRESET.Core;
}
function loadMoveIndex() { return loadIndex(getMovesUrlForPreset(), "Move"); }
function loadAbilityIndex() { return loadIndex(getAbilitiesUrlForPreset(), "Name"); }
function loadCapabilityIndex() { return loadIndex(getCapabilitiesUrlForPreset(), "Name"); }

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

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      return true;
    } catch {
      return false;
    }
  }
}

function showPokesheetsFeedback(msg, ok = true) {
  const fb = document.querySelector("#pokesheets-feedback");
  if (!fb) return;
  fb.textContent = msg;
  fb.classList.toggle("text-success", ok);
  fb.classList.toggle("text-danger", !ok);
}

function getPokesheetsUrlsForPreset() {
  // Only defined for Homebrew today
  return POKESHEETS_FILE_BY_PRESET[selectedPreset] || null;
}
// We'll reuse window.__POKEDEX as the Dex payload (merged, filtered by selected labels)

document.addEventListener("click", async (ev) => {
  const btnDex = ev.target.closest("#btn-copy-pokesheets-dex");
  const btnMoves = ev.target.closest("#btn-copy-pokesheets-moves");
  if (!btnDex && !btnMoves) return;

  const urls = getPokesheetsUrlsForPreset();
  if (!urls) {
    showPokesheetsFeedback("Pokésheets export is only available for the Homebrew dataset.", false);
    return;
  }

  if (btnDex) {
    try {
      const raw = await fetch(urls.dex, { cache: "no-store" }).then(r => r.ok ? r.json() : null);
      if (!raw) throw new Error("HTTP");
      const txt = await fetch(urls.dex, { cache: "no-store" }).then(r => r.ok ? r.text() : null);
      const ok = await copyToClipboard(txt);
      showPokesheetsFeedback(ok ? "Dex JSON copied to clipboard." : "Failed to copy Dex JSON.", ok);
    } catch {
      showPokesheetsFeedback("Failed to copy Dex JSON.", false);
    }
    return;
  }

  if (btnMoves) {
    try {
      const raw = await fetch(urls.moves, { cache: "no-store" }).then(r => r.ok ? r.json() : null);
      if (!raw) throw new Error("HTTP");
      const txt = await fetch(urls.moves, { cache: "no-store" }).then(r => r.ok ? r.text() : null);
      const ok = await copyToClipboard(txt);
      showPokesheetsFeedback(ok ? "Moves JSON copied to clipboard." : "Failed to copy Moves JSON.", ok);
    } catch {
      showPokesheetsFeedback("Failed to copy Moves JSON.", false);
    }
  }
});



// =========================
// Types & Badges helpers
// =========================
// Extraction robuste des types, y compris le cas:
// "Type": [ { "Baille": ["Fire","Flying"], "Pom Pom": ["Electric","Flying"], ... } ]
function extractTypes(p) {
  const info = p?.["Basic Information"] || {};
  const raw = info.Type;

  const out = [];
  const push = (t) => {
    if (!t) return;
    const s = String(t).trim();
    if (s && !out.includes(s)) out.push(s);
  };

  if (Array.isArray(raw)) {
    // ex: ["Fire","Flying"] OU [ { "Baille":[...], "Pom Pom":[...] } ]
    for (const item of raw) {
      if (typeof item === "string") {
        push(item);
      } else if (item && typeof item === "object") {
        // Union de toutes les formes si objet rencontré
        for (const v of Object.values(item)) {
          if (Array.isArray(v)) {
            v.forEach(push);
          } else {
            push(v);
          }
        }
      }
    }
  } else if (raw && typeof raw === "object") {
    // Au cas où "Type" serait directement un objet { Forme: [..], ... }
    for (const v of Object.values(raw)) {
      if (Array.isArray(v)) {
        v.forEach(push);
      } else {
        push(v);
      }
    }
  } else {
    // String simple ou null/undefined
    push(raw);
  }

  // Si tu utilises un cache des types, on le nourrit proprement
  if (typeof __TYPE_CACHE__ !== "undefined" && __TYPE_CACHE__ && typeof __TYPE_CACHE__.set === "function") {
    __TYPE_CACHE__.set(p, out);
  }

  return out;
}

// Strictly read only the species' own types (ignore per-form mappings)
function speciesTypes(p) {
  const info = p?.["Basic Information"] || {};
  const raw = info.Type;
  const out = [];
  const push = (t) => {
    if (!t) return;
    const s = String(t).trim();
    if (s && !out.includes(s)) out.push(s);
  };
  if (Array.isArray(raw)) {
    // Only keep plain string entries (species' base typing)
    for (const item of raw) {
      if (typeof item === "string") push(item);
    }
  } else if (typeof raw === "string") {
    push(raw);
  }
  // Fallback: if nothing detected from plain strings, fall back to union (keeps old behavior)
  if (!out.length) return extractTypes(p);
  return out;
}

// Snapshot the current radio mode to avoid stale globals
function currentTypeMatchMode() {
  const checked = document.querySelector('input[name="type-mode"]:checked');
  if (checked) return checked.id.endsWith('all') ? 'all' : 'any';
  // Fallback to last known global (avoids race when clicking label then a type immediately)
  if (typeof TYPE_MATCH_MODE !== "undefined" && (TYPE_MATCH_MODE === 'all' || TYPE_MATCH_MODE === 'any')) {
    return TYPE_MATCH_MODE;
  }
  return 'any';
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
  const __SEQ__ = (++__RENDER_SEQ);

  const grid = $("#dex-grid");
  if (!grid) return;
  grid.innerHTML = "";
  grid.querySelectorAll("#grid-sentinel").forEach(n => n.remove());

  const CHUNK = (typeof GRID_CHUNK_SIZE === "number" && GRID_CHUNK_SIZE > 0) ? GRID_CHUNK_SIZE : 60;
  let index = 0;

  function appendBatch() {
    if (__SEQ__ !== __RENDER_SEQ) return;
    const frag = document.createDocumentFragment();
    const end = Math.min(index + CHUNK, rows.length);
    for (; index < end; index++) {
      const p = rows[index];
      const name = p.Species || "Unknown";
      const num = pad3(p.Number ?? "0");
      const types = extractTypes(p);

      const li = document.createElement("div");
      li.className = "dex-badge";
      li.dataset.types = (types || []).join(",");

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
    }
    if (__SEQ__ !== __RENDER_SEQ) return;

    grid.appendChild(frag);

    // Apply type backgrounds to the last batch only
    const batch = Array.from(grid.querySelectorAll(".dex-badge")).slice(-CHUNK);
    for (const el of batch) {
      const types = el.dataset.types ? el.dataset.types.split(",") : [];
      applyBadgeBackground(el, types);
    }

    if (__SEQ__ !== __RENDER_SEQ) return;
    if (index < rows.length) {
      setTimeout(appendBatch, 0);
    }
  }

  appendBatch();
}


// =========================
// Rendering: details modal
// =========================
function transformBasicInformation(v) {
  if (!v || typeof v !== "object") return v;

  // Type -> déjà en place
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

  // NEW: Ability(s) -> string OU tableau -> liens cliquables
  for (const [bk, bv] of Object.entries(v)) {
    if (/ability/i.test(bk) && !/capabilit/i.test(bk)) {
      if (Array.isArray(bv)) {
        const parts = bv
          .filter(x => x != null && String(x).trim())
          .map(name => {
            const s = String(name).trim();
            return `<a href="#" class="js-ability-link" data-ability="${escapeHtml(s)}">${escapeHtml(s)}</a>`;
          });
        v[bk] = parts.join(" / ");
      } else if (typeof bv === "string" && bv.trim()) {
        const s = bv.trim();
        v[bk] = `<a href="#" class="js-ability-link" data-ability="${escapeHtml(s)}">${escapeHtml(s)}</a>`;
      }
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

function renderEvolutionList(evos, base, depth = 0) {
  if (!Array.isArray(evos) || !evos.length) return "";
  const h = Math.min(4 + depth, 6);

  // Build availability map from the currently loaded/merged Pokédex.
  // Use exact species name (which includes regional forms like "Linoone Galar")
  const all = (window.__POKEDEX || window.__pokedexData || []);
  const bySpeciesExact = new Map();
  for (const p of all) {
    const sp = String(p?.Species || "").toLowerCase();
    if (!sp) continue;
    bySpeciesExact.set(sp, p);
  }
  const current = String(base?.Species || "").toLowerCase();

  const items = evos.map(e => {
    const stade = e?.Stade ?? "";
    const species = e?.Species ?? "";
    const sp = String(species).toLowerCase();

    const levelNum = e?.["Minimum Level"];
    const cond = (e?.Condition ?? "").trim();

    let level = "";
    if (typeof levelNum === "number" && !isNaN(levelNum)) {
      level = `Lv ${levelNum} Minimum`;
    }

    // Exact match on full species name (includes regional forms)
    const exists = (sp === current) || bySpeciesExact.has(sp);
    const targetPokemon = bySpeciesExact.get(sp);
    const numForSp = targetPokemon?.Number;

    // Build species label: clickable if exists, plain text with tooltip if not
    let speciesLabel;
    if (exists) {
      const numAttr = (numForSp != null) ? ` data-dex-number="${escapeHtml(String(numForSp))}"` : "";
      speciesLabel =
        `<a href="#" class="fw-semibold js-species-link" data-dex-species="${escapeHtml(String(species))}"${numAttr}>${escapeHtml(species)}</a>`;
    } else {
      // Non-clickable with tooltip (Bootstrap-compatible)
      const tip = "Not found in current dataset";
      speciesLabel =
        `<span class="fw-semibold text-decoration-none" data-bs-toggle="tooltip" data-bs-placement="top" title="${tip}">${escapeHtml(species)}</span>`;
    }

    const extra =
      `${level ? ` [${escapeHtml(level)}]` : ""}` +
      `${cond ? ` (${escapeHtml(cond)})` : ""}`;

    const label = `${stade} - ${speciesLabel}${extra}`;

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

  const linkifyAbilities = (val) => {
    if (Array.isArray(val)) {
      return val
        .filter(x => x != null && String(x).trim())
        .map(name => {
          const s = String(name).trim();
          return `<a href="#" class="js-ability-link" data-ability="${escapeHtml(s)}">${escapeHtml(s)}</a>`;
        })
        .join(", ");
    }
    if (typeof val === "string" && val.trim()) {
      const s = val.trim();
      return `<a href="#" class="js-ability-link" data-ability="${escapeHtml(s)}">${escapeHtml(s)}</a>`;
    }
    return Array.isArray(val) ? val.join(", ")
      : (typeof val === "object" && val ? Object.keys(val).join(", ")
        : String(val ?? ""));
  };

  return Object.entries(forms).map(([label, f]) => {
    const t = document.createElement("img");
    setupIcon(t, f?.Icon ?? pNum, `${pName} — ${label}`, "full");
    const src = t.src;
    const types = wrapTypes(f?.Type || []);

    const line = (k) => {
      const val = f?.[k];
      if (!val) return "";
      const content = (/ability/i.test(k) && !/capabilit/i.test(k))
        ? linkifyAbilities(val)
        : (Array.isArray(val) ? val.join(", ")
          : (typeof val === "object" ? Object.keys(val).join(", ")
            : String(val)));
      return `<div class="small text-muted">${k}: <span class="text-body">${content}</span></div>`;
    };

    const stats = f?.Stats ? Object.entries(f.Stats).map(([k, v]) =>
      `<div class="d-flex justify-content-between small border-bottom"><span class="text-muted">${k}</span><span class="fw-semibold">${v}</span></div>`
    ).join("") : "";

    return `
      <div class="card accent w-100 mb-2"><div class="card-body">
        <div class="d-flex align-items-start gap-3">
          <div class="rounded dark-background p-1"><img class="dex-title-icon" src="${src}"></div>
          <div class="flex-grow-1">
            <div class="d-flex flex-wrap align-items-baseline gap-2">
              <span class="fw-semibold">${label}</span><span class="ms-1">${types}</span>
            </div>
            ${line("Ability")}${line("Adv Ability 1")}${line("Adv Ability 2")}${line("Adv Ability 3")}${line("High Ability")}${line("Capabilities")}
            ${stats ? `<div class="mt-2">${stats}</div>` : ""}
          </div>
        </div>
      </div></div>`;
  }).join("");
}

function renderTags(tags) {
  if (Array.isArray(tags) && tags.length)
    tags = tags.filter(t => SHOWN_TAGS.has(t));
  return Array.isArray(tags) && tags.length ? `<sup class="smaller text-uppercase text-muted ms-1">${escapeHtml(tags.join(" "))}</sup>` : "";
}

function renderTmTutorMovesComma(arr, title = "TM/Tutor Moves") {
  if (!Array.isArray(arr) || arr.length === 0) return "";
  const parts = arr.map(it => {
    if (typeof it === "string") return `<span class="small text-muted">${escapeHtml(it)}</span>`;
    const raw = it?.Move ?? "";
    const move = raw ? `<a href="#" class="js-move-link" data-move="${escapeHtml(raw)}">${escapeHtml(raw)}</a>` : "";
    const tagsSup = renderTags(it?.Tags);
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
    const tagsSup = renderTags(m?.Tags);
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
  const m = s.match(/(Damage Base.*)\s*:\s*(.+)$/i);
  if (m) {
    return `<div><span class="text-muted">${m[1]}:</span> ${m[2]}</div>`;
  }
  // fallback (raw may contain "4: 1d8+6 / 11" || just "1d8+6 / 11")
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
  if (!ab) return '<p class="text-muted mb-0">Unknown Ability.</p>';

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

function renderCapabilityDetails(cap) {
  if (!cap) return '<p class="text-muted mb-0">Unknown Capability.</p>';

  // cap.Effect est ajouté automatiquement par loadIndex() avec notre patch
  const text = cap.Effect || cap.effect || String(cap) || "";

  return `${escapeHtml(text)}
  `;
}

function renderObject(obj, depth = 0) {
  const leftSections = new Set(["Base Stats", "Basic Information", "Evolution", "Other Information", "Battle-Only Forms", "Confined"]);
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
          const block = renderEvolutionList(v, obj, depth);
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
      <div class="cap-item">
        <div class="cap-head">
          <a href="#" class="js-ability-link" data-capability="${escapeHtml(key)}">
            ${escapeHtml(key)}
          </a>
        </div>
        <div class="cap-val">${escapeHtml(String(value))}</div>
      </div>
    `).join("");

  const simple = parsed.simple.map(k => `
    <span class="cap-chip">
      <a href="#" class="js-ability-link" data-capability="${escapeHtml(k)}">
        ${escapeHtml(k)}
      </a>
    </span>
  `).join("");

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

function buildTypeSidebar(all, onChange) {
  const sidebar = $("#sidebar");
  if (!sidebar) return;

  // Inject compact CSS once
  (function ensureTypePillCSS() {
    if (document.getElementById("dex-typepill-style")) return;
    const s = document.createElement("style");
    s.id = "dex-typepill-style";
    s.textContent = `
        [data-role="type-filters"] #type-badges{display:flex;flex-wrap:wrap;gap:.25rem .25rem;margin-bottom:.25rem}
        .type-pill{padding:.15rem .4rem;font-size:.75rem;line-height:1;border-radius:9999px;border:1px solid rgba(255,255,255,.15);opacity:.95}
        .type-pill.active{outline:1px solid rgba(255,255,255,.25);opacity:1}
        [data-role="type-filters"] .btn-group.btn-group-sm .btn{padding:.15rem .35rem;font-size:.75rem}
        [data-role="type-filters"] .form-label{margin-bottom:.25rem}
      `;
    document.head.appendChild(s);
  })();

  let typesBox = sidebar.querySelector('[data-role="type-filters"]');
  const types = collectTypes(all);

  if (!typesBox) {
    typesBox = document.createElement("div");
    typesBox.setAttribute("data-role", "type-filters");

    typesBox.innerHTML = `
        <label class="form-label mt-2 d-flex align-items-center justify-content-between">
          <span>Types</span>
          <div class="btn-group btn-group-sm" role="group" aria-label="Type matching mode">
            <input type="radio" class="btn-check" name="type-mode" id="type-mode-any">
            <label class="btn btn-outline-primary" for="type-mode-any" title="Match any of the selected types">ANY</label>
            <input type="radio" class="btn-check" name="type-mode" id="type-mode-all">
            <label class="btn btn-outline-primary" for="type-mode-all" title="Must include all selected types">ALL</label>
          </div>
        </label>

        <div class="mb-2 d-flex gap-1 flex-wrap" id="type-badges"></div>

        <div class="mt-2">
          <label class="form-label mb-1">Learns move</label>
          <input id="filter-move" class="form-control form-control-sm" placeholder="eg: Thunderbolt or *bolt">
        </div>

        <div class="mt-2">
          <label class="form-label mb-1">Has ability</label>
          <input id="filter-ability" class="form-control form-control-sm" placeholder="eg: Intimidate or *date">
        </div>
        
        <div class="mt-2">
          <label class="form-label mb-1">Has capability</label>
          <input id="filter-capability" class="form-control form-control-sm" placeholder="eg: Underdog, under* or Mountable*">
        </div>

        <div class="mt-2">
          <button id="clear-filters" class="btn btn-sm btn-outline-secondary w-100">Clear filters</button>
        </div>
            `;

    const srcMenu = sidebar.querySelector('[data-role="source-menu"]');
    if (srcMenu) srcMenu.insertAdjacentElement("afterend", typesBox);
    else sidebar.prepend(typesBox);

    // Delegated once
    typesBox.addEventListener("change", (ev) => {
      const el = ev.target;
      if (!(el instanceof HTMLInputElement)) return;
      if (el.name === "type-mode") {
        TYPE_MATCH_MODE = el.id.endsWith("all") ? "all" : "any";
        onChange();
      }
    });
    typesBox.querySelector("#filter-move")?.addEventListener("input", debounce(onChange, 150));
    typesBox.querySelector("#filter-ability")?.addEventListener("input", debounce(onChange, 150));
    typesBox.querySelector("#filter-capability")?.addEventListener("input", debounce(onChange, 150));
    typesBox.querySelector("#clear-filters")?.addEventListener("click", () => {
      typesBox.querySelectorAll("button[data-type]").forEach(b => { b.setAttribute("data-selected", "0"); b.classList.remove("active"); });
      TYPE_MATCH_MODE = 'any';
      const anyRadio = typesBox.querySelector("#type-mode-any");
      if (anyRadio) anyRadio.checked = true;
      const moveInp = typesBox.querySelector("#filter-move");
      const abilInp = typesBox.querySelector("#filter-ability");
      const capaInp = typesBox.querySelector("#filter-capability");
      if (moveInp) moveInp.value = "";
      if (abilInp) abilInp.value = "";
      if (capaInp) capaInp.value = "";
      onChange();
    });
  }

  // Always refresh inline badges without duplicating the section
  const badgeWrap = typesBox.querySelector("#type-badges");
  badgeWrap.innerHTML = ""; // On nettoie au cas où

  buildPillSection(badgeWrap, "type-badges", types, {
    attr: "data-type",
    onChange
  });

  // Sync radios
  const anyRadio = typesBox.querySelector("#type-mode-any");
  const allRadio = typesBox.querySelector("#type-mode-all");
  if (anyRadio && allRadio) {
    anyRadio.checked = TYPE_MATCH_MODE === 'any';
    allRadio.checked = TYPE_MATCH_MODE === 'all';
  }
}


document.addEventListener('change', (ev) => {
  const t = ev.target;
  if (!(t instanceof Element)) return;
  if (t.matches('input[name="type-mode"]')) {
    window.TYPE_MATCH_MODE = t.id.endsWith('all') ? 'all' : 'any';
    // Re-render with the new mode
    try {
      const all = window.__pokedexData || [];
      renderGrid(filterRows(all));
    } catch { }
  }
}, true);

function activeTypes() {
  return getSelectedPills(
    document,
    "type-badges",
    "data-type"
  );
}

function pokemonHasCapability(p, queryRaw) {
  const matcher = __makeWildcardMatcher(queryRaw);
  if (!p || !p["Capabilities"]) return matcher("");
  const info = p["Capabilities"];

  for (const [k, v] of Object.entries(info)) {
    if (Array.isArray(v)) {
      if (v.some(x => matcher(String(x || "")))) return true;
    } else {
      if (matcher(String(v || ""))) return true;
    }
  }
  return false;
}

function pokemonHasAbility(p, queryRaw) {
  const matcher = __makeWildcardMatcher(queryRaw);
  if (!p || !p["Basic Information"]) return matcher("");
  const info = p["Basic Information"];

  for (const [k, v] of Object.entries(info)) {
    if (!/ability/i.test(k)) continue;

    if (Array.isArray(v)) {
      if (v.some(x => matcher(String(x || "")))) return true;
    } else {
      if (matcher(String(v || ""))) return true;
    }
  }
  return false;
}


function pokemonLearnsMove(p, queryRaw) {
  const matcher = __makeWildcardMatcher(queryRaw);
  if (!p || !p.Moves) return matcher("");

  const mv = p.Moves;
  const lists = [
    ...(Array.isArray(mv["Level Up Move List"]) ? mv["Level Up Move List"] : []),
    ...(Array.isArray(mv["TM/HM Move List"]) ? mv["TM/HM Move List"] : []),
    ...(Array.isArray(mv["Egg Move List"]) ? mv["Egg Move List"] : []),
    ...(Array.isArray(mv["Tutor Move List"]) ? mv["Tutor Move List"] : []),
    ...(Array.isArray(mv["TM/Tutor Moves List"]) ? mv["TM/Tutor Moves List"] : []),
  ];
  for (const it of lists) {
    const name = (typeof it === "string") ? it : (it?.Move || it?.Name || "");
    if (matcher(name)) return true;
  }
  return false;
}


function filterRows(rows) {
  const qRaw = ($("#dex-search")?.value || "").trim().toLowerCase();
  const types = activeTypes();
  const moveQ = ($("#filter-move")?.value || "").trim().toLowerCase();
  const abilQ = ($("#filter-ability")?.value || "").trim().toLowerCase();
  const capaQ = ($("#filter-capability")?.value || "").trim().toLowerCase();

  const out = rows.filter(p => {
    const name = (p.Species || "").toLowerCase();
    if (qRaw && !name.includes(qRaw)) {
      const num = String(p.Number || "");
      if (!num.includes(qRaw)) return false;
    }
    if (moveQ && !pokemonLearnsMove(p, moveQ)) return false;
    if (abilQ && !pokemonHasAbility(p, abilQ)) return false;
    if (capaQ && !pokemonHasCapability(p, capaQ)) return false;

    if (types.length) {
      const pTypes = speciesTypes(p);
      if (currentTypeMatchMode() === 'all') {
        for (const t of types) if (!pTypes.includes(t)) return false;
      } else {
        let ok = false;
        for (const t of types) if (pTypes.includes(t)) { ok = true; break; }
        if (!ok) return false;
      }
    }
    return true;
  }).sort((a, b) => (a.Number || 0) - (b.Number || 0));

  return out;
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

  const wrap = document.createElement("div");
  wrap.className = "mb-3 d-flex flex-column gap-2";
  wrap.setAttribute("data-role", "source-menu");
  wrap.innerHTML = `
      <div class="d-flex align-items-center gap-1">
        <button type="button"
                id="btn-pokesheets"
                class="btn btn-outline-primary"
                style="font-size:.75rem; padding:.1rem .4rem;">
          Pokésheets
        </button>
        <button type="button" 
                id="btn-readme"
                class="btn btn-primary"
                style="font-size:.75rem; padding:.1rem .25rem; min-width:unset; width:auto;">
          Readme
        </button>
      </div>
      <div class="d-flex align-items-center justify-content-between">
        <label class="form-label mb-0">Dataset</label>
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

  // Open Pokésheets modal (Homebrew only)
  wrap.querySelector("#btn-pokesheets")?.addEventListener("click", () => {
    bootstrap.Modal.getOrCreateInstance($("#pokesheetsModal")).show();
    // clear any previous feedback
    const fb = $("#pokesheets-feedback");
    if (fb) fb.textContent = "";
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
  const raw = String(moveName || "").trim();
  const base = raw.split("*")[0].trim(); // trim anything after '*' (eg. "Move* [...]" -> "Move")
  const name = base.toLowerCase();
  if (!name) return;
  const idx = await loadMoveIndex();
  // Also normalize moves in the index by trimming after '*'
  const found = Array.from(idx.entries()).find(([key, mv]) => {
    const moveBase = key.split("*")[0].trim().toLowerCase();
    return moveBase === name;
  });
  const mv = found ? found[1] : null;
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
  const ab = idx.get(name) || idx.get(name.split('(')[0].trim()) || null;
  const display = ab?.Name || ab?.__displayName || abilityName;
  $("#moveAbilityModalLabel").textContent = `Ability — ${display}`;
  $("#moveAbilityModalBody").innerHTML = renderAbilityDetails(ab);
  ensureMoveAbilityModal()?.show();
}

async function openCapabilityModalByName(capNameRaw) {
  const raw = String(capNameRaw || "").trim();
  if (!raw) return;

  const idx = await loadCapabilityIndex(); // Map(keys lowercase -> obj)

  // 1) Normalisation brute
  const exact = raw.toLowerCase();

  // 2) Recherche EXACTE
  let cap = idx.get(exact);

  // 3) Si "Mountable 1", chercher "Mountable X"
  if (!cap) {
    const baseWord = raw.split(/[ (]/)[0].trim().toLowerCase(); // "mountable"
    const maybe = Array.from(idx.entries()).find(([key]) =>
      key.startsWith(baseWord)   // mountable x
    );
    if (maybe) cap = maybe[1];
  }

  // 4) Cas Naturewalk (Forest) → chercher juste "naturewalk"
  if (!cap) {
    const base = raw.toLowerCase().split("(")[0].trim(); // "naturewalk"
    const maybe2 = idx.get(base);
    if (maybe2) cap = maybe2;
  }

  // 5) Dernière chance : fuzzy
  if (!cap) {
    const fuzzy = Array.from(idx.entries()).find(([key]) =>
      key.includes(exact)
      || exact.includes(key)
    );
    if (fuzzy) cap = fuzzy[1];
  }

  // Si toujours rien
  if (!cap) {
    ensureMoveAbilityModal()?.show();
    document.querySelector("#moveAbilityModalLabel").textContent =
      `Capability — ${raw}`;
    document.querySelector("#moveAbilityModalBody").innerHTML =
      `<p class="text-muted">No data for capability « ${escapeHtml(raw)} ».</p>`;
    return;
  }

  // Affichage
  const display = cap.Name || cap.__displayName || raw;
  const modal = ensureMoveAbilityModal();

  document.querySelector("#moveAbilityModalLabel").textContent =
    `Capability — ${display}`;

  document.querySelector("#moveAbilityModalBody").innerHTML =
    renderCapabilityDetails(cap);

  modal?.show();
}

document.addEventListener("click", (ev) => {
  const a = ev.target.closest("a.js-move-link, a.js-ability-link, a.js-capability-link");
  if (!a) return;
  ev.preventDefault();

  const move = a.dataset.move;
  const ability = a.dataset.ability;
  const capa = a.dataset.capability;

  if (move) openMoveModalByName(move);
  if (ability) openAbilityModalByName(ability);
  if (capa) openCapabilityModalByName(capa);
});


export async function loadPokedexPage() {
  // Initialisation des presets
  selectedLabels = new Set(PRESETS[selectedPreset] || []);

  // Construit le menu source + écouteurs
  buildSourceMenu();

  // Charge le pokédex
  const data = await loadPokedex();
  window.__POKEDEX = data;
  window.__pokedexData = data;

  // Fonction globale : open by species
  window.openModalBySpecies = (speciesName) => {
    const found = (window.__POKEDEX || []).find(
      p => String(p.Species || "").toLowerCase() === String(speciesName || "").toLowerCase()
    );
    if (found) openDetail(found);
  };

  // Paramètre ?species=xxx dans l’URL
  const params = new URLSearchParams(window.location.search);
  const s = params.get("species");
  if (s) openModalBySpecies(s);

  // Build filtres + grille
  buildTypeSidebar(data, () => renderGrid(filterRows(data)));
  wireSearch(data);
  renderGrid(filterRows(data));
}

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
  
  // Prioritize exact species name match (handles regional forms correctly)
  let target = null;
  if (species) {
    target = window.__pokedexData?.find(p =>
      String(p.Species).toLowerCase() === String(species).toLowerCase()
    );
  }
  // Fallback to number-only match if no species match found
  if (!target && number) {
    target = window.__pokedexData?.find(p =>
      String(p.Number) === String(number)
    );
  }
  
  if (target) openDetail(target);
});

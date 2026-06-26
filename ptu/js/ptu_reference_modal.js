import { DAMAGE_BASE_TABLE } from "/ptu/js/json_moves.js";

const DATA_BASE = "/ptu/data";
const REFERENCE_TYPES = ["move", "ability", "capability", "status", "edge", "pokeedge", "item", "feature", "keyword"];
const VALID_TYPES = new Set(REFERENCE_TYPES);

const FILES = {
  move: {
    Core: `${DATA_BASE}/moves/moves_core.min.json`,
    Community: `${DATA_BASE}/moves/moves_community.min.json`,
    Homebrew: `${DATA_BASE}/moves/moves_homebrew.min.json`
  },
  ability: {
    Core: `${DATA_BASE}/abilities/abilities_core.min.json`,
    Community: `${DATA_BASE}/abilities/abilities_community.min.json`,
    Homebrew: `${DATA_BASE}/abilities/abilities_homebrew.min.json`
  },
  capability: {
    Core: `${DATA_BASE}/capabilities/capabilities_core.min.json`,
    Community: `${DATA_BASE}/capabilities/capabilities_community.min.json`,
    Homebrew: `${DATA_BASE}/capabilities/capabilities_community.min.json`
  },
  status: {
    Core: `${DATA_BASE}/statuses/statuses_core.min.json`,
    Community: `${DATA_BASE}/statuses/statuses_homebrew.min.json`,
    Homebrew: `${DATA_BASE}/statuses/statuses_homebrew.min.json`
  },
  edge: {
    Core: `${DATA_BASE}/edges/edges_core.min.json`,
    Community: `${DATA_BASE}/edges/edges_homebrew.min.json`,
    Homebrew: `${DATA_BASE}/edges/edges_homebrew.min.json`
  },
  pokeedge: {
    Core: `${DATA_BASE}/pokeedges/pokeedges_core.min.json`,
    Community: `${DATA_BASE}/pokeedges/pokeedges_core.min.json`,
    Homebrew: `${DATA_BASE}/pokeedges/pokeedges_core.min.json`
  },
  item: {
    Core: `${DATA_BASE}/items/items_core.min.json`,
    Community: `${DATA_BASE}/items/items_community.min.json`,
    Homebrew: `${DATA_BASE}/items/items_community.min.json`
  },
  feature: {
    Core: `${DATA_BASE}/features/features_core.min.json`,
    Community: `${DATA_BASE}/features/features_homebrew.min.json`,
    Homebrew: `${DATA_BASE}/features/features_homebrew.min.json`
  },
  keyword: {
    Core: `${DATA_BASE}/moves/keywords_core.min.json`,
    Community: `${DATA_BASE}/moves/keywords_community.min.json`,
    Homebrew: `${DATA_BASE}/moves/keywords_community.min.json`
  }
};

const FANDEX_FILES = {
  move: {
    Insurgence: `${DATA_BASE}/moves/fandex/moves_insurgence.min.json`,
    Sage: `${DATA_BASE}/moves/fandex/moves_sage.min.json`,
    Uranium: `${DATA_BASE}/moves/fandex/moves_uranium.min.json`
  },
  ability: {
    Insurgence: `${DATA_BASE}/abilities/fandex/abilities_insurgence.min.json`,
    Sage: `${DATA_BASE}/abilities/fandex/abilities_sage.min.json`,
    Uranium: `${DATA_BASE}/abilities/fandex/abilities_uranium.min.json`
  },
  capability: {
    Insurgence: `${DATA_BASE}/capabilities/fandex/capabilities_insurgence.min.json`,
    Sage: `${DATA_BASE}/capabilities/fandex/capabilities_sage.min.json`,
    Uranium: `${DATA_BASE}/capabilities/fandex/capabilities_uranium.min.json`
  }
};

const NAME_FIELDS = {
  move: ["Move", "Name"],
  ability: ["Name"],
  capability: ["Name"],
  status: ["Name"],
  edge: ["Name"],
  pokeedge: ["Name"],
  item: ["Name"],
  feature: ["Name"],
  keyword: ["Name"]
};

const REFERENCE_TYPE_PATTERN = REFERENCE_TYPES.join("|");

let provider = {};
let initialized = false;
let observer = null;
let modalInstance = null;
let parsing = false;

const fetchCache = new Map();
const indexCache = new Map();

export function configureReferenceModal(nextProvider = {}) {
  provider = { ...provider, ...nextProvider };
  clearReferenceCache();
}

export function clearReferenceCache() {
  fetchCache.clear();
  indexCache.clear();
}

export function initReferenceLinks(root = document.body) {
  if (!root || initialized) return;
  initialized = true;
  window.__ptuReferenceModalHandlesClicks = true;
  ensureReferenceModal();
  linkReferenceTokens(root);
  document.addEventListener("click", handleReferenceClick);
  observer = new MutationObserver(mutations => {
    if (parsing) return;
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType === Node.TEXT_NODE || node.nodeType === Node.ELEMENT_NODE) {
          linkReferenceTokens(node);
        }
      }
    }
  });
  observer.observe(root, { childList: true, subtree: true });
}

export function linkReferenceTokens(root = document.body) {
  if (!root || parsing) return;
  parsing = true;
  try {
    const textNodes = [];
    const walkerRoot = root.nodeType === Node.TEXT_NODE ? root.parentNode : root;
    if (!walkerRoot) return;

    if (root.nodeType === Node.TEXT_NODE) {
      if (hasReferenceToken(root.nodeValue) && canReplaceTextNode(root)) textNodes.push(root);
    } else {
      const walker = document.createTreeWalker(walkerRoot, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          if (!hasReferenceToken(node.nodeValue) || !canReplaceTextNode(node)) {
            return NodeFilter.FILTER_REJECT;
          }
          return NodeFilter.FILTER_ACCEPT;
        }
      });
      let node;
      while ((node = walker.nextNode())) textNodes.push(node);
    }

    for (const node of textNodes) replaceReferenceTextNode(node);
  } finally {
    parsing = false;
  }
}

export async function openReferenceModal(typeRaw, nameRaw) {
  const type = normalizeType(typeRaw);
  const name = cleanLookupName(nameRaw);
  if (!type || !name) return;

  const modal = ensureReferenceModal();
  const labelEl = document.querySelector("#moveAbilityModalLabel");
  const bodyEl = document.querySelector("#moveAbilityModalBody");
  if (!modal || !labelEl || !bodyEl) return;

  labelEl.textContent = `${titleCase(type)} — ${name}`;
  bodyEl.innerHTML = `<p class="text-muted mb-0">Loading...</p>`;
  modal.show();

  const entry = await findEntry(type, name);
  const display = getDisplayName(type, entry, name);
  labelEl.innerHTML = renderReferenceTitle(type, display, entry);
  bodyEl.innerHTML = renderDetails(type, entry, name);
  modal.handleUpdate?.();
}

function handleReferenceClick(ev) {
  const a = ev.target.closest("a.js-reference-link, a.js-reference-link, a.js-reference-link, a.js-capability-link");
  if (!a) return;

  const type = a.dataset.refType || REFERENCE_TYPES.find(candidate => a.dataset[candidate]);
  const name = a.dataset.refName || (type ? a.dataset[type] : "") || a.textContent;
  if (!type || !name) return;

  ev.preventDefault();
  openReferenceModal(type, name);
}

function ensureReferenceModal() {
  let el = document.querySelector("#moveAbilityModal");
  if (!el) {
    document.body.insertAdjacentHTML("beforeend", `
      <div class="modal fade" id="moveAbilityModal" data-bs-scroll="true" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-lg modal-dialog-scrollable modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="moveAbilityModalLabel">Details</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body" id="moveAbilityModalBody"></div>
            <div class="modal-footer">
              <button class="btn btn-primary" data-bs-dismiss="modal">Close</button>
            </div>
          </div>
        </div>
      </div>`);
    el = document.querySelector("#moveAbilityModal");
  }
  if (!el || !window.bootstrap?.Modal) return null;
  modalInstance = window.bootstrap.Modal.getOrCreateInstance(el, { backdrop: true });
  return modalInstance;
}

function hasReferenceToken(text) {
  return new RegExp(`\\[\\[\\s*(${REFERENCE_TYPE_PATTERN})\\s*:[^\\]]+\\]\\](?:\\([^)]*\\))?`, "i").test(text || "");
}

function canReplaceTextNode(node) {
  const parent = node.parentElement;
  if (!parent) return false;
  if (parent.closest("script, style, textarea, code, pre, a, button, select, option")) return false;
  if (parent.closest("#moveAbilityModal")) return false;
  return true;
}

function replaceReferenceTextNode(node) {
  const text = node.nodeValue;
  const rx = new RegExp(`\\[\\[\\s*(${REFERENCE_TYPE_PATTERN})\\s*:\\s*([^\\]]+?)\\s*\\]\\](?:\\(([^)]*)\\))?`, "gi");
  let last = 0;
  let match;
  const frag = document.createDocumentFragment();

  while ((match = rx.exec(text))) {
    if (match.index > last) frag.appendChild(document.createTextNode(text.slice(last, match.index)));
    const type = normalizeType(match[1]);
    const name = match[2].trim();
    const label = (match[3] || "").trim() || name;
    frag.appendChild(createReferenceLink(type, name, label));
    last = rx.lastIndex;
  }
  if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
  node.parentNode.replaceChild(frag, node);
}

function createReferenceLink(type, name, label = name) {
  const a = document.createElement("a");
  a.href = "#";
  a.className = `js-reference-link js-${type}-link`;
  a.dataset.refType = type;
  a.dataset.refName = name;
  a.dataset[type] = name;
  a.textContent = label;
  return a;
}

async function findEntry(type, nameRaw) {
  const idx = await loadReferenceIndex(type);
  const name = normalizeKey(nameRaw);
  if (idx.has(name)) return idx.get(name);

  if (type === "move") {
    const base = normalizeKey(String(nameRaw).split("*")[0]);
    for (const [key, value] of idx) {
      if (normalizeKey(key.split("*")[0]) === base) return value;
    }
  }

  if (type === "ability") {
    const base = normalizeKey(String(nameRaw).split("(")[0]);
    return idx.get(base) || null;
  }

  if (type === "capability") {
    const raw = String(nameRaw);
    const baseWord = normalizeKey(raw.split(/[ (]/)[0]);
    const parenBase = normalizeKey(raw.split("(")[0]);
    return idx.get(parenBase)
      || Array.from(idx.entries()).find(([key]) => key.startsWith(baseWord))?.[1]
      || Array.from(idx.entries()).find(([key]) => key.includes(name) || name.includes(key))?.[1]
      || null;
  }

  return Array.from(idx.entries()).find(([key]) => key.includes(name) || name.includes(key))?.[1] || null;
}

async function loadReferenceIndex(type) {
  const cacheKey = `${type}:${getPreset()}:${getFanDexBase()}:${getSelectedLabels().join("|")}`;
  if (indexCache.has(cacheKey)) return indexCache.get(cacheKey);
  const promise = buildReferenceIndex(type);
  indexCache.set(cacheKey, promise);
  return promise;
}

async function buildReferenceIndex(type) {
  const urls = getReferenceUrls(type);
  const maps = await Promise.all(urls.map(({ url, source, label }) =>
    loadSingleIndex(type, url).then(idx => ({ idx, source, label }))
  ));

  const merged = new Map();
  for (const { idx, source, label } of maps) {
    for (const [key, value] of idx) {
      const next = { ...value, __source: source, __fandexLabel: label || value.__fandexLabel };
      if (merged.has(key) && source === "fandex") {
        next.__override = true;
        next.__baseEntry = merged.get(key);
      }
      merged.set(key, next);
    }
  }
  return merged;
}

async function loadSingleIndex(type, url) {
  const raw = await fetchJson(url);
  const idx = new Map();

  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    if (type === "item") {
      flattenItems(raw).forEach(item => addIndexItem(idx, type, item));
      return idx;
    }
    if (type === "feature") {
      flattenFeatures(raw).forEach(item => addIndexItem(idx, type, item));
      return idx;
    }
    if (type === "status") {
      for (const [section, entries] of Object.entries(raw)) {
        if (!entries || typeof entries !== "object") continue;
        for (const [name, value] of Object.entries(entries)) {
          const obj = typeof value === "string"
            ? { Name: name, Description: value, Section: section }
            : { Name: name, Section: section, ...value };
          addIndexItem(idx, type, obj, name);
        }
      }
      return idx;
    }
    for (const [name, value] of Object.entries(raw)) {
      const obj = typeof value === "string" ? { Name: name, Effect: value } : { Name: name, ...value };
      addIndexItem(idx, type, obj, name);
    }
    return idx;
  }

  if (Array.isArray(raw)) {
    raw.forEach(item => addIndexItem(idx, type, item));
  }
  return idx;
}

function addIndexItem(idx, type, item, fallbackName = "") {
  if (!item || typeof item !== "object") return;
  const fields = NAME_FIELDS[type] || ["Name"];
  const name = fields.map(field => item[field]).find(Boolean) || fallbackName;
  if (!name) return;
  const displayName = String(name).trim();
  idx.set(normalizeKey(displayName), { ...item, __displayName: displayName });
}

function flattenItems(data) {
  const out = [];
  for (const [category, catData] of Object.entries(data || {})) {
    if (!catData || typeof catData !== "object") continue;
    for (const [subcategory, entries] of Object.entries(catData)) {
      if (subcategory === "_display" || !Array.isArray(entries)) continue;
      entries.forEach(item => {
        if (item && typeof item === "object") {
          out.push({ ...item, Category: category, Subcategory: subcategory });
        }
      });
    }
  }
  return out;
}

function flattenFeatures(data) {
  const out = [];
  for (const [className, classData] of Object.entries(data || {})) {
    if (!classData || typeof classData !== "object") continue;
    const branches = Array.isArray(classData.branches) ? classData.branches : [];
    for (const branch of branches) {
      const features = Array.isArray(branch?.features) ? branch.features : [];
      for (const feature of features) {
        if (feature && typeof feature === "object") {
          out.push({
            ...feature,
            Class: className,
            Branch: branch.Name || "Default",
            Category: feature.Category || classData.category,
            Source: feature.Source || classData.source
          });
        }
      }
    }
  }
  return out;
}

async function fetchJson(url) {
  if (!url) return [];
  if (fetchCache.has(url)) return fetchCache.get(url);
  const promise = fetch(url, { cache: "no-store" })
    .then(r => r.ok ? r.json() : [])
    .catch(err => {
      console.warn("[ptu_reference_modal] failed to load", url, err);
      return [];
    });
  fetchCache.set(url, promise);
  return promise;
}

function getReferenceUrls(type) {
  const preset = getPreset();
  if (preset === "FanDex" && FANDEX_FILES[type]) {
    const base = getFanDexBase();
    const labels = getSelectedLabels();
    const urls = [{ url: FILES[type][base] || FILES[type].Core, source: "base" }];
    for (const label of labels) {
      if (FANDEX_FILES[type][label]) urls.push({ url: FANDEX_FILES[type][label], source: "fandex", label });
    }
    return urls;
  }
  const files = FILES[type] || {};
  const url = files[preset] || files.Community || files.Core;
  return [{ url, source: "base" }];
}

function getPreset() {
  if (typeof provider.getPreset === "function") return provider.getPreset() || "Community";
  if (window.selectedPreset) return window.selectedPreset;
  const path = window.location.pathname.toLowerCase();
  if (path.includes("/ptucore/")) return "Core";
  if (path.includes("/ptuhomebrew/")) return "Homebrew";
  if (path.includes("/ptucommunity/")) return "Community";
  return "Community";
}

function getFanDexBase() {
  return typeof provider.getFanDexBase === "function" ? provider.getFanDexBase() || "Core" : "Core";
}

function getSelectedLabels() {
  if (typeof provider.getSelectedLabels === "function") {
    return Array.from(provider.getSelectedLabels() || []);
  }
  return [];
}

function renderDetails(type, entry, requestedName) {
  if (!entry) return `<p class="text-muted mb-0">No data for ${escapeHtml(titleCase(type))} "${escapeHtml(requestedName)}".</p>`;
  if (type === "move") return renderMoveDetails(entry);
  if (type === "ability") return renderAbilityDetails(entry);
  if (type === "capability") return renderCapabilityDetails(entry);
  return renderReferenceGenericDetails(entry);
}

function renderMoveDetails(mv) {
  const source = renderSourceAndOverride(mv, "move", renderMoveDetailsCore);
  return source + renderMoveDetailsCore(mv);
}

function renderMoveDetailsCore(mv) {
  const row = (k, v) => isBlank(v) ? "" : `<div><span class="text-muted">${escapeHtml(k)}:</span> ${escapeHtml(String(v))}</div>`;
  const tags = Array.isArray(mv.Tags) && mv.Tags.length ? mv.Tags.join(", ") : (mv.Keywords || mv.Keyword || "");
  const effectKeys = Object.keys(mv).filter(k => /effect/i.test(k) && !["Contest Type", "Contest Effect"].includes(k));
  const effects = effectKeys.map(k => {
    const value = mv[k];
    if (isBlank(value)) return "";
    return /^effect$/i.test(k)
      ? `<div style="white-space:pre-wrap">${escapeHtml(String(value))}</div>`
      : `<div style="white-space:pre-wrap"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(value))}</div>`;
  }).filter(Boolean);

  return `
    ${row("Frequency", mv.Frequency)}
    ${row("AC", mv.AC)}
    ${formatDamageBase(mv)}
    ${row("Class", mv.Class)}
    ${row("Range", mv.Range)}
    ${row("Keywords", tags)}
    ${row("Target", mv.Target)}
    ${row("Trigger", mv.Trigger)}
    ${effects.length ? `<hr class="my-2">${effects.join("")}` : ""}
  `;
}

function renderAbilityDetails(ab) {
  const source = renderSourceAndOverride(ab, "ability", renderAbilityDetailsCore);
  return source + renderAbilityDetailsCore(ab);
}

function renderAbilityDetailsCore(ab) {
  const row = (k, v) => isBlank(v) ? "" : `<div><span class="text-muted">${escapeHtml(k)}:</span> ${escapeHtml(String(v))}</div>`;
  const effectKeys = Object.keys(ab).filter(k => /(effect|bonus|special)/i.test(k));
  const effects = effectKeys.map(k => {
    const value = ab[k];
    if (isBlank(value)) return "";
    return /^effect$/i.test(k)
      ? `<div style="white-space:pre-wrap">${escapeHtml(String(value))}</div>`
      : `<div style="white-space:pre-wrap"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(value))}</div>`;
  }).filter(Boolean);
  return `${row("Frequency", ab.Frequency)}${row("Target", ab.Target)}${row("Trigger", ab.Trigger)}${effects.length ? `<hr class="my-2">${effects.join("")}` : ""}`;
}

function renderCapabilityDetails(cap) {
  const source = renderSourceAndOverride(cap, "capability", base => escapeHtml(base.Effect || base.effect || String(base) || ""));
  const text = cap.Effect || cap.effect || cap.Description || "";
  return `${source}<div style="white-space:pre-wrap">${escapeHtml(text)}</div>`;
}

function renderReferenceTitle(type, display, entry) {
  if (type === "move") {
    const typeHtml = entry?.Type ? wrapTypes([entry.Type]) : "";
    return `<div><div class="fw-semibold">Move — ${escapeHtml(display)}</div><div class="mt-1">${typeHtml}</div></div>`;
  }
  return `
    <div>
      <div class="d-flex flex-wrap align-items-center gap-2">
        <span class="fw-semibold">${titleCase(type)} — ${escapeHtml(display)}</span>
        ${renderReferenceTitleBadges(entry)}
      </div>
    </div>`;
}

function renderReferenceTitleBadges(entry) {
  if (!entry) return "";
  const badges = [];
  const source = entry.Source || entry.source || entry.__fandexLabel;
  const category = entry.Category || entry.category || entry.Subcategory || entry.Class;
  if (source) badges.push(`<span class="badge bg-info">${escapeHtml(String(source))}</span>`);
  if (category) badges.push(`<span class="badge bg-secondary">${escapeHtml(String(category))}</span>`);
  return badges.join("");
}

function renderReferenceGenericDetails(entry) {
  const rows = Object.entries(entry)
    .filter(([key, value]) => !key.startsWith("__") && !["Name", "Move", "Source", "source", "Category", "category"].includes(key) && !isBlank(value))
    .map(([key, value]) => `<div class="mb-2"><span class="text-muted">${escapeHtml(key)}:</span> ${renderReferenceGenericValue(value)}</div>`);
  return rows.length ? rows.join("") : '<p class="text-muted mb-0">No details available.</p>';
}

function renderReferenceGenericValue(value) {
  if (Array.isArray(value)) {
    if (!value.length) return "";
    return `<div class="mt-1 ms-3">${value.map(item => `<div>${renderReferenceGenericValue(item)}</div>`).join("")}</div>`;
  }
  if (value && typeof value === "object") {
    return `<div class="mt-1 ms-3">${Object.entries(value)
      .filter(([key, child]) => !key.startsWith("__") && !isBlank(child))
      .map(([key, child]) => `<div><span class="text-muted">${escapeHtml(key)}:</span> ${renderReferenceGenericValue(child)}</div>`)
      .join("")}</div>`;
  }
  return escapeHtml(String(value)).replaceAll("\n", "<br>");
}

function renderSourceAndOverride(entry, noun, renderBase) {
  let html = "";
  if (entry.__source === "fandex" && entry.__fandexLabel) {
    html += `<span class="badge bg-info mb-2">Source: ${escapeHtml(entry.__fandexLabel)}</span><br>`;
  }
  if (entry.__override && entry.__baseEntry) {
    html += `
      <div class="alert alert-warning mb-3" role="alert">
        <strong>Warning — Override:</strong> This ${escapeHtml(noun)} exists in both the base dataset and FanDex.
        <details class="mt-2">
          <summary style="cursor: pointer; user-select: none;">Show base version</summary>
          <div class="mt-2 p-2 border rounded bg-light">${renderBase(entry.__baseEntry)}</div>
        </details>
      </div>`;
  }
  return html;
}

function formatDamageBase(mv) {
  const raw = mv?.["Damage Base"] || mv?.DB || "";
  if (isBlank(raw)) return "";
  const match = String(raw).match(/\d+/);
  if (!match) return `<div><span class="text-muted">Damage Base:</span> ${escapeHtml(String(raw))}</div>`;
  const value = Number.parseInt(match[0], 10);
  const info = DAMAGE_BASE_TABLE[value];
  return info
    ? `<div><span class="text-muted">Damage Base:</span> ${escapeHtml(String(value))} (${escapeHtml(info.dmg)} / ${escapeHtml(String(info.avg))})</div>`
    : `<div><span class="text-muted">Damage Base:</span> ${escapeHtml(String(value))}</div>`;
}

function wrapTypes(types) {
  return (types || []).filter(Boolean).map(t => `<span class="badge badge-type card-type-${escapeHtml(String(t))}">${escapeHtml(String(t))}</span>`).join(" ");
}

function getDisplayName(type, entry, fallback) {
  if (!entry) return fallback;
  return entry.Move || entry.Name || entry.__displayName || NAME_FIELDS[type]?.map(field => entry[field]).find(Boolean) || fallback;
}

function normalizeType(type) {
  const value = String(type || "").trim().toLowerCase();
  return VALID_TYPES.has(value) ? value : "";
}

function normalizeKey(value) {
  return cleanLookupName(value).toLowerCase().replace(/\*+$/, "");
}

function cleanLookupName(value) {
  return String(value || "").trim();
}

function titleCase(value) {
  if (value === "pokeedge") return "Poke Edge";
  return String(value || "").replace(/^./, c => c.toUpperCase());
}

function isBlank(value) {
  if (value == null) return true;
  const text = String(value).trim();
  return !text || /^none\.?$/i.test(text);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[c]));
}

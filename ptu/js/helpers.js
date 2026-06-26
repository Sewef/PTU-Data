export function includeHTML(callback) {
  const finish = () => {
    if (callback) callback();
    setupVersionSwitcher();
    if (typeof window.initThemeSwitcher === 'function') {
      window.initThemeSwitcher();
    }
    initPTUReferenceLinks();
  };

  const elements = document.querySelectorAll('[w3-include-html]');
  let total = elements.length;
  if (total === 0) {
    finish();
  }

  elements.forEach(el => {
    const file = el.getAttribute("w3-include-html");
    if (!file) {
      total--;
      return;
    }

    fetch(file)
      .then(resp => {
        if (!resp.ok) {
          console.error(`Failed to load ${file}: ${resp.status} ${resp.statusText}`);
          throw new Error(`Page not found: ${resp.status}`);
        }
        return resp.text();
      })
      .then(data => {
        el.innerHTML = data;
        el.removeAttribute("w3-include-html");
        total--;
        if (total === 0) {
          finish();
          return;
        }
      })
      .catch(err => {
        console.error(`Include error for ${file}:`, err);
        el.innerHTML = `Include failed: ${err.message}`;
        total--;
        if (total === 0) {
          finish();
          return;
        }
      });
  });
}

function initPTUReferenceLinks() {
  if (window.PTU_REFERENCE_LINKS_DISABLED === true) return;
  import("/ptu/js/ptu_reference_modal.js")
    .then(module => module.initReferenceLinks?.())
    .catch(err => console.warn("[helpers] Reference links unavailable:", err));
}

export function setActive() {
  const navLinks = document.querySelectorAll('.nav-link');
  const currentPage = window.location.pathname.split("/").pop();

  if (navLinks.length === 0) {
    setTimeout(setActive, 100); // Retry after 100ms
    return;
  }

  navLinks.forEach(link => {
    const linkHref = link.getAttribute("href");
    if (linkHref === currentPage) {
      link.classList.add("active");
      link.setAttribute("aria-current", "page");
    } else {
      link.classList.remove("active");
      link.removeAttribute("aria-current");
    }
  });
}

export function showPageWhenLoaded() {  
  $(function () {
    $('body').show();
  }); // end ready
}

// ===============================
//  ES6 HELPERS — Version minimale
// ===============================

// --- Debounce ---
export function debounce(fn, delay = 150) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}

// --- JSON utils ---
export function jsonToItems(obj) {
  return Object.entries(obj).map(([name, value]) =>
    typeof value === "string"
      ? { Name: name, Description: value }
      : { Name: name, ...value }
  );
}

// --- Build pill filter section ---
export function buildPillSection(root, id, values, { attr = "data-type", onChange, useTypeClass = true } = {}) {
  const container = document.createElement("div");
  container.id = id;
  container.className = "d-flex flex-wrap gap-1";

  values.forEach(v => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-sm type-pill";
    
    if (useTypeClass) {
      // Sanitize class name: remove spaces and special chars
      const sanitizedClass = `card-type-${v.replace(/\s+/g, '')}`;
      btn.classList.add(sanitizedClass);
    }
    
    btn.setAttribute(attr, v);
    btn.setAttribute("data-selected", "0");
    btn.textContent = v;
    container.appendChild(btn);
  });

  container.addEventListener("click", ev => {
    const btn = ev.target.closest(`button[${attr}]`);
    if (!btn) return;

    const state = btn.getAttribute("data-selected") === "1";
    btn.setAttribute("data-selected", state ? "0" : "1");
    btn.classList.toggle("active", !state);

    if (onChange) onChange();
  });

  root.appendChild(container);
  return container;
}

// --- Get selected pills ---
export function getSelectedPills(root, id, attr = "data-type") {
  const zone = root.querySelector(`#${id}`);
  if (!zone) return [];
  return Array.from(zone.querySelectorAll(`button[${attr}][data-selected="1"]`))
    .map(btn => btn.getAttribute(attr));
}

// --- Generic text filter ---
export function filterText(query, item) {
  if (!query) return true;
  return Object.values(item).some(v =>
    typeof v === "string" && v.toLowerCase().includes(query)
  );
}

// --- Type / Class filters ---
export function filterByTypes(item, types) {
  if (!types.length) return true;
  return types.includes(item.Type);
}

export function filterByClasses(item, classes) {
  if (!classes.length) return true;
  return classes.includes(item.Class);
}

// --- Damage Base filter ---
export function filterByDamageBase(item, damageBases) {
  if (!damageBases.length) return true;
  // Extract numeric value from Damage Base
  const damageBase = item["Damage Base"];
  if (!damageBase) return false;
  const match = String(damageBase).match(/\d+/);
  if (!match) return false;
  return damageBases.includes(match[0]);
}

// --- Effect filter ---
export function filterByEffect(item, hasEffectFilter) {
  if (!hasEffectFilter.length) return true;
  
  const hasWithEffect = hasEffectFilter.includes("With Effect");
  const hasNoEffect = hasEffectFilter.includes("No Effect");
  
  // Si les deux sont sélectionnés, montrer tout
  if (hasWithEffect && hasNoEffect) return true;
  
  // Helper pour vérifier si une valeur est vide ou "None"
  const isNoneOrEmpty = (value) => {
    if (!value) return true;
    const str = String(value).trim().toLowerCase();
    return str === "" || str === "none" || str === "none.";
  };
  
  // Vérifier si le move a un effet réel
  const effect = item.Effect || "";
  const setUpEffect = item["Set-Up Effect"] || "";
  
  const moveHasEffect = !isNoneOrEmpty(effect) || !isNoneOrEmpty(setUpEffect);
  
  if (hasWithEffect) return moveHasEffect;
  if (hasNoEffect) return !moveHasEffect;
  
  return true;
}

// --- Contest Type filter ---
export function filterByContestType(item, contestTypes) {
  if (!contestTypes.length) return true;
  return contestTypes.includes(item["Contest Type"]);
}

// --- Contest Effect filter ---
export function filterByContestEffect(item, contestEffects) {
  if (!contestEffects.length) return true;
  return contestEffects.includes(item["Contest Effect"]);
}

// --- Frequency filter ---
export function filterByFrequency(item, frequencies) {
  if (!frequencies.length) return true;
  return frequencies.includes(item["Frequency"]);
}

// --- Range Distance filter ---
export function filterByRangeDistance(item, rangeDistances) {
  if (!rangeDistances.length) return true;
  const range = item.Range || "";
  
  // Split by "; or " to separate variants
  const variants = range.split(/;\s*or\s+/i).map(v => v.trim());
  const distances = new Set();
  
  variants.forEach(variant => {
    const parts = variant.split(',').map(p => p.trim());
    
    parts.forEach(part => {
      // Si c'est Melee
      if (part.toLowerCase().includes('melee')) {
        distances.add('Melee');
      }
      // Si c'est un nombre isolé (pas suivi d'un mot comme "1 Target")
      const match = part.match(/^(\d+)$/);
      if (match) {
        distances.add(match[1]);
      }
      // Extraire les nombres dans "Cone 2", "Line 6", etc.
      const keywordMatch = part.match(/^(Cone|Line|Burst|Close Blast|Blast)\s+(\d+)$/i);
      if (keywordMatch) {
        distances.add(keywordMatch[2]);
      }
    });
  });
  
  return rangeDistances.some(d => distances.has(d));
}

// --- Range Keyword filter ---
export function filterByRangeKeyword(item, rangeKeywords) {
  if (!rangeKeywords.length) return true;
  const range = item.Range || "";
  
  // Split by "; or " to separate variants
  const variants = range.split(/;\s*or\s+/i).map(v => v.trim());
  const keywords = new Set();
  
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
          keywords.add('Recoil');
          return;
        }
        
        // Pattern "Burst 1*", "Cone 2*", etc. -> garder seulement le mot-clé
        const asteriskMatch = subPart.match(/^(Cone|Line|Burst|Close Blast|Blast)\s+\d+\*$/i);
        if (asteriskMatch) {
          keywords.add(asteriskMatch[1]);
          return;
        }
        
        // Extraire les patterns comme "Cone 2", "Line 6", etc. en gardant que le mot
        const keywordMatch = subPart.match(/^(Cone|Line|Burst|Close Blast|Blast)\s+\d+$/i);
        if (keywordMatch) {
          keywords.add(keywordMatch[1]);
          return;
        }
        
        // Pour les autres, enlever les nombres et garder les mots
        const cleaned = subPart.replace(/\d+/g, '').trim();
        // Exclure 'melee', 'target' et 'targets' (gérés par d'autres filtres)
        const lowerCleaned = cleaned.toLowerCase();
        if (cleaned && lowerCleaned !== 'melee' && lowerCleaned !== 'target' && lowerCleaned !== 'targets') {
          keywords.add(cleaned);
        }
      });
    });
  });
  
  return rangeKeywords.some(k => keywords.has(k));
}

// --- Targeting filter (Single vs Multi) ---
export function filterByTargeting(item, targeting) {
  if (!targeting.length) return true;
  const range = item.Range || "";
  
  const hasSingleTarget = targeting.includes("Single Target");
  const hasMultiTarget = targeting.includes("Multi Target");
  
  // Si les deux sont sélectionnés, montrer tout
  if (hasSingleTarget && hasMultiTarget) return true;
  
  // Split by "; or " to separate variants and check each one
  const variants = range.split(/;\s*or\s+/i).map(v => v.trim());
  
  let isSingleTarget = false;
  let isMultiTarget = false;
  
  variants.forEach(variant => {
    // Single target: "1 Target" uniquement
    if (/\b1\s+target\b/i.test(variant)) {
      isSingleTarget = true;
    }
    
    // Multi target: Cone, Line, Burst, Blast, "X Targets" (X > 1), All, etc.
    if (/\b(cone|line|burst|blast|all)\b/i.test(variant) ||
        /\b([2-9]|\d{2,})\s+targets?\b/i.test(variant)) {
      isMultiTarget = true;
    }
  });
  
  if (hasSingleTarget && isSingleTarget) return true;
  if (hasMultiTarget && isMultiTarget) return true;
  
  return false;
}

// --- Version Switcher ---
export function setupVersionSwitcher() {
  const links = document.querySelectorAll('.dropdown-menu a.dropdown-item');
  const currentPath = window.location.pathname;
  const hash = window.location.hash; // Préserver le hash (état de la page)
  const currentFile = currentPath.split('/').pop() || 'index.html';

  links.forEach(link => {
    const href = link.getAttribute('href');
    if (!href) return; // Skip if no href
    const newPath = href.replace(/[^/]*\.html$/, currentFile);
    link.href = newPath + hash;
  });
}

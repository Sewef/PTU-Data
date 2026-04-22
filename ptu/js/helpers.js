export function includeHTML(callback) {
  const elements = document.querySelectorAll('[w3-include-html]');
  let total = elements.length;
  if (total === 0 && callback) {
    callback();
    setupVersionSwitcher();
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
        if (total === 0 && callback) {
          callback(); // callback après tous les includes
          setupVersionSwitcher();
          // Réinitialiser le theme switcher après inclusion du header
          if (typeof window.initThemeSwitcher === 'function') {
            window.initThemeSwitcher();
          }
        }
      })
      .catch(err => {
        console.error(`Include error for ${file}:`, err);
        el.innerHTML = `Include failed: ${err.message}`;
        total--;
        if (total === 0 && callback) {
          callback();
          setupVersionSwitcher();
        }
      });
  });
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
export function buildPillSection(root, id, values, { attr = "data-type", onChange } = {}) {
  const container = document.createElement("div");
  container.id = id;
  container.className = "d-flex flex-wrap gap-1";

  container.innerHTML = values.map(v => `
    <button type="button"
      class="btn btn-sm type-pill card-type-${v}"
      ${attr}="${v}"
      data-selected="0"
    >${v}</button>
  `).join("");

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
export function includeHTML(callback) {
  const elements = document.querySelectorAll('[w3-include-html]');
  let total = elements.length;
  if (total === 0 && callback) callback();

  elements.forEach(el => {
    const file = el.getAttribute("w3-include-html");
    if (!file) {
      total--;
      return;
    }

    fetch(file)
      .then(resp => {
        if (!resp.ok) throw new Error("Page not found");
        return resp.text();
      })
      .then(data => {
        el.innerHTML = data;
        el.removeAttribute("w3-include-html");
        total--;
        if (total === 0 && callback) callback(); // callback après tous les includes
      })
      .catch(err => {
        el.innerHTML = "Include failed.";
        total--;
        if (total === 0 && callback) callback();
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
function includeHTML(callback) {
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


function setActive() {
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


function showPageWhenLoaded() {  
  $(function () {
    $('body').show();
  }); // end ready
}
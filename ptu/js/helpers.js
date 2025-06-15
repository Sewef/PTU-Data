function includeHTML() {
  var z, i, elmnt, file, xhttp;
  document.body.style.display = 'none'; // Hide body initially
  // Loop through a collection of all HTML elements: 
  z = document.getElementsByTagName("*");
  for (i = 0; i < z.length; i++) {
    elmnt = z[i];
    // search for elements with a certain atrribute:
    file = elmnt.getAttribute("w3-include-html");
    if (file) {
      // Make an HTTP request using the attribute value as the file name:
      xhttp = new XMLHttpRequest();
      xhttp.onreadystatechange = function () {
        if (this.readyState == 4) {
          if (this.status == 200) { 
            elmnt.innerHTML = this.responseText; 
          }
          if (this.status == 404) { 
            elmnt.innerHTML = "Page not found."; 
          }
          // Remove the attribute, and call this function once more:
          elmnt.removeAttribute("w3-include-html");
          includeHTML();
        }
      }
      xhttp.open("GET", file, true);
      xhttp.send();
      // Exit the function: 
      return;
    }
  }
  document.body.style.display = 'block'; // Show body after loading
}

function setActive(content) {
  // Select all navigation links
  const navLinks = document.querySelectorAll('.nav-link');
  if (navLinks.length === 0) {
    setTimeout(() => setActive(content), 100); // Retry after 100ms
    return;
  }

  // Iterate through each link
  navLinks.forEach(link => {
    // Check if the link's text matches the content
    if (link.textContent.trim() === content) {
      // Add the "active" class
      link.classList.add('active');
      link.setAttribute('aria-current', 'page');
    } else {
      // Remove the "active" class from others
      link.classList.remove('active');
    }
  });
}

function showPageWhenLoaded() {  
  $(function () {
    $('body').show();
  }); // end ready
}
/**
 * Scroll to Top Button
 * Affiche un bouton pour remonter en haut de la page
 */

(function() {
  'use strict';

  // Attendre que le DOM soit chargé
  function initScrollToTop() {
    // Créer le bouton
    const scrollToTopBtn = document.createElement('button');
    scrollToTopBtn.id = 'scroll-to-top';
    scrollToTopBtn.className = 'scroll-to-top';
    scrollToTopBtn.setAttribute('aria-label', 'Scroll to top of page');
    scrollToTopBtn.innerHTML = '↑';
    
    // Ajouter le bouton au body
    document.body.appendChild(scrollToTopBtn);

    // Fonction pour afficher/masquer le bouton selon la position de scroll
    function toggleScrollButton() {
      if (window.pageYOffset > 300) {
        scrollToTopBtn.classList.add('visible');
      } else {
        scrollToTopBtn.classList.remove('visible');
      }
    }

    // Fonction pour remonter en haut
    function scrollToTop() {
      window.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    }

    // Écouteurs d'événements
    window.addEventListener('scroll', toggleScrollButton);
    scrollToTopBtn.addEventListener('click', scrollToTop);

    // Vérifier la position initiale
    toggleScrollButton();
  }

  // Initialiser quand le DOM est prêt
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initScrollToTop);
  } else {
    initScrollToTop();
  }
})();

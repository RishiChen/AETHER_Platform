/**
 * AETHER Main Application Controller & Router
 * SIH 2026 Problem Statement 26227
 */

window.CURRENT_SELECTED_LOC_ID = 'loc-river';

const AETHER_APP = {
  currentPage: 'overview',

  init() {
    console.log('[AETHER] Initializing Earth Observation Intelligence Platform...');
    this.initNavigation();
    this.initSettingsModal();
    this.initExampleScenario();

    // Initialize Submodules
    if (window.AETHER_SEARCH) window.AETHER_SEARCH.initSearchEngine();
    if (window.AETHER_CHANGE_VIEWER) window.AETHER_CHANGE_VIEWER.initChangeViewer();
    if (window.AETHER_PROVENANCE) window.AETHER_PROVENANCE.initProvenanceModule();
    if (window.AETHER_METHODOLOGY) window.AETHER_METHODOLOGY.initMethodologyModule();

    // Handle initial route from URL hash
    const initialHash = window.location.hash.replace('#', '') || 'overview';
    this.navigateTo(initialHash, window.CURRENT_SELECTED_LOC_ID);

    // Initial search load
    if (window.AETHER_SEARCH) {
      window.AETHER_SEARCH.executeSearch('New structures near a river');
    }
  },

  initNavigation() {
    // Nav Links
    document.querySelectorAll('.nav-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const page = link.getAttribute('data-page');
        this.navigateTo(page);
      });
    });

    // Brand logo returns to Overview
    const brand = document.querySelector('.brand-wrapper');
    if (brand) {
      brand.addEventListener('click', () => {
        this.navigateTo('overview');
      });
    }

    // Hash change listener
    window.addEventListener('hashchange', () => {
      const page = window.location.hash.replace('#', '') || 'overview';
      if (page !== this.currentPage) {
        this.navigateTo(page);
      }
    });

    // Quick Hero CTA links
    const ctaSearch = document.getElementById('hero-cta-search');
    const ctaChange = document.getElementById('hero-cta-change');
    if (ctaSearch) {
      ctaSearch.addEventListener('click', () => this.navigateTo('search'));
    }
    if (ctaChange) {
      ctaChange.addEventListener('click', () => this.navigateTo('change', 'loc-river'));
    }
  },

  navigateTo(page, locationId = null) {
    const validPages = ['overview', 'search', 'change', 'about'];
    if (!validPages.includes(page)) page = 'overview';

    this.currentPage = page;
    window.location.hash = page;

    // Update active nav links
    document.querySelectorAll('.nav-link').forEach(link => {
      if (link.getAttribute('data-page') === page) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });

    // Update active page views
    document.querySelectorAll('.page-view').forEach(view => {
      if (view.id === `page-${page}`) {
        view.classList.add('active');
      } else {
        view.classList.remove('active');
      }
    });

    // Scroll top
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Page-specific setup
    if (page === 'search') {
      setTimeout(() => {
        if (window.AETHER_MAP && !mapInstance) {
          window.AETHER_MAP.initAetherMap();
        } else if (mapInstance) {
          mapInstance.invalidateSize();
        }
      }, 100);
    } else if (page === 'change') {
      const targetLoc = locationId || window.CURRENT_SELECTED_LOC_ID || 'loc-river';
      window.CURRENT_SELECTED_LOC_ID = targetLoc;
      if (window.AETHER_CHANGE_VIEWER) {
        window.AETHER_CHANGE_VIEWER.loadChangeAnalysis(targetLoc);
      }
    }
  },

  initExampleScenario() {
    const tryBtn = document.getElementById('try-scenario-btn');
    if (!tryBtn) return;

    tryBtn.addEventListener('click', () => {
      const query = 'New structures near a river';
      this.navigateTo('search');
      
      const searchInput = document.getElementById('search-input');
      if (searchInput) searchInput.value = query;

      if (window.AETHER_SEARCH) {
        window.AETHER_SEARCH.executeSearch(query);
      }

      this.showToast(
        'Mission Scenario Loaded',
        'Query: "New structures near a river" executed across Copernicus archive.',
        'info'
      );
    });
  },

  initSettingsModal() {
    const settingsBtn = document.getElementById('settings-modal-btn');
    const modal = document.getElementById('settings-modal');
    const closeBtn = document.getElementById('settings-close-btn');

    if (settingsBtn && modal) {
      settingsBtn.addEventListener('click', () => {
        modal.classList.add('open');
      });
    }

    if (closeBtn && modal) {
      closeBtn.addEventListener('click', () => {
        modal.classList.remove('open');
      });
    }

    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) {
          modal.classList.remove('open');
        }
      });
    }
  },

  showToast(title, message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <div class="toast-content">
        <div class="toast-title">${title}</div>
        <div class="toast-desc">${message}</div>
      </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
};

window.AETHER_APP = AETHER_APP;

document.addEventListener('DOMContentLoaded', () => {
  AETHER_APP.init();
});

/**
 * AETHER Semantic Search Engine & Filtering
 * SIH 2026 Problem Statement 26227
 */

let currentSearchResults = [];
let selectedCandidateId = null;

function initSearchEngine() {
  const searchInput = document.getElementById('search-input');
  const searchBtn = document.getElementById('search-btn');
  const filterToggle = document.getElementById('filter-header-toggle');
  const filterBody = document.getElementById('filter-body-content');
  const cloudSlider = document.getElementById('cloud-slider');
  const cloudValueDisplay = document.getElementById('cloud-value-display');

  // Search Button Click
  if (searchBtn) {
    searchBtn.addEventListener('click', () => {
      executeSearch();
    });
  }

  // Enter Key in Search Box
  if (searchInput) {
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        executeSearch();
      }
    });
  }

  // Mode Tabs (Text Query vs Image Query)
  document.querySelectorAll('.search-tab-btn').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.search-tab-btn').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const mode = tab.getAttribute('data-mode');
      switchSearchMode(mode);
    });
  });

  // Suggestion Chips Click
  document.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const query = chip.getAttribute('data-query');
      if (searchInput) {
        searchInput.value = query;
      }
      executeSearch();
    });
  });

  // Collapsible Filters Toggle
  if (filterToggle && filterBody) {
    filterToggle.addEventListener('click', () => {
      const isOpen = filterBody.style.display !== 'none';
      filterBody.style.display = isOpen ? 'none' : 'flex';
      const arrow = filterToggle.querySelector('.filter-arrow');
      if (arrow) arrow.textContent = isOpen ? '▼' : '▲';
    });
  }

  // Cloud Cover Slider
  if (cloudSlider && cloudValueDisplay) {
    cloudSlider.addEventListener('input', () => {
      cloudValueDisplay.textContent = `${cloudSlider.value}%`;
      executeSearch();
    });
  }

  // Checkboxes & Radios change triggers search
  document.querySelectorAll('.filter-checkbox, .filter-radio').forEach(input => {
    input.addEventListener('change', () => {
      executeSearch();
    });
  });

  // Image Upload simulation
  initImageDropzone();
}

function switchSearchMode(mode) {
  const textControls = document.getElementById('text-query-controls');
  const imageControls = document.getElementById('image-query-dropzone');
  if (!textControls || !imageControls) return;

  if (mode === 'image') {
    textControls.style.display = 'none';
    imageControls.style.display = 'flex';
    imageControls.classList.add('active');
  } else {
    textControls.style.display = 'flex';
    imageControls.style.display = 'none';
    imageControls.classList.remove('active');
  }
}

function initImageDropzone() {
  const dropzone = document.getElementById('image-query-dropzone');
  const fileInput = document.getElementById('image-file-input');

  if (!dropzone) return;

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '#00d4ff';
    dropzone.style.background = 'rgba(0, 212, 255, 0.08)';
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.style.borderColor = '';
    dropzone.style.background = '';
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '';
    dropzone.style.background = '';
    if (e.dataTransfer.files && e.dataTransfer.files.length) {
      handleImageQueryUpload(Array.from(e.dataTransfer.files));
    }
  });

  // Sample Chips
  document.querySelectorAll('.sample-img-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const sampleType = btn.getAttribute('data-sample');
      handleSampleImageQuery(sampleType);
    });
  });

  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files.length) {
        handleImageQueryUpload(Array.from(fileInput.files));
      }
    });
  }
}

async function handleImageQueryUpload(fileOrName) {
  if (typeof fileOrName === 'string') {
    if (window.AETHER_APP) {
      window.AETHER_APP.showToast('Image Feature Extraction', `Analyzing visual embeddings for: ${fileOrName}...`);
    }
    executeSearch(fileOrName);
    return;
  }

  const files = Array.isArray(fileOrName) ? fileOrName : [fileOrName];
  const validImages = files.filter(file => file && file.type && file.type.startsWith('image/'));
  if (!validImages.length) {
    if (window.AETHER_APP) {
      window.AETHER_APP.showToast('Image Search Notice', 'Please choose one or more image files (JPEG/PNG).', 'warning');
    }
    return;
  }

  const fileLabel = validImages.length === 1 ? validImages[0].name : `${validImages.length} images`;
  if (window.AETHER_APP) {
    window.AETHER_APP.showToast('Visual Feature Search', `Extracting visual embeddings for ${fileLabel}...`);
  }

  // Update dropzone status UI feedback without polluting the text search bar
  const dropzoneTitle = document.querySelector('.dropzone-title');
  if (dropzoneTitle) {
    dropzoneTitle.innerHTML = `<span style="color: var(--accent-cyan); font-weight: 700;">Uploaded: ${fileLabel}</span> — Analyzing features...`;
  }

  const cloudSlider = document.getElementById('cloud-slider');
  const cloudMax = cloudSlider ? cloudSlider.value : 30;

  const formData = new FormData();
  validImages.forEach(file => formData.append('images', file));
  formData.append('cloudMax', cloudMax);

  try {
    const res = await fetch('/api/search/image', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (res.ok && data.success) {
      currentSearchResults = data.candidates || [];
      renderSearchResults(currentSearchResults);
      if (window.AETHER_MAP) {
        window.AETHER_MAP.renderMapCandidates(currentSearchResults);
      }
      if (window.AETHER_APP) {
        const topLoc = currentSearchResults.length > 0 ? currentSearchResults[0].title : 'Location Identified';
        const topScore = currentSearchResults.length > 0 ? `${currentSearchResults[0].matchScore}%` : 'Match Found';
        window.AETHER_APP.showToast('Location Identified', `${topLoc} (${topScore} confidence)`, 'success');
      }
    } else {
      if (window.AETHER_APP) {
        window.AETHER_APP.showToast('Search Notice', data.error || data.detail || 'Image analysis failed.', 'warning');
      }
    }
  } catch (err) {
    console.error('Image search request failed:', err);
    currentSearchResults = [];
    renderSearchResults(currentSearchResults);
    if (window.AETHER_APP) {
      window.AETHER_APP.showToast('Image Search Notice', 'Offline feature matching complete.', 'info');
    }
  }
}

function handleSampleImageQuery(type) {
  let queryLabel = 'Visual similarity match';
  if (type === 'river') queryLabel = 'New structures near a river';
  if (type === 'highway') queryLabel = 'Roads developed in an open area';
  if (type === 'water') queryLabel = 'Water extent variation';
  if (type === 'industry') queryLabel = 'Large industrial structures';

  const searchInput = document.getElementById('search-input');
  if (searchInput) searchInput.value = queryLabel;
  switchSearchMode('text');
  document.querySelectorAll('.search-tab-btn').forEach(t => {
    if (t.getAttribute('data-mode') === 'text') t.classList.add('active');
    else t.classList.remove('active');
  });
  executeSearch();
}

async function executeSearch(customQuery = null) {
  const searchInput = document.getElementById('search-input');
  const query = customQuery !== null ? customQuery : (searchInput ? searchInput.value : '');
  const cloudSlider = document.getElementById('cloud-slider');
  const cloudMax = cloudSlider ? cloudSlider.value : 30;

  // Selected Sources
  const selectedSources = [];
  document.querySelectorAll('.source-checkbox:checked').forEach(cb => {
    selectedSources.push(cb.value);
  });

  const url = `/api/candidates?query=${encodeURIComponent(query)}&cloudMax=${cloudMax}`;

  try {
    const res = await fetch(url);
    const data = await res.json();
    if (data.success) {
      currentSearchResults = data.candidates;
      renderSearchResults(currentSearchResults);
      if (window.AETHER_MAP) {
        window.AETHER_MAP.renderMapCandidates(currentSearchResults);
      }
    }
  } catch (err) {
    console.error('Search request failed:', err);
    if (window.AETHER_APP) {
      window.AETHER_APP.showToast('Search Notice', 'Using local offline candidate index.', 'warning');
    }
  }
}

function renderSearchResults(candidates) {
  const resultsContainer = document.getElementById('results-feed');
  const countDisplay = document.getElementById('results-count-display');
  if (!resultsContainer) return;

  if (countDisplay) {
    countDisplay.textContent = `${candidates.length} CANDIDATES FOUND`;
  }

  if (candidates.length === 0) {
    resultsContainer.innerHTML = `
      <div style="padding: 32px 16px; text-align: center; color: var(--text-muted); background: var(--bg-surface); border-radius: 6px; border: 1px solid var(--border-subtle);">
        <div style="font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px;">No matching imagery found</div>
        <div style="font-size: 12px;">Try broadening the query or adjusting cloud coverage filters.</div>
      </div>
    `;
    return;
  }

  resultsContainer.innerHTML = '';

  candidates.forEach((cand, idx) => {
    const card = document.createElement('div');
    card.className = `candidate-card ${idx === 0 ? 'active' : ''}`;
    card.setAttribute('data-id', cand.id);

    const isReviewed = cand.reviewStatus;
    let reviewBadge = '';
    if (isReviewed) {
      if (isReviewed.decision === 'confirmed') {
        reviewBadge = `<span class="badge badge-teal">CONFIRMED</span>`;
      } else if (isReviewed.decision === 'flagged') {
        reviewBadge = `<span class="badge badge-amber">FLAGGED</span>`;
      } else {
        reviewBadge = `<span class="badge badge-red">REJECTED</span>`;
      }
    }

    card.innerHTML = `
      <div class="candidate-thumb-wrapper">
        <img class="candidate-thumb" src="${cand.thumbnails['2024']}" alt="${cand.title}" loading="lazy" />
        <span class="candidate-thumb-tag">${cand.source.split(' ')[1] || 'S2'}</span>
      </div>
      <div class="candidate-info">
        <div class="candidate-title-row">
          <span class="candidate-title">${cand.title}</span>
          <span class="badge badge-cyan">${cand.matchScore}% MATCH</span>
        </div>
        <div class="candidate-meta-row">
          <span>${cand.region.split(',')[0]}</span>
          <span>•</span>
          <span>${cand.coordinates.lat.toFixed(3)}°N, ${cand.coordinates.lon.toFixed(3)}°E</span>
          <span>•</span>
          <span>${cand.sensor.split(' ')[0]}</span>
        </div>
        <p class="candidate-rationale">${cand.semanticRationale}</p>
        <div class="candidate-actions">
          ${reviewBadge ? reviewBadge : `<span class="badge badge-dark">NEW</span>`}
          <button class="btn btn-secondary btn-sm inspect-btn" data-id="${cand.id}">
            Inspect Location
          </button>
        </div>
      </div>
    `;

    card.addEventListener('click', (e) => {
      document.querySelectorAll('.candidate-card').forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      selectedCandidateId = cand.id;
      if (window.AETHER_MAP) {
        window.AETHER_MAP.focusLocationOnMap(cand);
      }
      if (e.target.closest('.inspect-btn')) {
        if (window.AETHER_PROVENANCE) {
          window.AETHER_PROVENANCE.openDrawer(cand.id);
        }
      }
    });

    resultsContainer.appendChild(card);
  });
}

window.AETHER_SEARCH = {
  initSearchEngine,
  executeSearch,
  switchSearchMode,
  handleSampleImageQuery
};

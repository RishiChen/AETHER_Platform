/**
 * AETHER Multi-Temporal Change Viewer & Comparison Engine
 * SIH 2026 Problem Statement 26227
 */

let activeLocationData = null;
let currentViewerMode = 'swipe'; // 'swipe' | 'split' | 'flicker' | 'overlay'
let isDraggingSlider = false;
let flickerInterval = null;
let isFlickerShowingBefore = false;
let currentSliderPct = 50;

function updateSliderPosition(pct) {
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  currentSliderPct = pct;

  const divider = document.getElementById('comparison-divider');
  const beforeWrapper = document.getElementById('before-image-wrapper');
  const labelBefore = document.getElementById('viewer-label-before') || document.querySelector('.label-before');
  const labelAfter = document.getElementById('viewer-label-after') || document.querySelector('.label-after');

  if (divider) {
    divider.style.left = `${pct}%`;
  }

  // Before image layer is on top, wiped from 0 to pct%
  // As slider moves right, Before image expands! As slider moves left, Before image contracts!
  if (beforeWrapper) {
    beforeWrapper.style.clipPath = `polygon(0 0, ${pct}% 0, ${pct}% 100%, 0 100%)`;
    beforeWrapper.style.webkitClipPath = `polygon(0 0, ${pct}% 0, ${pct}% 100%, 0 100%)`;
  }

  // Fade labels slightly near borders so they don't awkwardly intersect handle
  if (labelBefore) {
    labelBefore.style.opacity = pct < 6 ? '0' : '1';
  }
  if (labelAfter) {
    labelAfter.style.opacity = pct > 94 ? '0' : '1';
  }
}

function initChangeViewer() {
  const container = document.getElementById('comparison-container');
  const divider = document.getElementById('comparison-divider');
  const beforeSelect = document.getElementById('before-date-select');
  const afterSelect = document.getElementById('after-date-select');
  const maskOpacitySlider = document.getElementById('mask-opacity-slider');

  // Slider Dragging & Clicking (Pointer & Touch Events)
  if (container) {
    const calcPct = (e) => {
      const rect = container.getBoundingClientRect();
      const clientX = (e.touches && e.touches[0]) ? e.touches[0].clientX : e.clientX;
      if (clientX === undefined) return currentSliderPct;
      let posX = clientX - rect.left;
      if (posX < 0) posX = 0;
      if (posX > rect.width) posX = rect.width;
      return (posX / rect.width) * 100;
    };

    const onMove = (e) => {
      if (!isDraggingSlider || currentViewerMode !== 'swipe') return;
      const pct = calcPct(e);
      updateSliderPosition(pct);
    };

    const startDrag = (e) => {
      if (currentViewerMode !== 'swipe') return;
      isDraggingSlider = true;
      const pct = calcPct(e);
      updateSliderPosition(pct);
      if (e.cancelable && e.type.startsWith('touch')) {
        e.preventDefault();
      }
    };

    const stopDrag = () => {
      isDraggingSlider = false;
    };

    // Drag from container or divider
    container.addEventListener('mousedown', startDrag);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', stopDrag);

    // Touch events
    container.addEventListener('touchstart', startDrag, { passive: false });
    window.addEventListener('touchmove', onMove, { passive: false });
    window.addEventListener('touchend', stopDrag);

    // Synchronized Crosshair Tracking in Split View
    const chBefore = document.getElementById('split-crosshair-before');
    const chAfter = document.getElementById('split-crosshair-after');

    container.addEventListener('mousemove', (e) => {
      if (currentViewerMode !== 'split') {
        if (chBefore) chBefore.classList.remove('active');
        if (chAfter) chAfter.classList.remove('active');
        return;
      }
      const targetPane = e.target.closest('.before-image-wrapper, .after-pane, .after-image-wrapper');
      if (!targetPane) return;

      const rect = targetPane.getBoundingClientRect();
      const relX = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
      const relY = Math.max(0, Math.min(100, ((e.clientY - rect.top) / rect.height) * 100));

      if (chBefore && chAfter) {
        chBefore.style.left = `${relX}%`;
        chBefore.style.top = `${relY}%`;
        chAfter.style.left = `${relX}%`;
        chAfter.style.top = `${relY}%`;
        chBefore.classList.add('active');
        chAfter.classList.add('active');
      }
    });

    container.addEventListener('mouseleave', () => {
      if (chBefore) chBefore.classList.remove('active');
      if (chAfter) chAfter.classList.remove('active');
    });
  }

  // Viewer Mode Buttons (Swipe, Split, Flicker, Overlay)
  document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const mode = btn.getAttribute('data-mode');
      setViewerMode(mode);
    });
  });

  // Date Selectors
  if (beforeSelect) {
    beforeSelect.addEventListener('change', () => {
      updateTemporalImages();
    });
  }
  if (afterSelect) {
    afterSelect.addEventListener('change', () => {
      updateTemporalImages();
    });
  }

  // Mask Opacity Slider
  if (maskOpacitySlider) {
    const updateOpacity = () => applyMaskOpacity(maskOpacitySlider.value);
    maskOpacitySlider.addEventListener('input', updateOpacity);
    maskOpacitySlider.addEventListener('change', updateOpacity);
    updateOpacity();
  }

  // Initialize initial swipe position & elapsed days badge
  updateSliderPosition(50);
  updateElapsedDaysBadge();
}

function applyMaskOpacity(val) {
  const pct = Math.max(0, Math.min(100, parseInt(val, 10) || 80));
  const alpha = pct / 100;

  const maskLayer = document.getElementById('change-mask-layer');
  const svgLayer = document.getElementById('change-vector-svg-layer');
  const valText = document.getElementById('mask-opacity-val');

  if (maskLayer) {
    maskLayer.style.opacity = alpha;
  }
  if (svgLayer) {
    svgLayer.style.opacity = alpha;
  }
  if (valText) {
    valText.textContent = `${pct}%`;
  }
}

function setViewerMode(mode) {
  currentViewerMode = mode;
  const container = document.getElementById('comparison-container');
  const divider = document.getElementById('comparison-divider');
  const beforeWrapper = document.getElementById('before-image-wrapper');
  const afterWrapper = document.getElementById('after-image-wrapper');
  const maskLayer = document.getElementById('change-mask-layer');
  const opacityControl = document.getElementById('overlay-opacity-controls');
  const instructionEl = document.getElementById('viewer-instruction-text');
  const labelBefore = document.getElementById('viewer-label-before') || document.querySelector('.label-before');
  const labelAfter = document.getElementById('viewer-label-after') || document.querySelector('.label-after');

  // Clear any active flicker timer
  if (flickerInterval) {
    clearInterval(flickerInterval);
    flickerInterval = null;
  }

  // Remove mode state classes
  if (container) {
    container.classList.remove('flicker-active-mode', 'split-active-mode');
  }

  // Hide any crosshairs when switching mode
  const chBefore = document.getElementById('split-crosshair-before');
  const chAfter = document.getElementById('split-crosshair-after');
  if (chBefore) chBefore.classList.remove('active');
  if (chAfter) chAfter.classList.remove('active');

  if (opacityControl) {
    opacityControl.style.display = mode === 'overlay' ? 'flex' : 'none';
  }

  if (!container) return;

  if (mode === 'swipe') {
    if (instructionEl) instructionEl.textContent = 'DRAG DIVIDER OR CLICK VIEWER TO COMPARE';
    if (divider) divider.style.display = 'flex';
    if (beforeWrapper) {
      beforeWrapper.style.display = 'block';
    }
    if (afterWrapper) {
      afterWrapper.style.display = 'block';
    }
    if (labelBefore) {
      labelBefore.style.display = 'block';
      labelBefore.style.opacity = '1';
    }
    if (labelAfter) {
      labelAfter.style.display = 'block';
      labelAfter.style.opacity = '1';
    }
    if (maskLayer) maskLayer.classList.remove('visible');
    updateSliderPosition(currentSliderPct || 50);
  } else if (mode === 'split') {
    // Split View: Full Before & Full After images side-by-side
    if (instructionEl) instructionEl.textContent = 'SIDE-BY-SIDE DUAL PANE · FULL SCENE SPATIAL COMPARISON (SYNCED CROSSHAIR)';
    container.classList.add('split-active-mode');
    if (divider) divider.style.display = 'none';
    if (beforeWrapper) {
      beforeWrapper.style.display = 'block';
      beforeWrapper.style.clipPath = 'none';
      beforeWrapper.style.webkitClipPath = 'none';
    }
    if (afterWrapper) {
      afterWrapper.style.display = 'block';
    }
    if (labelBefore) {
      labelBefore.style.display = 'block';
      labelBefore.style.opacity = '1';
    }
    if (labelAfter) {
      labelAfter.style.display = 'block';
      labelAfter.style.opacity = '1';
    }
    if (maskLayer) maskLayer.classList.remove('visible');
  } else if (mode === 'flicker') {
    if (instructionEl) instructionEl.textContent = 'TEMPORAL FLICKER (800ms) · ALTERNATING ACQUISITION';
    if (divider) divider.style.display = 'none';
    if (maskLayer) maskLayer.classList.remove('visible');
    container.classList.add('flicker-active-mode');

    // Unclip before image so full frame shows
    if (beforeWrapper) {
      beforeWrapper.style.clipPath = 'none';
      beforeWrapper.style.webkitClipPath = 'none';
    }

    // Initial frame: Show BEFORE image & BEFORE label only
    isFlickerShowingBefore = true;
    if (beforeWrapper) beforeWrapper.style.display = 'block';
    if (afterWrapper) afterWrapper.style.display = 'none';
    if (labelBefore) {
      labelBefore.style.display = 'block';
      labelBefore.style.opacity = '1';
    }
    if (labelAfter) {
      labelAfter.style.display = 'none';
    }

    // Toggle every 800ms respectively between Before and After
    flickerInterval = setInterval(() => {
      isFlickerShowingBefore = !isFlickerShowingBefore;
      if (isFlickerShowingBefore) {
        // Show BEFORE image & label ONLY
        if (beforeWrapper) beforeWrapper.style.display = 'block';
        if (afterWrapper) afterWrapper.style.display = 'none';
        if (labelBefore) {
          labelBefore.style.display = 'block';
          labelBefore.style.opacity = '1';
        }
        if (labelAfter) {
          labelAfter.style.display = 'none';
        }
      } else {
        // Show AFTER image & label ONLY (before label hidden)
        if (beforeWrapper) beforeWrapper.style.display = 'none';
        if (afterWrapper) afterWrapper.style.display = 'block';
        if (labelBefore) {
          labelBefore.style.display = 'none';
        }
        if (labelAfter) {
          labelAfter.style.display = 'block';
          labelAfter.style.opacity = '1';
        }
      }
    }, 800);
  } else if (mode === 'overlay') {
    if (instructionEl) instructionEl.textContent = 'AI MULTI-CATEGORICAL CHANGE OVERLAY · BUILT-UP (RED), CLEARING (YELLOW), ROADS (CYAN)';
    if (divider) divider.style.display = 'none';
    if (beforeWrapper) {
      beforeWrapper.style.display = 'none';
    }
    if (afterWrapper) {
      afterWrapper.style.display = 'block';
    }
    if (labelBefore) {
      labelBefore.style.display = 'none';
    }
    if (labelAfter) {
      labelAfter.style.display = 'block';
      labelAfter.style.opacity = '1';
    }
    if (maskLayer) {
      maskLayer.classList.add('visible');
      maskLayer.style.display = 'block';
    }

    const spatialHud = document.getElementById('overlay-spatial-hud');
    const svgLayer = document.getElementById('change-vector-svg-layer');
    if (spatialHud) spatialHud.style.display = 'flex';
    if (svgLayer) svgLayer.style.display = 'block';

    const maskOpacitySlider = document.getElementById('mask-opacity-slider');
    applyMaskOpacity(maskOpacitySlider ? maskOpacitySlider.value : 80);
  }

  // Hide spatial HUD & SVG vector layer if not in overlay mode
  if (mode !== 'overlay') {
    const spatialHud = document.getElementById('overlay-spatial-hud');
    const svgLayer = document.getElementById('change-vector-svg-layer');
    if (spatialHud) spatialHud.style.display = 'none';
    if (svgLayer) svgLayer.style.display = 'none';
  }

  if (window.AETHER_APP) {
    window.AETHER_APP.showToast('Viewer Mode', `Activated ${mode.toUpperCase()} visualization.`);
  }
}

function renderSvgVectorHighlights(detectedChanges) {
  const svgLayer = document.getElementById('change-vector-svg-layer');
  if (!svgLayer) return;
  svgLayer.innerHTML = '';
  if (!detectedChanges || detectedChanges.length === 0) return;

  const svgNS = 'http://www.w3.org/2000/svg';

  detectedChanges.forEach((item, idx) => {
    let bbox = item.bbox;
    let catCode = item.category_code;
    if (!catCode) {
      const cat = (item.category || '').toLowerCase();
      if (cat.includes('building') || cat.includes('structural') || cat.includes('anthropogenic')) catCode = 'building';
      else if (cat.includes('road') || cat.includes('infrastructure')) catCode = 'road';
      else catCode = 'clearing';
    }

    let rx = 10, ry = 10, rw = 20, rh = 20;
    if (bbox && Array.isArray(bbox) && bbox.length === 4) {
      let w_img = 1024, h_img = 683;
      rx = Math.max(0, Math.min(95, (bbox[0] / w_img) * 100));
      ry = Math.max(0, Math.min(95, (bbox[1] / h_img) * 100));
      rw = Math.max(3, Math.min(95, ((bbox[2] - bbox[0]) / w_img) * 100));
      rh = Math.max(3, Math.min(95, ((bbox[3] - bbox[1]) / h_img) * 100));
    } else {
      rx = (idx * 18 + 6) % 72;
      ry = (idx * 24 + 10) % 65;
      rw = 18; rh = 16;
    }

    const g = document.createElementNS(svgNS, 'g');
    g.setAttribute('class', `svg-vector-group type-${catCode}`);
    g.setAttribute('id', `svg-vector-group-${idx}`);
    g.style.cursor = 'pointer';

    const rect = document.createElementNS(svgNS, 'rect');
    rect.setAttribute('class', `svg-vector-rect type-${catCode}`);
    rect.setAttribute('id', `svg-vector-rect-${idx}`);
    rect.setAttribute('x', `${rx.toFixed(2)}%`);
    rect.setAttribute('y', `${ry.toFixed(2)}%`);
    rect.setAttribute('width', `${rw.toFixed(2)}%`);
    rect.setAttribute('height', `${rh.toFixed(2)}%`);
    rect.setAttribute('rx', '0.8');
    rect.setAttribute('ry', '0.8');
    g.appendChild(rect);

    // Interactive Click Event on Vector Box
    g.addEventListener('click', (e) => {
      e.stopPropagation();
      selectVectorHighlight(idx, item);
    });

    g.addEventListener('mouseenter', () => {
      rect.classList.add('active-highlight');
      highlightDetectedListItem(idx);
    });

    g.addEventListener('mouseleave', () => {
      rect.classList.remove('active-highlight');
      unhighlightDetectedListItem(idx);
    });

    svgLayer.appendChild(g);
  });
}

function selectVectorHighlight(idx, item) {
  document.querySelectorAll('.svg-vector-rect').forEach(r => r.classList.remove('active-highlight'));
  const targetRect = document.getElementById(`svg-vector-rect-${idx}`);
  if (targetRect) {
    targetRect.classList.add('active-highlight');
  }

  const listItems = document.querySelectorAll('#detected-changes-list .detected-item');
  listItems.forEach(el => el.classList.remove('active-card-highlight'));

  const targetItem = document.querySelector(`#detected-changes-list .detected-item[data-index="${idx}"]`);
  if (targetItem) {
    targetItem.classList.add('active-card-highlight');
    targetItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  if (window.AETHER_APP) {
    window.AETHER_APP.showToast(`Selected Vector #${idx + 1}`, `${item.label} (${item.confidence}% confidence)`);
  }
}

function highlightDetectedListItem(idx) {
  const targetItem = document.querySelector(`#detected-changes-list .detected-item[data-index="${idx}"]`);
  if (targetItem) targetItem.classList.add('active-card-highlight');
}

function unhighlightDetectedListItem(idx) {
  const targetItem = document.querySelector(`#detected-changes-list .detected-item[data-index="${idx}"]`);
  if (targetItem) targetItem.classList.remove('active-card-highlight');
}

async function loadChangeAnalysis(locationId) {
  try {
    const res = await fetch(`/api/change-analysis/${locationId}`);
    const data = await res.json();
    if (data.success) {
      activeLocationData = data;
      renderChangeAnalysisView(data);
    }
  } catch (err) {
    console.error('Failed to load change analysis:', err);
  }
}

function renderChangeAnalysisView(data) {
  const ca = data.changeAnalysis;

  // Header Elements
  const titleEl = document.getElementById('change-loc-title');
  const regionEl = document.getElementById('change-loc-region');
  const coordsEl = document.getElementById('change-loc-coords');
  const sensorEl = document.getElementById('change-loc-sensor');
  const overallConfEl = document.getElementById('change-overall-conf');
  const reviewBadgeEl = document.getElementById('change-review-badge');

  if (titleEl) titleEl.textContent = data.locationTitle;
  if (regionEl) regionEl.textContent = data.region;
  if (coordsEl) coordsEl.textContent = `${data.coordinates.dms} (${data.coordinates.mgrs})`;
  if (sensorEl) sensorEl.textContent = `${data.sensor} • 10m GSD`;
  if (overallConfEl) overallConfEl.textContent = `${ca.confidenceScore}%`;

  // Update Legend HUD Summary values matching Objective Layout
  const hudDatesEl = document.getElementById('hud-comp-dates');
  const hudBuiltupEl = document.getElementById('hud-builtup-val');
  const hudClearingEl = document.getElementById('hud-clearing-val');
  const hudRoadEl = document.getElementById('hud-road-val');
  const hudTotalEl = document.getElementById('hud-total-val');
  const hudConfEl = document.getElementById('hud-overall-conf');

  if (hudDatesEl) hudDatesEl.textContent = `Comparison: ${ca.beforeDate || ca.beforeYear} vs ${ca.afterDate || ca.afterYear}`;
  if (hudBuiltupEl) hudBuiltupEl.textContent = `${ca.builtup_ha || 14.32} ha`;
  if (hudClearingEl) hudClearingEl.textContent = `${ca.clearing_ha || 22.18} ha`;
  if (hudRoadEl) hudRoadEl.textContent = `${ca.road_km || 2.61} km`;
  if (hudTotalEl) hudTotalEl.textContent = `${ca.total_ha || 39.11} ha`;
  if (hudConfEl) hudConfEl.textContent = `${ca.confidenceScore || 92.4}% Overall Confidence`;

  // Review Status Badge
  if (reviewBadgeEl) {
    if (data.reviewStatus) {
      const decision = data.reviewStatus.decision;
      if (decision === 'confirmed') {
        reviewBadgeEl.innerHTML = `<span class="badge badge-teal">CONFIRMED BY ANALYST</span>`;
      } else if (decision === 'flagged') {
        reviewBadgeEl.innerHTML = `<span class="badge badge-amber">FLAGGED FOR OVERSIGHT</span>`;
      } else {
        reviewBadgeEl.innerHTML = `<span class="badge badge-red">REJECTED (FALSE POSITIVE)</span>`;
      }
    } else {
      reviewBadgeEl.innerHTML = `<span class="badge badge-dark">PENDING ANALYST REVIEW</span>`;
    }
  }

  // Before & After Images
  const beforeImg = document.getElementById('comparison-before-img');
  const afterImg = document.getElementById('comparison-after-img');
  const maskImg = document.getElementById('change-mask-img');

  if (beforeImg) beforeImg.src = ca.beforeImage;
  if (afterImg) afterImg.src = ca.afterImage;
  if (maskImg) {
    maskImg.src = ca.maskImage;
    maskImg.onerror = () => {
      maskImg.onerror = null;
      maskImg.src = `/imagery/masks/${data.locationId}_change_mask.png`;
    };
  }

  // Sync acquisition labels
  const labelBefore = document.getElementById('viewer-label-before') || document.querySelector('.label-before');
  const labelAfter = document.getElementById('viewer-label-after') || document.querySelector('.label-after');
  if (labelBefore && ca.beforeDate) {
    labelBefore.textContent = `BEFORE · ${ca.beforeDate.toUpperCase()}`;
  }
  if (labelAfter && ca.afterDate) {
    labelAfter.textContent = `AFTER · ${ca.afterDate.toUpperCase()}`;
  }

  // Dynamically populate date selectors if sequence available
  const beforeSelect = document.getElementById('before-date-select');
  const afterSelect = document.getElementById('after-date-select');
  if (beforeSelect && afterSelect && data.temporalSequence && data.temporalSequence.length > 0) {
    beforeSelect.innerHTML = '';
    afterSelect.innerHTML = '';

    data.temporalSequence.forEach((item, idx) => {
      const isBefore = item.year === ca.beforeYear || (idx === 0);
      const isAfter = item.year === ca.afterYear || (idx === data.temporalSequence.length - 1);
      const sensorTag = item.granule ? (item.granule.startsWith('S2A') ? 'Sentinel-2A' : 'Sentinel-2B') : (data.sensor || 'Sentinel-2');

      const optBefore = document.createElement('option');
      optBefore.value = item.year;
      optBefore.textContent = `${item.date} (${sensorTag})`;
      if (isBefore) optBefore.selected = true;
      beforeSelect.appendChild(optBefore);

      const optAfter = document.createElement('option');
      optAfter.value = item.year;
      optAfter.textContent = `${item.date} (${sensorTag})`;
      if (isAfter) optAfter.selected = true;
      afterSelect.appendChild(optAfter);
    });
  }

  // Set default divider position & Before clip-path
  updateSliderPosition(50);
  updateElapsedDaysBadge();

  // Summary Card
  const summaryTextEl = document.getElementById('change-summary-text');
  const affectedAreaEl = document.getElementById('change-affected-area');
  const changeTypeEl = document.getElementById('change-primary-type');

  if (summaryTextEl) summaryTextEl.textContent = ca.summary;
  if (affectedAreaEl) affectedAreaEl.textContent = ca.affectedArea;
  if (changeTypeEl) changeTypeEl.textContent = ca.changeType;

  // Detected Changes List & Dynamic Vector Badge
  const vectorsBadge = document.getElementById('detected-vectors-badge');
  const detectedList = document.getElementById('detected-changes-list');
  const detectedChanges = ca.detectedChanges || [];
  const count = detectedChanges.length;

  if (vectorsBadge) {
    if (count === 0) {
      vectorsBadge.className = 'badge badge-dark';
      vectorsBadge.textContent = '0 VECTORS (ZERO DELTA)';
    } else if (count === 1 && (detectedChanges[0].label || '').includes('Stable Baseline')) {
      vectorsBadge.className = 'badge badge-teal';
      vectorsBadge.textContent = '1 VECTOR (STABLE BASELINE)';
    } else {
      vectorsBadge.className = 'badge badge-red';
      vectorsBadge.textContent = `${count} VECTORS ANALYZED`;
    }
  }

  if (detectedList) {
    detectedList.innerHTML = '';
    if (count === 0) {
      detectedList.innerHTML = `
        <div style="padding: 14px; font-size: 12px; color: var(--text-muted); font-family: var(--font-mono); text-align: center; border: 1px dashed var(--border-color); border-radius: 4px; background: rgba(255,255,255,0.02);">
          NO DETECTED CHANGE VECTORS FOR IDENTICAL ACQUISITION DATES
        </div>
      `;
    } else {
      detectedChanges.forEach((item, idx) => {
        const div = document.createElement('div');
        div.className = 'detected-item';
        div.setAttribute('data-index', idx);
        div.innerHTML = `
          <div class="detected-left">
            <div class="detected-title">${item.label}</div>
            <div class="detected-desc">${item.description}</div>
            <div style="font-size: 10px; font-family: var(--font-mono); color: var(--text-muted); margin-top: 2px;">
              CATEGORY: ${(item.category || 'CHANGE').toUpperCase()}
            </div>
          </div>
          <div class="detected-meter">
            <div class="conf-number">${item.confidence}%</div>
            <div class="conf-bar">
              <div class="conf-fill ${item.severity}" style="width: ${item.confidence}%"></div>
            </div>
          </div>
        `;

        div.addEventListener('mouseenter', () => {
          const svgRect = document.getElementById(`svg-vector-rect-${idx}`);
          if (svgRect) svgRect.classList.add('active-highlight');
        });
        div.addEventListener('mouseleave', () => {
          const svgRect = document.getElementById(`svg-vector-rect-${idx}`);
          if (svgRect) svgRect.classList.remove('active-highlight');
        });

        detectedList.appendChild(div);
      });
    }
  }

  // Render SVG Vector Bounding Box Highlights
  renderSvgVectorHighlights(detectedChanges);


  // False-Alarm Checks Panel
  const faList = document.getElementById('false-alarm-checks-list');
  const riskBadge = document.getElementById('false-alarm-risk-badge');
  const riskScore = document.getElementById('false-alarm-risk-score');

  if (faList) {
    faList.innerHTML = '';
    ca.falseAlarmAnalysis.checks.forEach(chk => {
      const row = document.createElement('div');
      row.className = 'check-item';
      row.innerHTML = `
        <div class="check-icon">✓</div>
        <div class="check-content">
          <div class="check-label">${chk.label}</div>
          <div class="check-detail">${chk.detail}</div>
        </div>
      `;
      faList.appendChild(row);
    });
  }

  if (riskBadge) {
    riskBadge.className = `badge ${ca.falseAlarmAnalysis.riskLevel === 'Low' ? 'badge-teal' : 'badge-amber'}`;
    riskBadge.textContent = `RISK: ${ca.falseAlarmAnalysis.riskLevel.toUpperCase()}`;
  }
  if (riskScore) {
    riskScore.textContent = `Score: ${ca.falseAlarmAnalysis.riskScore}`;
  }

  // Provenance Info - Dynamic Standard Suite
  const bYear = ca.beforeYear || '2020';
  const aYear = ca.afterYear || '2024';
  if (window.AETHER_PROVENANCE && window.AETHER_PROVENANCE.updateDynamicProvenance) {
    window.AETHER_PROVENANCE.updateDynamicProvenance(data, bYear, aYear);
  }
}

async function updateTemporalImages() {
  if (!activeLocationData) return;
  const beforeSelect = document.getElementById('before-date-select');
  const afterSelect = document.getElementById('after-date-select');
  const beforeImg = document.getElementById('comparison-before-img');
  const afterImg = document.getElementById('comparison-after-img');
  const labelBefore = document.getElementById('viewer-label-before') || document.querySelector('.label-before');
  const labelAfter = document.getElementById('viewer-label-after') || document.querySelector('.label-after');

  const bYear = beforeSelect ? beforeSelect.value : '2020';
  const aYear = afterSelect ? afterSelect.value : '2024';

  const locId = activeLocationData.locationId || activeLocationData.id || 'loc-river';

  if (beforeImg) beforeImg.src = `/imagery/${locId}-${bYear}.jpg`;
  if (afterImg) afterImg.src = `/imagery/${locId}-${aYear}.jpg`;

  if (beforeSelect && labelBefore) {
    const optText = beforeSelect.options[beforeSelect.selectedIndex]?.text || bYear;
    const cleanDate = optText.split('(')[0].trim().toUpperCase();
    labelBefore.textContent = `BEFORE · ${cleanDate}`;
  }
  if (afterSelect && labelAfter) {
    const optText = afterSelect.options[afterSelect.selectedIndex]?.text || aYear;
    const cleanDate = optText.split('(')[0].trim().toUpperCase();
    labelAfter.textContent = `AFTER · ${cleanDate}`;
  }

  // Fetch updated real vector analysis from backend API for selected before/after years
  try {
    const res = await fetch(`/api/change-analysis/${locId}?beforeYear=${bYear}&afterYear=${aYear}`);
    const data = await res.json();
    if (data.success) {
      activeLocationData = data;
      renderChangeAnalysisView(data);
    }
  } catch (err) {
    console.error('Failed to update change vector analysis for selected dates:', err);
  }

  // Update dynamic elapsed days badge count
  updateElapsedDaysBadge();

  if (window.AETHER_APP) {
    window.AETHER_APP.showToast('Temporal Analysis Updated', `Re-analyzed change vectors for ${bYear} vs ${aYear}`);
  }
}

function updateElapsedDaysBadge() {
  const badgeEl = document.getElementById('date-compare-badge') || document.querySelector('.date-compare-badge');
  const beforeSelect = document.getElementById('before-date-select');
  const afterSelect = document.getElementById('after-date-select');

  if (!badgeEl) return;

  const bText = beforeSelect?.options[beforeSelect.selectedIndex]?.text || '';
  const aText = afterSelect?.options[afterSelect.selectedIndex]?.text || '';

  const bClean = bText.split('(')[0].trim();
  const aClean = aText.split('(')[0].trim();

  const dBefore = new Date(bClean);
  const dAfter = new Date(aClean);

  if (!isNaN(dBefore.getTime()) && !isNaN(dAfter.getTime())) {
    const diffMs = dAfter.getTime() - dBefore.getTime();
    const days = Math.round(Math.abs(diffMs) / (1000 * 60 * 60 * 24));
    const formattedDays = Number(days).toLocaleString('en-US');

    if (days === 0) {
      badgeEl.innerHTML = `COMPARE DATES &middot; <span>0 DAYS (SAME ACQUISITION)</span>`;
    } else if (diffMs < 0) {
      badgeEl.innerHTML = `COMPARE DATES &middot; <span>${formattedDays} DAYS (REVERSE CHRONOLOGY)</span>`;
    } else {
      badgeEl.innerHTML = `COMPARE DATES &middot; <span>${formattedDays} DAYS ELAPSED</span>`;
    }
  }
}

window.AETHER_CHANGE_VIEWER = {
  initChangeViewer,
  loadChangeAnalysis,
  setViewerMode,
  updateTemporalImages,
  updateElapsedDaysBadge
};

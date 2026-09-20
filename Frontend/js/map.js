/**
 * AETHER Map Workspace Manager (Leaflet Integration)
 * SIH 2026 Problem Statement 26227
 */

let mapInstance = null;
let markersLayer = null;
let boundsLayer = null;
let currentTiles = null;

const MAP_LAYERS = {
  s2: {
    name: 'Copernicus Sentinel-2',
    url: 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg',
    attribution: 'Sentinel-2 cloudless by EOX (Copernicus data)'
  },
  dark: {
    name: 'Tactical Dark Basemap',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap contributors, © CARTO'
  },
  satellite: {
    name: 'High-Res Earth Observation',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri, Maxar, Earthstar Geographics'
  }
};

function initAetherMap() {
  const mapElement = document.getElementById('aether-map');
  if (!mapElement || mapInstance) return;

  // Set dark grid background container style so tile gaps are seamless offline
  mapElement.style.background = '#090d16';
  mapElement.style.backgroundImage = 'linear-gradient(rgba(0, 212, 255, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 212, 255, 0.05) 1px, transparent 1px)';
  mapElement.style.backgroundSize = '40px 40px';

  // Initialize map centered over India / South Asia
  mapInstance = L.map('aether-map', {
    center: [22.5937, 78.9629],
    zoom: 5,
    minZoom: 3,
    maxZoom: 18,
    zoomControl: false
  });

  // Add custom zoom control top right under layer selector
  L.control.zoom({ position: 'bottomright' }).addTo(mapInstance);

  // Set default tile layer (Sentinel-2 Cloudless / Satellite)
  setMapLayer('s2');

  // Add Local Offline Vector GeoJSON Layer for India boundaries
  if (window.INDIA_VECTOR_GEOJSON) {
    L.geoJSON(window.INDIA_VECTOR_GEOJSON, {
      style: {
        color: '#00d4ff',
        weight: 1.5,
        opacity: 0.45,
        fillColor: '#0c1a30',
        fillOpacity: 0.25,
        dashArray: '3, 3'
      }
    }).addTo(mapInstance);
  }

  // Layer groups for markers and AOI footprint
  markersLayer = L.layerGroup().addTo(mapInstance);
  boundsLayer = L.layerGroup().addTo(mapInstance);

  // Mousemove telemetry listener
  mapInstance.on('mousemove', (e) => {
    const latElem = document.getElementById('hud-lat');
    const lonElem = document.getElementById('hud-lon');
    const zoomElem = document.getElementById('hud-zoom');
    if (latElem) latElem.textContent = e.latlng.lat.toFixed(4) + '° N';
    if (lonElem) lonElem.textContent = e.latlng.lng.toFixed(4) + '° E';
    if (zoomElem) zoomElem.textContent = mapInstance.getZoom();
  });

  // Layer buttons listener
  document.querySelectorAll('.layer-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.layer-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const layerKey = btn.getAttribute('data-layer');
      setMapLayer(layerKey);
      if (window.AETHER_APP) {
        window.AETHER_APP.showToast('Layer Switch', `Switched basemap to ${MAP_LAYERS[layerKey].name}`);
      }
    });
  });
}

function setMapLayer(key) {
  if (!mapInstance || !MAP_LAYERS[key]) return;
  if (currentTiles) {
    mapInstance.removeLayer(currentTiles);
  }

  const offlineSvgTile = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="%23090d16"/><path d="M0 32H256M0 64H256M0 96H256M0 128H256M0 160H256M0 192H256M0 224H256M32 0V256M64 0V256M96 0V256M128 0V256M160 0V256M192 0V256M224 0V256" stroke="%23141e33" stroke-width="1"/><text x="10" y="246" font-family="monospace" font-size="10" fill="%2300d4ff" opacity="0.4">AETHER OFFLINE GRID</text></svg>';

  currentTiles = L.tileLayer(MAP_LAYERS[key].url, {
    attribution: MAP_LAYERS[key].attribution,
    maxZoom: 18,
    errorTileUrl: offlineSvgTile
  }).addTo(mapInstance);
}

function renderMapCandidates(candidates) {
  if (!mapInstance || !markersLayer) return;
  markersLayer.clearLayers();

  const latLngs = [];

  candidates.forEach(cand => {
    const lat = cand.coordinates ? cand.coordinates.lat : 0;
    const lon = cand.coordinates ? cand.coordinates.lon : 0;

    // Only add valid non-zero coordinates
    if (lat !== 0 && lon !== 0) {
      latLngs.push([lat, lon]);
    }

    // Custom tactical marker icon
    const customIcon = L.divIcon({
      className: 'aether-marker',
      html: `
        <div class="marker-reticle" title="${cand.title} (${cand.matchScore}% Match)">
          <div class="marker-reticle-inner"></div>
        </div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });

    const marker = L.marker([lat, lon], { icon: customIcon });

    // Popup with satellite metadata
    marker.bindPopup(`
      <div style="font-family: var(--font-sans); color: #f8fafc; padding: 4px; min-width: 180px;">
        <div style="font-size: 11px; font-family: var(--font-mono); color: #38bdf8; font-weight: 700; margin-bottom: 2px;">
          ${cand.matchScore}% SEMANTIC MATCH
        </div>
        <div style="font-size: 13px; font-weight: 600; margin-bottom: 4px;">${cand.title}</div>
        <div style="font-size: 11px; color: #94a3b8; margin-bottom: 8px;">${cand.region}</div>
        <button onclick="window.AETHER_PROVENANCE.openDrawer('${cand.id}')" style="background: #00d4ff; color: #070b14; border: none; border-radius: 4px; font-size: 11px; font-weight: 600; padding: 4px 10px; cursor: pointer; width: 100%;">
          Inspect Location
        </button>
      </div>
    `, {
      className: 'aether-dark-popup'
    });

    marker.on('click', () => {
      highlightCandidateCard(cand.id);
      drawLocationFootprint(cand);
    });

    markersLayer.addLayer(marker);
  });

  // Fit bounds if we have valid candidate coordinates
  if (latLngs.length > 0) {
    mapInstance.fitBounds(L.latLngBounds(latLngs), {
      padding: [50, 50],
      maxZoom: 13
    });
  } else {
    // Keep centered over India
    mapInstance.setView([22.5937, 78.9629], 5);
  }
}

function focusLocationOnMap(cand) {
  if (!mapInstance) return;
  const lat = cand.coordinates.lat;
  const lon = cand.coordinates.lon;

  mapInstance.flyTo([lat, lon], 13, {
    duration: 1.2
  });

  drawLocationFootprint(cand);
}

function drawLocationFootprint(cand) {
  if (!mapInstance || !boundsLayer) return;
  boundsLayer.clearLayers();

  if (cand.bounds) {
    const polygon = L.polygon([
      cand.bounds[0],
      [cand.bounds[0][0], cand.bounds[1][1]],
      cand.bounds[1],
      [cand.bounds[1][0], cand.bounds[0][1]]
    ], {
      color: '#00d4ff',
      weight: 2,
      dashArray: '6, 4',
      fillColor: '#00d4ff',
      fillOpacity: 0.12
    });

    boundsLayer.addLayer(polygon);
  }
}

function highlightCandidateCard(locId) {
  document.querySelectorAll('.candidate-card').forEach(card => {
    if (card.getAttribute('data-id') === locId) {
      card.classList.add('active');
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } else {
      card.classList.remove('active');
    }
  });
}

window.AETHER_MAP = {
  initAetherMap,
  renderMapCandidates,
  focusLocationOnMap,
  drawLocationFootprint,
  setMapLayer
};

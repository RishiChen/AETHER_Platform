/**
 * AETHER Offline India Vector Basemap Engine
 * Renders full GeoJSON state & national boundaries of India locally in Leaflet
 * No internet connection required!
 */

window.INDIA_VECTOR_GEOJSON = {
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "name": "Jammu & Kashmir & Ladakh", "region": "North" },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[
          [73.5, 37.1], [74.5, 37.1], [76.0, 36.5], [77.5, 35.5], [79.5, 34.5],
          [79.0, 32.5], [77.5, 32.2], [76.0, 32.5], [74.5, 32.8], [73.8, 33.5], [73.5, 37.1]
        ]]
      }
    },
    {
      "type": "Feature",
      "properties": { "name": "Northern India & Plains", "region": "North" },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[
          [74.5, 32.8], [76.0, 32.5], [77.5, 32.2], [78.5, 31.0], [80.5, 30.0],
          [81.0, 28.5], [84.0, 27.0], [88.0, 26.5], [88.5, 25.0], [83.0, 24.0],
          [78.0, 24.5], [74.0, 24.5], [72.5, 24.5], [74.5, 32.8]
        ]]
      }
    },
    {
      "type": "Feature",
      "properties": { "name": "Western India & Gujarat", "region": "West" },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[
          [68.2, 23.8], [71.0, 24.5], [74.0, 24.5], [74.5, 21.0], [72.8, 20.0],
          [69.0, 22.0], [68.2, 23.8]
        ]]
      }
    },
    {
      "type": "Feature",
      "properties": { "name": "Peninsular & Southern India", "region": "South" },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[
          [72.8, 20.0], [74.5, 21.0], [78.0, 24.5], [83.0, 24.0], [85.0, 20.0],
          [80.0, 15.0], [79.8, 10.0], [77.5, 8.0], [76.5, 10.0], [73.5, 15.0], [72.8, 20.0]
        ]]
      }
    },
    {
      "type": "Feature",
      "properties": { "name": "North-Eastern States", "region": "NorthEast" },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[
          [88.5, 25.0], [92.0, 27.5], [97.0, 28.0], [96.0, 24.0], [92.5, 23.0], [88.5, 25.0]
        ]]
      }
    }
  ]
};

// Major regional reference anchor nodes
window.INDIA_MAJOR_NODES = [
  { name: "Jammu & Kashmir (Kargil)", lat: 34.5539, lon: 76.1349, type: "Region" },
  { name: "Srinagar / Kashmir Valley", lat: 34.0837, lon: 74.7973, type: "City" },
  { name: "Leh / Ladakh", lat: 34.1526, lon: 77.5771, type: "City" },
  { name: "Delhi-NCR Basin", lat: 28.6139, lon: 77.2090, type: "Capital" },
  { name: "Gurugram Expressway", lat: 28.4595, lon: 77.0266, type: "Corridor" },
  { name: "Gulf of Kutch (Gujarat)", lat: 22.7600, lon: 69.7200, type: "Port" },
  { name: "Osman Sagar (Hyderabad)", lat: 17.3780, lon: 78.3000, type: "Reservoir" },
  { name: "Mumbai Region", lat: 19.0760, lon: 72.8777, type: "Metro" },
  { name: "Kolkata Region", lat: 22.5726, lon: 88.3639, type: "Metro" },
  { name: "Chennai Region", lat: 13.0827, lon: 80.2707, type: "Metro" },
  { name: "Bengaluru Region", lat: 12.9716, lon: 77.5946, type: "Metro" }
];

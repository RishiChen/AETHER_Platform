const https = require('https');
const fs = require('fs');
const path = require('path');

function latLonTo3857(lat, lon) {
  const x = lon * 20037508.34 / 180;
  const y = Math.log(Math.tan((90 + lat) * Math.PI / 360)) / (Math.PI / 180) * 20037508.34 / 180;
  return [x, y];
}

const locations = [
  {
    id: 'loc-river',
    name: 'Yamuna River Corridor - Structural & Bridge Complex',
    lat: 28.545,
    lon: 77.310,
    span: 0.035, // ~3.8 km
    queryMatches: ['new structures near a river', 'river', 'structures', 'bridge', 'construction near river']
  },
  {
    id: 'loc-highway',
    name: 'South-West Expressway Corridor - Linear Arterial',
    lat: 28.485,
    lon: 77.025,
    span: 0.035,
    queryMatches: ['roads developed in an open area', 'road', 'highway', 'arterial', 'linear infrastructure']
  },
  {
    id: 'loc-water',
    name: 'Osman Sagar Catchment - Water Extent Variation',
    lat: 17.378,
    lon: 78.300,
    span: 0.038,
    queryMatches: ['water extent variation', 'water', 'reservoir', 'lake', 'flood']
  },
  {
    id: 'loc-industry',
    name: 'Coastal Port Logistics & Industrial Terminal',
    lat: 22.760,
    lon: 69.720,
    span: 0.035,
    queryMatches: ['large industrial structures', 'industrial', 'port', 'factory', 'storage tanks']
  },
  {
    id: 'loc-cleared',
    name: 'Southern Buffer Fringe - Land Clearing & Settlement',
    lat: 28.315,
    lon: 77.045,
    span: 0.035,
    queryMatches: ['cleared land near a settlement', 'cleared', 'deforestation', 'settlement', 'open land']
  }
];

const layers = [
  { year: 2020, layerName: 's2cloudless-2020_3857', tag: '2020' },
  { year: 2022, layerName: 's2cloudless-2022_3857', tag: '2022' },
  { year: 2024, layerName: 's2cloudless-2024_3857', tag: '2024' }
];

async function downloadTile(url, destPath) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode !== 200) {
        return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
      }
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => {
        const buffer = Buffer.concat(chunks);
        fs.writeFileSync(destPath, buffer);
        resolve(buffer.length);
      });
    }).on('error', reject);
  });
}

async function run() {
  const outDir = path.join(__dirname, '..', 'public', 'imagery');
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  for (const loc of locations) {
    console.log(`\nProcessing ${loc.name} (${loc.id})...`);
    const [minX, minY] = latLonTo3857(loc.lat - loc.span / 2, loc.lon - loc.span / 2);
    const [maxX, maxY] = latLonTo3857(loc.lat + loc.span / 2, loc.lon + loc.span / 2);
    const bbox = `${Math.round(minX)},${Math.round(minY)},${Math.round(maxX)},${Math.round(maxY)}`;

    for (const lyr of layers) {
      const filename = `${loc.id}-${lyr.tag}.jpg`;
      const destPath = path.join(outDir, filename);
      const url = `https://tiles.maps.eox.at/wms?service=wms&request=getmap&version=1.1.1&layers=${lyr.layerName}&styles=&format=image/jpeg&srs=epsg:3857&bbox=${bbox}&width=640&height=640`;
      try {
        console.log(`  Downloading ${lyr.tag} from Copernicus WMS...`);
        const bytes = await downloadTile(url, destPath);
        console.log(`  -> Saved ${filename} (${Math.round(bytes / 1024)} KB)`);
      } catch (err) {
        console.error(`  Error downloading ${filename}:`, err.message);
      }
    }
  }
  console.log('\nCopernicus imagery download complete!');
}

run().catch(console.error);

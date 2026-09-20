const fs = require('fs');
const path = require('path');

const masks = [
  {
    id: 'loc-river',
    svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" width="640" height="640">
  <defs>
    <filter id="glow-red" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#ef4444" flood-opacity="0.8"/>
    </filter>
  </defs>
  <!-- Primary structural expansion near river corridor -->
  <polygon points="310,240 430,220 460,330 340,360" fill="rgba(239, 68, 68, 0.3)" stroke="#ef4444" stroke-width="2.5" stroke-dasharray="6 3" filter="url(#glow-red)"/>
  <rect x="350" y="260" width="70" height="60" fill="rgba(249, 115, 22, 0.4)" stroke="#f97316" stroke-width="2"/>
  
  <!-- Bridge approach & pier footing -->
  <polygon points="260,310 320,295 340,370 280,385" fill="rgba(239, 68, 68, 0.35)" stroke="#ef4444" stroke-width="2"/>
  
  <!-- Bounding reticle & analyst annotations -->
  <rect x="250" y="210" width="220" height="190" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="8 6"/>
  <!-- Corner brackets -->
  <path d="M245,225 L245,205 L265,205" fill="none" stroke="#38bdf8" stroke-width="3"/>
  <path d="M475,225 L475,205 L455,205" fill="none" stroke="#38bdf8" stroke-width="3"/>
  <path d="M245,385 L245,405 L265,405" fill="none" stroke="#38bdf8" stroke-width="3"/>
  <path d="M475,385 L475,405 L455,405" fill="none" stroke="#38bdf8" stroke-width="3"/>
  
  <!-- Tactical badge -->
  <rect x="250" y="185" width="160" height="22" rx="3" fill="#0b1120" stroke="#ef4444" stroke-width="1.5"/>
  <text x="256" y="200" fill="#ef4444" font-family="monospace" font-size="11" font-weight="bold">TARGET 01: STRUCTURAL</text>
  <text x="415" y="200" fill="#38bdf8" font-family="monospace" font-size="10">94% CONF</text>
</svg>`
  },
  {
    id: 'loc-highway',
    svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" width="640" height="640">
  <!-- Linear highway corridor change -->
  <polygon points="120,540 180,560 520,130 460,110" fill="rgba(249, 115, 22, 0.35)" stroke="#f97316" stroke-width="2.5" stroke-dasharray="6 3"/>
  <polygon points="280,330 380,300 410,380 310,410" fill="rgba(239, 68, 68, 0.4)" stroke="#ef4444" stroke-width="2"/>
  <rect x="110" y="90" width="430" height="490" fill="none" stroke="#38bdf8" stroke-width="1" stroke-dasharray="6 4"/>
  <rect x="120" y="70" width="165" height="20" rx="3" fill="#0b1120" stroke="#f97316" stroke-width="1.5"/>
  <text x="126" y="84" fill="#f97316" font-family="monospace" font-size="11" font-weight="bold">LINEAR: ARTERIAL ROAD</text>
</svg>`
  },
  {
    id: 'loc-water',
    svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" width="640" height="640">
  <!-- Water extent delta -->
  <path d="M 210,180 Q 280,140 370,170 T 470,250 Q 420,380 330,420 T 180,360 Z" fill="rgba(6, 182, 212, 0.35)" stroke="#06b6d4" stroke-width="2.5" stroke-dasharray="4 4"/>
  <rect x="170" y="130" width="310" height="310" fill="none" stroke="#38bdf8" stroke-width="1" stroke-dasharray="4 4"/>
  <rect x="180" y="110" width="155" height="20" rx="3" fill="#0b1120" stroke="#06b6d4" stroke-width="1.5"/>
  <text x="186" y="124" fill="#06b6d4" font-family="monospace" font-size="11" font-weight="bold">SURFACE WATER SHIFT</text>
</svg>`
  },
  {
    id: 'loc-industry',
    svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" width="640" height="640">
  <!-- Industrial sheds & tank expansion -->
  <rect x="220" y="240" width="140" height="90" fill="rgba(239, 68, 68, 0.35)" stroke="#ef4444" stroke-width="2"/>
  <circle cx="420" cy="270" r="35" fill="rgba(249, 115, 22, 0.35)" stroke="#f97316" stroke-width="2"/>
  <circle cx="420" cy="350" r="35" fill="rgba(249, 115, 22, 0.35)" stroke="#f97316" stroke-width="2"/>
  <rect x="200" y="210" width="280" height="200" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="6 4"/>
  <rect x="200" y="185" width="170" height="22" rx="3" fill="#0b1120" stroke="#ef4444" stroke-width="1.5"/>
  <text x="206" y="200" fill="#ef4444" font-family="monospace" font-size="11" font-weight="bold">INDUSTRIAL EXPANSION</text>
</svg>`
  },
  {
    id: 'loc-cleared',
    svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" width="640" height="640">
  <!-- Cleared parcel -->
  <polygon points="260,200 410,190 440,380 270,390" fill="rgba(234, 179, 8, 0.35)" stroke="#eab308" stroke-width="2"/>
  <rect x="240" y="170" width="220" height="240" fill="none" stroke="#38bdf8" stroke-width="1" stroke-dasharray="6 4"/>
  <rect x="240" y="145" width="165" height="22" rx="3" fill="#0b1120" stroke="#eab308" stroke-width="1.5"/>
  <text x="246" y="160" fill="#eab308" font-family="monospace" font-size="11" font-weight="bold">CLEARED VEGETATION</text>
</svg>`
  }
];

const outDir = path.join(__dirname, '..', 'public', 'imagery');
for (const m of masks) {
  const filePath = path.join(outDir, `${m.id}-mask.svg`);
  fs.writeFileSync(filePath, m.svg.trim());
  console.log(`Saved mask: ${m.id}-mask.svg`);
}

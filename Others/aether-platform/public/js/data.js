/**
 * AETHER Global Data & Reference Constants
 * SIH 2026 Problem Statement 26227
 */

const PIPELINE_STEPS = [
  {
    num: '01',
    name: 'Satellite Imagery',
    stage: 'Archive Ingestion',
    summary: 'Raw multispectral & radar telemetry acquisition.',
    details: 'Ingests raw Top-Of-Atmosphere (TOA L1C) and Bottom-Of-Atmosphere (BOA L2A) granules from Copernicus Sentinel-2 (MSI), Sentinel-1 (C-SAR), Landsat Collection 2 (OLI), and Bhuvan/NRSC datasets.'
  },
  {
    num: '02',
    name: 'Ingestion & Preprocessing',
    stage: 'Calibration & Correction',
    summary: 'Atmospheric correction, radiometric calibration and QA masking.',
    details: 'Applies Sen2Cor radiative transfer atmospheric correction, Scene Classification Layer (SCL) generation, and invalid pixel/nodata masking across all spectral bands.'
  },
  {
    num: '03',
    name: 'Image Tiling & Registration',
    stage: 'Spatial Standardization',
    summary: 'Sub-pixel co-registration and uniform spatial chip tiling.',
    details: 'Standardizes imagery into consistent 512x512 pixel chips (10m GSD). Executes sub-pixel phase-correlation co-registration to guarantee spatial alignment RMS < 0.2 pixels across epochs.'
  },
  {
    num: '04',
    name: 'AI Representation',
    stage: 'Multimodal Embedding',
    summary: 'Self-supervised vision-language embedding extraction.',
    details: 'Feeds multispectral image chips and natural-language text into AETHER-GeoEmbed-v2 (Vision Transformer architecture fine-tuned on Earth observation tasks) to generate 768-dimensional normalized feature vectors.'
  },
  {
    num: '05',
    name: 'Vector Retrieval',
    stage: 'Sub-second Index Search',
    summary: 'Hierarchical Navigable Small World (HNSW) vector search.',
    details: 'Searches multi-terabyte offline vector index using cosine similarity distance metrics, returning candidate satellite tiles in under 35 milliseconds.'
  },
  {
    num: '06',
    name: 'Candidate Ranking',
    stage: 'Semantic Scoring',
    summary: 'Semantic alignment scoring and geographic filtering.',
    details: 'Ranks retrieved candidates by semantic affinity, applies spatial bounding filters, and thresholds candidates above a 70% relevance threshold.'
  },
  {
    num: '07',
    name: 'Temporal Comparison',
    stage: 'Multi-Epoch Pairing',
    summary: 'Bi-temporal and multi-temporal archive alignment for same AOI.',
    details: 'Retrieves historic multi-year baseline passes (e.g. 2020, 2022, 2024) for the selected candidate location under matching solar geometries.'
  },
  {
    num: '08',
    name: 'Quality Checks',
    stage: 'False-Alarm Screening',
    summary: 'Suppression of clouds, haze, shadows, and seasonal variations.',
    details: 'Applies multi-spectral QA filters: cloud mask validation, Cirrus band 10 inspection, shadow vector elimination, and phenological NDVI baseline verification.'
  },
  {
    num: '09',
    name: 'Change Detection',
    stage: 'Change Vector Analysis',
    summary: 'Isolates genuine structural emergence from background noise.',
    details: 'Executes Change Vector Analysis (CVA), spectral index deltas (NDBI, MNDWI, NDVI), and spatial morphological segmentation to outline changed regions.'
  },
  {
    num: '10',
    name: 'Confidence & Evidence',
    stage: 'Probabilistic Calibrated Scoring',
    summary: 'Generates confidence scores and provenance audit ledger.',
    details: 'Computes calibrated confidence scores per detected change category, links raw Copernicus granule IDs, processing checksums, and vector embeddings.'
  },
  {
    num: '11',
    name: 'Analyst Review',
    stage: 'Human-in-the-Loop Verification',
    summary: 'Interactive decision confirmation, rejection, or escalation.',
    details: 'AETHER presents evidence to geospatial intelligence analysts for final review. Analyst decisions are cryptographically logged with rationale to the inspection audit trail.'
  }
];

const FALSE_ALARM_MATRIX = [
  {
    challenge: 'Clouds & Cirrus',
    mitigation: 'Scene Classification Layer (SCL) & Cirrus Band 10 Filtering',
    impact: 'Masks opaque clouds, high-altitude cirrus, and cloud shadows before comparison.'
  },
  {
    challenge: 'Atmospheric Haze & Aerosols',
    mitigation: 'Sen2Cor Radiative Transfer Atmospheric Correction',
    impact: 'Normalizes Bottom-Of-Atmosphere (BOA) surface reflectance across varying optical depths.'
  },
  {
    challenge: 'Seasonal Phenology',
    mitigation: 'Harmonic NDVI Multi-Temporal Baseline Comparison',
    impact: 'Distinguishes natural vegetation dry/monsoon variations from permanent land-cover transformations.'
  },
  {
    challenge: 'Spatial Misalignment',
    mitigation: 'Phase-Correlation Sub-Pixel Co-Registration',
    impact: 'Eliminates boundary edge artifacts by enforcing sub-pixel alignment (<0.20 pixel error).'
  },
  {
    challenge: 'Solar & View Geometry Differentials',
    mitigation: 'Bidirectional Reflectance Distribution Function (BRDF) Normalization',
    impact: 'Normalizes reflectance anomalies caused by seasonal sun-zenith and satellite-sensor azimuth angles.'
  }
];

window.AETHER_DATA = {
  PIPELINE_STEPS,
  FALSE_ALARM_MATRIX
};

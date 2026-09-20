"""
AETHER Pydantic Request & Response Schemas
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# Health & System Stats
class HealthResponse(BaseModel):
    status: str = "ok"
    offlineMode: bool = True
    systemStatus: str = "ONLINE · LOCAL ARCHIVE READY"
    databaseConnected: bool = True
    aiModelStatus: str = "READY"


class StatsResponse(BaseModel):
    offlineMode: bool = True
    systemStatus: str = "ONLINE · LOCAL ARCHIVE READY"
    archiveSize: str = "1.4 TB (Indexed)"
    indexedTiles: int = 142850
    activeSensors: List[str] = [
        "Copernicus Sentinel-2 MSI",
        "Copernicus Sentinel-1 SAR",
        "USGS Landsat Collection 2"
    ]
    pendingReviews: int = 0
    completedReviews: int = 0


# Coordinates & Location Models
class Coordinates(BaseModel):
    lat: float
    lon: float
    dms: Optional[str] = None
    mgrs: Optional[str] = None
    utm: Optional[str] = None


class ReviewRecord(BaseModel):
    decision: str  # 'confirmed' | 'rejected' | 'flagged' | 'pending'
    analystId: str
    timestamp: str
    notes: Optional[str] = None
    auditId: str


class TemporalSequenceItem(BaseModel):
    year: str
    date: str
    granule: Optional[str] = None
    thumb: str
    quality: Optional[str] = None
    status: Optional[str] = None


class DetectedChangeItem(BaseModel):
    label: str
    confidence: float
    category: str
    category_code: Optional[str] = "building"
    severity: str
    description: str
    bbox: Optional[List[int]] = None
    area_m2: Optional[int] = None


class FalseAlarmCheck(BaseModel):
    label: str
    detail: str
    passed: bool = True


class FalseAlarmAnalysis(BaseModel):
    checks: List[FalseAlarmCheck]
    riskLevel: str
    riskScore: str
    verdict: str


class ProvenanceInfo(BaseModel):
    beforeGranule: str
    afterGranule: str
    sensor: str
    spatialResolution: str
    registrationMethod: str
    vectorModel: str
    sha256Digest: str
    archiveNode: str
    w3cProvDm: Optional[Dict[str, Any]] = None
    w3cProvOJsonLd: Optional[Dict[str, Any]] = None
    iso19115Lineage: Optional[Dict[str, Any]] = None


class ChangeAnalysisData(BaseModel):
    beforeYear: str
    beforeDate: str
    beforeImage: str
    afterYear: str
    afterDate: str
    afterImage: str
    maskImage: Optional[str] = None
    confidenceScore: float
    changeType: str
    affectedArea: str
    summary: str
    detectedChanges: List[DetectedChangeItem]
    falseAlarmAnalysis: FalseAlarmAnalysis
    provenance: Optional[ProvenanceInfo] = None
    builtup_ha: Optional[float] = None
    clearing_ha: Optional[float] = None
    road_km: Optional[float] = None
    total_ha: Optional[float] = None


class CandidateLocation(BaseModel):
    id: str
    title: str
    region: str
    coordinates: Coordinates
    bounds: List[List[float]] = []
    source: str
    sensor: str
    resolution: str
    sunZenith: Optional[str] = "30.0°"
    cloudCover: str
    matchScore: int = 80
    tags: List[str] = []
    semanticRationale: str
    thumbnails: Dict[str, str]
    temporalSequence: Optional[List[TemporalSequenceItem]] = []
    changeAnalysis: Optional[ChangeAnalysisData] = None
    reviewStatus: Optional[ReviewRecord] = None


class CandidatesListResponse(BaseModel):
    success: bool = True
    totalCount: int
    candidates: List[CandidateLocation]
    aiStatus: Optional[str] = "OPERATIONAL"


class LocationResponse(BaseModel):
    success: bool = True
    location: CandidateLocation


class ChangeAnalysisResponse(BaseModel):
    success: bool = True
    locationId: str
    locationTitle: str
    region: str
    coordinates: Coordinates
    source: str
    sensor: str
    temporalSequence: List[TemporalSequenceItem]
    changeAnalysis: ChangeAnalysisData
    reviewStatus: Optional[ReviewRecord] = None


# Review Submission
class ReviewRequest(BaseModel):
    locationId: str
    decision: str = Field(..., description="'confirmed' | 'rejected' | 'flagged'")
    analystId: Optional[str] = "ANALYST_4092_SIGINT"
    notes: Optional[str] = None


class ReviewResponse(BaseModel):
    success: bool = True
    message: str
    review: ReviewRecord


# Ingestion Response
class IngestionResponse(BaseModel):
    success: bool = True
    message: str
    filesProcessed: int
    indexedScenes: List[Any]

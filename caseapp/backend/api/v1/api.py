"""
API v1 router configuration
"""

from fastapi import APIRouter
from api.v1.endpoints import cases, documents, timeline, media, forensic, financial_analysis, collaboration, insights, exports, auth, audit, integrations, efiling, background_jobs, health, monitoring, diagnostics

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(timeline.router, prefix="/timeline", tags=["timeline"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(forensic.router, prefix="/forensic", tags=["forensic"])
api_router.include_router(financial_analysis.router, prefix="/financial", tags=["financial-analysis"])
api_router.include_router(collaboration.router, prefix="/collaboration", tags=["collaboration"])
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(efiling.router, prefix="/efiling", tags=["efiling"])
api_router.include_router(background_jobs.router, prefix="/jobs", tags=["background-jobs"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
api_router.include_router(diagnostics.router, prefix="/diagnostics", tags=["diagnostics"])
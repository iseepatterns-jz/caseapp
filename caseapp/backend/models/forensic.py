"""
Forensic models - compatibility import module
"""

# Import all forensic models from the main forensic_analysis module
from models.forensic_analysis import (
    ForensicSource,
    ForensicDataType,
    AnalysisStatus,
    ForensicAnalysis,
    EmailMessage,
    TextMessage,
    CallRecord,
    ContactEntry,
    LocationData,
    BrowserHistory,
    AppData,
    ForensicTimeline,
    ForensicReport
)

__all__ = [
    "ForensicSource",
    "ForensicDataType", 
    "AnalysisStatus",
    "ForensicAnalysis",
    "EmailMessage",
    "TextMessage",
    "CallRecord",
    "ContactEntry",
    "LocationData",
    "BrowserHistory",
    "AppData",
    "ForensicTimeline",
    "ForensicReport"
]
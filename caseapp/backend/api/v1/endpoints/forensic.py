"""
Forensic analysis API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from typing import List, Optional, Dict, Any
import structlog
import os
import shutil
from datetime import datetime, UTC

from core.database import get_db
from core.config import settings
from models.forensic_analysis import (
    ForensicSource, ForensicItem, ForensicAnalysisReport, ForensicAlert,
    CommunicationNetwork, ForensicDataType, AnalysisStatus
)
from services.forensic_analysis_service import ForensicAnalysisService
from schemas.forensic import (
    ForensicSourceCreate, ForensicSourceResponse, ForensicItemResponse,
    ForensicAnalysisReportResponse, ForensicSearchRequest, ForensicSearchResponse
)
from core.auth import get_current_user

from services.audit_service import AuditService

logger = structlog.get_logger()
router = APIRouter()

async def get_forensic_service(db: AsyncSession = Depends(get_db)) -> ForensicAnalysisService:
    """Dependency to get forensic service instance"""
    audit_service = AuditService(db)
    return ForensicAnalysisService(audit_service=audit_service)

@router.post("/upload", response_model=ForensicSourceResponse)
async def upload_forensic_data(
    case_id: int = Form(...),
    source_name: str = Form(...),
    source_type: str = Form(...),
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    forensic_service: ForensicAnalysisService = Depends(get_forensic_service)
):
    """Upload forensic data file for analysis"""
    
    # Validate file type
    allowed_extensions = ['.db', '.sqlite', '.sqlite3', '.mbox', '.eml', '.pst', '.zip']
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_extension} not supported. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Validate file size (max 1GB)
    max_size = 1024 * 1024 * 1024  # 1GB
    if file.size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed size of {max_size} bytes"
        )
    
    try:
        # Create forensic data directory
        forensic_dir = f"/tmp/forensic_data/{case_id}"
        os.makedirs(forensic_dir, exist_ok=True)
        
        # Save uploaded file
        file_path = os.path.join(forensic_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process forensic source
        source = await forensic_service.process_forensic_source(
            case_id=case_id,
            file_path=file_path,
            source_name=source_name,
            source_type=source_type,
            user_id=current_user.id
        )
        
        return source
        
    except Exception as e:
        logger.error("Failed to upload forensic data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to upload forensic data")

@router.get("/sources/{case_id}", response_model=List[ForensicSourceResponse])
async def get_forensic_sources(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all forensic sources for a case"""
    
    result = await db.execute(
        select(ForensicSource)
        .where(ForensicSource.case_id == case_id)
        .order_by(desc(ForensicSource.created_at))
    )
    sources = result.scalars().all()
    
    return sources

@router.get("/sources/{source_id}/status")
async def get_analysis_status(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get analysis status for a forensic source"""
    
    result = await db.execute(select(ForensicSource).where(ForensicSource.id == source_id))
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Forensic source not found")
    
    return {
        "source_id": source.id,
        "status": source.analysis_status.value,
        "progress": source.analysis_progress,
        "started_at": source.analysis_started_at,
        "completed_at": source.analysis_completed_at,
        "errors": source.analysis_errors
    }

@router.get("/items/search", response_model=ForensicSearchResponse)
async def search_forensic_items(
    case_id: int = Query(...),
    query: Optional[str] = Query(None, description="Search query"),
    item_types: Optional[List[ForensicDataType]] = Query(None, description="Filter by item types"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    sender: Optional[str] = Query(None, description="Filter by sender"),
    recipients: Optional[str] = Query(None, description="Filter by recipients"),
    min_relevance: Optional[float] = Query(None, description="Minimum relevance score"),
    has_attachments: Optional[bool] = Query(None, description="Filter items with attachments"),
    sentiment_range: Optional[str] = Query(None, description="Sentiment range: positive, negative, neutral"),
    is_flagged: Optional[bool] = Query(None, description="Filter flagged items"),
    is_suspicious: Optional[bool] = Query(None, description="Filter suspicious items"),
    is_deleted: Optional[bool] = Query(None, description="Filter deleted items"),
    keywords: Optional[str] = Query(None, description="Search in extracted keywords"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Search forensic items with advanced filters (Requirements 5.6)"""
    
    # Build query
    query_stmt = select(ForensicItem).join(ForensicSource).where(ForensicSource.case_id == case_id)
    
    if query:
        query_stmt = query_stmt.where(
            or_(
                ForensicItem.content.ilike(f"%{query}%"),
                ForensicItem.subject.ilike(f"%{query}%"),
                ForensicItem.sender.ilike(f"%{query}%")
            )
        )
    
    if item_types:
        query_stmt = query_stmt.where(ForensicItem.item_type.in_(item_types))
    
    if date_from:
        query_stmt = query_stmt.where(ForensicItem.timestamp >= date_from)
    
    if date_to:
        query_stmt = query_stmt.where(ForensicItem.timestamp <= date_to)
    
    if sender:
        query_stmt = query_stmt.where(ForensicItem.sender.ilike(f"%{sender}%"))
    
    if recipients:
        # Search in recipients JSON array
        query_stmt = query_stmt.where(
            ForensicItem.recipients.op('::text')(f'%{recipients}%')
        )
    
    if min_relevance:
        query_stmt = query_stmt.where(ForensicItem.relevance_score >= min_relevance)
    
    if has_attachments is not None:
        if has_attachments:
            query_stmt = query_stmt.where(ForensicItem.attachments.isnot(None))
        else:
            query_stmt = query_stmt.where(ForensicItem.attachments.is_(None))
    
    if is_flagged is not None:
        query_stmt = query_stmt.where(ForensicItem.is_flagged == is_flagged)
    
    if is_suspicious is not None:
        query_stmt = query_stmt.where(ForensicItem.is_suspicious == is_suspicious)
    
    if is_deleted is not None:
        query_stmt = query_stmt.where(ForensicItem.is_deleted == is_deleted)
    
    if keywords:
        # Search in extracted keywords JSON array
        query_stmt = query_stmt.where(
            ForensicItem.keywords.op('::text')(f'%{keywords}%')
        )
    
    if sentiment_range:
        if sentiment_range == "positive":
            query_stmt = query_stmt.where(ForensicItem.sentiment_score > 0.1)
        elif sentiment_range == "negative":
            query_stmt = query_stmt.where(ForensicItem.sentiment_score < -0.1)
        elif sentiment_range == "neutral":
            query_stmt = query_stmt.where(
                and_(
                    ForensicItem.sentiment_score >= -0.1,
                    ForensicItem.sentiment_score <= 0.1
                )
            )
    
    # Get total count
    count_stmt = select(func.count()).select_from(query_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    query_stmt = query_stmt.order_by(desc(ForensicItem.relevance_score), desc(ForensicItem.timestamp))
    query_stmt = query_stmt.offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query_stmt)
    items = result.scalars().all()
    
    return ForensicSearchResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit
    )

@router.get("/items/{item_id}", response_model=ForensicItemResponse)
async def get_forensic_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get detailed forensic item"""
    
    result = await db.execute(select(ForensicItem).where(ForensicItem.id == item_id))
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Forensic item not found")
    
    return item

@router.post("/items/{item_id}/flag")
async def flag_forensic_item(
    item_id: int,
    flag_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Flag forensic item as important or suspicious"""
    
    result = await db.execute(select(ForensicItem).where(ForensicItem.id == item_id))
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Forensic item not found")
    
    item.is_flagged = flag_data.get('is_flagged', True)
    item.flag_reason = flag_data.get('reason', '')
    item.is_suspicious = flag_data.get('is_suspicious', False)
    
    await db.commit()
    
    return {"message": "Item flagged successfully"}

@router.get("/reports/{source_id}", response_model=List[ForensicAnalysisReportResponse])
async def get_analysis_reports(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get analysis reports for forensic source"""
    
    result = await db.execute(
        select(ForensicAnalysisReport)
        .where(ForensicAnalysisReport.source_id == source_id)
        .order_by(desc(ForensicAnalysisReport.created_at))
    )
    reports = result.scalars().all()
    
    return reports

@router.get("/reports/{report_id}/details", response_model=ForensicAnalysisReportResponse)
async def get_report_details(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get detailed analysis report"""
    
    result = await db.execute(select(ForensicAnalysisReport).where(ForensicAnalysisReport.id == report_id))
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Analysis report not found")
    
    return report

@router.get("/network/{source_id}")
async def get_communication_network(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get communication network analysis"""
    
    result = await db.execute(
        select(CommunicationNetwork).where(CommunicationNetwork.source_id == source_id)
    )
    network = result.scalar_one_or_none()
    
    if not network:
        raise HTTPException(status_code=404, detail="Network analysis not found")
    
    return {
        "nodes": network.nodes,
        "edges": network.edges,
        "clusters": network.clusters,
        "centrality_scores": network.centrality_scores,
        "community_detection": network.community_detection,
        "temporal_analysis": network.temporal_analysis
    }

@router.get("/timeline/{source_id}")
async def get_forensic_timeline(
    source_id: int,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    item_types: Optional[List[ForensicDataType]] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get forensic timeline data"""
    
    query_stmt = select(ForensicItem).where(ForensicItem.source_id == source_id)
    
    if start_date:
        query_stmt = query_stmt.where(ForensicItem.timestamp >= start_date)
    
    if end_date:
        query_stmt = query_stmt.where(ForensicItem.timestamp <= end_date)
    
    if item_types:
        query_stmt = query_stmt.where(ForensicItem.item_type.in_(item_types))
    
    query_stmt = query_stmt.order_by(ForensicItem.timestamp)
    
    result = await db.execute(query_stmt)
    items = result.scalars().all()
    
    timeline_data = []
    for item in items:
        timeline_data.append({
            "id": item.id,
            "timestamp": item.timestamp.isoformat(),
            "type": item.item_type.value,
            "sender": item.sender,
            "recipients": item.recipients,
            "subject": item.subject,
            "content_preview": (item.content or "")[:200],
            "sentiment": item.sentiment_score,
            "relevance": item.relevance_score,
            "is_flagged": item.is_flagged,
            "is_suspicious": item.is_suspicious
        })
    
    return {
        "timeline": timeline_data,
        "total_items": len(timeline_data),
        "date_range": {
            "start": min(item["timestamp"] for item in timeline_data) if timeline_data else None,
            "end": max(item["timestamp"] for item in timeline_data) if timeline_data else None
        }
    }

@router.post("/items/{item_id}/pin-to-timeline")
async def pin_forensic_item_to_timeline(
    item_id: int,
    timeline_event_id: int,
    pin_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Pin forensic item to timeline event"""
    
    from models.forensic_analysis import ForensicTimelinePin
    
    # Verify forensic item exists
    item_result = await db.execute(select(ForensicItem).where(ForensicItem.id == item_id))
    item = item_result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Forensic item not found")
    
    # Create timeline pin
    pin = ForensicTimelinePin(
        timeline_event_id=timeline_event_id,
        forensic_item_id=item_id,
        relevance_score=pin_data.get('relevance_score', 5.0),
        context_note=pin_data.get('context_note', ''),
        is_key_evidence=pin_data.get('is_key_evidence', False),
        pinned_by_id=current_user.id
    )
    
    db.add(pin)
    await db.commit()
    await db.refresh(pin)
    
    return {"message": "Forensic item pinned to timeline successfully", "pin_id": pin.id}

@router.get("/alerts/{source_id}")
async def get_forensic_alerts(
    source_id: int,
    severity: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get forensic alerts"""
    
    query_stmt = select(ForensicAlert).where(ForensicAlert.source_id == source_id)
    
    if severity:
        query_stmt = query_stmt.where(ForensicAlert.severity == severity)
    
    if acknowledged is not None:
        query_stmt = query_stmt.where(ForensicAlert.is_acknowledged == acknowledged)
    
    query_stmt = query_stmt.order_by(desc(ForensicAlert.created_at))
    
    result = await db.execute(query_stmt)
    alerts = result.scalars().all()
    
    return alerts

@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Acknowledge forensic alert"""
    
    result = await db.execute(select(ForensicAlert).where(ForensicAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.is_acknowledged = True
    alert.acknowledged_by_id = current_user.id
    alert.acknowledged_at = datetime.now(UTC)
    
    await db.commit()
    
    return {"message": "Alert acknowledged successfully"}

@router.get("/patterns/{source_id}")
async def get_suspicious_patterns(
    source_id: int,
    severity: Optional[str] = Query(None, description="Filter by severity: low, medium, high"),
    pattern_type: Optional[str] = Query(None, description="Filter by pattern type: timing, content, participant, frequency"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get detected suspicious patterns for a forensic source (Requirements 5.5)"""
    
    # Get the analysis report which contains detected patterns
    result = await db.execute(
        select(ForensicAnalysisReport)
        .where(ForensicAnalysisReport.source_id == source_id)
        .order_by(desc(ForensicAnalysisReport.created_at))
        .limit(1)
    )
    report = result.scalar_one_or_none()
    
    if not report or not report.insights:
        return {"patterns": [], "total": 0}
    
    # Filter patterns from insights
    patterns = [
        insight for insight in report.insights 
        if insight.get('type') in ['suspicious', 'timing', 'content', 'participant', 'frequency', 'sentiment']
    ]
    
    # Apply filters
    if severity:
        patterns = [p for p in patterns if p.get('severity') == severity]
    
    if pattern_type:
        patterns = [p for p in patterns if p.get('type') == pattern_type]
    
    return {
        "patterns": patterns,
        "total": len(patterns),
        "source_id": source_id
    }

@router.post("/patterns/{source_id}/analyze")
async def analyze_suspicious_patterns(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    forensic_service: ForensicAnalysisService = Depends(get_forensic_service)
):
    """Re-analyze forensic source for suspicious patterns (Requirements 5.5)"""
    
    # Get forensic source
    source_result = await db.execute(select(ForensicSource).where(ForensicSource.id == source_id))
    source = source_result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Forensic source not found")
    
    # Get all forensic items for this source
    items_result = await db.execute(
        select(ForensicItem).where(ForensicItem.source_id == source_id)
    )
    items = items_result.scalars().all()
    
    if not items:
        return {"message": "No forensic items found for analysis", "patterns": []}
    
    # Analyze communication patterns
    communication_stats = forensic_service._analyze_communication_patterns(items)
    
    # Detect suspicious patterns
    suspicious_patterns = forensic_service._detect_suspicious_patterns(items, communication_stats)
    
    # Update the analysis report with new patterns
    report_result = await db.execute(
        select(ForensicAnalysisReport)
        .where(ForensicAnalysisReport.source_id == source_id)
        .order_by(desc(ForensicAnalysisReport.created_at))
        .limit(1)
    )
    report = report_result.scalar_one_or_none()
    
    if report:
        # Update existing report
        current_insights = report.insights or []
        # Remove old pattern insights
        current_insights = [i for i in current_insights if i.get('type') not in ['suspicious', 'timing', 'content', 'participant', 'frequency']]
        # Add new patterns
        current_insights.extend(suspicious_patterns)
        report.insights = current_insights
        await db.commit()
    
    # Create new forensic alerts for high/medium severity patterns
    for pattern in suspicious_patterns:
        if pattern.get('severity') in ['high', 'medium']:
            # Check if alert already exists
            existing_alert = await db.execute(
                select(ForensicAlert).where(
                    and_(
                        ForensicAlert.source_id == source_id,
                        ForensicAlert.title == pattern['title']
                    )
                )
            )
            
            if not existing_alert.scalar_one_or_none():
                alert = ForensicAlert(
                    source_id=source_id,
                    alert_type=pattern['type'],
                    severity=pattern['severity'],
                    title=pattern['title'],
                    description=pattern['description'],
                    trigger_criteria={
                        'pattern_type': pattern['type'],
                        'detection_method': 'manual_reanalysis'
                    },
                    affected_items=pattern.get('affected_items', [])
                )
                db.add(alert)
    
    await db.commit()
    
    return {
        "message": "Pattern analysis completed",
        "patterns_detected": len(suspicious_patterns),
        "patterns": suspicious_patterns
    }
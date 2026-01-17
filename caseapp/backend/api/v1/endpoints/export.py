"""
API endpoints for export and reporting functionality
Provides timeline and forensic report generation in multiple formats
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
import io
import structlog

from schemas.export import (
    TimelineExportRequest,
    ForensicReportRequest,
    SelectiveExportRequest,
    ExportResponse
)
from services.export_service import ExportService
from core.auth import get_current_user
from core.exceptions import CaseManagementException
from models.user import User

logger = structlog.get_logger()
router = APIRouter()

@router.post("/timeline/pdf", response_class=StreamingResponse)
async def export_timeline_pdf(
    request: TimelineExportRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Export timeline as professional PDF report
    
    - **case_id**: UUID of the case to export
    - **timeline_id**: Optional specific timeline ID
    - **date_range**: Optional date filtering
    - **include_evidence**: Whether to include evidence attachments
    - **include_metadata**: Whether to include event metadata
    """
    try:
        export_service = ExportService()
        
        # Convert date range if provided
        date_range = None
        if request.date_range:
            date_range = {
                'start': request.date_range.start_date,
                'end': request.date_range.end_date
            }
        
        pdf_content = await export_service.export_timeline_pdf(
            case_id=request.case_id,
            timeline_id=request.timeline_id,
            date_range=date_range,
            include_evidence=request.include_evidence,
            include_metadata=request.include_metadata
        )
        
        # Generate filename
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"timeline_report_{request.case_id[:8]}_{timestamp}.pdf"
        
        # Return as streaming response
        pdf_stream = io.BytesIO(pdf_content)
        
        logger.info("Timeline PDF export completed", 
                   case_id=request.case_id, 
                   user_id=str(current_user.id),
                   file_size=len(pdf_content))
        
        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except CaseManagementException as e:
        logger.error("Timeline PDF export failed", 
                    case_id=request.case_id, 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in timeline PDF export", 
                    case_id=request.case_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/timeline/png", response_class=StreamingResponse)
async def export_timeline_png(
    request: TimelineExportRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Export timeline as high-resolution PNG visualization
    
    - **case_id**: UUID of the case to export
    - **timeline_id**: Optional specific timeline ID
    - **date_range**: Optional date filtering
    - **width**: Image width in pixels (default: 1920)
    - **height**: Image height in pixels (default: 1080)
    - **dpi**: Image resolution (default: 300)
    """
    try:
        export_service = ExportService()
        
        # Convert date range if provided
        date_range = None
        if request.date_range:
            date_range = {
                'start': request.date_range.start_date,
                'end': request.date_range.end_date
            }
        
        png_content = await export_service.export_timeline_png(
            case_id=request.case_id,
            timeline_id=request.timeline_id,
            date_range=date_range,
            width=request.width or 1920,
            height=request.height or 1080,
            dpi=request.dpi or 300
        )
        
        # Generate filename
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"timeline_visualization_{request.case_id[:8]}_{timestamp}.png"
        
        logger.info("Timeline PNG export completed", 
                   case_id=request.case_id, 
                   user_id=str(current_user.id),
                   file_size=len(png_content))
        
        return StreamingResponse(
            io.BytesIO(png_content),
            media_type="image/png",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except CaseManagementException as e:
        logger.error("Timeline PNG export failed", 
                    case_id=request.case_id, 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in timeline PNG export", 
                    case_id=request.case_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/forensic/pdf", response_class=StreamingResponse)
async def export_forensic_report_pdf(
    request: ForensicReportRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Export comprehensive forensic analysis report as PDF
    
    - **case_id**: UUID of the case to export
    - **source_ids**: Optional list of specific forensic source IDs
    - **include_statistics**: Whether to include communication statistics
    - **include_network_analysis**: Whether to include network graphs
    - **include_raw_data**: Whether to include raw message data
    """
    try:
        export_service = ExportService()
        
        pdf_content = await export_service.export_forensic_report_pdf(
            case_id=request.case_id,
            source_ids=request.source_ids,
            include_statistics=request.include_statistics,
            include_network_analysis=request.include_network_analysis,
            include_raw_data=request.include_raw_data
        )
        
        # Generate filename
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"forensic_report_{request.case_id[:8]}_{timestamp}.pdf"
        
        logger.info("Forensic report PDF export completed", 
                   case_id=request.case_id, 
                   user_id=str(current_user.id),
                   file_size=len(pdf_content))
        
        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except CaseManagementException as e:
        logger.error("Forensic report PDF export failed", 
                    case_id=request.case_id, 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in forensic report PDF export", 
                    case_id=request.case_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/selective", response_model=ExportResponse)
async def export_selective_data(
    request: SelectiveExportRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Export case data with selective filtering
    
    - **case_id**: UUID of the case to export
    - **export_format**: Export format ('pdf', 'json', 'csv')
    - **filters**: Export filters including date ranges, evidence types, etc.
    """
    try:
        export_service = ExportService()
        
        # Convert date range in filters if provided
        if 'date_range' in request.filters and request.filters['date_range']:
            date_range = request.filters['date_range']
            if isinstance(date_range, dict):
                if 'start_date' in date_range:
                    date_range['start'] = date_range.pop('start_date')
                if 'end_date' in date_range:
                    date_range['end'] = date_range.pop('end_date')
        
        result = await export_service.export_selective_data(
            case_id=request.case_id,
            export_format=request.export_format,
            filters=request.filters
        )
        
        if request.export_format.lower() == 'json':
            logger.info("Selective JSON export completed", 
                       case_id=request.case_id, 
                       user_id=str(current_user.id),
                       format=request.export_format)
            
            return ExportResponse(
                success=True,
                message="Export completed successfully",
                data=result,
                export_format=request.export_format,
                timestamp=datetime.now(UTC)
            )
        else:
            # For PDF format, return as streaming response
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            filename = f"selective_export_{request.case_id[:8]}_{timestamp}.pdf"
            
            logger.info("Selective PDF export completed", 
                       case_id=request.case_id, 
                       user_id=str(current_user.id),
                       format=request.export_format,
                       file_size=len(result))
            
            return StreamingResponse(
                io.BytesIO(result),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
    except CaseManagementException as e:
        logger.error("Selective export failed", 
                    case_id=request.case_id, 
                    user_id=str(current_user.id),
                    format=request.export_format,
                    error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in selective export", 
                    case_id=request.case_id,
                    format=request.export_format,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/formats")
async def get_supported_formats(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of supported export formats and their capabilities
    """
    return {
        "timeline_formats": [
            {
                "format": "pdf",
                "description": "Professional PDF report with events and evidence",
                "supports_filtering": True,
                "supports_evidence": True,
                "supports_metadata": True
            },
            {
                "format": "png",
                "description": "High-resolution timeline visualization",
                "supports_filtering": True,
                "supports_evidence": False,
                "supports_metadata": False
            }
        ],
        "forensic_formats": [
            {
                "format": "pdf",
                "description": "Comprehensive forensic analysis report",
                "supports_statistics": True,
                "supports_network_analysis": True,
                "supports_raw_data": True
            }
        ],
        "selective_formats": [
            {
                "format": "json",
                "description": "Structured data export in JSON format",
                "supports_filtering": True
            },
            {
                "format": "pdf",
                "description": "Filtered PDF report",
                "supports_filtering": True
            }
        ],
        "available_filters": [
            "date_range",
            "event_types",
            "evidence_types",
            "include_evidence",
            "include_metadata",
            "participant_filter",
            "location_filter"
        ]
    }

@router.get("/history/{case_id}")
async def get_export_history(
    case_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get export history for a specific case
    
    Note: This is a placeholder endpoint. In a full implementation,
    export history would be tracked in the database.
    """
    # TODO: Implement export history tracking
    return {
        "case_id": case_id,
        "exports": [],
        "message": "Export history tracking not yet implemented"
    }

@router.post("/forensic/dashboard", response_model=Dict[str, Any])
async def generate_court_presentation_dashboard(
    case_id: str,
    source_ids: Optional[List[str]] = None,
    include_key_statistics: bool = True,
    include_network_graphs: bool = True,
    include_timeline_correlation: bool = True,
    current_user: User = Depends(get_current_user)
):
    """
    Generate court presentation dashboard with key statistics and visual highlights
    
    - **case_id**: UUID of the case to analyze
    - **source_ids**: Optional list of specific forensic source IDs
    - **include_key_statistics**: Whether to include key statistics
    - **include_network_graphs**: Whether to include network graph data
    - **include_timeline_correlation**: Whether to correlate with timeline events
    """
    try:
        export_service = ExportService()
        
        dashboard = await export_service.generate_court_presentation_dashboard(
            case_id=case_id,
            source_ids=source_ids,
            include_key_statistics=include_key_statistics,
            include_network_graphs=include_network_graphs,
            include_timeline_correlation=include_timeline_correlation
        )
        
        logger.info("Court presentation dashboard generated", 
                   case_id=case_id, 
                   user_id=str(current_user.id))
        
        return dashboard
        
    except CaseManagementException as e:
        logger.error("Court presentation dashboard generation failed", 
                    case_id=case_id, 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in court presentation dashboard generation", 
                    case_id=case_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/forensic/statistics", response_model=Dict[str, Any])
async def export_communication_statistics(
    case_id: str,
    source_ids: Optional[List[str]] = None,
    include_sentiment_analysis: bool = True,
    include_participant_breakdown: bool = True,
    current_user: User = Depends(get_current_user)
):
    """
    Export detailed communication statistics report
    
    - **case_id**: UUID of the case to analyze
    - **source_ids**: Optional list of specific forensic source IDs
    - **include_sentiment_analysis**: Whether to include sentiment analysis
    - **include_participant_breakdown**: Whether to include participant breakdown
    """
    try:
        export_service = ExportService()
        
        stats_report = await export_service.export_communication_statistics_report(
            case_id=case_id,
            source_ids=source_ids,
            include_sentiment_analysis=include_sentiment_analysis,
            include_participant_breakdown=include_participant_breakdown
        )
        
        logger.info("Communication statistics report generated", 
                   case_id=case_id, 
                   user_id=str(current_user.id),
                   total_messages=stats_report['communication_metrics']['total_messages'])
        
        return stats_report
        
    except CaseManagementException as e:
        logger.error("Communication statistics report generation failed", 
                    case_id=case_id, 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in communication statistics report generation", 
                    case_id=case_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/forensic/network", response_model=Union[Dict[str, Any], StreamingResponse])
async def export_network_graph_data(
    case_id: str,
    format_type: str = "json",
    source_ids: Optional[List[str]] = None,
    include_metadata: bool = True,
    current_user: User = Depends(get_current_user)
):
    """
    Export communication network graph data for visualization
    
    - **case_id**: UUID of the case to analyze
    - **format_type**: Export format ('json', 'csv')
    - **source_ids**: Optional list of specific forensic source IDs
    - **include_metadata**: Whether to include node/edge metadata
    """
    try:
        export_service = ExportService()
        
        network_data = await export_service.export_network_graph_data(
            case_id=case_id,
            source_ids=source_ids,
            format_type=format_type,
            include_metadata=include_metadata
        )
        
        if format_type.lower() == 'json':
            logger.info("Network graph JSON export completed", 
                       case_id=case_id, 
                       user_id=str(current_user.id),
                       nodes_count=network_data['statistics']['total_nodes'])
            
            return network_data
        else:
            # CSV format - return as streaming response
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            filename = f"network_graph_{case_id[:8]}_{timestamp}.csv"
            
            logger.info("Network graph CSV export completed", 
                       case_id=case_id, 
                       user_id=str(current_user.id),
                       file_size=len(network_data))
            
            return StreamingResponse(
                io.BytesIO(network_data),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
    except CaseManagementException as e:
        logger.error("Network graph export failed", 
                    case_id=case_id, 
                    user_id=str(current_user.id),
                    format_type=format_type,
                    error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in network graph export", 
                    case_id=case_id,
                    format_type=format_type,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
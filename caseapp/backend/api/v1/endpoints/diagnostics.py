"""
Diagnostic and Troubleshooting API endpoints
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
import structlog

from services.diagnostic_service import DiagnosticService
from core.auth import get_current_user
from models.user import User

logger = structlog.get_logger()
router = APIRouter()

# Pydantic models for request/response
class DiagnosticReportRequest(BaseModel):
    """Request model for diagnostic report generation"""
    include_logs: bool = True
    hours_back: int = 24

class TroubleshootingRequest(BaseModel):
    """Request model for guided troubleshooting"""
    issue_category: str
    include_current_status: bool = True

def get_diagnostic_service() -> DiagnosticService:
    """Dependency to get diagnostic service instance"""
    return DiagnosticService()

@router.post("/report", response_model=Dict[str, Any])
async def generate_diagnostic_report(
    request: DiagnosticReportRequest,
    current_user: User = Depends(get_current_user),
    diagnostic_service: DiagnosticService = Depends(get_diagnostic_service)
):
    """
    Generate comprehensive diagnostic report
    
    Args:
        request: Diagnostic report configuration
        
    Returns:
        Comprehensive diagnostic report with issues, recommendations, and troubleshooting workflows
    """
    try:
        logger.info(
            "Generating diagnostic report",
            user_id=current_user.id,
            include_logs=request.include_logs,
            hours_back=request.hours_back
        )
        
        report = await diagnostic_service.generate_diagnostic_report(
            include_logs=request.include_logs,
            hours_back=request.hours_back
        )
        
        if "error" in report:
            raise HTTPException(status_code=500, detail=report["error"])
        
        logger.info(
            "Diagnostic report generated successfully",
            user_id=current_user.id,
            report_id=report.get("report_id"),
            issue_count=len(report.get("issues", []))
        )
        
        return report
        
    except Exception as e:
        logger.error("Failed to generate diagnostic report", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate diagnostic report: {str(e)}")

@router.get("/report/quick", response_model=Dict[str, Any])
async def generate_quick_diagnostic_report(
    hours_back: int = Query(6, description="Hours of data to analyze", ge=1, le=48),
    current_user: User = Depends(get_current_user),
    diagnostic_service: DiagnosticService = Depends(get_diagnostic_service)
):
    """
    Generate quick diagnostic report without detailed log analysis
    
    Args:
        hours_back: Hours of historical data to analyze
        
    Returns:
        Quick diagnostic report focusing on current system status
    """
    try:
        logger.info(
            "Generating quick diagnostic report",
            user_id=current_user.id,
            hours_back=hours_back
        )
        
        report = await diagnostic_service.generate_diagnostic_report(
            include_logs=False,
            hours_back=hours_back
        )
        
        if "error" in report:
            raise HTTPException(status_code=500, detail=report["error"])
        
        # Return simplified report
        quick_report = {
            "report_id": report.get("report_id"),
            "timestamp": report.get("timestamp"),
            "summary": report.get("summary"),
            "issues": report.get("issues", []),
            "recommendations": report.get("recommendations", [])[:10],  # Top 10 recommendations
            "health_score": report.get("health_data", {}).get("health_score", 0)
        }
        
        return quick_report
        
    except Exception as e:
        logger.error("Failed to generate quick diagnostic report", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate quick diagnostic report: {str(e)}")

@router.get("/troubleshooting/{category}", response_model=Dict[str, Any])
async def get_guided_troubleshooting(
    category: str,
    current_user: User = Depends(get_current_user),
    diagnostic_service: DiagnosticService = Depends(get_diagnostic_service)
):
    """
    Get guided troubleshooting steps for a specific issue category
    
    Args:
        category: Issue category (health, performance, deployment, application)
        
    Returns:
        Guided troubleshooting workflow with step-by-step instructions
    """
    try:
        valid_categories = ["health", "performance", "deployment", "application", "general"]
        if category not in valid_categories:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            )
        
        logger.info(
            "Getting guided troubleshooting",
            user_id=current_user.id,
            category=category
        )
        
        result = await diagnostic_service.get_guided_troubleshooting(category)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get guided troubleshooting", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get guided troubleshooting: {str(e)}")

@router.get("/issues/summary", response_model=Dict[str, Any])
async def get_issues_summary(
    current_user: User = Depends(get_current_user),
    diagnostic_service: DiagnosticService = Depends(get_diagnostic_service)
):
    """
    Get summary of current system issues
    
    Returns:
        Summary of detected issues by category and severity
    """
    try:
        logger.info("Getting issues summary", user_id=current_user.id)
        
        # Generate quick report to get current issues
        report = await diagnostic_service.generate_diagnostic_report(
            include_logs=False,
            hours_back=1
        )
        
        if "error" in report:
            raise HTTPException(status_code=500, detail=report["error"])
        
        issues = report.get("issues", [])
        
        # Categorize issues
        issues_by_category = {}
        issues_by_severity = {"critical": 0, "warning": 0, "info": 0}
        
        for issue in issues:
            category = issue.get("category", "unknown")
            severity = issue.get("severity", "info")
            
            if category not in issues_by_category:
                issues_by_category[category] = {"critical": 0, "warning": 0, "info": 0}
            
            issues_by_category[category][severity] += 1
            issues_by_severity[severity] += 1
        
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_issues": len(issues),
            "issues_by_severity": issues_by_severity,
            "issues_by_category": issues_by_category,
            "requires_immediate_attention": issues_by_severity["critical"] > 0,
            "health_score": report.get("health_data", {}).get("health_score", 0),
            "top_issues": issues[:5]  # Top 5 most critical issues
        }
        
        return summary
        
    except Exception as e:
        logger.error("Failed to get issues summary", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get issues summary: {str(e)}")

@router.get("/workflows", response_model=Dict[str, Any])
async def get_troubleshooting_workflows(
    current_user: User = Depends(get_current_user),
    diagnostic_service: DiagnosticService = Depends(get_diagnostic_service)
):
    """
    Get all available troubleshooting workflows
    
    Returns:
        List of available troubleshooting workflows by category
    """
    try:
        logger.info("Getting troubleshooting workflows", user_id=current_user.id)
        
        # Generate report to get current workflows
        report = await diagnostic_service.generate_diagnostic_report(
            include_logs=False,
            hours_back=1
        )
        
        if "error" in report:
            # Return default workflows even if report generation fails
            workflows = {
                "general": diagnostic_service._create_general_workflow(),
                "health": diagnostic_service._create_category_workflow("health", []),
                "performance": diagnostic_service._create_category_workflow("performance", []),
                "deployment": diagnostic_service._create_category_workflow("deployment", []),
                "application": diagnostic_service._create_category_workflow("application", [])
            }
        else:
            workflows = report.get("troubleshooting_workflows", {})
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "available_workflows": list(workflows.keys()),
            "workflows": workflows
        }
        
    except Exception as e:
        logger.error("Failed to get troubleshooting workflows", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get troubleshooting workflows: {str(e)}")

@router.get("/recommendations", response_model=Dict[str, Any])
async def get_diagnostic_recommendations(
    priority_filter: Optional[str] = Query(None, description="Filter by priority: critical, warning, info"),
    category_filter: Optional[str] = Query(None, description="Filter by category: health, performance, deployment, application"),
    limit: int = Query(20, description="Maximum number of recommendations", ge=1, le=100),
    current_user: User = Depends(get_current_user),
    diagnostic_service: DiagnosticService = Depends(get_diagnostic_service)
):
    """
    Get prioritized diagnostic recommendations
    
    Args:
        priority_filter: Filter recommendations by priority level
        category_filter: Filter recommendations by issue category
        limit: Maximum number of recommendations to return
        
    Returns:
        Prioritized list of diagnostic recommendations
    """
    try:
        logger.info(
            "Getting diagnostic recommendations",
            user_id=current_user.id,
            priority_filter=priority_filter,
            category_filter=category_filter,
            limit=limit
        )
        
        # Generate report to get recommendations
        report = await diagnostic_service.generate_diagnostic_report(
            include_logs=False,
            hours_back=6
        )
        
        if "error" in report:
            raise HTTPException(status_code=500, detail=report["error"])
        
        recommendations = report.get("recommendations", [])
        
        # Apply filters
        if priority_filter:
            recommendations = [r for r in recommendations if r.get("severity") == priority_filter]
        
        if category_filter:
            recommendations = [r for r in recommendations if r.get("category") == category_filter]
        
        # Apply limit
        recommendations = recommendations[:limit]
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_recommendations": len(recommendations),
            "filters_applied": {
                "priority": priority_filter,
                "category": category_filter,
                "limit": limit
            },
            "recommendations": recommendations
        }
        
    except Exception as e:
        logger.error("Failed to get diagnostic recommendations", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get diagnostic recommendations: {str(e)}")

@router.get("/system/info", response_model=Dict[str, Any])
async def get_system_information(
    current_user: User = Depends(get_current_user),
    diagnostic_service: DiagnosticService = Depends(get_diagnostic_service)
):
    """
    Get comprehensive system information for diagnostics
    
    Returns:
        Detailed system information including platform, resources, and configuration
    """
    try:
        logger.info("Getting system information", user_id=current_user.id)
        
        system_info = await diagnostic_service._collect_system_information()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system_info": system_info
        }
        
    except Exception as e:
        logger.error("Failed to get system information", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get system information: {str(e)}")

@router.get("/logs/analysis", response_model=Dict[str, Any])
async def get_log_analysis(
    hours_back: int = Query(24, description="Hours of logs to analyze", ge=1, le=168),
    current_user: User = Depends(get_current_user),
    diagnostic_service: DiagnosticService = Depends(get_diagnostic_service)
):
    """
    Get application log analysis for troubleshooting
    
    Args:
        hours_back: Hours of historical logs to analyze
        
    Returns:
        Log analysis with error patterns and recommendations
    """
    try:
        logger.info(
            "Getting log analysis",
            user_id=current_user.id,
            hours_back=hours_back
        )
        
        log_analysis = await diagnostic_service._analyze_application_logs(hours_back)
        
        if "error" in log_analysis:
            raise HTTPException(status_code=500, detail=log_analysis["error"])
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "log_analysis": log_analysis
        }
        
    except Exception as e:
        logger.error("Failed to get log analysis", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get log analysis: {str(e)}")
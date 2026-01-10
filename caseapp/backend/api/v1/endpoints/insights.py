"""
AI insights endpoints - placeholder
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any

from core.auth import get_current_user
from schemas.base import BaseResponse

router = APIRouter()

@router.get("/case/{case_id}")
async def get_case_insights(case_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get case insights - placeholder"""
    return BaseResponse(message="Case insights endpoint - to be implemented")
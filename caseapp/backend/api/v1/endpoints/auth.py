"""
Authentication endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from typing import Dict, Any

from core.auth import AuthService, get_current_user
from schemas.base import BaseResponse

router = APIRouter()
security = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseResponse):
    access_token: str
    token_type: str = "bearer"
    user_info: Dict[str, Any]

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """User login endpoint"""
    # TODO: Implement actual user authentication
    # For now, return a mock token
    token = AuthService.create_access_token(
        data={"sub": "user123", "roles": ["attorney"]}
    )
    
    return LoginResponse(
        access_token=token,
        user_info={"id": "user123", "username": request.username, "roles": ["attorney"]}
    )

@router.get("/me")
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user information"""
    return BaseResponse(message="User info retrieved", data=current_user)
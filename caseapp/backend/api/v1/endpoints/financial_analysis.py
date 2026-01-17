"""
Financial Analysis API endpoints
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from core.database import get_db
from schemas.financial_analysis import (
    FinancialAccountCreate, FinancialAccountResponse,
    FinancialTransactionCreate, FinancialTransactionResponse,
    FinancialTransactionUpdate, FinancialAlertResponse, FinancialSummary
)
from services.financial_analysis_service import FinancialAnalysisService
from models.financial_analysis import FinancialAccount, FinancialTransaction, FinancialAlert

router = APIRouter()

@router.get("/case/{case_id}/summary", response_model=FinancialSummary)
async def get_financial_summary(
    case_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get summarized financial metrics for a case"""
    service = FinancialAnalysisService(db)
    return await service.get_case_summary(case_id)

@router.post("/case/{case_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def trigger_financial_analysis(
    case_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Trigger automated risk analysis for all case transactions"""
    service = FinancialAnalysisService(db)
    await service.run_analysis(case_id)
    return {"message": "Analysis triggered successfully"}

@router.get("/case/{case_id}/accounts", response_model=List[FinancialAccountResponse])
async def list_accounts(
    case_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """List all financial accounts associated with a case"""
    service = FinancialAnalysisService(db)
    return await service.get_accounts(case_id)

@router.post("/accounts", response_model=FinancialAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account_in: FinancialAccountCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new financial account record"""
    service = FinancialAnalysisService(db)
    account = await service.create_account(account_in.case_id, account_in.dict())
    await db.commit()
    return account

@router.post("/transactions", response_model=FinancialTransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    tx_in: FinancialTransactionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new financial transaction record"""
    service = FinancialAnalysisService(db)
    tx = await service.create_transaction(tx_in.case_id, tx_in.dict())
    await db.commit()
    return tx

@router.get("/case/{case_id}/transactions", response_model=List[FinancialTransactionResponse])
async def list_transactions(
    case_id: UUID,
    account_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db)
):
    """List financial transactions for a case"""
    service = FinancialAnalysisService(db)
    return await service.get_transactions(case_id, account_id)

@router.put("/transactions/{transaction_id}", response_model=FinancialTransactionResponse)
async def update_transaction(
    transaction_id: UUID,
    tx_data: FinancialTransactionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a financial transaction"""
    service = FinancialAnalysisService(db)
    transaction = await service.update_transaction(transaction_id, tx_data.dict(exclude_unset=True))
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await db.commit()
    return transaction

@router.get("/case/{case_id}/alerts", response_model=List[FinancialAlertResponse])
async def list_alerts(
    case_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """List financial risk alerts for a case"""
    service = FinancialAnalysisService(db)
    return await service.get_alerts(case_id)

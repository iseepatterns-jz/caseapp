"""
Pydantic schemas for financial analysis API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

from models.financial_analysis import TransactionType, AlertSeverity

class FinancialAccountBase(BaseModel):
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    institution_name: Optional[str] = None
    account_type: Optional[str] = None
    currency: str = "USD"
    owner_name: Optional[str] = None
    owner_details: Optional[Dict[str, Any]] = None

class FinancialAccountCreate(FinancialAccountBase):
    case_id: UUID

class FinancialAccountResponse(FinancialAccountBase):
    id: UUID
    case_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class FinancialTransactionBase(BaseModel):
    transaction_date: datetime
    amount: float
    currency: str = "USD"
    transaction_type: TransactionType = TransactionType.OTHER
    description: Optional[str] = None
    counterparty_name: Optional[str] = None
    counterparty_account: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None

class FinancialTransactionCreate(FinancialTransactionBase):
    account_id: UUID
    case_id: UUID
    document_id: Optional[UUID] = None
    forensic_item_id: Optional[UUID] = None

class FinancialTransactionUpdate(BaseModel):
    transaction_date: Optional[datetime] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    transaction_type: Optional[TransactionType] = None
    description: Optional[str] = None
    counterparty_name: Optional[str] = None
    counterparty_account: Optional[str] = None
    is_suspicious: Optional[bool] = None
    risk_score: Optional[float] = None
    tags: Optional[List[str]] = None

class FinancialTransactionResponse(FinancialTransactionBase):
    id: UUID
    account_id: UUID
    case_id: UUID
    document_id: Optional[UUID] = None
    is_suspicious: bool
    risk_score: float
    tags: Optional[List[str]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class FinancialAlertResponse(BaseModel):
    id: UUID
    case_id: UUID
    transaction_id: Optional[UUID] = None
    alert_type: str
    severity: AlertSeverity
    title: str
    description: Optional[str]
    trigger_criteria: Optional[Dict[str, Any]]
    is_acknowledged: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class FinancialSummary(BaseModel):
    """Aggregated financial summary for a case"""
    total_accounts: int
    total_transactions: int
    total_alerts: int
    total_credit: float
    total_debit: float
    net_flow: float
    unaccounted_flows: Optional[float] = None
    high_risk_transactions: int
    top_counterparties: List[Dict[str, Any]]
    timeline_data: List[Dict[str, Any]]

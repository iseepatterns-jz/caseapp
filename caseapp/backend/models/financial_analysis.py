"""
Financial analysis model definitions for detecting suspicious activity
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, Float, ForeignKey, JSON, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any
import uuid

from core.database import Base

class TransactionType(PyEnum):
    """Financial transaction types"""
    CREDIT = "credit"
    DEBIT = "debit"
    TRANSFER = "transfer"
    CASH_DEPOSIT = "cash_deposit"
    CASH_WITHDRAWAL = "cash_withdrawal"
    WIRE_TRANSFER = "wire_transfer"
    CRYPTO_TRANSFER = "crypto_transfer"
    OTHER = "other"

class AlertSeverity(PyEnum):
    """Financial alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class FinancialAccount(Base):
    """Financial account model (Bank, Wallet, etc.)"""
    __tablename__ = "financial_accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    
    account_number = Column(String(100), index=True)
    account_name = Column(String(200))
    institution_name = Column(String(200))
    account_type = Column(String(50))  # Checking, Savings, Credit, Crypto, etc.
    currency = Column(String(10), default="USD")
    
    # Metadata and owner info
    owner_name = Column(String(200))
    owner_details = Column(JSON)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    case = relationship("Case")
    transactions = relationship("FinancialTransaction", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<FinancialAccount(id={self.id}, number='{self.account_number}', institution='{self.institution_name}')>"

class FinancialTransaction(Base):
    """Financial transaction model"""
    __tablename__ = "financial_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("financial_accounts.id"), nullable=False, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    
    # Source document or forensic item (if extracted)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    forensic_item_id = Column(UUID(as_uuid=True)) # Link to forensic items if applicable
    
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    transaction_type = Column(Enum(TransactionType), default=TransactionType.OTHER)
    
    description = Column(Text)
    counterparty_name = Column(String(200))
    counterparty_account = Column(String(100))
    
    # Analysis fields
    is_suspicious = Column(Boolean, default=False)
    risk_score = Column(Float, default=0.0)  # 0.0 to 1.0
    tags = Column(JSON)  # High-value, structure, tax-avoidance, etc.
    
    # Extended data
    metadata_json = Column(JSON)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    account = relationship("FinancialAccount", back_populates="transactions")
    case = relationship("Case")
    document = relationship("Document")
    alerts = relationship("FinancialAlert", back_populates="transaction")
    
    def __repr__(self):
        return f"<FinancialTransaction(id={self.id}, amount={self.amount}, date='{self.transaction_date}')>"

class FinancialAlert(Base):
    """Financial analysis alert model"""
    __tablename__ = "financial_alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("financial_transactions.id"))
    
    alert_type = Column(String(50), nullable=False)  # structuring, rapid_succession, unusual_volume, etc.
    severity = Column(Enum(AlertSeverity), default=AlertSeverity.MEDIUM)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Detection details
    trigger_criteria = Column(JSON)
    detected_patterns = Column(JSON)
    
    # Status
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    acknowledged_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    case = relationship("Case")
    transaction = relationship("FinancialTransaction", back_populates="alerts")
    
    def __repr__(self):
        return f"<FinancialAlert(id={self.id}, type='{self.alert_type}', severity='{self.severity}')>"

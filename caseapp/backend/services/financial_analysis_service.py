"""
Financial analysis service for detecting suspicious financial activity
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta, UTC
import structlog
import re

from models.financial_analysis import FinancialAccount, FinancialTransaction, FinancialAlert, TransactionType, AlertSeverity
from core.exceptions import CaseManagementException

logger = structlog.get_logger()

class FinancialAnalysisService:
    """Service for analyzing financial transactions and detecting patterns"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_case_summary(self, case_id: UUID) -> Dict[str, Any]:
        """Get aggregated financial summary for a case"""
        try:
            # Get basic counts
            account_count_res = await self.db.execute(
                select(func.count(FinancialAccount.id)).where(FinancialAccount.case_id == case_id)
            )
            total_accounts = account_count_res.scalar()
            
            transaction_count_res = await self.db.execute(
                select(func.count(FinancialTransaction.id)).where(FinancialTransaction.case_id == case_id)
            )
            total_transactions = transaction_count_res.scalar()
            
            alert_count_res = await self.db.execute(
                select(func.count(FinancialAlert.id)).where(FinancialAlert.case_id == case_id)
            )
            total_alerts = alert_count_res.scalar()
            
            # Sum amounts
            credit_res = await self.db.execute(
                select(func.sum(FinancialTransaction.amount))
                .where(and_(FinancialTransaction.case_id == case_id, FinancialTransaction.transaction_type == TransactionType.CREDIT))
            )
            total_credit = credit_res.scalar() or 0.0
            
            debit_res = await self.db.execute(
                select(func.sum(FinancialTransaction.amount))
                .where(and_(FinancialTransaction.case_id == case_id, FinancialTransaction.transaction_type == TransactionType.DEBIT))
            )
            total_debit = debit_res.scalar() or 0.0
            
            # Top counterparties
            counterparty_res = await self.db.execute(
                select(FinancialTransaction.counterparty_name, func.sum(FinancialTransaction.amount).label("total_amount"))
                .where(FinancialTransaction.case_id == case_id)
                .group_by(FinancialTransaction.counterparty_name)
                .order_by(desc("total_amount"))
                .limit(5)
            )
            top_counterparties = [
                {"name": name or "Unknown", "amount": amount} 
                for name, amount in counterparty_res.all()
            ]
            
            # Timeline data (last 30 days)
            thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
            timeline_res = await self.db.execute(
                select(func.date(FinancialTransaction.transaction_date).label("date"), func.sum(FinancialTransaction.amount).label("total"))
                .where(and_(FinancialTransaction.case_id == case_id, FinancialTransaction.transaction_date >= thirty_days_ago))
                .group_by(func.date(FinancialTransaction.transaction_date))
                .order_by("date")
            )
            # High risk transactions
            high_risk_res = await self.db.execute(
                select(func.count(FinancialTransaction.id))
                .where(and_(FinancialTransaction.case_id == case_id, FinancialTransaction.risk_score >= 0.7))
            )
            high_risk_count = high_risk_res.scalar() or 0
            
            timeline_data = [
                {"date": str(row.date), "amount": row.total}
                for row in timeline_res.all()
            ]
            
            return {
                "total_accounts": total_accounts,
                "total_transactions": total_transactions,
                "total_alerts": total_alerts,
                "total_credit": total_credit,
                "total_debit": total_debit,
                "net_flow": total_credit - total_debit,
                "unaccounted_flows": 0.0, # Placeholder
                "high_risk_transactions": high_risk_count,
                "top_counterparties": top_counterparties,
                "timeline_data": timeline_data,
                "generated_at": datetime.now(UTC).isoformat()
            }
        except Exception as e:
            logger.error("Failed to get financial summary", case_id=str(case_id), error=str(e))
            raise CaseManagementException(f"Failed to get financial summary: {str(e)}")

    async def run_analysis(self, case_id: UUID):
        """Run automated analysis on all transactions for a case"""
        try:
            # Get all transactions for the case
            result = await self.db.execute(
                select(FinancialTransaction).where(FinancialTransaction.case_id == case_id).order_by(FinancialTransaction.transaction_date)
            )
            transactions = list(result.scalars().all())
            
            if not transactions:
                return
            
            # 1. Detect High-Value Transactions
            await self._detect_high_value_transactions(case_id, transactions)
            
            # 2. Detect Structuring / Rapid Succession
            await self._detect_structuring(case_id, transactions)
            
            # 3. Detect Unusual Concentration (Top Recipients)
            await self._detect_unusual_concentration(case_id, transactions)
            
            await self.db.commit()
            logger.info("Financial analysis completed", case_id=str(case_id), transaction_count=len(transactions))
            
        except Exception as e:
            logger.error("Financial analysis failed", case_id=str(case_id), error=str(e))
            await self.db.rollback()
            raise CaseManagementException(f"Financial analysis failed: {str(e)}")

    async def _detect_high_value_transactions(self, case_id: UUID, transactions: List[FinancialTransaction]):
        """Flag transactions above a certain threshold (e.g., $10,000)"""
        THRESHOLD = 10000.0
        for tx in transactions:
            if tx.amount >= THRESHOLD:
                tx.is_suspicious = True
                tx.risk_score = max(tx.risk_score, 0.6)
                
                # Check if alert already exists
                alert_exists = await self.db.execute(
                    select(FinancialAlert).where(and_(FinancialAlert.transaction_id == tx.id, FinancialAlert.alert_type == "high_value"))
                )
                if not alert_exists.scalar_one_or_none():
                    alert = FinancialAlert(
                        case_id=case_id,
                        transaction_id=tx.id,
                        alert_type="high_value",
                        severity=AlertSeverity.MEDIUM,
                        title="High-Value Transaction",
                        description=f"Transaction of {tx.amount} {tx.currency} exceeds reporting threshold.",
                        trigger_criteria={"threshold": THRESHOLD}
                    )
                    self.db.add(alert)

    async def _detect_structuring(self, case_id: UUID, transactions: List[FinancialTransaction]):
        """Detect rapid succession of smaller transactions just below threshold (e.g. $9,000-$9,999)"""
        # Simple implementation: 3+ transactions to same counterparty within 48h totalling > $10k
        for i in range(len(transactions)):
            tx_a = transactions[i]
            if tx_a.transaction_type != TransactionType.DEBIT and tx_a.transaction_type != TransactionType.CREDIT:
                continue
                
            sequence = [tx_a]
            for j in range(i + 1, len(transactions)):
                tx_b = transactions[j]
                if tx_b.counterparty_account == tx_a.counterparty_account and \
                   (tx_b.transaction_date - tx_a.transaction_date).total_seconds() <= 172800: # 48h
                    sequence.append(tx_b)
            
            if len(sequence) >= 3:
                total_amount = sum(s.amount for s in sequence)
                if total_amount >= 10000.0:
                    for s in sequence:
                        s.is_suspicious = True
                        s.risk_score = max(s.risk_score, 0.8)
                    
                    alert = FinancialAlert(
                        case_id=case_id,
                        alert_type="structuring",
                        severity=AlertSeverity.HIGH,
                        title="Potential Structuring Detected",
                        description=f"Sequence of {len(sequence)} transactions totalling {total_amount} detected within 48h to same counterparty.",
                        trigger_criteria={"item_count": len(sequence), "total_amount": total_amount}
                    )
                    self.db.add(alert)
                    # Skip processed sequence items to avoid double alerts
                    i += len(sequence) - 1

    async def _detect_unusual_concentration(self, case_id: UUID, transactions: List[FinancialTransaction]):
        """Detect if a single counterparty receives more than 50% of total outflows"""
        try:
            debits = [tx for tx in transactions if tx.transaction_type == TransactionType.DEBIT]
            if not debits:
                return
                
            total_outflow = sum(tx.amount for tx in debits)
            if total_outflow == 0:
                return
                
            concentration: Dict[str, float] = {}
            for tx in debits:
                if tx.counterparty_account:
                    concentration[tx.counterparty_account] = concentration.get(tx.counterparty_account, 0) + tx.amount
            
            for counterparty, amount in concentration.items():
                percentage = (amount / total_outflow) * 100
                if percentage >= 50.0:
                    # Flag transactions for this counterparty
                    for tx in debits:
                        if tx.counterparty_account == counterparty:
                            tx.is_suspicious = True
                            tx.risk_score = max(tx.risk_score, 0.7)
                    
                    # Create alert
                    alert = FinancialAlert(
                        case_id=case_id,
                        alert_type="concentration",
                        severity=AlertSeverity.MEDIUM,
                        title="Unusual Concentration of Funds",
                        description=f"Counterparty {counterparty} received {percentage:.1f}% of total outflows (${amount:,.2f} of ${total_outflow:,.2f}).",
                        trigger_criteria={"counterparty": counterparty, "percentage": percentage, "amount": amount}
                    )
                    self.db.add(alert)
                    
        except Exception as e:
            logger.error("Concentration detection failed", case_id=str(case_id), error=str(e))

    async def ingest_from_text(self, case_id: UUID, text: str, document_id: Optional[UUID] = None):
        """Extract transactions from raw text patterns (OCR/Forensic)"""
        # Common bank statement patterns
        # Example: 01/15/2024 DEBIT AMAZON.COM $125.50
        patterns = [
            # Standard M/D/Y with type and amount
            r'(\d{1,2}/\d{1,2}/\d{2,4})\s+(CREDIT|DEBIT|TRANSFER|CASH_DEPOSIT|CASH_WITHDRAWAL)\s+(.*?)\s+\$?([\d,]+\.\d{2})',
            # ISO Date with description and amount
            r'(\d{4}-\d{2}-\d{2})\s+(.*?)\s+([+-]?[\d,]+\.\d{2})'
        ]
        
        extracted_count = 0
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                try:
                    groups = match.groups()
                    if len(groups) == 4: # Pattern 1
                        date_str, tx_type_str, desc, amount_str = groups
                        tx_type = TransactionType(tx_type_str.lower())
                    elif len(groups) == 3: # Pattern 2
                        date_str, desc, amount_str = groups
                        amount = float(amount_str.replace(',', ''))
                        tx_type = TransactionType.DEBIT if amount < 0 else TransactionType.CREDIT
                        amount = abs(amount)
                    
                    # Parse date
                    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
                        try:
                            date_obj = datetime.strptime(date_str, fmt).replace(tzinfo=UTC)
                            break
                        except ValueError:
                            continue
                    else:
                        continue # Skip if date format unknown
                    
                    amount = float(amount_str.replace(',', ''))
                    
                    # Create transaction
                    transaction = FinancialTransaction(
                        case_id=case_id,
                        transaction_date=date_obj,
                        amount=amount,
                        transaction_type=tx_type,
                        description=desc.strip(),
                        document_id=document_id,
                        is_suspicious=False,
                        risk_score=0.0
                    )
                    self.db.add(transaction)
                    extracted_count += 1
                except Exception as e:
                    logger.error("Failed to parse financial pattern", error=str(e))
                    continue
        
        if extracted_count > 0:
            await self.db.flush()
            logger.info("Ingested transactions from text", case_id=str(case_id), count=extracted_count)
            # Run analysis automatically
            await self.run_analysis(case_id)

    # --- CRUD Operations ---

    async def create_account(self, case_id: UUID, account_data: Dict[str, Any]) -> FinancialAccount:
        """Create a new financial account for a case"""
        account = FinancialAccount(
            case_id=case_id,
            account_number=account_data.get("account_number"),
            account_holder=account_data.get("account_holder"),
            institution_name=account_data.get("institution_name"),
            account_type=account_data.get("account_type"),
            balance=account_data.get("balance", 0.0),
            currency=account_data.get("currency", "USD")
        )
        self.db.add(account)
        await self.db.flush()
        return account

    async def get_accounts(self, case_id: UUID) -> List[FinancialAccount]:
        """Get all accounts for a case"""
        result = await self.db.execute(
            select(FinancialAccount).where(FinancialAccount.case_id == case_id)
        )
        return list(result.scalars().all())

    async def create_transaction(self, case_id: UUID, tx_data: Dict[str, Any]) -> FinancialTransaction:
        """Create a new financial transaction"""
        transaction = FinancialTransaction(
            case_id=case_id,
            account_id=tx_data.get("account_id"),
            transaction_date=tx_data.get("transaction_date", datetime.now(UTC)),
            amount=tx_data.get("amount"),
            currency=tx_data.get("currency", "USD"),
            transaction_type=tx_data.get("transaction_type"),
            description=tx_data.get("description"),
            counterparty_account=tx_data.get("counterparty_account"),
            counterparty_name=tx_data.get("counterparty_name"),
            category=tx_data.get("category"),
            reference_number=tx_data.get("reference_number")
        )
        self.db.add(transaction)
        await self.db.flush()
        return transaction

    async def get_transactions(self, case_id: UUID, account_id: Optional[UUID] = None) -> List[FinancialTransaction]:
        """Get transactions for a case, optionally filtered by account"""
        query = select(FinancialTransaction).where(FinancialTransaction.case_id == case_id)
        if account_id:
            query = query.where(FinancialTransaction.account_id == account_id)
        
        result = await self.db.execute(query.order_by(desc(FinancialTransaction.transaction_date)))
        return list(result.scalars().all())

    async def update_transaction(self, transaction_id: UUID, update_data: Dict[str, Any]) -> Optional[FinancialTransaction]:
        """Update a financial transaction"""
        result = await self.db.execute(
            select(FinancialTransaction).where(FinancialTransaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            return None
            
        for key, value in update_data.items():
            if hasattr(transaction, key) and value is not None:
                setattr(transaction, key, value)
        
        await self.db.flush()
        return transaction

    async def get_alerts(self, case_id: UUID) -> List[FinancialAlert]:
        """Get all financial alerts for a case"""
        result = await self.db.execute(
            select(FinancialAlert)
            .where(FinancialAlert.case_id == case_id)
            .order_by(desc(FinancialAlert.created_at))
        )
        return list(result.scalars().all())

# Financial Forensic Analysis Feature Documentation

## Overview
The Financial Forensic Analysis feature provides legal professionals with automated tools to ingest, analyze, and visualize complex financial data within the Court Case Management System. It aims to identify risk patterns such as money laundering indicators, unusual concentration, and large scale cash movements.

## Technical Architecture

### Backend Services
- **`FinancialAnalysisService`**: 
    - Located at `backend/services/financial_analysis_service.py`.
    - Responsible for transaction aggregation, alert generation, and risk scoring.
    - Uses Pydantic schemas for data validation.
- **Data Models**:
    - `FinancialAccount`: Represents bank accounts, crypto wallets, or credit lines.
    - `FinancialTransaction`: Individual ledger entries with amount, type (Credit/Debit), and category.
    - `FinancialAlert`: System-generated flags based on predefined risk rules.

### Risk Detection Engine
The service automatically evaluates every transaction against the following rules:
1. **Structuring Detection**: Identifies multiple small cash transactions that appear designed to avoid reporting thresholds.
2. **Large Cash Movement**: Flags cash withdrawals or deposits exceeding $10,000.
3. **Unusual Concentration**: Detects when a disproportionate amount of funds flows to a single counterparty.
4. **Rapid Depletion**: Detects accounts where funds are withdrawn immediately after deposit.

### Frontend Implementation
- **Component**: `FinancialAnalysis.tsx`
- **Location**: `frontend/src/pages/FinancialAnalysis.tsx`
- **Design System**: 
    - Glassmorphism aesthetic.
    - Real-time data fetching using React Hooks.
    - Interactive metrics cards for "Total Risk Alerts" and "Net Cash Flow".
    - Filterable transaction history.

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/cases/{case_id}/financial/summary` | Returns high-level financial metrics. |
| GET | `/api/v1/cases/{case_id}/financial/transactions` | List all transactions with optional filtering. |
| GET | `/api/v1/cases/{case_id}/financial/alerts` | List all risk alerts for the case. |
| POST | `/api/v1/cases/{case_id}/financial/ingest` | Ingest raw text or CSV summaries for processing. |

## Future Roadmap
- integration with Plaid for real-time bank feed ingestion.
- Advanced relationship graphing for complex money laundering networks.
- Predictive budgeting and cash flow forecasting for legal fee planning.

"""Add financial analysis and update audit logs

Revision ID: 0f087aba17ae
Revises: 
Create Date: 2026-01-17 00:43:26.754987

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0f087aba17ae'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create Enums
    transaction_type = postgresql.ENUM('CREDIT', 'DEBIT', 'TRANSFER', 'CASH_DEPOSIT', 'CASH_WITHDRAWAL', 'WIRE_TRANSFER', 'CRYPTO_TRANSFER', 'OTHER', name='transactiontype')
    transaction_type.create(op.get_bind())
    
    alert_severity = postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='alertseverity')
    alert_severity.create(op.get_bind())

    # Update audit_logs table
    op.add_column('audit_logs', sa.Column('entity_name', sa.String(length=200), nullable=True))

    # Create financial_accounts table
    op.create_table(
        'financial_accounts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('case_id', sa.UUID(), nullable=False),
        sa.Column('account_number', sa.String(length=100), nullable=True),
        sa.Column('account_name', sa.String(length=200), nullable=True),
        sa.Column('institution_name', sa.String(length=200), nullable=True),
        sa.Column('account_type', sa.String(length=50), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('owner_name', sa.String(length=200), nullable=True),
        sa.Column('owner_details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_financial_accounts_account_number'), 'financial_accounts', ['account_number'], unique=False)
    op.create_index(op.f('ix_financial_accounts_case_id'), 'financial_accounts', ['case_id'], unique=False)
    op.create_index(op.f('ix_financial_accounts_id'), 'financial_accounts', ['id'], unique=False)

    # Create financial_transactions table
    op.create_table(
        'financial_transactions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('account_id', sa.UUID(), nullable=False),
        sa.Column('case_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('forensic_item_id', sa.UUID(), nullable=True),
        sa.Column('transaction_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('transaction_type', transaction_type, nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('counterparty_name', sa.String(length=200), nullable=True),
        sa.Column('counterparty_account', sa.String(length=100), nullable=True),
        sa.Column('is_suspicious', sa.Boolean(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['financial_accounts.id'], ),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_financial_transactions_account_id'), 'financial_transactions', ['account_id'], unique=False)
    op.create_index(op.f('ix_financial_transactions_case_id'), 'financial_transactions', ['case_id'], unique=False)
    op.create_index(op.f('ix_financial_transactions_id'), 'financial_transactions', ['id'], unique=False)

    # Create financial_alerts table
    op.create_table(
        'financial_alerts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('case_id', sa.UUID(), nullable=False),
        sa.Column('transaction_id', sa.UUID(), nullable=True),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', alert_severity, nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trigger_criteria', sa.JSON(), nullable=True),
        sa.Column('detected_patterns', sa.JSON(), nullable=True),
        sa.Column('is_acknowledged', sa.Boolean(), nullable=True),
        sa.Column('acknowledged_by', sa.UUID(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['acknowledged_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.ForeignKeyConstraint(['transaction_id'], ['financial_transactions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_financial_alerts_case_id'), 'financial_alerts', ['case_id'], unique=False)
    op.create_index(op.f('ix_financial_alerts_id'), 'financial_alerts', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_financial_alerts_id'), table_name='financial_alerts')
    op.drop_index(op.f('ix_financial_alerts_case_id'), table_name='financial_alerts')
    op.drop_table('financial_alerts')
    
    op.drop_index(op.f('ix_financial_transactions_id'), table_name='financial_transactions')
    op.drop_index(op.f('ix_financial_transactions_case_id'), table_name='financial_transactions')
    op.drop_index(op.f('ix_financial_transactions_account_id'), table_name='financial_transactions')
    op.drop_table('financial_transactions')
    
    op.drop_index(op.f('ix_financial_accounts_id'), table_name='financial_accounts')
    op.drop_index(op.f('ix_financial_accounts_case_id'), table_name='financial_accounts')
    op.drop_index(op.f('ix_financial_accounts_account_number'), table_name='financial_accounts')
    op.drop_table('financial_accounts')
    
    op.drop_column('audit_logs', 'entity_name')
    
    op.execute('DROP TYPE alertseverity')
    op.execute('DROP TYPE transactiontype')
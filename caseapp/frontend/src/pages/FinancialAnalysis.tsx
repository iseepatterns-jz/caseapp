import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { 
    TrendingUp, 
    AlertTriangle, 
    ArrowUpRight, 
    ArrowDownRight,
    Search,
    Filter
} from 'lucide-react';
import { motion } from 'framer-motion';

interface FinancialSummary {
    total_accounts: number;
    total_transactions: number;
    total_alerts: number;
    total_credit: number;
    total_debit: number;
    net_flow: number;
    unaccounted_flows?: number;
    high_risk_transactions: number;
    top_counterparties: Record<string, unknown>[];
    timeline_data: Record<string, unknown>[];
}

interface FinancialTransaction {
    id: string;
    transaction_date: string;
    amount: number;
    transaction_type: string;
    description: string;
    is_suspicious: boolean;
    risk_score: number;
}

interface FinancialAlert {
    id: string;
    title: string;
    description: string;
    severity: string;
    created_at: string;
}

export const FinancialAnalysis: React.FC = () => {
    const { id: caseId } = useParams<{ id: string }>();
    const [loading, setLoading] = useState(true);
    const [summary, setSummary] = useState<FinancialSummary | null>(null);
    const [transactions, setTransactions] = useState<FinancialTransaction[]>([]);
    const [alerts, setAlerts] = useState<FinancialAlert[]>([]);

    useEffect(() => {
        // Fetch financial data from backend
        const fetchData = async () => {
            try {
                const [summaryRes, transactionsRes, alertsRes] = await Promise.all([
                    fetch(`http://localhost:8000/api/v1/financial/case/${caseId}/summary`),
                    fetch(`http://localhost:8000/api/v1/financial/case/${caseId}/transactions`),
                    fetch(`http://localhost:8000/api/v1/financial/case/${caseId}/alerts`)
                ]);

                if (summaryRes.ok) setSummary(await summaryRes.json());
                if (transactionsRes.ok) setTransactions(await transactionsRes.json());
                if (alertsRes.ok) setAlerts(await alertsRes.json());
                
                setLoading(false);
            } catch (error) {
                console.error("Failed to fetch financial data", error);
                setLoading(false);
            }
        };
        fetchData();
    }, [caseId]);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500"></div>
            </div>
        );
    }

    return (
        <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
            <header style={{ marginBottom: '32px' }}>
                <h1 className="gradient-text" style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '8px' }}>
                    Financial Forensic Analysis
                </h1>
                <p style={{ color: 'var(--text-secondary)' }}>
                    Advanced transaction tracking and pattern detection for Case {caseId}
                </p>
            </header>

            {/* Metrics Overview */}
            <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', 
                gap: '20px', 
                marginBottom: '32px' 
            }}>
                <MetricCard 
                    title="Total Inflow" 
                    value={`$${summary?.total_credit.toLocaleString() ?? '0'}`} 
                    icon={ArrowUpRight} 
                    trend="+12% from last month"
                    color="var(--accent-primary)"
                />
                 <MetricCard 
                    title="Total Outflow" 
                    value={`$${summary?.total_debit.toLocaleString() ?? '0'}`} 
                    icon={ArrowDownRight} 
                    trend="-5% from last month"
                    color="var(--accent-secondary)"
                />
                 <MetricCard 
                    title="Suspicious Activity" 
                    value={summary?.high_risk_transactions.toString() ?? '0'} 
                    icon={AlertTriangle} 
                    trend="Requires Review"
                    color="#ff9800"
                />
                 <MetricCard 
                    title="Net Flow" 
                    value={`$${summary?.net_flow.toLocaleString() ?? '0'}`} 
                    icon={TrendingUp} 
                    trend="Healthy Ratio"
                    color="#4caf50"
                />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '32px' }}>
                {/* Transaction Table */}
                <div className="glass-panel" style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                        <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Recent Transactions</h3>
                        <div style={{ display: 'flex', gap: '12px' }}>
                            <div className="glass-card" style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <Search size={16} />
                                <input type="text" placeholder="Search..." style={{ background: 'none', border: 'none', color: 'inherit', outline: 'none', fontSize: '0.875rem' }} />
                            </div>
                            <button className="glass-card" style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                <Filter size={16} />
                                <span>Filter</span>
                            </button>
                        </div>
                    </div>

                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                                <th style={{ padding: '12px' }}>Date</th>
                                <th style={{ padding: '12px' }}>Description</th>
                                <th style={{ padding: '12px' }}>Type</th>
                                <th style={{ padding: '12px', textAlign: 'right' }}>Amount</th>
                                <th style={{ padding: '12px' }}>Risk</th>
                            </tr>
                        </thead>
                        <tbody>
                            {transactions.map((tx) => (
                                <TransactionRow 
                                    key={tx.id}
                                    date={new Date(tx.transaction_date).toLocaleDateString()} 
                                    desc={tx.description} 
                                    type={tx.transaction_type} 
                                    amount={`${tx.amount > 0 ? '+' : ''}${tx.amount.toLocaleString()}`} 
                                    risk={tx.is_suspicious ? 'High' : (tx.risk_score > 50 ? 'Medium' : 'Low')} 
                                />
                            ))}
                            {transactions.length === 0 && (
                                <tr>
                                    <td colSpan={5} style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                                        No transactions found for this case.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Alerts Section */}
                <div className="glass-panel" style={{ padding: '24px' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '24px' }}>Risk Alerts</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        {alerts.map((alert) => (
                            <AlertItem 
                                key={alert.id}
                                title={alert.title} 
                                desc={alert.description}
                                severity={alert.severity}
                            />
                        ))}
                        {alerts.length === 0 && (
                            <div style={{ padding: '12px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                                No risk alerts detected.
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

interface MetricCardProps {
    title: string;
    value: string;
    icon: React.ElementType;
    trend: string;
    color: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, icon: Icon, trend, color }) => (
    <motion.div 
        whileHover={{ translateY: -4 }}
        className="glass-panel" 
        style={{ padding: '20px', borderLeft: `4px solid ${color}` }}
    >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>{title}</span>
            <Icon size={20} color={color} />
        </div>
        <div style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '4px' }}>{value}</div>
        <div style={{ fontSize: '0.75rem', color: color }}>{trend}</div>
    </motion.div>
);

interface TransactionRowProps {
    date: string;
    desc: string;
    type: string;
    amount: string;
    risk: string;
}

const TransactionRow: React.FC<TransactionRowProps> = ({ date, desc, type, amount, risk }) => (
    <tr style={{ borderBottom: '1px solid var(--border-subtle)', fontSize: '0.875rem' }}>
        <td style={{ padding: '12px', color: 'var(--text-secondary)' }}>{date}</td>
        <td style={{ padding: '12px', fontWeight: 500 }}>{desc}</td>
        <td style={{ padding: '12px' }}>
            <span style={{ 
                padding: '4px 8px', 
                borderRadius: '4px', 
                fontSize: '0.75rem', 
                background: type === 'CREDIT' ? 'rgba(76, 175, 80, 0.1)' : 'rgba(244, 67, 54, 0.1)',
                color: type === 'CREDIT' ? '#4caf50' : '#f44336'
            }}>{type}</span>
        </td>
        <td style={{ padding: '12px', textAlign: 'right', fontWeight: 600 }}>{amount}</td>
        <td style={{ padding: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <div style={{ 
                    width: '8px', 
                    height: '8px', 
                    borderRadius: '50%', 
                    backgroundColor: risk === 'High' ? '#f44336' : (risk === 'Medium' ? '#ff9800' : '#4caf50')
                }} />
                {risk}
            </div>
        </td>
    </tr>
);

interface AlertItemProps {
    title: string;
    desc: string;
    severity: string;
}

const AlertItem: React.FC<AlertItemProps> = ({ title, desc, severity }) => (
    <div className="glass-card" style={{ padding: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <AlertTriangle size={14} color={severity === 'CRITICAL' ? '#f44336' : (severity === 'HIGH' ? '#ff9800' : '#2196f3')} />
            <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{title}</span>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{desc}</p>
    </div>
);


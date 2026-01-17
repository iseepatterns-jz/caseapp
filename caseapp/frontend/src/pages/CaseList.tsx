import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Search, Plus, Filter, MoreVertical, ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { caseService } from '../services/api';

export const CaseList: React.FC = () => {
    const navigate = useNavigate();
    const [cases, setCases] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchCases = async () => {
            try {
                const response = await caseService.getAll();
                setCases(Array.isArray(response.data) ? response.data : []);
            } catch (error) {
                console.error('Failed to fetch cases:', error);
                // Fallback for demonstration if API fails or returns mock data
                setCases([
                    { id: '1', case_number: 'CR-2024-001', title: 'State v. Peterson', status: 'Active', priority: 'High', date: '2024-03-12' },
                    { id: '2', case_number: 'CV-2024-042', title: 'TechCorp v. Innovation Inc', status: 'Discovery', priority: 'Medium', date: '2024-03-15' },
                    { id: '3', case_number: 'CR-2023-892', title: 'People v. Rodriguez', status: 'Hearing', priority: 'High', date: '2024-04-01' },
                    { id: '4', case_number: 'CV-2023-115', title: 'Estate of Miller', status: 'Closed', priority: 'Low', date: '2024-02-10' },
                ]);
            } finally {
                setLoading(false);
            }
        };
        fetchCases();
    }, []);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                <div>
                    <h1 className="gradient-text" style={{ fontSize: '2rem', marginBottom: '8px' }}>Case Management</h1>
                    <p style={{ color: 'var(--text-secondary)' }}>Manage and track all legal proceedings and forensic records.</p>
                </div>
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    style={{
                        background: 'var(--accent-primary)',
                        color: 'white',
                        border: 'none',
                        padding: '12px 24px',
                        borderRadius: 'var(--radius-md)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        cursor: 'pointer',
                        fontWeight: 600
                    }}
                >
                    <Plus size={20} />
                    New Case
                </motion.button>
            </header>

            <div style={{ display: 'flex', gap: '16px' }}>
                <div className="glass-panel" style={{ flex: 1, padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Search size={20} style={{ color: 'var(--text-muted)' }} />
                    <input
                        type="text"
                        placeholder="Search cases by number, title, or judge..."
                        style={{
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--text-primary)',
                            width: '100%',
                            outline: 'none',
                            padding: '8px 0'
                        }}
                    />
                </div>
                <button className="glass-panel" style={{ padding: '0 16px', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                    <Filter size={18} />
                    Filters
                </button>
            </div>

            <div className="glass-panel" style={{ overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                            <th style={{ padding: '20px 24px' }}>Case Details</th>
                            <th style={{ padding: '20px 24px' }}>Status</th>
                            <th style={{ padding: '20px 24px' }}>Priority</th>
                            <th style={{ padding: '20px 24px' }}>Financial Risk</th>
                            <th style={{ padding: '20px 24px' }}>Next Hearing</th>
                            <th style={{ padding: '20px 24px' }}></th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr><td colSpan={5} style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading records...</td></tr>
                        ) : cases.map((item) => (
                            <tr
                                key={item.id}
                                className="glass-card"
                                onClick={() => navigate(`/cases/${item.id}`)}
                                style={{
                                    borderBottom: '1px solid var(--border-subtle)',
                                    borderRadius: 0,
                                    transition: 'background 0.2s',
                                    cursor: 'pointer'
                                }}
                                onMouseEnter={(e) => {
                                    (e.currentTarget as HTMLElement).style.background = 'var(--bg-tertiary)';
                                }}
                                onMouseLeave={(e) => {
                                    (e.currentTarget as HTMLElement).style.background = 'transparent';
                                }}
                            >
                                <td style={{ padding: '20px 24px' }}>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.title}</span>
                                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{item.case_number}</span>
                                    </div>
                                </td>
                                <td style={{ padding: '20px 24px' }}>
                                    <span style={{
                                        padding: '4px 10px',
                                        background: item.status === 'Active' ? 'hsla(150, 80%, 50%, 0.1)' : 'var(--bg-tertiary)',
                                        color: item.status === 'Active' ? 'hsl(150, 80%, 60%)' : 'var(--text-secondary)',
                                        borderRadius: '20px',
                                        fontSize: '0.75rem',
                                        fontWeight: 600
                                    }}>
                                        {item.status}
                                    </span>
                                </td>
                                <td style={{ padding: '20px 24px' }}>
                                    <span style={{
                                        color: item.priority === 'High' ? 'var(--accent-secondary)' : 'var(--text-secondary)',
                                        fontSize: '0.9rem'
                                    }}>
                                        {item.priority}
                                    </span>
                                </td>
                                <td style={{ padding: '20px 24px' }}>
                                    <span style={{
                                        color: item.financial_risk === 'High' ? 'var(--accent-secondary)' :
                                            item.financial_risk === 'Medium' ? '#ffcc00' : 'var(--text-muted)',
                                        fontSize: '0.9rem',
                                        fontWeight: item.financial_risk === 'High' ? 600 : 400
                                    }}>
                                        {item.financial_risk || 'Low'}
                                    </span>
                                </td>
                                <td style={{ padding: '20px 24px' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                                        {item.date}
                                    </div>
                                </td>
                                <td style={{ padding: '20px 24px', textAlign: 'right' }}>
                                    <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                                        <button style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                                            <ExternalLink size={18} />
                                        </button>
                                        <button style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                                            <MoreVertical size={18} />
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

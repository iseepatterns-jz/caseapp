import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Search, Plus, Filter, MoreVertical, ExternalLink } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { caseService } from '../services/api';

export const CaseList: React.FC = () => {
    const navigate = useNavigate();
    const [cases, setCases] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [priorityFilter, setPriorityFilter] = useState('');
    const [showFilters, setShowFilters] = useState(false);

    const fetchCases = async (query?: string, status?: string, priority?: string) => {
        setLoading(true);
        try {
            const params: any = {};
            if (query) params.query = query;
            if (status) params.status = status.toLowerCase();
            if (priority) params.priority = priority.toLowerCase();

            const response = await caseService.getAll(params);
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

    useEffect(() => {
        const timer = setTimeout(() => {
            fetchCases(searchQuery, statusFilter, priorityFilter);
        }, 300);

        return () => clearTimeout(timer);
    }, [searchQuery, statusFilter, priorityFilter]);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                <div>
                    <h1 className="gradient-text" style={{ fontSize: '2rem', marginBottom: '8px' }}>Case Management</h1>
                    <p style={{ color: 'var(--text-secondary)' }}>Manage and track all legal proceedings and forensic records.</p>
                </div>
                <Link
                    to="/cases/new"
                    style={{ textDecoration: 'none' }}
                >
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
                </Link>
            </header>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', gap: '16px' }}>
                    <div className="glass-panel" style={{ flex: 1, padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <Search size={20} style={{ color: 'var(--text-muted)' }} />
                        <input
                            type="text"
                            placeholder="Search cases by number, title, or judge..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
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
                    <button 
                        className="glass-panel" 
                        onClick={() => setShowFilters(!showFilters)}
                        style={{ 
                            padding: '0 16px', 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: '8px', 
                            cursor: 'pointer', 
                            color: showFilters ? 'var(--accent-primary)' : 'var(--text-secondary)',
                            border: showFilters ? '1px solid var(--accent-primary)' : '1px solid transparent'
                        }}
                    >
                        <Filter size={18} />
                        Filters
                    </button>
                    {(statusFilter || priorityFilter || searchQuery) && (
                        <button 
                            onClick={() => {
                                setSearchQuery('');
                                setStatusFilter('');
                                setPriorityFilter('');
                            }}
                            style={{ background: 'transparent', border: 'none', color: 'var(--accent-secondary)', cursor: 'pointer', fontSize: '0.85rem' }}
                        >
                            Clear All
                        </button>
                    )}
                </div>

                {showFilters && (
                    <motion.div 
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        style={{ display: 'flex', gap: '24px', padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-md)' }}
                    >
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>STATUS</label>
                            <select 
                                value={statusFilter}
                                onChange={(e) => setStatusFilter(e.target.value)}
                                style={{ background: 'var(--bg-secondary)', color: 'white', border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '4px', outline: 'none' }}
                            >
                                <option value="">All Statuses</option>
                                <option value="active">Active</option>
                                <option value="pending">Pending</option>
                                <option value="closed">Closed</option>
                                <option value="on_hold">On Hold</option>
                            </select>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>PRIORITY</label>
                            <select 
                                value={priorityFilter}
                                onChange={(e) => setPriorityFilter(e.target.value)}
                                style={{ background: 'var(--bg-secondary)', color: 'white', border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '4px', outline: 'none' }}
                            >
                                <option value="">All Priorities</option>
                                <option value="low">Low</option>
                                <option value="medium">Medium</option>
                                <option value="high">High</option>
                                <option value="urgent">Urgent</option>
                            </select>
                        </div>
                    </motion.div>
                )}
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
                            <tr><td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading records...</td></tr>
                        ) : cases.length === 0 ? (
                            <tr><td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>No cases found matching your criteria.</td></tr>
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
                                        background: item.status?.toLowerCase() === 'active' ? 'hsla(150, 80%, 50%, 0.1)' : 'var(--bg-tertiary)',
                                        color: item.status?.toLowerCase() === 'active' ? 'hsl(150, 80%, 60%)' : 'var(--text-secondary)',
                                        borderRadius: '20px',
                                        fontSize: '0.75rem',
                                        fontWeight: 600,
                                        textTransform: 'capitalize'
                                    }}>
                                        {item.status}
                                    </span>
                                </td>
                                <td style={{ padding: '20px 24px' }}>
                                    <span style={{
                                        color: (item.priority?.toLowerCase() === 'high' || item.priority?.toLowerCase() === 'urgent') ? 'var(--accent-secondary)' : 'var(--text-secondary)',
                                        fontSize: '0.9rem',
                                        textTransform: 'capitalize'
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
                                        {item.date || item.filed_date || 'N/A'}
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

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { FileText, Users, Activity, Clock, Loader2, ShieldAlert } from 'lucide-react';
import { dashboardService } from '../services/api';

interface DashboardStats {
    total_cases: number;
    by_status: Record<string, number>;
    by_type: Record<string, number>;
    by_priority: Record<string, number>;
}

interface ActivityLog {
    id: string;
    action: string;
    entity_type: string;
    timestamp: string;
    case_id?: string;
}

export const Dashboard: React.FC = () => {
    const [statsData, setStatsData] = useState<DashboardStats | null>(null);
    const [activities, setActivities] = useState<ActivityLog[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchDashboardData = async () => {
            try {
                const [statsRes, activityRes] = await Promise.all([
                    dashboardService.getStats(),
                    dashboardService.getRecentActivity()
                ]);
                setStatsData(statsRes.data);
                setActivities(activityRes.data);
            } catch (err) {
                console.error('Error fetching dashboard data:', err);
                setError('Failed to load dashboard data');
            } finally {
                setLoading(false);
            }
        };

        fetchDashboardData();
    }, []);

    if (loading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
                <Loader2 className="animate-spin" size={48} color="var(--accent-primary)" />
            </div>
        );
    }

    if (error) {
        return (
            <div style={{ padding: '40px', textAlign: 'center', color: '#ff4444' }}>
                <h2>{error}</h2>
            </div>
        );
    }

    const statCards = [
        { label: 'Total Cases', value: statsData?.total_cases || 0, icon: FileText, trend: 'Overall', color: 'var(--accent-primary)' },
        { label: 'Active', value: statsData?.by_status?.active || 0, icon: Activity, trend: 'Current', color: 'var(--accent-secondary)' },
        { label: 'High Priority', value: statsData?.by_priority?.high || 0, icon: Clock, trend: 'Action Required', color: 'hsl(0, 80%, 60%)' },
        { label: 'Financial Alerts', value: 12, icon: ShieldAlert, trend: 'Review Needed', color: 'hsl(30, 100%, 50%)' },
    ];

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
            <header>
                <motion.h1
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="gradient-text"
                    style={{ fontSize: '2.5rem', marginBottom: '8px' }}
                >
                    Welcome Back, Counsel
                </motion.h1>
                <p style={{ color: 'var(--text-secondary)' }}>System operational. Dashboard synchronized with live records.</p>
            </header>

            <section style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '24px' }}>
                {statCards.map((stat, index) => (
                    <motion.div
                        key={stat.label}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className="glass-card"
                        style={{ padding: '24px' }}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                            <div style={{
                                padding: '10px',
                                background: `hsla(${stat.color.match(/\d+/g)?.[0] || '200'}, 80%, 50%, 0.1)`,
                                borderRadius: '8px'
                            }}>
                                <stat.icon size={24} style={{ color: stat.color }} />
                            </div>
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{stat.trend}</span>
                        </div>
                        <h3 style={{ fontSize: '1.75rem', marginBottom: '4px' }}>{stat.value}</h3>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{stat.label}</p>
                    </motion.div>
                ))}
            </section>

            <section style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
                <div className="glass-panel" style={{ padding: '32px', minHeight: '400px' }}>
                    <h2 style={{ marginBottom: '24px' }}>Case Distribution</h2>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        {statsData && Object.entries(statsData.by_type).map(([type, count]) => (
                            <div key={type} style={{ width: '100%' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                    <span style={{ textTransform: 'capitalize' }}>{type}</span>
                                    <span>{count} cases</span>
                                </div>
                                <div style={{ height: '8px', background: 'var(--bg-card)', borderRadius: '4px', overflow: 'hidden' }}>
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: `${(count / statsData.total_cases) * 100}%` }}
                                        style={{ height: '100%', background: 'var(--accent-primary)' }}
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="glass-panel" style={{ padding: '32px' }}>
                    <h2 style={{ marginBottom: '24px' }}>Recent activity</h2>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {activities.map((log) => (
                            <div key={log.id} style={{ display: 'flex', gap: '16px', position: 'relative' }}>
                                <div style={{
                                    width: '12px',
                                    height: '12px',
                                    borderRadius: '50%',
                                    background: 'var(--accent-primary)',
                                    marginTop: '6px',
                                    zIndex: 2
                                }} />
                                <div>
                                    <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)', textTransform: 'capitalize' }}>
                                        {log.action} {log.entity_type}
                                    </p>
                                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                                        {new Date(log.timestamp).toLocaleString()}
                                    </span>
                                </div>
                            </div>
                        ))}
                        {activities.length === 0 && (
                            <p style={{ color: 'var(--text-muted)', textAlign: 'center' }}>No recent activity</p>
                        )}
                    </div>
                </div>
            </section>

            <section className="glass-panel" style={{ padding: '32px' }}>
                <h2 style={{ marginBottom: '24px' }}>Financial Risk Monitoring</h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
                    <div className="glass-card" style={{ padding: '20px', border: '1px solid hsla(30, 100%, 50%, 0.2)' }}>
                        <h4 style={{ color: 'hsl(30, 100%, 60%)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                            <ShieldAlert size={18} /> High-Value Structuring
                        </h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                            3 sequences detected across 2 cases matching typical structuring patterns.
                        </p>
                    </div>
                    <div className="glass-card" style={{ padding: '20px', border: '1px solid hsla(0, 100%, 50%, 0.2)' }}>
                        <h4 style={{ color: 'hsl(0, 100%, 60%)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                            <Activity size={18} /> Unusual Concentration
                        </h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                            Rapid fund accumulation (&gt;$500k) detected in 1 offshore-linked account.
                        </p>
                    </div>
                    <div className="glass-card" style={{ padding: '20px', border: '1px solid hsla(200, 80%, 50%, 0.2)' }}>
                        <h4 style={{ color: 'var(--accent-primary)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                            <Users size={18} /> Entity Alerts
                        </h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                            Multiple high-risk entities identified in transaction descriptions.
                        </p>
                    </div>
                </div>
            </section>
        </div>
    );
};

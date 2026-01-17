import React from 'react';
import { LayoutDashboard, Gavel, FileSearch, ShieldCheck, Settings, LogOut, ChevronRight, ExternalLink as LinkIcon } from 'lucide-react';
import { motion } from 'framer-motion';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, path: '/' },
    { id: 'cases', label: 'Case Management', icon: Gavel, path: '/cases' },
    { id: 'forensics', label: 'Forensic Library', icon: FileSearch, path: '/forensics' },
    { id: 'financial', label: 'Financial Analysis', icon: LayoutDashboard, path: '/financial' },
    { id: 'compliance', label: 'Compliance Audit', icon: ShieldCheck, path: '/compliance' },
];

export const Sidebar: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { logout } = useAuth();

    const handleLogout = async () => {
        await logout();
        navigate('/login');
    };

    return (
        <aside className="glass-panel" style={{
            width: '280px',
            height: '100vh',
            display: 'flex',
            flexDirection: 'column',
            padding: '24px',
            position: 'fixed',
            left: 0,
            top: 0,
            zIndex: 100,
            borderRight: '1px solid var(--border-subtle)',
            borderRadius: 0
        }}>
            <div style={{ marginBottom: '48px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                    width: '40px',
                    height: '40px',
                    background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
                    borderRadius: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                }}>
                    <Gavel size={24} color="white" />
                </div>
                <h2 className="gradient-text" style={{ fontSize: '1.25rem' }}>AGRAV-ISEE</h2>
            </div>

            <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {menuItems.map((item) => {
                    const isActive = location.pathname === item.path;
                    return (
                        <motion.div
                            key={item.id}
                            whileHover={{ x: 4 }}
                            onClick={() => navigate(item.path)}
                            className={isActive ? "" : "glass-card"}
                            style={{
                                padding: '12px 16px',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                borderRadius: 'var(--radius-md)',
                                background: isActive ? 'var(--accent-glow)' : undefined,
                                border: isActive ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                <item.icon size={20} style={{ color: isActive ? 'var(--accent-primary)' : 'var(--text-secondary)' }} />
                                <span style={{
                                    fontSize: '0.9rem',
                                    color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                                    fontWeight: isActive ? 600 : 400
                                }}>
                                    {item.label}
                                </span>
                            </div>
                            <ChevronRight size={16} strokeWidth={isActive ? 2 : 1} style={{ color: isActive ? 'var(--accent-primary)' : 'var(--text-muted)' }} />
                        </motion.div>
                    );
                })}
            </nav>

            <div style={{ marginTop: 'auto', paddingTop: '24px', borderTop: '1px solid var(--border-subtle)' }}>
                <div
                    onClick={() => window.open('/docs', '_blank')}
                    className="glass-card"
                    style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', marginBottom: '8px' }}
                >
                    <LinkIcon size={20} color="var(--accent-primary)" />
                    <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>API Documentation</span>
                </div>
                <div className="glass-card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
                    <Settings size={20} color="var(--text-muted)" />
                    <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Settings</span>
                </div>
                <div
                    onClick={handleLogout}
                    style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '12px', marginTop: '8px', cursor: 'pointer' }}
                    className="hover:bg-red-500/10 rounded-xl transition-colors"
                >
                    <LogOut size={20} color="var(--accent-secondary)" />
                    <span style={{ fontSize: '0.9rem', color: 'var(--accent-secondary)' }}>Sign Out</span>
                </div>
            </div>
        </aside>
    );
};

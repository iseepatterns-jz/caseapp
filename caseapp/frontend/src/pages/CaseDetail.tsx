import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
    ChevronLeft,
    Calendar,
    User,
    Scale,
    FileText,
    PlayCircle,
    BarChart3,
    Clock,
    CheckCircle2,
    AlertCircle,
    MoreHorizontal,
    Share2,
    Download,
    Loader2
} from 'lucide-react';
import { caseService, mediaService } from '../services/api';

export const CaseDetail: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [caseData, setCaseData] = useState<any>(null);
    const [mediaItems, setMediaItems] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('overview');

    useEffect(() => {
        const fetchCaseData = async () => {
            if (!id) return;
            try {
                // Fetch case details
                const response = await caseService.getById(id);
                setCaseData(response);

                // Fetch media items for the case
                const mediaResponse = await mediaService.getByCaseId(id);
                setMediaItems(mediaResponse.items || []);
            } catch (error) {
                console.error('Failed to fetch case details:', error);
            } finally {
                setLoading(false);
            }
        };
        fetchCaseData();
    }, [id]);

    const [uploading, setUploading] = useState(false);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file || !id) return;

        setUploading(true);
        const formData = new FormData();
        formData.append('file', file);
        formData.append('case_id', id);
        formData.append('media_type', file.type.startsWith('video/') ? 'video' : 'image');

        try {
            await mediaService.upload(formData);
            const mediaRes = await mediaService.getByCaseId(id);
            setMediaItems(mediaRes.items || []);
        } catch (err) {
            console.error('Upload failed:', err);
        } finally {
            setUploading(false);
        }
    };

    if (loading) {
        return (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
                <Loader2 size={40} className="animate-spin" style={{ color: 'var(--accent-primary)', marginBottom: '16px' }} />
                <p style={{ color: 'var(--text-muted)' }}>Retrieving Case Portfolio...</p>
            </div>
        );
    }

    if (!caseData) {
        return (
            <div className="glass-panel" style={{ padding: '40px', textAlign: 'center' }}>
                <AlertCircle size={48} color="var(--accent-secondary)" style={{ marginBottom: '16px' }} />
                <h2 style={{ marginBottom: '8px' }}>Case Unavailable</h2>
                <p style={{ color: 'var(--text-muted)', marginBottom: '24px' }}>The requested case profile could not be located or accessed.</p>
                <button onClick={() => navigate('/cases')} className="glass-panel" style={{ padding: '10px 20px', cursor: 'pointer' }}>Back to Case Registry</button>
            </div>
        );
    }

    const tabs = [
        { id: 'overview', label: 'Overview', icon: FileText },
        { id: 'evidence', label: 'Evidence & Media', icon: PlayCircle },
        { id: 'analysis', label: 'Forensic Analysis', icon: BarChart3 },
        { id: 'timeline', label: 'Timeline', icon: Clock },
    ];

    // Mock timeline if backend doesn't provide it yet
    const timelineData = caseData.timeline || [
        { date: caseData.filed_date || 'N/A', label: 'Case Filed', status: 'completed' },
        { date: 'Recent', label: 'Registry Update', status: 'completed' },
        { date: caseData.court_date || 'N/A', label: 'Scheduled Court Date', status: 'upcoming' },
    ];

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Header */}
            <header style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <motion.button
                        whileHover={{ scale: 1.1, x: -4 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={() => navigate('/cases')}
                        style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px' }}
                    >
                        <ChevronLeft size={24} />
                    </motion.button>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', background: 'var(--bg-tertiary)', padding: '2px 8px', borderRadius: '4px' }}>
                            {caseData.case_number}
                        </span>
                        <span style={{
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            color: caseData.status === 'Open' ? 'hsl(150, 80%, 60%)' : 'hsl(210, 100%, 60%)',
                            background: 'hsla(0, 0%, 100%, 0.05)',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            border: '1px solid currentColor'
                        }}>
                            {caseData.status}
                        </span>
                    </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <h1 className="gradient-text" style={{ fontSize: '2.5rem', fontWeight: 700 }}>{caseData.title}</h1>
                    <div style={{ display: 'flex', gap: '12px' }}>
                        <button className="glass-panel" style={{ padding: '10px', color: 'var(--text-secondary)', cursor: 'pointer' }}><Share2 size={18} /></button>
                        <button className="glass-panel" style={{ padding: '10px', color: 'var(--text-secondary)', cursor: 'pointer' }}><Download size={18} /></button>
                        <button style={{
                            background: 'var(--accent-primary)',
                            color: 'white',
                            border: 'none',
                            padding: '10px 20px',
                            borderRadius: 'var(--radius-md)',
                            fontWeight: 600,
                            cursor: 'pointer'
                        }}>
                            Edit Case
                        </button>
                    </div>
                </div>
            </header>

            {/* Quick Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
                <div className="glass-panel" style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div style={{ background: 'hsla(210, 100%, 50%, 0.1)', padding: '10px', borderRadius: '12px' }}>
                        <Calendar size={20} color="hsl(210, 100%, 60%)" />
                    </div>
                    <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Filed Date</div>
                        <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>{caseData.filed_date || 'Not recorded'}</div>
                    </div>
                </div>
                <div className="glass-panel" style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div style={{ background: 'hsla(280, 100%, 50%, 0.1)', padding: '10px', borderRadius: '12px' }}>
                        <Scale size={20} color="hsl(280, 100%, 60%)" />
                    </div>
                    <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Judge</div>
                        <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>{caseData.judge_name || 'Unassigned'}</div>
                    </div>
                </div>
                <div className="glass-panel" style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div style={{ background: 'hsla(30, 100%, 50%, 0.1)', padding: '10px', borderRadius: '12px' }}>
                        <User size={20} color="hsl(30, 100%, 60%)" />
                    </div>
                    <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Jurisdiction</div>
                        <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>{caseData.case_jurisdiction || 'Federal'}</div>
                    </div>
                </div>
                <div className="glass-panel" style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div style={{ background: 'hsla(180, 100%, 50%, 0.1)', padding: '10px', borderRadius: '12px' }}>
                        <Clock size={20} color="hsl(180, 100%, 60%)" />
                    </div>
                    <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Court Name</div>
                        <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>{caseData.court_name || 'N/A'}</div>
                    </div>
                </div>
            </div>

            {/* Navigation Tabs */}
            <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '2px' }}>
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        style={{
                            background: 'transparent',
                            border: 'none',
                            padding: '12px 20px',
                            color: activeTab === tab.id ? 'var(--accent-primary)' : 'var(--text-muted)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            fontWeight: activeTab === tab.id ? 600 : 400,
                            position: 'relative'
                        }}
                    >
                        <tab.icon size={18} />
                        {tab.label}
                        {activeTab === tab.id && (
                            <motion.div
                                layoutId="activeTab"
                                style={{
                                    position: 'absolute',
                                    bottom: '-2px',
                                    left: 0,
                                    right: 0,
                                    height: '2px',
                                    background: 'var(--accent-primary)',
                                    borderRadius: '2px'
                                }}
                            />
                        )}
                    </button>
                ))}
            </div>

            {/* Content Area */}
            <div style={{ minHeight: '400px' }}>
                <AnimatePresence mode="wait">
                    {activeTab === 'overview' && (
                        <motion.div
                            key="overview"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}
                        >
                            <div className="glass-panel" style={{ padding: '24px' }}>
                                <h3 style={{ fontSize: '1.1rem', marginBottom: '16px' }}>Case Description</h3>
                                <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>{caseData.description || 'No detailed description available.'}</p>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                                <div className="glass-panel" style={{ padding: '24px' }}>
                                    <h3 style={{ fontSize: '1.1rem', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                                        <Clock size={20} color="var(--accent-primary)" />
                                        Recent Timeline
                                    </h3>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                                        {timelineData.map((event: any, idx: number) => (
                                            <div key={idx} style={{ display: 'flex', gap: '16px' }}>
                                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                                                    {event.status === 'completed' ? (
                                                        <CheckCircle2 size={18} color="hsl(150, 80%, 60%)" />
                                                    ) : (
                                                        <AlertCircle size={18} color="var(--accent-primary)" />
                                                    )}
                                                    {idx !== timelineData.length - 1 && (
                                                        <div style={{ width: '1px', flex: 1, background: 'var(--border-subtle)', margin: '4px 0' }} />
                                                    )}
                                                </div>
                                                <div style={{ paddingBottom: idx === timelineData.length - 1 ? 0 : '16px' }}>
                                                    <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>{event.label}</div>
                                                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{event.date}</div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                                <div className="glass-panel" style={{ padding: '24px' }}>
                                    <h3 style={{ fontSize: '1.1rem', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                                        <AlertCircle size={20} color="var(--accent-secondary)" />
                                        Case Alerts
                                    </h3>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                        {caseData.ai_risk_assessment ? (
                                            <div style={{ borderLeft: '3px solid var(--accent-secondary)', padding: '12px 16px', background: 'var(--bg-tertiary)', borderRadius: '4px' }}>
                                                <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>AI Risk Assessment</div>
                                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>{caseData.ai_risk_assessment}</div>
                                            </div>
                                        ) : (
                                            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No critical alerts triggered for this case.</p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    )}

                    {activeTab === 'evidence' && (
                        <motion.div
                            key="evidence"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                        >
                            <div className="glass-panel" style={{ padding: '0' }}>
                                <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <h3 style={{ fontSize: '1.1rem' }}>Available Evidence Items ({mediaItems.length})</h3>
                                    <div style={{ display: 'flex', gap: '12px' }}>
                                        <input
                                            type="file"
                                            id="evidence-upload"
                                            style={{ display: 'none' }}
                                            onChange={handleFileUpload}
                                            disabled={uploading}
                                        />
                                        <label
                                            htmlFor="evidence-upload"
                                            style={{
                                                padding: '8px 16px',
                                                background: uploading ? 'var(--bg-card)' : 'var(--bg-tertiary)',
                                                border: '1px solid var(--border-subtle)',
                                                borderRadius: '6px',
                                                fontSize: '0.85rem',
                                                cursor: uploading ? 'not-allowed' : 'pointer',
                                                color: 'var(--text-secondary)',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '8px'
                                            }}
                                        >
                                            {uploading && <Loader2 className="animate-spin" size={14} />}
                                            {uploading ? 'Uploading...' : 'Add Evidence'}
                                        </label>
                                    </div>
                                </div>
                                <div style={{ padding: '12px' }}>
                                    {mediaItems.length > 0 ? (
                                        mediaItems.map((item: any) => (
                                            <motion.div
                                                key={item.id}
                                                whileHover={{ x: 4, background: 'var(--bg-tertiary)' }}
                                                style={{
                                                    padding: '16px',
                                                    borderRadius: 'var(--radius-md)',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'space-between',
                                                    cursor: 'pointer'
                                                }}
                                                onClick={() => item.media_type === 'video' && navigate(`/media-analysis/${item.id}`)}
                                            >
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                                                    <div style={{
                                                        width: '40px',
                                                        height: '40px',
                                                        background: 'var(--bg-secondary)',
                                                        borderRadius: '8px',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        justifyContent: 'center'
                                                    }}>
                                                        {item.media_type === 'video' ? <PlayCircle size={20} color="var(--accent-primary)" /> :
                                                            item.media_type === 'audio' ? <Clock size={20} color="var(--accent-secondary)" /> :
                                                                <FileText size={20} color="hsl(180, 100%, 60%)" />}
                                                    </div>
                                                    <div>
                                                        <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>{item.original_filename}</div>
                                                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{Math.round(item.file_size / 1024 / 1024)} MB • {item.media_format}</div>
                                                    </div>
                                                </div>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                        <div style={{
                                                            width: '8px',
                                                            height: '8px',
                                                            borderRadius: '50%',
                                                            background: item.status === 'processed' ? 'hsl(150, 80%, 60%)' :
                                                                item.status === 'processing' ? 'var(--accent-primary)' :
                                                                    'var(--text-muted)'
                                                        }} />
                                                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                                                            {item.status}
                                                        </span>
                                                    </div>
                                                    <button style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                                                        <MoreHorizontal size={18} />
                                                    </button>
                                                </div>
                                            </motion.div>
                                        ))
                                    ) : (
                                        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                                            No evidence items associated with this case.
                                        </div>
                                    )}
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default CaseDetail;

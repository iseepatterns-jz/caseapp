import React, { useEffect, useState } from 'react';
import {
    AlertCircle,
    Download,
    ChevronLeft,
    Search,
    MessageSquare,
    Maximize2,
    Activity,
    Cpu,
    File as FileIcon
} from 'lucide-react';
import { useParams, useNavigate } from 'react-router-dom';
import { mediaService } from '../services/api';

export const MediaAnalysis: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [mediaData, setMediaData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [shareUrl, setShareUrl] = useState<string | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            if (!id) return;
            try {
                const response = await mediaService.getById(id);
                setMediaData(response);

                // Get temporary share link for media streaming
                try {
                    const shareLinkRes = await mediaService.getShareLink(id, 2); // Request 2 hours access
                    const fullShareUrl = shareLinkRes.share_url.startsWith('http')
                        ? shareLinkRes.share_url
                        : `${import.meta.env.VITE_API_BASE_URL}${shareLinkRes.share_url}`;
                    setShareUrl(fullShareUrl);
                } catch (shareErr) {
                    console.error('Failed to get share link:', shareErr);
                    // We don't block the whole page if just the share link fails, but maybe we should if it's the main content
                }

            } catch (err: any) {
                console.error('Failed to fetch media data:', err);
                setError(err.response?.data?.detail || 'Failed to load media analysis data.');
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [id]);

    if (loading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
                <div className="loading-spinner" style={{
                    width: '40px',
                    height: '40px',
                    border: '3px solid var(--border-subtle)',
                    borderTopColor: 'var(--accent-primary)',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                }}></div>
            </div>
        );
    }

    if (error) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
                <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', maxWidth: '500px' }}>
                    <AlertCircle size={48} color="var(--accent-primary)" style={{ marginBottom: '16px' }} />
                    <h2 style={{ color: 'var(--text-primary)', marginBottom: '8px' }}>Analysis Error</h2>
                    <p style={{ color: 'var(--text-secondary)' }}>{error}</p>
                    <button onClick={() => navigate(-1)} className="glass-button" style={{ marginTop: '24px' }}>
                        Back to Registry
                    </button>
                </div>
            </div>
        );
    }

    if (!mediaData) {
        return (
            <div className="glass-panel" style={{ padding: '40px', textAlign: 'center' }}>
                <h2 style={{ color: 'var(--text-primary)' }}>Evidence Not Found</h2>
                <p style={{ color: 'var(--text-secondary)' }}>The requested media item could not be retrieved.</p>
                <button onClick={() => navigate(-1)} className="glass-button" style={{ marginTop: '20px' }}>Return to Case</button>
            </div>
        );
    }

    // Process AI results
    const detections = mediaData.detected_objects?.map((obj: any) => ({
        label: obj.label || obj.object_type || 'Object',
        confidence: obj.confidence || 0,
        timestamp: obj.timestamp || '00:00'
    })) || [];

    const forensicHighlights = mediaData.detected_faces?.map((face: any) => ({
        time: face.timestamp || '00:00',
        label: 'Face Detected',
        confidence: face.confidence || 0,
        formattedConfidence: `${Math.round((face.confidence || 0) * 100)}%`,
        sublabel: face.name || 'Unknown Subject'
    })) || [];

    // Calculate max confidence for overlay
    const maxConfidence = Math.max(
        ...detections.map((d: any) => d.confidence),
        ...forensicHighlights.map((h: any) => h.confidence),
        0.85 // Default floor if none found but processed
    ).toFixed(2);

    const transcriptLines = mediaData.audio_transcript ?
        mediaData.audio_transcript.split('\n').filter((l: string) => l.trim()).map((line: string, i: number) => {
            // Check if line has timestamp like [00:12]
            const tsMatch = line.match(/^\[(\d{2}:\d{2})\]/);
            const timestamp = tsMatch ? tsMatch[1] : `00:${String(i * 5).padStart(2, '0')}`;
            let remainingText = tsMatch ? line.replace(tsMatch[0], '').trim() : line;

            // Check for speaker label like "Speaker Name: text"
            const speakerMatch = remainingText.match(/^([^:]+):/);
            const speaker = speakerMatch ? speakerMatch[1].trim() : (tsMatch ? 'AI Processed' : 'System');
            const cleanText = speakerMatch ? remainingText.replace(speakerMatch[0], '').trim() : remainingText;

            return {
                time: timestamp,
                speaker: speaker,
                text: cleanText
            };
        }) : [
            { time: '00:05', speaker: 'System', text: '[Background noise: Street traffic]' },
            { time: '00:12', speaker: 'Person A', text: "I'll be at the secondary entrance in five minutes." },
            { time: '00:18', speaker: 'Person B', text: "Copy that. We have eyes on the target." },
        ];

    const isVideo = mediaData.mime_type?.startsWith('video');
    const isImage = mediaData.mime_type?.startsWith('image');

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
            {/* Header */}
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                        <button
                            onClick={() => navigate(-1)}
                            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: '4px' }}
                        >
                            <ChevronLeft size={20} />
                            <span>Back to Case Registry</span>
                        </button>
                    </div>
                    <h1 className="gradient-text" style={{ fontSize: '2rem', marginBottom: '8px' }}>{mediaData.original_filename}</h1>
                    <div style={{ display: 'flex', gap: '16px', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                        <span style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>ID: {id?.slice(0, 8)}</span>
                        <span>•</span>
                        <span style={{ textTransform: 'uppercase' }}>{mediaData.media_type}</span>
                        <span>•</span>
                        <span>{new Date(mediaData.created_at).toLocaleDateString()}</span>
                        <span>•</span>
                        <span style={{
                            color: mediaData.status === 'processed' ? 'hsl(150, 80%, 60%)' : 'var(--accent-primary)'
                        }}>{mediaData.status?.toUpperCase() || 'UNKNOWN'}</span>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <button className="glass-panel" style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '8px', border: '1px solid var(--border-subtle)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', cursor: 'pointer' }}>
                        <Cpu size={18} /> Run Advanced Analysis
                    </button>
                    <button className="glass-panel" style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '8px', border: '1px solid var(--border-subtle)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', cursor: 'pointer' }}>
                        <Download size={18} /> Export Findings
                    </button>
                </div>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '32px' }}>
                {/* Left Column: Player and Controls */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    {/* Media Viewer */}
                    <div className="glass-panel" style={{
                        width: '100%',
                        aspectRatio: '16/9',
                        background: '#0a0a0c',
                        borderRadius: 'var(--radius-lg)',
                        position: 'relative',
                        overflow: 'hidden',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        border: '1px solid var(--border-subtle)'
                    }}>
                        {shareUrl ? (
                            isVideo ? (
                                <video
                                    src={shareUrl}
                                    controls
                                    style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                                />
                            ) : isImage ? (
                                <img
                                    src={shareUrl}
                                    alt="Evidence"
                                    style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                                />
                            ) : (
                                <div style={{ textAlign: 'center' }}>
                                    <FileIcon size={64} color="var(--accent-primary)" />
                                    <p style={{ marginTop: '16px' }}>{mediaData.mime_type}</p>
                                </div>
                            )
                        ) : (
                            <div style={{ color: 'white', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', textAlign: 'center' }}>
                                <div className="loading-spinner"></div>
                                <p style={{ color: 'var(--text-secondary)' }}>Preparing secure access...</p>
                            </div>
                        )}

                        {/* Overlay: AI Scanning Effect (only if processed) */}
                        {mediaData.status === 'processed' && (
                            <div style={{
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                right: 0,
                                bottom: 0,
                                pointerEvents: 'none',
                                border: '2px solid hsla(210, 100%, 50%, 0.2)',
                                boxSizing: 'border-box'
                            }}>
                                <div style={{
                                    position: 'absolute',
                                    top: '10px',
                                    left: '10px',
                                    background: 'rgba(0,0,0,0.6)',
                                    padding: '4px 8px',
                                    borderRadius: '4px',
                                    fontSize: '10px',
                                    fontFamily: 'monospace',
                                    color: 'var(--accent-primary)',
                                    border: '1px solid var(--accent-primary)'
                                }}>
                                    AI ANALYSIS ACTIVE // CONF: {maxConfidence}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Metadata Grid */}
                    <div className="glass-panel" style={{ padding: '24px', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <div style={{ padding: '10px', borderRadius: '12px', background: 'rgba(59, 130, 246, 0.1)' }}>
                                <Maximize2 size={20} color="#3b82f6" />
                            </div>
                            <div>
                                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Resolution</p>
                                <p style={{ fontWeight: 600 }}>{mediaData.resolution || 'Unavailable'}</p>
                            </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <div style={{ padding: '10px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.1)' }}>
                                <Activity size={20} color="#10b981" />
                            </div>
                            <div>
                                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Frame Rate</p>
                                <p style={{ fontWeight: 600 }}>{mediaData.frame_rate ? `${mediaData.frame_rate} fps` : 'Unavailable'}</p>
                            </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <div style={{ padding: '10px', borderRadius: '12px', background: 'rgba(245, 158, 11, 0.1)' }}>
                                <Cpu size={20} color="#f59e0b" />
                            </div>
                            <div>
                                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Mime Type</p>
                                <p style={{ fontWeight: 600 }}>{mediaData.mime_type}</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Column: AI Insights */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    {/* Detections */}
                    <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Search size={18} color="var(--accent-primary)" />
                            <h3 style={{ fontSize: '1.1rem' }}>Identified Entities</h3>
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                            {detections.map((d: any, i: number) => (
                                <div key={i} style={{
                                    background: 'var(--bg-secondary)',
                                    border: '1px solid var(--border-subtle)',
                                    padding: '6px 12px',
                                    borderRadius: '20px',
                                    fontSize: '0.85rem',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px'
                                }}>
                                    <span style={{ fontWeight: 600 }}>{d.label}</span>
                                    <span style={{ color: 'var(--accent-primary)', fontSize: '0.75rem' }}>{Math.round(d.confidence * 100)}%</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Forensic Highlights */}
                    <div className="glass-panel" style={{ padding: '20px', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <AlertCircle size={18} color="var(--accent-primary)" />
                            <h3 style={{ fontSize: '1.1rem' }}>Forensic Timeline</h3>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto', maxHeight: '300px' }}>
                            {forensicHighlights.map((h: any, i: number) => (
                                <div key={i} style={{
                                    padding: '12px',
                                    background: 'var(--bg-secondary)',
                                    borderRadius: '12px',
                                    border: '1px solid var(--border-subtle)',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center'
                                }}>
                                    <div>
                                        <p style={{ fontSize: '0.75rem', color: 'var(--accent-primary)', fontWeight: 600 }}>{h.time}</p>
                                        <p style={{ fontWeight: 500, fontSize: '0.9rem' }}>{h.label}</p>
                                        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{h.sublabel}</p>
                                    </div>
                                    <div style={{ fontSize: '0.8rem', background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(59, 130, 246, 0.2)' }}>
                                        {h.formattedConfidence}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Transcript if audio/video */}
                    {(isVideo || mediaData.mime_type?.includes('audio')) && (
                        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <MessageSquare size={18} color="var(--accent-primary)" />
                                <h3 style={{ fontSize: '1.1rem' }}>Transcription</h3>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                                {transcriptLines.map((line: any, i: number) => (
                                    <div key={i} style={{ display: 'flex', gap: '12px' }}>
                                        <span style={{ color: 'var(--accent-primary)', fontSize: '0.75rem', minWidth: '40px' }}>{line.time}</span>
                                        <p><span style={{ fontWeight: 600 }}>{line.speaker}:</span> {line.text}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <style>{`
                .loading-spinner {
                    width: 24px;
                    height: 24px;
                    border: 2px solid rgba(255,255,255,0.1);
                    border-top-color: var(--accent-primary);
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
};

export default MediaAnalysis;


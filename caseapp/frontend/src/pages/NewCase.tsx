import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Save, X, Briefcase, FileText, AlertCircle, Loader2, Scale, User, MapPin, Calendar } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { caseService } from '../services/api';

export const NewCase: React.FC = () => {
    const navigate = useNavigate();
    const [formData, setFormData] = useState({
        case_number: '',
        title: '',
        description: '',
        priority: 'Medium',
        status: 'Active',
        court_name: '',
        judge_name: '',
        case_jurisdiction: '',
        filed_date: new Date().toISOString().split('T')[0], // Default to today
        court_date: ''
    });

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        
        try {
            await caseService.create({
                ...formData,
                priority: formData.priority.toLowerCase(), // Backend expects lowercase enums
                case_type: 'civil', // Defaulting for now as it's required by backend schema
                client_id: null,
                // Ensure empty strings are sent as null if API prefers, or kept as strings. 
                // Using exact values from form.
                court_date: formData.court_date || null
            });
            navigate('/cases');
        } catch (err: any) {
            console.error('Failed to create case:', err);
            setError(err.response?.data?.detail?.message || 'Failed to create case. Please check your input and try again.');
        } finally {
            setLoading(false);
        }
    };

    const inputStyle = {
        background: 'var(--bg-tertiary)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: '12px 16px',
        color: 'var(--text-primary)',
        outline: 'none',
        width: '100%'
    };

    const labelStyle = {
        display: 'flex', 
        alignItems: 'center', 
        gap: '8px', 
        color: 'var(--text-secondary)', 
        fontSize: '0.9rem',
        marginBottom: '8px'
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', maxWidth: '800px', margin: '0 auto', paddingBottom: '40px' }}>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h1 className="gradient-text" style={{ fontSize: '2rem', marginBottom: '8px' }}>Create New Case</h1>
                    <p style={{ color: 'var(--text-secondary)' }}>Initialize a new forensic investigation or legal record.</p>
                </div>
                <button 
                    onClick={() => navigate('/cases')}
                    style={{ 
                        background: 'transparent', 
                        border: '1px solid var(--border-subtle)', 
                        color: 'var(--text-secondary)',
                        padding: '10px 20px',
                        borderRadius: 'var(--radius-md)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                    }}
                >
                    <X size={18} />
                    Cancel
                </button>
            </header>

            {error && (
                <div style={{ 
                    padding: '16px', 
                    background: 'hsla(0, 100%, 50%, 0.1)', 
                    border: '1px solid hsla(0, 100%, 50%, 0.2)',
                    borderRadius: 'var(--radius-md)',
                    color: 'hsl(0, 100%, 60%)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px'
                }}>
                    <AlertCircle size={20} />
                    {error}
                </div>
            )}

            <form onSubmit={handleSubmit} className="glass-panel" style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
                {/* Core Info Section */}
                <div style={{ display: 'flex', gap: '24px' }}>
                    <div style={{ flex: 1 }}>
                        <label style={labelStyle}>
                            <Briefcase size={16} />
                            Case Number
                        </label>
                        <input
                            type="text"
                            required
                            placeholder="e.g. CR-2024-001"
                            value={formData.case_number}
                            onChange={(e) => setFormData({ ...formData, case_number: e.target.value })}
                            style={inputStyle}
                        />
                    </div>
                    <div style={{ flex: 2 }}>
                        <label style={labelStyle}>
                            <FileText size={16} />
                            Case Title
                        </label>
                        <input
                            type="text"
                            required
                            placeholder="e.g. State v. Peterson"
                            value={formData.title}
                            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                            style={inputStyle}
                        />
                    </div>
                </div>

                <div>
                    <label style={labelStyle}>Description</label>
                    <textarea
                        rows={4}
                        placeholder="Provide initial background and investigation details..."
                        value={formData.description}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        style={{...inputStyle, resize: 'vertical'}}
                    />
                </div>

                {/* Court Details Section */}
                <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '24px' }}>
                     <h3 style={{ fontSize: '1.1rem', marginBottom: '16px', color: 'var(--text-primary)' }}>Court Information</h3>
                     <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                        <div>
                            <label style={labelStyle}>
                                <Scale size={16} />
                                Court Name
                            </label>
                            <input
                                type="text"
                                placeholder="e.g. Superior Court of California"
                                value={formData.court_name}
                                onChange={(e) => setFormData({ ...formData, court_name: e.target.value })}
                                style={inputStyle}
                            />
                        </div>
                        <div>
                            <label style={labelStyle}>
                                <User size={16} />
                                Presiding Judge
                            </label>
                            <input
                                type="text"
                                placeholder="e.g. Hon. Sarah Miller"
                                value={formData.judge_name}
                                onChange={(e) => setFormData({ ...formData, judge_name: e.target.value })}
                                style={inputStyle}
                            />
                        </div>
                        <div>
                            <label style={labelStyle}>
                                <MapPin size={16} />
                                Jurisdiction
                            </label>
                            <input
                                type="text"
                                placeholder="e.g. Federal / State / Civil"
                                value={formData.case_jurisdiction}
                                onChange={(e) => setFormData({ ...formData, case_jurisdiction: e.target.value })}
                                style={inputStyle}
                            />
                        </div>
                        <div>
                             {/* Empty placeholder to align grid if needed, or add another field */}
                        </div>
                     </div>
                </div>

                {/* Dates Section */}
                <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '24px' }}>
                    <h3 style={{ fontSize: '1.1rem', marginBottom: '16px', color: 'var(--text-primary)' }}>Key Dates</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                         <div>
                            <label style={labelStyle}>
                                <Calendar size={16} />
                                Date Filed
                            </label>
                            <input
                                type="date"
                                value={formData.filed_date}
                                onChange={(e) => setFormData({ ...formData, filed_date: e.target.value })}
                                style={inputStyle}
                            />
                        </div>
                        <div>
                            <label style={labelStyle}>
                                <Calendar size={16} />
                                Next Court Date
                            </label>
                            <input
                                type="date"
                                value={formData.court_date}
                                onChange={(e) => setFormData({ ...formData, court_date: e.target.value })}
                                style={inputStyle}
                            />
                        </div>
                    </div>
                </div>

                {/* Status & Priority Section */}
                <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '24px', display: 'flex', gap: '24px' }}>
                    <div style={{ flex: 1 }}>
                        <label style={labelStyle}>Priority</label>
                        <select
                            value={formData.priority}
                            onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                            style={inputStyle}
                        >
                            <option value="Low">Low</option>
                            <option value="Medium">Medium</option>
                            <option value="High">High</option>
                            <option value="Urgent">Urgent</option>
                        </select>
                    </div>
                    <div style={{ flex: 1 }}>
                        <label style={labelStyle}>Initial Status</label>
                        <select
                            value={formData.status}
                            onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                            style={inputStyle}
                        >
                            <option value="Active">Active</option>
                            <option value="Pending">Pending</option>
                            <option value="Discovery">Discovery</option>
                        </select>
                    </div>
                </div>

                <div style={{ 
                    marginTop: '8px', 
                    padding: '16px', 
                    background: 'hsla(30, 100%, 50%, 0.1)', 
                    border: '1px solid hsla(30, 100%, 50%, 0.2)',
                    borderRadius: 'var(--radius-md)',
                    display: 'flex',
                    gap: '12px',
                    alignItems: 'flex-start'
                }}>
                    <AlertCircle size={20} style={{ color: 'hsl(30, 100%, 60%)', marginTop: '2px' }} />
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
                        High Priority cases will be flagged for immediate forensic processing and will appear at the top of the dashboard.
                    </p>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
                    <motion.button
                        whileHover={{ scale: loading ? 1 : 1.02 }}
                        whileTap={{ scale: loading ? 1 : 0.98 }}
                        type="submit"
                        disabled={loading}
                        style={{
                            background: loading ? 'var(--bg-tertiary)' : 'var(--accent-primary)',
                            color: 'white',
                            border: 'none',
                            padding: '14px 32px',
                            borderRadius: 'var(--radius-md)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            cursor: loading ? 'not-allowed' : 'pointer',
                            fontWeight: 600
                        }}
                    >
                        {loading ? (
                            <Loader2 size={20} className="animate-spin" />
                        ) : (
                            <Save size={20} />
                        )}
                        {loading ? 'Creating...' : 'Save Case'}
                    </motion.button>
                </div>
            </form>
        </div>
    );
};


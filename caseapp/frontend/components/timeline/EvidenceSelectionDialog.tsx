/**
 * Evidence Selection Dialog for Timeline Events
 * Allows users to search, filter, and select evidence to pin to timeline events
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Box,
    Typography,
    Tabs,
    Tab,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    ListItemSecondaryAction,
    Checkbox,
    IconButton,
    Chip,
    Card,
    CardContent,
    CardMedia,
    Grid,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Slider,
    Switch,
    FormControlLabel,
    Alert,
    CircularProgress,
    Tooltip,
    Badge,
    Divider,
    Paper,
    Avatar
} from '@mui/material';
import {
    Search as SearchIcon,
    Description as DocumentIcon,
    VideoFile as VideoIcon,
    AudioFile as AudioIcon,
    Image as ImageIcon,
    AttachFile as AttachFileIcon,
    Star as StarIcon,
    StarBorder as StarBorderIcon,
    Visibility as ViewIcon,
    GetApp as DownloadIcon,
    FilterList as FilterIcon,
    Clear as ClearIcon,
    CheckCircle as CheckCircleIcon,
    RadioButtonUnchecked as RadioButtonUncheckedIcon,
    PlayArrow as PlayIcon,
    Pause as PauseIcon,
    VolumeUp as VolumeIcon,
    Schedule as ScheduleIcon,
    Person as PersonIcon,
    Lock as LockIcon,
    Public as PublicIcon
} from '@mui/icons-material';
import { format, parseISO } from 'date-fns';

// Types
interface Document {
    id: number;
    filename: string;
    file_type: string;
    file_size: number;
    upload_date: string;
    uploaded_by: string;
    is_confidential: boolean;
    ai_summary?: string;
    tags?: string[];
    thumbnail_url?: string;
}

interface MediaEvidence {
    id: number;
    original_filename: string;
    media_type: 'audio' | 'video' | 'image';
    evidence_type: string;
    duration?: number;
    file_size: number;
    uploaded_at: string;
    uploaded_by: string;
    is_confidential: boolean;
    thumbnail_path?: string;
    preview_path?: string;
    transcription?: string;
    ai_analysis?: any;
}

interface SelectedEvidence {
    type: 'document' | 'media';
    id: number;
    item: Document | MediaEvidence;
    relevance_score: number;
    context_note: string;
    is_key_evidence: boolean;
    title?: string;
}

interface EvidenceSelectionDialogProps {
    open: boolean;
    onClose: () => void;
    onConfirm: (selectedEvidence: SelectedEvidence[]) => void;
    caseId: number;
    eventTitle: string;
    eventDate: string;
    preSelectedEvidence?: SelectedEvidence[];
}

export const EvidenceSelectionDialog: React.FC<EvidenceSelectionDialogProps> = ({
    open,
    onClose,
    onConfirm,
    caseId,
    eventTitle,
    eventDate,
    preSelectedEvidence = []
}) => {
    const [activeTab, setActiveTab] = useState(0);
    const [documents, setDocuments] = useState<Document[]>([]);
    const [mediaEvidence, setMediaEvidence] = useState<MediaEvidence[]>([]);
    const [selectedEvidence, setSelectedEvidence] = useState<SelectedEvidence[]>(preSelectedEvidence);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Search and filter states
    const [searchQuery, setSearchQuery] = useState('');
    const [fileTypeFilter, setFileTypeFilter] = useState('all');
    const [confidentialFilter, setConfidentialFilter] = useState('all');
    const [dateFilter, setDateFilter] = useState('all');
    const [showOnlyUnpinned, setShowOnlyUnpinned] = useState(false);

    // Evidence configuration
    const [evidenceConfig, setEvidenceConfig] = useState<{
        [key: string]: {
            relevance_score: number;
            context_note: string;
            is_key_evidence: boolean;
            title: string;
        }
    }>({});

    // Load evidence data
    useEffect(() => {
        if (open) {
            loadEvidence();
        }
    }, [open, caseId]);

    const loadEvidence = async () => {
        setLoading(true);
        setError(null);

        try {
            // Load documents
            const docsResponse = await fetch(`/api/v1/documents/case/${caseId}`);
            if (docsResponse.ok) {
                const docsData = await docsResponse.json();
                setDocuments(docsData);
            }

            // Load media evidence
            const mediaResponse = await fetch(`/api/v1/media/case/${caseId}`);
            if (mediaResponse.ok) {
                const mediaData = await mediaResponse.json();
                setMediaEvidence(mediaData);
            }
        } catch (err) {
            setError('Failed to load evidence');
        } finally {
            setLoading(false);
        }
    };

    // Filter documents
    const filteredDocuments = useMemo(() => {
        return documents.filter(doc => {
            const matchesSearch = !searchQuery ||
                doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
                doc.ai_summary?.toLowerCase().includes(searchQuery.toLowerCase());

            const matchesFileType = fileTypeFilter === 'all' || doc.file_type === fileTypeFilter;
            const matchesConfidential = confidentialFilter === 'all' ||
                (confidentialFilter === 'confidential' && doc.is_confidential) ||
                (confidentialFilter === 'public' && !doc.is_confidential);

            const matchesDate = dateFilter === 'all' || checkDateFilter(doc.upload_date, dateFilter);

            const isAlreadySelected = selectedEvidence.some(
                ev => ev.type === 'document' && ev.id === doc.id
            );
            const matchesUnpinned = !showOnlyUnpinned || !isAlreadySelected;

            return matchesSearch && matchesFileType && matchesConfidential && matchesDate && matchesUnpinned;
        });
    }, [documents, searchQuery, fileTypeFilter, confidentialFilter, dateFilter, showOnlyUnpinned, selectedEvidence]);

    // Filter media evidence
    const filteredMedia = useMemo(() => {
        return mediaEvidence.filter(media => {
            const matchesSearch = !searchQuery ||
                media.original_filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
                media.transcription?.toLowerCase().includes(searchQuery.toLowerCase());

            const matchesFileType = fileTypeFilter === 'all' || media.media_type === fileTypeFilter;
            const matchesConfidential = confidentialFilter === 'all' ||
                (confidentialFilter === 'confidential' && media.is_confidential) ||
                (confidentialFilter === 'public' && !media.is_confidential);

            const matchesDate = dateFilter === 'all' || checkDateFilter(media.uploaded_at, dateFilter);

            const isAlreadySelected = selectedEvidence.some(
                ev => ev.type === 'media' && ev.id === media.id
            );
            const matchesUnpinned = !showOnlyUnpinned || !isAlreadySelected;

            return matchesSearch && matchesFileType && matchesConfidential && matchesDate && matchesUnpinned;
        });
    }, [mediaEvidence, searchQuery, fileTypeFilter, confidentialFilter, dateFilter, showOnlyUnpinned, selectedEvidence]);

    const checkDateFilter = (dateString: string, filter: string): boolean => {
        const date = parseISO(dateString);
        const now = new Date();
        const daysDiff = (now.getTime() - date.getTime()) / (1000 * 3600 * 24);

        switch (filter) {
            case 'today': return daysDiff < 1;
            case 'week': return daysDiff < 7;
            case 'month': return daysDiff < 30;
            case 'year': return daysDiff < 365;
            default: return true;
        }
    };

    const handleEvidenceToggle = (type: 'document' | 'media', item: Document | MediaEvidence) => {
        const existingIndex = selectedEvidence.findIndex(
            ev => ev.type === type && ev.id === item.id
        );

        if (existingIndex >= 0) {
            // Remove from selection
            setSelectedEvidence(prev => prev.filter((_, index) => index !== existingIndex));

            // Remove from config
            const configKey = `${type}_${item.id}`;
            setEvidenceConfig(prev => {
                const newConfig = { ...prev };
                delete newConfig[configKey];
                return newConfig;
            });
        } else {
            // Add to selection
            const newEvidence: SelectedEvidence = {
                type,
                id: item.id,
                item,
                relevance_score: 5,
                context_note: '',
                is_key_evidence: false,
                title: type === 'document' ? (item as Document).filename : (item as MediaEvidence).original_filename
            };

            setSelectedEvidence(prev => [...prev, newEvidence]);

            // Initialize config
            const configKey = `${type}_${item.id}`;
            setEvidenceConfig(prev => ({
                ...prev,
                [configKey]: {
                    relevance_score: 5,
                    context_note: '',
                    is_key_evidence: false,
                    title: newEvidence.title || ''
                }
            }));
        }
    };

    const updateEvidenceConfig = (type: 'document' | 'media', id: number, field: string, value: any) => {
        const configKey = `${type}_${id}`;
        setEvidenceConfig(prev => ({
            ...prev,
            [configKey]: {
                ...prev[configKey],
                [field]: value
            }
        }));

        // Update selected evidence
        setSelectedEvidence(prev => prev.map(ev =>
            ev.type === type && ev.id === id
                ? { ...ev, [field]: value }
                : ev
        ));
    };

    const isSelected = (type: 'document' | 'media', id: number): boolean => {
        return selectedEvidence.some(ev => ev.type === type && ev.id === id);
    };

    const getFileIcon = (item: Document | MediaEvidence) => {
        if ('media_type' in item) {
            switch (item.media_type) {
                case 'video': return <VideoIcon />;
                case 'audio': return <AudioIcon />;
                case 'image': return <ImageIcon />;
                default: return <AttachFileIcon />;
            }
        } else {
            switch (item.file_type?.toLowerCase()) {
                case 'pdf': return <DocumentIcon color="error" />;
                case 'doc':
                case 'docx': return <DocumentIcon color="primary" />;
                case 'jpg':
                case 'jpeg':
                case 'png': return <ImageIcon color="success" />;
                default: return <DocumentIcon />;
            }
        }
    };

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const formatDuration = (seconds?: number): string => {
        if (!seconds) return '';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const handleConfirm = () => {
        // Apply configurations to selected evidence
        const finalEvidence = selectedEvidence.map(ev => {
            const configKey = `${ev.type}_${ev.id}`;
            const config = evidenceConfig[configKey];

            return {
                ...ev,
                ...config
            };
        });

        onConfirm(finalEvidence);
    };

    const renderDocumentItem = (doc: Document) => {
        const selected = isSelected('document', doc.id);
        const configKey = `document_${doc.id}`;
        const config = evidenceConfig[configKey];

        return (
            <Card key={doc.id} sx={{ mb: 1, border: selected ? '2px solid #1976D2' : '1px solid #e0e0e0' }}>
                <CardContent sx={{ p: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                        <Checkbox
                            checked={selected}
                            onChange={() => handleEvidenceToggle('document', doc)}
                            icon={<RadioButtonUncheckedIcon />}
                            checkedIcon={<CheckCircleIcon />}
                        />

                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {getFileIcon(doc)}
                            {doc.is_confidential && <LockIcon fontSize="small" color="warning" />}
                        </Box>

                        <Box sx={{ flex: 1 }}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                                {doc.filename}
                            </Typography>

                            <Box sx={{ display: 'flex', gap: 1, mt: 0.5, mb: 1 }}>
                                <Chip size="small" label={doc.file_type?.toUpperCase()} />
                                <Chip size="small" label={formatFileSize(doc.file_size)} />
                                <Chip
                                    size="small"
                                    label={format(parseISO(doc.upload_date), 'MMM dd, yyyy')}
                                    variant="outlined"
                                />
                            </Box>

                            {doc.ai_summary && (
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                    {doc.ai_summary.substring(0, 150)}...
                                </Typography>
                            )}

                            {doc.tags && doc.tags.length > 0 && (
                                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                                    {doc.tags.map(tag => (
                                        <Chip key={tag} size="small" label={tag} variant="outlined" />
                                    ))}
                                </Box>
                            )}
                        </Box>

                        <Box sx={{ display: 'flex', gap: 1 }}>
                            <Tooltip title="View Document">
                                <IconButton size="small">
                                    <ViewIcon />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Download">
                                <IconButton size="small">
                                    <DownloadIcon />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    </Box>

                    {selected && config && (
                        <Box sx={{ mt: 2, p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                            <Grid container spacing={2}>
                                <Grid item xs={12}>
                                    <TextField
                                        fullWidth
                                        size="small"
                                        label="Evidence Title"
                                        value={config.title}
                                        onChange={(e) => updateEvidenceConfig('document', doc.id, 'title', e.target.value)}
                                    />
                                </Grid>
                                <Grid item xs={12}>
                                    <TextField
                                        fullWidth
                                        multiline
                                        rows={2}
                                        size="small"
                                        label="Context Note"
                                        placeholder="How does this evidence relate to the event?"
                                        value={config.context_note}
                                        onChange={(e) => updateEvidenceConfig('document', doc.id, 'context_note', e.target.value)}
                                    />
                                </Grid>
                                <Grid item xs={8}>
                                    <Typography gutterBottom>Relevance Score: {config.relevance_score}/10</Typography>
                                    <Slider
                                        value={config.relevance_score}
                                        onChange={(_, value) => updateEvidenceConfig('document', doc.id, 'relevance_score', value)}
                                        min={1}
                                        max={10}
                                        marks
                                        step={1}
                                        valueLabelDisplay="auto"
                                    />
                                </Grid>
                                <Grid item xs={4}>
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={config.is_key_evidence}
                                                onChange={(e) => updateEvidenceConfig('document', doc.id, 'is_key_evidence', e.target.checked)}
                                            />
                                        }
                                        label="Key Evidence"
                                    />
                                </Grid>
                            </Grid>
                        </Box>
                    )}
                </CardContent>
            </Card>
        );
    };

    const renderMediaItem = (media: MediaEvidence) => {
        const selected = isSelected('media', media.id);
        const configKey = `media_${media.id}`;
        const config = evidenceConfig[configKey];

        return (
            <Card key={media.id} sx={{ mb: 1, border: selected ? '2px solid #1976D2' : '1px solid #e0e0e0' }}>
                <CardContent sx={{ p: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                        <Checkbox
                            checked={selected}
                            onChange={() => handleEvidenceToggle('media', media)}
                            icon={<RadioButtonUncheckedIcon />}
                            checkedIcon={<CheckCircleIcon />}
                        />

                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {getFileIcon(media)}
                            {media.is_confidential && <LockIcon fontSize="small" color="warning" />}
                        </Box>

                        {media.thumbnail_path && (
                            <Avatar
                                src={media.thumbnail_path}
                                variant="rounded"
                                sx={{ width: 60, height: 60 }}
                            />
                        )}

                        <Box sx={{ flex: 1 }}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                                {media.original_filename}
                            </Typography>

                            <Box sx={{ display: 'flex', gap: 1, mt: 0.5, mb: 1 }}>
                                <Chip size="small" label={media.media_type.toUpperCase()} />
                                <Chip size="small" label={media.evidence_type} />
                                <Chip size="small" label={formatFileSize(media.file_size)} />
                                {media.duration && (
                                    <Chip
                                        size="small"
                                        icon={<ScheduleIcon />}
                                        label={formatDuration(media.duration)}
                                    />
                                )}
                            </Box>

                            <Typography variant="caption" color="text.secondary">
                                Uploaded {format(parseISO(media.uploaded_at), 'MMM dd, yyyy')} by {media.uploaded_by}
                            </Typography>

                            {media.transcription && (
                                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                                    <strong>Transcription:</strong> {media.transcription.substring(0, 100)}...
                                </Typography>
                            )}
                        </Box>

                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                            <Tooltip title="Preview">
                                <IconButton size="small">
                                    <PlayIcon />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Download">
                                <IconButton size="small">
                                    <DownloadIcon />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    </Box>

                    {selected && config && (
                        <Box sx={{ mt: 2, p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                            <Grid container spacing={2}>
                                <Grid item xs={12}>
                                    <TextField
                                        fullWidth
                                        size="small"
                                        label="Evidence Title"
                                        value={config.title}
                                        onChange={(e) => updateEvidenceConfig('media', media.id, 'title', e.target.value)}
                                    />
                                </Grid>
                                <Grid item xs={12}>
                                    <TextField
                                        fullWidth
                                        multiline
                                        rows={2}
                                        size="small"
                                        label="Context Note"
                                        placeholder="How does this evidence relate to the event?"
                                        value={config.context_note}
                                        onChange={(e) => updateEvidenceConfig('media', media.id, 'context_note', e.target.value)}
                                    />
                                </Grid>
                                <Grid item xs={8}>
                                    <Typography gutterBottom>Relevance Score: {config.relevance_score}/10</Typography>
                                    <Slider
                                        value={config.relevance_score}
                                        onChange={(_, value) => updateEvidenceConfig('media', media.id, 'relevance_score', value)}
                                        min={1}
                                        max={10}
                                        marks
                                        step={1}
                                        valueLabelDisplay="auto"
                                    />
                                </Grid>
                                <Grid item xs={4}>
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={config.is_key_evidence}
                                                onChange={(e) => updateEvidenceConfig('media', media.id, 'is_key_evidence', e.target.checked)}
                                            />
                                        }
                                        label="Key Evidence"
                                    />
                                </Grid>
                            </Grid>
                        </Box>
                    )}
                </CardContent>
            </Card>
        );
    };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="lg"
            fullWidth
            PaperProps={{ sx: { height: '90vh' } }}
        >
            <DialogTitle>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                        <Typography variant="h6">Pin Evidence to Event</Typography>
                        <Typography variant="body2" color="text.secondary">
                            {eventTitle} • {format(parseISO(eventDate), 'MMM dd, yyyy')}
                        </Typography>
                    </Box>
                    <Badge badgeContent={selectedEvidence.length} color="primary">
                        <AttachFileIcon />
                    </Badge>
                </Box>
            </DialogTitle>

            <DialogContent sx={{ p: 0 }}>
                {/* Filters */}
                <Paper sx={{ p: 2, m: 2, mb: 0 }}>
                    <Grid container spacing={2} alignItems="center">
                        <Grid item xs={12} md={4}>
                            <TextField
                                fullWidth
                                size="small"
                                placeholder="Search evidence..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                InputProps={{
                                    startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
                                }}
                            />
                        </Grid>
                        <Grid item xs={6} md={2}>
                            <FormControl fullWidth size="small">
                                <InputLabel>File Type</InputLabel>
                                <Select
                                    value={fileTypeFilter}
                                    onChange={(e) => setFileTypeFilter(e.target.value)}
                                    label="File Type"
                                >
                                    <MenuItem value="all">All Types</MenuItem>
                                    <MenuItem value="pdf">PDF</MenuItem>
                                    <MenuItem value="doc">Word</MenuItem>
                                    <MenuItem value="video">Video</MenuItem>
                                    <MenuItem value="audio">Audio</MenuItem>
                                    <MenuItem value="image">Image</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={6} md={2}>
                            <FormControl fullWidth size="small">
                                <InputLabel>Access</InputLabel>
                                <Select
                                    value={confidentialFilter}
                                    onChange={(e) => setConfidentialFilter(e.target.value)}
                                    label="Access"
                                >
                                    <MenuItem value="all">All</MenuItem>
                                    <MenuItem value="public">Public</MenuItem>
                                    <MenuItem value="confidential">Confidential</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={6} md={2}>
                            <FormControl fullWidth size="small">
                                <InputLabel>Date</InputLabel>
                                <Select
                                    value={dateFilter}
                                    onChange={(e) => setDateFilter(e.target.value)}
                                    label="Date"
                                >
                                    <MenuItem value="all">All Time</MenuItem>
                                    <MenuItem value="today">Today</MenuItem>
                                    <MenuItem value="week">This Week</MenuItem>
                                    <MenuItem value="month">This Month</MenuItem>
                                    <MenuItem value="year">This Year</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={6} md={2}>
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={showOnlyUnpinned}
                                        onChange={(e) => setShowOnlyUnpinned(e.target.checked)}
                                    />
                                }
                                label="Unpinned Only"
                            />
                        </Grid>
                    </Grid>
                </Paper>

                {/* Tabs */}
                <Box sx={{ borderBottom: 1, borderColor: 'divider', mx: 2 }}>
                    <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
                        <Tab
                            label={`Documents (${filteredDocuments.length})`}
                            icon={<DocumentIcon />}
                            iconPosition="start"
                        />
                        <Tab
                            label={`Media (${filteredMedia.length})`}
                            icon={<VideoIcon />}
                            iconPosition="start"
                        />
                    </Tabs>
                </Box>

                {/* Content */}
                <Box sx={{ p: 2, height: 'calc(100% - 120px)', overflow: 'auto' }}>
                    {loading ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 200 }}>
                            <CircularProgress />
                        </Box>
                    ) : error ? (
                        <Alert severity="error">{error}</Alert>
                    ) : (
                        <>
                            {activeTab === 0 && (
                                <Box>
                                    {filteredDocuments.length === 0 ? (
                                        <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                                            No documents found matching your criteria
                                        </Typography>
                                    ) : (
                                        filteredDocuments.map(renderDocumentItem)
                                    )}
                                </Box>
                            )}

                            {activeTab === 1 && (
                                <Box>
                                    {filteredMedia.length === 0 ? (
                                        <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                                            No media evidence found matching your criteria
                                        </Typography>
                                    ) : (
                                        filteredMedia.map(renderMediaItem)
                                    )}
                                </Box>
                            )}
                        </>
                    )}
                </Box>
            </DialogContent>

            <DialogActions sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                    <Typography variant="body2" color="text.secondary">
                        {selectedEvidence.length} evidence item{selectedEvidence.length !== 1 ? 's' : ''} selected
                    </Typography>

                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button onClick={onClose}>Cancel</Button>
                        <Button
                            onClick={handleConfirm}
                            variant="contained"
                            disabled={selectedEvidence.length === 0}
                            startIcon={<AttachFileIcon />}
                        >
                            Pin Evidence ({selectedEvidence.length})
                        </Button>
                    </Box>
                </Box>
            </DialogActions>
        </Dialog>
    );
};
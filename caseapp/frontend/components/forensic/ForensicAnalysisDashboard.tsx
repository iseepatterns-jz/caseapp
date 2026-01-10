/**
 * Forensic Analysis Dashboard for Email and Text Message Analysis
 */

import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    Grid,
    Card,
    CardContent,
    Button,
    IconButton,
    Chip,
    LinearProgress,
    Alert,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    ListItemSecondaryAction,
    Divider,
    Tooltip,
    Badge,
    CircularProgress,
    Tabs,
    Tab,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TablePagination
} from '@mui/material';
import {
    Upload as UploadIcon,
    Email as EmailIcon,
    Sms as SmsIcon,
    Phone as PhoneIcon,
    ContactPhone as ContactIcon,
    Timeline as TimelineIcon,
    NetworkCheck as NetworkIcon,
    Warning as WarningIcon,
    Flag as FlagIcon,
    Search as SearchIcon,
    FilterList as FilterIcon,
    GetApp as DownloadIcon,
    Visibility as ViewIcon,
    Delete as DeleteIcon,
    Security as SecurityIcon,
    Psychology as PsychologyIcon,
    TrendingUp as TrendingUpIcon,
    TrendingDown as TrendingDownIcon,
    Remove as NeutralIcon,
    AttachFile as AttachFileIcon,
    Schedule as ScheduleIcon,
    Person as PersonIcon,
    Group as GroupIcon
} from '@mui/icons-material';
import { format, parseISO } from 'date-fns';
import {
    LineChart,
    Line,
    AreaChart,
    Area,
    BarChart,
    Bar,
    PieChart,
    Pie,
    Cell,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip as RechartsTooltip,
    Legend,
    ResponsiveContainer,
    ScatterChart,
    Scatter
} from 'recharts';

// Types
interface ForensicSource {
    id: number;
    case_id: number;
    source_name: string;
    source_type: string;
    file_size: number;
    analysis_status: 'pending' | 'processing' | 'completed' | 'failed';
    analysis_progress: number;
    created_at: string;
    device_info?: any;
    total_items?: number;
}

interface ForensicItem {
    id: number;
    item_type: 'email' | 'sms' | 'imessage' | 'whatsapp' | 'call_log';
    timestamp: string;
    sender: string;
    recipients: string[];
    subject?: string;
    content: string;
    sentiment_score?: number;
    relevance_score: number;
    is_flagged: boolean;
    is_suspicious: boolean;
    is_deleted: boolean;
    attachments?: any[];
    keywords?: string[];
    entities?: any[];
}

interface AnalysisReport {
    id: number;
    title: string;
    total_items: number;
    date_range_start: string;
    date_range_end: string;
    statistics: any;
    insights: any[];
    charts_data: any;
    network_data: any;
    created_at: string;
}

interface ForensicAnalysisDashboardProps {
    caseId: number;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

export const ForensicAnalysisDashboard: React.FC<ForensicAnalysisDashboardProps> = ({
    caseId
}) => {
    const [activeTab, setActiveTab] = useState(0);
    const [sources, setSources] = useState<ForensicSource[]>([]);
    const [selectedSource, setSelectedSource] = useState<ForensicSource | null>(null);
    const [items, setItems] = useState<ForensicItem[]>([]);
    const [reports, setReports] = useState<AnalysisReport[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Upload dialog
    const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
    const [uploadFile, setUploadFile] = useState<File | null>(null);
    const [sourceName, setSourceName] = useState('');
    const [sourceType, setSourceType] = useState('');

    // Search and filters
    const [searchQuery, setSearchQuery] = useState('');
    const [itemTypeFilter, setItemTypeFilter] = useState('all');
    const [sentimentFilter, setSentimentFilter] = useState('all');
    const [flaggedOnly, setFlaggedOnly] = useState(false);

    // Pagination
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(25);

    useEffect(() => {
        loadForensicSources();
    }, [caseId]);

    useEffect(() => {
        if (selectedSource) {
            loadForensicItems();
            loadAnalysisReports();
        }
    }, [selectedSource, searchQuery, itemTypeFilter, sentimentFilter, flaggedOnly]);

    const loadForensicSources = async () => {
        setLoading(true);
        try {
            const response = await fetch(`/api/v1/forensic/sources/${caseId}`);
            if (response.ok) {
                const data = await response.json();
                setSources(data);
                if (data.length > 0 && !selectedSource) {
                    setSelectedSource(data[0]);
                }
            } else {
                setError('Failed to load forensic sources');
            }
        } catch (err) {
            setError('Error loading forensic sources');
        } finally {
            setLoading(false);
        }
    };

    const loadForensicItems = async () => {
        if (!selectedSource) return;

        setLoading(true);
        try {
            const params = new URLSearchParams({
                case_id: caseId.toString(),
                limit: rowsPerPage.toString(),
                offset: (page * rowsPerPage).toString()
            });

            if (searchQuery) params.append('query', searchQuery);
            if (itemTypeFilter !== 'all') params.append('item_types', itemTypeFilter);
            if (sentimentFilter !== 'all') params.append('sentiment_range', sentimentFilter);

            const response = await fetch(`/api/v1/forensic/items/search?${params}`);
            if (response.ok) {
                const data = await response.json();
                setItems(data.items);
            } else {
                setError('Failed to load forensic items');
            }
        } catch (err) {
            setError('Error loading forensic items');
        } finally {
            setLoading(false);
        }
    };

    const loadAnalysisReports = async () => {
        if (!selectedSource) return;

        try {
            const response = await fetch(`/api/v1/forensic/reports/${selectedSource.id}`);
            if (response.ok) {
                const data = await response.json();
                setReports(data);
            }
        } catch (err) {
            console.error('Error loading reports:', err);
        }
    };

    const handleUploadFile = async () => {
        if (!uploadFile || !sourceName || !sourceType) return;

        setLoading(true);
        try {
            const formData = new FormData();
            formData.append('file', uploadFile);
            formData.append('case_id', caseId.toString());
            formData.append('source_name', sourceName);
            formData.append('source_type', sourceType);

            const response = await fetch('/api/v1/forensic/upload', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                setUploadDialogOpen(false);
                setUploadFile(null);
                setSourceName('');
                setSourceType('');
                loadForensicSources();
            } else {
                setError('Failed to upload forensic data');
            }
        } catch (err) {
            setError('Error uploading file');
        } finally {
            setLoading(false);
        }
    };

    const handleFlagItem = async (itemId: number, flagged: boolean, reason?: string) => {
        try {
            const response = await fetch(`/api/v1/forensic/items/${itemId}/flag`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    is_flagged: flagged,
                    reason: reason || '',
                    is_suspicious: flagged
                })
            });

            if (response.ok) {
                loadForensicItems();
            } else {
                setError('Failed to flag item');
            }
        } catch (err) {
            setError('Error flagging item');
        }
    };

    const getItemTypeIcon = (type: string) => {
        switch (type) {
            case 'email': return <EmailIcon />;
            case 'sms': return <SmsIcon />;
            case 'imessage': return <SmsIcon color="primary" />;
            case 'whatsapp': return <SmsIcon color="success" />;
            case 'call_log': return <PhoneIcon />;
            default: return <AttachFileIcon />;
        }
    };

    const getSentimentIcon = (score?: number) => {
        if (!score) return <NeutralIcon />;
        if (score > 0.1) return <TrendingUpIcon color="success" />;
        if (score < -0.1) return <TrendingDownIcon color="error" />;
        return <NeutralIcon />;
    };

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const renderSourcesTab = () => (
        <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h6">Forensic Data Sources</Typography>
                <Button
                    variant="contained"
                    startIcon={<UploadIcon />}
                    onClick={() => setUploadDialogOpen(true)}
                >
                    Upload Data
                </Button>
            </Box>

            <Grid container spacing={2}>
                {sources.map((source) => (
                    <Grid item xs={12} md={6} lg={4} key={source.id}>
                        <Card
                            sx={{
                                cursor: 'pointer',
                                border: selectedSource?.id === source.id ? '2px solid #1976D2' : '1px solid #e0e0e0',
                                '&:hover': { boxShadow: 3 }
                            }}
                            onClick={() => setSelectedSource(source)}
                        >
                            <CardContent>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                                    <Typography variant="h6" component="h3">
                                        {source.source_name}
                                    </Typography>
                                    <Chip
                                        label={source.analysis_status}
                                        color={
                                            source.analysis_status === 'completed' ? 'success' :
                                                source.analysis_status === 'processing' ? 'warning' :
                                                    source.analysis_status === 'failed' ? 'error' : 'default'
                                        }
                                        size="small"
                                    />
                                </Box>

                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                    Type: {source.source_type}
                                </Typography>

                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                    Size: {formatFileSize(source.file_size)}
                                </Typography>

                                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                    Uploaded: {format(parseISO(source.created_at), 'MMM dd, yyyy')}
                                </Typography>

                                {source.analysis_status === 'processing' && (
                                    <Box sx={{ mb: 2 }}>
                                        <Typography variant="body2" sx={{ mb: 1 }}>
                                            Analysis Progress: {Math.round(source.analysis_progress)}%
                                        </Typography>
                                        <LinearProgress variant="determinate" value={source.analysis_progress} />
                                    </Box>
                                )}

                                {source.total_items && (
                                    <Typography variant="body2" color="primary">
                                        {source.total_items} items analyzed
                                    </Typography>
                                )}
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>
        </Box>
    );

    const renderAnalysisTab = () => {
        if (!selectedSource || reports.length === 0) {
            return (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                    <Typography variant="h6" color="text.secondary">
                        {!selectedSource ? 'Select a data source to view analysis' : 'No analysis reports available'}
                    </Typography>
                </Box>
            );
        }

        const report = reports[0]; // Use the latest report

        return (
            <Box>
                <Typography variant="h6" gutterBottom>
                    Analysis Report: {report.title}
                </Typography>

                {/* Statistics Cards */}
                <Grid container spacing={2} sx={{ mb: 4 }}>
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent sx={{ textAlign: 'center' }}>
                                <Typography variant="h4" color="primary">
                                    {report.total_items}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Total Items
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>

                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent sx={{ textAlign: 'center' }}>
                                <Typography variant="h4" color="success.main">
                                    {report.statistics?.flagged_items || 0}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Flagged Items
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>

                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent sx={{ textAlign: 'center' }}>
                                <Typography variant="h4" color="warning.main">
                                    {report.statistics?.suspicious_items || 0}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Suspicious Items
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>

                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent sx={{ textAlign: 'center' }}>
                                <Typography variant="h4" color="error.main">
                                    {report.statistics?.deleted_items || 0}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Deleted Items
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                {/* Charts */}
                <Grid container spacing={3}>
                    {/* Communication Volume Chart */}
                    <Grid item xs={12} md={6}>
                        <Paper sx={{ p: 2 }}>
                            <Typography variant="h6" gutterBottom>
                                Communication Volume Over Time
                            </Typography>
                            <ResponsiveContainer width="100%" height={300}>
                                <AreaChart data={report.charts_data?.communication_volume || []}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="date" />
                                    <YAxis />
                                    <RechartsTooltip />
                                    <Area type="monotone" dataKey="count" stroke="#8884d8" fill="#8884d8" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </Paper>
                    </Grid>

                    {/* Message Types Distribution */}
                    <Grid item xs={12} md={6}>
                        <Paper sx={{ p: 2 }}>
                            <Typography variant="h6" gutterBottom>
                                Message Types Distribution
                            </Typography>
                            <ResponsiveContainer width="100%" height={300}>
                                <PieChart>
                                    <Pie
                                        data={Object.entries(report.statistics?.by_type || {}).map(([type, count]) => ({
                                            name: type,
                                            value: count
                                        }))}
                                        cx="50%"
                                        cy="50%"
                                        labelLine={false}
                                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                        outerRadius={80}
                                        fill="#8884d8"
                                        dataKey="value"
                                    >
                                        {Object.entries(report.statistics?.by_type || {}).map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <RechartsTooltip />
                                </PieChart>
                            </ResponsiveContainer>
                        </Paper>
                    </Grid>

                    {/* Activity by Hour */}
                    <Grid item xs={12}>
                        <Paper sx={{ p: 2 }}>
                            <Typography variant="h6" gutterBottom>
                                Activity by Hour of Day
                            </Typography>
                            <ResponsiveContainer width="100%" height={300}>
                                <BarChart data={report.statistics?.by_hour?.map((count, hour) => ({
                                    hour: `${hour}:00`,
                                    count
                                })) || []}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="hour" />
                                    <YAxis />
                                    <RechartsTooltip />
                                    <Bar dataKey="count" fill="#8884d8" />
                                </BarChart>
                            </ResponsiveContainer>
                        </Paper>
                    </Grid>
                </Grid>

                {/* Insights */}
                {report.insights && report.insights.length > 0 && (
                    <Paper sx={{ p: 2, mt: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            AI Insights
                        </Typography>
                        {report.insights.map((insight, index) => (
                            <Alert
                                key={index}
                                severity={insight.severity === 'high' ? 'error' : insight.severity === 'warning' ? 'warning' : 'info'}
                                sx={{ mb: 1 }}
                            >
                                <Typography variant="subtitle2">{insight.title}</Typography>
                                <Typography variant="body2">{insight.description}</Typography>
                            </Alert>
                        ))}
                    </Paper>
                )}
            </Box>
        );
    };

    const renderItemsTab = () => (
        <Box>
            {/* Search and Filters */}
            <Paper sx={{ p: 2, mb: 3 }}>
                <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} md={4}>
                        <TextField
                            fullWidth
                            size="small"
                            placeholder="Search messages..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            InputProps={{
                                startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
                            }}
                        />
                    </Grid>
                    <Grid item xs={6} md={2}>
                        <FormControl fullWidth size="small">
                            <InputLabel>Type</InputLabel>
                            <Select
                                value={itemTypeFilter}
                                onChange={(e) => setItemTypeFilter(e.target.value)}
                                label="Type"
                            >
                                <MenuItem value="all">All Types</MenuItem>
                                <MenuItem value="email">Email</MenuItem>
                                <MenuItem value="sms">SMS</MenuItem>
                                <MenuItem value="imessage">iMessage</MenuItem>
                                <MenuItem value="whatsapp">WhatsApp</MenuItem>
                                <MenuItem value="call_log">Call Log</MenuItem>
                            </Select>
                        </FormControl>
                    </Grid>
                    <Grid item xs={6} md={2}>
                        <FormControl fullWidth size="small">
                            <InputLabel>Sentiment</InputLabel>
                            <Select
                                value={sentimentFilter}
                                onChange={(e) => setSentimentFilter(e.target.value)}
                                label="Sentiment"
                            >
                                <MenuItem value="all">All</MenuItem>
                                <MenuItem value="positive">Positive</MenuItem>
                                <MenuItem value="negative">Negative</MenuItem>
                                <MenuItem value="neutral">Neutral</MenuItem>
                            </Select>
                        </FormControl>
                    </Grid>
                    <Grid item xs={12} md={4}>
                        <Button
                            variant={flaggedOnly ? 'contained' : 'outlined'}
                            onClick={() => setFlaggedOnly(!flaggedOnly)}
                            startIcon={<FlagIcon />}
                            size="small"
                        >
                            Flagged Only
                        </Button>
                    </Grid>
                </Grid>
            </Paper>

            {/* Items Table */}
            <TableContainer component={Paper}>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>Type</TableCell>
                            <TableCell>Date/Time</TableCell>
                            <TableCell>From/To</TableCell>
                            <TableCell>Subject/Preview</TableCell>
                            <TableCell>Sentiment</TableCell>
                            <TableCell>Relevance</TableCell>
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {items.map((item) => (
                            <TableRow key={item.id}>
                                <TableCell>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        {getItemTypeIcon(item.item_type)}
                                        <Typography variant="body2">
                                            {item.item_type.toUpperCase()}
                                        </Typography>
                                        {item.is_flagged && <FlagIcon color="warning" fontSize="small" />}
                                        {item.is_suspicious && <WarningIcon color="error" fontSize="small" />}
                                        {item.is_deleted && <DeleteIcon color="action" fontSize="small" />}
                                    </Box>
                                </TableCell>
                                <TableCell>
                                    <Typography variant="body2">
                                        {format(parseISO(item.timestamp), 'MMM dd, yyyy')}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {format(parseISO(item.timestamp), 'h:mm a')}
                                    </Typography>
                                </TableCell>
                                <TableCell>
                                    <Typography variant="body2">
                                        From: {item.sender || 'Unknown'}
                                    </Typography>
                                    {item.recipients && item.recipients.length > 0 && (
                                        <Typography variant="caption" color="text.secondary">
                                            To: {item.recipients.join(', ')}
                                        </Typography>
                                    )}
                                </TableCell>
                                <TableCell>
                                    {item.subject && (
                                        <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 0.5 }}>
                                            {item.subject}
                                        </Typography>
                                    )}
                                    <Typography variant="body2" color="text.secondary">
                                        {(item.content || '').substring(0, 100)}...
                                    </Typography>
                                    {item.attachments && item.attachments.length > 0 && (
                                        <Chip
                                            size="small"
                                            icon={<AttachFileIcon />}
                                            label={`${item.attachments.length} attachment${item.attachments.length > 1 ? 's' : ''}`}
                                            sx={{ mt: 0.5 }}
                                        />
                                    )}
                                </TableCell>
                                <TableCell>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        {getSentimentIcon(item.sentiment_score)}
                                        <Typography variant="body2">
                                            {item.sentiment_score ? item.sentiment_score.toFixed(2) : 'N/A'}
                                        </Typography>
                                    </Box>
                                </TableCell>
                                <TableCell>
                                    <LinearProgress
                                        variant="determinate"
                                        value={item.relevance_score * 100}
                                        sx={{ width: 60 }}
                                    />
                                    <Typography variant="caption">
                                        {(item.relevance_score * 100).toFixed(0)}%
                                    </Typography>
                                </TableCell>
                                <TableCell>
                                    <Box sx={{ display: 'flex', gap: 1 }}>
                                        <Tooltip title="View Details">
                                            <IconButton size="small">
                                                <ViewIcon />
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title={item.is_flagged ? "Unflag" : "Flag"}>
                                            <IconButton
                                                size="small"
                                                onClick={() => handleFlagItem(item.id, !item.is_flagged)}
                                            >
                                                <FlagIcon color={item.is_flagged ? "warning" : "action"} />
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title="Pin to Timeline">
                                            <IconButton size="small">
                                                <TimelineIcon />
                                            </IconButton>
                                        </Tooltip>
                                    </Box>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>

                <TablePagination
                    rowsPerPageOptions={[25, 50, 100]}
                    component="div"
                    count={-1} // We don't have total count from API
                    rowsPerPage={rowsPerPage}
                    page={page}
                    onPageChange={(_, newPage) => setPage(newPage)}
                    onRowsPerPageChange={(e) => {
                        setRowsPerPage(parseInt(e.target.value, 10));
                        setPage(0);
                    }}
                />
            </TableContainer>
        </Box>
    );

    return (
        <Box sx={{ p: 3 }}>
            <Typography variant="h4" gutterBottom>
                Forensic Analysis Dashboard
            </Typography>

            <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)} sx={{ mb: 3 }}>
                <Tab label="Data Sources" icon={<SecurityIcon />} iconPosition="start" />
                <Tab label="Analysis" icon={<PsychologyIcon />} iconPosition="start" />
                <Tab label="Items" icon={<SearchIcon />} iconPosition="start" />
                <Tab label="Network" icon={<NetworkIcon />} iconPosition="start" />
                <Tab label="Timeline" icon={<TimelineIcon />} iconPosition="start" />
            </Tabs>

            {loading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
                    <CircularProgress />
                </Box>
            )}

            {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                    {error}
                </Alert>
            )}

            {activeTab === 0 && renderSourcesTab()}
            {activeTab === 1 && renderAnalysisTab()}
            {activeTab === 2 && renderItemsTab()}
            {activeTab === 3 && (
                <Typography variant="h6" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                    Network Analysis Coming Soon
                </Typography>
            )}
            {activeTab === 4 && (
                <Typography variant="h6" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                    Forensic Timeline Coming Soon
                </Typography>
            )}

            {/* Upload Dialog */}
            <Dialog open={uploadDialogOpen} onClose={() => setUploadDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Upload Forensic Data</DialogTitle>
                <DialogContent>
                    <Box sx={{ mt: 2 }}>
                        <TextField
                            fullWidth
                            label="Source Name"
                            value={sourceName}
                            onChange={(e) => setSourceName(e.target.value)}
                            sx={{ mb: 2 }}
                        />

                        <FormControl fullWidth sx={{ mb: 2 }}>
                            <InputLabel>Source Type</InputLabel>
                            <Select
                                value={sourceType}
                                onChange={(e) => setSourceType(e.target.value)}
                                label="Source Type"
                            >
                                <MenuItem value="iphone_backup">iPhone Backup</MenuItem>
                                <MenuItem value="android_backup">Android Backup</MenuItem>
                                <MenuItem value="email_archive">Email Archive</MenuItem>
                                <MenuItem value="whatsapp_db">WhatsApp Database</MenuItem>
                                <MenuItem value="generic_db">Generic Database</MenuItem>
                            </Select>
                        </FormControl>

                        <Button
                            variant="outlined"
                            component="label"
                            fullWidth
                            sx={{ mb: 2 }}
                        >
                            {uploadFile ? uploadFile.name : 'Select File'}
                            <input
                                type="file"
                                hidden
                                accept=".db,.sqlite,.sqlite3,.mbox,.eml,.pst,.zip"
                                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                            />
                        </Button>

                        <Alert severity="info">
                            Supported formats: .db, .sqlite, .mbox, .eml, .pst, .zip
                            <br />
                            Maximum file size: 1GB
                        </Alert>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setUploadDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={handleUploadFile}
                        variant="contained"
                        disabled={!uploadFile || !sourceName || !sourceType}
                    >
                        Upload & Analyze
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};
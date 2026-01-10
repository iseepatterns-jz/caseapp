/**
 * Timeline Builder Component for Case Management
 * Allows building visual timelines and pinning evidence to events
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
    Box,
    Paper,
    Typography,
    Button,
    IconButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Chip,
    Tooltip,
    Menu,
    MenuList,
    MenuItem as MuiMenuItem,
    Divider,
    Alert,
    CircularProgress,
    Grid,
    Card,
    CardContent,
    Badge,
    Fab,
    Zoom,
    Slide
} from '@mui/material';
import {
    Timeline,
    TimelineItem,
    TimelineSeparator,
    TimelineConnector,
    TimelineContent,
    TimelineDot,
    TimelineOppositeContent
} from '@mui/lab';
import {
    Add as AddIcon,
    Edit as EditIcon,
    Delete as DeleteIcon,
    AttachFile as AttachFileIcon,
    VideoFile as VideoIcon,
    AudioFile as AudioIcon,
    Image as ImageIcon,
    Description as DocumentIcon,
    Star as StarIcon,
    StarBorder as StarBorderIcon,
    FilterList as FilterIcon,
    Search as SearchIcon,
    Export as ExportIcon,
    AutoAwesome as AutoDetectIcon,
    Timeline as TimelineIcon,
    Event as EventIcon,
    Gavel as GavelIcon,
    Assignment as AssignmentIcon,
    RecordVoiceOver as DepositionIcon,
    AccountBalance as CourtIcon,
    Handshake as SettlementIcon,
    Appeal as AppealIcon
} from '@mui/icons-material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format, parseISO, isValid } from 'date-fns';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';

// Types
interface TimelineEvent {
    id: number;
    title: string;
    description?: string;
    event_type: string;
    event_date: string;
    end_date?: string;
    location?: string;
    participants?: string[];
    importance: 'low' | 'medium' | 'high' | 'critical';
    status: 'draft' | 'confirmed' | 'disputed' | 'verified';
    has_evidence: boolean;
    evidence_count: number;
    evidence_pins?: EvidencePin[];
    color?: string;
    icon?: string;
    legal_significance?: string;
    outcome?: string;
}

interface EvidencePin {
    id: number;
    timeline_event_id: number;
    document_id?: number;
    media_evidence_id?: number;
    title?: string;
    description?: string;
    context_note?: string;
    relevance_score: number;
    is_key_evidence: boolean;
    is_confidential: boolean;
    document?: any;
    media_evidence?: any;
}

interface CaseTimeline {
    id: number;
    case_id: number;
    title: string;
    description?: string;
    is_primary: boolean;
    events: TimelineEvent[];
}

interface TimelineBuilderProps {
    caseId: number;
    timelineId?: number;
    onTimelineChange?: (timeline: CaseTimeline) => void;
}

const eventTypeIcons = {
    incident: <EventIcon />,
    filing: <AssignmentIcon />,
    hearing: <GavelIcon />,
    deposition: <DepositionIcon />,
    discovery: <SearchIcon />,
    motion: <AssignmentIcon />,
    settlement: <SettlementIcon />,
    verdict: <GavelIcon />,
    appeal: <AppealIcon />,
    evidence: <AttachFileIcon />,
    witness: <RecordVoiceOver />,
    communication: <Description />,
    deadline: <Event />,
    milestone: <Star />,
    custom: <Event />
};

const importanceColors = {
    low: '#90CAF9',
    medium: '#42A5F5',
    high: '#FF9800',
    critical: '#F44336'
};

export const TimelineBuilder: React.FC<TimelineBuilderProps> = ({
    caseId,
    timelineId,
    onTimelineChange
}) => {
    const [timeline, setTimeline] = useState<CaseTimeline | null>(null);
    const [events, setEvents] = useState<TimelineEvent[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Dialog states
    const [eventDialogOpen, setEventDialogOpen] = useState(false);
    const [evidencePinDialogOpen, setEvidencePinDialogOpen] = useState(false);
    const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);
    const [editingEvent, setEditingEvent] = useState<Partial<TimelineEvent>>({});

    // Filter and search states
    const [searchQuery, setSearchQuery] = useState('');
    const [filterType, setFilterType] = useState<string>('all');
    const [filterImportance, setFilterImportance] = useState<string>('all');
    const [showEvidenceOnly, setShowEvidenceOnly] = useState(false);

    // Evidence selection
    const [availableDocuments, setAvailableDocuments] = useState([]);
    const [availableMedia, setAvailableMedia] = useState([]);
    const [selectedEvidence, setSelectedEvidence] = useState<any[]>([]);

    // Load timeline data
    useEffect(() => {
        if (timelineId) {
            loadTimeline();
        } else {
            loadCaseTimelines();
        }
    }, [caseId, timelineId]);

    const loadTimeline = async () => {
        setLoading(true);
        try {
            const response = await fetch(`/api/v1/timeline/${timelineId}?include_events=true`);
            if (response.ok) {
                const data = await response.json();
                setTimeline(data);
                setEvents(data.events || []);
                onTimelineChange?.(data);
            } else {
                setError('Failed to load timeline');
            }
        } catch (err) {
            setError('Error loading timeline');
        } finally {
            setLoading(false);
        }
    };

    const loadCaseTimelines = async () => {
        setLoading(true);
        try {
            const response = await fetch(`/api/v1/timeline/case/${caseId}`);
            if (response.ok) {
                const timelines = await response.json();
                if (timelines.length > 0) {
                    const primaryTimeline = timelines.find(t => t.is_primary) || timelines[0];
                    setTimeline(primaryTimeline);
                    setEvents(primaryTimeline.events || []);
                    onTimelineChange?.(primaryTimeline);
                }
            }
        } catch (err) {
            setError('Error loading timelines');
        } finally {
            setLoading(false);
        }
    };

    // Filter events based on search and filters
    const filteredEvents = useMemo(() => {
        return events.filter(event => {
            const matchesSearch = !searchQuery ||
                event.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                event.description?.toLowerCase().includes(searchQuery.toLowerCase());

            const matchesType = filterType === 'all' || event.event_type === filterType;
            const matchesImportance = filterImportance === 'all' || event.importance === filterImportance;
            const matchesEvidence = !showEvidenceOnly || event.has_evidence;

            return matchesSearch && matchesType && matchesImportance && matchesEvidence;
        }).sort((a, b) => new Date(a.event_date).getTime() - new Date(b.event_date).getTime());
    }, [events, searchQuery, filterType, filterImportance, showEvidenceOnly]);

    const handleAddEvent = async () => {
        if (!timeline) return;

        try {
            const response = await fetch(`/api/v1/timeline/${timeline.id}/events`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(editingEvent)
            });

            if (response.ok) {
                const newEvent = await response.json();
                setEvents(prev => [...prev, newEvent]);
                setEventDialogOpen(false);
                setEditingEvent({});
            } else {
                setError('Failed to add event');
            }
        } catch (err) {
            setError('Error adding event');
        }
    };

    const handleUpdateEvent = async (eventId: number) => {
        try {
            const response = await fetch(`/api/v1/timeline/events/${eventId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(editingEvent)
            });

            if (response.ok) {
                const updatedEvent = await response.json();
                setEvents(prev => prev.map(e => e.id === eventId ? updatedEvent : e));
                setEventDialogOpen(false);
                setEditingEvent({});
            } else {
                setError('Failed to update event');
            }
        } catch (err) {
            setError('Error updating event');
        }
    };

    const handlePinEvidence = async (eventId: number, evidenceData: any) => {
        try {
            const response = await fetch(`/api/v1/timeline/events/${eventId}/pin-evidence`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(evidenceData)
            });

            if (response.ok) {
                const pin = await response.json();
                // Update the event with new evidence
                setEvents(prev => prev.map(e =>
                    e.id === eventId
                        ? { ...e, has_evidence: true, evidence_count: e.evidence_count + 1 }
                        : e
                ));
                setEvidencePinDialogOpen(false);
            } else {
                setError('Failed to pin evidence');
            }
        } catch (err) {
            setError('Error pinning evidence');
        }
    };

    const handleAutoDetectEvents = async () => {
        if (!timeline) return;

        setLoading(true);
        try {
            const response = await fetch(`/api/v1/timeline/${timeline.id}/auto-detect-events`, {
                method: 'POST'
            });

            if (response.ok) {
                const data = await response.json();
                // Show suggested events in a dialog or add them automatically
                console.log('Suggested events:', data.suggested_events);
            }
        } catch (err) {
            setError('Error auto-detecting events');
        } finally {
            setLoading(false);
        }
    };

    const renderEventIcon = (event: TimelineEvent) => {
        const IconComponent = eventTypeIcons[event.event_type] || EventIcon;
        return (
            <TimelineDot
                sx={{
                    bgcolor: event.color || importanceColors[event.importance],
                    border: event.has_evidence ? '2px solid #4CAF50' : 'none'
                }}
            >
                {IconComponent}
            </TimelineDot>
        );
    };

    const renderEvidenceChips = (event: TimelineEvent) => {
        if (!event.evidence_pins || event.evidence_pins.length === 0) return null;

        return (
            <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {event.evidence_pins.map((pin) => (
                    <Chip
                        key={pin.id}
                        size="small"
                        icon={pin.document_id ? <DocumentIcon /> :
                            pin.media_evidence?.media_type === 'video' ? <VideoIcon /> :
                                pin.media_evidence?.media_type === 'audio' ? <AudioIcon /> :
                                    <ImageIcon />}
                        label={pin.title || 'Evidence'}
                        color={pin.is_key_evidence ? 'primary' : 'default'}
                        variant={pin.is_confidential ? 'filled' : 'outlined'}
                        sx={{ fontSize: '0.7rem' }}
                    />
                ))}
            </Box>
        );
    };

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <CircularProgress />
            </Box>
        );
    }

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns}>
            <Box sx={{ p: 2 }}>
                {/* Header */}
                <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="h5" component="h2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <TimelineIcon />
                        {timeline?.title || 'Case Timeline'}
                    </Typography>

                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                            startIcon={<AutoDetectIcon />}
                            onClick={handleAutoDetectEvents}
                            variant="outlined"
                            size="small"
                        >
                            Auto-Detect Events
                        </Button>
                        <Button
                            startIcon={<AddIcon />}
                            onClick={() => {
                                setEditingEvent({
                                    event_type: 'custom',
                                    importance: 'medium',
                                    event_date: new Date().toISOString()
                                });
                                setEventDialogOpen(true);
                            }}
                            variant="contained"
                        >
                            Add Event
                        </Button>
                    </Box>
                </Box>

                {/* Filters */}
                <Paper sx={{ p: 2, mb: 3 }}>
                    <Grid container spacing={2} alignItems="center">
                        <Grid item xs={12} md={3}>
                            <TextField
                                fullWidth
                                size="small"
                                placeholder="Search events..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                InputProps={{
                                    startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
                                }}
                            />
                        </Grid>
                        <Grid item xs={12} md={2}>
                            <FormControl fullWidth size="small">
                                <InputLabel>Event Type</InputLabel>
                                <Select
                                    value={filterType}
                                    onChange={(e) => setFilterType(e.target.value)}
                                    label="Event Type"
                                >
                                    <MenuItem value="all">All Types</MenuItem>
                                    <MenuItem value="incident">Incident</MenuItem>
                                    <MenuItem value="filing">Filing</MenuItem>
                                    <MenuItem value="hearing">Hearing</MenuItem>
                                    <MenuItem value="deposition">Deposition</MenuItem>
                                    <MenuItem value="evidence">Evidence</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={12} md={2}>
                            <FormControl fullWidth size="small">
                                <InputLabel>Importance</InputLabel>
                                <Select
                                    value={filterImportance}
                                    onChange={(e) => setFilterImportance(e.target.value)}
                                    label="Importance"
                                >
                                    <MenuItem value="all">All Levels</MenuItem>
                                    <MenuItem value="low">Low</MenuItem>
                                    <MenuItem value="medium">Medium</MenuItem>
                                    <MenuItem value="high">High</MenuItem>
                                    <MenuItem value="critical">Critical</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={12} md={2}>
                            <Button
                                variant={showEvidenceOnly ? 'contained' : 'outlined'}
                                onClick={() => setShowEvidenceOnly(!showEvidenceOnly)}
                                startIcon={<AttachFileIcon />}
                                size="small"
                            >
                                With Evidence
                            </Button>
                        </Grid>
                    </Grid>
                </Paper>

                {/* Timeline */}
                <Timeline position="alternate">
                    {filteredEvents.map((event, index) => (
                        <TimelineItem key={event.id}>
                            <TimelineOppositeContent sx={{ m: 'auto 0' }} variant="body2" color="text.secondary">
                                <Typography variant="caption" display="block">
                                    {format(parseISO(event.event_date), 'MMM dd, yyyy')}
                                </Typography>
                                <Typography variant="caption" display="block">
                                    {format(parseISO(event.event_date), 'h:mm a')}
                                </Typography>
                                {event.location && (
                                    <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                                        📍 {event.location}
                                    </Typography>
                                )}
                            </TimelineOppositeContent>

                            <TimelineSeparator>
                                {renderEventIcon(event)}
                                {index < filteredEvents.length - 1 && <TimelineConnector />}
                            </TimelineSeparator>

                            <TimelineContent sx={{ py: '12px', px: 2 }}>
                                <Card
                                    sx={{
                                        cursor: 'pointer',
                                        '&:hover': { boxShadow: 3 },
                                        border: event.importance === 'critical' ? '2px solid #F44336' : 'none'
                                    }}
                                    onClick={() => setSelectedEvent(event)}
                                >
                                    <CardContent>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                                            <Typography variant="h6" component="h3">
                                                {event.title}
                                                {event.has_evidence && (
                                                    <Badge badgeContent={event.evidence_count} color="primary" sx={{ ml: 1 }}>
                                                        <AttachFileIcon fontSize="small" />
                                                    </Badge>
                                                )}
                                            </Typography>

                                            <Box>
                                                <IconButton
                                                    size="small"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setEditingEvent(event);
                                                        setEventDialogOpen(true);
                                                    }}
                                                >
                                                    <EditIcon fontSize="small" />
                                                </IconButton>
                                                <IconButton
                                                    size="small"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setSelectedEvent(event);
                                                        setEvidencePinDialogOpen(true);
                                                    }}
                                                >
                                                    <AttachFileIcon fontSize="small" />
                                                </IconButton>
                                            </Box>
                                        </Box>

                                        {event.description && (
                                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                                {event.description}
                                            </Typography>
                                        )}

                                        <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                            <Chip
                                                label={event.event_type}
                                                size="small"
                                                color="primary"
                                                variant="outlined"
                                            />
                                            <Chip
                                                label={event.importance}
                                                size="small"
                                                sx={{
                                                    bgcolor: importanceColors[event.importance],
                                                    color: 'white'
                                                }}
                                            />
                                            <Chip
                                                label={event.status}
                                                size="small"
                                                color={event.status === 'verified' ? 'success' : 'default'}
                                                variant="outlined"
                                            />
                                        </Box>

                                        {event.participants && event.participants.length > 0 && (
                                            <Typography variant="caption" display="block" sx={{ mb: 1 }}>
                                                👥 {event.participants.join(', ')}
                                            </Typography>
                                        )}

                                        {renderEvidenceChips(event)}

                                        {event.legal_significance && (
                                            <Alert severity="info" sx={{ mt: 1, fontSize: '0.8rem' }}>
                                                {event.legal_significance}
                                            </Alert>
                                        )}
                                    </CardContent>
                                </Card>
                            </TimelineContent>
                        </TimelineItem>
                    ))}
                </Timeline>

                {filteredEvents.length === 0 && (
                    <Box sx={{ textAlign: 'center', py: 4 }}>
                        <Typography variant="h6" color="text.secondary">
                            No events found
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            {searchQuery || filterType !== 'all' || filterImportance !== 'all' || showEvidenceOnly
                                ? 'Try adjusting your filters'
                                : 'Start building your timeline by adding events'
                            }
                        </Typography>
                        <Button
                            startIcon={<AddIcon />}
                            onClick={() => {
                                setEditingEvent({
                                    event_type: 'custom',
                                    importance: 'medium',
                                    event_date: new Date().toISOString()
                                });
                                setEventDialogOpen(true);
                            }}
                            variant="contained"
                        >
                            Add First Event
                        </Button>
                    </Box>
                )}

                {/* Event Dialog */}
                <Dialog
                    open={eventDialogOpen}
                    onClose={() => setEventDialogOpen(false)}
                    maxWidth="md"
                    fullWidth
                >
                    <DialogTitle>
                        {editingEvent.id ? 'Edit Event' : 'Add New Event'}
                    </DialogTitle>
                    <DialogContent>
                        <Grid container spacing={2} sx={{ mt: 1 }}>
                            <Grid item xs={12}>
                                <TextField
                                    fullWidth
                                    label="Event Title"
                                    value={editingEvent.title || ''}
                                    onChange={(e) => setEditingEvent(prev => ({ ...prev, title: e.target.value }))}
                                />
                            </Grid>
                            <Grid item xs={12}>
                                <TextField
                                    fullWidth
                                    multiline
                                    rows={3}
                                    label="Description"
                                    value={editingEvent.description || ''}
                                    onChange={(e) => setEditingEvent(prev => ({ ...prev, description: e.target.value }))}
                                />
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <FormControl fullWidth>
                                    <InputLabel>Event Type</InputLabel>
                                    <Select
                                        value={editingEvent.event_type || 'custom'}
                                        onChange={(e) => setEditingEvent(prev => ({ ...prev, event_type: e.target.value }))}
                                        label="Event Type"
                                    >
                                        <MenuItem value="incident">Incident</MenuItem>
                                        <MenuItem value="filing">Filing</MenuItem>
                                        <MenuItem value="hearing">Hearing</MenuItem>
                                        <MenuItem value="deposition">Deposition</MenuItem>
                                        <MenuItem value="discovery">Discovery</MenuItem>
                                        <MenuItem value="motion">Motion</MenuItem>
                                        <MenuItem value="settlement">Settlement</MenuItem>
                                        <MenuItem value="verdict">Verdict</MenuItem>
                                        <MenuItem value="appeal">Appeal</MenuItem>
                                        <MenuItem value="evidence">Evidence</MenuItem>
                                        <MenuItem value="custom">Custom</MenuItem>
                                    </Select>
                                </FormControl>
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <FormControl fullWidth>
                                    <InputLabel>Importance</InputLabel>
                                    <Select
                                        value={editingEvent.importance || 'medium'}
                                        onChange={(e) => setEditingEvent(prev => ({ ...prev, importance: e.target.value }))}
                                        label="Importance"
                                    >
                                        <MenuItem value="low">Low</MenuItem>
                                        <MenuItem value="medium">Medium</MenuItem>
                                        <MenuItem value="high">High</MenuItem>
                                        <MenuItem value="critical">Critical</MenuItem>
                                    </Select>
                                </FormControl>
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <DateTimePicker
                                    label="Event Date"
                                    value={editingEvent.event_date ? parseISO(editingEvent.event_date) : null}
                                    onChange={(date) => setEditingEvent(prev => ({
                                        ...prev,
                                        event_date: date?.toISOString()
                                    }))}
                                    renderInput={(params) => <TextField {...params} fullWidth />}
                                />
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <TextField
                                    fullWidth
                                    label="Location"
                                    value={editingEvent.location || ''}
                                    onChange={(e) => setEditingEvent(prev => ({ ...prev, location: e.target.value }))}
                                />
                            </Grid>
                            <Grid item xs={12}>
                                <TextField
                                    fullWidth
                                    multiline
                                    rows={2}
                                    label="Legal Significance"
                                    value={editingEvent.legal_significance || ''}
                                    onChange={(e) => setEditingEvent(prev => ({ ...prev, legal_significance: e.target.value }))}
                                    helperText="Why is this event important to the case?"
                                />
                            </Grid>
                        </Grid>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setEventDialogOpen(false)}>Cancel</Button>
                        <Button
                            onClick={() => editingEvent.id ? handleUpdateEvent(editingEvent.id) : handleAddEvent()}
                            variant="contained"
                        >
                            {editingEvent.id ? 'Update' : 'Add'} Event
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* Evidence Pin Dialog */}
                <Dialog
                    open={evidencePinDialogOpen}
                    onClose={() => setEvidencePinDialogOpen(false)}
                    maxWidth="md"
                    fullWidth
                >
                    <DialogTitle>
                        Pin Evidence to Event: {selectedEvent?.title}
                    </DialogTitle>
                    <DialogContent>
                        {/* Evidence selection interface would go here */}
                        <Typography>Evidence pinning interface coming soon...</Typography>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setEvidencePinDialogOpen(false)}>Cancel</Button>
                        <Button variant="contained">Pin Evidence</Button>
                    </DialogActions>
                </Dialog>

                {error && (
                    <Alert severity="error" sx={{ mt: 2 }}>
                        {error}
                    </Alert>
                )}
            </Box>
        </LocalizationProvider>
    );
};
/**
 * Timeline Collaboration Component
 * Manages sharing, permissions, and real-time collaboration features
 */

import React, { useState, useEffect } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Box,
    Typography,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    ListItemSecondaryAction,
    Avatar,
    IconButton,
    Chip,
    Switch,
    FormControlLabel,
    FormGroup,
    Divider,
    Alert,
    CircularProgress,
    Tooltip,
    Menu,
    MenuItem,
    Card,
    CardContent,
    Grid,
    Badge,
    Paper,
    Tabs,
    Tab,
    Autocomplete
} from '@mui/material';
import {
    Share as ShareIcon,
    Person as PersonIcon,
    Edit as EditIcon,
    Delete as DeleteIcon,
    MoreVert as MoreVertIcon,
    Visibility as ViewIcon,
    Lock as LockIcon,
    Public as PublicIcon,
    Link as LinkIcon,
    Notifications as NotificationsIcon,
    NotificationsOff as NotificationsOffIcon,
    Online as OnlineIcon,
    Offline as OfflineIcon,
    Comment as CommentIcon,
    History as HistoryIcon,
    Group as GroupIcon,
    PersonAdd as PersonAddIcon,
    Send as SendIcon,
    Copy as CopyIcon,
    Check as CheckIcon
} from '@mui/icons-material';
import { format, parseISO } from 'date-fns';

// Types
interface Collaborator {
    user_id: number;
    user_name: string;
    user_email: string;
    permissions: {
        can_view: boolean;
        can_edit: boolean;
        can_add_events: boolean;
        can_pin_evidence: boolean;
        can_share: boolean;
    };
    receive_notifications: boolean;
    shared_at: string;
    is_online: boolean;
}

interface User {
    id: number;
    full_name: string;
    email: string;
    avatar_url?: string;
    role: string;
}

interface ShareLink {
    url: string;
    expires_at: string;
    permissions: {
        can_view: boolean;
        can_edit: boolean;
    };
}

interface TimelineCollaborationProps {
    open: boolean;
    onClose: () => void;
    timelineId: number;
    timelineTitle: string;
    isOwner: boolean;
    onCollaboratorsChange?: (collaborators: Collaborator[]) => void;
}

export const TimelineCollaboration: React.FC<TimelineCollaborationProps> = ({
    open,
    onClose,
    timelineId,
    timelineTitle,
    isOwner,
    onCollaboratorsChange
}) => {
    const [activeTab, setActiveTab] = useState(0);
    const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
    const [availableUsers, setAvailableUsers] = useState<User[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Share user dialog
    const [shareUserDialog, setShareUserDialog] = useState(false);
    const [selectedUser, setSelectedUser] = useState<User | null>(null);
    const [sharePermissions, setSharePermissions] = useState({
        can_view: true,
        can_edit: false,
        can_add_events: false,
        can_pin_evidence: false,
        can_share: false
    });
    const [shareMessage, setShareMessage] = useState('');

    // Share link
    const [shareLink, setShareLink] = useState<ShareLink | null>(null);
    const [linkCopied, setLinkCopied] = useState(false);

    // Menu states
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [selectedCollaborator, setSelectedCollaborator] = useState<Collaborator | null>(null);

    // Load data when dialog opens
    useEffect(() => {
        if (open) {
            loadCollaborators();
            loadAvailableUsers();
        }
    }, [open, timelineId]);

    const loadCollaborators = async () => {
        setLoading(true);
        try {
            const response = await fetch(`/api/v1/timeline/${timelineId}/collaborators`);
            if (response.ok) {
                const data = await response.json();
                setCollaborators(data);
                onCollaboratorsChange?.(data);
            } else {
                setError('Failed to load collaborators');
            }
        } catch (err) {
            setError('Error loading collaborators');
        } finally {
            setLoading(false);
        }
    };

    const loadAvailableUsers = async () => {
        try {
            const response = await fetch('/api/v1/users/available-for-sharing');
            if (response.ok) {
                const data = await response.json();
                setAvailableUsers(data);
            }
        } catch (err) {
            console.error('Error loading available users:', err);
        }
    };

    const handleShareWithUser = async () => {
        if (!selectedUser) return;

        setLoading(true);
        try {
            const response = await fetch(`/api/v1/timeline/${timelineId}/share`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: selectedUser.id,
                    permissions: sharePermissions,
                    message: shareMessage
                })
            });

            if (response.ok) {
                setSuccess(`Timeline shared with ${selectedUser.full_name}`);
                setShareUserDialog(false);
                setSelectedUser(null);
                setShareMessage('');
                loadCollaborators();
            } else {
                setError('Failed to share timeline');
            }
        } catch (err) {
            setError('Error sharing timeline');
        } finally {
            setLoading(false);
        }
    };

    const handleUpdatePermissions = async (collaborator: Collaborator, newPermissions: any) => {
        try {
            const response = await fetch(`/api/v1/timeline/${timelineId}/collaborators/${collaborator.user_id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ permissions: newPermissions })
            });

            if (response.ok) {
                setSuccess('Permissions updated');
                loadCollaborators();
            } else {
                setError('Failed to update permissions');
            }
        } catch (err) {
            setError('Error updating permissions');
        }
    };

    const handleRemoveCollaborator = async (collaborator: Collaborator) => {
        try {
            const response = await fetch(`/api/v1/timeline/${timelineId}/collaborators/${collaborator.user_id}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                setSuccess(`${collaborator.user_name} removed from timeline`);
                loadCollaborators();
            } else {
                setError('Failed to remove collaborator');
            }
        } catch (err) {
            setError('Error removing collaborator');
        }
        setAnchorEl(null);
    };

    const handleCreateShareLink = async () => {
        try {
            const response = await fetch(`/api/v1/timeline/${timelineId}/share-link`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    expires_in_hours: 24,
                    permissions: { can_view: true, can_edit: false }
                })
            });

            if (response.ok) {
                const data = await response.json();
                setShareLink(data);
            } else {
                setError('Failed to create share link');
            }
        } catch (err) {
            setError('Error creating share link');
        }
    };

    const handleCopyLink = async () => {
        if (shareLink) {
            try {
                await navigator.clipboard.writeText(shareLink.url);
                setLinkCopied(true);
                setTimeout(() => setLinkCopied(false), 2000);
            } catch (err) {
                setError('Failed to copy link');
            }
        }
    };

    const renderCollaboratorsList = () => (
        <List>
            {collaborators.map((collaborator) => (
                <ListItem key={collaborator.user_id} divider>
                    <ListItemIcon>
                        <Badge
                            overlap="circular"
                            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                            badgeContent={
                                collaborator.is_online ? (
                                    <OnlineIcon sx={{ color: '#4CAF50', fontSize: 16 }} />
                                ) : (
                                    <OfflineIcon sx={{ color: '#9E9E9E', fontSize: 16 }} />
                                )
                            }
                        >
                            <Avatar sx={{ bgcolor: '#1976D2' }}>
                                {collaborator.user_name.charAt(0).toUpperCase()}
                            </Avatar>
                        </Badge>
                    </ListItemIcon>

                    <ListItemText
                        primary={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Typography variant="subtitle2">{collaborator.user_name}</Typography>
                                {collaborator.is_online && (
                                    <Chip size="small" label="Online" color="success" variant="outlined" />
                                )}
                            </Box>
                        }
                        secondary={
                            <Box>
                                <Typography variant="body2" color="text.secondary">
                                    {collaborator.user_email}
                                </Typography>
                                <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
                                    {collaborator.permissions.can_view && (
                                        <Chip size="small" label="View" variant="outlined" />
                                    )}
                                    {collaborator.permissions.can_edit && (
                                        <Chip size="small" label="Edit" color="primary" variant="outlined" />
                                    )}
                                    {collaborator.permissions.can_add_events && (
                                        <Chip size="small" label="Add Events" color="secondary" variant="outlined" />
                                    )}
                                    {collaborator.permissions.can_pin_evidence && (
                                        <Chip size="small" label="Pin Evidence" color="info" variant="outlined" />
                                    )}
                                    {collaborator.permissions.can_share && (
                                        <Chip size="small" label="Share" color="warning" variant="outlined" />
                                    )}
                                </Box>
                                <Typography variant="caption" color="text.secondary">
                                    Shared {format(parseISO(collaborator.shared_at), 'MMM dd, yyyy')}
                                </Typography>
                            </Box>
                        }
                    />

                    {isOwner && (
                        <ListItemSecondaryAction>
                            <IconButton
                                onClick={(e) => {
                                    setAnchorEl(e.currentTarget);
                                    setSelectedCollaborator(collaborator);
                                }}
                            >
                                <MoreVertIcon />
                            </IconButton>
                        </ListItemSecondaryAction>
                    )}
                </ListItem>
            ))}

            {collaborators.length === 0 && (
                <ListItem>
                    <ListItemText
                        primary="No collaborators yet"
                        secondary="Share this timeline with team members to start collaborating"
                    />
                </ListItem>
            )}
        </List>
    );

    const renderShareLinkTab = () => (
        <Box sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
                Share Link
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Create a shareable link that allows anyone with the link to view the timeline.
            </Typography>

            {shareLink ? (
                <Card sx={{ mb: 2 }}>
                    <CardContent>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                            <LinkIcon color="primary" />
                            <Box sx={{ flex: 1 }}>
                                <Typography variant="subtitle2">Timeline Share Link</Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Expires {format(parseISO(shareLink.expires_at), 'MMM dd, yyyy at h:mm a')}
                                </Typography>
                            </Box>
                        </Box>

                        <TextField
                            fullWidth
                            value={shareLink.url}
                            InputProps={{
                                readOnly: true,
                                endAdornment: (
                                    <IconButton onClick={handleCopyLink}>
                                        {linkCopied ? <CheckIcon color="success" /> : <CopyIcon />}
                                    </IconButton>
                                )
                            }}
                            sx={{ mb: 2 }}
                        />

                        <Box sx={{ display: 'flex', gap: 1 }}>
                            <Chip
                                size="small"
                                label="View Only"
                                color="primary"
                                variant="outlined"
                            />
                            <Chip
                                size="small"
                                label="24 Hour Expiry"
                                variant="outlined"
                            />
                        </Box>
                    </CardContent>
                </Card>
            ) : (
                <Button
                    variant="contained"
                    startIcon={<LinkIcon />}
                    onClick={handleCreateShareLink}
                    sx={{ mb: 2 }}
                >
                    Create Share Link
                </Button>
            )}

            <Alert severity="info">
                Share links provide view-only access and expire after 24 hours. For more control over permissions, share directly with specific users.
            </Alert>
        </Box>
    );

    return (
        <>
            <Dialog
                open={open}
                onClose={onClose}
                maxWidth="md"
                fullWidth
                PaperProps={{ sx: { height: '80vh' } }}
            >
                <DialogTitle>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Box>
                            <Typography variant="h6">Timeline Collaboration</Typography>
                            <Typography variant="body2" color="text.secondary">
                                {timelineTitle}
                            </Typography>
                        </Box>
                        {isOwner && (
                            <Button
                                variant="contained"
                                startIcon={<PersonAddIcon />}
                                onClick={() => setShareUserDialog(true)}
                            >
                                Share
                            </Button>
                        )}
                    </Box>
                </DialogTitle>

                <DialogContent sx={{ p: 0 }}>
                    <Tabs
                        value={activeTab}
                        onChange={(_, newValue) => setActiveTab(newValue)}
                        sx={{ borderBottom: 1, borderColor: 'divider' }}
                    >
                        <Tab
                            label={`Collaborators (${collaborators.length})`}
                            icon={<GroupIcon />}
                            iconPosition="start"
                        />
                        <Tab
                            label="Share Link"
                            icon={<LinkIcon />}
                            iconPosition="start"
                        />
                        <Tab
                            label="Activity"
                            icon={<HistoryIcon />}
                            iconPosition="start"
                        />
                    </Tabs>

                    <Box sx={{ height: 'calc(100% - 48px)', overflow: 'auto' }}>
                        {loading ? (
                            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 200 }}>
                                <CircularProgress />
                            </Box>
                        ) : (
                            <>
                                {activeTab === 0 && renderCollaboratorsList()}
                                {activeTab === 1 && renderShareLinkTab()}
                                {activeTab === 2 && (
                                    <Box sx={{ p: 2 }}>
                                        <Typography variant="h6" gutterBottom>Activity Log</Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Activity tracking coming soon...
                                        </Typography>
                                    </Box>
                                )}
                            </>
                        )}
                    </Box>

                    {error && (
                        <Alert severity="error" sx={{ m: 2 }}>
                            {error}
                        </Alert>
                    )}

                    {success && (
                        <Alert severity="success" sx={{ m: 2 }}>
                            {success}
                        </Alert>
                    )}
                </DialogContent>

                <DialogActions>
                    <Button onClick={onClose}>Close</Button>
                </DialogActions>
            </Dialog>

            {/* Share User Dialog */}
            <Dialog
                open={shareUserDialog}
                onClose={() => setShareUserDialog(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>Share Timeline</DialogTitle>
                <DialogContent>
                    <Box sx={{ mt: 1 }}>
                        <Autocomplete
                            options={availableUsers}
                            getOptionLabel={(option) => `${option.full_name} (${option.email})`}
                            value={selectedUser}
                            onChange={(_, newValue) => setSelectedUser(newValue)}
                            renderInput={(params) => (
                                <TextField
                                    {...params}
                                    label="Select User"
                                    placeholder="Search by name or email..."
                                    fullWidth
                                />
                            )}
                            renderOption={(props, option) => (
                                <Box component="li" {...props}>
                                    <Avatar sx={{ mr: 2, bgcolor: '#1976D2' }}>
                                        {option.full_name.charAt(0).toUpperCase()}
                                    </Avatar>
                                    <Box>
                                        <Typography variant="body2">{option.full_name}</Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {option.email} • {option.role}
                                        </Typography>
                                    </Box>
                                </Box>
                            )}
                            sx={{ mb: 3 }}
                        />

                        <Typography variant="subtitle2" gutterBottom>
                            Permissions
                        </Typography>

                        <FormGroup sx={{ mb: 2 }}>
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={sharePermissions.can_view}
                                        onChange={(e) => setSharePermissions(prev => ({ ...prev, can_view: e.target.checked }))}
                                    />
                                }
                                label="Can view timeline"
                            />
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={sharePermissions.can_edit}
                                        onChange={(e) => setSharePermissions(prev => ({ ...prev, can_edit: e.target.checked }))}
                                    />
                                }
                                label="Can edit events"
                            />
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={sharePermissions.can_add_events}
                                        onChange={(e) => setSharePermissions(prev => ({ ...prev, can_add_events: e.target.checked }))}
                                    />
                                }
                                label="Can add new events"
                            />
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={sharePermissions.can_pin_evidence}
                                        onChange={(e) => setSharePermissions(prev => ({ ...prev, can_pin_evidence: e.target.checked }))}
                                    />
                                }
                                label="Can pin evidence"
                            />
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={sharePermissions.can_share}
                                        onChange={(e) => setSharePermissions(prev => ({ ...prev, can_share: e.target.checked }))}
                                    />
                                }
                                label="Can share with others"
                            />
                        </FormGroup>

                        <TextField
                            fullWidth
                            multiline
                            rows={3}
                            label="Message (optional)"
                            placeholder="Add a message to include with the sharing invitation..."
                            value={shareMessage}
                            onChange={(e) => setShareMessage(e.target.value)}
                        />
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShareUserDialog(false)}>Cancel</Button>
                    <Button
                        onClick={handleShareWithUser}
                        variant="contained"
                        disabled={!selectedUser}
                        startIcon={<SendIcon />}
                    >
                        Share Timeline
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Collaborator Menu */}
            <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={() => setAnchorEl(null)}
            >
                <MenuItem
                    onClick={() => {
                        // Open permissions dialog
                        setAnchorEl(null);
                    }}
                >
                    <ListItemIcon>
                        <EditIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText>Edit Permissions</ListItemText>
                </MenuItem>
                <MenuItem
                    onClick={() => {
                        if (selectedCollaborator) {
                            handleRemoveCollaborator(selectedCollaborator);
                        }
                    }}
                >
                    <ListItemIcon>
                        <DeleteIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText>Remove Access</ListItemText>
                </MenuItem>
            </Menu>
        </>
    );
};
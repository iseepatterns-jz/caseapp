import axios from 'axios';
import { fetchAuthSession, signOut } from 'aws-amplify/auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add response interceptor to handle auth errors
apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        if (error.response && (error.response.status === 401 || error.response.status === 403)) {
            try {
                // Clear local session
                await signOut();
            } catch (signOutError) {
                console.error('Error signing out during auth redirect:', signOutError);
            } finally {
                // Redirect to login
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

// Add request interceptor to inject Authorization header
apiClient.interceptors.request.use(async (config) => {
    try {
        const session = await fetchAuthSession();
        const token = session.tokens?.idToken?.toString();

        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
    } catch (error) {
        // Fallback for unauthenticated requests if applicable
        console.debug('No active session found for API request');
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

export const healthService = {
    checkHealth: async () => {
        const response = await apiClient.get('/health');
        return response.data;
    },
};

export const caseService = {
    getAll: async (params?: any) => {
        const response = await apiClient.get('/api/v1/cases/', { params });
        return response.data;
    },
    getById: async (id: string) => {
        const response = await apiClient.get(`/api/v1/cases/${id}`);
        return response.data;
    },
    create: async (data: any) => {
        const response = await apiClient.post('/api/v1/cases/', data);
        return response.data;
    },
    update: async (id: string, data: any) => {
        const response = await apiClient.put(`/api/v1/cases/${id}`, data);
        return response.data;
    },
    delete: async (id: string) => {
        const response = await apiClient.delete(`/api/v1/cases/${id}`);
        return response.data;
    },
};

export const mediaService = {
    getByCaseId: async (caseId: string) => {
        const response = await apiClient.get(`/api/v1/media/case/${caseId}`);
        return response.data;
    },
    getById: async (mediaId: string) => {
        const response = await apiClient.get(`/api/v1/media/${mediaId}`);
        return response.data;
    },
    upload: async (formData: FormData) => {
        const response = await apiClient.post('/api/v1/media/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },
    getShareLink: async (mediaId: string, expirationHours: number = 1) => {
        const formData = new FormData();
        formData.append('expiration_hours', expirationHours.toString());
        const response = await apiClient.post(`/api/v1/media/${mediaId}/share`, formData);
        return response.data;
    }
};

export const dashboardService = {
    getStats: async () => {
        const response = await apiClient.get('/api/v1/cases/statistics/dashboard');
        return response.data;
    },
    getRecentActivity: async () => {
        const response = await apiClient.get('/api/v1/audit/search?page_size=5');
        return response.data;
    }
};

export const financialAnalysisService = {
    getSummary: async (caseId: string) => {
        const response = await apiClient.get(`/api/v1/financial/case/${caseId}/summary`);
        return response.data;
    },
    getAccounts: async (caseId: string) => {
        const response = await apiClient.get(`/api/v1/financial/case/${caseId}/accounts`);
        return response.data;
    },
    getTransactions: async (caseId: string) => {
        const response = await apiClient.get(`/api/v1/financial/case/${caseId}/transactions`);
        return response.data;
    },
    getAlerts: async (caseId: string) => {
        const response = await apiClient.get(`/api/v1/financial/case/${caseId}/alerts`);
        return response.data;
    },
    triggerAnalysis: async (caseId: string) => {
        const response = await apiClient.post(`/api/v1/financial/case/${caseId}/analyze`);
        return response.data;
    }
};

export default apiClient;

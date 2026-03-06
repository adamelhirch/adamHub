import axios from 'axios';

// Create a custom axios instance for the AdamHUB Life API
export const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add an interceptor to insert the API key automatically
api.interceptors.request.use((config) => {
    // Try to get key from localStorage, otherwise prompt or use a default if dev
    const apiKey = localStorage.getItem('adamhub_api_key') || 'change-me';

    if (apiKey) {
        config.headers['X-API-KEY'] = apiKey;
    }

    return config;
});

// API helper functions
export const API = {
    finances: {
        getAnalytics: (year: number, month: number) =>
            api.get(`/api/v1/finances/analytics?year=${year}&month=${month}`).then(res => res.data),
    },
};

import axios from "axios";

const apiBaseUrl = import.meta.env.VITE_API_URL?.trim() || "/api/v1";
const apiKey = import.meta.env.VITE_API_KEY?.trim();

// Create an Axios instance with base configuration
export const api = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  },
});

export default api;

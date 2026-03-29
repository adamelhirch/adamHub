import axios from "axios";

// Create an Axios instance with base configuration
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": import.meta.env.VITE_API_KEY || "change-me",
  },
});

export default api;

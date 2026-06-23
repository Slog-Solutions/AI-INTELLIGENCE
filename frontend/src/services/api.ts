import axios from "axios";
import { getAuthToken, clearAuthSession, isTokenExpired } from "./auth";

const api = axios.create({
  baseURL: "http://localhost:8000",
  // Let axios set Content-Type automatically for FormData
  headers: {},
  // Increased timeout for slow AI responses (3 minutes)
  timeout: 180000,
});

api.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearAuthSession();
      window.location.href = "/";
    }
    return Promise.reject(error);
  }
);

export default api;

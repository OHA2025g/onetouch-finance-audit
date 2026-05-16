import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const normalizedBackend = (BACKEND_URL || "").replace(/\/+$/, "");
export const API = normalizedBackend ? `${normalizedBackend}/api` : "/api";

export const http = axios.create({ baseURL: API });

http.interceptors.request.use((config) => {
  const token = localStorage.getItem("ota_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

http.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("ota_token");
      localStorage.removeItem("ota_user");
      if (window.location.pathname !== "/login") window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

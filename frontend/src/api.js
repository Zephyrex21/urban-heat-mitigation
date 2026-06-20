// In production, set VITE_API_BASE_URL in your deployment platform's
// environment variables (e.g. https://your-backend.onrender.com).
// Locally, it falls back to your FastAPI dev server.
export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

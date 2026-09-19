/**
 * auth.js — Authentication service for Nexus Data Platform.
 * Handles JWT-based authentication with backend API.
 */

const TOKEN_KEY = 'nexus_token';
const ROLE_KEY = 'nexus_role';
const USER_KEY = 'nexus_user';

// ── Token helpers ──────────────────────────────────────────────────────────

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const getRole = () => localStorage.getItem(ROLE_KEY);
export const getCurrentUser = () => {
  const stored = localStorage.getItem(USER_KEY);
  return stored ? JSON.parse(stored) : null;
};

/**
 * Build headers with Authorization bearer token.
 */
export const authHeaders = () => {
  const token = getToken();
  return token
    ? { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
    : { 'Content-Type': 'application/json' };
};

// ── Auth actions ───────────────────────────────────────────────────────────

/**
 * Login — POST /auth/login
 * Returns { token, role, user } on success.
 * Throws on failure.
 */
export const login = async (email, password, role = 'admin') => {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, role }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(err.detail || 'Login failed');
  }

  const data = await res.json();
  const user = {
    email,
    displayName: email.split('@')[0],
    role: data.role || role,
  };
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(ROLE_KEY, data.role || role);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  return { token: data.access_token, role: data.role || role, user };
};

/**
 * Register a new user — POST /auth/register (admin only)
 */
export const register = async (email, password, role, displayName = '') => {
  const res = await fetch('/auth/register', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      email,
      password,
      role,
      display_name: displayName,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
    throw new Error(err.detail || 'Registration failed');
  }

  return res.json();
};

/**
 * Get current user profile — GET /auth/me
 */
export const getMe = async () => {
  const res = await fetch('/auth/me', {
    headers: authHeaders(),
  });

  if (!res.ok) return null;
  return res.json();
};

/**
 * Return metadata proving that the current JWT session exists server-side.
 */
export const getTokenStatus = async () => {
  const res = await fetch('/auth/token-status', { headers: authHeaders() });
  if (!res.ok) return null;
  return res.json();
};

/**
 * List all users — GET /auth/users (admin only)
 */
export const listUsers = async () => {
  const res = await fetch('/auth/users', {
    headers: authHeaders(),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to load users' }));
    throw new Error(err.detail || 'Failed to load users');
  }

  return res.json();
};

/**
 * Logout — revoke the backend session and clear browser auth data.
 */
export const logout = () => {
  if (getToken()) {
    fetch('/auth/logout', {
      method: 'POST',
      headers: authHeaders(),
    }).catch(() => {});
  }
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(USER_KEY);
};

export const createUser = async (email, password, role, displayName = '') => {
 const { request } = await import('./http.js');
 return request('/auth/users', {method:'POST',body:{email,password,role,display_name:displayName}});
};

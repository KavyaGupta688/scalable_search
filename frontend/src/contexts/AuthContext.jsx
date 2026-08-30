import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import * as authService from '../services/auth';

/**
 * AuthContext — manages authentication state for the entire application.
 * Wired to POST /auth/login backend endpoint with JWT Bearer tokens.
 */
const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => authService.getToken());
  const [role, setRole] = useState(() => authService.getRole());
  const [currentUser, setCurrentUser] = useState(() => authService.getCurrentUser());
  const [authLoading, setAuthLoading] = useState(false);

  const isAuthenticated = Boolean(token);

  // Validate token on mount by calling GET /auth/me
  useEffect(() => {
    if (!token) return;

    authService.getMe().then((profile) => {
      if (!profile) {
        // Token is invalid or expired — log out silently
        authService.logout();
        setToken(null);
        setRole(null);
        setCurrentUser(null);
      }
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(async (email, password, loginRole) => {
    setAuthLoading(true);
    try {
      const result = await authService.login(email, password, loginRole);
      setToken(result.token);
      setRole(result.role);
      setCurrentUser(result.user);
      return result;
    } finally {
      setAuthLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    authService.logout();
    setToken(null);
    setRole(null);
    setCurrentUser(null);
  }, []);

  const register = useCallback(async (email, password, userRole, displayName) => {
    return authService.register(email, password, userRole, displayName);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        token,
        role,
        currentUser,
        authLoading,
        login,
        logout,
        register,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
};

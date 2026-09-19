import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

/**
 * RequireAuth — route guard.
 * If not authenticated, redirects to landing page.
 * If authenticated but wrong role, redirects to landing page.
 */
export const RequireAuth = ({ role: requiredRole, children }) => {
  const { isAuthenticated, role } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (requiredRole && role !== requiredRole) {
    // Authenticated but wrong role — redirect to their own dashboard
    if (role === 'admin') return <Navigate to="/admin/overview" replace />;
    if (role === 'user') return <Navigate to="/user/search" replace />;
    return <Navigate to="/" replace />;
  }

  return children;
};

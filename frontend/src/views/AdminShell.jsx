import React, { useState, useCallback, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Sidebar } from '../components/Shell/Sidebar';
import { Header } from '../components/Shell/Header';

/**
 * AdminShell — layout wrapper for all /admin/* routes.
 * Handles Cmd+K shortcut, logout, navigation.
 */
export const AdminShell = ({ showToast }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { currentUser, logout } = useAuth();

  // Derive current route ID from path for Sidebar active state
  const currentRoute = location.pathname.replace('/admin/', '') || 'overview';

  const handleNavigate = useCallback((route) => {
    navigate(`/admin/${route}`);
  }, [navigate]);

  const handleLogout = useCallback(() => {
    logout();
    showToast('Signed out of platform', 'info');
    navigate('/', { replace: true });
  }, [logout, showToast, navigate]);

  // Cmd+K / Ctrl+K shortcut
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        navigate('/admin/search');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [navigate]);

  return (
    <div className="flex min-h-screen bg-nexus-bg text-nexus-textPrimary font-sans">
      <Sidebar
        currentRoute={currentRoute}
        onNavigate={handleNavigate}
        onLogout={handleLogout}
        currentUser={currentUser}
      />
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        <Header
          onOpenSearch={() => navigate('/admin/search')}
          onLogout={handleLogout}
        />
        <main key={location.pathname} className="flex-1 p-6 lg:p-8 max-w-7xl w-full mx-auto page-transition">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

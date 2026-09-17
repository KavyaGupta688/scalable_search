import { PageMotion } from '../components/Motion';
import React, { useState, useCallback, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Sidebar } from '../components/Shell/Sidebar';
import { Header } from '../components/Shell/Header';

/**
 * AdminShell — layout wrapper for all /admin/* routes.
 * Handles logout and responsive navigation.
 */
export const AdminShell = ({ showToast }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { currentUser, logout } = useAuth();

  // Derive current route ID from path for Sidebar active state
  const currentRoute = location.pathname.replace('/admin/', '') || 'overview';

  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 768px)');
    const closeMobile = () => { if (desktop.matches) setMobileOpen(false); };
    desktop.addEventListener('change', closeMobile);
    return () => desktop.removeEventListener('change', closeMobile);
  }, []);

  const handleNavigate = useCallback((route) => {
    navigate(`/admin/${route}`);
  }, [navigate]);

  const handleLogout = useCallback(() => {
    logout();
    showToast('Signed out of platform', 'info');
    navigate('/', { replace: true });
  }, [logout, showToast, navigate]);

  return (
    <div className="admin-workspace"><a className="skip-link" href="#main-content">Skip to content</a>
      <Sidebar
        currentRoute={currentRoute}
        onNavigate={handleNavigate}
        onLogout={handleLogout}
        currentUser={currentUser}
        collapsed={collapsed} onCollapse={() => setCollapsed((value) => !value)}
        mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)}
      />
      <div className="admin-main">
        <Header onMenu={() => setMobileOpen(true)} />
        <PageMotion as="main" id="main-content" key={location.pathname} className="workspace-content">
          <Outlet />
        </PageMotion>
      </div>
    </div>
  );
};

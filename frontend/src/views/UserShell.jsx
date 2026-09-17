import { PageMotion } from '../components/Motion';
import React from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { Search, Download, LogOut } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { Brand } from '../components/DesignSystem';

export function UserShell({ showToast }) {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const handleLogout = () => {
    logout();
    showToast('Signed out', 'info');
    navigate('/', { replace: true });
  };

  return (
    <div className="user-workspace">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="user-header">
        <Brand />
        <nav aria-label="User navigation">
          <NavLink to="/user/search"><Search size={17} />Search</NavLink>
          <NavLink to="/user/downloads"><Download size={17} />Downloads</NavLink>
        </nav>
        <div className="user-account">
          <span className="avatar">{currentUser?.displayName?.[0] || 'U'}</span>
          <span>{currentUser?.displayName || 'User'}</span>
          <button className="icon-button" aria-label="Sign out" title="Sign out" onClick={handleLogout}>
            <LogOut size={18} />
          </button>
        </div>
      </header>
      <PageMotion as="main" id="main-content" key={location.pathname} className="user-content">
        <Outlet />
      </PageMotion>
      <footer className="workspace-footer">
        <Brand />
        <span>Your next discovery is one search away.</span>
      </footer>
    </div>
  );
}

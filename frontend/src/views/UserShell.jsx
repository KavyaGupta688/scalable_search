import React, { useCallback } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { NexusIcon, SearchIcon, DownloadIcon, LogoutIcon } from '../components/Icons';

const userNavItems = [
  { id: 'search', label: 'Search', icon: SearchIcon, path: '/user/search' },
  { id: 'downloads', label: 'Downloads', icon: DownloadIcon, path: '/user/downloads' },
];

/**
 * UserShell — minimal sidebar layout for the user track.
 * Only Search and Downloads navigation items.
 */
export const UserShell = ({ showToast }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { currentUser, logout } = useAuth();

  const currentRoute = location.pathname.replace('/user/', '') || 'search';

  const handleLogout = useCallback(() => {
    logout();
    showToast('Signed out', 'info');
    navigate('/', { replace: true });
  }, [logout, showToast, navigate]);

  return (
    <div className="flex min-h-screen bg-nexus-bg text-nexus-textPrimary font-sans">
      {/* Minimal sidebar */}
      <aside className="w-60 bg-nexus-surface border-r border-nexus-border flex flex-col h-screen sticky top-0 z-30 select-none">
        {/* Brand */}
        <div className="h-13 px-4 flex items-center gap-2.5 border-b border-nexus-borderSubtle">
          <div className="w-7 h-7 bg-nexus-brand rounded-sm flex items-center justify-center text-white shrink-0">
            <NexusIcon className="w-4 h-4" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-xs font-bold text-nexus-textPrimary tracking-tight">Nexus</span>
            <span className="text-[9px] font-semibold text-nexus-textMuted uppercase tracking-wider">Data Search</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-2.5 flex flex-col gap-1">
          <div className="text-[10px] font-semibold text-nexus-textMuted uppercase tracking-wider px-2 py-1.5 mt-1">
            Navigation
          </div>
          {userNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentRoute === item.id;
            return (
              <button
                key={item.id}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-sm text-xs font-medium border transition-colors ${
                  isActive
                    ? 'bg-nexus-brandSubtle text-nexus-brandText border-[#23426e] font-semibold'
                    : 'text-nexus-textSecondary hover:text-nexus-textPrimary hover:bg-nexus-hover border-transparent'
                }`}
              >
                <Icon className="w-3.5 h-3.5 shrink-0" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* User footer */}
        <div className="p-3 border-t border-nexus-borderSubtle">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-sm bg-nexus-elevated flex items-center justify-center text-nexus-textMuted text-[10px] font-bold uppercase shrink-0">
              {currentUser?.displayName?.[0] || 'U'}
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-[11px] font-semibold text-nexus-textPrimary truncate">
                {currentUser?.displayName || 'User'}
              </span>
              <span className="text-[9px] text-nexus-textMuted truncate">Standard access</span>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-2 py-1.5 text-[11px] text-nexus-textMuted hover:text-nexus-textPrimary hover:bg-nexus-hover rounded-sm border border-transparent transition-colors"
          >
            <LogoutIcon className="w-3.5 h-3.5 shrink-0" />
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      {/* Main */}
      <main key={location.pathname} className="flex-1 p-6 lg:p-8 page-transition">
        <Outlet />
      </main>
    </div>
  );
};

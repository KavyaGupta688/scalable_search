import React from 'react';
import {
  NexusIcon,
  OverviewIcon,
  SearchIcon,
  S3Icon,
  IngestionIcon,
  CpuIcon,
  AuditIcon,
  UsersNavIcon,
  LogoutIcon
} from '../Icons';

export const Sidebar = ({ currentRoute, onNavigate, onLogout, currentUser }) => {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: OverviewIcon },
    { id: 'search', label: 'Multimodal Search', icon: SearchIcon },
    { id: 'data-sources', label: 'S3 Buckets', icon: S3Icon },
    { id: 'ingestion', label: 'S3 Ingestion', icon: IngestionIcon },
    { id: 'enrichment', label: 'AI Enrichment', icon: CpuIcon },
    { id: 'audit', label: 'Audit Log', icon: AuditIcon },
    { id: 'users', label: 'Users', icon: UsersNavIcon },
  ];

  return (
    <aside className="w-60 bg-nexus-surface border-r border-nexus-border flex flex-col h-screen sticky top-0 z-30 select-none">
      {/* Brand Header */}
      <div className="h-13 px-4 flex items-center gap-2.5 border-b border-nexus-borderSubtle">
        <div className="w-7 h-7 bg-nexus-brand rounded-sm flex items-center justify-center text-white shrink-0">
          <NexusIcon className="w-4 h-4" />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-xs font-bold text-nexus-textPrimary tracking-tight">Nexus</span>
          <span className="text-[9px] font-semibold text-nexus-textMuted uppercase tracking-wider">Multimodal Data Platform</span>
        </div>
      </div>

      {/* Nav List */}
      <nav className="flex-1 overflow-y-auto p-2.5 flex flex-col gap-1">
        <div className="text-[10px] font-semibold text-nexus-textMuted uppercase tracking-wider px-2 py-1.5 mt-1">
          Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentRoute === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-sm text-xs font-medium border transition-colors ${
                isActive
                  ? 'bg-nexus-brandSubtle text-nexus-brandText border-[#23426e] font-semibold'
                  : 'bg-transparent text-nexus-textSecondary border-transparent hover:bg-nexus-hover hover:text-nexus-textPrimary'
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="p-3 border-t border-nexus-borderSubtle bg-[#0f151f]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-sm bg-nexus-brandSubtle border border-[#284470] text-nexus-brandText flex items-center justify-center text-[10px] font-bold shrink-0">
            {currentUser?.displayName?.[0]?.toUpperCase() || currentUser?.email?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="flex flex-col min-w-0 flex-1 leading-tight">
            <span className="text-[11px] font-semibold text-nexus-textPrimary truncate">{currentUser?.displayName || currentUser?.email || 'User'}</span>
            <span className="text-[10px] text-nexus-textMuted truncate capitalize">{currentUser?.role || 'admin'}</span>
          </div>
          <button
            onClick={onLogout}
            title="Sign out"
            className="p-1 text-nexus-textMuted hover:text-nexus-textPrimary hover:bg-nexus-hover rounded-sm transition-colors"
          >
            <LogoutIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};

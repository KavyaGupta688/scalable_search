import React from 'react';
import {
  PrismIcon,
  OverviewIcon,
  SearchIcon,
  S3Icon,
  IngestionIcon,
  CpuIcon,
  AuditIcon,
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
  ];

  return (
    <aside className="w-60 bg-prism-surface border-r border-prism-border flex flex-col h-screen sticky top-0 z-30 select-none">
      {/* Brand Header */}
      <div className="h-13 px-4 flex items-center gap-2.5 border-b border-prism-borderSubtle">
        <div className="w-7 h-7 bg-prism-brand rounded-sm flex items-center justify-center text-white shrink-0">
          <PrismIcon className="w-4 h-4" />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-xs font-bold text-prism-textPrimary tracking-tight">Samsung Prism</span>
          <span className="text-[9px] font-semibold text-prism-textMuted uppercase tracking-wider">S3 Multimodal Data</span>
        </div>
      </div>

      {/* Nav List */}
      <nav className="flex-1 overflow-y-auto p-2.5 flex flex-col gap-1">
        <div className="text-[10px] font-semibold text-prism-textMuted uppercase tracking-wider px-2 py-1.5 mt-1">
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
                  ? 'bg-prism-brandSubtle text-prism-brandText border-[#23426e] font-semibold'
                  : 'bg-transparent text-prism-textSecondary border-transparent hover:bg-prism-hover hover:text-prism-textPrimary'
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Footer / User Profile */}
      <div className="p-3 border-t border-prism-borderSubtle bg-[#0f151f]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-sm bg-prism-brandSubtle border border-[#284470] text-prism-brandText flex items-center justify-center text-[10px] font-bold shrink-0">
            AK
          </div>
          <div className="flex flex-col min-w-0 flex-1 leading-tight">
            <span className="text-[11px] font-semibold text-prism-textPrimary truncate">{currentUser.email}</span>
            <span className="text-[10px] text-prism-textMuted truncate">{currentUser.role}</span>
          </div>
          <button
            onClick={onLogout}
            title="Sign out"
            className="p-1 text-prism-textMuted hover:text-prism-textPrimary hover:bg-prism-hover rounded-sm transition-colors"
          >
            <LogoutIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};

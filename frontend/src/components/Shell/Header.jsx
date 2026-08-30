import React from 'react';
import { SearchIcon, LogoutIcon } from '../Icons';

export const Header = ({ onOpenSearch, onLogout }) => {
  return (
    <header className="h-13 bg-nexus-surface border-b border-nexus-border flex items-center justify-between px-6 sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-bold rounded-sm bg-[#122a1e] border border-[#1f5739] text-[#4ade80] uppercase tracking-wider">
          <span className="w-1.5 h-1.5 rounded-full bg-[#4ade80]" />
          <span>PRD-AP-EAST-1</span>
        </div>
        <span className="text-nexus-borderStrong text-xs">/</span>
        <span className="text-xs font-semibold text-nexus-textSecondary">
          Nexus · Multimodal Data Platform
        </span>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={onOpenSearch}
          className="flex items-center gap-2.5 bg-nexus-input border border-nexus-border hover:border-nexus-borderStrong rounded-sm px-3 h-8 text-xs text-nexus-textMuted hover:text-nexus-textSecondary transition-colors"
        >
          <SearchIcon className="w-3.5 h-3.5" />
          <span>Search S3 Objects...</span>
          <kbd className="font-mono text-[10px] px-1 py-0.5 bg-nexus-elevated border border-nexus-borderSubtle rounded-sm text-nexus-textMuted">
            ⌘K
          </kbd>
        </button>

        <button
          onClick={onLogout}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-nexus-textSecondary hover:text-nexus-textPrimary hover:bg-nexus-hover rounded-sm border border-transparent transition-colors"
        >
          <LogoutIcon className="w-3.5 h-3.5" />
          <span>Sign out</span>
        </button>
      </div>
    </header>
  );
};

import React from 'react';
import {
  LayoutDashboard, Search, Database, Workflow, Sparkles, ClipboardList,
  Users, LogOut, Download,
} from 'lucide-react';
import { Brand } from '../DesignSystem';
import { useDialog } from '../useDialog';
import { useMediaQuery } from '../Motion';

const items = [
  ['overview', 'Overview', LayoutDashboard],
  ['search', 'Multimodal Search', Search],
  ['data-sources', 'Data Sources', Database],
  ['ingestion', 'Ingestion', Workflow],
  ['enrichment', 'AI Enrichment', Sparkles],
  ['downloads', 'Downloads', Download],
  ['audit', 'Audit Log', ClipboardList],
  ['users', 'Users', Users],
];

export function Sidebar({
  currentRoute, onNavigate, onLogout, currentUser,
  collapsed, onCollapse, mobileOpen, onMobileClose,
}) {
  const dialogRef = useDialog(onMobileClose, mobileOpen);
  const mobile = useMediaQuery('(max-width:767px)');
  return (
    <>
      <div className={`sidebar-backdrop ${mobileOpen ? 'is-open' : ''}`} onClick={onMobileClose} aria-hidden="true" />
      <aside
        inert={mobile && !mobileOpen ? '' : undefined}
        ref={dialogRef}
        tabIndex={-1}
        role={mobileOpen ? 'dialog' : undefined}
        aria-modal={mobileOpen || undefined}
        aria-label="Admin navigation"
        className={`admin-sidebar ${collapsed ? 'is-collapsed' : ''} ${mobileOpen ? 'is-mobile-open' : ''}`}
      >
        <div className="sidebar-brand">
          <button
            type="button"
            className="sidebar-brand-toggle"
            onClick={mobileOpen ? onMobileClose : onCollapse}
            title={mobileOpen ? 'Close navigation' : collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={mobileOpen ? 'Close navigation' : collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={mobileOpen || !collapsed}
            aria-controls="admin-sidebar-navigation"
          >
            <Brand compact={collapsed && !mobileOpen} />
          </button>
        </div>
        <div className="sidebar-scroll" id="admin-sidebar-navigation">
        <div className="sidebar-caption">WORKSPACE</div>
        <nav aria-label="Admin modules">
          {items.map(([id, label, Icon]) => (
            <button
              key={id}
              title={label}
              aria-label={label}
              aria-current={currentRoute === id ? 'page' : undefined}
              className={`sidebar-item ${currentRoute === id ? 'active' : ''}`}
              onClick={() => { onNavigate(id); onMobileClose(); }}
            >
              <Icon size={19} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-profile">
            <span className="avatar">{currentUser?.displayName?.[0] || 'A'}</span>
            <div>
              <strong>{currentUser?.displayName || 'Administrator'}</strong>
              <small>Administrator</small>
            </div>
            <button className="icon-button" onClick={onLogout} aria-label="Sign out" title="Sign out">
              <LogOut size={18} />
            </button>
          </div>
        </div>
        </div>
      </aside>
    </>
  );
}

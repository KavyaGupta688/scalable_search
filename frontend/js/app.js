/**
 * Samsung Prism Enterprise Platform - Application Controller
 * 
 * Manages routing, authentication state, login screen, shell rendering, and toast notifications.
 */

import { api } from './api.js';
import { renderIcon } from './icons.js';
import { renderLoginView } from './views/login.js';
import { renderOverviewView } from './views/overview.js';
import { renderSearchView } from './views/search.js';
import { renderDataSourcesView } from './views/data-sources.js';
import { renderIngestionView } from './views/ingestion.js';
import { renderEnrichmentView } from './views/enrichment.js';
import { renderAuditView } from './views/audit.js';
import { openDocumentDetailModal } from './views/modal-detail.js';

export class PrismApp {
  constructor() {
    this.appRoot = document.querySelector('#app-root');
    this.toastContainer = document.querySelector('#toast-container');
    this.currentRoute = 'overview';
    this.init();
  }

  init() {
    this.setupEventListeners();
    this.handleRoute();
  }

  setupEventListeners() {
    window.addEventListener('hashchange', () => {
      this.handleRoute();
    });

    // Global Cmd+K / Ctrl+K search shortcut
    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (api.isAuthenticated()) {
          window.location.hash = '#search';
          setTimeout(() => {
            const input = document.querySelector('#search-main-input');
            if (input) input.focus();
          }, 100);
        }
      }
    });
  }

  handleRoute() {
    if (!api.isAuthenticated()) {
      this.renderLogin();
      return;
    }

    const hash = window.location.hash.replace('#', '') || 'overview';
    if (hash === 'login') {
      window.location.hash = '#overview';
      return;
    }

    this.currentRoute = hash;
    this.renderShell();
    this.renderActiveView();
  }

  renderLogin() {
    this.appRoot.innerHTML = '';
    const loginContainer = document.createElement('div');
    this.appRoot.appendChild(loginContainer);

    renderLoginView(loginContainer, {
      onLoginSuccess: () => {
        window.location.hash = '#overview';
        this.handleRoute();
      },
      onShowToast: (msg, type) => this.showToast(msg, type)
    });
  }

  renderShell() {
    // Only render shell structure if not already rendered
    if (document.querySelector('.app-layout')) return;

    this.appRoot.innerHTML = `
      <div class="app-layout">
        <!-- Sidebar -->
        <aside class="app-sidebar">
          <div class="sidebar-brand">
            <div class="brand-logo-icon">
              ${renderIcon('prism')}
            </div>
            <div class="brand-text-group">
              <span class="brand-title">Samsung Prism</span>
              <span class="brand-subtitle">S3 Multimodal Platform</span>
            </div>
          </div>

          <nav class="sidebar-nav">
            <div class="nav-section-title">Navigation</div>
            <a href="#overview" class="nav-item ${this.currentRoute === 'overview' ? 'active' : ''}" data-route="overview">
              ${renderIcon('overview')} Overview
            </a>
            <a href="#search" class="nav-item ${this.currentRoute === 'search' ? 'active' : ''}" data-route="search">
              ${renderIcon('search')} Multimodal Search
            </a>
            <a href="#data-sources" class="nav-item ${this.currentRoute === 'data-sources' ? 'active' : ''}" data-route="data-sources">
              ${renderIcon('s3')} S3 Buckets
            </a>
            <a href="#ingestion" class="nav-item ${this.currentRoute === 'ingestion' ? 'active' : ''}" data-route="ingestion">
              ${renderIcon('ingestion')} S3 Ingestion
            </a>
            <a href="#enrichment" class="nav-item ${this.currentRoute === 'enrichment' ? 'active' : ''}" data-route="enrichment">
              ${renderIcon('cpu')} AI Enrichment
            </a>
            <a href="#audit" class="nav-item ${this.currentRoute === 'audit' ? 'active' : ''}" data-route="audit">
              ${renderIcon('audit')} Audit Log
            </a>
          </nav>

          <div class="sidebar-footer">
            <div class="user-profile-widget">
              <div class="user-avatar-badge">AD</div>
              <div class="user-meta-group">
                <span class="user-name-text">admin@samsung.com</span>
                <span class="user-role-text">Platform Admin</span>
              </div>
              <button class="btn btn-ghost btn-sm" id="btn-sidebar-logout" title="Sign out" style="padding: 4px; color: var(--text-muted);">
                ${renderIcon('logout')}
              </button>
            </div>
          </div>
        </aside>

        <!-- Main Wrapper -->
        <div class="app-main-wrapper">
          <!-- Top Persistent Header -->
          <header class="app-header">
            <div class="header-left">
              <div class="env-pill">
                <span class="badge-dot" style="background-color: var(--status-success);"></span>
                <span>PRD-AP-EAST-1</span>
              </div>
              <span class="header-separator">/</span>
              <span class="org-context-title">Samsung Electronics · Semiconductor & Display Fabric</span>
            </div>

            <div class="header-right">
              <button class="command-search-trigger" id="btn-cmd-search">
                ${renderIcon('search')}
                <span class="search-hint-text">Search S3 Objects...</span>
                <kbd class="kbd-shortcut">⌘K</kbd>
              </button>

              <button class="btn btn-ghost btn-sm" id="btn-header-logout" title="Sign out">
                ${renderIcon('logout')} Sign out
              </button>
            </div>
          </header>

          <!-- Main View Mount Area -->
          <main class="app-main-view" id="view-mount-point"></main>
        </div>
      </div>
    `;

    // Bind Logout
    const logoutHandler = () => {
      api.logout();
      this.showToast('Signed out of data platform', 'info');
      window.location.hash = '#login';
      this.handleRoute();
    };

    const sidebarLogout = document.querySelector('#btn-sidebar-logout');
    if (sidebarLogout) sidebarLogout.addEventListener('click', logoutHandler);

    const headerLogout = document.querySelector('#btn-header-logout');
    if (headerLogout) headerLogout.addEventListener('click', logoutHandler);

    // Bind Search Trigger
    const cmdSearch = document.querySelector('#btn-cmd-search');
    if (cmdSearch) {
      cmdSearch.addEventListener('click', () => {
        window.location.hash = '#search';
      });
    }
  }

  renderActiveView() {
    const mount = document.querySelector('#view-mount-point');
    if (!mount) return;

    // Update active state in sidebar
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
      if (item.dataset.route === this.currentRoute) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    mount.innerHTML = '';
    const viewContainer = document.createElement('div');
    viewContainer.className = 'view-content-wrapper';
    mount.appendChild(viewContainer);

    const callbacks = {
      onNavigate: (route) => {
        window.location.hash = `#${route}`;
      },
      onOpenDocument: (docId) => {
        openDocumentDetailModal(docId, {
          onShowToast: (msg, type) => this.showToast(msg, type)
        });
      },
      onShowToast: (msg, type) => this.showToast(msg, type)
    };

    switch (this.currentRoute) {
      case 'overview':
        renderOverviewView(viewContainer, callbacks);
        break;
      case 'search':
        renderSearchView(viewContainer, callbacks);
        break;
      case 'data-sources':
        renderDataSourcesView(viewContainer, callbacks);
        break;
      case 'ingestion':
        renderIngestionView(viewContainer, callbacks);
        break;
      case 'enrichment':
        renderEnrichmentView(viewContainer, callbacks);
        break;
      case 'audit':
        renderAuditView(viewContainer, callbacks);
        break;
      default:
        renderOverviewView(viewContainer, callbacks);
        break;
    }
  }

  showToast(message, type = 'info') {
    if (!this.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span>${type === 'success' ? renderIcon('check') : renderIcon('alert')}</span>
      <span>${message}</span>
    `;
    this.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 250);
    }, 3200);
  }
}

// Initialize on DOM ready
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    window.prismApp = new PrismApp();
  });
}

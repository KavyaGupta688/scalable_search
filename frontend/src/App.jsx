import React, { useState, useEffect } from 'react';
import { api } from './services/api';
import { initialMockData } from './services/mockData';
import { Sidebar } from './components/Shell/Sidebar';
import { Header } from './components/Shell/Header';
import { ToastContainer } from './components/Shell/Toast';
import { ModalDetail } from './components/ModalDetail';

import { LoginView } from './views/LoginView';
import { OverviewView } from './views/OverviewView';
import { SearchView } from './views/SearchView';
import { DataSourcesView } from './views/DataSourcesView';
import { IngestionView } from './views/IngestionView';
import { EnrichmentView } from './views/EnrichmentView';
import { AuditView } from './views/AuditView';

export const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(api.isAuthenticated());
  const [currentRoute, setCurrentRoute] = useState('overview');
  const [activeDocId, setActiveDocId] = useState(null);
  const [toasts, setToasts] = useState([]);

  // Hash-based routing synchronization
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '') || 'overview';
      if (hash === 'login' && isAuthenticated) {
        window.location.hash = '#overview';
        return;
      }
      setCurrentRoute(hash);
    };

    window.addEventListener('hashchange', handleHashChange);
    handleHashChange();

    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [isAuthenticated]);

  // Global Cmd+K / Ctrl+K shortcut
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (isAuthenticated) {
          window.location.hash = '#search';
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isAuthenticated]);

  const showToast = (message, type = 'info') => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const newToast = { id, message, type };
    setToasts((prev) => [...prev, newToast]);

    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3200);
  };

  const handleLogin = (credentials) => {
    api.login(credentials);
    setIsAuthenticated(true);
    window.location.hash = '#overview';
  };

  const handleLogout = () => {
    api.logout();
    setIsAuthenticated(false);
    showToast('Signed out of data platform', 'info');
    window.location.hash = '#login';
  };

  const handleNavigate = (route) => {
    window.location.hash = `#${route}`;
  };

  if (!isAuthenticated) {
    return (
      <>
        <LoginView onLogin={handleLogin} onShowToast={showToast} />
        <ToastContainer toasts={toasts} />
      </>
    );
  }

  const renderActiveView = () => {
    switch (currentRoute) {
      case 'overview':
        return <OverviewView onNavigate={handleNavigate} onOpenDocument={setActiveDocId} />;
      case 'search':
        return <SearchView onOpenDocument={setActiveDocId} onShowToast={showToast} />;
      case 'data-sources':
        return <DataSourcesView onShowToast={showToast} />;
      case 'ingestion':
        return <IngestionView onShowToast={showToast} />;
      case 'enrichment':
        return <EnrichmentView onShowToast={showToast} />;
      case 'audit':
        return (initialMockData.currentUser.role === 'Administrator' || initialMockData.currentUser.role === 'admin')
          ? <AuditView onShowToast={showToast} />
          : <OverviewView onNavigate={handleNavigate} onOpenDocument={setActiveDocId} />;
      default:
        return <OverviewView onNavigate={handleNavigate} onOpenDocument={setActiveDocId} />;
    }
  };

  return (
    <div className="flex min-h-screen bg-prism-bg text-prism-textPrimary font-sans">
      {/* Sidebar */}
      <Sidebar
        currentRoute={currentRoute}
        onNavigate={handleNavigate}
        onLogout={handleLogout}
        currentUser={initialMockData.currentUser}
      />

      {/* Main Wrapper */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        <Header
          onOpenSearch={() => handleNavigate('search')}
          onLogout={handleLogout}
        />
        <main key={currentRoute} className="flex-1 p-6 lg:p-8 max-w-7xl w-full mx-auto page-transition">
          {renderActiveView()}
        </main>
      </div>

      {/* Document Detail Inspector Modal */}
      {activeDocId && (
        <ModalDetail
          docId={activeDocId}
          onClose={() => setActiveDocId(null)}
          onShowToast={showToast}
        />
      )}

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} />
    </div>
  );
};

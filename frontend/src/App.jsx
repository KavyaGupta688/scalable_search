import React, { useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { RequireAuth } from './components/RequireAuth';
import { ToastContainer } from './components/Shell/Toast';
import { PublicMotionLayout } from './components/Motion';

// Public pages
import { LandingView } from './views/LandingView';
import { AdminLoginView } from './views/AdminLoginView';
import { UserLoginView } from './views/UserLoginView';
import { RegisterView } from './views/RegisterView';

// Admin shell + views
import { AdminShell } from './views/AdminShell';
import { OverviewView } from './views/OverviewView';
import { SearchView } from './views/SearchView';
import { DataSourcesView } from './views/DataSourcesView';
import { IngestionView } from './views/IngestionView';
import { EnrichmentView } from './views/EnrichmentView';
import { AuditView } from './views/AuditView';
import { UserManagementView } from './views/UserManagementView';

// User shell + views
import { UserShell } from './views/UserShell';
import { UserSearchView } from './views/UserSearchView';
import { UserDownloadsView } from './views/UserDownloadsView';

/**
 * App — Root component.
 * Toast state lives here so it can be passed down via context or props.
 */
export const App = () => {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, type = 'info') => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3200);
  }, []);

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* ── Public ─────────────────────────────────────────────────────── */}
          <Route element={<PublicMotionLayout />}>
          <Route path="/" element={<LandingView />} />
          <Route path="/login/admin" element={<AdminLoginView showToast={showToast} />} />
          <Route path="/login/user" element={<UserLoginView showToast={showToast} />} />
          <Route path="/register" element={<RegisterView showToast={showToast} />} />
          </Route>

          {/* ── Admin track ─────────────────────────────────────────────────── */}
          <Route
            path="/admin"
            element={
              <RequireAuth role="admin">
                <AdminShell showToast={showToast} />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="overview" replace />} />
            <Route path="overview" element={<OverviewView showToast={showToast} />} />
            <Route path="search" element={<SearchView showToast={showToast} />} />
            <Route path="data-sources" element={<DataSourcesView showToast={showToast} />} />
            <Route path="ingestion" element={<IngestionView showToast={showToast} />} />
            <Route path="enrichment" element={<EnrichmentView showToast={showToast} />} />
            <Route path="audit" element={<AuditView showToast={showToast} />} />
            <Route path="downloads" element={<UserDownloadsView showToast={showToast} administrator />} />
            <Route path="users" element={<UserManagementView showToast={showToast} />} />
          </Route>

          {/* ── User track ──────────────────────────────────────────────────── */}
          <Route
            path="/user"
            element={
              <RequireAuth role="user">
                <UserShell showToast={showToast} />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="search" replace />} />
            <Route path="search" element={<UserSearchView showToast={showToast} />} />
            <Route path="downloads" element={<UserDownloadsView showToast={showToast} />} />
          </Route>

          {/* ── Fallback ────────────────────────────────────────────────────── */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>

        <ToastContainer toasts={toasts} />
      </AuthProvider>
    </BrowserRouter>
  );
};

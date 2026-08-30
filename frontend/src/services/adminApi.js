/**
 * adminApi.js — Admin-only API client.
 * Covers: Connectors, Ingestion jobs, Audit logs.
 */
import { api } from './api';

const getToken = () => localStorage.getItem('nexus_token');

const headers = () => ({
  'Content-Type': 'application/json',
  ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
});

async function handleResponse(res) {
  if (res.status === 401) {
    localStorage.removeItem('nexus_token');
    localStorage.removeItem('nexus_role');
    window.location.href = '/';
    return;
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Connectors ──────────────────────────────────────────────────────────────

/**
 * GET /admin/connectors
 * Returns { connectors: Connector[] }
 */
export async function getConnectors() {
  try {
    const res = await fetch('/admin/connectors', { headers: headers() });
    return await handleResponse(res);
  } catch {
    // Fallback to mock
    return {
      connectors: api.getDataSources().map(s => ({
        id: s.id,
        name: s.name,
        source_type: 'S3-compatible',
        endpoint_or_path: s.endpoint,
        status: s.status === 'Connected' ? 'Verified' : 'Unverified',
        created_at: s.lastSync,
        syncMode: s.syncStatus,
        fileTypes: s.fileTypes,
        region: s.region,
        authType: s.authType,
        discoveredFiles: s.discoveredFiles,
        totalBytes: s.totalBytes,
      })),
    };
  }
}

/**
 * POST /admin/connectors
 * @param {object} payload — connector config (credentials go to Vault server-side)
 */
export async function createConnector(payload) {
  try {
    const res = await fetch('/admin/connectors', {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(payload),
    });
    return await handleResponse(res);
  } catch (e) {
    // Mock: simulate creation
    return {
      id: `connector-${Date.now()}`,
      name: payload.name,
      source_type: payload.source_type,
      endpoint_or_path: payload.endpoint_url || payload.share_path || '',
      status: 'Unverified',
      created_at: new Date().toISOString(),
    };
  }
}

/**
 * POST /admin/connectors/{id}/test
 */
export async function testConnector(connectorId) {
  try {
    const res = await fetch(`/admin/connectors/${connectorId}/test`, {
      method: 'POST',
      headers: headers(),
    });
    return await handleResponse(res);
  } catch {
    // Mock: randomly simulate success/fail for demo
    const ok = Math.random() > 0.3;
    return { status: ok ? 'Verified' : 'Failed', message: ok ? 'Connection successful' : 'Connection timed out' };
  }
}

// ── Ingestion ────────────────────────────────────────────────────────────────

/**
 * GET /ingestion/{ingestion_id}
 */
export async function getIngestionJob(ingestionId) {
  try {
    const res = await fetch(`/ingestion/${ingestionId}`, { headers: headers() });
    return await handleResponse(res);
  } catch {
    return null;
  }
}

// ── Audit ────────────────────────────────────────────────────────────────────

/**
 * GET /api/audit/logs
 * @param {object} filters — { date_range_start, date_range_end, action_type, user_id, page, page_size }
 */
export async function getAuditLogs(filters = {}) {
  try {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    if (!params.has('page')) params.set('page', '1');
    if (!params.has('page_size')) params.set('page_size', '50');
    const res = await fetch(`/api/audit/logs?${params}`, { headers: headers() });
    return await handleResponse(res);
  } catch {
    // Fallback to mock
    const events = api.getAuditEvents();
    return { events, total: events.length, page: 1, page_size: 50 };
  }
}

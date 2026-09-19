/**
 * downloadApi.js — Download & Auditing Module client.
 * Endpoint prefix: /downloads
 */

import { recordDownload } from './downloadHistory.js';

const getToken = () => localStorage.getItem('nexus_token');

const headers = () => ({
  'Content-Type': 'application/json',
  ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
});

async function handleResponse(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * POST /downloads/batch
 * @param {string[]} fileIds — 1..100 file IDs
 * Returns { download_id, status: "building", file_count }
 */
export async function createBatchDownload(fileIds) {
  try {
    const res = await fetch('/downloads/batch', {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ file_ids: fileIds }),
    });
    const data = await handleResponse(res);
    recordDownload({ ...data, file_count: data.file_count ?? fileIds.length });
    return data;
  } catch {
    // Mock
    const data = { download_id: `dl-mock-${globalThis.crypto.randomUUID()}`, status: 'building', file_count: fileIds.length, simulated: true };
    recordDownload(data);
    return data;
  }
}

/**
 * GET /downloads/{download_id}
 * Returns { download_id, status: "building"|"ready"|"failed", updated_at, download_url? }
 */
export async function getDownloadStatus(downloadId) {
  if (downloadId.startsWith('dl-mock-')) {
    const data = { download_id: downloadId, status: 'ready', updated_at: new Date().toISOString(), download_url: null, simulated: true };
    recordDownload(data);
    return data;
  }
  try {
    const res = await fetch(`/downloads/${downloadId}`, { headers: headers() });
    const data = await handleResponse(res);
    recordDownload({ ...data, download_id: downloadId });
    return data;
  } catch {
    // A real job with an unavailable API is not a completed prototype download.
    throw new Error('Unable to refresh download status. Please try again.');
  }
}

/**
 * GET /downloads/audit/events
 * Currently a stub endpoint on the backend.
 */
export async function getDownloadAuditEvents() {
  try {
    const res = await fetch('/downloads/audit/events', { headers: headers() });
    const data = await handleResponse(res);
    return data.events || [];
  } catch {
    return [];
  }
}

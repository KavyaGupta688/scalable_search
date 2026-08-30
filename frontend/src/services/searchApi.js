/**
 * searchApi.js — Multimodal Search Module client.
 * Endpoint prefix: /search
 * Falls back to mock data when backend is unavailable.
 */
import { api } from './api';

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
 * POST /search
 * @param {string} query
 * @param {"text"|"vector"|"similar"} mode
 * @param {string|null} contentType
 * @param {number} limit
 */
export async function search(query, mode = 'text', contentType = null, limit = 20) {
  try {
    const body = { query, mode, limit };
    if (contentType) body.content_type = contentType;
    const res = await fetch('/search', { method: 'POST', headers: headers(), body: JSON.stringify(body) });
    return await handleResponse(res);
  } catch {
    // Fallback to mock
    const results = api.search(query, contentType ? [contentType] : []);
    return {
      query,
      mode,
      total: results.length,
      results: results.map(d => ({
        file_id: d.id,
        name: d.filename,
        content_type: d.modality,
        description: d.description,
        tags: d.tags,
        score: d.confidenceScore,
        created_at: d.indexedAt,
      })),
    };
  }
}

/**
 * GET /search/facets
 */
export async function getFacets() {
  try {
    const res = await fetch('/search/facets', { headers: headers() });
    return await handleResponse(res);
  } catch {
    return { content_type: ['image', 'video', 'document', 'audio', 'tabular'] };
  }
}

/**
 * GET /search/suggestions?q=
 * @param {string} q
 */
export async function getSuggestions(q) {
  try {
    const res = await fetch(`/search/suggestions?q=${encodeURIComponent(q)}`, { headers: headers() });
    const data = await handleResponse(res);
    return data.suggestions || data;
  } catch {
    return [];
  }
}

/**
 * GET /search/trending
 */
export async function getTrending() {
  try {
    const res = await fetch('/search/trending', { headers: headers() });
    return await handleResponse(res);
  } catch {
    return {
      terms: [
        { query: 'Optical inspection', count: 142 },
        { query: 'Defect telemetry', count: 98 },
        { query: 'Panel assembly', count: 87 },
        { query: 'Quality records', count: 74 },
        { query: 'Sensor logs', count: 61 },
      ],
    };
  }
}

/**
 * GET /datasets/popular
 */
export async function getPopularDatasets() {
  try {
    const res = await fetch('/datasets/popular', { headers: headers() });
    return await handleResponse(res);
  } catch {
    return {
      datasets: [
        { id: 'ds-001', name: 'Production Inspection Images', file_count: 6820100, view_count_7d: 842 },
        { id: 'ds-002', name: 'Defect Telemetry Records', file_count: 3920400, view_count_7d: 619 },
        { id: 'ds-003', name: 'Multimodal R&D Archive', file_count: 2420800, view_count_7d: 441 },
        { id: 'ds-004', name: 'Cleanroom Sensor Streams', file_count: 1731110, view_count_7d: 387 },
      ],
    };
  }
}

/**
 * GET /files/{file_id}
 */
export async function getFile(fileId) {
  try {
    const res = await fetch(`/files/${fileId}`, { headers: headers() });
    return await handleResponse(res);
  } catch {
    return api.getDocument(fileId);
  }
}

/**
 * POST /events/search
 */
export async function postSearchEvent(actionType, payload = {}) {
  try {
    await fetch('/events/search', {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ action_type: actionType, ...payload }),
    });
  } catch {
    // Fire-and-forget; silently ignore failures
  }
}

/**
 * POST /search/similar
 */
export async function searchSimilar(fileId, limit = 8) {
  try {
    const res = await fetch('/search/similar', {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ file_id: fileId, limit }),
    });
    return await handleResponse(res);
  } catch {
    return { query: fileId, mode: 'similar', total: 0, results: [] };
  }
}

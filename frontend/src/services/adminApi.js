import { request } from './http.js';
import { connectorView, auditView } from './presentation.js';

export async function getConnectors(signal) {
  const rows = await request('/admin/connectors?limit=100', {signal});
  return {connectors: rows.map(connectorView)};
}
export const createConnector = body => request('/admin/connectors', {method: 'POST', body});
export const testConnector = async id => {
  const result = await request(`/admin/connectors/${encodeURIComponent(id)}/test`, {method: 'POST'});
  return {...result, status: result.status.charAt(0).toUpperCase() + result.status.slice(1)};
};
export const startScan = id => request(`/admin/ingestion/trigger/${encodeURIComponent(id)}`, {method: 'POST'});
export const archiveConnector = id => request(`/admin/connectors/${encodeURIComponent(id)}/archive`, {method: 'PATCH'});
export const deleteConnector = id => request(`/admin/connectors/${encodeURIComponent(id)}`, {method: 'DELETE'});
export async function getAuditLogs(filters, signal) {
  const params = new URLSearchParams({page: filters.page || 1, page_size: filters.page_size || 50});
  for (const [key, value] of Object.entries({action: filters.action_type, actor: filters.user_id, status: filters.status})) {
    if (value) params.set(key, value);
  }
  const data = await request(`/api/audit/logs?${params}`, {signal});
  return {...data, events: data.events.map(auditView)};
}

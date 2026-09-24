import { request } from './http.js';
export const createBatchDownload = (file_ids, details = {}) => request('/downloads/batch', {method:'POST',body:{file_ids, ...details}});
export const previewDownload = (file_ids, signal) => request('/downloads/preview', {method:'POST', signal, body:{file_ids}});
export const getDownloadStatus = (id) => request(`/downloads/${encodeURIComponent(id)}`);
export const getDownloadHistory = (offset=0) => request(`/downloads?limit=25&offset=${offset}`);

// Size and limits of downloading the top `count` results of a search (all results when count is null).
// With includeIds the response also carries the file ids to pass to createBatchDownload.
export const planDownload = ({query, mode, filters = {}}, {count = null, includeIds = false, signal} = {}) =>
  request('/search/download-plan', {method:'POST', signal, body:{query, search_mode:mode, filters, count, include_ids:includeIds}});

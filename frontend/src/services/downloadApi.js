import { request } from './http.js';
export const createBatchDownload = (file_ids) => request('/downloads/batch', {method:'POST',body:{file_ids}});
export const getDownloadStatus = (id) => request(`/downloads/${encodeURIComponent(id)}`);
export const getDownloadHistory = (offset=0) => request(`/downloads?limit=25&offset=${offset}`);

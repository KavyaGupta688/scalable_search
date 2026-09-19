import { request } from './http.js';
export const search = (query, mode = 'hybrid', filters = {}, limit = 20, offset = 0, signal) => request('/search', {method:'POST', body:{query, search_mode:mode, filters, limit, offset}, signal});
export const getSuggestions = async (q, signal) => (await request(`/search/suggestions?q=${encodeURIComponent(q)}&limit=8`, {signal})).suggestions;
export const getTrending = () => request('/search/trending');
export const getPopularDatasets = async () => { const d=await request('/datasets/popular'); return {...d,datasets:d.datasets.map(row=>({...row,dataset_id:row.id,dataset_name:row.name}))}; };
export const getFile = (id, signal) => request(`/files/${encodeURIComponent(id)}`, {signal});
export const getSimilar = (id, filters = {}, signal) => request('/search/similar', {method:'POST',body:{file_id:id, filters, limit:20},signal});
export const postSearchEvent = (event_type, data = {}) => request('/events/search', {method:'POST',body:{event_type,...data}});

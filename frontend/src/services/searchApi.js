import { request } from './http.js';
import { fileView, modality } from './presentation.js';
export const search = (query, mode = 'hybrid', filters = {}, limit = 20, offset = 0, signal) => request('/search', {method:'POST', body:{query, search_mode:mode, filters, limit, offset}, signal});
export const getSuggestions = async (q, signal) => (await request(`/search/suggestions?q=${encodeURIComponent(q)}&limit=8`, {signal})).suggestions;
export const getTrending = async () => {const data = await request('/search/trending'); return {...data, terms: data.trending.map(t => ({...t, count:t.search_count}))};};
export const getPopularDatasets = async () => { const d=await request('/datasets/popular'); return {...d,datasets:d.datasets.map(row=>({...row,dataset_id:row.id,dataset_name:row.name}))}; };
export const getFile = async (id, signal) => fileView(await request(`/files/${encodeURIComponent(id)}`, {signal}));
export const getSimilar = (id, filters = {}, signal) => request('/search/similar', {method:'POST',body:{file_id:id, filters, limit:20},signal});
export const postSearchEvent = (event_type, data = {}) => request('/events/search', {method:'POST',body:{event_type,...data}});
export const getFacets = async signal => { const data = await request('/search/facets', {signal}); return {...data, content_type:data.file_types.map(f => modality(f.value))}; };
export const searchSimilar = async (id, limit = 8, filters = {}, signal) => {
  const data = await request('/search/similar', {method:'POST',body:{file_id:id, filters, limit},signal});
  return {...data, results:data.results.map(fileView)};
};

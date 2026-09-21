import { modality } from './presentation.js';

export const MODALITIES = [
  { id: 'image', label: 'Images' },
  { id: 'video', label: 'Videos' },
  { id: 'document', label: 'Documents' },
  { id: 'audio', label: 'Audio' },
  { id: 'tabular', label: 'Tabular' },
];

// Per-modality counts from the backend file_types facet, or null while facets are unavailable.
export function modalityCounts(facets) {
  if (!Array.isArray(facets?.file_types)) return null;
  const counts = Object.fromEntries(MODALITIES.map(m => [m.id, 0]));
  for (const { value, count } of facets.file_types) {
    const id = modality(value);
    if (id in counts) counts[id] += count;
  }
  return counts;
}

// Count for one facet bucket (e.g. facetCount(facets, 'ai_generated', true)), undefined if absent.
export const facetCount = (facets, source, value) =>
  facets?.[source]?.find(bucket => String(bucket.value) === String(value))?.count;

export const formatCount = count => (typeof count === 'number' ? count.toLocaleString() : '–');

// Photo/video resolution tiers, judged by the longer edge. Ids match the backend.
export const RESOLUTIONS = [
  { id: '4k', label: '4K', hint: 'Longer edge 3840 px or more' },
  { id: '2k', label: '2K / QHD', hint: 'Longer edge 2560-3839 px' },
  { id: 'fhd', label: 'Full HD', hint: 'Longer edge 1920-2559 px' },
  { id: 'hd', label: 'HD', hint: 'Longer edge 1280-1919 px' },
  { id: 'sd', label: 'Below HD', hint: 'Longer edge under 1280 px' },
];

// Per-tier counts (plus `unknown`) from the backend resolutions facet, or null while unavailable.
export function resolutionCounts(facets) {
  if (!Array.isArray(facets?.resolutions)) return null;
  const counts = Object.fromEntries([...RESOLUTIONS.map(r => r.id), 'unknown'].map(id => [id, 0]));
  for (const { value, count } of facets.resolutions) {
    if (value in counts) counts[value] += count;
  }
  return counts;
}

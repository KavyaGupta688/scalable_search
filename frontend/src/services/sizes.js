// File-size buckets. Ids match the backend; sizes use 1 KB = 1024 bytes, as file managers show them.
export const SIZES = [
  { id: 'lt100k', label: 'Under 100 KB', hint: 'Smaller than 100 KB' },
  { id: '100k-1m', label: '100 KB – 1 MB', hint: '100 KB up to 1 MB' },
  { id: '1m-10m', label: '1 – 10 MB', hint: '1 MB up to 10 MB' },
  { id: '10m-100m', label: '10 – 100 MB', hint: '10 MB up to 100 MB' },
  { id: '100m-1g', label: '100 MB – 1 GB', hint: '100 MB up to 1 GB' },
  { id: 'gte1g', label: '1 GB and larger', hint: '1 GB or more' },
];

// Per-bucket counts from the backend sizes facet, or null while unavailable.
export function sizeCounts(facets) {
  if (!Array.isArray(facets?.sizes)) return null;
  const counts = Object.fromEntries(SIZES.map(s => [s.id, 0]));
  for (const { value, count } of facets.sizes) {
    if (value in counts) counts[value] += count;
  }
  return counts;
}

const MB = 1024 ** 2;

// Bytes as file managers show them: 1 KB = 1024 bytes, one decimal from KB upward.
export function formatBytes(bytes) {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes) || bytes < 0) return '–';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes, unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return unit === 0 ? `${bytes} B` : `${value.toFixed(1)} ${units[unit]}`;
}

export const bytesToMb = bytes => (bytes == null ? '' : Math.round((bytes / MB) * 100) / 100);
export const mbToBytes = mb => Math.round(Number(mb) * MB);

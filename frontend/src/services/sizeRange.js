// Logarithmic scale gives small files useful slider travel alongside multi-GB files.
export const SIZE_RANGE_MAX = 20 * 1024 ** 3;
export const sizeAt = position => position <= 0 ? 0 : Math.round(1024 * (SIZE_RANGE_MAX / 1024) ** (position / 100));
export const positionAt = bytes => bytes <= 0 ? 0 : Math.max(0, Math.min(100, Math.log(bytes / 1024) / Math.log(SIZE_RANGE_MAX / 1024) * 100));
export const sizeRangeFilters = (minimum, maximum) => ({
  min_size: minimum === 0 ? undefined : sizeAt(minimum),
  max_size: maximum === 100 ? undefined : sizeAt(maximum),
  size_buckets: undefined,
});

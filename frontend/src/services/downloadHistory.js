const KEY = 'nexus_downloads';
export const HISTORY_EVENT = 'nexus-downloads-updated';

export function getDownloadHistory() {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || '[]');
    return Array.isArray(value) ? value : [];
  } catch { return []; }
}

export function recordDownload(update) {
  if (!update?.download_id) return;
  const history = getDownloadHistory();
  const index = history.findIndex(item => item.download_id === update.download_id);
  if (index < 0) history.unshift({ created_at: new Date().toISOString(), ...update });
  else history[index] = { ...history[index], ...update };
  localStorage.setItem(KEY, JSON.stringify(history));
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(HISTORY_EVENT));
  return history;
}

import { authHeaders } from './auth.js';

export async function request(path, { body, headers, ...options } = {}) {
  const response = await fetch(path, {
    ...options, headers: { ...authHeaders(), ...headers },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail || error.message || `HTTP ${response.status}`);
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

export async function protectedBlob(path, { signal, maximum = 2 * 1024 ** 3 } = {}) {
  const response = await fetch(path, { headers: authHeaders(), signal });
  if (!response.ok) throw new Error(`Content unavailable (HTTP ${response.status})`);
  const reader = response.body.getReader();
  const chunks = []; let length = 0;
  try {
    const declaredLength = Number(response.headers.get('content-length'));
    if (Number.isFinite(declaredLength) && declaredLength > maximum) {
      throw new Error('Content exceeds the browser size limit');
    }
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > maximum) throw new Error('Content exceeds the browser size limit');
      chunks.push(value);
    }
  } finally { await reader.cancel(); reader.releaseLock(); }
  return new Blob(chunks, { type: response.headers.get('content-type') || 'application/octet-stream' });
}

export async function saveArchive(id, part = 1, parts = 1, expectedBytes, {onProgress = () => {}, signal} = {}) {
  const filename = parts > 1 ? `assets-${id}-part${part}.zip` : `assets-${id}.zip`;
  // Ask while the Save click still has browser user activation, before any network wait.
  const handle = typeof window.showSaveFilePicker === 'function'
    ? await window.showSaveFilePicker({suggestedName: filename, types:[{description:'ZIP archive',accept:{'application/zip':['.zip']}}]}) : null;
  const query = parts > 1 || part > 1 ? `?part=${part}` : '';
  const started = performance.now();
  let bytes = 0, total = expectedBytes || 0, reader, writable, timer;
  const samples = [{time:started, bytes:0}];
  const report = (state = 'downloading') => {
    const now = performance.now();
    samples.push({time:now, bytes});
    while(samples.length > 2 && samples[1].time < now - 3000) samples.shift();
    const speed = (bytes - samples[0].bytes) / Math.max((now - samples[0].time) / 1000, 0.001);
    const elapsed = (now - started) / 1000;
    const stats = {state, filename:handle?.name || filename, bytes, total, speed, elapsed,
      average:bytes / Math.max(elapsed, 0.001), remaining:speed > 0 && total ? Math.max(0,(total-bytes)/speed) : null,
      completedAt:state === 'saved' || state === 'handed-off' ? new Date().toISOString() : null};
    onProgress(stats); return stats;
  };
  try {
    report(); timer = setInterval(() => report(), 250);
    const response = await fetch(`/downloads/${encodeURIComponent(id)}/content${query}`, {headers:authHeaders(), signal});
    if (!response.ok) throw new Error(`Download unavailable (HTTP ${response.status}). Refresh the request and try again.`);
    total = Number(response.headers.get('content-length')) || total;
    if (handle) writable = await handle.createWritable();
    reader = response.body.getReader();
    const chunks = [];
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      if (writable) await writable.write(value); else chunks.push(value);
      bytes += value.byteLength;
    }
    if (total && bytes !== total) throw new Error('Download was interrupted: received size does not match the archive. Retry saving.');
    if (writable) { await writable.close(); writable = null; }
    else {
      const url = URL.createObjectURL(new Blob(chunks, {type:'application/zip'}));
      const a = document.createElement('a'); a.href=url; a.download=filename; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    }
    return report(handle ? 'saved' : 'handed-off');
  } finally {
    clearInterval(timer);
    if (reader) { await reader.cancel().catch(() => {}); reader.releaseLock(); }
    if (writable) await writable.abort().catch(() => {});
  }
}

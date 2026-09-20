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

export async function saveArchive(id) {
  const blob = await protectedBlob(`/downloads/${encodeURIComponent(id)}/content`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = `assets-${id}.zip`; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

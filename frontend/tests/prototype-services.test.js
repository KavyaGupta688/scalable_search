import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { search } from '../src/services/searchApi.js';
import { api } from '../src/services/api.js';
import { createConnector, getConnectors } from '../src/services/adminApi.js';
import { createBatchDownload, getDownloadStatus } from '../src/services/downloadApi.js';
import { getDownloadHistory } from '../src/services/downloadHistory.js';

beforeEach(() => {
  const store = new Map();
  globalThis.localStorage = { getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value), removeItem: key => store.delete(key) };
  globalThis.fetch = async () => { throw new Error('Offline fixture'); };
});

test('offline search preserves record metadata, filters, total, and limit', async () => {
  const result = await search('', 'vector', null, 2);
  assert.equal(result.total, api.documents.length);
  assert.equal(result.results.length, 2);
  const doc = api.getDocument(result.results[0].file_id);
  assert.equal(result.results[0].description, doc.aiDescription);
  assert.equal(result.results[0].created_at, doc.createdAt);
  assert.ok(result.results[0].score >= 0 && result.results[0].score <= 1);
  const filtered = await search('', 'text', 'image', 100);
  assert.ok(filtered.results.length > 0);
  assert.ok(filtered.results.every(item => item.content_type === 'image'));
  assert.equal((await search('no-match-xyz-123')).total, 0);
});

test('successful search keeps the API response and request contract', async () => {
  const fixture = { query: 'launch', mode: 'text', total: 1, results: [{ file_id: 'live-1', name: 'Launch' }] };
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/search');
    assert.deepEqual(JSON.parse(options.body), { query: 'launch', mode: 'text', limit: 20, content_type: 'image' });
    return Response.json(fixture);
  };
  assert.deepEqual(await search('launch', 'text', 'image'), fixture);
});

test('prototype connectors survive a list refresh without removing fixture sources', async () => {
  const before = await getConnectors();
  const created = await createConnector({ name: 'Review NAS', source_type: 'NAS (NFS)', share_path: '/review/data' });
  const after = await getConnectors();
  assert.equal(after.connectors.length, before.connectors.length + 1);
  assert.deepEqual(after.connectors[0], created);
  assert.equal(after.connectors[0].endpoint_or_path, '/review/data');
  for (const source of before.connectors) assert.ok(after.connectors.some(item => item.id === source.id));
});

test('prototype downloads persist initiation and completion with no invented archive URL', async () => {
  localStorage.setItem('nexus_downloads', JSON.stringify([{ download_id: 'old', status: 'ready', file_count: 3, download_url: '/existing.zip' }]));
  const request = await createBatchDownload(['doc-1', 'doc-2']);
  assert.equal(getDownloadHistory()[0].file_count, 2);
  assert.equal(getDownloadHistory()[0].status, 'building');
  const status = await getDownloadStatus(request.download_id);
  assert.equal(status.status, 'ready');
  assert.equal(status.simulated, true);
  assert.equal(status.download_url, null);
  assert.equal(getDownloadHistory()[0].file_count, 2);
  assert.equal(getDownloadHistory().length, 2);
  assert.equal(getDownloadHistory()[1].download_url, '/existing.zip');
});

test('real download status updates the existing history entry and retains its file count', async () => {
  globalThis.fetch = async () => Response.json({ download_id: 'real-1', status: 'building', file_count: 2 });
  await createBatchDownload(['a', 'b']);
  globalThis.fetch = async () => Response.json({ download_id: 'real-1', status: 'ready', download_url: '/archive.zip' });
  await getDownloadStatus('real-1');
  assert.equal(getDownloadHistory().length, 1);
  assert.equal(getDownloadHistory()[0].file_count, 2);
  assert.equal(getDownloadHistory()[0].download_url, '/archive.zip');
});

test('unavailable status for a real job never becomes a fake completed download', async () => {
  await assert.rejects(getDownloadStatus('real-unavailable'), /Unable to refresh/);
  assert.deepEqual(getDownloadHistory(), []);
});

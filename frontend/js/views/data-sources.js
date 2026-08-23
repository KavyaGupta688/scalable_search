/**
 * Samsung Prism Enterprise Platform - S3 Buckets Screen View
 * 
 * Simple, clean management of connected Amazon S3 Buckets.
 */

import { api } from '../api.js';
import { renderIcon } from '../icons.js';

export function renderDataSourcesView(container, { onShowToast }) {
  const sources = api.getDataSources();

  function renderList(filteredSources) {
    const grid = container.querySelector('#sources-grid');
    if (!grid) return;

    if (filteredSources.length === 0) {
      grid.innerHTML = `
        <div class="search-empty-state" style="grid-column: 1 / -1;">
          <div class="empty-state-icon">${renderIcon('s3')}</div>
          <div class="empty-state-title">No S3 Buckets Found</div>
          <div class="empty-state-copy">Try searching for a different bucket name or region.</div>
        </div>
      `;
      return;
    }

    grid.innerHTML = filteredSources.map(src => `
      <div class="source-card" data-source-id="${src.id}">
        <div class="source-card-header">
          <div class="source-title-group">
            <div class="source-name">${src.name}</div>
            <div class="source-type">
              ${renderIcon('s3')} Amazon S3 · ${src.region}
            </div>
          </div>
          <span class="badge badge-success">
            <span class="badge-dot"></span> ${src.status}
          </span>
        </div>

        <div class="source-endpoint mono-text" title="${src.endpoint}">
          ${src.endpoint}
        </div>

        <div class="source-metrics-grid">
          <div class="source-metric">
            <span class="source-metric-label">Discovered Objects</span>
            <span class="source-metric-val">${src.discoveredFiles.toLocaleString()}</span>
          </div>
          <div class="source-metric">
            <span class="source-metric-label">Total Size</span>
            <span class="source-metric-val">${src.totalBytes}</span>
          </div>
        </div>

        <div class="source-card-footer">
          <div class="source-sync-indicator">
            ${renderIcon('refresh')} ${src.syncStatus}
          </div>
          <span class="mono-text">IAM Role Active</span>
        </div>
      </div>
    `).join('');

    // Attach click handlers to open drawer
    grid.querySelectorAll('.source-card').forEach(card => {
      card.addEventListener('click', () => {
        const id = card.dataset.sourceId;
        const source = sources.find(s => s.id === id);
        if (source) openSourceDetail(source);
      });
    });
  }

  function openSourceDetail(src) {
    const modalRoot = document.querySelector('#modal-root');
    modalRoot.innerHTML = `
      <div class="drawer-backdrop" id="source-drawer-backdrop">
        <div class="drawer-panel">
          <div class="drawer-header">
            <div>
              <div class="drawer-title">${src.name}</div>
              <div class="panel-subtitle">Amazon S3 Bucket: ${src.bucketName}</div>
            </div>
            <button class="btn btn-ghost btn-sm" id="btn-close-source-drawer" aria-label="Close">
              ${renderIcon('close')}
            </button>
          </div>

          <div class="drawer-body">
            <div>
              <div class="drawer-section-title">Bucket Configuration</div>
              <div class="drawer-spec-list">
                <span class="spec-key">Status:</span>
                <span class="spec-val">
                  <span class="badge badge-success"><span class="badge-dot"></span> Connected</span>
                </span>
                <span class="spec-key">S3 URI:</span>
                <span class="spec-val mono-text">${src.endpoint}</span>
                <span class="spec-key">AWS Region:</span>
                <span class="spec-val">${src.region}</span>
                <span class="spec-key">Discovered Objects:</span>
                <span class="spec-val">${src.discoveredFiles.toLocaleString()}</span>
                <span class="spec-key">Storage Volume:</span>
                <span class="spec-val">${src.totalBytes}</span>
                <span class="spec-key">Event Notification:</span>
                <span class="spec-val">${src.syncInterval}</span>
                <span class="spec-key">Authentication:</span>
                <span class="spec-val">${src.authType}</span>
                <span class="spec-key">File Formats:</span>
                <span class="spec-val">${src.fileTypes.join(', ')}</span>
              </div>
            </div>

            <div>
              <div class="drawer-section-title">Ingestion Telemetry</div>
              <div class="panel" style="background: var(--bg-surface-elevated); padding: 12px; font-size: 11px; color: var(--text-secondary); line-height: 1.5;">
                S3 object event notifications are streamed via Amazon SQS and S3 EventBridge.
                New binary uploads are validated, checksummed, and enriched with AI tags and 1536-d vectors in real time.
              </div>
            </div>
          </div>

          <div class="detail-drawer-footer">
            <button class="btn btn-ghost btn-sm" id="btn-test-conn">
              ${renderIcon('refresh')} Test S3 Access
            </button>
            <button class="btn btn-primary btn-sm" id="btn-sync-now">
              Trigger S3 Crawl
            </button>
          </div>
        </div>
      </div>
    `;

    const backdrop = modalRoot.querySelector('#source-drawer-backdrop');
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) modalRoot.innerHTML = '';
    });
    modalRoot.querySelector('#btn-close-source-drawer').addEventListener('click', () => {
      modalRoot.innerHTML = '';
    });
    modalRoot.querySelector('#btn-test-conn').addEventListener('click', () => {
      onShowToast('S3 Bucket connection verified: Read/List 200 OK (12ms latency)', 'success');
    });
    modalRoot.querySelector('#btn-sync-now').addEventListener('click', () => {
      onShowToast(`Dispatched S3 crawl for ${src.bucketName}`, 'info');
      modalRoot.innerHTML = '';
    });
  }

  function openAddSourceModal() {
    const modalRoot = document.querySelector('#modal-root');
    modalRoot.innerHTML = `
      <div class="modal-backdrop" id="add-source-backdrop">
        <div class="modal-content">
          <div class="modal-header">
            <div class="modal-title">Connect Amazon S3 Bucket</div>
            <button class="btn btn-ghost btn-sm" id="btn-close-add-modal" aria-label="Close">
              ${renderIcon('close')}
            </button>
          </div>
          <form id="add-source-form">
            <div class="modal-body">
              <div class="form-group">
                <label class="form-label">S3 Bucket Name</label>
                <input class="form-input mono-text" id="new-bucket-name" placeholder="samsung-inspection-dataset" required />
                <span class="form-hint">Must be an existing S3 bucket in your AWS organization.</span>
              </div>

              <div class="form-group">
                <label class="form-label">Display Name</label>
                <input class="form-input" id="new-src-name" placeholder="e.g. Production Line 02 Inspection S3" required />
              </div>

              <div class="form-group">
                <label class="form-label">AWS Region</label>
                <input class="form-input" id="new-src-region" value="ap-northeast-2 (Seoul)" required />
              </div>

              <div class="form-group">
                <label class="form-label">IAM Role ARN for Ingestion</label>
                <input class="form-input mono-text" id="new-src-arn" value="arn:aws:iam::123456789012:role/SamsungPrismS3IngestRole" required />
              </div>
            </div>

            <div class="modal-footer">
              <button type="button" class="btn btn-ghost" id="btn-cancel-add">Cancel</button>
              <button type="submit" class="btn btn-primary" id="btn-submit-add">Connect S3 Bucket</button>
            </div>
          </form>
        </div>
      </div>
    `;

    const backdrop = modalRoot.querySelector('#add-source-backdrop');
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) modalRoot.innerHTML = '';
    });
    modalRoot.querySelector('#btn-close-add-modal').addEventListener('click', () => modalRoot.innerHTML = '');
    modalRoot.querySelector('#btn-cancel-add').addEventListener('click', () => modalRoot.innerHTML = '');

    modalRoot.querySelector('#add-source-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const name = modalRoot.querySelector('#new-src-name').value.trim();
      const bucketName = modalRoot.querySelector('#new-bucket-name').value.trim();
      const region = modalRoot.querySelector('#new-src-region').value.trim();

      api.addDataSource({ name, bucketName, region });
      modalRoot.innerHTML = '';
      onShowToast(`Connected S3 bucket 's3://${bucketName}/' successfully`, 'success');
      renderList(api.getDataSources());
    });
  }

  container.innerHTML = `
    <div class="sources-container">
      <div class="page-header">
        <div class="page-title-group">
          <span class="page-eyebrow">Object Storage Connectors</span>
          <h1 class="page-title">Amazon S3 Buckets</h1>
          <p class="page-description">
            Connected S3 buckets storing raw multimodal binaries for continuous AI ingestion.
          </p>
        </div>
        <div class="page-actions">
          <button class="btn btn-primary" id="btn-open-add-source">
            ${renderIcon('plus')} Connect S3 Bucket
          </button>
        </div>
      </div>

      <div class="sources-toolbar">
        <div class="sources-search">
          <input class="form-input" id="source-search-input" placeholder="Search S3 buckets..." style="width: 100%;" />
        </div>
        <div class="sources-stats-bar">
          <span>Connected S3 Buckets: <b>${sources.length}</b></span> ·
          <span>Total Discovered: <b>${sources.reduce((acc, s) => acc + s.discoveredFiles, 0).toLocaleString()} objects</b></span>
        </div>
      </div>

      <div class="sources-grid" id="sources-grid"></div>
    </div>
  `;

  renderList(sources);

  container.querySelector('#source-search-input').addEventListener('input', (e) => {
    const term = e.target.value.trim().toLowerCase();
    const filtered = sources.filter(s => 
      s.name.toLowerCase().includes(term) ||
      s.endpoint.toLowerCase().includes(term) ||
      s.region.toLowerCase().includes(term)
    );
    renderList(filtered);
  });

  container.querySelector('#btn-open-add-source').addEventListener('click', openAddSourceModal);
}

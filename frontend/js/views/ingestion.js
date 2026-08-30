/**
 * Samsung Prism Enterprise Platform - S3 Ingestion Monitor
 * 
 * Clean, production-grade monitoring for automated S3 bucket ingestion streams:
 * - Active S3 EventBridge streams and queue telemetry
 * - Deduplication metrics (exact and perceptual SHA-256)
 * - Ingestion batch and streaming jobs table
 * - Job details modal with stage breakdown
 */

import { api } from '../api.js';
import { renderIcon } from '../icons.js';

export function renderIngestionView(container, { onShowToast }) {
  const jobs = api.getIngestionJobs();

  function openJobDetail(job) {
    const modalRoot = document.querySelector('#modal-root');
    modalRoot.innerHTML = `
      <div class="modal-backdrop" id="job-detail-backdrop">
        <div class="modal-content" style="max-width: 600px;">
          <div class="modal-header">
            <div>
              <div class="modal-title">${job.name}</div>
              <div class="panel-subtitle">S3 Bucket: ${job.bucket}</div>
            </div>
            <button class="btn btn-ghost btn-sm" id="btn-close-job-modal" aria-label="Close">
              ${renderIcon('close')}
            </button>
          </div>

          <div class="modal-body" style="display: flex; flex-direction: column; gap: 16px;">
            <div class="spec-grid" style="grid-template-columns: 1fr 1fr; gap: 12px; background: var(--bg-surface-elevated); padding: 14px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
              <div>
                <span class="spec-key-label" style="font-size: 11px; color: var(--text-muted); display: block;">Status:</span>
                <span class="badge ${job.status === 'Completed' ? 'badge-success' : 'badge-info'}">
                  <span class="badge-dot"></span> ${job.status}
                </span>
              </div>
              <div>
                <span class="spec-key-label" style="font-size: 11px; color: var(--text-muted); display: block;">Current S3 Speed:</span>
                <span class="mono-text" style="font-weight: 700; color: var(--brand-primary-text);">${job.currentThroughput}</span>
              </div>
              <div>
                <span class="spec-key-label" style="font-size: 11px; color: var(--text-muted); display: block;">Data Volume:</span>
                <span class="mono-text">${job.dataVolume}</span>
              </div>
              <div>
                <span class="spec-key-label" style="font-size: 11px; color: var(--text-muted); display: block;">Validated S3 Objects:</span>
                <span class="mono-text">${job.validatedCount.toLocaleString()} / ${job.discoveredCount.toLocaleString()}</span>
              </div>
            </div>

            <div>
              <div class="drawer-section-title">Ingestion Stages</div>
              <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 6px;">
                ${job.stages.map(stg => `
                  <div style="display: flex; align-items: center; justify-content: space-between; font-size: 11px; background: var(--bg-surface-elevated); padding: 10px 14px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
                    <span style="font-weight: 600; color: var(--text-primary);">${stg.name}</span>
                    <div style="display: flex; align-items: center; gap: 10px; width: 180px;">
                      <div class="progress-track" style="height: 6px; flex: 1;">
                        <div class="progress-fill ${stg.status === 'completed' ? 'complete' : ''}" style="width: ${stg.progress}%;"></div>
                      </div>
                      <span class="mono-text" style="font-size: 10px; width: 34px; text-align: right;">${stg.progress}%</span>
                    </div>
                  </div>
                `).join('')}
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn btn-ghost" id="btn-close-job-modal-footer">Close</button>
            <button class="btn btn-primary" id="btn-revalidate-job">
              ${renderIcon('refresh')} Trigger S3 Verification
            </button>
          </div>
        </div>
      </div>
    `;

    const backdrop = modalRoot.querySelector('#job-detail-backdrop');
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) modalRoot.innerHTML = '';
    });
    modalRoot.querySelector('#btn-close-job-modal').addEventListener('click', () => modalRoot.innerHTML = '');
    modalRoot.querySelector('#btn-close-job-modal-footer').addEventListener('click', () => modalRoot.innerHTML = '');
    modalRoot.querySelector('#btn-revalidate-job').addEventListener('click', () => {
      onShowToast(`Dispatched S3 checksum verification for ${job.bucket}`, 'info');
      modalRoot.innerHTML = '';
    });
  }

  container.innerHTML = `
    <div class="ingestion-layout">
      <!-- Page Header -->
      <div class="page-header">
        <div class="page-title-group">
          <span class="page-eyebrow">Object Storage Connectors</span>
          <h1 class="page-title">S3 Ingestion Monitor</h1>
          <p class="page-description">
            Automated event streaming, MIME validation, SHA-256 deduplication, and UUID v7 stamping from connected Amazon S3 buckets.
          </p>
        </div>
        <div class="page-actions">
          <button class="btn btn-ghost" id="btn-refresh-jobs">
            ${renderIcon('refresh')} Refresh Streams
          </button>
        </div>
      </div>

      <!-- Ingest Metrics Row -->
      <div class="ingest-metrics-row" style="grid-template-columns: repeat(3, 1fr);">
        <div class="ingest-metric-card">
          <span class="ingest-metric-title">Active S3 Ingest Speed</span>
          <span class="ingest-metric-value" style="color: var(--brand-primary-text);">31.2 GB/s</span>
          <span class="ingest-metric-sub">Continuous S3 EventBridge & SQS feeds</span>
        </div>

        <div class="ingest-metric-card">
          <span class="ingest-metric-title">Validated Today</span>
          <span class="ingest-metric-value">3,561,454</span>
          <span class="ingest-metric-sub">99.1% checksum & MIME pass rate</span>
        </div>

        <div class="ingest-metric-card">
          <span class="ingest-metric-title">Deduplicated</span>
          <span class="ingest-metric-value" style="color: var(--status-warning-text);">31,566</span>
          <span class="ingest-metric-sub">Avoided duplicate AI re-indexing</span>
        </div>
      </div>

      <!-- Ingestion Jobs Table -->
      <div class="ingest-jobs-panel">
        <div class="ingest-panel-header">
          <div class="ingest-panel-title">Active S3 Ingestion Streams</div>
          <span class="mono-text" style="color: var(--text-muted); font-size: 11px;">${jobs.length} Active Streams</span>
        </div>

        <div class="data-table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Stream & S3 Bucket</th>
                <th>Status</th>
                <th>Throughput</th>
                <th>Volume</th>
                <th>Validated Objects</th>
                <th>Progress</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${jobs.map(job => `
                <tr class="job-row" data-job-id="${job.id}" style="cursor: pointer;">
                  <td>
                    <div style="font-weight: 600; color: var(--text-primary);">${job.name}</div>
                    <div class="mono-text" style="font-size: 10px; color: var(--text-muted);">${job.bucket}</div>
                  </td>
                  <td>
                    <span class="badge ${job.status === 'Completed' ? 'badge-success' : 'badge-info'}">
                      <span class="badge-dot"></span> ${job.status}
                    </span>
                  </td>
                  <td class="mono-text" style="font-weight: 600; color: var(--brand-primary-text);">${job.currentThroughput}</td>
                  <td class="mono-text">${job.dataVolume}</td>
                  <td class="mono-text">${job.validatedCount.toLocaleString()} / ${job.discoveredCount.toLocaleString()}</td>
                  <td style="min-width: 140px;">
                    <div class="stage-progress-bar">
                      <div class="progress-track">
                        <div class="progress-fill ${job.status === 'Completed' ? 'complete' : ''}" style="width: ${job.status === 'Completed' ? 100 : 88}%;"></div>
                      </div>
                      <span class="progress-pct">${job.status === 'Completed' ? '100%' : '88%'}</span>
                    </div>
                  </td>
                  <td>
                    <button class="btn btn-sm btn-ghost btn-inspect-job" data-job-id="${job.id}">
                      Inspect
                    </button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  // Bind Job clicks
  container.querySelectorAll('.job-row, .btn-inspect-job').forEach(elem => {
    elem.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = elem.dataset.jobId;
      const job = jobs.find(j => j.id === id);
      if (job) openJobDetail(job);
    });
  });

  // Bind Refresh
  container.querySelector('#btn-refresh-jobs').addEventListener('click', () => {
    onShowToast('Refreshed S3 ingestion telemetry', 'info');
  });
}

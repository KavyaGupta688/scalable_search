/**
 * Samsung Prism Enterprise Platform - Platform Overview View (Simplified)
 * 
 * Clean, user-friendly control center:
 * - 4 Key S3 metrics
 * - Clean 3-step pipeline flow: S3 Ingestion -> AI Enrichment -> Multimodal Search
 * - S3 Modality distribution
 * - Recent S3 discovery items
 */

import { mockData } from '../mock-data.js';
import { renderIcon } from '../icons.js';

export function renderOverviewView(container, { onNavigate, onOpenDocument }) {
  const { platformOverview } = mockData;

  container.innerHTML = `
    <div class="overview-grid">
      <!-- Header -->
      <div class="page-header">
        <div class="page-title-group">
          <span class="page-eyebrow">S3 Data Platform</span>
          <h1 class="page-title">Overview</h1>
          <p class="page-description">
            Continuous ingestion, AI enrichment, and multimodal discovery across connected Amazon S3 buckets.
          </p>
        </div>
        <div class="page-actions">
          <button class="btn btn-primary" id="overview-btn-search">
            ${renderIcon('search')} Open Search
          </button>
        </div>
      </div>

      <!-- 4 Clean Summary Cards -->
      <div class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-header">
            <span class="kpi-label">Total S3 Objects</span>
            <span class="badge badge-success"><span class="badge-dot"></span> Active</span>
          </div>
          <div class="kpi-value">${platformOverview.totalIndexedFiles.toLocaleString()}</div>
          <div class="kpi-footer">
            <span>Across 4 production S3 buckets</span>
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-header">
            <span class="kpi-label">S3 Storage Volume</span>
            ${renderIcon('s3')}
          </div>
          <div class="kpi-value">${platformOverview.totalStorageFormatted}</div>
          <div class="kpi-footer">
            <span>ap-northeast-2 (Seoul)</span>
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-header">
            <span class="kpi-label">AI Enrichment</span>
            <span class="badge badge-success">${platformOverview.enrichmentRate}%</span>
          </div>
          <div class="kpi-value">14.6M Enriched</div>
          <div class="kpi-footer">
            <span>Vision, OCR, Audio, Vectors</span>
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-header">
            <span class="kpi-label">Search Latency</span>
            ${renderIcon('cpu')}
          </div>
          <div class="kpi-value">${platformOverview.searchLatencyAvgMs} ms</div>
          <div class="kpi-footer">
            <span>1536-d Vector Index</span>
          </div>
        </div>
      </div>

      <!-- Simplified Pipeline Architecture Visualizer -->
      <div class="pipeline-panel">
        <div class="pipeline-header">
          <div class="pipeline-title-group">
            <div class="pipeline-title">Platform Processing Pipeline</div>
            <div class="pipeline-subtitle">Continuous automated pipeline from Amazon S3 to searchable AI knowledge</div>
          </div>
          <button class="btn btn-sm btn-ghost" id="overview-view-ingest">
            View Ingestion ${renderIcon('chevronRight')}
          </button>
        </div>

        <div class="pipeline-flow" style="grid-template-columns: repeat(3, 1fr);">
          <div class="pipeline-stage">
            <div class="pipeline-stage-header">
              <span class="stage-step-num">STEP 01</span>
              <span class="badge badge-success"><span class="badge-dot"></span> S3 Stream</span>
            </div>
            <div class="stage-name">S3 Ingestion & Validation</div>
            <div class="stage-metric">
              <span class="stage-metric-val">18.4 GB/s</span>
              <span class="stage-metric-label">MIME, SHA-256 & UUID v7 Stamping</span>
            </div>
            <div class="stage-footer">
              <span>Connected</span>
              <span class="mono-text">4 S3 Buckets</span>
            </div>
          </div>

          <div class="pipeline-stage">
            <div class="pipeline-stage-header">
              <span class="stage-step-num">STEP 02</span>
              <span class="badge badge-info"><span class="badge-dot"></span> Active</span>
            </div>
            <div class="stage-name">AI Enrichment & Fusion</div>
            <div class="stage-metric">
              <span class="stage-metric-val">420 docs/s</span>
              <span class="stage-metric-label">Vision-LLM, Whisper & OCR Models</span>
            </div>
            <div class="stage-footer">
              <span>Confidence</span>
              <span class="mono-text">96.8% Average</span>
            </div>
          </div>

          <div class="pipeline-stage">
            <div class="pipeline-stage-header">
              <span class="stage-step-num">STEP 03</span>
              <span class="badge badge-success"><span class="badge-dot"></span> Indexed</span>
            </div>
            <div class="stage-name">Multimodal Search Index</div>
            <div class="stage-metric">
              <span class="stage-metric-val">14.8M Vectors</span>
              <span class="stage-metric-label">Hybrid Lexical + Vector Retrieval</span>
            </div>
            <div class="stage-footer">
              <span>P95 Speed</span>
              <span class="mono-text">38 ms</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Two Column Layout: Modality Distribution & Recent S3 Items -->
      <div class="overview-columns">
        <!-- Modality Breakdown -->
        <div class="panel">
          <div class="panel-header">
            <div>
              <div class="panel-title">S3 Objects by Type</div>
              <div class="panel-subtitle">Indexed media and documents across all S3 buckets</div>
            </div>
            <button class="btn btn-sm btn-ghost" id="overview-filter-search">
              Browse All ${renderIcon('chevronRight')}
            </button>
          </div>

          <div class="modality-list">
            ${platformOverview.modalityDistribution.map(item => `
              <div class="modality-row">
                <div class="modality-row-header">
                  <span class="modality-row-name">
                    <span class="badge badge-modality ${item.type}">${item.type}</span>
                    ${item.label}
                  </span>
                  <span class="modality-row-stats">${item.count.toLocaleString()} files (${item.bytes})</span>
                </div>
                <div class="modality-bar-bg">
                  <div class="modality-bar-fill" style="width: ${item.percentage}%; background-color: var(--modality-${item.type});"></div>
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Recent S3 Discoveries -->
        <div class="panel">
          <div class="panel-header">
            <div>
              <div class="panel-title">Recent S3 Objects</div>
              <div class="panel-subtitle">Latest enriched assets ready for discovery</div>
            </div>
          </div>

          <div class="activity-stream">
            ${mockData.documents.slice(0, 3).map(doc => `
              <div class="activity-item" style="cursor: pointer;" data-open-doc="${doc.id}">
                <div class="activity-icon-wrap">
                  ${renderIcon(doc.modality === 'image' ? 'image' : doc.modality === 'video' ? 'video' : doc.modality === 'audio' ? 'audio' : 'document')}
                </div>
                <div class="activity-body">
                  <div class="activity-action" style="color: var(--text-primary);">${doc.filename}</div>
                  <div class="activity-desc">${doc.canonicalCaption}</div>
                  <div class="activity-meta">
                    <span class="badge badge-modality ${doc.modality}">${doc.modality}</span> ·
                    <span class="mono-text">${doc.fileSize}</span> ·
                    <span class="mono-text" style="color: var(--brand-primary-text);">s3://${doc.sourceUri.split('//')[1].split('/')[0]}</span>
                  </div>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    </div>
  `;

  // Bind Interactions
  container.querySelector('#overview-btn-search').addEventListener('click', () => onNavigate('search'));
  container.querySelector('#overview-view-ingest').addEventListener('click', () => onNavigate('ingestion'));
  container.querySelector('#overview-filter-search').addEventListener('click', () => onNavigate('search'));

  container.querySelectorAll('[data-open-doc]').forEach(el => {
    el.addEventListener('click', () => onOpenDocument(el.dataset.openDoc));
  });
}

/**
 * Samsung Prism Enterprise Platform - AI Enrichment Workspace
 * 
 * Interactive multimodal enrichment console:
 * - 4-stage neural pipeline telemetry
 * - GPU cluster model cards (Vision-LLM 9.4B, Whisper-Large-v3, OCR v4, ViT-H/14)
 * - Interactive S3 Object AI Inspector & Live Re-enrichment Simulator
 * - 1536-d Vector Embedding inspector & JSON schema viewer
 * - Confidence calibration distribution
 */

import { api } from '../api.js';
import { mockData } from '../mock-data.js';
import { renderIcon } from '../icons.js';

export function renderEnrichmentView(container, { onShowToast }) {
  const { aiEnrichment, documents } = mockData;
  let selectedDocId = documents[0].id;

  function getSelectedDoc() {
    return api.getDocument(selectedDocId) || documents[0];
  }

  function renderInspector() {
    const doc = getSelectedDoc();
    const inspectorMount = container.querySelector('#ai-inspector-mount');
    if (!inspectorMount) return;

    inspectorMount.innerHTML = `
      <div class="ai-inspector-grid">
        <!-- Left: S3 Binary Source & Media Preview -->
        <div class="ai-preview-box">
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <span class="ai-section-title">S3 Input Object</span>
            <span class="badge badge-modality ${doc.modality}">${doc.modality}</span>
          </div>

          <div style="font-size: 13px; font-weight: 700; color: var(--text-primary); word-break: break-all;">
            ${doc.filename}
          </div>

          <div class="mono-text" style="font-size: 11px; color: var(--text-muted); background: var(--bg-surface); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
            ${doc.sourceUri}
          </div>

          <!-- Media Visual Sample -->
          <div style="background: #000; height: 180px; border-radius: var(--radius-sm); position: relative; display: flex; align-items: center; justify-content: center; overflow: hidden;">
            <div style="color: #64748b; text-align: center;">
              ${renderIcon(doc.modality)}
              <div style="font-size: 10px; margin-top: 4px;">${doc.modality.toUpperCase()} RAW STREAM</div>
            </div>
            ${doc.modality === 'image' && doc.detectedObjects.length > 0 ? `
              <div style="position: absolute; top: 20%; left: 55%; width: 32%; height: 38%; border: 2px solid #ef4444; background: rgba(239,68,68,0.18); border-radius: 2px;">
                <span style="position: absolute; top: -16px; left: 0; background: #ef4444; color: #fff; font-size: 9px; padding: 1px 4px; font-weight: 700;">
                  Defect (96.8%)
                </span>
              </div>
            ` : ''}
          </div>

          <!-- Technical Specs List -->
          <div class="drawer-spec-list" style="padding: 10px; font-size: 11px; grid-template-columns: 110px 1fr;">
            <span class="spec-key">Document ID:</span>
            <span class="spec-val mono-text" style="color: var(--brand-primary-text); font-size: 10px;">${doc.id.slice(0, 24)}...</span>
            <span class="spec-key">File Size:</span>
            <span class="spec-val mono-text">${doc.fileSize}</span>
            <span class="spec-key">SHA-256 Checksum:</span>
            <span class="spec-val mono-text" style="font-size: 9px;">${doc.checksum.slice(0, 20)}...</span>
          </div>

          <button class="btn btn-primary btn-sm" id="btn-re-enrich-doc" style="margin-top: 4px;">
            ${renderIcon('refresh')} Simulate Re-Enrichment
          </button>
        </div>

        <!-- Right: AI Fusion & 1536-d Vectors -->
        <div class="ai-results-box">
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <span class="ai-section-title">Multimodal Extracted Intelligence</span>
            <span class="badge badge-success">${Math.round(doc.confidence * 100)}% Model Confidence</span>
          </div>

          <!-- Caption -->
          <div>
            <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); margin-bottom: 4px;">AI Synthesized Caption:</div>
            <div style="font-size: 13px; color: var(--text-primary); line-height: 1.4; background: var(--bg-surface); padding: 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
              ${doc.canonicalCaption}
            </div>
          </div>

          <!-- Tags -->
          <div>
            <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); margin-bottom: 4px;">Semantic Tags & Labels:</div>
            <div style="display: flex; flex-wrap: wrap; gap: 5px;">
              ${doc.tags.map(t => `<span class="result-tag-pill" style="font-size: 11px; padding: 3px 8px; color: var(--brand-primary-text);">${t}</span>`).join('')}
            </div>
          </div>

          <!-- Extracted OCR or Audio -->
          ${doc.ocrText ? `
            <div>
              <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); margin-bottom: 4px;">OCR Extracted Text:</div>
              <div class="mono-text" style="font-size: 11px; color: var(--text-secondary); background: var(--bg-surface); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
                ${doc.ocrText}
              </div>
            </div>
          ` : ''}

          ${doc.transcript ? `
            <div>
              <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); margin-bottom: 4px;">Whisper Audio Transcript:</div>
              <div class="mono-text" style="font-size: 11px; color: var(--text-secondary); background: var(--bg-surface); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
                ${doc.transcript}
              </div>
            </div>
          ` : ''}

          <!-- 1536-d Vector Embedding Representation -->
          <div>
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
              <span style="font-size: 11px; font-weight: 600; color: var(--text-muted);">1536-d Joint Multimodal Vector:</span>
              <span class="mono-text" style="font-size: 10px; color: var(--brand-primary-text);">ViT-H/14 · L2 Normalized</span>
            </div>
            <div class="ai-vector-preview-bar">
              ${Array.from({ length: 48 }).map((_, i) => `
                <div class="ai-vector-slice" style="opacity: ${0.2 + (Math.abs(Math.sin(i * 0.5)) * 0.8)};"></div>
              `).join('')}
            </div>
            <div class="mono-text" style="font-size: 10px; color: var(--text-muted); margin-top: 4px;">
              [-0.0482, 0.1291, 0.0814, -0.0029, 0.2319, -0.1102, 0.0451, ...]
            </div>
          </div>

          <!-- JSON Schema Preview -->
          <div>
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
              <span style="font-size: 11px; font-weight: 600; color: var(--text-muted);">Enriched JSON Payload:</span>
              <button class="btn btn-ghost btn-sm" id="btn-copy-enriched-json" style="padding: 2px 6px; font-size: 10px;">
                ${renderIcon('copy')} Copy JSON
              </button>
            </div>
            <pre class="mono-text" style="background: var(--bg-surface); padding: 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); color: #93c5fd; font-size: 10px; margin: 0; max-height: 120px; overflow-y: auto;">${JSON.stringify({
              document_id: doc.id,
              s3_uri: doc.sourceUri,
              modality: doc.modality,
              caption: doc.canonicalCaption,
              tags: doc.tags,
              confidence: doc.confidence,
              vector_dim: 1536
            }, null, 2)}</pre>
          </div>
        </div>
      </div>
    `;

    // Bind Inspector Buttons
    const reEnrichBtn = inspectorMount.querySelector('#btn-re-enrich-doc');
    if (reEnrichBtn) {
      reEnrichBtn.addEventListener('click', async () => {
        reEnrichBtn.innerHTML = `${renderIcon('refresh')} Running Vision-LLM 9.4B...`;
        reEnrichBtn.disabled = true;
        await new Promise(r => setTimeout(r, 600));
        reEnrichBtn.innerHTML = `${renderIcon('check')} Re-Enriched (100% Synced)`;
        onShowToast(`Re-enriched S3 object '${doc.filename}' with latest ViT-H/14 model weights`, 'success');
        setTimeout(() => {
          reEnrichBtn.innerHTML = `${renderIcon('refresh')} Simulate Re-Enrichment`;
          reEnrichBtn.disabled = false;
        }, 2000);
      });
    }

    const copyJsonBtn = inspectorMount.querySelector('#btn-copy-enriched-json');
    if (copyJsonBtn) {
      copyJsonBtn.addEventListener('click', () => {
        const payload = JSON.stringify(doc, null, 2);
        if (navigator.clipboard) navigator.clipboard.writeText(payload);
        onShowToast('Copied enriched metadata JSON to clipboard', 'success');
      });
    }
  }

  container.innerHTML = `
    <div class="enrichment-layout">
      <!-- Header -->
      <div class="page-header">
        <div class="page-title-group">
          <span class="page-eyebrow">Neural Processing Fabric</span>
          <h1 class="page-title">AI Enrichment</h1>
          <p class="page-description">
            Automated neural tagging, OCR layout analysis, audio transcription, and 1536-d vector embeddings for S3 objects.
          </p>
        </div>
        <div class="page-actions">
          <button class="btn btn-primary" id="btn-run-benchmark">
            ${renderIcon('cpu')} Run Model Benchmark
          </button>
        </div>
      </div>

      <!-- 4-Stage Pipeline Flow -->
      <div class="pipeline-flow-panel">
        <div class="ingest-panel-header">
          <div>
            <div class="ingest-panel-title">AI Processing Pipeline</div>
            <div class="panel-subtitle">End-to-end automated multimodal enrichment workflow</div>
          </div>
          <span class="badge badge-success"><span class="badge-dot"></span> Pipeline Healthy</span>
        </div>

        <div class="neural-stage-track">
          ${aiEnrichment.stages.map((stg, i) => `
            <div class="neural-stage-step ${stg.status}">
              <div class="neural-step-badge">STEP 0${i + 1}</div>
              <div class="neural-step-name">${stg.name}</div>
              <div class="neural-step-meta">
                <span class="mono-text">${stg.count.toLocaleString()} S3 Objects</span>
                <span class="badge ${stg.status === 'completed' ? 'badge-success' : 'badge-info'}">
                  ${stg.status}
                </span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- Active AI Models Grid -->
      <div>
        <div class="ingest-panel-header" style="margin-bottom: 12px;">
          <div>
            <div class="ingest-panel-title">Active Multimodal Models</div>
            <div class="panel-subtitle">Dedicated neural cluster engines processing S3 object streams</div>
          </div>
        </div>

        <div class="model-cards-grid">
          ${aiEnrichment.activePipelines.map(pipe => `
            <div class="model-card">
              <div class="model-card-header">
                <div>
                  <div class="model-name">${pipe.name}</div>
                  <div class="model-meta">Engine: GPU Cluster 04 · Latency: ${pipe.latencyAvg}</div>
                </div>
                <span class="badge badge-success"><span class="badge-dot"></span> ${pipe.status}</span>
              </div>
              <div class="model-stats-row">
                <div class="model-stat">
                  <span class="model-stat-label">Throughput</span>
                  <span class="model-stat-val mono-text">${pipe.throughput}</span>
                </div>
                <div class="model-stat">
                  <span class="model-stat-label">Queue Backlog</span>
                  <span class="model-stat-val mono-text">${pipe.queueSize.toLocaleString()}</span>
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- Interactive S3 Object AI Enrichment Inspector -->
      <div class="ai-inspector-panel">
        <div class="ingest-panel-header" style="flex-wrap: wrap; gap: 12px;">
          <div>
            <div class="ingest-panel-title">Interactive S3 Object AI Inspector</div>
            <div class="panel-subtitle">Select an S3 object to inspect its extracted neural metadata and vector representation</div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <label class="sort-label" for="select-inspect-doc">Inspect S3 Object:</label>
            <select class="sort-select" id="select-inspect-doc" style="min-width: 240px;">
              ${documents.map(d => `
                <option value="${d.id}" ${d.id === selectedDocId ? 'selected' : ''}>
                  ${d.filename} (${d.modality})
                </option>
              `).join('')}
            </select>
          </div>
        </div>

        <div id="ai-inspector-mount"></div>
      </div>

      <!-- Confidence Distribution -->
      <div class="panel" style="padding: 20px;">
        <div class="panel-header" style="margin-bottom: 14px;">
          <div>
            <div class="panel-title">Model Confidence Calibration</div>
            <div class="panel-subtitle">Confidence score distribution across 14.6M processed S3 documents</div>
          </div>
          <span class="badge badge-success">98.4% Quality Pass Rate</span>
        </div>

        <div style="display: flex; flex-direction: column; gap: 10px;">
          ${aiEnrichment.confidenceDistribution.map(bracket => `
            <div style="display: flex; flex-direction: column; gap: 4px;">
              <div style="display: flex; justify-content: space-between; font-size: 11px;">
                <span style="font-weight: 600; color: var(--text-primary);">${bracket.range}</span>
                <span class="mono-text" style="color: var(--text-muted);">${bracket.count} (${bracket.percentage}%)</span>
              </div>
              <div class="progress-track" style="height: 6px;">
                <div class="progress-fill" style="width: ${bracket.percentage}%;"></div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;

  // Initial render of inspector
  renderInspector();

  // Document select listener
  container.querySelector('#select-inspect-doc').addEventListener('change', (e) => {
    selectedDocId = e.target.value;
    renderInspector();
  });

  // Benchmark button
  container.querySelector('#btn-run-benchmark').addEventListener('click', async () => {
    onShowToast('Dispatched model benchmark across 1,000 S3 validation objects', 'info');
    await new Promise(r => setTimeout(r, 1200));
    onShowToast('Benchmark Completed: Vision-LLM 9.4B (142ms P95), Whisper (480ms P95), ViT-H/14 (24ms P95)', 'success');
  });
}

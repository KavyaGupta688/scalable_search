/**
 * Samsung Prism Enterprise Platform - Document Detail Inspector (Simplified)
 * 
 * Clean, user-friendly modal drawer for inspecting S3 multimodal objects:
 * - High-res preview with bounding box toggle
 * - S3 Storage URI and SHA-256
 * - AI tags, captions, and confidence scores
 */

import { api } from '../api.js';
import { renderIcon } from '../icons.js';

export function openDocumentDetailModal(docId, { onShowToast }) {
  const doc = api.getDocument(docId);
  if (!doc) return;

  const modalRoot = document.querySelector('#modal-root');
  let isSaved = api.isDocumentSaved(doc.id);
  let showBoundingBoxes = true;

  function renderMediaViewer() {
    if (doc.modality === 'image') {
      return `
        <div class="detail-media-container" style="background: #000; border-radius: var(--radius-sm); position: relative; overflow: hidden; height: 260px; display: flex; align-items: center; justify-content: center;">
          <div style="color: #64748b; text-align: center;">
            ${renderIcon('image')}
            <div style="font-size: 11px; margin-top: 6px;">Optical Micrograph Sample</div>
          </div>
          ${showBoundingBoxes && doc.detectedObjects.length > 0 ? `
            <div style="position: absolute; top: 18%; left: 60%; width: 28%; height: 32%; border: 2px solid #ef4444; background: rgba(239, 68, 68, 0.15); border-radius: 2px;">
              <span style="position: absolute; top: -18px; left: 0; background: #ef4444; color: #fff; font-size: 9px; padding: 1px 4px; font-weight: 700;">
                Glass Fissure (96.8%)
              </span>
            </div>
          ` : ''}
        </div>
      `;
    }

    if (doc.modality === 'video') {
      return `
        <div class="detail-media-container" style="background: #000; border-radius: var(--radius-sm); height: 220px; display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative;">
          <div style="width: 44px; height: 44px; border-radius: 50%; background: rgba(255,255,255,0.15); display: grid; place-items: center; cursor: pointer; color: #fff;">
            ${renderIcon('play')}
          </div>
          <span style="font-size: 11px; color: #94a3b8; margin-top: 8px;">Line 02 Robotic Feed (1080p 60fps)</span>
        </div>
      `;
    }

    if (doc.modality === 'audio') {
      return `
        <div class="detail-media-container" style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 18px;">
          <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--brand-primary); color: #fff; display: grid; place-items: center;">
              ${renderIcon('play')}
            </div>
            <div>
              <div style="font-size: 12px; font-weight: 600; color: var(--text-primary);">Acoustic Vibration Track</div>
              <div class="mono-text" style="font-size: 10px; color: var(--text-muted);">48 kHz · 24-bit PCM WAV</div>
            </div>
          </div>
          <div style="height: 38px; display: flex; align-items: center; gap: 3px;">
            ${Array.from({ length: 42 }).map((_, i) => `
              <div style="flex: 1; height: ${Math.sin(i * 0.4) * 14 + 16}px; background: var(--brand-primary); opacity: ${i < 18 ? '0.9' : '0.3'}; border-radius: 1px;"></div>
            `).join('')}
          </div>
        </div>
      `;
    }

    return `
      <div class="detail-media-container" style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 16px;">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
          ${renderIcon('document')}
          <span style="font-size: 12px; font-weight: 600; color: var(--text-primary);">${doc.filename}</span>
        </div>
        <div class="mono-text" style="font-size: 11px; color: var(--text-secondary); line-height: 1.4; background: var(--bg-surface); padding: 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
          ${doc.ocrText || 'Extracted document content indexed in multimodal database.'}
        </div>
      </div>
    `;
  }

  modalRoot.innerHTML = `
    <div class="drawer-backdrop" id="detail-drawer-backdrop">
      <div class="drawer-panel" style="max-width: 640px;">
        <!-- Header -->
        <div class="drawer-header">
          <div>
            <span class="badge badge-modality ${doc.modality}">${doc.modality}</span>
            <div class="drawer-title" style="margin-top: 4px;" title="${doc.filename}">${doc.filename}</div>
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            <button class="btn btn-ghost btn-sm" id="btn-save-doc" title="Save S3 Object">
              ${renderIcon('bookmark')} ${isSaved ? 'Saved' : 'Save'}
            </button>
            <button class="btn btn-ghost btn-sm" id="btn-close-detail-drawer" aria-label="Close">
              ${renderIcon('close')}
            </button>
          </div>
        </div>

        <!-- Body -->
        <div class="drawer-body" style="display: flex; flex-direction: column; gap: 18px;">
          <!-- Media Preview -->
          <div id="media-viewer-mount">
            ${renderMediaViewer()}
          </div>

          <!-- AI Description -->
          <div>
            <div class="drawer-section-title">AI Summary & Findings</div>
            <div style="font-size: 13px; line-height: 1.5; color: var(--text-primary); background: var(--bg-surface-elevated); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
              ${doc.aiDescription}
            </div>
          </div>

          <!-- AI Tags -->
          <div>
            <div class="drawer-section-title">AI Tags</div>
            <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;">
              ${doc.tags.map(t => `<span class="result-tag-pill">${t}</span>`).join('')}
            </div>
          </div>

          <!-- Technical Specs -->
          <div>
            <div class="drawer-section-title">S3 Technical Details</div>
            <div class="drawer-spec-list">
              <span class="spec-key">Document ID (UUID v7):</span>
              <span class="spec-val mono-text" style="color: var(--brand-primary-text);">${doc.id}</span>
              <span class="spec-key">S3 Location:</span>
              <span class="spec-val mono-text">${doc.sourceUri}</span>
              <span class="spec-key">S3 Bucket:</span>
              <span class="spec-val">${doc.source}</span>
              <span class="spec-key">SHA-256 Checksum:</span>
              <span class="spec-val mono-text" style="font-size: 10px;">${doc.checksum}</span>
              <span class="spec-key">File Size:</span>
              <span class="spec-val mono-text">${doc.fileSize}</span>
              <span class="spec-key">AI Confidence:</span>
              <span class="spec-val">
                <span class="badge badge-success">${Math.round(doc.confidence * 100)}%</span>
              </span>
              <span class="spec-key">Governance:</span>
              <span class="spec-val">${doc.governance}</span>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="detail-drawer-footer">
          <button class="btn btn-ghost btn-sm" id="btn-copy-s3-uri">
            ${renderIcon('copy')} Copy S3 URI
          </button>
          <button class="btn btn-primary btn-sm" id="btn-download-s3">
            ${renderIcon('download')} Download S3 Object
          </button>
        </div>
      </div>
    </div>
  `;

  const backdrop = modalRoot.querySelector('#detail-drawer-backdrop');
  backdrop.addEventListener('click', (e) => {
    if (e.target === backdrop) modalRoot.innerHTML = '';
  });

  modalRoot.querySelector('#btn-close-detail-drawer').addEventListener('click', () => {
    modalRoot.innerHTML = '';
  });

  modalRoot.querySelector('#btn-save-doc').addEventListener('click', () => {
    isSaved = api.toggleSaveDocument(doc.id);
    modalRoot.querySelector('#btn-save-doc').innerHTML = `${renderIcon('bookmark')} ${isSaved ? 'Saved' : 'Save'}`;
    onShowToast(isSaved ? 'Saved S3 object to bookmarks' : 'Removed from bookmarks', 'info');
  });

  modalRoot.querySelector('#btn-copy-s3-uri').addEventListener('click', () => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(doc.sourceUri);
    }
    onShowToast(`Copied S3 URI: ${doc.sourceUri}`, 'success');
  });

  modalRoot.querySelector('#btn-download-s3').addEventListener('click', () => {
    onShowToast(`Dispatched secure S3 presigned URL for ${doc.filename}`, 'success');
  });
}

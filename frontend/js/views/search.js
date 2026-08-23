/**
 * Samsung Prism Enterprise Platform - Multimodal Search Workspace (Simplified)
 * 
 * Clean, user-friendly search experience for S3 objects:
 * - Simple search bar with natural language, keyword, and similar file modes
 * - Interactive Example Query Chips
 * - Simple S3 bucket & modality filters
 * - Clean card results with detail drawer trigger
 */

import { api } from '../api.js';
import { renderIcon } from '../icons.js';

export function renderSearchView(container, { onOpenDocument, onShowToast }) {
  let currentMode = 'natural';
  let currentViewMode = 'grid'; // 'grid' | 'table'
  let activeModalities = [];
  let activeSources = [];
  let activeTags = [];
  let minConfidence = 0;
  let currentSort = 'relevance';
  let referenceDocId = null;

  const exampleQueries = [
    "Cracked OLED display panels",
    "Robotic assembly line videos",
    "Display panel quality failures",
    "Motor vibration acoustic anomalies",
    "OLED defect records CSV"
  ];

  container.innerHTML = `
    <div class="search-workspace">
      <!-- Search Top Bar -->
      <div class="search-header-area">
        <div class="search-bar-wrapper">
          <div class="search-input-box">
            <span class="search-prefix-icon">${renderIcon('search')}</span>
            <input 
              class="search-main-input" 
              id="search-main-input" 
              type="text" 
              placeholder="Search S3 objects with natural language, tags, or filenames..." 
              autocomplete="off"
            />
            <button class="btn btn-ghost btn-sm btn-clear-search hidden" id="btn-clear-search" aria-label="Clear Search">
              ${renderIcon('close')}
            </button>
            <button class="btn btn-primary btn-sm" id="btn-execute-search">
              Search
            </button>
          </div>
        </div>

        <!-- Mode Tabs -->
        <div class="search-mode-tabs">
          <div class="mode-tab-group">
            <button class="mode-tab active" data-mode="natural">
              Natural Language
            </button>
            <button class="mode-tab" data-mode="keyword">
              Exact Keyword
            </button>
            <button class="mode-tab" data-mode="similar">
              Similar S3 Object
            </button>
          </div>

          <div class="view-toggle-group">
            <button class="view-toggle-btn active" id="btn-view-grid" title="Grid View">
              ${renderIcon('grid')}
            </button>
            <button class="view-toggle-btn" id="btn-view-table" title="Table View">
              ${renderIcon('list')}
            </button>
          </div>
        </div>

        <!-- Interactive Query Chips -->
        <div class="query-chips-row">
          <span class="chips-label">Try:</span>
          ${exampleQueries.map(q => `
            <button class="query-chip" data-query="${q}">
              ${q}
            </button>
          `).join('')}
        </div>
      </div>

      <!-- Main Layout: Filters Sidebar + Results Area -->
      <div class="search-body-layout">
        <!-- Simplified Filters Sidebar -->
        <aside class="search-filters-sidebar">
          <div class="filters-header">
            <span class="filters-title">${renderIcon('filter')} Filters</span>
            <button class="btn-reset-filters" id="btn-reset-filters">Reset</button>
          </div>

          <!-- Modality Filter -->
          <div class="filter-section">
            <div class="filter-section-title">Modality</div>
            <div class="filter-options-list">
              ${[
                { id: 'image', label: 'Images' },
                { id: 'video', label: 'Videos' },
                { id: 'document', label: 'Documents' },
                { id: 'audio', label: 'Audio' },
                { id: 'tabular', label: 'Tabular' }
              ].map(m => `
                <label class="filter-checkbox-label">
                  <input type="checkbox" class="filter-modality" value="${m.id}" />
                  <span>${m.label}</span>
                </label>
              `).join('')}
            </div>
          </div>

          <!-- S3 Buckets Filter -->
          <div class="filter-section">
            <div class="filter-section-title">S3 Bucket</div>
            <div class="filter-options-list">
              ${api.getDataSources().map(src => `
                <label class="filter-checkbox-label">
                  <input type="checkbox" class="filter-source" value="${src.name}" />
                  <span>${src.name}</span>
                </label>
              `).join('')}
            </div>
          </div>

          <!-- AI Confidence Slider -->
          <div class="filter-section">
            <div class="filter-section-title">Min AI Confidence (<span id="confidence-val">0%</span>)</div>
            <input type="range" class="confidence-slider" id="filter-confidence" min="0" max="95" step="5" value="0" />
          </div>
        </aside>

        <!-- Results Area -->
        <main class="search-results-area">
          <!-- Results Header Info -->
          <div class="results-stats-row">
            <div class="results-count-text" id="results-count-text">
              Loading S3 objects...
            </div>
            <div class="results-sort-group">
              <label class="sort-label">Sort by:</label>
              <select class="sort-select" id="select-sort">
                <option value="relevance">AI Relevance</option>
                <option value="date-desc">Newest First</option>
                <option value="size-desc">File Size</option>
              </select>
            </div>
          </div>

          <!-- Results Container -->
          <div class="results-grid" id="results-container"></div>
        </main>
      </div>
    </div>
  `;

  // Search execution
  async function performSearch() {
    const query = container.querySelector('#search-main-input').value;
    const results = await api.search({
      query,
      mode: currentMode,
      modalities: activeModalities,
      sources: activeSources,
      tags: activeTags,
      minConfidence,
      referenceDocId,
      sortBy: currentSort
    });

    renderResults(results);
  }

  function renderResults({ results, total, query }) {
    const countEl = container.querySelector('#results-count-text');
    const containerEl = container.querySelector('#results-container');

    countEl.innerHTML = query 
      ? `Found <strong>${total}</strong> S3 objects matching "<em>${query}</em>"`
      : `Showing <strong>${total}</strong> indexed S3 objects`;

    if (results.length === 0) {
      containerEl.innerHTML = `
        <div class="search-empty-state" style="grid-column: 1 / -1;">
          <div class="empty-state-icon">${renderIcon('search')}</div>
          <div class="empty-state-title">No matching S3 objects found</div>
          <div class="empty-state-copy">Try broadening your search query or removing filter constraints.</div>
        </div>
      `;
      return;
    }

    if (currentViewMode === 'table') {
      containerEl.className = 'results-table-container';
      containerEl.innerHTML = `
        <table class="data-table">
          <thead>
            <tr>
              <th>Filename & Preview</th>
              <th>Modality</th>
              <th>S3 Source Bucket</th>
              <th>AI Description</th>
              <th>Score</th>
              <th>Size</th>
            </tr>
          </thead>
          <tbody>
            ${results.map(doc => `
              <tr data-doc-id="${doc.id}" style="cursor: pointer;">
                <td>
                  <strong style="color: var(--text-primary);">${doc.filename}</strong>
                  <div class="mono-text" style="font-size: 10px; color: var(--text-muted);">${doc.id.slice(0, 18)}...</div>
                </td>
                <td><span class="badge badge-modality ${doc.modality}">${doc.modality}</span></td>
                <td><span class="mono-text" style="font-size: 11px;">${doc.sourceUri.split('//')[1].split('/')[0]}</span></td>
                <td style="max-width: 320px; font-size: 12px; color: var(--text-secondary);">${doc.canonicalCaption}</td>
                <td><span class="badge badge-success">${Math.round((doc.searchScore || doc.relevanceScore) * 100)}%</span></td>
                <td class="mono-text">${doc.fileSize}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;

      containerEl.querySelectorAll('tbody tr').forEach(tr => {
        tr.addEventListener('click', () => onOpenDocument(tr.dataset.docId));
      });
      return;
    }

    // Grid View
    containerEl.className = 'results-grid';
    containerEl.innerHTML = results.map(doc => `
      <div class="result-card" data-doc-id="${doc.id}">
        <div class="result-preview-thumb ${doc.modality}">
          ${renderIcon(doc.modality)}
          <span class="badge badge-modality ${doc.modality}" style="position: absolute; top: 8px; left: 8px;">${doc.modality}</span>
          <span class="badge badge-success" style="position: absolute; top: 8px; right: 8px;">
            ${Math.round((doc.searchScore || doc.relevanceScore) * 100)}% match
          </span>
        </div>

        <div class="result-card-body">
          <div class="result-title" title="${doc.filename}">${doc.filename}</div>
          <div class="result-summary">${doc.canonicalCaption}</div>

          <div class="result-tags-row">
            ${doc.tags.slice(0, 3).map(t => `<span class="result-tag-pill">${t}</span>`).join('')}
          </div>

          <div class="result-footer-meta">
            <span class="mono-text" title="${doc.sourceUri}">s3://${doc.sourceUri.split('//')[1].split('/')[0]}</span>
            <span class="mono-text">${doc.fileSize}</span>
          </div>
        </div>
      </div>
    `).join('');

    containerEl.querySelectorAll('.result-card').forEach(card => {
      card.addEventListener('click', () => onOpenDocument(card.dataset.docId));
    });
  }

  // Bind Mode Switching
  container.querySelectorAll('.mode-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      container.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentMode = tab.dataset.mode;
      const input = container.querySelector('#search-main-input');
      if (currentMode === 'similar') {
        input.placeholder = "Enter Document ID or filename for reference file similarity...";
      } else if (currentMode === 'keyword') {
        input.placeholder = "Enter exact keywords, OCR text tokens, or tags...";
      } else {
        input.placeholder = "Search S3 objects with natural language, tags, or filenames...";
      }
      performSearch();
    });
  });

  // Bind View Mode Toggle
  container.querySelector('#btn-view-grid').addEventListener('click', () => {
    currentViewMode = 'grid';
    container.querySelector('#btn-view-grid').classList.add('active');
    container.querySelector('#btn-view-table').classList.remove('active');
    performSearch();
  });

  container.querySelector('#btn-view-table').addEventListener('click', () => {
    currentViewMode = 'table';
    container.querySelector('#btn-view-table').classList.add('active');
    container.querySelector('#btn-view-grid').classList.remove('active');
    performSearch();
  });

  // Bind Search Input & Buttons
  const searchInput = container.querySelector('#search-main-input');
  const clearBtn = container.querySelector('#btn-clear-search');

  searchInput.addEventListener('input', () => {
    if (searchInput.value.length > 0) {
      clearBtn.classList.remove('hidden');
    } else {
      clearBtn.classList.add('hidden');
    }
  });

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') performSearch();
  });

  container.querySelector('#btn-execute-search').addEventListener('click', performSearch);

  clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    clearBtn.classList.add('hidden');
    performSearch();
  });

  // Query Chips
  container.querySelectorAll('.query-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      searchInput.value = chip.dataset.query;
      clearBtn.classList.remove('hidden');
      performSearch();
    });
  });

  // Filter Handlers
  container.querySelectorAll('.filter-modality').forEach(cb => {
    cb.addEventListener('change', () => {
      activeModalities = Array.from(container.querySelectorAll('.filter-modality:checked')).map(c => c.value);
      performSearch();
    });
  });

  container.querySelectorAll('.filter-source').forEach(cb => {
    cb.addEventListener('change', () => {
      activeSources = Array.from(container.querySelectorAll('.filter-source:checked')).map(c => c.value);
      performSearch();
    });
  });

  const confSlider = container.querySelector('#filter-confidence');
  const confVal = container.querySelector('#confidence-val');
  confSlider.addEventListener('input', (e) => {
    minConfidence = Number(e.target.value);
    confVal.textContent = `${minConfidence}%`;
    performSearch();
  });

  container.querySelector('#select-sort').addEventListener('change', (e) => {
    currentSort = e.target.value;
    performSearch();
  });

  container.querySelector('#btn-reset-filters').addEventListener('click', () => {
    container.querySelectorAll('.filter-modality, .filter-source').forEach(cb => cb.checked = false);
    activeModalities = [];
    activeSources = [];
    minConfidence = 0;
    confSlider.value = 0;
    confVal.textContent = '0%';
    performSearch();
  });

  // Initial Search Run
  performSearch();
}

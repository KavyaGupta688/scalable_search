// Multimodal Discovery & Hybrid Search Frontend Logic
// Automatically detects origin if served from FastAPI server or fallbacks to localhost:8000
const API_BASE = (window.location.origin && window.location.origin.startsWith('http')) 
  ? window.location.origin 
  : 'http://localhost:8000';

console.log('[Multimodal Search] Initialized API Base URL:', API_BASE);

const state = {
  query: '',
  searchMode: 'hybrid', // 'hybrid' | 'vector' | 'text'
  filters: {
    file_types: [],
    categories: [],
    dataset_ids: [],
    ai_generated: null,
    pii_detected: null,
    tags: []
  },
  selectedFileIds: new Set(),
  currentResults: [],
  facets: null
};

// DOM Elements
const searchInput = document.getElementById('searchInput');
const clearSearchBtn = document.getElementById('clearSearchBtn');
const submitSearchBtn = document.getElementById('submitSearchBtn');
const suggestionsBox = document.getElementById('suggestionsBox');
const trendingPills = document.getElementById('trendingPills');
const popularDatasetsWrapper = document.getElementById('popularDatasetsWrapper');
const popularDatasetsGrid = document.getElementById('popularDatasetsGrid');
const resultsHeaderBar = document.getElementById('resultsHeaderBar');
const resultsCount = document.getElementById('resultsCount');
const resultsQueryHighlight = document.getElementById('resultsQueryHighlight');
const resultsLatency = document.getElementById('resultsLatency');
const resultsModeTag = document.getElementById('resultsModeTag');
const resultsGrid = document.getElementById('resultsGrid');
const noResultsState = document.getElementById('noResultsState');
const resetFiltersBtn = document.getElementById('resetFiltersBtn');
const btnResetSearch = document.getElementById('btnResetSearch');
const activeChipsBar = document.getElementById('activeChipsBar');

// Modals & Batch Elements
const batchBar = document.getElementById('batchBar');
const batchCountBadge = document.getElementById('batchCountBadge');
const btnClearBatch = document.getElementById('btnClearBatch');
const btnOpenExportModal = document.getElementById('btnOpenExportModal');

const previewModal = document.getElementById('previewModal');
const closePreviewModalBtn = document.getElementById('closePreviewModalBtn');
const previewModalContent = document.getElementById('previewModalContent');

const similarModal = document.getElementById('similarModal');
const closeSimilarModalBtn = document.getElementById('closeSimilarModalBtn');
const similarResultsGrid = document.getElementById('similarResultsGrid');
const similarModalSubtitle = document.getElementById('similarModalSubtitle');

const exportModal = document.getElementById('exportModal');
const closeExportModalBtn = document.getElementById('closeExportModalBtn');
const btnCancelExport = document.getElementById('btnCancelExport');
const btnConfirmExport = document.getElementById('btnConfirmExport');
const exportTotalFiles = document.getElementById('exportTotalFiles');
const exportResultBox = document.getElementById('exportResultBox');
const toastContainer = document.getElementById('toastContainer');

// Toast Notification
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `<span>${type === 'success' ? '✓' : 'ℹ'}</span> <span>${message}</span>`;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

// Health Check
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) {
      document.getElementById('healthText').textContent = 'API Live';
    }
  } catch (e) {
    document.getElementById('healthText').textContent = 'API Offline';
    console.warn('Health check failed:', e);
  }
}

// Fetch and Render Trending Searches
async function loadTrendingSearches() {
  try {
    const res = await fetch(`${API_BASE}/search/trending?limit=6`);
    const data = await res.json();
    trendingPills.innerHTML = '';
    
    if (data.trending && data.trending.length > 0) {
      data.trending.forEach(item => {
        const btn = document.createElement('button');
        btn.className = 'trending-pill';
        btn.innerHTML = `${item.query} <span style="font-size:0.68rem; opacity:0.7">(${item.search_count})</span>`;
        btn.onclick = () => {
          searchInput.value = item.query;
          state.query = item.query;
          state.filters.dataset_ids = [];
          executeSearch();
        };
        trendingPills.appendChild(btn);
      });
    }
  } catch (e) {
    console.warn('Failed to load trending searches:', e);
  }
}

// Fetch and Render Popular Datasets
async function loadPopularDatasets() {
  try {
    const res = await fetch(`${API_BASE}/datasets/popular?limit=6`);
    const data = await res.json();
    popularDatasetsGrid.innerHTML = '';

    if (data.datasets && data.datasets.length > 0) {
      data.datasets.forEach(ds => {
        const card = document.createElement('div');
        card.className = 'dataset-card';
        card.innerHTML = `
          <img class="dataset-card-banner" src="${ds.thumbnail_url || 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600'}" alt="${ds.name}" />
          <div class="dataset-name">${ds.name}</div>
          <div class="dataset-desc">${ds.description || 'Multimodal asset collection'}</div>
          <div class="dataset-footer">
            <span>${ds.category} • ${ds.file_count || 15} files</span>
            <span class="dataset-pop-score">⭐ ${Math.round(ds.popularity_score)} score</span>
          </div>
        `;
        card.onclick = () => {
          searchInput.value = ds.name;
          state.query = ds.name;
          state.filters.dataset_ids = [];
          executeSearch();
        };
        popularDatasetsGrid.appendChild(card);
      });
    }
  } catch (e) {
    console.warn('Failed to load popular datasets:', e);
  }
}

// Fetch Facets
async function loadFacets() {
  try {
    const queryParams = new URLSearchParams();
    const q = (searchInput.value || state.query || '').trim();
    if (q) queryParams.append('q', q);
    state.filters.file_types.forEach(ft => queryParams.append('file_type', ft));
    state.filters.categories.forEach(cat => queryParams.append('category', cat));
    
    const res = await fetch(`${API_BASE}/search/facets?${queryParams.toString()}`);
    const data = await res.json();
    state.facets = data;
    renderFacets(data);
  } catch (e) {
    console.warn('Failed to load facets:', e);
  }
}

// Render Facet Sidebar Lists
function renderFacets(data) {
  if (!data) return;

  // File Types
  const ftContainer = document.getElementById('facetFileTypes');
  ftContainer.innerHTML = '';
  const standardTypes = ['image', 'video', 'audio', 'document', 'csv'];
  
  standardTypes.forEach(type => {
    const matched = (data.file_types || []).find(f => f.value.toLowerCase() === type);
    const count = matched ? matched.count : 0;
    const isSelected = state.filters.file_types.includes(type);

    const row = document.createElement('div');
    row.className = `filter-option-row ${isSelected ? 'selected' : ''}`;
    row.innerHTML = `
      <div class="filter-option-left">
        <input type="checkbox" ${isSelected ? 'checked' : ''} style="accent-color:var(--accent-cyan);" />
        <span>${type.toUpperCase()}</span>
      </div>
      <span class="facet-badge-count">${count}</span>
    `;
    row.onclick = () => {
      if (isSelected) {
        state.filters.file_types = state.filters.file_types.filter(t => t !== type);
      } else {
        state.filters.file_types.push(type);
      }
      executeSearch();
    };
    ftContainer.appendChild(row);
  });

  // Categories
  const catContainer = document.getElementById('facetCategories');
  catContainer.innerHTML = '';
  (data.categories || []).forEach(cat => {
    const isSelected = state.filters.categories.includes(cat.value);
    const row = document.createElement('div');
    row.className = `filter-option-row ${isSelected ? 'selected' : ''}`;
    row.innerHTML = `
      <div class="filter-option-left">
        <input type="checkbox" ${isSelected ? 'checked' : ''} style="accent-color:var(--accent-cyan);" />
        <span>${cat.value}</span>
      </div>
      <span class="facet-badge-count">${cat.count}</span>
    `;
    row.onclick = () => {
      if (isSelected) {
        state.filters.categories = state.filters.categories.filter(c => c !== cat.value);
      } else {
        state.filters.categories.push(cat.value);
      }
      executeSearch();
    };
    catContainer.appendChild(row);
  });

  // AI Generated
  const aiContainer = document.getElementById('facetAiGenerated');
  aiContainer.innerHTML = '';
  [
    { label: 'AI Generated Only', val: true },
    { label: 'Human / Authentic Only', val: false }
  ].forEach(opt => {
    const isSelected = state.filters.ai_generated === opt.val;
    const row = document.createElement('div');
    row.className = `filter-option-row ${isSelected ? 'selected' : ''}`;
    row.innerHTML = `
      <div class="filter-option-left">
        <input type="checkbox" ${isSelected ? 'checked' : ''} style="accent-color:var(--accent-cyan);" />
        <span>${opt.label}</span>
      </div>
    `;
    row.onclick = () => {
      state.filters.ai_generated = isSelected ? null : opt.val;
      executeSearch();
    };
    aiContainer.appendChild(row);
  });

  // PII Detected
  const piiContainer = document.getElementById('facetPiiDetected');
  piiContainer.innerHTML = '';
  [
    { label: 'PII Flagged Content', val: true },
    { label: 'Privacy Safe (No PII)', val: false }
  ].forEach(opt => {
    const isSelected = state.filters.pii_detected === opt.val;
    const row = document.createElement('div');
    row.className = `filter-option-row ${isSelected ? 'selected' : ''}`;
    row.innerHTML = `
      <div class="filter-option-left">
        <input type="checkbox" ${isSelected ? 'checked' : ''} style="accent-color:var(--accent-cyan);" />
        <span>${opt.label}</span>
      </div>
    `;
    row.onclick = () => {
      state.filters.pii_detected = isSelected ? null : opt.val;
      executeSearch();
    };
    piiContainer.appendChild(row);
  });

  // Top Tags
  const tagsContainer = document.getElementById('facetTopTags');
  tagsContainer.innerHTML = '';
  (data.top_tags || []).slice(0, 12).forEach(tag => {
    const isSelected = state.filters.tags.includes(tag.value);
    const tagEl = document.createElement('span');
    tagEl.className = `tag-cloud-item ${isSelected ? 'selected' : ''}`;
    tagEl.textContent = `#${tag.value} (${tag.count})`;
    tagEl.onclick = () => {
      if (isSelected) {
        state.filters.tags = state.filters.tags.filter(t => t !== tag.value);
      } else {
        state.filters.tags.push(tag.value);
      }
      executeSearch();
    };
    tagsContainer.appendChild(tagEl);
  });

  renderActiveChips();
}

// Render Active Filter Chips
function renderActiveChips() {
  activeChipsBar.innerHTML = '';
  let count = 0;

  state.filters.file_types.forEach(ft => {
    count++;
    createChip(`Type: ${ft}`, () => {
      state.filters.file_types = state.filters.file_types.filter(t => t !== ft);
      executeSearch();
    });
  });

  state.filters.categories.forEach(cat => {
    count++;
    createChip(`Category: ${cat}`, () => {
      state.filters.categories = state.filters.categories.filter(c => c !== cat);
      executeSearch();
    });
  });

  if (state.filters.ai_generated !== null) {
    count++;
    createChip(state.filters.ai_generated ? 'AI-Generated' : 'Authentic', () => {
      state.filters.ai_generated = null;
      executeSearch();
    });
  }

  if (state.filters.pii_detected !== null) {
    count++;
    createChip(state.filters.pii_detected ? 'PII Flagged' : 'No PII', () => {
      state.filters.pii_detected = null;
      executeSearch();
    });
  }

  state.filters.tags.forEach(t => {
    count++;
    createChip(`#${t}`, () => {
      state.filters.tags = state.filters.tags.filter(tag => tag !== t);
      executeSearch();
    });
  });

  activeChipsBar.classList.toggle('hidden', count === 0);
}

function createChip(text, onRemove) {
  const chip = document.createElement('div');
  chip.className = 'active-chip';
  chip.innerHTML = `<span>${text}</span> <span class="active-chip-remove">&times;</span>`;
  chip.onclick = onRemove;
  activeChipsBar.appendChild(chip);
}

// Main Search Function
async function executeSearch() {
  const rawInput = searchInput ? searchInput.value : '';
  const query = (rawInput || state.query || '').trim();
  state.query = query;

  suggestionsBox.classList.add('hidden');

  const hasFilters = state.filters.file_types.length > 0 ||
                     state.filters.categories.length > 0 ||
                     state.filters.tags.length > 0 ||
                     state.filters.ai_generated !== null ||
                     state.filters.pii_detected !== null;

  // Show results header
  popularDatasetsWrapper.classList.add('hidden');
  resultsHeaderBar.classList.remove('hidden');

  const payload = {
    query: query || 'all',
    filters: {
      file_types: state.filters.file_types.length ? state.filters.file_types : null,
      categories: state.filters.categories.length ? state.filters.categories : null,
      dataset_ids: state.filters.dataset_ids.length ? state.filters.dataset_ids : null,
      ai_generated: state.filters.ai_generated,
      pii_detected: state.filters.pii_detected,
      tags: state.filters.tags.length ? state.filters.tags : null
    },
    search_mode: state.searchMode,
    limit: 24,
    offset: 0,
    rrf_k: 60,
    keyword_weight: 0.5,
    vector_weight: 0.5
  };

  console.log('[Multimodal Search] Executing search with payload:', payload);

  try {
    resultsGrid.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding:3rem; color:var(--accent-cyan);">⚡ Querying Hybrid Neural & Keyword Retrieval Pipelines...</div>';
    
    let res;
    if (state.searchMode === 'vector') {
      res = await fetch(`${API_BASE}/search/vector`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query || 'all', filters: payload.filters, limit: 24 })
      });
    } else if (state.searchMode === 'text') {
      res = await fetch(`${API_BASE}/search/text?q=${encodeURIComponent(query || 'all')}`, {
        method: 'GET'
      });
    } else {
      res = await fetch(`${API_BASE}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    }

    if (!res.ok) {
      throw new Error(`API returned HTTP ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    console.log('[Multimodal Search] Received results:', data);
    state.currentResults = data.results || [];

    // Header info
    resultsCount.textContent = data.total || 0;
    resultsQueryHighlight.textContent = query ? `"${query}"` : 'All assets';
    resultsLatency.textContent = `${data.execution_time_ms}ms`;
    resultsModeTag.textContent = state.searchMode.toUpperCase();

    if (data.facets) {
      renderFacets(data.facets);
    } else {
      await loadFacets();
    }

    renderResults(state.currentResults);

  } catch (e) {
    console.error('Search error:', e);
    resultsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding:3rem; color:var(--accent-rose);">Error executing search: ${e.message}</div>`;
  }
}

// Render Result Cards
function renderResults(results) {
  resultsGrid.innerHTML = '';
  
  if (!results || results.length === 0) {
    noResultsState.classList.remove('hidden');
    return;
  }

  noResultsState.classList.add('hidden');

  results.forEach(file => {
    const isSelected = state.selectedFileIds.has(file.file_id);
    const score = file.score_info;
    const scoreText = score ? `RRF ${score.rrf_score.toFixed(3)}` : '1.0';

    const card = document.createElement('div');
    card.className = 'result-card';
    card.innerHTML = `
      <div class="media-thumbnail-container">
        <img class="media-img" src="${file.thumbnail_url || 'https://images.unsplash.com/photo-1578328819058-b69f3a3b0f6b?w=600'}" alt="${file.title}" onerror="this.src='https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600'" />
        <div class="type-pill">
          <span>${getTypeIcon(file.file_type)}</span>
          <span>${file.file_type}</span>
        </div>
        <input type="checkbox" class="card-checkbox" ${isSelected ? 'checked' : ''} />
        <div class="rrf-score-badge" title="RRF score computed from Keyword & Vector rank">${scoreText}</div>
      </div>

      <div class="card-content">
        <div class="card-dataset-label">${file.dataset_name} • ${file.category}</div>
        <div class="card-title-text">${file.title}</div>
        <div class="card-caption-snippet">${file.caption || file.description || file.content_summary || ''}</div>
        
        <div class="card-tags-list">
          ${(file.tags || []).slice(0, 4).map(t => `<span class="tag-badge">#${t}</span>`).join('')}
          ${file.ai_generated ? '<span class="tag-badge" style="color:var(--accent-purple)">AI-Gen</span>' : ''}
          ${file.pii_detected ? '<span class="tag-badge" style="color:var(--accent-amber)">PII</span>' : ''}
        </div>

        <div class="card-actions-footer">
          <button class="action-btn-sm btn-preview" title="View Full AI Enrichment & Preview">
            👁️ Preview
          </button>
          <button class="action-btn-sm btn-similar" title="Find Similar Files in Vector Space">
            🔄 Similar
          </button>
        </div>
      </div>
    `;

    // Checkbox toggle
    const checkbox = card.querySelector('.card-checkbox');
    checkbox.onclick = (e) => {
      e.stopPropagation();
      toggleSelectFile(file.file_id);
    };

    // Actions
    card.querySelector('.btn-preview').onclick = (e) => {
      e.stopPropagation();
      openFilePreview(file.file_id);
    };

    card.querySelector('.btn-similar').onclick = (e) => {
      e.stopPropagation();
      openSimilarFiles(file.file_id, file.title);
    };

    resultsGrid.appendChild(card);
  });
}

function getTypeIcon(fileType) {
  switch (fileType) {
    case 'image': return '🖼️';
    case 'video': return '🎥';
    case 'audio': return '🎙️';
    case 'document': return '📄';
    case 'csv': return '📊';
    default: return '📁';
  }
}

// Batch Selection Logic
function toggleSelectFile(fileId) {
  if (state.selectedFileIds.has(fileId)) {
    state.selectedFileIds.delete(fileId);
  } else {
    state.selectedFileIds.add(fileId);
  }
  updateBatchUI();
}

function updateBatchUI() {
  const count = state.selectedFileIds.size;
  batchCountBadge.textContent = count;
  batchBar.classList.toggle('hidden', count === 0);
}

btnClearBatch.onclick = () => {
  state.selectedFileIds.clear();
  updateBatchUI();
  renderResults(state.currentResults);
};

// Open File Preview Modal
async function openFilePreview(fileId) {
  previewModal.classList.remove('hidden');
  previewModalContent.innerHTML = '<div style="text-align:center; padding:3rem; color:var(--accent-cyan);">Loading file enrichment metadata...</div>';

  try {
    const res = await fetch(`${API_BASE}/files/${fileId}`);
    const file = await res.json();

    previewModalContent.innerHTML = `
      <img class="preview-top-banner" src="${file.preview_url || file.thumbnail_url || 'https://images.unsplash.com/photo-1578328819058-b69f3a3b0f6b?w=1600'}" alt="${file.title}" onerror="this.src='https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1600'" />
      
      <div>
        <div style="font-size:0.78rem; color:var(--text-muted);">${file.dataset_name} • ${file.category}</div>
        <h2 style="font-family:var(--font-display); font-size:1.3rem; margin-top:0.2rem;">${file.title}</h2>
      </div>

      <div class="preview-grid-details">
        <!-- AI Vision & Caption -->
        <div class="detail-card-box">
          <div class="detail-box-title">🤖 AI Vision Caption & Summary</div>
          <p style="font-size:0.85rem; color:var(--text-secondary); margin-bottom:0.5rem;">${file.caption || 'No caption generated'}</p>
          <p style="font-size:0.8rem; color:var(--text-muted);">${file.content_summary || ''}</p>
        </div>

        <!-- Technical Specs -->
        <div class="detail-card-box">
          <div class="detail-box-title">⚙️ Technical Metadata</div>
          <table class="technical-specs-table">
            <tr><td class="spec-key">File Name:</td><td class="spec-val">${file.file_name}</td></tr>
            <tr><td class="spec-key">Format / Mime:</td><td class="spec-val">${file.technical.mime_type}</td></tr>
            <tr><td class="spec-key">File Size:</td><td class="spec-val">${(file.technical.file_size / 1024 / 1024).toFixed(2)} MB</td></tr>
            ${file.technical.duration ? `<tr><td class="spec-key">Duration:</td><td class="spec-val">${file.technical.duration}s</td></tr>` : ''}
            ${file.technical.width ? `<tr><td class="spec-key">Dimensions:</td><td class="spec-val">${file.technical.width} x ${file.technical.height}</td></tr>` : ''}
            <tr><td class="spec-key">SHA-256 Checksum:</td><td class="spec-val" style="font-size:0.68rem;">${file.technical.checksum}</td></tr>
          </table>
        </div>

        <!-- OCR Text -->
        ${file.ocr_text ? `
          <div class="detail-card-box" style="grid-column: 1/-1;">
            <div class="detail-box-title">🔤 Optical Character Recognition (OCR Text)</div>
            <div class="detail-text-content">${file.ocr_text}</div>
          </div>
        ` : ''}

        <!-- Audio Transcript -->
        ${file.transcript ? `
          <div class="detail-card-box" style="grid-column: 1/-1;">
            <div class="detail-box-title">🎙️ Audio Speech-To-Text Transcript</div>
            <div class="detail-text-content">${file.transcript}</div>
          </div>
        ` : ''}
      </div>

      <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--border-glass); padding-top:1rem;">
        <button class="btn-secondary" id="previewFindSimilarBtn">🔄 Find Similar Files</button>
        <button class="btn-primary" id="previewSelectDownloadBtn">
          ${state.selectedFileIds.has(file.file_id) ? '✓ Selected for Download' : '➕ Add to Download Selection'}
        </button>
      </div>
    `;

    document.getElementById('previewFindSimilarBtn').onclick = () => {
      previewModal.classList.add('hidden');
      openSimilarFiles(file.file_id, file.title);
    };

    document.getElementById('previewSelectDownloadBtn').onclick = () => {
      toggleSelectFile(file.file_id);
      previewModal.classList.add('hidden');
      renderResults(state.currentResults);
      showToast(`Updated selection for ${file.file_name}`, 'success');
    };

  } catch (e) {
    previewModalContent.innerHTML = `<div style="color:var(--accent-rose);">Error fetching file preview: ${e.message}</div>`;
  }
}

closePreviewModalBtn.onclick = () => previewModal.classList.add('hidden');
previewModal.onclick = (e) => {
  if (e.target === previewModal) previewModal.classList.add('hidden');
};

// Open Similar Files Modal
async function openSimilarFiles(fileId, title) {
  similarModal.classList.remove('hidden');
  similarModalSubtitle.textContent = `Finding vector nearest neighbors for "${title}" in Qdrant...`;
  similarResultsGrid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:2rem; color:var(--accent-cyan);">⚡ Querying Cosine Distance in Qdrant Vector Collection...</div>';

  try {
    const res = await fetch(`${API_BASE}/search/similar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: fileId, limit: 6 })
    });
    const data = await res.json();
    similarResultsGrid.innerHTML = '';

    if (!data.results || data.results.length === 0) {
      similarResultsGrid.innerHTML = '<div style="grid-column:1/-1; text-align:center; color:var(--text-muted);">No similar files found.</div>';
      return;
    }

    data.results.forEach(file => {
      const card = document.createElement('div');
      card.className = 'result-card';
      card.innerHTML = `
        <div class="media-thumbnail-container" style="height:140px;">
          <img class="media-img" src="${file.thumbnail_url || 'https://images.unsplash.com/photo-1578328819058-b69f3a3b0f6b?w=600'}" alt="${file.title}" onerror="this.src='https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600'" />
          <div class="type-pill"><span>${getTypeIcon(file.file_type)}</span> ${file.file_type}</div>
          <div class="rrf-score-badge">Similarity: ${(file.score_info.vector_similarity || 0.85).toFixed(2)}</div>
        </div>
        <div class="card-content">
          <div class="card-title-text">${file.title}</div>
          <div class="card-dataset-label">${file.dataset_name}</div>
        </div>
      `;
      card.onclick = () => {
        similarModal.classList.add('hidden');
        openFilePreview(file.file_id);
      };
      similarResultsGrid.appendChild(card);
    });

  } catch (e) {
    similarResultsGrid.innerHTML = `<div style="grid-column:1/-1; color:var(--accent-rose);">Error loading similar files: ${e.message}</div>`;
  }
}

closeSimilarModalBtn.onclick = () => similarModal.classList.add('hidden');
similarModal.onclick = (e) => {
  if (e.target === similarModal) similarModal.classList.add('hidden');
};

// Download & Audit Export Modal
btnOpenExportModal.onclick = () => {
  exportModal.classList.remove('hidden');
  exportTotalFiles.textContent = `${state.selectedFileIds.size} assets selected`;
  exportResultBox.classList.add('hidden');
  btnConfirmExport.disabled = false;
};

closeExportModalBtn.onclick = () => exportModal.classList.add('hidden');
btnCancelExport.onclick = () => exportModal.classList.add('hidden');
exportModal.onclick = (e) => {
  if (e.target === exportModal) exportModal.classList.add('hidden');
};

btnConfirmExport.onclick = async () => {
  btnConfirmExport.disabled = true;
  btnConfirmExport.textContent = 'Dispatching to Auditing...';

  try {
    const res = await fetch(`${API_BASE}/events/export-download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        selected_file_ids: Array.from(state.selectedFileIds),
        bundle_metadata_csv: true,
        search_query: state.query
      })
    });
    const data = await res.json();

    exportResultBox.classList.remove('hidden');
    exportResultBox.innerHTML = `
      <div style="font-weight:700; color:var(--accent-emerald); margin-bottom:0.4rem;">
        ✓ ${data.message}
      </div>
      <div><strong>Audit Event ID:</strong> <code>${data.audit_event_id}</code></div>
      <div><strong>Download Task:</strong> <code>${data.export_task_id}</code></div>
      <div><strong>Bundled Manifest:</strong> <code>${data.metadata_bundle}</code></div>
    `;

    btnConfirmExport.textContent = 'Export Dispatched';
    showToast('Batch submitted to Download & Auditing module!', 'success');

  } catch (e) {
    exportResultBox.classList.remove('hidden');
    exportResultBox.innerHTML = `<div style="color:var(--accent-rose);">Export failed: ${e.message}</div>`;
    btnConfirmExport.disabled = false;
    btnConfirmExport.textContent = 'Confirm & Dispatch';
  }
};

// Autocomplete Suggestions with Debounce
let suggestTimer = null;
searchInput.addEventListener('input', () => {
  const val = searchInput.value.trim();
  state.query = val;
  clearTimeout(suggestTimer);

  if (!val) {
    suggestionsBox.classList.add('hidden');
    return;
  }

  suggestTimer = setTimeout(async () => {
    try {
      const res = await fetch(`${API_BASE}/search/suggestions?q=${encodeURIComponent(val)}&limit=6`);
      const data = await res.json();
      
      if (data.suggestions && data.suggestions.length > 0) {
        suggestionsBox.innerHTML = '';
        data.suggestions.forEach(item => {
          const div = document.createElement('div');
          div.className = 'suggestion-item';
          div.innerHTML = `
            <span>${item.text}</span>
            <span class="suggestion-badge">${item.badge || item.type}</span>
          `;
          div.onclick = () => {
            searchInput.value = item.text;
            state.query = item.text;
            suggestionsBox.classList.add('hidden');
            executeSearch();
          };
          suggestionsBox.appendChild(div);
        });
        suggestionsBox.classList.remove('hidden');
      } else {
        suggestionsBox.classList.add('hidden');
      }
    } catch (e) {
      console.warn(e);
    }
  }, 200);
});

// Search Mode Tabs
document.querySelectorAll('.mode-tab').forEach(tab => {
  tab.onclick = () => {
    document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    state.searchMode = tab.dataset.mode;
    executeSearch();
  };
});

// Submit Buttons & Enter Key
submitSearchBtn.onclick = executeSearch;
searchInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') executeSearch();
});

clearSearchBtn.onclick = () => {
  searchInput.value = '';
  state.query = '';
  suggestionsBox.classList.add('hidden');
  executeSearch();
};

resetFiltersBtn.onclick = () => {
  state.filters.file_types = [];
  state.filters.categories = [];
  state.filters.dataset_ids = [];
  state.filters.ai_generated = null;
  state.filters.pii_detected = null;
  state.filters.tags = [];
  executeSearch();
};

btnResetSearch.onclick = () => {
  searchInput.value = '';
  state.query = '';
  resetFiltersBtn.click();
};

// Initialize on page load - loads initial results immediately!
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  loadTrendingSearches();
  loadPopularDatasets();
  loadFacets();
  // Auto-load initial discovery files on startup
  executeSearch();
});

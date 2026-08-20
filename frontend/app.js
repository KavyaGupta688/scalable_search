const form = document.querySelector('#search-form');
const queryInput = document.querySelector('#query');
const modeInput = document.querySelector('#mode');
const typeInput = document.querySelector('#content-type');
const status = document.querySelector('#status');
const grid = document.querySelector('#result-grid');
const title = document.querySelector('#result-title');

function renderResults(data) {
  title.textContent = `${data.total} result${data.total === 1 ? '' : 's'} found`;
  status.textContent = data.total ? `Matching “${data.query}” in your library` : 'No files matched that search.';
  grid.innerHTML = data.results.map((result) => `
    <article class="result-card">
      <div class="thumb" aria-hidden="true">${result.content_type === 'image' ? '◈' : '▤'}</div>
      <div class="card-copy"><h3>${result.name}</h3><p>${result.description}</p><div class="tags">${result.tags.map((tag) => `<span class="tag">${tag}</span>`).join('')}</div></div>
    </article>`).join('');
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  status.textContent = 'Searching your library...';
  grid.innerHTML = '';
  const payload = { query: queryInput.value, mode: modeInput.value, content_type: typeInput.value || null };
  try {
    const response = await fetch('/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error('Search request failed');
    renderResults(await response.json());
  } catch (error) {
    title.textContent = 'Search unavailable';
    status.textContent = 'Start the API server to connect this view to your library.';
  }
});

document.querySelector('#clear-filters').addEventListener('click', () => { typeInput.value = ''; });

const uploadForm = document.querySelector('#upload-form');
const documentInput = document.querySelector('#document');
const fileName = document.querySelector('#file-name');
const uploadStatus = document.querySelector('#upload-status');

documentInput.addEventListener('change', () => {
  fileName.textContent = documentInput.files[0]?.name || 'Choose a document';
});

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData();
  formData.append('file', documentInput.files[0]);
  uploadStatus.textContent = 'Validating document and queueing pipeline...';
  try {
    const response = await fetch('/ingestion/upload', { method: 'POST', body: formData });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Upload failed');
    uploadStatus.textContent = `${result.filename} queued. Extraction, AI enrichment, and indexing are pending.`;
    uploadForm.reset();
    fileName.textContent = 'Choose a document';
  } catch (error) {
    uploadStatus.textContent = error.message;
  }
});
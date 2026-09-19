// Frontend logic for the Forensic Watermarking Gateway Dashboard (Celery + Redis + PostgreSQL)

let availableFiles = [];
let pollingInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    checkSystemHealth();
    loadS3Files();
    loadAuditLogs();
    initDownloadForm();
    initAsyncBatchQueue();
    initForensicDropzone();
    initExplorerControls();

    // Refresh Buttons
    document.getElementById('btn-refresh-s3')?.addEventListener('click', loadS3Files);
    document.getElementById('btn-refresh-audit')?.addEventListener('click', loadAuditLogs);
});

// Initialize Folder Tree and Search Controls
function initExplorerControls() {
    // 1. View Mode Toggles
    const btnTree = document.getElementById('btn-view-tree');
    const btnFlat = document.getElementById('btn-view-flat');

    btnTree?.addEventListener('click', () => {
        currentViewMode = 'tree';
        btnTree.classList.add('active');
        btnFlat?.classList.remove('active');
        renderS3Catalog();
    });

    btnFlat?.addEventListener('click', () => {
        currentViewMode = 'flat';
        btnFlat.classList.add('active');
        btnTree?.classList.remove('active');
        renderS3Catalog();
    });

    // 2. S3 Catalog Search Filter
    const searchInput = document.getElementById('s3-search-input');
    searchInput?.addEventListener('input', (e) => {
        catalogSearchQuery = e.target.value;
        renderS3Catalog();
    });

    // 3. Catalog Select All & Clear
    document.getElementById('btn-select-all-catalog')?.addEventListener('click', () => {
        availableFiles.forEach(f => toggleFileSelection(f, true, false));
        updateSelectionUI();
        renderS3Catalog();
    });

    document.getElementById('btn-clear-selection')?.addEventListener('click', () => {
        selectedFilesMap.clear();
        updateSelectionUI();
        renderS3Catalog();
    });

    // 4. Selected Items Drawer Toggle
    const drawerEl = document.getElementById('selected-items-drawer');
    const toggleDrawerBtn = document.getElementById('btn-toggle-selected-drawer');
    const closeDrawerBtn = document.getElementById('btn-close-drawer');

    toggleDrawerBtn?.addEventListener('click', () => {
        const isHidden = drawerEl?.classList.toggle('hidden');
        if (toggleDrawerBtn) {
            toggleDrawerBtn.textContent = isHidden ? 'View Selected ▾' : 'Hide Selected ▴';
        }
    });

    closeDrawerBtn?.addEventListener('click', () => {
        drawerEl?.classList.add('hidden');
        if (toggleDrawerBtn) {
            toggleDrawerBtn.textContent = 'View Selected ▾';
        }
    });

    // 5. Expand All / Collapse All
    document.getElementById('btn-expand-all')?.addEventListener('click', () => {
        document.querySelectorAll('#s3-file-list .folder-children').forEach(el => el.classList.remove('collapsed'));
        document.querySelectorAll('#s3-file-list .folder-arrow').forEach(el => el.classList.add('expanded'));
        document.querySelectorAll('#s3-file-list .folder-icon').forEach(el => el.textContent = '📂');
    });

    document.getElementById('btn-collapse-all')?.addEventListener('click', () => {
        document.querySelectorAll('#s3-file-list .folder-children').forEach(el => el.classList.add('collapsed'));
        document.querySelectorAll('#s3-file-list .folder-arrow').forEach(el => el.classList.remove('expanded'));
        document.querySelectorAll('#s3-file-list .folder-icon').forEach(el => el.textContent = '📁');
    });

    // 6. Async Batch Selection Controls
    const asyncSearchInput = document.getElementById('async-search-input');
    asyncSearchInput?.addEventListener('input', (e) => {
        asyncSearchQuery = e.target.value;
        renderAsyncBatchSelector();
    });

    document.getElementById('btn-select-all')?.addEventListener('click', () => {
        availableFiles.forEach(f => toggleFileSelection(f, true, false));
        updateSelectionUI();
        renderS3Catalog();
        renderAsyncBatchSelector();
    });

    document.getElementById('btn-deselect-all')?.addEventListener('click', () => {
        selectedFilesMap.clear();
        updateSelectionUI();
        renderS3Catalog();
        renderAsyncBatchSelector();
    });
}

// 1. System Health Check (PostgreSQL + Redis + S3)
async function checkSystemHealth() {
    const dbLabel = document.getElementById('db-status-label');
    const dbDot = document.getElementById('db-dot');
    const redisLabel = document.getElementById('redis-status-label');
    const auditEngineLabel = document.getElementById('audit-db-engine-label');

    try {
        const res = await fetch('/api/system/health');
        const data = await res.json();

        if (data.database && data.database.connected) {
            dbLabel.textContent = `DB: ${data.database.engine}`;
            dbDot.style.background = 'var(--accent-emerald)';
            dbDot.style.boxShadow = '0 0 10px var(--accent-emerald)';
            if (auditEngineLabel) {
                auditEngineLabel.textContent = `Database Engine: ${data.database.engine}`;
            }
        } else {
            dbLabel.textContent = `DB: Offline (${data.database.engine})`;
            dbDot.style.background = 'var(--accent-amber)';
        }

        if (data.redis_broker && data.redis_broker.connected) {
            redisLabel.textContent = `Redis: Connected (${data.redis_broker.host})`;
        } else {
            redisLabel.textContent = `Redis: Standby / Inline Mode`;
        }
    } catch (e) {
        console.warn('Health check failed:', e);
    }
}

// 2. Tab Switching
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetTabId = btn.getAttribute('data-tab');
            const targetPanel = document.getElementById(targetTabId);
            if (targetPanel) {
                targetPanel.classList.add('active');
            }

            if (targetTabId === 'tab-audit') {
                loadAuditLogs();
            }
        });
    });
}

// View & Selection State (Persistent Memory)
let currentViewMode = 'tree'; // 'tree' or 'flat'
let catalogSearchQuery = '';
let asyncSearchQuery = '';
const selectedFilesMap = new Map(); // key -> { key, size_bytes, name }

// Helper: Build nested tree hierarchy from flat S3 keys
function buildFolderTree(files) {
    const root = { name: '', path: '', isFolder: true, children: {}, files: [], totalSize: 0, totalCount: 0 };

    files.forEach(file => {
        const parts = file.key.split('/');
        let current = root;
        current.totalSize += file.size_bytes || 0;
        current.totalCount += 1;

        for (let i = 0; i < parts.length - 1; i++) {
            const folderName = parts[i];
            const folderPath = parts.slice(0, i + 1).join('/');
            if (!current.children[folderName]) {
                current.children[folderName] = {
                    name: folderName,
                    path: folderPath,
                    isFolder: true,
                    children: {},
                    files: [],
                    totalSize: 0,
                    totalCount: 0
                };
            }
            current = current.children[folderName];
            current.totalSize += file.size_bytes || 0;
            current.totalCount += 1;
        }

        const fileName = parts[parts.length - 1];
        if (fileName) {
            current.files.push({
                ...file,
                name: fileName
            });
        }
    });

    return root;
}

// 3. Fetch & Render S3 Catalog
async function loadS3Files() {
    const listEl = document.getElementById('s3-file-list');
    const bucketInfoEl = document.getElementById('bucket-info-text');

    try {
        const res = await fetch('/api/s3/files');
        const data = await res.json();
        availableFiles = data.files || [];

        if (bucketInfoEl) {
            bucketInfoEl.textContent = `Bucket: ${data.bucket} ${data.is_mock_mode ? '(Local Demo Repository)' : '(Live AWS S3)'}`;
        }

        if (data.error) {
            listEl.innerHTML = `
                <div style="padding: 1.25rem; background: rgba(239, 68, 68, 0.1); border: 1px solid var(--accent-rose); border-radius: 8px; color: var(--text-primary);">
                    <div style="color: var(--accent-rose); font-weight: 600; margin-bottom: 0.5rem;">⚠️ AWS S3 Connection Error</div>
                    <div style="font-size: 0.85rem; font-family: monospace; margin-bottom: 0.75rem; word-break: break-word;">${data.error}</div>
                    <div style="font-size: 0.8rem; color: var(--text-muted);">${data.hint || 'Check credentials in .env file'}</div>
                </div>
            `;
            return;
        }

        if (availableFiles.length === 0) {
            listEl.innerHTML = '<div class="loading-spinner">No files found in S3 bucket.</div>';
            return;
        }

        // Auto-select first file if nothing is selected yet
        if (selectedFilesMap.size === 0 && availableFiles.length > 0) {
            toggleFileSelection(availableFiles[0], true, false);
        }

        renderS3Catalog();
        renderAsyncBatchSelector();
        updateSelectionUI();

    } catch (err) {
        console.error('Failed to load S3 files:', err);
        listEl.innerHTML = `<div class="loading-spinner" style="color: var(--accent-rose)">Failed to connect to S3 gateway.</div>`;
    }
}

// Toggle individual file selection
function toggleFileSelection(file, isSelected, shouldUpdateUI = true) {
    if (isSelected) {
        selectedFilesMap.set(file.key, file);
    } else {
        selectedFilesMap.delete(file.key);
    }
    if (shouldUpdateUI) {
        updateSelectionUI();
    }
}

// Toggle all files in a folder
function toggleFolderSelection(node, isSelected) {
    const applyToNode = (n) => {
        n.files.forEach(f => toggleFileSelection(f, isSelected, false));
        Object.values(n.children).forEach(child => applyToNode(child));
    };
    applyToNode(node);
    updateSelectionUI();
    renderS3Catalog();
}

// Update all selection stats, memory metrics, badges, and button labels
function updateSelectionUI() {
    const count = selectedFilesMap.size;
    let totalBytes = 0;
    const selectedKeys = [];

    selectedFilesMap.forEach((file) => {
        totalBytes += file.size_bytes || 0;
        selectedKeys.push(file.key);
    });

    const memoryFormatted = formatBytes(totalBytes);

    // 1. Memory Tracker Bar
    const countEl = document.getElementById('selection-count');
    const memoryEl = document.getElementById('selection-memory');
    if (countEl) countEl.textContent = `${count} file${count === 1 ? '' : 's'}`;
    if (memoryEl) memoryEl.textContent = memoryFormatted;

    // 2. Right Form Summary Box
    const primarySummaryEl = document.getElementById('summary-primary-text');
    const secondarySummaryEl = document.getElementById('summary-secondary-text');
    const hiddenKeyInput = document.getElementById('selected-s3-key');

    if (count === 0) {
        if (primarySummaryEl) primarySummaryEl.textContent = 'No files selected';
        if (secondarySummaryEl) secondarySummaryEl.textContent = 'Select files or whole folders using checkboxes on the left';
        if (hiddenKeyInput) hiddenKeyInput.value = '';
    } else if (count === 1) {
        const firstFile = selectedFilesMap.values().next().value;
        if (primarySummaryEl) primarySummaryEl.textContent = `1 File Selected (${memoryFormatted})`;
        if (secondarySummaryEl) secondarySummaryEl.textContent = firstFile.key;
        if (hiddenKeyInput) hiddenKeyInput.value = firstFile.key;
    } else {
        if (primarySummaryEl) primarySummaryEl.textContent = `${count} Files Selected (${memoryFormatted})`;
        if (secondarySummaryEl) secondarySummaryEl.textContent = `${selectedKeys.slice(0, 3).join(', ')}${count > 3 ? ` ... +${count - 3} more` : ''}`;
        if (hiddenKeyInput) hiddenKeyInput.value = selectedKeys[0];
    }

    // 3. Action Buttons
    const btnZipText = document.getElementById('btn-zip-text');
    const btnSingleText = document.getElementById('btn-single-text');
    if (btnZipText) {
        btnZipText.textContent = `Download Selected as ZIP (${count} files • ${memoryFormatted})`;
    }
    if (btnSingleText) {
        if (count <= 1) {
            btnSingleText.textContent = count === 1 ? `Stream 1 File (${memoryFormatted})` : 'Stream Single File';
        } else {
            btnSingleText.textContent = `Stream 1st File (${formatBytes(selectedFilesMap.values().next().value?.size_bytes || 0)})`;
        }
    }

    // 4. Update Checkboxes in Catalog
    document.querySelectorAll('#s3-file-list .file-checkbox').forEach(cb => {
        const key = cb.getAttribute('data-key');
        cb.checked = selectedFilesMap.has(key);
    });

    // 5. Update Selected Drawer List
    const drawerListEl = document.getElementById('selected-items-list');
    if (drawerListEl) {
        drawerListEl.innerHTML = '';
        if (count === 0) {
            drawerListEl.innerHTML = '<div style="color: var(--text-dim); font-size: 0.75rem;">No files currently selected.</div>';
        } else {
            selectedFilesMap.forEach((file) => {
                const itemEl = document.createElement('div');
                itemEl.className = 'selected-drawer-item';
                itemEl.innerHTML = `
                    <span class="item-path">${file.key}</span>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span class="item-size">${formatBytes(file.size_bytes)}</span>
                        <button class="btn-remove-item" title="Remove from selection">✕</button>
                    </div>
                `;
                itemEl.querySelector('.btn-remove-item').addEventListener('click', () => {
                    toggleFileSelection(file, false);
                    renderS3Catalog();
                });
                drawerListEl.appendChild(itemEl);
            });
        }
    }
}

// Render S3 Catalog in Tree or Flat mode
function renderS3Catalog() {
    const listEl = document.getElementById('s3-file-list');
    if (!listEl) return;
    listEl.innerHTML = '';

    const query = catalogSearchQuery.trim().toLowerCase();
    const filteredFiles = query
        ? availableFiles.filter(f => f.key.toLowerCase().includes(query))
        : availableFiles;

    if (filteredFiles.length === 0) {
        listEl.innerHTML = `<div class="loading-spinner">No matching files found.</div>`;
        return;
    }

    if (currentViewMode === 'flat') {
        // Flat List View
        filteredFiles.forEach((file) => {
            listEl.appendChild(createFileItemEl(file));
        });
    } else {
        // Folder Tree View
        const treeRoot = buildFolderTree(filteredFiles);
        renderFolderNode(treeRoot, listEl, true);
    }
}

// Recursively render a folder node
function renderFolderNode(node, containerEl, isRoot = false) {
    if (!isRoot && node.name) {
        const folderNodeEl = document.createElement('div');
        folderNodeEl.className = 'folder-node';

        // Check if all files in this folder are selected
        const allFilesUnderNode = [];
        const collectFiles = (n) => {
            n.files.forEach(f => allFilesUnderNode.push(f));
            Object.values(n.children).forEach(c => collectFiles(c));
        };
        collectFiles(node);
        const isAllSelected = allFilesUnderNode.length > 0 && allFilesUnderNode.every(f => selectedFilesMap.has(f.key));

        const folderHeaderEl = document.createElement('div');
        folderHeaderEl.className = 'folder-header';
        folderHeaderEl.innerHTML = `
            <div class="folder-info">
                <input type="checkbox" class="folder-select-checkbox" ${isAllSelected ? 'checked' : ''} style="width: 15px; height: 15px; accent-color: var(--accent-blue);" title="Select/Deselect all files in this folder">
                <span class="folder-arrow expanded">▶</span>
                <span class="folder-icon">📂</span>
                <span class="folder-title">${node.name}</span>
                <span class="folder-meta">(${node.totalCount} files &bull; ${formatBytes(node.totalSize)})</span>
            </div>
            <button class="btn-text-sm select-folder-btn" title="Toggle selection of this folder">Toggle All</button>
        `;

        const childrenContainerEl = document.createElement('div');
        childrenContainerEl.className = 'folder-children';

        // Folder Checkbox Handler
        const folderCb = folderHeaderEl.querySelector('.folder-select-checkbox');
        folderCb.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleFolderSelection(node, folderCb.checked);
        });

        // Folder Header Click (Collapse/Expand)
        folderHeaderEl.addEventListener('click', (e) => {
            if (e.target.classList.contains('folder-select-checkbox') || e.target.classList.contains('select-folder-btn')) return;
            const arrow = folderHeaderEl.querySelector('.folder-arrow');
            const icon = folderHeaderEl.querySelector('.folder-icon');
            const isCollapsed = childrenContainerEl.classList.toggle('collapsed');
            if (isCollapsed) {
                arrow.classList.remove('expanded');
                icon.textContent = '📁';
            } else {
                arrow.classList.add('expanded');
                icon.textContent = '📂';
            }
        });

        // "Toggle All" Button
        folderHeaderEl.querySelector('.select-folder-btn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            const shouldSelect = !isAllSelected;
            toggleFolderSelection(node, shouldSelect);
        });

        // Render subfolders
        Object.values(node.children).forEach(childNode => {
            renderFolderNode(childNode, childrenContainerEl, false);
        });

        // Render direct files in this folder
        node.files.forEach(file => {
            childrenContainerEl.appendChild(createFileItemEl(file));
        });

        folderNodeEl.appendChild(folderHeaderEl);
        folderNodeEl.appendChild(childrenContainerEl);
        containerEl.appendChild(folderNodeEl);
    } else {
        // Root container: render direct subfolders and root files
        Object.values(node.children).forEach(childNode => {
            renderFolderNode(childNode, containerEl, false);
        });
        node.files.forEach(file => {
            containerEl.appendChild(createFileItemEl(file));
        });
    }
}

// Helper to create single file DOM item
function createFileItemEl(file) {
    const ext = file.key.split('.').pop().toLowerCase();
    const displayName = file.name || file.key.split('/').pop() || file.key;
    const isSelected = selectedFilesMap.has(file.key);

    const item = document.createElement('div');
    item.className = `file-item ${isSelected ? 'selected' : ''}`;
    item.setAttribute('data-key', file.key);
    item.innerHTML = `
        <div class="file-info">
            <input type="checkbox" class="file-checkbox" data-key="${file.key}" ${isSelected ? 'checked' : ''} style="width: 15px; height: 15px; accent-color: var(--accent-blue);">
            <span class="file-badge badge-${ext}">${ext}</span>
            <div>
                <div class="file-name">${displayName}</div>
                <div class="file-meta">${formatBytes(file.size_bytes)} &bull; ${file.key}</div>
            </div>
        </div>
        <button class="btn-secondary-sm select-btn">${isSelected ? 'Deselect' : 'Select'}</button>
    `;

    const cb = item.querySelector('.file-checkbox');
    cb.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleFileSelection(file, cb.checked);
        item.classList.toggle('selected', cb.checked);
        item.querySelector('.select-btn').textContent = cb.checked ? 'Deselect' : 'Select';
    });

    item.addEventListener('click', (e) => {
        if (e.target.classList.contains('file-checkbox')) return;
        const newState = !selectedFilesMap.has(file.key);
        toggleFileSelection(file, newState);
        cb.checked = newState;
        item.classList.toggle('selected', newState);
        item.querySelector('.select-btn').textContent = newState ? 'Deselect' : 'Select';
    });

    return item;
}

// Render Batch Selection grouped by Folder
function renderAsyncBatchSelector() {
    const asyncListEl = document.getElementById('async-file-selector');
    if (!asyncListEl) return;
    asyncListEl.innerHTML = '';

    const query = asyncSearchQuery.trim().toLowerCase();
    const filteredFiles = query
        ? availableFiles.filter(f => f.key.toLowerCase().includes(query))
        : availableFiles;

    if (filteredFiles.length === 0) {
        asyncListEl.innerHTML = '<div class="loading-spinner">No matching files for batch selection.</div>';
        return;
    }

    // Group files by immediate parent folder
    const folderGroups = {};
    filteredFiles.forEach(file => {
        const parts = file.key.split('/');
        const folder = parts.length > 1 ? parts.slice(0, -1).join('/') : 'Root';
        if (!folderGroups[folder]) folderGroups[folder] = [];
        folderGroups[folder].push(file);
    });

    Object.entries(folderGroups).forEach(([folderName, files], groupIdx) => {
        const groupEl = document.createElement('div');
        groupEl.className = 'folder-node';
        groupEl.style.marginBottom = '8px';

        const allChecked = files.every(f => selectedFilesMap.has(f.key));

        // Folder Batch Header with Master Checkbox
        const headerEl = document.createElement('div');
        headerEl.className = 'folder-header';
        headerEl.style.padding = '8px 12px';
        headerEl.innerHTML = `
            <div class="folder-info">
                <input type="checkbox" class="folder-master-checkbox" ${allChecked ? 'checked' : ''} style="width: 16px; height: 16px; accent-color: var(--accent-blue);">
                <span class="folder-icon">📁</span>
                <span class="folder-title">${folderName}</span>
                <span class="folder-meta">(${files.length} files)</span>
            </div>
            <button class="btn-text-sm toggle-group-collapse">▼</button>
        `;

        const childrenEl = document.createElement('div');
        childrenEl.className = 'folder-children';

        const masterCheckbox = headerEl.querySelector('.folder-master-checkbox');
        masterCheckbox.addEventListener('click', (e) => {
            e.stopPropagation();
            files.forEach(f => toggleFileSelection(f, masterCheckbox.checked, false));
            updateSelectionUI();
            renderS3Catalog();
            const childCheckboxes = childrenEl.querySelectorAll('.batch-checkbox');
            childCheckboxes.forEach(cb => cb.checked = masterCheckbox.checked);
        });

        headerEl.addEventListener('click', (e) => {
            if (e.target.type === 'checkbox') return;
            const btn = headerEl.querySelector('.toggle-group-collapse');
            const isCollapsed = childrenEl.classList.toggle('collapsed');
            btn.textContent = isCollapsed ? '▶' : '▼';
        });

        files.forEach((file, idx) => {
            const ext = file.key.split('.').pop().toLowerCase();
            const fileName = file.key.split('/').pop();
            const isChecked = selectedFilesMap.has(file.key);

            const batchItem = document.createElement('div');
            batchItem.className = 'batch-file-item';
            batchItem.innerHTML = `
                <div class="file-info">
                    <input type="checkbox" class="batch-checkbox" value="${file.key}" ${isChecked ? 'checked' : ''} style="width: 16px; height: 16px; accent-color: var(--accent-blue);">
                    <div>
                        <div class="file-name">${fileName}</div>
                        <div class="file-meta">${formatBytes(file.size_bytes)} &bull; ${file.key}</div>
                    </div>
                </div>
                <span class="file-badge badge-${ext}">${ext}</span>
            `;

            const cb = batchItem.querySelector('.batch-checkbox');
            cb.addEventListener('change', () => {
                toggleFileSelection(file, cb.checked);
                renderS3Catalog();
                const isAllSelected = files.every(f => selectedFilesMap.has(f.key));
                masterCheckbox.checked = isAllSelected;
            });

            childrenEl.appendChild(batchItem);
        });

        groupEl.appendChild(headerEl);
        groupEl.appendChild(childrenEl);
        asyncListEl.appendChild(groupEl);
    });
}

// 4. Multi-File and Single Stream Downloader
function initDownloadForm() {
    const form = document.getElementById('download-form');
    const btnZipInstant = document.getElementById('btn-download-zip-instant');
    const resultPanel = document.getElementById('download-stream-result');
    const summaryDetails = document.getElementById('download-summary-details');
    const directLink = document.getElementById('direct-download-link');
    const resultHeaderTitle = document.getElementById('result-header-title');
    const btnDownload = document.getElementById('btn-start-download');

    // 1. Instant Multi-File ZIP Download Handler
    btnZipInstant?.addEventListener('click', async () => {
        const selectedKeys = Array.from(selectedFilesMap.keys());
        if (selectedKeys.length === 0) {
            alert('Please select at least one file or folder to download.');
            return;
        }

        const userId = document.getElementById('user-id').value;
        const userEmail = document.getElementById('user-email').value;
        const userRole = document.getElementById('user-role').value;

        btnZipInstant.disabled = true;
        btnZipInstant.innerHTML = `<span class="btn-icon">⏳</span> Packaging & Watermarking ZIP...`;

        try {
            const resp = await fetch('/api/download/zip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    s3_keys: selectedKeys,
                    user_id: userId,
                    user_email: userEmail,
                    user_role: userRole
                })
            });

            if (!resp.ok) {
                const errData = await resp.json();
                throw new Error(errData.detail || 'ZIP package generation failed');
            }

            const blob = await resp.blob();
            const objectUrl = URL.createObjectURL(blob);
            const zipName = `s3_watermarked_package_${selectedKeys.length}_files.zip`;

            resultPanel.classList.remove('hidden');
            if (resultHeaderTitle) resultHeaderTitle.textContent = 'Multi-File ZIP Package Generated';
            summaryDetails.textContent = 
`[ZIP PACKAGE DOWNLOAD COMPLETE]
• Packaged Files:    ${selectedKeys.length} assets
• Total Memory Size: ${formatBytes(blob.size)}
• Downloader:        ${userId} (${userEmail})
• Watermark Type:    ${resp.headers.get('X-Watermark-Status') || 'See server configuration'}
• Audit Trail:       Logged ${selectedKeys.length} records in PostgreSQL
• Status:            100% Validated & Delivered`;

            directLink.href = objectUrl;
            directLink.download = zipName;

            // Auto-trigger download
            const autoLink = document.createElement('a');
            autoLink.href = objectUrl;
            autoLink.download = zipName;
            document.body.appendChild(autoLink);
            autoLink.click();
            document.body.removeChild(autoLink);

            loadAuditLogs();
        } catch (err) {
            alert('ZIP Download Error: ' + err.message);
        } finally {
            btnZipInstant.disabled = false;
            updateSelectionUI();
        }
    });

    // 2. Stream Single File Submit Handler
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const selectedKeys = Array.from(selectedFilesMap.keys());
        if (selectedKeys.length === 0) {
            alert('Please select an S3 file first.');
            return;
        }

        // If multiple files selected, redirect to ZIP download
        if (selectedKeys.length > 1) {
            btnZipInstant.click();
            return;
        }

        const s3Key = selectedKeys[0];
        const userId = document.getElementById('user-id').value;
        const userEmail = document.getElementById('user-email').value;
        const userRole = document.getElementById('user-role').value;

        btnDownload.disabled = true;
        btnDownload.innerHTML = `<span class="btn-icon">⏳</span> Streaming & Watermarking...`;

        try {
            const queryParams = new URLSearchParams({
                s3_key: s3Key,
                user_id: userId,
                user_email: userEmail,
                user_role: userRole
            });

            const downloadUrl = `/api/download?${queryParams.toString()}`;
            const response = await fetch(downloadUrl);

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Download stream failed');
            }

            const downloadId = response.headers.get('X-Watermark-Download-ID') || 'N/A';
            const watermarkStatus = response.headers.get('X-Watermark-Status') || 'Injected';
            const pixelDistortion = response.headers.get('X-Watermark-Pixel-Distortion') || 'Not measured';

            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);
            const filename = s3Key.split('/').pop();

            resultPanel.classList.remove('hidden');
            if (resultHeaderTitle) resultHeaderTitle.textContent = 'Single File Stream Completed';
            summaryDetails.textContent = 
`[STREAM COMPLETE]
• Target File:       ${filename}
• Downloader:        ${userId} (${userEmail})
• Download UUID:     ${downloadId}
• Stream Size:       ${formatBytes(blob.size)}
• Header Injection:  ${watermarkStatus}
• Pixel Alteration:  ${pixelDistortion}
• Database Registry: Logged in PostgreSQL`;

            directLink.href = objectUrl;
            directLink.download = filename;

            // Auto trigger browser download
            const autoLink = document.createElement('a');
            autoLink.href = objectUrl;
            autoLink.download = filename;
            document.body.appendChild(autoLink);
            autoLink.click();
            document.body.removeChild(autoLink);

            loadAuditLogs();
        } catch (err) {
            alert('Download Error: ' + err.message);
        } finally {
            btnDownload.disabled = false;
            updateSelectionUI();
        }
    });
}

// 5. Celery + Redis Async Batch Downloader
function initAsyncBatchQueue() {
    const btnDispatch = document.getElementById('btn-dispatch-celery');
    const btnSelectAll = document.getElementById('btn-select-all');
    const progressCard = document.getElementById('async-progress-card');
    const progressBar = document.getElementById('job-progress-bar');
    const progressText = document.getElementById('job-percent-text');
    const statusText = document.getElementById('job-status-text');
    const statusBadge = document.getElementById('job-status-badge');
    const jobUuid = document.getElementById('job-uuid');
    const jobOutputName = document.getElementById('job-output-name');
    const btnDownloadZip = document.getElementById('btn-download-async-zip');

    btnSelectAll?.addEventListener('click', () => {
        const checkboxes = document.querySelectorAll('.batch-checkbox');
        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
        checkboxes.forEach(cb => cb.checked = !allChecked);
        btnSelectAll.textContent = allChecked ? 'Select All' : 'Deselect All';
    });

    btnDispatch?.addEventListener('click', async () => {
        const selectedCheckboxes = document.querySelectorAll('.batch-checkbox:checked');
        const selectedKeys = Array.from(selectedCheckboxes).map(cb => cb.value);

        if (selectedKeys.length === 0) {
            alert('Please select at least one file for the Celery batch job.');
            return;
        }

        const userId = document.getElementById('async-user-id').value;
        const userEmail = document.getElementById('async-user-email').value;

        btnDispatch.disabled = true;
        btnDispatch.innerHTML = `<span class="btn-icon">⏳</span> Dispatching to Redis Queue...`;

        try {
            const resp = await fetch('/api/async/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    s3_keys: selectedKeys,
                    user_id: userId,
                    user_email: userEmail
                })
            });

            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail || 'Failed to dispatch Celery job');

            const jobId = data.job_id;
            progressCard.classList.remove('hidden');
            jobUuid.textContent = jobId;
            btnDownloadZip.classList.add('hidden');
            progressBar.style.width = '10%';
            progressText.textContent = '10%';
            statusBadge.textContent = 'QUEUED';
            statusBadge.style.background = 'var(--accent-purple)';
            statusText.textContent = 'Queued in Redis message broker...';

            // Start Polling Redis & PostgreSQL for progress
            if (pollingInterval) clearInterval(pollingInterval);
            pollingInterval = setInterval(async () => {
                try {
                    const pollRes = await fetch(`/api/async/job/${jobId}`);
                    const pollData = await pollRes.json();
                    const job = pollData.job;

                    if (job) {
                        const pct = job.progress_pct || 15;
                        progressBar.style.width = `${pct}%`;
                        progressText.textContent = `${pct}%`;

                        if (job.status === 'PROCESSING') {
                            statusBadge.textContent = 'PROCESSING';
                            statusBadge.style.background = 'var(--accent-blue)';
                            statusText.textContent = `Streaming ${job.total_files} assets through watermark engine...`;
                        } else if (job.status === 'COMPLETED') {
                            clearInterval(pollingInterval);
                            progressBar.style.width = '100%';
                            progressText.textContent = '100%';
                            statusBadge.textContent = 'COMPLETED';
                            statusBadge.style.background = 'var(--accent-emerald)';
                            statusText.textContent = `All ${job.total_files} files watermarked & packaged in ZIP.`;
                            jobOutputName.textContent = `${job.output_filename} (${formatBytes(job.file_size_bytes)})`;

                            btnDownloadZip.classList.remove('hidden');
                            btnDownloadZip.href = `/api/async/package/${jobId}`;
                            btnDownloadZip.download = job.output_filename;

                            loadAuditLogs();
                        } else if (job.status === 'FAILED') {
                            clearInterval(pollingInterval);
                            statusBadge.textContent = 'FAILED';
                            statusBadge.style.background = 'var(--accent-rose)';
                            statusText.textContent = `Job error: ${job.error_message}`;
                        }
                    }
                } catch (pollErr) {
                    console.error('Polling error:', pollErr);
                }
            }, 1000);

        } catch (err) {
            alert('Dispatch Failed: ' + err.message);
        } finally {
            btnDispatch.disabled = false;
            btnDispatch.innerHTML = `<span class="btn-icon">⚡</span> Dispatch Celery Background Job`;
        }
    });
}

// 6. Forensic Dropzone & Verification
function initForensicDropzone() {
    const dropzone = document.getElementById('forensic-dropzone');
    const fileInput = document.getElementById('forensic-file-input');

    ['dragenter', 'dragover'].forEach(name => {
        dropzone.addEventListener(name, (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(name => {
        dropzone.addEventListener(name, (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            runForensicInspection(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            runForensicInspection(e.target.files[0]);
        }
    });
}

async function runForensicInspection(file) {
    const reportCard = document.getElementById('forensic-report-card');
    const verdictTitle = document.getElementById('report-verdict-title');
    const verdictBadge = document.getElementById('report-verdict-badge');
    const fileNameEl = document.getElementById('report-file-name');
    const repUid = document.getElementById('rep-uid');
    const repEmail = document.getElementById('rep-email');
    const repDid = document.getElementById('rep-did');
    const repKey = document.getElementById('rep-key');
    const repTs = document.getElementById('rep-ts');
    const repCrypto = document.getElementById('rep-crypto-status');
    const repRawJson = document.getElementById('rep-raw-json');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/forensic/verify', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        reportCard.classList.remove('hidden');
        fileNameEl.textContent = `${data.filename_analyzed || file.name} (${formatBytes(data.file_size_bytes || file.size)})`;

        if (!data.watermark_found) {
            verdictBadge.textContent = 'NO WATERMARK DETECTED';
            verdictBadge.style.background = 'var(--accent-rose)';
            verdictTitle.textContent = 'Untracked File / No Enterprise Header';
            repUid.textContent = 'None';
            repEmail.textContent = 'None';
            repDid.textContent = 'None';
            repKey.textContent = 'None';
            repTs.textContent = 'None';
            repCrypto.textContent = 'Not Applicable';
            repCrypto.className = 'item-value';
            repRawJson.textContent = JSON.stringify(data, null, 2);
            return;
        }

        const payload = data.decoded_payload || {};
        const audit = data.forensic_audit_trail || {};

        if (data.identity_conflict) {
            verdictBadge.textContent = 'IDENTITY CONFLICT';
            verdictBadge.style.background = 'var(--accent-amber)';
            verdictTitle.textContent = 'Metadata and coefficient IDs disagree';
            repCrypto.textContent = 'Review both authenticated IDs';
            repCrypto.className = 'item-value';
        } else if (data.signature_valid) {
            verdictBadge.textContent = 'AUTHENTICATED DOWNLOAD ID';
            verdictBadge.style.background = 'var(--accent-emerald)';
            verdictTitle.textContent = 'Download watermark verified';
            repCrypto.textContent = 'Valid HMAC-SHA256 Signature';
            repCrypto.className = 'item-value valid';
        } else {
            verdictBadge.textContent = 'CRYPTOGRAPHIC TAMPER DETECTED';
            verdictBadge.style.background = 'var(--accent-rose)';
            verdictTitle.textContent = 'Watermark Tampered or Forged';
            repCrypto.textContent = 'Invalid Cryptographic Signature';
            repCrypto.className = 'item-value';
            repCrypto.style.color = 'var(--accent-rose)';
        }

        repUid.textContent = payload.uid || audit.user_id || 'N/A';
        repEmail.textContent = payload.uem || audit.user_email || 'N/A';
        repDid.textContent = payload.did || 'N/A';
        repKey.textContent = payload.key || audit.s3_key || 'N/A';
        repTs.textContent = payload.ts ? new Date(payload.ts * 1000).toUTCString() : (audit.iso_timestamp || 'N/A');

        repRawJson.textContent = JSON.stringify({
            analysis_verdict: data.verification_status,
            signal_watermark: data.signal_watermark,
            identity_conflict: data.identity_conflict,
            metadata_download_id: data.metadata_download_id,
            embedded_token: data.embedded_token,
            decoded_metadata: payload,
            database_audit_record: audit
        }, null, 2);

    } catch (err) {
        alert('Forensic Inspection Failed: ' + err.message);
    }
}

// 7. Load Forensic Audit Registry from PostgreSQL
async function loadAuditLogs() {
    const tbody = document.getElementById('audit-table-body');
    const engineLabel = document.getElementById('audit-db-engine-label');

    try {
        const res = await fetch('/api/audit-logs?limit=30');
        const data = await res.json();

        if (engineLabel && data.database_engine) {
            engineLabel.textContent = `Database Engine: ${data.database_engine}`;
        }

        tbody.innerHTML = '';
        if (!data.logs || data.logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No download records in audit registry yet.</td></tr>';
            return;
        }

        data.logs.forEach(log => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${log.iso_timestamp ? log.iso_timestamp.replace('T', ' ').substring(0, 19) : 'N/A'}</td>
                <td style="font-weight: 600; color: #60a5fa">${log.user_id}</td>
                <td>${log.user_email}</td>
                <td style="font-family: var(--font-mono); font-size: 0.8rem">${log.s3_key}</td>
                <td style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-dim)">${log.download_id.substring(0, 8)}...</td>
                <td>${log.client_ip}</td>
                <td><span class="status-badge-delivered">${log.status}</span></td>
            `;
            tbody.appendChild(tr);
        });

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell" style="color: var(--accent-rose)">Failed to load audit registry.</td></tr>';
    }
}

// Helper: Format Bytes
function formatBytes(bytes, decimals = 1) {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

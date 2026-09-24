// Display adapters preserve missing values; they never manufacture operational data.
export const unavailable = 'Unavailable';
export const number = value => value == null ? '—' : Number(value).toLocaleString();
export function bytes(value) {
  if (value == null) return '—';
  if (value === 0) return '0 B';
  const unit = Math.min(3, Math.floor(Math.log(value) / Math.log(1024)));
  return `${(value / 1024 ** unit).toFixed(unit ? 1 : 0)} ${['B', 'KiB', 'MiB', 'GiB'][unit]}`;
}
export function tags(values) {
  if (!Array.isArray(values)) return [];
  return values.map(v => typeof v === 'string' ? v : v?.tag || v?.label || v?.name).filter(Boolean);
}
export const modality = value => value === 'csv' ? 'tabular' : value;
export const backendModality = value => value === 'tabular' ? 'csv' : value;
export function matchLabel(info) {
  const sources = info?.match_sources || [];
  if (sources.includes('keyword') && sources.includes('vector')) return 'Keyword + semantic match';
  if (sources.includes('keyword')) return 'Keyword match';
  if (sources.includes('vector')) return 'Semantic match';
  return '';
}
export function fileView(file) {
  return {
    ...file,
    id: file.file_id, name: file.title || file.file_name, filename: file.file_name,
    modality: modality(file.file_type), content_type: modality(file.file_type),
    created_at: file.ingested_at, fileSize: bytes(file.file_size ?? file.technical?.file_size),
    source: file.dataset_name, sourceUri: file.source_uri || '',
    checksum: file.technical?.checksum,
    aiDescription: file.description || file.ai_enrichment?.content_summary,
    canonicalCaption: file.caption || file.ai_enrichment?.caption,
    ocrText: file.ai_enrichment?.ocr_text, tags: tags(file.tags),
    // RRF is a ranking score, not a confidence probability.
    score: null, scoreLabel: matchLabel(file.score_info) || '—',
  };
}
export function connectorView(connector) {
  return {
    ...connector, rawStatus: connector.status,
    status: connector.archived_at ? 'Archived' : connector.status.charAt(0).toUpperCase() + connector.status.slice(1),
    endpoint_or_path: connector.bucket ? `s3://${connector.bucket}/${connector.s3_prefix || ''}` : connector.mount_path,
    syncMode: 'Manual scans', authType: connector.source_type === 'S3' ? connector.s3_auth_mode || 'Vault managed' : 'Vault / mounted access',
    discoveredFiles: null, region: null,
  };
}
export function runView(run, connectors = []) {
  const connector = connectors.find(c => c.id === run.connector_id);
  return {
    ...run, name: connector?.name || `Run ${run.id.slice(0, 8)}`,
    bucket: connector?.endpoint_or_path || run.connector_id,
    currentThroughput: run.mib_per_second == null ? '—' : `${run.mib_per_second.toFixed(2)} MiB/s (run average)`,
    dataVolume: bytes(run.bytes_processed), validatedCount: run.succeeded_count,
    discoveredCount: run.enumerated_count,
    progress: run.enumeration_completed_at && run.enumerated_count > 0 ? Math.min(100, Math.round(run.terminal_count / run.enumerated_count * 100)) : null,
    prefix: run.source_type === 'S3' ? connector?.s3_prefix || '(bucket root)' : connector?.mount_path || 'Source folder not recorded',
    remainingItems: Math.max(0, (run.enumerated_count ?? 0) - (run.terminal_count ?? 0)),
  };
}
export function auditView(event) {
  return {...event, id: event.event_id, timestamp: event.occurred_at, user: event.actor,
    role: event.user_role, target: event.entity_id, complianceCode: null};
}

export function pipelineGroups(task) {
  return [
    ['Source preprocessing', ['preprocessing'], 'Source validation and preparation'],
    ['Content extraction', ['ocr_extraction'], 'OCR and extracted text'],
    ['Tags captions and safety', ['tagging','captioning','quality_safety'], 'Generated labels and safety checks'],
    ['Metadata and persistence', ['metadata_fusion','confidence_validation','persistence'], 'Persisted metadata feeds indexing'],
  ].map(([name,keys,desc],i) => {
    const results = keys.map(key => task?.stage_results?.[key]?.status);
    const failed = results.some(status => ['failed','error'].includes(status));
    const complete = results.every(status => ['completed','success','skipped'].includes(status));
    const active = task?.status === 'in_progress' && keys.includes(task.current_stage);
    return {id:String(i),num:`STEP 0${i+1}`,name,desc,
      status:failed ? 'failed' : complete ? 'completed' : active ? 'active' : task ? 'pending' : 'unavailable',
      count:task ? `${results.filter(s => ['completed','success','skipped'].includes(s)).length}/${keys.length} stages` : '—'};
  });
}

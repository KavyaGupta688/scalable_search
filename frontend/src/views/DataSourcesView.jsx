import React, { useState } from 'react';
import { api } from '../services/api';
import { S3Icon, PlusIcon, RefreshIcon, CloseIcon, ShieldIcon } from '../components/Icons';

export const DataSourcesView = ({ onShowToast }) => {
  const [sources, setSources] = useState(api.getDataSources());
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSource, setSelectedSource] = useState(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Form State
  const [newBucketName, setNewBucketName] = useState('');
  const [newDisplayName, setNewDisplayName] = useState('');
  const [newRegion, setNewRegion] = useState('ap-northeast-2 (Seoul)');
  const [authType, setAuthType] = useState('IAM Role Delegation');
  const [iamRoleArn, setIamRoleArn] = useState('arn:aws:iam::123456789012:role/SamsungPrismS3IngestRole');
  const [accessKeyId, setAccessKeyId] = useState('');
  const [secretAccessKey, setSecretAccessKey] = useState('');
  const [syncInterval, setSyncInterval] = useState('Continuous EventStream');
  const [prefix, setPrefix] = useState('');

  const filteredSources = sources.filter(
    (s) =>
      s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.endpoint.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.region.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.syncStatus.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleAddSource = (e) => {
    e.preventDefault();
    if (!newBucketName) return;

    const added = api.addDataSource({
      name: newDisplayName || `S3 / ${newBucketName}`,
      bucketName: newBucketName,
      region: newRegion,
      authType,
      iamRoleArn: authType === 'IAM Role Delegation' ? iamRoleArn : `IAM User (${accessKeyId || 'AKIA...'})`,
      syncInterval,
      prefix
    });

    setSources(api.getDataSources());
    setIsAddModalOpen(false);

    // Reset Form
    setNewBucketName('');
    setNewDisplayName('');
    setPrefix('');
    setAccessKeyId('');
    setSecretAccessKey('');

    onShowToast(`Connected S3 bucket 's3://${added.bucketName}/' via ${authType} with ${syncInterval}`, 'success');
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-[10px] font-bold font-mono tracking-widest text-prism-brandText uppercase">
            Object Storage Connectors
          </span>
          <h1 className="text-xl font-bold text-prism-textPrimary tracking-tight">Amazon S3 Buckets</h1>
          <p className="text-xs text-prism-textMuted mt-0.5">
            Connected S3 buckets storing raw multimodal binaries for continuous AI ingestion.
          </p>
        </div>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-prism-brand hover:bg-prism-brandHover text-white text-xs font-semibold rounded-sm transition-colors self-start shadow-sm"
        >
          <PlusIcon className="w-3.5 h-3.5" />
          <span>Connect S3 Bucket</span>
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-prism-surface border border-prism-border p-3.5 rounded-sm">
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search S3 buckets by name, URI, region, or sync mode..."
          className="bg-prism-input border border-prism-border focus:border-prism-brand rounded-sm px-3 h-8 text-xs text-prism-textPrimary outline-none w-full max-w-sm"
        />
        <div className="text-xs text-prism-textMuted font-mono">
          Connected S3 Buckets: <strong className="text-prism-textPrimary">{sources.length}</strong> ·
          Total Discovered: <strong className="text-prism-textPrimary">{sources.reduce((acc, s) => acc + s.discoveredFiles, 0).toLocaleString()} objects</strong>
        </div>
      </div>

      {/* Buckets Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredSources.map((src) => (
          <div
            key={src.id}
            onClick={() => setSelectedSource(src)}
            className="bg-prism-surface border border-prism-border hover:border-prism-borderStrong p-4 rounded-sm flex flex-col gap-3 cursor-pointer transition-colors"
          >
            <div className="flex items-start justify-between">
              <div className="flex flex-col min-w-0 pr-2">
                <span className="text-xs font-bold text-prism-textPrimary truncate">{src.name}</span>
                <span className="inline-flex items-center gap-1 text-[11px] text-prism-textMuted mt-0.5">
                  <S3Icon className="w-3.5 h-3.5 text-prism-brandText shrink-0" />
                  Amazon S3 · {src.region}
                </span>
              </div>
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-xs shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                {src.status}
              </span>
            </div>

            <div className="font-mono text-[11px] text-prism-brandText bg-prism-elevated px-2.5 py-1.5 rounded-xs truncate border border-prism-borderSubtle" title={src.endpoint}>
              {src.endpoint}
            </div>

            <div className="grid grid-cols-2 gap-2 bg-prism-elevated p-2.5 rounded-xs border border-prism-borderSubtle">
              <div className="flex flex-col">
                <span className="text-[10px] uppercase text-prism-textMuted font-medium">Discovered Objects</span>
                <span className="text-xs font-bold text-prism-textPrimary font-mono">
                  {src.discoveredFiles.toLocaleString()}
                </span>
              </div>
              <div className="flex flex-col">
                <span className="text-[10px] uppercase text-prism-textMuted font-medium">Storage Volume</span>
                <span className="text-xs font-bold text-prism-textPrimary font-mono">
                  {src.totalBytes}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between text-[11px] text-prism-textMuted border-t border-prism-borderSubtle pt-2 mt-auto">
              <span className="inline-flex items-center gap-1 text-blue-300">
                <RefreshIcon className="w-3 h-3 text-prism-brandText shrink-0" />
                <span className="truncate max-w-[170px]">{src.syncStatus || src.syncInterval}</span>
              </span>
              <span className="font-mono text-[10px] text-prism-textSecondary truncate max-w-[140px]" title={src.authType}>
                {src.authType}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* S3 Detail Drawer */}
      {selectedSource && (
        <div
          className="fixed inset-0 z-50 bg-black/75 flex justify-end backdrop-enter"
          onClick={() => setSelectedSource(null)}
        >
          <div
            className="w-full max-w-lg bg-prism-surface border-l border-prism-borderStrong h-full p-6 flex flex-col gap-5 overflow-y-auto drawer-enter"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-prism-border pb-3">
              <div>
                <h3 className="text-sm font-bold text-prism-textPrimary">{selectedSource.name}</h3>
                <span className="text-xs text-prism-textMuted font-mono">Amazon S3: {selectedSource.bucketName}</span>
              </div>
              <button
                onClick={() => setSelectedSource(null)}
                className="p-1 text-prism-textMuted hover:text-prism-textPrimary"
              >
                <CloseIcon className="w-4 h-4" />
              </button>
            </div>

            <div className="flex flex-col gap-3">
              <span className="text-[11px] font-bold text-prism-textMuted uppercase tracking-wider font-mono">
                Bucket Configuration
              </span>
              <div className="grid grid-cols-[130px_1fr] gap-2.5 text-xs bg-prism-elevated p-3.5 rounded-sm border border-prism-borderSubtle">
                <span className="text-prism-textMuted">Status:</span>
                <span className="text-emerald-400 font-semibold">Connected (Active)</span>
                <span className="text-prism-textMuted">S3 URI:</span>
                <span className="font-mono text-prism-brandText break-all">{selectedSource.endpoint}</span>
                <span className="text-prism-textMuted">AWS Region:</span>
                <span className="text-prism-textPrimary">{selectedSource.region}</span>
                <span className="text-prism-textMuted">Discovered:</span>
                <span className="font-mono text-prism-textPrimary">{selectedSource.discoveredFiles.toLocaleString()} files</span>
                <span className="text-prism-textMuted">Storage Volume:</span>
                <span className="font-mono text-prism-textPrimary">{selectedSource.totalBytes}</span>
                <span className="text-prism-textMuted">Ingest Schedule:</span>
                <span className="text-blue-300 font-medium">{selectedSource.syncInterval || selectedSource.syncStatus}</span>
                <span className="text-prism-textMuted">Authentication:</span>
                <span className="text-prism-textPrimary">{selectedSource.authType}</span>
                <span className="text-prism-textMuted">IAM Role / User:</span>
                <span className="font-mono text-[11px] text-prism-textSecondary break-all">{selectedSource.iamRoleArn || 'Role: SamsungPrismS3IngestRole'}</span>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-[11px] font-bold text-prism-textMuted uppercase tracking-wider font-mono">
                Ingestion Telemetry
              </span>
              <p className="text-xs text-prism-textSecondary leading-relaxed bg-prism-elevated p-3 rounded-sm border border-prism-borderSubtle">
                S3 object notifications are streamed via {selectedSource.syncInterval || 'Continuous EventStream'}.
                New binary uploads are validated, checksummed, and enriched with AI tags and 1536-d vectors in real time.
              </p>
            </div>

            <div className="mt-auto flex items-center justify-end gap-2.5 border-t border-prism-border pt-4">
              <button
                onClick={() => onShowToast('S3 Bucket connection verified: Read/List 200 OK (12ms latency)', 'success')}
                className="px-3 py-1.5 bg-prism-elevated hover:bg-prism-hover border border-prism-border rounded-sm text-xs font-semibold text-prism-textPrimary transition-colors"
              >
                Test S3 Access
              </button>
              <button
                onClick={() => {
                  onShowToast(`Triggered S3 crawl for ${selectedSource.bucketName}`, 'info');
                  setSelectedSource(null);
                }}
                className="px-3.5 py-1.5 bg-prism-brand hover:bg-prism-brandHover rounded-sm text-xs font-semibold text-white transition-colors"
              >
                Trigger S3 Crawl
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add S3 Modal with IAM User / Role and Ingest Options */}
      {isAddModalOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4 backdrop-enter"
          onClick={() => setIsAddModalOpen(false)}
        >
          <div
            className="w-full max-w-lg bg-prism-surface border border-prism-borderStrong rounded-sm p-6 flex flex-col gap-4 max-h-[90vh] overflow-y-auto modal-enter"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-prism-border pb-3">
              <div className="flex items-center gap-2">
                <S3Icon className="w-5 h-5 text-prism-brandText" />
                <h3 className="text-sm font-bold text-prism-textPrimary">Connect Amazon S3 Bucket</h3>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="p-1 text-prism-textMuted hover:text-prism-textPrimary"
              >
                <CloseIcon className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleAddSource} className="flex flex-col gap-4">
              {/* S3 Bucket Name */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-semibold text-prism-textSecondary">S3 Bucket Name *</label>
                <input
                  type="text"
                  required
                  value={newBucketName}
                  onChange={(e) => setNewBucketName(e.target.value)}
                  placeholder="e.g. samsung-inspection-dataset"
                  className="h-9 px-3 bg-prism-input border border-prism-border focus:border-prism-brand rounded-sm text-xs text-prism-textPrimary font-mono outline-none"
                />
                <span className="text-[10px] text-prism-textMuted">Must be a valid Amazon S3 bucket name.</span>
              </div>

              {/* Display Name & Prefix */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-semibold text-prism-textSecondary">Display Name</label>
                  <input
                    type="text"
                    value={newDisplayName}
                    onChange={(e) => setNewDisplayName(e.target.value)}
                    placeholder="e.g. Production Line 02 S3"
                    className="h-9 px-3 bg-prism-input border border-prism-border focus:border-prism-brand rounded-sm text-xs text-prism-textPrimary outline-none"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-semibold text-prism-textSecondary">Optional Prefix / Folder</label>
                  <input
                    type="text"
                    value={prefix}
                    onChange={(e) => setPrefix(e.target.value)}
                    placeholder="e.g. raw_captures/2026/"
                    className="h-9 px-3 bg-prism-input border border-prism-border focus:border-prism-brand rounded-sm text-xs text-prism-textPrimary font-mono outline-none"
                  />
                </div>
              </div>

              {/* AWS Region */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-semibold text-prism-textSecondary">AWS Region</label>
                <select
                  value={newRegion}
                  onChange={(e) => setNewRegion(e.target.value)}
                  className="h-9 px-3 bg-prism-input border border-prism-border focus:border-prism-brand rounded-sm text-xs text-prism-textPrimary outline-none"
                >
                  <option value="ap-northeast-2 (Seoul)">ap-northeast-2 (Seoul)</option>
                  <option value="ap-northeast-1 (Tokyo)">ap-northeast-1 (Tokyo)</option>
                  <option value="us-east-1 (N. Virginia)">us-east-1 (N. Virginia)</option>
                  <option value="us-west-2 (Oregon)">us-west-2 (Oregon)</option>
                  <option value="eu-central-1 (Frankfurt)">eu-central-1 (Frankfurt)</option>
                </select>
              </div>

              {/* Ingestion & Sync Schedule Options */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-semibold text-prism-textSecondary">Ingestion & Sync Schedule *</label>
                <select
                  value={syncInterval}
                  onChange={(e) => setSyncInterval(e.target.value)}
                  className="h-9 px-3 bg-prism-input border border-prism-border focus:border-prism-brand rounded-sm text-xs text-prism-textPrimary outline-none"
                >
                  <option value="Continuous EventStream">Continuous EventStream (S3 EventBridge + SQS)</option>
                  <option value="Real-time Stream">Real-time Stream (Kinesis / S3 Object Lambda)</option>
                  <option value="Hourly Ingest">Hourly Ingest (Batch Delta)</option>
                  <option value="Daily at 04:00 KST">Daily at 04:00 KST (Nightly Crawl)</option>
                  <option value="Pub/Sub Trigger">Pub/Sub Event Trigger</option>
                </select>
                <span className="text-[10px] text-prism-textMuted">Select how new S3 objects are triggered and ingested.</span>
              </div>

              {/* Authentication Type: IAM Role vs IAM User */}
              <div className="flex flex-col gap-2 bg-prism-elevated p-3.5 rounded-sm border border-prism-borderSubtle">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-prism-textPrimary flex items-center gap-1.5">
                    <ShieldIcon className="w-3.5 h-3.5 text-prism-brandText" />
                    AWS Authentication Method
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                  <label className={`flex items-center gap-2 p-2 rounded-xs border cursor-pointer select-none transition-colors ${
                    authType === 'IAM Role Delegation'
                      ? 'bg-prism-brandSubtle border-[#23426e] text-prism-brandText font-semibold'
                      : 'bg-prism-surface border-prism-border text-prism-textSecondary'
                  }`}>
                    <input
                      type="radio"
                      name="authType"
                      value="IAM Role Delegation"
                      checked={authType === 'IAM Role Delegation'}
                      onChange={(e) => setAuthType(e.target.value)}
                      className="accent-prism-brand"
                    />
                    <span>IAM Role ARN</span>
                  </label>

                  <label className={`flex items-center gap-2 p-2 rounded-xs border cursor-pointer select-none transition-colors ${
                    authType === 'IAM User Credentials'
                      ? 'bg-prism-brandSubtle border-[#23426e] text-prism-brandText font-semibold'
                      : 'bg-prism-surface border-prism-border text-prism-textSecondary'
                  }`}>
                    <input
                      type="radio"
                      name="authType"
                      value="IAM User Credentials"
                      checked={authType === 'IAM User Credentials'}
                      onChange={(e) => setAuthType(e.target.value)}
                      className="accent-prism-brand"
                    />
                    <span>IAM User (Keys)</span>
                  </label>
                </div>

                {/* Role ARN Field */}
                {authType === 'IAM Role Delegation' ? (
                  <div className="flex flex-col gap-1 mt-2">
                    <label className="text-[11px] font-semibold text-prism-textSecondary">IAM Role ARN *</label>
                    <input
                      type="text"
                      required
                      value={iamRoleArn}
                      onChange={(e) => setIamRoleArn(e.target.value)}
                      placeholder="arn:aws:iam::123456789012:role/SamsungPrismS3IngestRole"
                      className="h-8 px-2.5 bg-prism-input border border-prism-border focus:border-prism-brand rounded-sm text-xs text-prism-textPrimary font-mono outline-none"
                    />
                    <span className="text-[10px] text-prism-textMuted">Cross-account IAM role with s3:GetObject and s3:ListBucket permissions.</span>
                  </div>
                ) : (
                  <div className="flex flex-col gap-2 mt-2">
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] font-semibold text-prism-textSecondary">AWS Access Key ID *</label>
                      <input
                        type="text"
                        required
                        value={accessKeyId}
                        onChange={(e) => setAccessKeyId(e.target.value)}
                        placeholder="AKIAIOSFODNN7EXAMPLE"
                        className="h-8 px-2.5 bg-prism-input border border-prism-border focus:border-prism-brand rounded-sm text-xs text-prism-textPrimary font-mono outline-none"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] font-semibold text-prism-textSecondary">AWS Secret Access Key *</label>
                      <input
                        type="password"
                        required
                        value={secretAccessKey}
                        onChange={(e) => setSecretAccessKey(e.target.value)}
                        placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
                        className="h-8 px-2.5 bg-prism-input border border-prism-border focus:border-prism-brand rounded-sm text-xs text-prism-textPrimary font-mono outline-none"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-prism-border">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-3 py-1.5 text-xs text-prism-textMuted hover:text-prism-textPrimary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-prism-brand hover:bg-prism-brandHover text-white text-xs font-semibold rounded-sm transition-colors shadow-sm"
                >
                  Connect S3 Bucket
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

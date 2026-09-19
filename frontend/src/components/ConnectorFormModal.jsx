import { Presence } from './Motion';
import { DialogBackdrop } from './DialogBackdrop';
import React, { useState } from 'react';
import { createConnector } from '../services/adminApi';
import { CloseIcon, DatabaseIcon, NASIcon, ShieldIcon, SpinnerIcon, CheckCircleIcon, XCircleIcon } from './Icons';

/**
 * ConnectorFormModal — Modal form for adding and verifying S3-compatible and NAS data sources.
 * Includes IAM User Role options, Hourly Ingest, Continuous Event Stream, Real-time Stream settings.
 */
export const ConnectorFormModal = ({
  isOpen,
  onClose,
  onSuccess,
  showToast,
}) => {
  const [sourceType, setSourceType] = useState('s3'); // 's3' | 'nas_smb' | 'nas_nfs'
  const [name, setName] = useState('');

  // S3 fields
  const [endpointUrl, setEndpointUrl] = useState('');
  const [bucketName, setBucketName] = useState('');
  const [region, setRegion] = useState('ap-east-1');
  const [addressingStyle, setAddressingStyle] = useState('virtual-hosted');
  const [signatureVersion, setSignatureVersion] = useState('SigV4');
  const [authMethod, setAuthMethod] = useState('iam_role'); // 'iam_role' | 'access_key'
  const [iamRoleArn, setIamRoleArn] = useState('');
  const [accessKeyId, setAccessKeyId] = useState('');
  const [secretAccessKey, setSecretAccessKey] = useState('');

  // NAS fields
  const [sharePath, setSharePath] = useState('');
  const [nasUsername, setNasUsername] = useState('');
  const [nasPassword, setNasPassword] = useState('');
  const [prefix, setPrefix] = useState('');
  const [maxFiles, setMaxFiles] = useState(100);
  const [externalId, setExternalId] = useState('');
  const [kerberosPrincipal, setKerberosPrincipal] = useState('');

  // Ingest / Sync stream options
  const [syncMode, setSyncMode] = useState('manual'); // 'hourly' | 'continuous_event_stream' | 'realtime_stream' | 'daily'

  // States
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState(null); // null | { status: 'Verified'|'Failed', message: string }
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');



  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) {
      setError('Please provide a connector name.');
      return;
    }

    if (sourceType === 's3' && !bucketName.trim()) {
      setError('Bucket name is required for S3 connector.');
      return;
    }

    if ((sourceType === 'nas_smb' || sourceType === 'nas_nfs') && !sharePath.trim()) {
      setError('Share/mount path is required for NAS connector.');
      return;
    }

    if (!Number.isInteger(Number(maxFiles)) || Number(maxFiles) < 1) {setError('Maximum files must be a positive integer.'); return;}
    setIsSubmitting(true);

    const payload = {name, source_type:sourceType.toUpperCase()};
    if (sourceType === 's3') {
      payload.s3 = {
        endpoint_url: endpointUrl || `https://s3.${region}.amazonaws.com`, bucket:bucketName,
        auth_mode:authMethod === 'iam_role' ? 'aws_assume_role' : 'static_keys',
        addressing_style:addressingStyle === 'virtual-hosted' ? 'virtual' : 'path',
        signature_version:signatureVersion === 'SigV4' ? 's3v4' : 's3', prefix, max_objects:Number(maxFiles),
        ...(authMethod === 'iam_role' ? {role_arn:iamRoleArn, external_id:externalId || null} : {access_key:accessKeyId, secret_key:secretAccessKey}),
      };
    } else {
      const parts = nasUsername.split('\\');
      payload.nas = {protocol:sourceType === 'nas_smb' ? 'SMB' : 'NFS', mount_path:sharePath,
        username:sourceType === 'nas_smb' ? parts.at(-1) || null : null,
        domain:parts.length > 1 ? parts[0] : null, password:nasPassword || null, max_files:Number(maxFiles)};
    }

    try {
      const created = await createConnector(payload);
      showToast(`Connector '${name}' configured successfully`, 'success');
      if (onSuccess) onSuccess(created);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to create connector');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Presence>{isOpen && <DialogBackdrop onClose={onClose}>
      <div className="detail-dialog max-w-2xl flex flex-col dialog-surface connector-dialog" role="dialog" aria-modal="true" aria-label="Connect a Data Source" tabIndex={-1}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-nexus-border flex items-center justify-between bg-nexus-elevated">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-sm bg-nexus-brandSubtle border border-nexus-border flex items-center justify-center text-nexus-brandText">
              <DatabaseIcon className="w-3.5 h-3.5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-nexus-textPrimary">
                Connect a Data Source
              </h2>
              <p className="text-sm text-nexus-textMuted">
                Configure S3 bucket or NAS storage with automated ingestion
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog" className="p-1 text-nexus-textMuted hover:text-nexus-textPrimary rounded-sm transition-colors"
          >
            <CloseIcon className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Form Body */}
        <form onSubmit={handleSubmit} className="min-h-0 flex-1 overflow-y-auto p-6 flex flex-col gap-5 text-sm">
          {error && (
            <div className="p-2.5 rounded-xs bg-red-950/30 border border-red-800 text-nexus-danger text-sm">
              {error}
            </div>
          )}

          {/* 1. Source Type */}
          <div className="flex flex-col gap-2">
            <label className="font-semibold text-nexus-textSecondary">Storage Source Type</label>
            <div className="grid grid-cols-3 gap-2.5">
              {[
                { id: 's3', label: 'S3 / Object Store', icon: DatabaseIcon },
                { id: 'nas_smb', label: 'NAS (SMB)', icon: NASIcon },
                { id: 'nas_nfs', label: 'NAS (NFS)', icon: NASIcon },
              ].map((item) => {
                const Icon = item.icon;
                const active = sourceType === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setSourceType(item.id);
                      setTestResult(null);
                    }}
                    className={`flex items-center gap-2 p-3 rounded-sm border text-left transition-colors ${
                      active
                        ? 'bg-nexus-brandSubtle text-nexus-brandText border-nexus-border font-semibold'
                        : 'bg-nexus-input text-nexus-textSecondary border-nexus-border hover:border-nexus-borderStrong'
                    }`}
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    <span className="text-sm">{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 2. Common Name */}
          <div className="flex flex-col gap-1.5">
            <label className="font-semibold text-nexus-textSecondary" htmlFor="conn-name">
              Connector Display Name *
            </label>
            <input
              id="conn-name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., prod-fab-inspection-archive"
              className="h-9 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm text-nexus-textPrimary outline-none"
            />
          </div>

          {/* 3. S3 Specific Options */}
          {sourceType === 's3' && (
            <div className="flex flex-col gap-4 p-4 rounded-sm bg-nexus-elevated border border-nexus-borderSubtle">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div className="flex flex-col gap-1.5">
                  <label className="font-semibold text-nexus-textSecondary" htmlFor="s3-bucket">
                    Bucket Name *
                  </label>
                  <input
                    id="s3-bucket"
                    type="text"
                    required
                    value={bucketName}
                    onChange={(e) => setBucketName(e.target.value)}
                    placeholder="my-multimodal-bucket"
                    className="h-9 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm font-mono text-nexus-textPrimary outline-none"
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="font-semibold text-nexus-textSecondary" htmlFor="s3-region">
                    AWS / Cluster Region
                  </label>
                  <input
                    id="s3-region"
                    type="text"
                    value={region}
                    onChange={(e) => setRegion(e.target.value)}
                    placeholder="ap-east-1"
                    className="h-9 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm font-mono text-nexus-textPrimary outline-none"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="font-semibold text-nexus-textSecondary" htmlFor="s3-endpoint">
                  Custom Endpoint URL
                </label>
                <input
                  id="s3-endpoint"
                  type="text"
                  value={endpointUrl}
                  onChange={(e) => setEndpointUrl(e.target.value)}
                  placeholder="https://s3.amazonaws.com (leave blank for standard AWS S3)"
                  className="h-9 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm font-mono text-nexus-textPrimary outline-none"
                />
              </div>

              {/* Addressing & Signature */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
                <div className="flex flex-col gap-1.5">
                  <label className="font-semibold text-nexus-textSecondary">Addressing Style</label>
                  <div className="flex items-center gap-3 text-sm pt-1">
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="radio"
                        name="addrStyle"
                        checked={addressingStyle === 'virtual-hosted'}
                        onChange={() => setAddressingStyle('virtual-hosted')}
                        className="accent-nexus-brand"
                      />
                      <span>Virtual-hosted</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="radio"
                        name="addrStyle"
                        checked={addressingStyle === 'path'}
                        onChange={() => setAddressingStyle('path')}
                        className="accent-nexus-brand"
                      />
                      <span>Path-style</span>
                    </label>
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="font-semibold text-nexus-textSecondary">Signature Version</label>
                  <div className="flex items-center gap-3 text-sm pt-1">
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="radio"
                        name="sigVer"
                        checked={signatureVersion === 'SigV4'}
                        onChange={() => setSignatureVersion('SigV4')}
                        className="accent-nexus-brand"
                      />
                      <span>SigV4 (Recommended)</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="radio"
                        name="sigVer"
                        checked={signatureVersion === 'SigV2'}
                        onChange={() => setSignatureVersion('SigV2')}
                        className="accent-nexus-brand"
                      />
                      <span>SigV2</span>
                    </label>
                  </div>
                </div>
              </div>

              {/* S3 Auth: IAM Role vs Access Keys */}
              <div className="flex flex-col gap-2 pt-2 border-t border-nexus-borderSubtle">
                <label className="font-semibold text-nexus-textSecondary">Authentication & Authorization</label>
                <div className="flex items-center gap-4 text-sm">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="s3Auth"
                      checked={authMethod === 'iam_role'}
                      onChange={() => setAuthMethod('iam_role')}
                      className="accent-nexus-brand"
                    />
                    <span className="font-semibold text-nexus-brandText">IAM Role ARN (Recommended)</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="s3Auth"
                      checked={authMethod === 'access_key'}
                      onChange={() => setAuthMethod('access_key')}
                      className="accent-nexus-brand"
                    />
                    <span>Access Key & Secret</span>
                  </label>
                </div>

                {authMethod === 'iam_role' ? (
                  <div className="flex flex-col gap-1.5 pt-1">
                    <label className="text-sm text-nexus-textMuted" htmlFor="iam-role-arn">
                      Target IAM Role ARN (Cross-account or Task Role)
                    </label>
                    <input
                      id="iam-role-arn"
                      type="text"
                      value={iamRoleArn}
                      onChange={(e) => setIamRoleArn(e.target.value)}
                      placeholder="arn:aws:iam::123456789012:role/NexusS3IngestRole"
                      className="h-9 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm font-mono text-nexus-textPrimary outline-none"
                    />
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-sm text-nexus-textMuted" htmlFor="s3-key">
                        Access Key ID
                      </label>
                      <input
                        id="s3-key"
                        type="text"
                        value={accessKeyId}
                        onChange={(e) => setAccessKeyId(e.target.value)}
                        placeholder="AKIAIOSFODNN7EXAMPLE"
                        className="h-9 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm font-mono text-nexus-textPrimary outline-none"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-sm text-nexus-textMuted" htmlFor="s3-secret">
                        Secret Access Key
                      </label>
                      <input
                        id="s3-secret"
                        type="password"
                        value={secretAccessKey}
                        onChange={(e) => setSecretAccessKey(e.target.value)}
                        placeholder="••••••••••••••••••••••••"
                        className="h-9 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm font-mono text-nexus-textPrimary outline-none"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 4. NAS Specific Options */}
          {(sourceType === 'nas_smb' || sourceType === 'nas_nfs') && (
            <div className="flex flex-col gap-4 p-4 rounded-sm bg-nexus-elevated border border-nexus-borderSubtle">
              <div className="flex flex-col gap-1.5">
                <label className="font-semibold text-nexus-textSecondary" htmlFor="nas-share">
                  {sourceType === 'nas_smb' ? 'SMB Share Path *' : 'Mounted NFS Path *'}
                </label>
                <input
                  id="nas-share"
                  type="text"
                  required
                  value={sharePath}
                  onChange={(e) => setSharePath(e.target.value)}
                  placeholder={sourceType === 'nas_smb' ? '//nas-server.internal/shared-fab' : '/mnt/vendor-data'}
                  className="h-9 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm font-mono text-nexus-textPrimary outline-none"
                />
              </div>

              {sourceType === 'nas_smb' ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-sm text-nexus-textMuted" htmlFor="smb-user">
                      SMB Username / Domain
                    </label>
                    <input
                      id="smb-user"
                      type="text"
                      value={nasUsername}
                      onChange={(e) => setNasUsername(e.target.value)}
                      placeholder="DOMAIN\svc-ingest"
                      className="h-9 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm font-mono text-nexus-textPrimary outline-none"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-sm text-nexus-textMuted" htmlFor="smb-pass">
                      SMB Password
                    </label>
                    <input
                      id="smb-pass"
                      type="password"
                      value={nasPassword}
                      onChange={(e) => setNasPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="h-9 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm font-mono text-nexus-textPrimary outline-none"
                    />
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm text-nexus-textMuted" htmlFor="nfs-krb">
                    Kerberos Principal / Auth FLAVOR
                  </label>
                  <input
                    id="nfs-krb" disabled title="Configure NFS authentication on the host mount; it cannot be set here."
                    type="text"
                    value={kerberosPrincipal}
                    onChange={(e) => setKerberosPrincipal(e.target.value)}
                    placeholder="nfs/ingest@REALM.INTERNAL (or leave blank for sys auth)"
                    className="h-9 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm font-mono text-nexus-textPrimary outline-none"
                  />
                </div>
              )}
            </div>
          )}

          {/* 5. Ingestion Frequency & Stream Option */}
          <div className="flex flex-col gap-2">
            <label className="font-semibold text-nexus-textSecondary">
              Ingestion Schedule & Streaming Mode · Manual scans only
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { id: 'hourly', title: 'Hourly Ingest', sub: 'Batched delta crawl' },
                { id: 'continuous_event_stream', title: 'Event Stream', sub: 'S3 SQS/SNS trigger' },
                { id: 'realtime_stream', title: 'Real-time Stream', sub: 'Direct Kafka pipeline' },
                { id: 'daily', title: 'Daily Batch', sub: 'Off-peak sync' },
              ].map((opt) => {
                const active = syncMode === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    disabled title="Unavailable: only manual scans are supported."
                    className={`flex flex-col p-2.5 rounded-sm border text-left transition-colors ${
                      active
                        ? 'bg-nexus-brandSubtle text-nexus-brandText border-nexus-border'
                        : 'bg-nexus-input text-nexus-textSecondary border-nexus-border hover:border-nexus-borderStrong'
                    }`}
                  >
                    <span className="text-sm font-bold">{opt.title}</span>
                    <span className="text-sm text-nexus-textMuted mt-0.5">{opt.sub}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <p className="text-sm text-nexus-textMuted">Scheduling is unavailable. Save and test this connector, then start a manual scan from Sources. NFS paths must be mounted in both ingestion containers.</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {sourceType === 's3' && <label className="flex flex-col gap-1.5">Object prefix<input className="nx-input" value={prefix} onChange={e => setPrefix(e.target.value)}/></label>}
            <label className="flex flex-col gap-1.5">Maximum files per scan<input type="number" min="1" required className="nx-input" value={maxFiles} onChange={e => setMaxFiles(e.target.value)}/></label>
            {sourceType === 's3' && authMethod === 'iam_role' && <label className="flex flex-col gap-1.5">External ID<input type="password" className="nx-input" value={externalId} onChange={e => setExternalId(e.target.value)}/></label>}
          </div>
          {/* Security Banner */}
          <div className="flex items-start gap-2.5 p-3 rounded-sm bg-[#0c1424] border border-[#192a47] text-nexus-textMuted">
            <ShieldIcon className="w-4 h-4 text-nexus-brandText shrink-0 mt-0.5" />
            <div className="text-sm leading-relaxed">
              <strong className="text-nexus-textPrimary block">Secure Vault Storage</strong>
              Secret keys and passwords are write-only to HashiCorp Vault. They will never be echoed back in API responses.
            </div>
          </div>
        </form>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-nexus-border bg-nexus-elevated flex items-center justify-between gap-3">
          <p className="text-xs text-nexus-textMuted max-w-[180px]">Save first, then test the connection from Sources.</p>
          {/* Test connection status badge */}
          <div className="flex items-center gap-2">
            {testResult && (
              <span
                className={`inline-flex items-center gap-1.5 text-sm font-mono px-2 py-1 rounded-xs border ${
                  testResult.status === 'Verified'
                    ? 'bg-[#122a1e] border-[#1f5739] text-[#4ade80]'
                    : 'bg-[#2b1414] border-[#592323] text-[#f87171]'
                }`}
              >
                {testResult.status === 'Verified' ? (
                  <CheckCircleIcon className="w-3.5 h-3.5" />
                ) : (
                  <XCircleIcon className="w-3.5 h-3.5" />
                )}
                <span>{testResult.status === 'Verified' ? 'Connection Verified' : 'Connection Failed'}</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              disabled title="Save the connector first, then test it from Sources."
              className="flex items-center gap-1.5 px-3 py-2 rounded-sm bg-nexus-surface hover:bg-nexus-hover border border-nexus-border text-sm text-nexus-textSecondary hover:text-nexus-textPrimary transition-colors disabled:opacity-50"
            >
              {isTesting ? <SpinnerIcon className="w-3.5 h-3.5 animate-spin" /> : null}
              <span>Test after saving</span>
            </button>

            <button
              type="button"
              onClick={handleSubmit}
              disabled={isSubmitting || isTesting}
              className="flex items-center gap-1.5 px-4 py-2 bg-nexus-brand hover:bg-nexus-brandHover active:bg-blue-900 text-white text-sm font-semibold rounded-sm border border-nexus-brand transition-colors disabled:opacity-50"
            >
              {isSubmitting ? <SpinnerIcon className="w-3.5 h-3.5 animate-spin" /> : null}
              <span>Save Connector</span>
            </button>
          </div>
        </div>
      </div>
    </DialogBackdrop>}</Presence>
  );
};

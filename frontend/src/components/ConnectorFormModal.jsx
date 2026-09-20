import React, { useEffect, useRef, useState } from 'react';
import { Presence } from './Motion';
import { DialogBackdrop } from './DialogBackdrop';
import { createConnector, testConnector } from '../services/adminApi';
import { connectorPayload, defaultConnectorForm } from '../services/connectorForm.js';
import { CloseIcon, DatabaseIcon, NASIcon, ShieldIcon, SpinnerIcon } from './Icons';

export const ConnectorFormModal = ({ isOpen, onClose, onSuccess, showToast }) => {
  const [form, setForm] = useState(defaultConnectorForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(null);
  const pending = useRef(false);
  const formRef = useRef(null);
  const errorRef = useRef(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  const change = event => setForm(previous => ({ ...previous, [event.target.name]: event.target.value }));
  const nas = form.sourceType !== 's3';
  const close = () => { if (!pending.current) onClose(); };
  const submit = async (event, verify = false) => {
    event.preventDefault();
    if (pending.current || nas || (!saved && !formRef.current.reportValidity())) return;
    setError('');
    let payload;
    try { if (!saved) payload = connectorPayload(form); }
    catch (failure) { setError(failure.message); return; }
    pending.current = true; setBusy(true);
    let connector = saved;
    try {
      if (!connector) {
        connector = await createConnector(payload);
        setSaved(connector);
        // Retain the ID after failed verification; retry must not create duplicates.
        onSuccess?.(connector);
      }
      if (verify) {
        const result = await testConnector(connector.id);
        onSuccess?.(connector);
        if (result.status !== 'Verified') throw new Error(result.message || 'Connection test failed.');
      }
      showToast?.(verify ? `Connection to '${connector.name || form.name}' verified` : 'Connector saved', 'success');
      onClose();
    } catch (failure) {
      setError(`${connector ? 'Connector saved. ' : ''}${failure.message || 'Unable to save connector.'}`);
    } finally { pending.current = false; setBusy(false); }
  };
  const input = (name, props = {}) => <input name={name} id={props.id || name} value={form[name]} onChange={change} {...props} />;
  const field = (name, label, props = {}, help = '') => <label className="connector-field" htmlFor={props.id || name}><span className="connector-label">{label}</span>{input(name, props)}{help && <span className="connector-help">{help}</span>}</label>;
  const radio = (name, value, label) => <label className="connector-radio"><input type="radio" name={name} value={value} checked={form[name] === value} onChange={change} /><span>{label}</span></label>;
  const mono = {className:'connector-mono'};

  return <Presence>{isOpen && <DialogBackdrop onClose={close}>
    <div className="detail-dialog dialog-surface connector-dialog" role="dialog" aria-modal="true" aria-labelledby="connector-heading" tabIndex={-1}>
      <header className="connector-header">
        <div className="connector-heading-icon"><DatabaseIcon /></div>
        <div><h2 id="connector-heading">Connect a Data Source</h2><p>Configure S3 bucket or NAS storage for bounded manual ingestion</p></div>
        <button type="button" onClick={close} disabled={busy} aria-label="Close dialog"><CloseIcon /></button>
      </header>
      <form id="connector-form" ref={formRef} onSubmit={submit} className="connector-body">
        {error && <div ref={errorRef} tabIndex={-1} className="connector-error" role="alert">{error}{saved && ' Retry the test or close this dialog; the connector is already listed in Sources.'}</div>}
        <fieldset disabled={busy || Boolean(saved)} className="connector-fields">
          <div className="connector-field"><span className="connector-label">Storage Source Type</span>
            <div className="connector-source-types">
              {[['s3', 'S3 / Object Store', DatabaseIcon], ['nas_smb', 'NAS (SMB)', NASIcon], ['nas_nfs', 'NAS (NFS)', NASIcon]].map(([value, label, Icon]) =>
                <button key={value} type="button" aria-pressed={form.sourceType === value} onClick={() => { setForm(previous => ({...previous, sourceType:value})); setError(''); }}><Icon /><span>{label}</span></button>)}
            </div>
          </div>
          {field('name', 'Connector Display Name *', {id:'conn-name', required:true, placeholder:'e.g., prod-fab-inspection-archive'})}
          {!nas ? <section className="connector-section" aria-label="S3 configuration">
            <div className="connector-columns">
              {field('bucketName', 'Bucket Name *', {...mono, id:'s3-bucket', required:true, placeholder:'my-multimodal-bucket'})}
              {field('region', 'AWS / Cluster Region', {...mono, id:'s3-region', required:true, placeholder:'ap-south-1'})}
            </div>
            {field('endpointUrl', 'Custom Endpoint URL', {...mono, id:'s3-endpoint', type:'url', placeholder:'https://s3.amazonaws.com (leave blank for standard AWS S3)'})}
            <div className="connector-divider">{field('prefix', 'Object-key prefix', {...mono, id:'s3-prefix', placeholder:'datasets/meld/images/', maxLength:1024}, 'Relative to the bucket. Leave empty only when you intend to scan the entire bucket.')}</div>
            <div className="connector-columns">
              {field('maxFiles', 'Maximum objects', {...mono, id:'s3-limit', type:'number', min:1, step:1}, 'Clear only for an intentional unbounded scan.')}
              {field('pageSize', 'Listing page size', {...mono, id:'s3-page-size', type:'number', min:1, max:1000, step:1, required:true})}
            </div>
            <div className="connector-columns">
              <fieldset className="connector-option-group"><legend>Addressing Style</legend><div>{radio('addressingStyle','virtual-hosted','Virtual-hosted')}{radio('addressingStyle','path','Path-style')}</div></fieldset>
              <fieldset className="connector-option-group"><legend>Signature Version</legend><div>{radio('signatureVersion','SigV4','SigV4 (Recommended)')}{radio('signatureVersion','SigV2','SigV2')}</div></fieldset>
            </div>
            <fieldset className="connector-option-group connector-divider"><legend>Authentication &amp; Authorization</legend>
              <div>{radio('authMethod','iam_role',<strong>IAM Role ARN (Recommended)</strong>)}{radio('authMethod','access_key','Access Key & Secret')}</div>
              {form.authMethod === 'iam_role' ? <>
                {field('iamRoleArn', 'Target IAM Role ARN (Cross-account or Task Role)', {...mono, id:'iam-role-arn', required:true, placeholder:'arn:aws:iam::123456789012:role/NexusS3IngestRole'})}
                <details className="connector-advanced"><summary>External ID (optional)</summary>{field('externalId', 'Cross-account External ID', {...mono, type:'password', autoComplete:'off'})}</details>
              </> : <div className="connector-columns">
                {field('accessKeyId', 'Access Key ID', {...mono, id:'s3-key', required:true, autoComplete:'off', placeholder:'Enter your AWS access key ID'})}
                {field('secretAccessKey', 'Secret Access Key', {...mono, id:'s3-secret', type:'password', required:true, autoComplete:'new-password', placeholder:'••••••••••••••••••••••••'})}
              </div>}
            </fieldset>
          </section> : <section className="connector-section" aria-label="NAS configuration">
            {field('sharePath', form.sourceType === 'nas_smb' ? 'SMB Share Path *' : 'Mounted NFS Path *', {...mono, id:'nas-share', placeholder:form.sourceType === 'nas_smb' ? '//nas-server.internal/shared-fab' : '/mnt/vendor-data'})}
            {field('maxFiles', 'Maximum files', {...mono, id:'nas-limit', type:'number', min:1}, 'Keep a limit for tests. Clear only when you intentionally want to scan the complete share.')}
            {form.sourceType === 'nas_smb' ? <div className="connector-columns">
              {field('nasUsername', 'SMB Username / Domain', {...mono, id:'smb-user', placeholder:'DOMAIN\\svc-ingest'})}
              {field('nasPassword', 'SMB Password', {...mono, id:'smb-pass', type:'password', autoComplete:'new-password', placeholder:'••••••••••••'})}
            </div> : <p className="connector-help">NFS must be mounted on the ingestion host. Authentication is configured on that mount.</p>}
          </section>}
        </fieldset>
        {nas && <p className="connector-help" role="status">NAS integration is deferred. These fields are available for review; saving and testing NAS sources will be enabled when the source is connected.</p>}
        <div className="connector-security"><ShieldIcon /><p><strong>Secure Vault Storage</strong><span>Secret keys and passwords are write-only to HashiCorp Vault. They will never be echoed back in API responses.</span></p></div>
      </form>
      <footer className="connector-footer">
        <button type="button" disabled={busy || nas} onClick={event => submit(event, true)} title={nas ? 'NAS integration is deferred' : undefined}>{busy && <SpinnerIcon className="animate-spin" />}{saved ? 'Retry Test' : 'Save & Test'}</button>
        <button type={saved ? 'button' : 'submit'} form="connector-form" className="connector-save" onClick={saved ? close : undefined} disabled={busy || nas} title={nas ? 'NAS integration is deferred' : undefined}>{saved ? 'Done' : 'Save Connector'}</button>
      </footer>
    </div>
  </DialogBackdrop>}</Presence>;
};

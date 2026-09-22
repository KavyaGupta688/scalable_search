// Translate browser form values to ingestion's existing connector contract.
export const defaultConnectorForm = {
  sourceType:'s3', name:'', bucketName:'', region:'ap-south-1', endpointUrl:'',
  prefix:'', maxFiles:'1000', pageSize:'1000', addressingStyle:'virtual-hosted',
  signatureVersion:'SigV4', authMethod:'iam_role', iamRoleArn:'', externalId:'',
  accessKeyId:'', secretAccessKey:'', sharePath:'', nasUsername:'', nasPassword:'',
  metadataMode:'required',
};

export function connectorPayload(form) {
  if (!form.name.trim()) throw new Error('Connector name is required.');
  const limit = String(form.maxFiles).trim() === '' ? null : Number(form.maxFiles);
  if (limit !== null && (!Number.isSafeInteger(limit) || limit < 1)) throw new Error('Maximum objects must be a positive integer or empty.');
  if (form.sourceType === 'nas_smb') {
    const path = form.sharePath.trim().replaceAll('/', '\\');
    const parts = path.slice(2).split('\\');
    if (!path.startsWith('\\\\') || parts.length < 2 || parts.some(p => !p || p === '.' || p === '..')) throw new Error('Enter an SMB UNC path such as \\\\server\\share\\folder.');
    if (!form.nasUsername.trim() || !form.nasPassword) throw new Error('SMB username and password are required.');
    return {name:form.name.trim(), source_type:'NAS_SMB', nas:{protocol:'SMB', mount_path:path,
      username:form.nasUsername.trim(), password:form.nasPassword, max_files:limit}};
  }
  if (form.sourceType === 'nas_nfs') {
    if (!form.sharePath.startsWith('/') || form.sharePath.split('/').includes('..')) throw new Error('NFS requires an absolute path already mounted in the ingestion containers.');
    return {name:form.name.trim(), source_type:'NAS_NFS', nas:{protocol:'NFS',mount_path:form.sharePath.trim(),max_files:limit}};
  }
  if (form.sourceType !== 's3') throw new Error('Unsupported source type.');
  if (!form.bucketName.trim()) throw new Error('Bucket name is required.');
  const pageSize = Number(form.pageSize);
  if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 1000) throw new Error('Listing page size must be between 1 and 1000.');
  if (!/^[a-z]{2}(?:-[a-z]+)+-\d+$/.test(form.region.trim())) throw new Error('Enter a valid AWS region.');
  let endpoint = form.endpointUrl.trim();
  if (endpoint) {
    const url = new URL(endpoint);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Use an HTTP(S) endpoint without embedded credentials.');
  } else endpoint = `https://s3.${form.region.trim()}.amazonaws.com${form.region.trim().startsWith('cn-') ? '.cn' : ''}`;
  const role = form.authMethod === 'iam_role';
  const anonymous = form.authMethod === 'anonymous';
  if (role && !form.iamRoleArn.trim()) throw new Error('IAM Role ARN is required.');
  if (!role && !anonymous && (!form.accessKeyId.trim() || !form.secretAccessKey)) throw new Error('Access key and secret are required.');
  return {name:form.name.trim(), source_type:'S3', s3:{
    endpoint_url:endpoint, bucket:form.bucketName.trim(),
    auth_mode:anonymous ? 'anonymous' : role ? 'aws_assume_role' : 'static_keys',
    metadata_mode:form.metadataMode || 'required',
    addressing_style:form.addressingStyle === 'virtual-hosted' ? 'virtual' : 'path',
    signature_version:form.signatureVersion === 'SigV4' ? 's3v4' : 's3',
    prefix:form.prefix, max_objects:limit, page_size:pageSize,
    ...(anonymous ? {} : role ? {role_arn:form.iamRoleArn.trim(), external_id:form.externalId || null} : {access_key:form.accessKeyId.trim(), secret_key:form.secretAccessKey}),
  }};
}

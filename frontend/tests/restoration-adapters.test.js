import test from 'node:test';
import assert from 'node:assert/strict';
import {bytes, number, fileView, connectorView, runView, pipelineGroups} from '../src/services/presentation.js';
import {getConnectors, createConnector, startScan, archiveConnector, getAuditLogs} from '../src/services/adminApi.js';
import {connectorPayload, defaultConnectorForm} from '../src/services/connectorForm.js';

global.localStorage = {getItem: key => key === 'nexus_token' ? 'test-session' : null};

test('connector form preserves S3 prefix, bounds, region and mutually exclusive credentials', () => {
  const role = {...defaultConnectorForm, name:'Source', bucketName:'bucket', iamRoleArn:'arn:aws:iam::123456789012:role/Ingest', prefix:'datasets/meld/images/', pageSize:'250', secretAccessKey:'must-not-leak'};
  const body = connectorPayload(role);
  assert.equal(body.s3.endpoint_url, 'https://s3.ap-south-1.amazonaws.com');
  assert.equal(body.s3.max_objects, 1000); assert.equal(body.s3.page_size, 250);
  assert.equal(body.s3.prefix, 'datasets/meld/images/'); assert.equal(body.s3.secret_key, undefined);
  const keys = connectorPayload({...role, authMethod:'access_key', accessKeyId:'example', secretAccessKey:'example-secret', maxFiles:'', addressingStyle:'path'});
  assert.equal(keys.s3.role_arn, undefined); assert.equal(keys.s3.max_objects, null);
  assert.equal(keys.s3.addressing_style, 'path'); assert.equal(keys.s3.auth_mode, 'static_keys');
});

test('connector form rejects invalid bounds, missing authentication and deferred NAS', () => {
  const form = {...defaultConnectorForm, name:'Source', bucketName:'bucket', iamRoleArn:'arn:aws:iam::123456789012:role/Ingest'};
  for (const maxFiles of ['0', '-1', '1.5', 'oops']) assert.throws(() => connectorPayload({...form,maxFiles}), /Maximum objects/);
  for (const pageSize of ['', '0', '1001', '1.5']) assert.throws(() => connectorPayload({...form,pageSize}), /Listing page size/);
  assert.throws(() => connectorPayload({...form,iamRoleArn:''}), /IAM Role ARN/);
  assert.throws(() => connectorPayload({...form,authMethod:'access_key'}), /Access key/);
  assert.throws(() => connectorPayload({...form,sourceType:'nas_smb'}), /deferred/);
  assert.throws(() => connectorPayload({...form,endpointUrl:'https://user:secret@example.test'}), /embedded credentials/);
});

test('display adapters distinguish missing data from measured zero', () => {
  assert.equal(bytes(null), '—'); assert.equal(bytes(0), '0 B');
  assert.equal(bytes(2048), '2.0 KiB'); assert.equal(number(null), '—'); assert.equal(number(0), '0');
  const row = fileView({file_id:'canonical-id',file_type:'csv',file_name:'table.csv',tags:[{tag:'data'}],score_info:{rrf_score:0.01234}});
  assert.equal(row.id,'canonical-id'); assert.equal(row.modality,'tabular');
  assert.equal(row.score,null); assert.equal(row.scoreLabel,'0.0123');
  assert.equal(row.fileSize,'—'); assert.equal(row.sourceUri,''); assert.deepEqual(row.tags,['data']);
});

test('connector archival and ingestion progress use persisted facts', () => {
  const row = connectorView({id:'source',status:'verified',source_type:'S3',bucket:'bucket',archived_at:'2026-01-01'});
  assert.equal(row.status,'Archived'); assert.equal(row.rawStatus,'verified'); assert.equal(row.discoveredFiles,null);
  const run = {id:'run',connector_id:'source',enumerated_count:10,terminal_count:4};
  assert.equal(runView(run).progress,null);
  assert.equal(runView({...run,enumeration_completed_at:'2026-01-01'}).progress,40);
  assert.equal(runView({...run,enumeration_completed_at:'2026-01-01',enumerated_count:0}).progress,null);
});

test('AI pipeline never reports missing or failed stages as complete', () => {
  assert.ok(pipelineGroups(null).every(stage => stage.status === 'unavailable'));
  const stages = pipelineGroups({status:'failed_terminal',current_stage:'tagging',stage_results:{preprocessing:{status:'completed'},tagging:{status:'failed'}}});
  assert.equal(stages[0].status,'completed'); assert.equal(stages[1].status,'pending'); assert.equal(stages[2].status,'failed');
  assert.equal(stages[3].status,'pending');
});

test('source mutations use real bounded connector contracts and canonical IDs', async () => {
  const calls=[];
  global.fetch=async(url,options) => {calls.push({url,options});return Response.json({id:'connector'});};
  const body={name:'Test',source_type:'NAS_NFS',nas:{protocol:'NFS',mount_path:'/fixture',max_files:3}};
  await createConnector(body); await startScan('source/id'); await archiveConnector('source/id');
  assert.deepEqual(JSON.parse(calls[0].options.body),body);
  assert.equal(calls[1].url,'/admin/ingestion/trigger/source%2Fid'); assert.equal(calls[1].options.method,'POST');
  assert.equal(calls[2].url,'/admin/connectors/source%2Fid/archive'); assert.equal(calls[2].options.method,'PATCH');
  assert.equal(calls[0].options.headers.Authorization,'Bearer test-session');
});

test('audit maps filters, pagination and identity without fabricating compliance', async () => {
  const controller=new AbortController();
  global.fetch=async(url,options) => {
    const params=new URL(url,'http://localhost').searchParams;
    assert.equal(params.get('actor'),'reader@example.test'); assert.equal(params.get('action'),'SEARCH');
    assert.equal(params.get('status'),'success'); assert.equal(params.get('page'),'2');
    assert.equal(options.signal,controller.signal);
    return Response.json({total:1,events:[{event_id:'event',actor:'reader@example.test',entity_id:'doc',occurred_at:'2026-01-01'}]});
  };
  const data=await getAuditLogs({user_id:'reader@example.test',action_type:'SEARCH',status:'success',page:2},controller.signal);
  assert.equal(data.events[0].id,'event'); assert.equal(data.events[0].target,'doc'); assert.equal(data.events[0].complianceCode,null);
});

test('sources surface permission and service failures instead of prototype fixtures', async () => {
  global.fetch=async()=>Response.json({detail:'Administrator permission required'},{status:403});
  await assert.rejects(getConnectors(),/Administrator permission required/);
  global.fetch=async()=>Response.json({detail:'Source service unavailable'},{status:503});
  await assert.rejects(getConnectors(),/Source service unavailable/);
});

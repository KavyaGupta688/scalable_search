import test from 'node:test';
import assert from 'node:assert/strict';
import {bytes, number, fileView, connectorView, runView, pipelineGroups} from '../src/services/presentation.js';
import {getConnectors, createConnector, startScan, archiveConnector, getAuditLogs} from '../src/services/adminApi.js';

global.localStorage = {getItem: key => key === 'nexus_token' ? 'test-session' : null};

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

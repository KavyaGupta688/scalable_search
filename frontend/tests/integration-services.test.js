import test from 'node:test';
import assert from 'node:assert/strict';
import { search,getSuggestions,getSimilar } from '../src/services/searchApi.js';
import { createBatchDownload,getDownloadStatus } from '../src/services/downloadApi.js';
import { protectedBlob } from '../src/services/http.js';
global.localStorage={getItem:k=>k==='nexus_token'?'session-token':null};
test('search forwards mode, filters and pagination without changing server order',async()=>{
 let call;const results=[{file_id:'second',score:0.1},{file_id:'first',score:0.9}];
 global.fetch=async(url,options)=>{call={url,options};return Response.json({results,total:45});};
 const data=await search('mountain','hybrid',{file_types:['image']},20,20);
 assert.equal(call.url,'/search');assert.equal(call.options.headers.Authorization,'Bearer session-token');
 assert.deepEqual(JSON.parse(call.options.body),{query:'mountain',search_mode:'hybrid',filters:{file_types:['image']},limit:20,offset:20});assert.deepEqual(data.results,results);
});
test('backend failures never become fabricated success',async()=>{global.fetch=async()=>Response.json({detail:'Broker unavailable'},{status:503});await assert.rejects(createBatchDownload(['id']),/Broker unavailable/);await assert.rejects(search('x'),/Broker unavailable/);});
test('autocomplete carries AbortSignal and encodes query',async()=>{const c=new AbortController();global.fetch=async(url,options)=>{assert.match(url,/q=a%26b/);assert.equal(options.signal,c.signal);return Response.json({suggestions:[]});};assert.deepEqual(await getSuggestions('a&b',c.signal),[]);});
test('similarity uses canonical document POST contract',async()=>{global.fetch=async(url,options)=>{assert.equal(url,'/search/similar');assert.equal(options.method,'POST');assert.equal(JSON.parse(options.body).file_id,'canonical-id');return Response.json({results:[]});};await getSimilar('canonical-id');});
test('downloads use persistent server IDs',async()=>{global.fetch=async(url,options)=>{assert.equal(url,'/downloads/batch');assert.deepEqual(JSON.parse(options.body),{file_ids:['a','b']});return Response.json({download_id:'server-job',status:'building'});};assert.equal((await createBatchDownload(['a','b'])).download_id,'server-job');global.fetch=async url=>{assert.equal(url,'/downloads/server-job');return Response.json({status:'failed',error:'Access expired'});};assert.equal((await getDownloadStatus('server-job')).status,'failed');});
test('protected content enforces browser bounds and authentication',async()=>{global.fetch=async(url,options)=>{assert.equal(options.headers.Authorization,'Bearer session-token');return new Response('abcdef');};await assert.rejects(protectedBlob('/documents/id/content',{maximum:3}),/size limit/);});

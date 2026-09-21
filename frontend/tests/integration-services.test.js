import test from 'node:test';
import assert from 'node:assert/strict';
import { search,getSuggestions,getSimilar,postSearchEvent,getPopularDatasets } from '../src/services/searchApi.js';
import { createBatchDownload,getDownloadStatus } from '../src/services/downloadApi.js';
import { protectedBlob } from '../src/services/http.js';
import { modalityCounts, facetCount, formatCount, resolutionCounts, RESOLUTIONS } from '../src/services/facets.js';
import { formatBytes, sizeCounts, SIZES, bytesToMb, mbToBytes } from '../src/services/sizes.js';
import { planDownload } from '../src/services/downloadApi.js';
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
test('oversized declared content is cancelled before reading source bytes', async () => {
 let reads=0,cancelled=false,released=false;
 global.fetch=async()=>({ok:true,headers:new Headers({'content-length':'447000000'}),body:{getReader:()=>({read:async()=>{reads++;throw new Error('Must not read');},cancel:async()=>{cancelled=true;},releaseLock:()=>{released=true;}})}});
 await assert.rejects(protectedBlob('/documents/id/content',{maximum:32*1024**2}),/size limit/);
 assert.equal(reads,0);assert.ok(cancelled);assert.ok(released);
});
test('dataset browse records a DATASET_OPEN event and popular datasets keep the 7-day view count',async()=>{
 global.fetch=async(url,options)=>{assert.equal(url,'/events/search');assert.equal(options.method,'POST');assert.deepEqual(JSON.parse(options.body),{event_type:'DATASET_OPEN',dataset_id:'ds-1'});return Response.json({status:'RECORDED'},{status:201});};
 assert.equal((await postSearchEvent('DATASET_OPEN',{dataset_id:'ds-1'})).status,'RECORDED');
 global.fetch=async url=>{assert.equal(url,'/datasets/popular');return Response.json({datasets:[{id:'ds-1',name:'Survey',view_count_7d:3}],total:1});};
 const popular=await getPopularDatasets();assert.equal(popular.datasets[0].view_count_7d,3);assert.equal(popular.datasets[0].dataset_id,'ds-1');
});
test('file-type facet counts map csv to tabular, ignore unknown types and never invent numbers',()=>{
 assert.equal(modalityCounts(undefined),null);
 assert.deepEqual(modalityCounts({file_types:[{value:'image',count:12},{value:'csv',count:4},{value:'document',count:20},{value:'unknown',count:9}]}),{image:12,video:0,document:20,audio:0,tabular:4});
 assert.equal(facetCount({ai_generated:[{value:'true',count:3}]},'ai_generated',true),3);
 assert.equal(facetCount({ai_generated:[{value:'true',count:3}]},'ai_generated',false),undefined);
 assert.equal(formatCount(undefined),'–');assert.equal(formatCount(0),'0');assert.equal(formatCount(1234),(1234).toLocaleString());
});
test('resolution counts cover every tier, keep unknown separate and never invent numbers',()=>{
 assert.equal(resolutionCounts(undefined),null);
 assert.equal(resolutionCounts({}),null);
 assert.deepEqual(resolutionCounts({resolutions:[{value:'4k',count:5},{value:'fhd',count:8},{value:'unknown',count:2},{value:'8k',count:9}]}),{'4k':5,'2k':0,fhd:8,hd:0,sd:0,unknown:2});
 assert.deepEqual(RESOLUTIONS.map(r=>r.id),['4k','2k','fhd','hd','sd']);
});
test('sizes are shown as file managers show them and size counts never invent numbers',()=>{
 assert.equal(formatBytes(0),'0 B');assert.equal(formatBytes(1536),'1.5 KB');assert.equal(formatBytes(3*1024**3),'3.0 GB');assert.equal(formatBytes(100*1024**4),'100.0 TB');
 assert.equal(formatBytes(undefined),'–');assert.equal(formatBytes(-1),'–');assert.equal(formatBytes(NaN),'–');
 assert.equal(sizeCounts(undefined),null);
 assert.deepEqual(sizeCounts({sizes:[{value:'lt100k',count:4},{value:'gte1g',count:1},{value:'other',count:9}]}),{lt100k:4,'100k-1m':0,'1m-10m':0,'10m-100m':0,'100m-1g':0,gte1g:1});
 assert.deepEqual(SIZES.map(s=>s.id),['lt100k','100k-1m','1m-10m','10m-100m','100m-1g','gte1g']);
 assert.equal(mbToBytes('5'),5*1024**2);assert.equal(bytesToMb(5*1024**2),5);assert.equal(bytesToMb(undefined),'');
});
test('download planning asks for the same search and returns ids only when requested',async()=>{
 const calls=[];global.fetch=async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});return Response.json({count:3,file_ids:['a','b','c']});};
 await planDownload({query:'ice',mode:'hybrid',filters:{file_types:['image']}},{count:3});
 assert.equal(calls[0].url,'/search/download-plan');
 assert.deepEqual(calls[0].body,{query:'ice',search_mode:'hybrid',filters:{file_types:['image']},count:3,include_ids:false});
 await planDownload({query:'*',mode:'text'},{includeIds:true});
 assert.deepEqual(calls[1].body,{query:'*',search_mode:'text',filters:{},count:null,include_ids:true});
});

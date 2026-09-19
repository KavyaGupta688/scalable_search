// Browser-only fixtures. Never imported by the application or written to backend data.
// First extract frontend/ from 92ff6d1 into .integration/redesign-reference and run it on 18001.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const assert=require('node:assert/strict');
(async()=>{
 const {initialMockData:original}=await import(pathToFileURL(path.resolve('.integration/redesign-reference/frontend/src/services/mockData.js')));
 const out='.integration/redesign-qa/comparison';fs.mkdirSync(out,{recursive:true});
 const docs=original.documents.map(d=>({...d,file_id:d.id,file_name:d.filename,title:d.filename,file_type:d.modality==='tabular'?'csv':d.modality,dataset_id:original.dataSources[0].id,dataset_name:d.source,description:d.aiDescription,ingested_at:d.createdAt,file_size:d.fileSizeBytes,score_info:{rrf_score:0.025},technical:{file_size:d.fileSizeBytes,checksum:d.checksum},ai_enrichment:{caption:d.canonicalCaption,ocr_text:d.ocrText,content_summary:d.aiDescription,embedding_model:'CLIP',embedding_version:'pinned',embedding_status:'indexed'}}));
 const connectors=original.dataSources.map(s=>({...s,status:'verified',source_type:'S3',bucket:s.bucketName,s3_prefix:s.endpoint.split('/').slice(3).join('/'),s3_auth_mode:'aws_assume_role'}));
 const runs=original.ingestionJobs.map((r,i)=>({...r,connector_id:connectors[i%connectors.length].id,status:'running',source_type:'S3',enumerated_count:r.discoveredCount,succeeded_count:r.validatedCount,terminal_count:r.validatedCount,duplicate_count:r.duplicateCount,failed_count:r.failedCount,enumeration_completed_at:'2026-08-20T20:00:00Z',mib_per_second:null}));
 const audit=original.auditEvents.map(e=>({...e,event_id:e.id,actor:e.user,occurred_at:e.timestamp,entity_id:e.target,user_role:e.role}));
 const jobs=[{download_id:'comparison-job',status:'ready',file_count:2,progress:2,created_at:'2026-08-20T21:00:00Z',updated_at:'2026-08-20T21:00:00Z'}];
 const facets={file_types:['image','video','audio','document','csv'].map(value=>({value,count:2})),content_type:['image','video','audio','document','tabular'],datasets:[{value:connectors[0].id,count:docs.length}],categories:[],top_tags:[{value:'inspection',count:2}]};
 const browser=await chromium.launch({channel:'msedge',headless:true});const results=[];const errors=[];
 for(const width of [1440,390])for(const label of ['reference','integrated'])for(const role of ['admin','user','public']){
  const context=await browser.newContext({viewport:{width,height:width===390?844:1000},reducedMotion:'reduce'});
  await context.addInitScript(({role,jobs})=>{
   if(role!=='public'){localStorage.setItem('nexus_token','test-only-comparison-token');localStorage.setItem('nexus_role',role);localStorage.setItem('nexus_user',JSON.stringify({email:'comparison@example.test',role,displayName:'Review'}));}
   localStorage.setItem('nexus_downloads',JSON.stringify(jobs));
  },{role,jobs});
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;
   if(!['xhr','fetch'].includes(req.resourceType()))return route.continue();
   let body={};
   if(p==='/auth/me')body={email:'comparison@example.test',role};
   else if(p==='/auth/users')body={users:[]};
   else if(p==='/api/admin/overview')body={documents:original.platformOverview.totalIndexedFiles,sources:4,enrichment:{completed:original.platformOverview.filesProcessed},ingestion:{running:3}};
   else if(p==='/admin/connectors')body=label==='integrated'?connectors:{connectors:original.dataSources.map(s=>({...s,source_type:'S3',status:'Verified',endpoint_or_path:s.endpoint}))};
   else if(p==='/admin/ingestion/runs')body=runs;
   else if(p.startsWith('/admin/ingestion/runs/'))body=[];
   else if(p==='/api/audit/logs')body={events:audit,total:audit.length,page:1,page_size:50};
   else if(p==='/admin/audit/analytics')body={total:2,hours:24,breakdown:[]};
   else if(p==='/ai/tasks')body={tasks:docs.map(d=>({document_id:d.id,mime_type:d.contentType,status:'completed'})),total:docs.length};
   else if(p.startsWith('/ai/status/'))body={status:'completed',current_stage:'persistence',stage_results:Object.fromEntries(['preprocessing','ocr_extraction','tagging','captioning','quality_safety','metadata_fusion','confidence_validation','persistence'].map(s=>[s,{status:'completed'}]))};
   else if(p.startsWith('/ai/metadata/')){const d=docs.find(d=>p.endsWith(d.id))||docs[0];body={document_id:d.id,status:'completed',short_description:d.aiDescription,generated_tags:d.tags,ocr_text:d.ocrText,model_version:'test-only'};}
   else if(p==='/search'||p==='/search/similar')body={results:docs,total:docs.length,facets,execution_time_ms:20};
   else if(p==='/search/facets')body=facets;
   else if(p==='/search/suggestions')body={suggestions:[]};
   else if(p==='/search/trending')body={terms:[{query:'Optical inspection',count:142}],trending:[{query:'Optical inspection',search_count:142}]};
   else if(p==='/datasets/popular')body={datasets:connectors.map(s=>({id:s.id,name:s.name,file_count:2}))};
   else if(p.startsWith('/files/'))body=docs.find(d=>p.endsWith(d.id))||docs[0];
   else if(p==='/downloads')body={downloads:jobs};
   else if(p.startsWith('/downloads/'))body=jobs[0];
   else if(p.startsWith('/documents/'))return route.fulfill({status:200,contentType:'image/png',body:fs.readFileSync('.integration/nas/blue-square.png')});
   return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(`${label}/${role}/${width}: ${e.message}`));
  const base=`http://127.0.0.1:${label==='reference'?18001:18000}`;
  const capture=async name=>{await page.waitForTimeout(250);await page.screenshot({path:`${out}/${label}-${width}-${name}.png`,fullPage:true,animations:'disabled'});const size=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth}));results.push({label,width,name,overflow:size.width>size.viewport+1});};
  const routes=role==='public'?['','login/admin','login/user','register']:role==='user'?['user/search','user/downloads']:['admin/overview','admin/data-sources','admin/ingestion','admin/enrichment','admin/audit','admin/search'];
  for(const route of routes){
   await page.goto(`${base}/${route}`);await page.waitForTimeout(550);const name=route.replaceAll('/','-')||'landing';await capture(name);
   if(route==='admin/data-sources'){
    await page.getByRole('button',{name:'Connect a Source',exact:true}).click();await capture('source-form-s3');
    await page.getByLabel('Access Key & Secret',{exact:true}).check();await capture('source-form-s3-keys');
    await page.getByRole('button',{name:'NAS (SMB)',exact:true}).click();await capture('source-form-smb');
    await page.getByRole('button',{name:'NAS (NFS)',exact:true}).click();await capture('source-form-nas');await page.keyboard.press('Escape');
    await page.getByText(connectors[0].name,{exact:true}).click();await capture('source-detail');await page.keyboard.press('Escape');
   }
   if(route==='admin/ingestion'){await page.locator('tbody tr').first().click();await capture('ingestion-detail');await page.keyboard.press('Escape');}
   if(route==='admin/overview' && width===390){await page.getByRole('button',{name:'Open navigation',exact:true}).click();await capture('mobile-navigation');await page.keyboard.press('Escape');}
   if(route.endsWith('/search')){
    await page.locator(role==='admin'?'#admin-search-input':'#user-search-input').fill('inspection');
    if(role==='admin')await page.getByRole('button',{name:'Search',exact:true}).click();
    await page.locator('.result-card').first().waitFor();await page.getByRole('heading').first().click();await capture(`${role}-results`);
    if(role==='admin'){await page.getByTitle('Table View',{exact:true}).click();await capture('admin-results-table');await page.getByTitle('Grid View',{exact:true}).click();}
    await page.locator('.result-card').first().click();await page.getByRole('dialog').waitFor();await page.waitForTimeout(300);await capture(`${role}-detail`);
    await page.getByRole('button',{name:'Find Similar Files',exact:true}).click();await page.getByText('Similar Vector Matches',{exact:true}).waitFor();await capture(`${role}-similar`);await page.keyboard.press('Escape');
    if(role==='user'){await page.getByRole('button',{name:'Select for batch download'}).first().click();await capture('user-selection');}
    if(label==='integrated'){await page.getByText('More filters',{exact:true}).click();await capture(`${role}-expanded-filters`);}
   }
  }
  await context.close();
 }
 fs.writeFileSync(`${out}/results.json`,JSON.stringify({captures:results,errors},null,2));await browser.close();
 console.log(JSON.stringify({captures:results.length,overflows:results.filter(r=>r.overflow),errors},null,2));assert.deepEqual(errors,[]);
})().catch(error=>{console.error(error.stack);process.exit(1);});

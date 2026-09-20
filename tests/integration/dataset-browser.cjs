// Live browser acceptance for an explicitly selected S3 dataset. No data mocks.
// --complete additionally checks all search modes, previews and download outcomes.
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const cid=process.argv[2];
assert.match(cid||'',/^[0-9a-f-]{36}$/);
const complete=process.argv.includes('--complete');
const paginationOnly=process.argv.includes('--pagination-only');
const base='http://127.0.0.1:18000';
const output=`.integration/dataset-browser-${paginationOnly?'pagination':complete?'complete':'progress'}`;
const env=Object.fromEntries(fs.readFileSync('.integration/stack.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>{const i=l.indexOf('=');return [l.slice(0,i),l.slice(i+1)];}));
let page,browser;
const checks=[],errors=[],limitations=[];
const pass=name=>{checks.push(name);console.log('PASS:',name);fs.writeFileSync(`${output}/results.json`,JSON.stringify({checks,errors,limitations},null,2));};
async function capture(name){await page.screenshot({path:`${output}/${name}.png`,fullPage:true,animations:'disabled',mask:[page.locator('#s3-key'),page.locator('#s3-secret'),page.locator('input[type=password]')]});}
async function login(role,email,password){
  await page.goto(`${base}/login/${role}`);
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password',{exact:true}).fill(password);
  await page.locator('button[type=submit]').click();
  await page.waitForURL(`**/${role}/${role==='admin'?'overview':'search'}`);
}
async function registerUser(){
  await page.goto(`${base}/register?role=user`);
  assert.ok(await page.getByRole('button',{name:'Administrator',exact:true}).isDisabled());
  const email=`dataset-browser-${Date.now()}@example.test`,password=crypto.randomBytes(18).toString('base64url')+'aA1!';
  await page.locator('#reg-email').fill(email);await page.locator('#reg-name').fill('Dataset acceptance tester');
  await page.locator('#reg-password').fill(password);await page.locator('#reg-confirm').fill(password);
  await page.locator('button[type=submit]').click();await page.waitForURL('**/user/search');
}
async function searchAction(action,predicate=()=>true){
  const reply=page.waitForResponse(r=>r.url()===`${base}/search`&&r.request().method()==='POST'&&predicate(r.request().postDataJSON()),{timeout:90000});
  await action();const r=await reply;assert.ok(r.ok(),`search ${r.status()}`);
  const data=await r.json();
  await page.waitForFunction(n=>document.querySelectorAll('.result-card').length===n,data.results.length);
  return data;
}
async function openFilters(){const d=page.locator('details').filter({hasText:'More filters'});if(await d.getAttribute('open')===null)await d.locator('summary').click();}
async function datasetSearch(){
  await page.getByRole('button',{name:'Exact Keyword',exact:true}).click();
  await searchAction(()=>page.getByRole('combobox',{name:'Search data catalog'}).fill('test asset'),d=>d.query==='test asset'&&d.search_mode==='text');
  await page.keyboard.press('Escape');await openFilters();
  const results=await searchAction(()=>page.getByLabel('Dataset',{exact:true}).selectOption(cid),d=>d.filters?.dataset_ids?.[0]===cid);
  assert.match(await page.getByLabel('Dataset',{exact:true}).locator('option:checked').innerText(),/CSV multimodal 5 GB website acceptance/);
  return results;
}
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  browser=await chromium.launch({channel:'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  page=await context.newPage();page.setDefaultTimeout(20000);
  page.on('pageerror',e=>errors.push(e.message));
  if(paginationOnly){
    await registerUser();
    for(const role of ['user','admin']){
      if(role==='admin'){
        await page.getByRole('button',{name:'Sign out',exact:true}).click();
        await login('admin',env.BOOTSTRAP_ADMIN_EMAIL,env.BOOTSTRAP_ADMIN_PASSWORD);
        await page.goto(`${base}/admin/search`);await page.getByRole('button',{name:'Grid View',exact:true}).click();
      }
      const first=await datasetSearch(),limit=role==='user'?30:24;
      assert.ok(first.total>limit,`Need more than ${limit} published records`);
      const next=page.getByRole('navigation',{name:'Result pages'}).getByRole('button',{name:'Next',exact:true});
      const second=await searchAction(()=>next.click(),d=>d.offset===limit);
      assert.ok(second.results.length);
      assert.ok(second.results.every(r=>!first.results.some(f=>f.file_id===r.file_id)));
      await capture(`${role}-page-2`);
      await searchAction(()=>page.getByRole('navigation',{name:'Result pages'}).getByRole('button',{name:'Previous',exact:true}).click(),d=>d.offset===0);
      pass(`${role} next/previous search pages preserve dataset filters without duplicate results`);
    }
    assert.deepEqual(errors,[]);await page.getByRole('button',{name:'Sign out',exact:true}).click();
    await browser.close();return;
  }
  await page.goto(base);await page.locator('main').waitFor();await capture('public-home');pass('public landing page');
  await login('admin',env.BOOTSTRAP_ADMIN_EMAIL,env.BOOTSTRAP_ADMIN_PASSWORD);
  await page.getByText('Manage your data',{exact:true}).first().waitFor();
  await capture('admin-overview');pass('administrator login and overview');
  await page.goto(`${base}/admin/data-sources`);
  await page.getByText('CSV multimodal 5 GB website acceptance',{exact:true}).first().click();
  await page.getByRole('dialog',{name:'Data source details'}).waitFor();
  await page.getByText('demos/csv-multimodal-5gb/20260920-b114b5d3/',{exact:false}).first().waitFor();
  await capture('source-details');await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Connect a Source',exact:true}).click();
  await capture('connector-s3');
  for(const name of ['NAS (SMB)','NAS (NFS)']){
    await page.getByRole('button',{name,exact:true}).click();
    assert.ok(await page.getByRole('button',{name:'Save Connector',exact:false}).isDisabled());
  }
  await page.keyboard.press('Escape');pass('real source details, connector form and deferred NAS');
  if(complete){
    // This connector is created solely by this test and has never been scanned.
    const secrets=Object.fromEntries(fs.readFileSync('.integration/source.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>{const i=l.indexOf('=');return [l.slice(0,i),l.slice(i+1).replace(/^["']|["']$/g,'')];}));
    const name=`Browser lifecycle test ${Date.now()}`;
    await page.getByRole('button',{name:'Connect a Source',exact:true}).click();
    await page.locator('#conn-name').fill(name);await page.locator('#s3-bucket').fill('demo-bucket-prism');
    await page.locator('#s3-region').fill('ap-south-1');
    await page.locator('#s3-prefix').fill('demos/csv-multimodal-5gb/20260920-b114b5d3/__empty_browser_test__/');
    await page.locator('#s3-limit').fill('1');
    await page.getByLabel('Access Key & Secret',{exact:true}).check();
    await page.locator('#s3-key').fill(secrets.AWS_ACCESS_KEY_ID);await page.locator('#s3-secret').fill(secrets.AWS_SECRET_ACCESS_KEY);
    const tested=page.waitForResponse(r=>/\/admin\/connectors\/[^/]+\/test$/.test(r.url())&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Save & Test',exact:true}).click();assert.ok((await tested).ok());
    await page.getByRole('dialog',{name:'Connect a Data Source'}).waitFor({state:'hidden'});
    await page.getByText(name,{exact:true}).click();
    const archived=page.waitForResponse(r=>/\/archive$/.test(r.url())&&r.request().method()==='PATCH');
    await page.getByRole('button',{name:'Archive',exact:true}).click();assert.ok((await archived).ok());
    await page.getByRole('dialog',{name:'Data source details'}).waitFor({state:'hidden'});
    await page.getByText(name,{exact:true}).click();
    assert.ok(await page.getByRole('button',{name:'Trigger Manual Crawl',exact:true}).isDisabled());
    await capture('archived-test-source');
    const removed=page.waitForResponse(r=>/\/admin\/connectors\/[^/]+$/.test(r.url())&&r.request().method()==='DELETE');
    await page.getByRole('button',{name:'Delete if unused',exact:true}).click();assert.ok((await removed).ok());
    await page.getByRole('dialog',{name:'Data source details'}).waitFor({state:'hidden'});
    pass('UI Save & Test, connector archival, disabled scanning and deletion of unused test source');
  }
  await page.goto(`${base}/admin/ingestion`);
  const row=page.locator('tbody tr').filter({hasText:'CSV multimodal 5 GB website acceptance'}).first();
  await row.waitFor();await capture('ingestion-history');await row.getByRole('button',{name:'Details',exact:true}).click();
  await page.getByRole('dialog',{name:'Ingestion details'}).waitFor();
  await page.getByText('demos/csv-multimodal-5gb/20260920-b114b5d3/',{exact:false}).first().waitFor();
  await capture('ingestion-details');await page.keyboard.press('Escape');pass('live ingestion history and run detail outcomes');
  await page.goto(`${base}/admin/enrichment`);
  await page.locator('#inspect-doc-select option[value]:not([value=""])').first().waitFor({state:'attached'});
  await capture('enrichment');
  const taskNext=page.getByRole('navigation',{name:'Task pages'}).getByRole('button',{name:'Next',exact:true});
  if(await taskNext.isEnabled()){
    const response=page.waitForResponse(r=>r.url().includes('/ai/tasks?limit=25&offset=25')&&r.ok());
    await taskNext.click();await response;await capture('enrichment-page-2');
  }
  assert.ok(await page.getByRole('button',{name:'Run Model Benchmark',exact:true}).isDisabled());
  pass('real AI tasks, pagination where available and honest unavailable telemetry');
  await page.goto(`${base}/admin/users`);await page.locator('tbody tr').first().waitFor();await capture('admin-users');pass('administrator user directory');
  await page.goto(`${base}/admin/search`);
  await page.getByRole('button',{name:'Grid View',exact:true}).click();
  const adminResults=await datasetSearch();assert.ok(adminResults.total>0);
  await capture('admin-search');pass('administrator discovery of cleared dataset records');
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await registerUser();
  pass('public registration creates a standard user and signs in');
  let result=await datasetSearch();assert.ok(result.total>0);await capture('user-search');
  if(complete){
    for(const [label,mode] of [['Hybrid','hybrid'],['Semantic','vector'],['Exact Keyword','text']]){
      result=await searchAction(()=>page.getByRole('button',{name:label,exact:true}).click(),d=>d.search_mode===mode);
      assert.ok(result.total>0);
    }
    const next=page.getByRole('navigation',{name:'Result pages'}).getByRole('button',{name:'Next',exact:true});
    if(result.total>30){
      const first=result.results.map(r=>r.file_id);
      const second=await searchAction(()=>next.click(),d=>d.offset===30);
      assert.ok(second.results.length);assert.ok(second.results.every(r=>!first.includes(r.file_id)));
      await capture('user-search-page-2');
      await searchAction(()=>page.getByRole('navigation',{name:'Result pages'}).getByRole('button',{name:'Previous',exact:true}).click(),d=>d.offset===0);
    }else{assert.ok(await next.isDisabled());limitations.push(`Only ${result.total} cleared records; second search page unavailable at the UI page size of 30. API pagination belongs to the separate dataset acceptance run.`);}
    pass('all search modes and live pagination boundaries');
    for(const [label,type] of [['Images','image'],['Documents','document'],['Audio','audio'],['Tabular','csv'],['Videos','video']]){
      const data=await searchAction(()=>page.getByRole('button',{name:label,exact:true}).click(),d=>d.filters?.file_types?.[0]===type);
      assert.ok(data.results.every(r=>r.file_type===type));
      if(!data.results.length){limitations.push(`${type}: no cleared results available`);continue;}
      await page.locator('.result-card').first().click();
      const dialog=page.getByRole('dialog',{name:'File details'});await dialog.waitFor();
      if(['image','audio','video'].includes(type)){
        // The dialog mounts before its metadata and preview request. Waiting
        // for an absent loading label can finish before that request starts.
        const previewStarted=Date.now();
        await page.waitForFunction(kind=>{
          const dialog=document.querySelector('[role=dialog]');
          if(!dialog)return false;
          if(dialog.querySelector('[role=alert]'))return true;
          const media=dialog.querySelector(kind==='image'?'img':kind);
          return Boolean(media&&(kind==='image'?media.naturalWidth>0:media.readyState>=1));
        },type,{timeout:90000});
        if(Date.now()-previewStarted>20000)limitations.push(`${type} preview took ${Math.round((Date.now()-previewStarted)/1000)} seconds.`);
        if(await dialog.getByRole('alert').count())limitations.push(`${type} preview: ${await dialog.getByRole('alert').allTextContents()}`);
      }else await dialog.getByText('Preview unavailable',{exact:true}).waitFor();
      await page.getByRole('button',{name:'Find Similar Files',exact:true}).click();
      await page.getByText('Similar Vector Matches',{exact:true}).waitFor();
      await page.getByText('Querying vector index for nearest neighbors...',{exact:true}).waitFor({state:'hidden',timeout:90000});
      await capture(`${type}-details`);await page.keyboard.press('Escape');
    }
    pass('modality filters, protected detail previews and similarity');
    await searchAction(()=>page.getByRole('button',{name:'Images',exact:true}).click(),d=>d.filters?.file_types?.[0]==='image');
    await page.getByRole('button',{name:'Select for batch download'}).first().click();
    await page.getByRole('button',{name:'Download Selected',exact:true}).click();
    await page.getByRole('button',{name:'Save archive',exact:true}).waitFor({timeout:90000});
    const download=page.waitForEvent('download');await page.getByRole('button',{name:'Save archive',exact:true}).click();
    assert.match((await download).suggestedFilename(),/assets-.*\.zip/);
    await capture('archive-ready');await page.getByRole('button',{name:'Done',exact:true}).click();
    pass('actual image archive delivered through selection bar');
    await searchAction(()=>page.getByRole('button',{name:'Videos',exact:true}).click(),d=>d.filters?.file_types?.[0]==='video');
    const large=page.locator('.result-card').filter({hasText:/mp4/i}).first();
    if(await large.count()){
      await large.click();await page.getByRole('dialog',{name:'File details'}).getByRole('alert').waitFor({timeout:90000});
      await capture('large-video-preview-limit');await page.keyboard.press('Escape');
      await large.getByRole('button',{name:'Select for batch download'}).click();
      await page.getByRole('button',{name:'Download Selected',exact:true}).click();
      await page.getByText('Download failed',{exact:true}).waitFor({timeout:90000});
      assert.equal(await page.getByRole('button',{name:'Save archive',exact:true}).count(),0);
      await capture('oversize-download-failed');pass('large-file preview and download limits produce visible errors');
    }else limitations.push('No cleared MP4 available for UI size-limit test.');
    await page.goto(`${base}/user/downloads`);await page.getByRole('button',{name:'Download',exact:true}).first().waitFor();await capture('download-history');pass('persistent user download history');
  }
  await page.goto(`${base}/admin/data-sources`);await page.waitForURL('**/user/search');pass('administrator routes reject standard users');
  if(complete){
    await page.getByRole('button',{name:'Exact Keyword',exact:true}).click();
    const empty=await searchAction(()=>page.getByRole('combobox',{name:'Search data catalog'}).fill('notpresent'+crypto.randomBytes(12).toString('hex')));
    assert.equal(empty.total,0);await capture('empty-search');pass('empty search has no fabricated results');
    // Fault injection affects this browser request only, never shared services.
    await page.route('**/search',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Acceptance-test simulated backend outage'})}));
    await page.getByRole('combobox',{name:'Search data catalog'}).fill('outage check');
    await page.getByRole('alert').filter({hasText:'Acceptance-test simulated backend outage'}).waitFor();
    assert.equal(await page.locator('.result-card').count(),0);await capture('injected-outage');
    await page.unroute('**/search');pass('browser-only injected outage shows an error and no false success');
  }
  await datasetSearch();await page.setViewportSize({width:390,height:844});await capture('user-mobile');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));pass('mobile search fits the viewport');
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await page.setViewportSize({width:1440,height:1000});await login('admin',env.BOOTSTRAP_ADMIN_EMAIL,env.BOOTSTRAP_ADMIN_PASSWORD);
  await page.goto(`${base}/admin/audit`);await page.locator('tbody tr').first().waitFor();await capture('audit');
  const exported=page.waitForEvent('download');await page.getByRole('button',{name:'Export All CSV',exact:true}).click();assert.equal((await exported).suggestedFilename(),'audit.csv');pass('persistent Audit table and export');
  assert.deepEqual(errors,[]);await page.getByRole('button',{name:'Sign out',exact:true}).click();pass('no uncaught browser errors and successful logout');
  await browser.close();
})().catch(async error=>{console.error(error.stack);if(page){await capture('failure');console.error((await page.locator('body').innerText()).slice(0,10000));}await browser?.close();process.exitCode=1;});

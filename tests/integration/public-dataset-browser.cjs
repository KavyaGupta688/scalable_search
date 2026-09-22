// Live public ABO acceptance. Requires completed enrichment; no response fixtures.
const {chromium}=require('playwright');
const fs=require('node:fs'), assert=require('node:assert/strict'), crypto=require('node:crypto');
const base='http://127.0.0.1:18000', output='.integration/public-dataset-browser';
const cid=process.argv[2]; assert.match(cid||'',/^[0-9a-f-]{36}$/);
const paperCid=process.argv[3]; if(paperCid)assert.match(paperCid,/^[0-9a-f-]{36}$/);
const env=Object.fromEntries(fs.readFileSync('.integration/stack.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>{const i=l.indexOf('=');return [l.slice(0,i),l.slice(i+1)];}));
const checks=[],errors=[]; let browser,page;
function pass(name){checks.push(name);console.log('PASS:',name);fs.writeFileSync(`${output}/results.json`,JSON.stringify({checks,errors},null,2));}
async function shot(name){await page.screenshot({path:`${output}/${name}.png`,fullPage:true,animations:'disabled'});}
async function search(action,predicate=()=>true){
  const pending=page.waitForResponse(r=>r.url()===base+'/search'&&r.request().method()==='POST'&&predicate(r.request().postDataJSON()),{timeout:90000});
  await action();const r=await pending;assert.equal(r.status(),200);const data=await r.json();
  await page.waitForFunction(n=>document.querySelectorAll('.result-card').length===n,data.results.length);
  return data;
}
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  browser=await chromium.launch({channel:'msedge',headless:true});
  page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});page.setDefaultTimeout(30000);
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/login/admin');await page.getByLabel('Email address').fill(env.BOOTSTRAP_ADMIN_EMAIL);
  await page.getByLabel('Password',{exact:true}).fill(env.BOOTSTRAP_ADMIN_PASSWORD);
  await page.locator('button[type=submit]').click();await page.waitForURL('**/admin/overview');
  for(const route of ['overview','data-sources','ingestion','enrichment','downloads','audit']){
    await page.goto(base+'/admin/'+route);await page.locator('main').waitFor();
    if(route==='data-sources')await page.getByText('ABO real product photographs (6)',{exact:true}).first().waitFor();
    if(route==='audit')await page.locator('tbody tr').first().waitFor();
    await shot('admin-'+route);
  }
  pass('administrator screens render with the real ABO source and no uncaught errors');
  await page.goto(base+'/admin/data-sources');await page.getByRole('button',{name:'Connect a Source',exact:true}).click();
  await page.getByLabel('Public bucket (no credentials)',{exact:true}).check();
  await page.getByLabel('Vendor metadata',{exact:true}).selectOption('none');
  assert.equal(await page.locator('#s3-secret').count(),0);
  await shot('public-s3-connector');await page.keyboard.press('Escape');pass('public S3 form has explicit metadata policy and no credential inputs');
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await page.goto(base+'/register?role=user');
  await page.locator('#reg-email').fill(`abo-browser-${Date.now()}@example.test`);
  await page.locator('#reg-name').fill('Real dataset tester');
  const password=crypto.randomBytes(18).toString('base64url')+'aA1!';
  await page.locator('#reg-password').fill(password);await page.locator('#reg-confirm').fill(password);
  await page.locator('button[type=submit]').click();await page.waitForURL('**/user/search');
  await page.getByRole('button',{name:'Exact Keyword',exact:true}).click();
  await search(()=>page.getByRole('combobox',{name:'Search data catalog'}).fill('*'),d=>d.query==='*'&&d.search_mode==='text');
  await page.keyboard.press('Escape');
  const filters=page.locator('details').filter({hasText:'More filters'});await filters.locator('summary').click();
  let data=await search(()=>page.getByLabel('Dataset',{exact:true}).selectOption(cid),d=>d.filters?.dataset_ids?.[0]===cid);
  assert.ok(data.total>0);assert.ok(data.results.every(r=>r.dataset_id===cid));
  await shot('real-photographs');
  for(const [label,mode] of [['Semantic','vector'],['Hybrid','hybrid'],['Exact Keyword','text']]){
    data=await search(()=>page.getByRole('button',{name:label,exact:true}).click(),d=>d.search_mode===mode);
    assert.ok(data.total>0);assert.equal(data.facets.total_matches,data.total);
  }
  pass('new standard account sees published real photographs in all three search modes');
  await page.locator('.result-card').first().click();await page.getByRole('dialog',{name:'File details'}).waitFor();
  await page.waitForFunction(()=>[...document.querySelectorAll('[role=dialog] img')].some(i=>i.naturalWidth>0),null,{timeout:90000});
  await page.getByRole('button',{name:'Find Similar Files',exact:true}).click();
  await page.getByText('Similar Vector Matches',{exact:true}).waitFor();
  await page.getByText('Querying vector index for nearest neighbors...',{exact:true}).waitFor({state:'hidden',timeout:90000});
  await shot('photo-preview-and-similarity');await page.keyboard.press('Escape');pass('protected real image preview and similarity render');
  await page.getByRole('button',{name:'Select for batch download'}).first().click();
  await page.getByRole('button',{name:'Download Selected',exact:true}).click();
  await page.getByRole('button',{name:'Save archive',exact:true}).waitFor({timeout:120000});
  const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Save archive',exact:true}).click();
  assert.match((await downloaded).suggestedFilename(),/assets-.*\.zip/);await shot('real-archive');
  await page.getByRole('button',{name:'Done',exact:true}).click();pass('selected real photograph is packaged and delivered through the browser');
  await page.goto(base+'/user/downloads');await page.getByRole('button',{name:'Download',exact:true}).first().waitFor();await shot('user-download-history');
  if(paperCid){
    await page.goto(base+'/user/search');await page.getByRole('button',{name:'Exact Keyword',exact:true}).click();
    await search(()=>page.getByRole('combobox',{name:'Search data catalog'}).fill('*'),d=>d.query==='*'&&d.search_mode==='text');
    await page.keyboard.press('Escape');await page.locator('details').filter({hasText:'More filters'}).locator('summary').click();
    const paper=await search(()=>page.getByLabel('Dataset',{exact:true}).selectOption(paperCid),d=>d.filters?.dataset_ids?.[0]===paperCid);
    assert.equal(paper.total,1);assert.equal(paper.results[0].file_name,'ABO_CVPR2022.pdf');
    await page.locator('.result-card').first().click();await page.getByText('Extracted text preview',{exact:true}).waitFor();
    assert.match(await page.getByRole('dialog',{name:'File details'}).innerText(),/Amazon Berkeley Objects/i);
    await shot('paper-extracted-text');await page.keyboard.press('Escape');pass('real PDF is searchable and its extracted text is visible');
  }
  await page.goto(base+'/admin/data-sources');await page.waitForURL('**/user/search');pass('standard account is blocked from administrator routes');
  await page.setViewportSize({width:390,height:844});await shot('mobile-search');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);pass('mobile viewport fits and no uncaught browser errors');
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await browser.close();
})().catch(async e=>{console.error(e.stack);if(page){await shot('failure');console.error((await page.locator('body').innerText()).slice(0,6000));}await browser?.close();process.exitCode=1;});

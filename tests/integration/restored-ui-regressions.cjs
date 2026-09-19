// Deterministic UI contracts; all responses below are intercepted in this test browser only.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'});
 await context.addInitScript(()=>{localStorage.setItem('nexus_token','test-only');localStorage.setItem('nexus_role','user');localStorage.setItem('nexus_user',JSON.stringify({email:'test@example.test',role:'user',displayName:'Test'}));});
 const calls=[],errors=[],checks=[];let scenario='normal';
 const record=(query,index)=>({file_id:`${query}-${index}`,file_name:`${query} item ${index}`,file_type:'image',dataset_name:'Test fixture',tags:[],score_info:{rrf_score:index/1000}});
 await context.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url());if(!['xhr','fetch'].includes(req.resourceType()))return route.continue();
  let data={};
  if(url.pathname==='/auth/me')data={role:'user',email:'test@example.test'};
  if(url.pathname==='/search/facets')data={file_types:[{value:'image',count:61}],datasets:[],categories:[],top_tags:[]};
  if(url.pathname==='/search/suggestions'){if(url.searchParams.get('q')==='old')await new Promise(r=>setTimeout(r,1200));data={suggestions:[{text:url.searchParams.get('q')+' suggestion'}]};}
  if(url.pathname==='/search'){
   const body=req.postDataJSON();calls.push(body);
   if(body.query==='old')await new Promise(r=>setTimeout(r,1200));
   if(body.query==='slow')await new Promise(r=>setTimeout(r,900));
   if(body.query==='denied')return route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({detail:'Test permission denied'})});
   const total=body.query==='empty'?0:61;
   data={results:Array.from({length:Math.max(0,Math.min(body.limit,total-body.offset))},(_,i)=>record(body.query,body.offset+i)),total,facets:{file_types:[],datasets:[],categories:[],top_tags:[]}};
  }
  if(url.pathname==='/downloads/batch')return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Test packaging unavailable'})});
  if(url.pathname.startsWith('/files/'))data=record('slow',0);
  if(url.pathname.startsWith('/documents/'))return route.fulfill({status:200,contentType:'image/png',body:'invalid-image-test-fixture'});
  if(url.pathname==='/datasets/popular')data={datasets:[]};
  if(url.pathname==='/search/trending')data={trending:[]};
  try {await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});}catch(error){if(!/closed|disposed|intercept|Invalid/.test(error.message))throw error;}
 });
 const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(10000);
 await page.goto('http://127.0.0.1:18000/user/search');const input=page.getByRole('combobox',{name:'Search data catalog'});
 await input.fill('ordered');await page.locator('.result-card').first().waitFor();await input.press('Escape');
 assert.equal(await input.inputValue(),'ordered');assert.equal(await page.locator('.result-card').count(),30);
 assert.match(await page.locator('.result-card').first().innerText(),/ordered item 0/);assert.match(await page.locator('.result-card').last().innerText(),/ordered item 29/);
 assert.equal(calls.at(-1).search_mode,'hybrid');checks.push('hybrid default and server ordering');
 await page.getByRole('navigation',{name:'Result pages'}).getByRole('button',{name:'Next'}).click();
 await page.getByRole('button',{name:'Preview ordered item 30',exact:true}).waitFor();assert.equal(calls.at(-1).offset,30);
 await page.getByRole('navigation',{name:'Result pages'}).getByRole('button',{name:'Next'}).click();
 await page.getByRole('button',{name:'Preview ordered item 60',exact:true}).waitFor();assert.equal(await page.locator('.result-card').count(),1);assert.ok(await page.getByRole('navigation',{name:'Result pages'}).getByRole('button',{name:'Next'}).isDisabled());checks.push('three-page traversal with 61 results');
 await page.getByRole('button',{name:'Images',exact:true}).click();await page.getByRole('button',{name:'Preview ordered item 0',exact:true}).waitFor();assert.deepEqual(calls.at(-1).filters.file_types,['image']);assert.equal(calls.at(-1).offset,0);checks.push('filter resets pagination and is sent to server');
 await input.fill('old');await page.waitForTimeout(420);await input.fill('new');
 await page.getByRole('button',{name:'Preview new item 0',exact:true}).waitFor();await page.waitForTimeout(1300);
 assert.equal(await page.getByRole('button',{name:'Preview old item 0',exact:true}).count(),0);assert.equal(await page.getByRole('option',{name:'old suggestion',exact:true}).count(),0);
 await input.press('ArrowDown');await input.press('Enter');assert.equal(await input.inputValue(),'new suggestion');checks.push('stale search/autocomplete rejection and keyboard suggestion selection');
 await input.fill('slow');await page.getByText('Searching index...',{exact:true}).waitFor();await page.getByRole('button',{name:'Preview slow item 0',exact:true}).waitFor();checks.push('visible loading state');
 await input.press('Escape');await page.locator('.result-card').first().click();await page.getByRole('alert').filter({hasText:'Preview cannot be decoded by this browser.'}).waitFor();await page.keyboard.press('Escape');checks.push('undecodable media has an explicit unavailable preview');
 await page.getByRole('button',{name:'Select for batch download'}).first().click();await page.getByRole('button',{name:'Download Selected',exact:true}).click();await page.getByRole('alert').filter({hasText:'Test packaging unavailable'}).waitFor();assert.equal(await page.getByRole('button',{name:'Save archive',exact:true}).count(),0);checks.push('failed download request never becomes archive success');
 await input.fill('empty');await page.getByText('Found 0 files matching "empty"',{exact:true}).waitFor();assert.equal(await page.locator('.result-card').count(),0);checks.push('empty state');
 await input.fill('denied');await page.getByRole('alert').filter({hasText:'Test permission denied'}).waitFor();assert.equal(await page.locator('.result-card').count(),0);checks.push('permission denied clears stale results');
 assert.deepEqual(errors,[]);fs.writeFileSync('.integration/redesign-qa/regression-results.json',JSON.stringify({checks,errors},null,2));await browser.close();console.log(JSON.stringify({checks,errors},null,2));
})().catch(error=>{console.error(error.stack);process.exit(1);});

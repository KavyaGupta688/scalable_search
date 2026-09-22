// Real-service acceptance: page selection, pagination, table/grid and ZIP delivery.
const {chromium}=require('playwright');
const fs=require('node:fs'), assert=require('node:assert/strict'), crypto=require('node:crypto');
const base='http://localhost:18000', cid=process.argv[2];
assert.match(cid||'',/^[a-f0-9-]{36}$/);
const env=Object.fromEntries(fs.readFileSync('.integration/stack.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>{const i=l.indexOf('=');return [l.slice(0,i),l.slice(i+1)];}));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  for(const role of process.argv[3] ? [process.argv[3]] : ['admin','user']) {
   const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
   const page=await context.newPage();page.setDefaultTimeout(45000);
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   async function search(action,predicate=()=>true){
    const pending=page.waitForResponse(r=>r.url()===base+'/search'&&r.request().method()==='POST'&&predicate(r.request().postDataJSON()));
    const [response]=await Promise.all([pending,action()]);assert.equal(response.status(),200);
    const data=await response.json();await page.getByRole('checkbox',{name:'Select this page',exact:true}).waitFor();
    await page.waitForFunction(()=>!document.querySelector('input[type=checkbox][disabled]')||!document.querySelector('[aria-busy=true]'));
    return data;
   }
   if(role==='admin') {
    await page.goto(base+'/login/admin');await page.getByLabel('Email address').fill(env.BOOTSTRAP_ADMIN_EMAIL);
    await page.getByLabel('Password',{exact:true}).fill(env.BOOTSTRAP_ADMIN_PASSWORD);
    await page.locator('button[type=submit]').click();await page.waitForURL('**/admin/overview');
    await search(()=>page.goto(base+'/admin/search'));
   } else {
    await page.goto(base+'/register?role=user');
    await page.locator('#reg-email').fill(`group-download-${Date.now()}@example.test`);
    await page.locator('#reg-name').fill('Group download tester');
    const password=crypto.randomBytes(18).toString('base64url')+'aA1!';
    await page.locator('#reg-password').fill(password);await page.locator('#reg-confirm').fill(password);
    await page.locator('button[type=submit]').click();await page.waitForURL('**/user/search');
    await search(()=>page.getByRole('combobox',{name:'Search data catalog'}).fill('*'),d=>d.query==='*');
    await page.keyboard.press('Escape');
   }
   const all=page.getByRole('checkbox',{name:'Select this page',exact:true});
   await page.locator('.result-card').first().waitFor();
   const pageSize=await page.locator('.result-card').count();
   await all.check();await page.getByText(`${pageSize} / 100 files selected`,{exact:true}).waitFor();
   const next=await search(()=>page.getByRole('button',{name:'Next',exact:true}).click(),d=>d.offset===pageSize);
   assert.ok(next.results.length>0);await page.getByText(`${pageSize} / 100 files selected`,{exact:true}).waitFor();
   await all.check();await page.getByText(`${pageSize+next.results.length} / 100 files selected`,{exact:true}).waitFor();
   await all.uncheck();await page.getByText(`${pageSize} / 100 files selected`,{exact:true}).waitFor();
   await search(()=>page.getByRole('button',{name:'Previous',exact:true}).click(),d=>d.offset===0);
   assert.equal(await all.isChecked(),true);
   if(role==='admin') {
    await page.getByTitle('Table View',{exact:true}).click();
    const row=page.getByRole('checkbox',{name:/^Select .* for download$/}).first();
    await row.uncheck();assert.equal(await all.evaluate(el=>el.indeterminate),true);
    assert.equal(await page.getByRole('dialog').count(),0);
    await row.check();await page.getByTitle('Grid View',{exact:true}).click();
   }
   console.log('PASS',role,'selection persists across pages; page deselection preserves other pages');
   await page.locator('details').filter({hasText:'More filters'}).locator('summary').click();
   const dataset=await search(()=>page.getByLabel('Dataset',{exact:true}).selectOption(cid),d=>d.filters?.dataset_ids?.[0]===cid);
   await page.getByText('0 / 100 files selected',{exact:true}).waitFor();assert.equal(dataset.total,6);
   await all.check();await page.getByText('6 / 100 files selected',{exact:true}).waitFor();
   await page.getByRole('button',{name:'Deselect file',exact:true}).first().click();
   assert.equal(await all.evaluate(el=>el.indeterminate),true);
   await all.check();
   const batch=page.waitForResponse(r=>r.url()===base+'/downloads/batch'&&r.request().method()==='POST');
   await page.getByRole('button',{name:'Download Selected',exact:true}).click();
   const response=await batch;assert.ok(response.ok());
   assert.deepEqual([...response.request().postDataJSON().file_ids].sort(),dataset.results.map(r=>r.file_id).sort());
   await page.getByRole('button',{name:'Save archive',exact:true}).waitFor({timeout:180000});
   const pending=page.waitForEvent('download');await page.getByRole('button',{name:'Save archive',exact:true}).click();
   const download=await pending;await download.saveAs(`.integration/group-download-${role}.zip`);
   assert.equal(await download.failure(),null);
   await page.screenshot({path:`.integration/group-selection-${role}.png`,fullPage:true});
   await page.getByRole('button',{name:'Done',exact:true}).click();await page.getByText('0 / 100 files selected',{exact:true}).waitFor();
   await page.setViewportSize({width:390,height:844});await all.check();
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.getByRole('button',{name:'Clear selection',exact:true}).click();
   await page.setViewportSize({width:1440,height:1000});
   assert.deepEqual(errors,[]);await page.getByRole('button',{name:'Sign out',exact:true}).click();
   console.log('PASS',role,'filter reset, individual/group selection, six-file ZIP and mobile layout');
   await context.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});

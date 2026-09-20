// Isolated browser contracts: no writes to sources, Vault or RDS.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}, reducedMotion:'reduce'});
    await context.addInitScript(() => {
      localStorage.setItem('nexus_token','test-only'); localStorage.setItem('nexus_role','admin');
      localStorage.setItem('nexus_user',JSON.stringify({email:'test@example.test',role:'admin',displayName:'Test'}));
    });
    const calls=[]; let failTest=true, failSave=false;
    await context.route('**/*', async route => {
      const req=route.request(), url=new URL(req.url());
      if(!['xhr','fetch'].includes(req.resourceType()))return route.continue();
      let data={}; let status=200;
      if(url.pathname==='/auth/me')data={role:'admin',email:'test@example.test'};
      if(url.pathname==='/admin/connectors'&&req.method()==='GET')data=[];
      if(url.pathname==='/admin/connectors'&&req.method()==='POST'){
        calls.push({action:'create',body:req.postDataJSON()});
        data=failSave ? {detail:'Database unavailable'} : {id:'canonical-connector-id',name:'Test Source'}; status=failSave ? 503 : 200;
      }
      if(url.pathname.endsWith('/test')) {calls.push({action:'test',path:url.pathname});data={status:failTest?'failed':'verified',message:failTest?'Access denied by source':'Connection test successful'};}
      await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
    });
    const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:18000/admin/data-sources');
    const open=()=>page.getByRole('button',{name:'Connect a Source',exact:true}).click();
    await open(); const dialog=page.getByRole('dialog');
    fs.mkdirSync('.integration/team-review',{recursive:true});
    await dialog.screenshot({path:'.integration/team-review/connector-s3-top.png'});
    await page.locator('#iam-role-arn').scrollIntoViewIfNeeded();
    await dialog.screenshot({path:'.integration/team-review/connector-s3-bottom.png'});
    await page.getByRole('button',{name:'NAS (SMB)',exact:true}).click();
    await page.locator('.connector-body').evaluate(el=>el.scrollTop=0);
    assert.ok(await page.getByRole('button',{name:'Save Connector',exact:true}).isDisabled());
    assert.ok(await page.getByRole('button',{name:'Save & Test',exact:true}).isDisabled());
    await dialog.screenshot({path:'.integration/team-review/connector-smb.png'});
    await page.getByRole('button',{name:'NAS (NFS)',exact:true}).click();
    assert.ok(await page.getByRole('status').filter({hasText:'NAS integration is deferred'}).isVisible());
    await page.getByRole('button',{name:'S3 / Object Store',exact:true}).click();
    await page.locator('#conn-name').fill('Test Source');await page.locator('#s3-bucket').fill('bucket');
    await page.locator('#s3-prefix').fill('datasets/meld/images/');
    await page.locator('#iam-role-arn').fill('arn:aws:iam::123456789012:role/Ingest');
    await page.getByRole('button',{name:'Save & Test',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Connector saved. Access denied by source'}).waitFor();
    assert.equal(calls.filter(c=>c.action==='create').length,1);
    assert.equal(calls[0].body.s3.page_size,1000);assert.equal(calls[0].body.s3.max_objects,1000);
    failTest=false;
    await page.getByRole('button',{name:'Retry Test',exact:true}).click();
    await dialog.waitFor({state:'hidden'});
    assert.equal(calls.filter(c=>c.action==='create').length,1);
    assert.equal(calls.filter(c=>c.action==='test').length,2);
    await open();await page.locator('#conn-name').fill('Failure');await page.locator('#s3-bucket').fill('bucket');
    await page.locator('#iam-role-arn').fill('arn:aws:iam::123456789012:role/Ingest');failSave=true;
    await page.getByRole('button',{name:'Save Connector',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Database unavailable'}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Done',exact:true}).count(),0);
    await page.keyboard.press('Escape');
    await page.setViewportSize({width:390,height:844});await open();
    await dialog.screenshot({path:'.integration/team-review/connector-mobile.png'});
    assert.ok(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth));
    await page.locator('#iam-role-arn').scrollIntoViewIfNeeded();
    const footerButton = await page.getByRole('button',{name:'Save Connector',exact:true}).boundingBox();
    assert.ok(footerButton && footerButton.y >= 0 && footerButton.y + footerButton.height <= 844);
    assert.deepEqual(errors,[]);
    console.log('PASS: S3 limits/auth, save-and-test failure/retry without duplicates, failed save, deferred NAS, desktop/mobile layout');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});

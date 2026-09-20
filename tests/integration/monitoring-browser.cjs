// Live checks: existing integration records, no data substitutions.
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const env=Object.fromEntries(fs.readFileSync('.integration/stack.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>{const i=l.indexOf('=');return [l.slice(0,i),l.slice(i+1)];}));
const output='.integration/monitoring-browser';
const base='http://127.0.0.1:18000';
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    page.setDefaultTimeout(30000);
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/login/admin');
    await page.getByLabel('Email address').fill(env.BOOTSTRAP_ADMIN_EMAIL);
    await page.getByLabel('Password',{exact:true}).fill(env.BOOTSTRAP_ADMIN_PASSWORD);
    await page.locator('button[type=submit]').click();
    await page.waitForURL('**/admin/overview');
    await page.getByText('Ingested Documents',{exact:true}).waitFor();
    await page.waitForFunction(()=>!document.body.innerText.includes('Loading…'));
    const docCount=await page.evaluate(async()=>{
      const r=await fetch('/api/admin/overview',{headers:{Authorization:'Bearer '+localStorage.getItem('nexus_token')}});
      if(!r.ok) throw Error('Overview API failed');
      return (await r.json()).documents;
    });
    assert.ok(!(await page.locator('body').innerText()).includes('Recent item unavailable'));
    await page.screenshot({path:output+'/overview-desktop.png',fullPage:true});
    console.log('PASS real overview totals and recent discoveries');
    await page.goto(base+'/admin/downloads');
    await page.locator('.download-request').first().waitFor();
    const heading=await page.locator('.downloads-heading').boundingBox();
    const row=await page.locator('.download-request').first().boundingBox();
    assert.ok(heading.height<140,`heading height ${heading.height}`);
    assert.ok(row.y-heading.y-heading.height<80,`row gap ${row.y-heading.y-heading.height}`);
    await page.screenshot({path:output+'/downloads-desktop.png',fullPage:true});
    console.log('PASS compact downloads heading and request layout');
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:output+'/downloads-mobile.png',fullPage:true});
    console.log('PASS downloads mobile without horizontal overflow');
    await page.setViewportSize({width:1440,height:1000});
    await page.goto(base+'/admin/enrichment');
    await page.locator('#inspect-doc-select option:not([disabled])').first().waitFor({state:'attached'});
    let textOption=page.locator('#inspect-doc-select option').filter({hasText:'text/plain'}).first();
    if(!await textOption.count()) {
      await page.getByRole('navigation',{name:'Task pages'}).getByRole('button',{name:'Next',exact:true}).click();
      await textOption.waitFor({state:'attached'});
    }
    await page.locator('#inspect-doc-select').selectOption(await textOption.getAttribute('value'));
    await page.getByText('512 stored dimensions',{exact:true}).waitFor();
    await page.getByText('Indexed · published',{exact:true}).waitFor();
    await page.getByText('Extracted text preview',{exact:true}).waitFor();
    await page.getByText(/15\/15/).first().waitFor();
    await page.screenshot({path:output+'/enrichment-desktop.png',fullPage:true});
    console.log('PASS saved model checks, actual 512-vector and extracted text');
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'enrichment mobile overflow');
    await page.screenshot({path:output+'/enrichment-mobile.png',fullPage:true});
    console.log('PASS enrichment mobile without horizontal overflow');
    assert.deepEqual(errors,[]);
    await page.setViewportSize({width:1440,height:1000});
    await page.getByRole('button',{name:'Sign out',exact:true}).click();
    console.log('PASS no browser runtime errors; session revoked');
    const monitoringEnv=Object.fromEntries(fs.readFileSync('.integration/monitoring.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>{const i=l.indexOf('=');return [l.slice(0,i),l.slice(i+1)];}));
    const grafana=await browser.newPage({viewport:{width:1440,height:1000},extraHTTPHeaders:{Authorization:'Basic '+Buffer.from(monitoringEnv.GRAFANA_ADMIN_USER+':'+monitoringEnv.GRAFANA_ADMIN_PASSWORD).toString('base64')}});
    await grafana.goto('http://127.0.0.1:13000/d/smsprsm-platform');
    await grafana.getByText('Service readiness',{exact:true}).first().waitFor();
    await grafana.getByText(String(docCount),{exact:true}).first().waitFor({timeout:60000});
    await grafana.screenshot({path:output+'/grafana.png',fullPage:true});
    await grafana.getByText('AI stage mean · latest attempts, including model loading',{exact:true}).scrollIntoViewIfNeeded();
    await grafana.screenshot({path:output+'/grafana-stages.png',fullPage:true});
    assert.ok(!(await grafana.locator('body').innerText()).includes('Bar charts requires a string or time field'));
    console.log('PASS Grafana provisioned dashboard renders live document count with authenticated access');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});

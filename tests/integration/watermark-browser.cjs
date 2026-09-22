// Real role authorization and local-file upload, without mock responses.
const {chromium}=require('playwright');
const fs=require('node:fs'), assert=require('node:assert/strict'),crypto=require('node:crypto');
const env=Object.fromEntries(fs.readFileSync('.integration/stack.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>{const i=l.indexOf('=');return [l.slice(0,i),l.slice(i+1)];}));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.goto('http://localhost:18000/login/admin');
  await page.getByLabel('Email address').fill(env.BOOTSTRAP_ADMIN_EMAIL);
  await page.getByLabel('Password',{exact:true}).fill(env.BOOTSTRAP_ADMIN_PASSWORD);
  await page.locator('button[type=submit]').click();await page.waitForURL('**/admin/overview');
  await page.goto('http://localhost:18000/admin/downloads');
  await page.locator('.download-request').first().waitFor();
  await page.getByLabel('Downloaded file to trace').setInputFiles('.integration/download-tracker-proof.jpg');
  await page.getByRole('button',{name:'Trace watermark',exact:true}).click();
  await page.getByText('Authenticated watermark matches a recorded package.',{exact:true}).waitFor();
  await page.screenshot({path:'.integration/watermark-tracker-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.querySelector('.admin-sidebar').getBoundingClientRect().right<=0);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:'.integration/watermark-tracker-mobile.png',fullPage:true});
  const user=await browser.newPage();
  await user.goto('http://localhost:18000/register?role=user');
  const password=crypto.randomBytes(18).toString('base64url')+'aA1!';
  await user.locator('#reg-email').fill(`tracker-test-${Date.now()}@example.test`);
  await user.locator('#reg-name').fill('Tracker permission tester');
  await user.locator('#reg-password').fill(password);await user.locator('#reg-confirm').fill(password);
  await user.locator('button[type=submit]').click();await user.waitForURL('**/user/search');
  await user.goto('http://localhost:18000/user/downloads');
  assert.equal(await user.getByRole('heading',{name:'Watermark tracker',exact:true}).count(),0);
  const status=await user.evaluate(async()=>{
   const data=new FormData();data.append('file',new Blob(['test']),'test.txt');
   return (await fetch('/downloads/forensic/verify',{method:'POST',headers:{Authorization:'Bearer '+localStorage.getItem('nexus_token')},body:data})).status;
  });assert.equal(status,403);
  console.log('PASS: admin local-file tracing, responsive layout, user tracker hidden and API forbidden');
 } finally { await browser.close(); }
})().catch(e=>{console.error(e.message);process.exitCode=1;});

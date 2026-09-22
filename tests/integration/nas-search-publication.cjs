const {chromium}=require('playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
const env=Object.fromEntries(fs.readFileSync('.integration/stack.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>{const i=l.indexOf('=');return [l.slice(0,i),l.slice(i+1)];}));
const dataset='0f91a09b-127a-4a9c-b61a-f844f1479f3f',dog='01a0c2c8-0ea7-7ca3-a2d9-5526ec886b54';
(async()=>{
 const login=await fetch('http://localhost:18000/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:env.BOOTSTRAP_ADMIN_EMAIL,password:env.BOOTSTRAP_ADMIN_PASSWORD,role:'admin'})});
 assert(login.ok);const auth=await login.json();
 const headers={'Content-Type':'application/json',Authorization:`Bearer ${auth.access_token}`};
 for(const mode of ['text','hybrid','vector']){
  const r=await fetch('http://localhost:18000/search',{method:'POST',headers,body:JSON.stringify({query:'dog',search_mode:mode,filters:{dataset_ids:[dataset]},limit:100})});
  assert(r.ok);const data=await r.json();assert(data.results.some(f=>f.file_id===dog),`Dog missing in ${mode}`);
  console.log(mode,'dog present',data.total);
 }
 for(const word of ['dog','flower','car','beach','pizza','city','red','water','outdoor','search_dog_001']){
  const r=await fetch('http://localhost:18000/search',{method:'POST',headers,body:JSON.stringify({query:word,search_mode:'text',filters:{dataset_ids:[dataset],file_types:['image'],tags:[word]},limit:100})});
  assert(r.ok);const data=await r.json();console.log('image tag',word,data.total,data.results.map(f=>f.file_name));assert(data.total>0,`No image for ${word}`);
 }
 const videos=await fetch('http://localhost:18000/search',{method:'POST',headers,body:JSON.stringify({query:'conversation',search_mode:'text',filters:{dataset_ids:[dataset],file_types:['video']},limit:100})});
 assert(videos.ok);const videoResults=await videos.json();assert.equal(videoResults.total,4);console.log('PASS: all four recovered videos searchable');
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.goto('http://localhost:18000/login/admin');
  await page.getByLabel('Email address').fill(env.BOOTSTRAP_ADMIN_EMAIL);await page.getByLabel('Password',{exact:true}).fill(env.BOOTSTRAP_ADMIN_PASSWORD);
  await page.locator('button[type=submit]').click();await page.waitForURL('**/admin/overview');
  await page.goto('http://localhost:18000/admin/search');
  await page.getByRole('button',{name:'Exact Keyword',exact:true}).click();
  await page.locator('input[type=text]').first().fill('dog');
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await page.getByText('a dog running in the grass with a red ball',{exact:true}).first().waitFor({timeout:60000});
  await page.screenshot({path:'.integration/nas-dog-search-fixed.png',fullPage:true});
  console.log('PASS: real search API modes, NAS image tags and browser dog result');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});

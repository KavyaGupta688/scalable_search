// Explicit repair of the six NAS records affected by the pre-fix NudeNet adapter.
const fs=require('node:fs');
const env=Object.fromEntries(fs.readFileSync('.integration/stack.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>{const i=l.indexOf('=');return [l.slice(0,i),l.slice(i+1)];}));
const ids=['01a0c2c8-0ea7-7ca3-a2d9-5526ec886b54','01a0c2c8-5f10-7732-bf65-51de2699afde','01a0c2c8-77c9-7072-9b9b-9c848524b9b3','01a0c2c8-7fd1-7192-83fc-a7910343ed3d','01a0c2c8-6684-73a2-8aaf-3bbb212a041d','01a0c2c8-7046-70d0-bec6-840ecc8dac17'];
(async()=>{
 const response=await fetch('http://localhost:18000/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:env.BOOTSTRAP_ADMIN_EMAIL,password:env.BOOTSTRAP_ADMIN_PASSWORD,role:'admin'})});
 if(!response.ok)throw Error('Login failed');
 const {access_token}=await response.json();
 for(const id of ids){
  const r=await fetch(`http://localhost:18000/ai/retry/${id}`,{method:'POST',headers:{Authorization:`Bearer ${access_token}`}});
  console.log(id,r.status,await r.text());
  if(!r.ok)throw Error('Retry failed');
 }
})().catch(e=>{console.error(e.message);process.exitCode=1;});

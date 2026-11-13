// Production React + real FastAPI/SQL sessions; synthetic provider, isolated HTTPS.
const {chromium} = require(process.env.PLAYWRIGHT_CORE_MODULE || 'playwright-core');
const {spawn} = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const checks = [];
const demoOnly=process.argv.includes('--demo-only');
const revision=process.argv.includes('--revision004')?'004':'005';
let server, browser;
function assert(value, message) { if (!value) throw Error(message); }
async function check(name, work) { await work(); checks.push(name); }
(async () => {
 const port = await new Promise(resolve => { const s=net.createServer(); s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p));}); });
 const origin = `https://localhost:${port}`;
 server=spawn(path.join(root,'.venv/bin/python'),['-B',path.join(root,'backend/tests/sso_browser_server.py'),'--port',String(port),'--revision',revision,...(demoOnly?['--demo-only']:[])],{cwd:root,stdio:['ignore','ignore','pipe']});
 let stderr=''; server.stderr.on('data',d=>{stderr+=d;});
 browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(let n=0;n<100;n++){try {if((await context.request.get(origin+'/health')).ok())break;}catch{}await new Promise(r=>setTimeout(r,100));if(n===99)throw Error('Disposable fixture startup failed');}
 await check('Protected API denies missing cookie',async()=>assert((await context.request.get(origin+'/api/policies')).status()===401,'Missing cookie accepted'));
 if(demoOnly){
  await page.goto(origin+'/policies');
  await check('Production demo form remains available',async()=>{await page.getByLabel('Access token').waitFor();assert(await page.getByRole('button',{name:'Sign in with Microsoft'}).count()===0,'Unexpected SSO');});
  await check('Demo credential exchanges for existing server session',async()=>{await page.getByLabel('Access token').fill('synthetic-browser-demo');await page.getByRole('button',{name:'Connect workspace'}).click();await page.getByTitle('Sign out',{exact:true}).waitFor();});
  await check('Policy reads and role denial remain enforced',async()=>{
   const statuses=await page.evaluate(async()=>{const headers={Authorization:'Bearer '+sessionStorage.getItem('governance-token'),'Content-Type':'application/json'};return [(await fetch('/api/policies',{headers})).status,(await fetch('/api/policies',{method:'POST',headers,body:JSON.stringify({name:'Denied'})})).status];});
   assert(statuses[0]===200&&statuses[1]===403,'RBAC boundary');
  });
  await check('Refresh restores demo session after server validation',async()=>{await page.reload();await page.getByTitle('Sign out',{exact:true}).waitFor();});
  await check('Readiness reports the actual migrated revision',async()=>{const r=await context.request.get(origin+'/ready');assert(r.status()===200&&(await r.json()).database_revision===revision,'Readiness mismatch');});
  await check('Demo logout ends browser access',async()=>{await page.getByTitle('Sign out',{exact:true}).click();await page.getByLabel('Access token').waitFor();assert(await page.evaluate(()=>sessionStorage.getItem('governance-token'))===null,'Token retained');});
  await check('No browser errors',async()=>assert(errors.length===0,'Runtime errors'));
  console.log(JSON.stringify({mode:'DEMO_COMPATIBILITY',revision,passed:checks.length,failed:0,checks},null,2));
  return;
 }
 await page.goto(origin+'/policies');
 await check('Production login exposes Microsoft button only',async()=>{await page.getByRole('button',{name:'Sign in with Microsoft'}).waitFor();assert(await page.getByLabel('Access token').count()===0,'Legacy field exposed');});
 await check('Authorization redirect and callback restore original route',async()=>{await page.getByRole('button',{name:'Sign in with Microsoft'}).click();await page.waitForURL(origin+'/policies');await page.getByText('Synthetic User · Auditor · browser-fixture').waitFor();});
 await check('Session cookie attributes and no browser token storage',async()=>{const c=(await context.cookies()).find(c=>c.name==='__Host-governance-session');assert(c&&c.secure&&c.httpOnly&&c.sameSite==='Lax','Cookie attributes');assert(await page.evaluate(()=>sessionStorage.getItem('governance-token'))===null,'Browser bearer token stored');});
 await check('Refresh restores server session',async()=>{await page.reload();await page.getByText('Synthetic User · Auditor · browser-fixture').waitFor();assert((await context.request.get(origin+'/api/policies')).status()===200,'Session not restored');});
 await check('CSRF missing denied',async()=>assert((await context.request.post(origin+'/api/sso/logout')).status()===403,'CSRF accepted'));
 await check('Logout revokes session before Microsoft signout',async()=>{await page.route('https://login.microsoftonline.com/**',route=>route.fulfill({status:200,body:'Mock Microsoft sign-out'}));await page.getByTitle('Sign out',{exact:true}).click();await page.waitForURL(/login.microsoftonline.com/);assert((await context.request.get(origin+'/api/policies')).status()===401,'Logout failed');});
 await check('Sign-in succeeds again',async()=>{await page.goto(origin);await page.getByRole('button',{name:'Sign in with Microsoft'}).click();await page.getByText('Synthetic User · Auditor · browser-fixture').waitFor();});
 await check('Expired cookie returns protected navigation to login',async()=>{await context.clearCookies();await page.reload();await page.getByRole('button',{name:'Sign in with Microsoft'}).waitFor();});
 await check('Mobile login fits viewport',async()=>{await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Horizontal overflow');});
 await check('No browser runtime errors',async()=>assert(errors.length===0,'Runtime errors'));
 console.log(JSON.stringify({provider:'SYNTHETIC_NOT_MICROSOFT',passed:checks.length,failed:0,checks},null,2));
})().catch(e=>{console.error(JSON.stringify({passed:checks.length,failed:1,error:e.message.split('\n')[0]}));process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server)server.kill('SIGTERM');});

// Consolidated real Chrome acceptance. Disposable HTTPS fixture + mocked OIDC only.
const { chromium } = require(process.env.PLAYWRIGHT_CORE_MODULE || 'playwright-core');
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs/promises');
const root = path.resolve(__dirname, '../..');
const out = process.env.PHASE5_EVIDENCE;
if (!out) throw Error('PHASE5_EVIDENCE must point to a test evidence directory');
const checks = [], errors = [], failures = [], servers = [];
let browser, activePage;
function assert(value, message) { if (!value) throw Error(message); }
async function check(name, work) { try { await work(); checks.push(name); } catch (error) { if (activePage) { await activePage.screenshot({path:path.join(out,"failure.png"),fullPage:true}).catch(()=>{}); await fs.writeFile(path.join(out,"failure-page.txt"), await activePage.locator("body").innerText()).catch(()=>{}); } failures.push({ name, message: error.message.split('\n')[0] }); throw error; } }
async function fixture(role) {
  const port = await new Promise(resolve => { const server = net.createServer(); server.listen(0,'127.0.0.1',()=>{const port=server.address().port;server.close(()=>resolve(port));}); });
  const server = spawn(path.join(root,'.venv/bin/python'), ['-B',path.join(root,'backend/tests/sso_browser_server.py'),'--port',String(port),'--revision','007','--role',role,'--protected-content','--seed-policy'], {cwd:root,stdio:['ignore','ignore','pipe']});
  servers.push(server); server.stderr.on('data',()=>{});
  const origin = `https://localhost:${port}`;
  const context = await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:1440,height:1000}});
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === origin) return route.continue();
    // Never contact Microsoft or other external services in acceptance tests.
    if (url.hostname === 'login.microsoftonline.com') return route.fulfill({status:302,headers:{location:origin+'/'},body:''});
    return route.fulfill({status:200,body:'',contentType:'text/plain'});
  });
  let ready = false;
  for (let attempt=0;attempt<150;attempt++) {
    try { if ((await context.request.get(origin+'/ready')).status()===200) {ready=true;break;} } catch {}
    if (server.exitCode!==null) throw Error('Isolated HTTPS fixture exited');
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert(ready,'Isolated revision 007 fixture did not become ready');
  const page=await context.newPage(); activePage=page; page.on('pageerror',error=>errors.push(error.message)); page.on('dialog',dialog=>dialog.accept());
  return {origin,context,page};
}
(async()=>{
  browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
  const user=await fixture('User');
  await check('User bookmark login route /chat and clean login',async()=>{
    await user.page.goto(user.origin+'/chat');
    const button=user.page.getByRole('button',{name:'Sign in',exact:true}); await button.waitFor();
    assert(await button.locator('svg,img').count()===0,'Logo remains in Sign in');
    assert(await user.page.getByRole('alert').count()===0,'Anonymous login warning');
    await button.click(); await user.page.getByRole('heading',{name:'Your AI assistant',exact:true}).waitFor({timeout:10000});
  });
  await check('User cannot access privileged APIs',async()=>assert((await user.context.request.get(user.origin+'/api/policies')).status()===403,'User policy access allowed'));
  await check('User refresh restores chatbot session',async()=>{await user.page.reload();await user.page.getByRole('heading',{name:'Your AI assistant',exact:true}).waitFor();});
  await user.context.close();
  const {origin,context,page}=await fixture('Admin');
  await page.goto(origin+'/'); await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await check('Admin callback and secure 120-minute cookie',async()=>{
    await page.getByTitle('Sign out',{exact:true}).waitFor();
    const cookie=(await context.cookies()).find(cookie=>cookie.name==='__Host-governance-session');
    assert(cookie&&cookie.secure&&cookie.httpOnly&&cookie.sameSite==='Lax','Cookie security flags');
    const me=await (await context.request.get(origin+'/api/sso/me')).json();
    const remaining=(Date.parse(me.expires_at)-Date.parse(me.server_now))/1000;
    assert(remaining>7100&&remaining<=7200,'Absolute session duration');
    assert(await page.evaluate(()=>sessionStorage.getItem('governance-token'))===null,'Session credential in browser storage');
  });
  await check('Missing CSRF denied',async()=>assert((await context.request.post(origin+'/api/sso/logout')).status()===403,'CSRF bypass'));
  for(const [route,title] of [['/policies','Policy management'],['/playground','AI playground'],['/reviews','Human review'],['/history','Validation history'],['/reports','Audit & reports'],['/analytics','Compliance analytics'],['/settings','Settings & diagnostics']]) {
    await check('Admin navigation '+route,async()=>{await page.goto(origin+route);await page.getByRole('heading',{name:title,exact:true}).waitFor();assert(await page.locator('.environment-banner').count()===0,'Provider banner remains');});
  }
  await check('Settings sessions and analytics consumption',async()=>{
    await page.getByRole('heading',{name:'Workspace sessions',exact:true}).waitFor(); await page.getByRole('button',{name:'Refresh sessions',exact:true}).click();
    await page.getByText('Active · this page',{exact:true}).waitFor();
    await page.goto(origin+'/analytics');await page.getByRole('heading',{name:'AI Usage & Consumption',exact:true}).waitFor();
    await page.getByRole('progressbar',{name:'Daily request reservations'}).waitFor();
  });
  await check('Playground ALLOW BLOCK REDACT and HUMAN_REVIEW',async()=>{
    await page.goto(origin+'/playground');
    for(const [input,decision] of [['Explain safe governance','ALLOW'],['sk-syntheticnotarealkey000000000000000000000','BLOCK'],['Email synthetic@example.test','REDACT'],['internal-only browser review','HUMAN_REVIEW']]) {
      await page.getByLabel('User prompt',{exact:true}).fill(input);await page.getByRole('button',{name:/Run governed request/}).click();await page.getByText('Final decision: '+decision,{exact:true}).waitFor();
    }
  });
  await check('Protected Human Review assignment, reveal and resolution',async()=>{
    await page.goto(origin+'/reviews'); await page.getByRole('button',{name:'Open review',exact:true}).first().click();
    await page.getByLabel('Assigned reviewer username').fill('Synthetic User');await page.getByRole('button',{name:'Save assignment',exact:true}).click();
    await page.getByRole('button',{name:'Reveal original prompt',exact:true}).click();
    assert(await page.getByLabel('Original user prompt').textContent()==='internal-only browser review','Exact prompt mismatch');
    await page.getByRole('button',{name:'Hide original prompt',exact:true}).click();
    await page.getByRole('button',{name:'approve',exact:true}).first().click();await page.getByText('Review approve recorded.',{exact:true}).waitFor();
    assert(await page.getByLabel('Original user prompt').count()===0,'Plaintext retained after disposition');
  });
  await check('Audit date Apply/Clear and no export buttons',async()=>{
    await page.goto(origin+'/reports'); const today=new Date().toISOString().slice(0,10);
    await page.getByLabel('Start date',{exact:true}).fill(today);await page.getByLabel('End date',{exact:true}).fill(today);await page.getByRole('button',{name:'Apply Filter',exact:true}).click();
    await page.getByText(/Applied range \(UTC\)/).waitFor();
    for(const tab of ['Policy history','Governance execution history','Administrative history']) await page.getByRole('button',{name:tab,exact:true}).click();
    await page.getByRole('button',{name:'Clear Filter',exact:true}).click();
    assert(await page.getByLabel('Start date',{exact:true}).inputValue()==='','Filter not cleared');
    assert(await page.getByRole('button',{name:/Export JSON|Export CSV/}).count()===0,'Export buttons remain');
  });
  await check('Policy draft lifecycle',async()=>{
    await page.goto(origin+'/policies/new');await page.getByLabel('Policy name',{exact:true}).fill('Phase 5 Browser Draft');await page.getByRole('button',{name:'Save draft',exact:true}).click();
    await page.getByRole('heading',{name:'Policy management',exact:true}).waitFor();
    for(const operation of ['submit','approve','publish']) {await page.getByRole('row').filter({hasText:'Phase 5 Browser Draft'}).getByRole('button',{name:operation,exact:true}).click();await page.getByText('Policy '+operation+' completed.',{exact:true}).waitFor();}
  });
  for(const [label,width,height] of [['desktop',1440,1000],['tablet',820,1180],['mobile',390,844]]) {
    await page.setViewportSize({width,height});
    for(const route of ['/policies','/playground','/reviews','/history','/reports','/analytics','/settings']) await check('Responsive '+label+' '+route,async()=>{
      await page.goto(origin+route);await page.locator('main h1').waitFor();await page.waitForFunction(()=>document.querySelectorAll('.skeleton').length===0);if(route==='/settings')await page.getByRole('heading',{name:'Workspace sessions',exact:true}).waitFor();
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),'Horizontal page overflow');
    });
    await page.screenshot({path:path.join(out,'phase5-'+label+'.png'),fullPage:true});
  }
  await check('Manual logout returns clean login',async()=>{
    await page.getByTitle('Sign out',{exact:true}).click();await page.getByRole('button',{name:'Sign in',exact:true}).waitFor();assert(await page.getByRole('alert').count()===0,'Logout warning');
  });
  await context.close();
})().catch(error=>{if(!failures.length)failures.push({name:'Runner',message:error.message.split('\n')[0]});}).finally(async()=>{
  if(browser)await browser.close();
  for(const server of servers) if(server.exitCode===null){server.kill('SIGTERM');await new Promise(resolve=>{const timer=setTimeout(()=>{server.kill('SIGKILL');resolve();},5000);server.once('exit',()=>{clearTimeout(timer);resolve();});});}
  const result={scope:'real headless Chrome, isolated HTTPS revision 007, mocked OIDC/providers; no external services',passed:checks.length,failed:failures.length+errors.length,checks,failures,errors};
  await fs.writeFile(path.join(out,'browser.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));if(result.failed)process.exitCode=1;
});

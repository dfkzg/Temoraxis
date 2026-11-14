const {chromium}=require('playwright');const assert=require('node:assert/strict');const fs=require('node:fs/promises');const path=require('node:path');
(async()=>{
 const browser=await chromium.launch();const context=await browser.newContext(),p=await context.newPage();const base=process.env.PAGES_TEST_URL;
 await p.goto(base+'/Temoraxis/');await p.evaluate(async()=>{const c=await caches.open('unrelated-project');await c.put('/unrelated',new Response('keep me'));});
 await p.goto(base+'/Temoraxis/app/planner.html');await p.evaluate(async()=>{await navigator.serviceWorker.register('sw.js');await Promise.race([navigator.serviceWorker.ready,new Promise((_,reject)=>setTimeout(()=>reject(Error('Worker registration timeout')),10000))]);});await p.reload();await p.waitForFunction(()=>!!navigator.serviceWorker.controller);
 const manifest=await p.evaluate(async()=>await(await fetch('manifest.webmanifest')).json());assert.equal(manifest.scope,'/Temoraxis/app/');assert.equal(manifest.start_url,'/Temoraxis/app/planner.html');assert(manifest.icons.every(x=>x.src.startsWith('/Temoraxis/app/')));
 const cacheKeys=await p.evaluate(async()=>{return await caches.keys();});assert(cacheKeys.includes('unrelated-project'),'service worker erased another project cache');
 const assets=await p.evaluate(async()=>{const c=await caches.open('temoraxis-app:/Temoraxis/app/:v1');return (await c.keys()).map(r=>new URL(r.url).pathname);});assert(assets.includes('/Temoraxis/app/planner.html'));assert(assets.every(x=>x.startsWith('/Temoraxis/app/')));
 await context.setOffline(true);await p.reload();assert.equal(await p.locator('#page-tasks').isVisible(),true);await p.goto(base+'/Temoraxis/app/Start_page.html');assert.equal(await p.locator('.title').innerText(),'Экспресс-панель');await context.close();
 const owner=await browser.newContext();const setup=await owner.newPage();await setup.goto(base+'/Temoraxis/setup/');assert.equal(await setup.locator('#sql').inputValue(),await fs.readFile(path.resolve(__dirname,'../supabase/schema.sql'),'utf8'));assert.equal(await setup.locator('meta[name="robots"]').getAttribute('content'),'noindex');
 const official=await browser.newContext({serviceWorkers:'block'});await official.route('https://dfkzg.github.io/Temoraxis/app/**',async route=>{
  const name=new URL(route.request().url()).pathname.split('/').pop();if(!['planner.html','icon.svg','manifest.webmanifest','icon-180.png'].includes(name))return route.abort();
  return route.fulfill({path:path.resolve(__dirname,'../dist/pages/app',name)});
 });const app=await official.newPage();await app.goto('https://dfkzg.github.io/Temoraxis/app/planner.html');assert.equal(await app.locator('#psync-kind').inputValue(),'supabase','official web app must default to cloud');assert.equal(await app.locator('meta[name="robots"]').getAttribute('content'),'noindex');
 await browser.close();console.log('PASS: Pages project-prefix manifest/offline both pages, isolated service worker cache, owner setup SQL, official cloud default');
})();

const {chromium}=require('playwright');const assert=require('node:assert/strict');
const BASE=process.env.PLANNER_TEST_URL;const CLOUD='https://udrlbmlofdzevwvzssfw.supabase.co';
const INVITE='test-invitation-only-123456';
(async()=>{
 const browser=await chromium.launch();const users=new Map(),tokens=new Map(),refreshes=new Map(),documents=new Map();let refreshCount=0,sequence=0,delayedRead=null;
 function session(user){const token='session-'+(++sequence),refresh='refresh-'+sequence;tokens.set(token,user);refreshes.set(refresh,user);return {access_token:token,refresh_token:refresh,expires_in:3600,expires_at:Math.floor(Date.now()/1000)+3600,user:{id:user.id,email:user.email}};}
 async function context(){const c=await browser.newContext();await c.route(CLOUD+'/**',async route=>{
  const r=route.request(),url=new URL(r.url()),body=r.postDataJSON()||{},headers=r.headers();
  const respond=(status,data)=>route.fulfill({status,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify(data)});
  if(r.method()==='OPTIONS')return route.fulfill({status:204,headers:{'access-control-allow-origin':'*','access-control-allow-headers':'apikey,authorization,content-type','access-control-allow-methods':'GET,POST,OPTIONS'}});
  assert(headers.apikey?.startsWith('sb_publishable_'));
  if(url.pathname==='/auth/v1/signup'){
   const user={email:body.email,id:require('node:crypto').randomUUID(),joined:false,confirmed:!body.email.startsWith('confirm')};users.set(body.email,user);
   return respond(200,user.confirmed?session(user):{user:{id:user.id,email:user.email}});
  }
  if(url.pathname==='/auth/v1/token'){
   if(url.searchParams.get('grant_type')==='refresh_token'){
    refreshCount++;const u=refreshes.get(body.refresh_token);return u?respond(200,session(u)):respond(400,{error:'invalid_grant'});
   }
   const u=users.get(body.email);if(!u||body.password!=='test-cloud-password')return respond(400,{code:'invalid_credentials'});
   if(!u.confirmed)return respond(400,{code:'email_not_confirmed'});
   return respond(200,session(u));
  }
  const token=headers.authorization?.replace('Bearer ',''),user=tokens.get(token);
  if(!user)return respond(401,{message:'expired'});
  if(url.pathname==='/auth/v1/logout'){assert.equal(url.searchParams.get('scope'),'local');tokens.delete(token);return respond(200,{});}
  if(url.pathname==='/rest/v1/rpc/temoraxis_join'){
   if(!user.joined&&body.p_invite_code!==INVITE)return respond(403,{message:'Неверный код приглашения.'});user.joined=true;return respond(200,true);
  }
  if(!user.joined)return respond(403,{message:'not invited'});
  if(url.pathname==='/rest/v1/temoraxis_documents'){
   assert.equal(url.searchParams.get('user_id'),'eq.'+user.id);
   if(delayedRead?.email===user.email){const gate=delayedRead;delayedRead=null;gate.started();await gate.wait;}
   const d=documents.get(user.id);return respond(200,d?[d]:[]);
  }
  if(url.pathname==='/rest/v1/rpc/temoraxis_push'){
   const current=documents.get(user.id),rev=current?.revision||0;
   if(body.p_expected_revision!==rev)return respond(200,{conflict:true,revision:rev});
   const value={revision:rev+1,document:body.p_document,updated_at:new Date().toISOString()};documents.set(user.id,value);return respond(200,{revision:value.revision});
  }
  throw Error('Unexpected cloud request: '+url.pathname);
 });return c;}
 const contexts=[await context(),await context(),await context()];const [a,b,c]=await Promise.all(contexts.map(v=>v.newPage()));
 for(const p of [a,b,c]){await p.goto(BASE+'/planner.html');await p.click('[data-page="settings"]');await p.locator('.psync-launch').click();await p.selectOption('#psync-kind','supabase');assert.equal(await p.locator('#psync-url-label').isVisible(),false);}
 async function auth(p,email,register=false,invite=INVITE){await p.fill('#psync-login',email);await p.fill('#psync-password','test-cloud-password');await p.fill('#psync-invite',invite);await p.click(register?'#psync-register':'#psync-login-btn');await p.waitForFunction(()=>document.getElementById('psync-auth').hidden);}
 async function sync(p){await p.click('#psync-now');await p.waitForFunction(()=>!['Проверяю изменения…','Подключение…'].includes(document.getElementById('psync-status').textContent));}
 await auth(a,'first@example.test',true);await auth(b,'first@example.test');
 await a.evaluate(()=>createTask({id:'cloud-case',title:'С телефона',date:todayKey(),repeat:'daily'}));await sync(a);await sync(b);assert.equal(await b.evaluate(()=>getTask('cloud-case').title),'С телефона');
 await a.evaluate(()=>updateTask('cloud-case',{title:'Правка А'}));await b.evaluate(()=>updateTask('cloud-case',{title:'Правка Б'}));await sync(a);await sync(b);assert.equal(await b.locator('#psync-conflict').isVisible(),true);assert.equal(await b.evaluate(()=>getTask('cloud-case').title),'Правка Б');
 await b.click('#psync-pull');await b.waitForFunction(()=>getTask('cloud-case').title==='Правка А');assert.equal(await b.evaluate(()=>JSON.parse(localStorage.getItem('planner_sync_recovery_v1')).document.tasks[0].title),'Правка Б');
 await b.evaluate(()=>setTaskDone('cloud-case',todayKey()));await sync(b);await sync(a);assert.equal(await a.evaluate(()=>taskByDate('cloud-case',todayKey()).status),'done');
 await a.evaluate(()=>{const k='planner_sync_connection_v1',v=JSON.parse(localStorage.getItem(k));v.expiresAt=0;localStorage.setItem(k,JSON.stringify(v));});await sync(a);assert(refreshCount>0,'expired session was not refreshed');
 await b.evaluate(()=>hardDeleteTask('cloud-case'));await sync(b);await sync(a);assert.equal(await a.evaluate(()=>getTask('cloud-case').deleted),true);
 await auth(c,'second@example.test',true);await sync(c);assert.equal(await c.evaluate(()=>getTask('cloud-case')),null,'another account received user data');
 // Reusing a device for another account must require explicit handling of local data.
 await a.click('#psync-logout');await auth(a,'second@example.test');await sync(a);assert.equal(await a.locator('#psync-conflict').isVisible(),true);assert.equal(documents.get(users.get('second@example.test').id).document.tasks.length,0);
 let beginRead,releaseRead;const began=new Promise(resolve=>beginRead=resolve),gate=new Promise(resolve=>releaseRead=resolve);delayedRead={email:'second@example.test',started:beginRead,wait:gate};
 const firstAuth=await b.evaluate(()=>JSON.parse(localStorage.getItem('planner_sync_connection_v1')));
 const pending=a.evaluate(()=>PlannerSync.sync('pull'));await began;await a.evaluate(auth=>localStorage.setItem('planner_sync_connection_v1',JSON.stringify(auth)),firstAuth);releaseRead();await pending;
 assert.equal(await a.evaluate(()=>getTask('cloud-case').deleted),true,'cross-tab account change applied another account document');assert.match(await a.locator('#psync-status').innerText(),/Аккаунт изменился/);
 const denied=await (await context()).newPage();await denied.goto(BASE+'/planner.html');await denied.click('[data-page="settings"]');await denied.locator('.psync-launch').click();await denied.selectOption('#psync-kind','supabase');await denied.fill('#psync-login','uninvited@example.test');await denied.fill('#psync-password','test-cloud-password');await denied.fill('#psync-invite','wrong-code');await denied.click('#psync-register');await denied.waitForFunction(()=>document.getElementById('psync-status').textContent.includes('Неверный код'));
 assert.equal(await denied.evaluate(()=>localStorage.getItem('planner_sync_connection_v1')),null);await auth(denied,'uninvited@example.test');
 await b.evaluate(()=>{const k='planner_sync_connection_v1',v=JSON.parse(localStorage.getItem(k));v.expiresAt=0;v.refreshToken='invalid-refresh-token';localStorage.setItem(k,JSON.stringify(v));});await sync(b);assert.match(await b.locator('#psync-status').innerText(),/Сессия истекла/);assert.equal(await b.evaluate(()=>getTask('cloud-case').deleted),true);
 const confirmation=await (await context()).newPage();await confirmation.goto(BASE+'/planner.html');await confirmation.click('[data-page="settings"]');await confirmation.locator('.psync-launch').click();await confirmation.selectOption('#psync-kind','supabase');
 await confirmation.fill('#psync-login','confirm@example.test');await confirmation.fill('#psync-password','test-cloud-password');await confirmation.fill('#psync-invite',INVITE);await confirmation.click('#psync-register');await confirmation.waitForFunction(()=>document.getElementById('psync-status').textContent.includes('Проверьте почту'));
 assert.equal(await confirmation.evaluate(()=>localStorage.getItem('planner_sync_connection_v1')),null);assert.equal(await confirmation.locator('#psync-password').inputValue(),'');
 users.get('confirm@example.test').confirmed=true;await auth(confirmation,'confirm@example.test');
 const account=await confirmation.evaluate(()=>JSON.parse(localStorage.getItem('planner_sync_connection_v1')));tokens.delete(account.token);await sync(confirmation);assert(refreshCount>1,'401 did not trigger a refresh');
 // Auth callback tokens are removed and are never trusted as a signed-in identity.
 const callback=await (await context()).newPage();await callback.goto(BASE+'/planner.html#access_token=untrusted&refresh_token=untrusted');assert.equal(new URL(callback.url()).hash,'');assert.equal(await callback.evaluate(()=>localStorage.getItem('planner_sync_connection_v1')),null);
 await browser.close();console.log('PASS: cloud auth/invites, two-device sync, conflicts/recovery, recurring completion/deletion, account isolation/switch, token refresh, email confirmation, URL token cleanup');
})();

(function(){
'use strict';
const AUTH='planner_sync_connection_v1', BASE='planner_sync_baseline_v1', RECOVERY='planner_sync_recovery_v1', OWNER='planner_sync_owner_v1';
const KEYS={tasks:'planner_tasks_v1',clock:'planner_clock_v1',dates:'planner_special_dates_v1',settings:'planner_settings_v1',start:'vivaldi_startpage_v3'};
let autoTimer=null, observedDocument=null, autoPaused=false;
let busy=false, remoteConflict=null, previousFocus=null, previousOverflow='', nativeTimer=null, selectedBackend=null;
const read=(key,fallback)=>{try{const value=JSON.parse(localStorage.getItem(key));return value===null?fallback:value;}catch(_){return fallback;}};
const write=(key,value)=>localStorage.setItem(key,JSON.stringify(value));
const canonical=value=>JSON.stringify(sortObject(value));
function sortObject(value){if(Array.isArray(value))return value.map(sortObject);if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(key=>[key,sortObject(value[key])]));return value;}
async function hash(value){const bytes=new TextEncoder().encode(canonical(value));const digest=await crypto.subtle.digest('SHA-256',bytes);return [...new Uint8Array(digest)].map(byte=>byte.toString(16).padStart(2,'0')).join('');}
function documentSnapshot(){const settings=read(KEYS.settings,{});const clock=typeof clockData==='function'?clockData():read(KEYS.clock,{overrides:{},sources:{},threshold:15,custom:[]});return{tasks:typeof getAllTasks==='function'?getAllTasks(true):read(KEYS.tasks,[]),clock,specialDates:read(KEYS.dates,[]),tags:settings.tags||[],startPage:read(KEYS.start,null)};}
function validateDocument(value){
 if(!value||typeof value!=='object'||!Array.isArray(value.tasks)||!value.clock||!Array.isArray(value.specialDates)||!Array.isArray(value.tags)||value.tags.some(tag=>typeof tag!=='string'))throw Error('Сервер вернул некорректные данные.');
 const id=value=>typeof value==='string'&&/^[A-Za-z0-9_-]{1,128}$/.test(value);
 const subtasks=value=>Array.isArray(value)&&value.every(sub=>sub&&typeof sub.title==='string'&&id(sub.id));
 const slots=value=>Array.isArray(value)&&value.length===288&&value.every(slot=>slot===null||(slot&&typeof slot.label==='string'&&/^#[0-9a-f]{6}$/i.test(slot.color)));
 const clock=value.clock;
 if(!clock.overrides||typeof clock.overrides!=='object'||!Array.isArray(clock.custom)||!Object.values(clock.overrides).every(slots)||clock.custom.some(t=>!t||!id(t.id)||typeof t.name!=='string'||!slots(t.slots)))throw Error('Некорректные шаблоны часов.');
 if(clock.weekdayTemplates&&(typeof clock.weekdayTemplates!=='object'||Array.isArray(clock.weekdayTemplates)||Object.entries(clock.weekdayTemplates).some(([day,t])=>! /^[0-6]$/.test(day)||!t||typeof t.name!=='string'||!slots(t.slots))))throw Error('Некорректные шаблоны дней недели.');
 if(new Set(value.tasks.map(t=>t?.id)).size!==value.tasks.length||value.tasks.some(t=>!t||!id(t.id)||typeof t.title!=='string'||!['low','mid','high'].includes(t.priority)||!Array.isArray(t.tags)||t.tags.some(tag=>typeof tag!=='string')||!subtasks(t.subtasks)||!Array.isArray(t.repeatDays)))throw Error('Некорректные задачи на сервере.');
 for(const task of value.tasks){if(task.occurrences&&(typeof task.occurrences!=='object'||Array.isArray(task.occurrences)||Object.entries(task.occurrences).some(([date,record])=>!/^\d{4}-\d{2}-\d{2}$/.test(date)||!record||!['todo','waiting','done','missed'].includes(record.status||'todo')||(record.subtasks&&!subtasks(record.subtasks)))))throw Error('Некорректные отметки повторений.');}
 if(value.specialDates.some(d=>!d||typeof d.name!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(d.date)))throw Error('Некорректные особые даты.');
 if(value.startPage!==null){if(!value.startPage||!Array.isArray(value.startPage.groups)||value.startPage.groups.some(g=>!g||!id(g.id)||typeof g.name!=='string'||!Array.isArray(g.links)||g.links.some(l=>!l||!id(l.id)||typeof l.name!=='string'||typeof l.url!=='string'||!/^https?:\/\//i.test(l.url))))throw Error('Некорректные ссылки экспресс-панели.');}
}
function hasUserData(doc){return doc.tasks.length||doc.specialDates.length||doc.tags.length||doc.clock.custom.length||Object.keys(doc.clock.weekdayTemplates||{}).length||Object.keys(doc.clock.overrides).length||doc.startPage!==null;}
function setStatus(text){document.getElementById('psync-status').textContent=text;document.querySelectorAll('[data-sync-summary]').forEach(element=>element.textContent=text);}
function localServerURL(){return location.protocol==='https:'?location.origin:(location.hostname==='127.0.0.1'||location.hostname==='localhost')?location.origin:'';}
function defaultBackend(){const c=window.TemoraxisCloud;if(!c?.publishableKey)return 'server';const app=new URL(c.appURL);return window.PlannerAndroid||(location.origin===app.origin&&location.pathname.startsWith(app.pathname.slice(0,app.pathname.lastIndexOf('/')+1)))?'supabase':'server';}
function currentBackend(){const auth=read(AUTH,{});return auth.token?(auth.backend||'server'):(selectedBackend||defaultBackend());}
function connectionId(auth){return JSON.stringify([auth.backend||'server',auth.url,auth.username,auth.userId||'']);}
function assertConnection(id){if(id!==connectionId(read(AUTH,{})))throw Error('Аккаунт изменился. Повторите синхронизацию.');}
function normalizeURL(raw){const url=new URL(raw.trim());if(url.username||url.password||url.search||url.hash||!(url.protocol==='https:'||(url.protocol==='http:'&&['localhost','127.0.0.1'].includes(url.hostname)&&!window.PlannerAndroid)))throw Error('Нужен адрес сервера с HTTPS.');return url.origin;}
async function api(path,options={}){
 const auth=read(AUTH,{}),url=options.url||auth.url;
 if(options.expectedConnection)assertConnection(options.expectedConnection);
 if(auth.backend==='supabase'&&!options.anonymous){
  const id=connectionId(auth);
  return window.TemoraxisSupabase.api(path,options,auth,updated=>{assertConnection(id);write(AUTH,updated);});
 }
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
 try{const response=await fetch(url+path,{method:options.method||'GET',headers:{'Content-Type':'application/json',...(auth.token&&!options.anonymous?{'Authorization':'Bearer '+auth.token}:{})},body:options.body?JSON.stringify(options.body):undefined,signal:controller.signal,cache:'no-store'});let result;try{result=await response.json();}catch(_){throw Error('По этому адресу нет сервера планёра.');}if(!response.ok){const error=Error(result.error||'Ошибка сервера');error.status=response.status;throw error;}return result;}catch(error){if(error.name==='AbortError')throw Error('Сервер не ответил за 15 секунд.');throw error;}finally{clearTimeout(timer);}
}
function renderConnection(){
 const auth=read(AUTH,{}),connected=!!auth.token,backend=currentBackend(),cloud=backend==='supabase';
 document.getElementById('psync-kind').value=backend;document.getElementById('psync-kind').disabled=connected;
 document.getElementById('psync-url-label').hidden=cloud;
 document.getElementById('psync-login-label').textContent=cloud?'Email':'Логин';
 document.getElementById('psync-login').type=cloud?'email':'text';
 document.getElementById('psync-user').textContent=connected?'Аккаунт: '+auth.username:'';
 document.getElementById('psync-auth').hidden=connected;document.getElementById('psync-connected').hidden=!connected;
 document.getElementById('psync-url').value=auth.url||localServerURL();document.getElementById('psync-url').disabled=connected;
 document.getElementById('psync-user').textContent=connected?'Аккаунт: '+auth.username:'';
 document.getElementById('psync-recover').hidden=!read(RECOVERY,null);
 document.getElementById('psync-file-note').hidden=location.protocol!=='file:';
 if(cloud)document.getElementById('psync-file-note').textContent='Для подключения откройте веб-версию Temoraxis или Android-приложение.';
}
async function authenticate(register){
 if(busy)return;busy=true;setStatus('Подключение…');
 try{
  if(location.protocol==='file:')throw Error('Для входа на ПК откройте HTTPS-адрес размещённого сервера. Старые данные перенесите через экспорт и импорт JSON.');
  const backend=currentBackend(),username=document.getElementById('psync-login').value.trim(),password=document.getElementById('psync-password').value,inviteCode=document.getElementById('psync-invite').value;
  let result,url;
  if(backend==='supabase'){
   result=await window.TemoraxisSupabase.authenticate(register,username,password,inviteCode);
   if(result.confirmationRequired){setStatus('Проверьте почту и подтвердите email. Затем вернитесь и войдите с кодом приглашения.');return;}
   url=result.url;
  }else{
   url=normalizeURL(document.getElementById('psync-url').value);
   result=await api(register?'/api/register':'/api/login',{url,method:'POST',anonymous:true,body:{username,password,inviteCode}});
   result={...result,url,backend:'server'};
  }
  const owner=read(OWNER,null);write(AUTH,{...result,accountChanged:!!owner&&(owner.url!==url||owner.username!==result.username)});localStorage.removeItem(BASE);renderConnection();setStatus('Вход выполнен. Синхронизация начнётся автоматически.');
 }catch(error){setStatus(error.message);}finally{document.getElementById('psync-password').value='';document.getElementById('psync-invite').value='';busy=false;}
}
function editingLocalData(){const modal=document.getElementById('taskModalBg');return !!((modal&&!modal.hidden)||document.querySelector('.modal-bg.open')||(typeof ClockUI!=='undefined'&&ClockUI.dragging));}
async function applyDocument(doc){
 if(editingLocalData())throw Error('Завершите редактирование перед загрузкой данных с сервера.');
 validateDocument(doc);
 const previous=documentSnapshot();write(RECOVERY,{savedAt:new Date().toISOString(),owner:read(OWNER,null),document:previous});
 const settings=read(KEYS.settings,{}),entries={[KEYS.tasks]:doc.tasks,[KEYS.clock]:doc.clock,[KEYS.dates]:doc.specialDates,[KEYS.settings]:{...settings,tags:doc.tags}};
 if(doc.startPage!==null)entries[KEYS.start]=doc.startPage;
 const before=Object.fromEntries([...Object.keys(entries),KEYS.start].map(key=>[key,localStorage.getItem(key)]));
 try{for(const [key,value]of Object.entries(entries))write(key,value);if(doc.startPage===null)localStorage.removeItem(KEYS.start);}catch(error){for(const [key,value]of Object.entries(before))if(value===null)localStorage.removeItem(key);else localStorage.setItem(key,value);throw error;}
 if(typeof refreshPlannerViews==='function')refreshPlannerViews({preserveDetail:true});
 if(typeof data!=='undefined'&&typeof DEFAULT_DATA!=='undefined'&&typeof render==='function'){data=doc.startPage||structuredClone(DEFAULT_DATA);render();if(typeof renderStartSpecialDates==='function')renderStartSpecialDates();}
 rememberDocument();renderConnection();scheduleNative(true);
}
async function storeBaseline(revision,doc){const auth=read(AUTH,{}),id=connectionId(auth),value=await hash(doc);assertConnection(id);write(BASE,{url:auth.url,username:auth.username,revision,hash:value});write(OWNER,{url:auth.url,username:auth.username});if(auth.accountChanged)write(AUTH,{...read(AUTH,{}),accountChanged:false});}
function showConflict(remote){remoteConflict=remote;document.getElementById('psync-pull').hidden=!remote.document;document.getElementById('psync-empty').hidden=!!remote.document;document.getElementById('psync-conflict').hidden=false;setStatus('На устройстве и сервере разные изменения. Выберите версию; автоматической перезаписи не будет.');}
async function sync(force){
 if(busy)return;const auth=read(AUTH,{}),expectedConnection=connectionId(auth);if(!auth.token){setStatus('Сначала войдите в аккаунт.');return;}busy=true;setStatus('Проверяю изменения…');
 try{
  const remote=await api('/api/sync',{expectedConnection});if(remote.document)validateDocument(remote.document);
  assertConnection(expectedConnection);
  const local=documentSnapshot(),localHash=await hash(local),remoteHash=remote.document?await hash(remote.document):null;
  let baseline=read(BASE,null);if(baseline&&(baseline.url!==auth.url||baseline.username!==auth.username))baseline=null;
  if(!force&&auth.accountChanged&&hasUserData(local)){showConflict(remote);setStatus('На устройстве остались данные другого аккаунта. Загрузите данные нового аккаунта, начните с пустой копии или явно подтвердите перенос.');return;}
  if(remoteHash===localHash){assertConnection(expectedConnection);await storeBaseline(remote.revision,local);document.getElementById('psync-conflict').hidden=true;remoteConflict=null;setStatus('Устройства синхронизированы.');return;}
  if(force==='pull'){
   if(!remote.document)throw Error('На сервере пока нет данных.');
   if(await hash(documentSnapshot())!==localHash)throw Error('Локальные данные изменились во время загрузки. Повторите синхронизацию.');assertConnection(expectedConnection);await applyDocument(remote.document);assertConnection(expectedConnection);await storeBaseline(remote.revision,remote.document);setStatus('Данные сервера загружены. Предыдущая локальная копия сохранена.');
  }else if(force==='push'||remote.revision===0||(baseline&&remote.revision===baseline.revision)){
   const result=await api('/api/sync',{method:'PUT',expectedConnection,body:{expectedRevision:remote.revision,document:local}});assertConnection(expectedConnection);await storeBaseline(result.revision,local);setStatus('Данные отправлены на сервер.');
  }else if((baseline&&localHash===baseline.hash)||(!baseline&&!hasUserData(local))){
   if(await hash(documentSnapshot())!==localHash)throw Error('Локальные данные изменились во время загрузки. Повторите синхронизацию.');assertConnection(expectedConnection);await applyDocument(remote.document);assertConnection(expectedConnection);await storeBaseline(remote.revision,remote.document);setStatus('Изменения с другого устройства загружены.');
  }else {showConflict(remote);return;}
  remoteConflict=null;document.getElementById('psync-conflict').hidden=true;
 }catch(error){if(error.status===409)setStatus('Сервер изменился во время отправки. Повторите синхронизацию, чтобы сравнить версии.');else if(error.status===401)setStatus('Сессия истекла. Выйдите и войдите заново; локальные данные сохраняются.');else setStatus(error.message==='Failed to fetch'?'Нет подключения к серверу. Локальные изменения сохраняются.':error.message);}
 finally{busy=false;}
}
// Compare only shared data: covers task saves, imports, templates and the start page,
// without patching browser storage or reacting to token refreshes/local preferences.
function rememberDocument(){observedDocument=canonical(documentSnapshot());}
function queueAutoSync(delay=900){clearTimeout(autoTimer);autoTimer=setTimeout(runAutoSync,delay);}
function runAutoSync(){
 clearTimeout(autoTimer);autoTimer=null;
 if(autoPaused||!read(AUTH,{}).token||remoteConflict||document.hidden||!navigator.onLine)return;
 if(busy||editingLocalData()){queueAutoSync(1000);return;}
 sync();
}
function observeLocalChanges(){
 const current=canonical(documentSnapshot());
 if(observedDocument!==null&&current!==observedDocument){autoPaused=false;queueAutoSync();}
 observedDocument=current;
}
function scheduleNative(immediate=false){clearTimeout(nativeTimer);if(!window.PlannerAndroid)return;const send=()=>{
 try{const settings=read(KEYS.settings,{});const tasks=typeof getAllTasks==='function'?getAllTasks(true):read(KEYS.tasks,[]);PlannerAndroid.scheduleReminders(JSON.stringify({enabled:settings.notifications!==false,tasks:PlannerReminderRules.nativeTasks(tasks,read(KEYS.dates,[]))}));}catch(_){}
 };if(immediate)send();else nativeTimer=setTimeout(send,250);}
function importNativeCompletions(list){
 if(!window.PlannerAndroid)return;
 try{const records=list||JSON.parse(PlannerAndroid.pendingCompletions());for(const record of records){const tasks=read(KEYS.tasks,[]),task=tasks.find(t=>t.id===record.id);if(task){if(['daily','weekly'].includes(task.repeat))task.occurrences={...task.occurrences,[record.date]:{...task.occurrences?.[record.date],status:'done',updatedAt:new Date().toISOString()}};else task.status='done';task.updatedAt=new Date().toISOString();write(KEYS.tasks,tasks);}PlannerAndroid.acknowledgeCompletion(record.key);}if(records.length&&typeof refreshTaskState==='function')refreshTaskState();scheduleNative();}catch(_){setStatus('Не удалось применить отметку из Android. Освободите место в хранилище и откройте приложение снова.');}
}
function open(){previousFocus=document.activeElement;previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden';renderConnection();const backdrop=document.getElementById('psync-backdrop');backdrop.hidden=false;document.getElementById('psync-title').focus();}
function closeIfOpen(){const backdrop=document.getElementById('psync-backdrop');if(!backdrop||backdrop.hidden)return false;backdrop.hidden=true;document.body.style.overflow=previousOverflow;previousFocus?.focus?.({preventScroll:true});return true;}
function initialize(){
 const callback=new URLSearchParams(location.hash.slice(1));const emailCallback=callback.has('access_token')||callback.has('refresh_token')||callback.has('error_description');if(emailCallback)history.replaceState(null,'',location.pathname+location.search);
 const style=document.createElement('style');style.textContent=/*SYNC_CSS*/'';document.head.appendChild(style);
 const holder=document.createElement('div');holder.innerHTML=`<div class="psync-backdrop" id="psync-backdrop" hidden><section class="psync" role="dialog" aria-modal="true" aria-labelledby="psync-title"><div class="psync-header"><h2 id="psync-title" tabindex="-1">Синхронизация</h2><button id="psync-close" aria-label="Закрыть синхронизацию">✕</button></div><p class="psync-note">Создайте аккаунт Temoraxis и войдите в него на телефоне и ПК. Без интернета изменения сохраняются на устройстве.</p><p id="psync-status" role="status" aria-live="polite">Сервер пока не подключён.</p><p class="psync-note" id="psync-file-note">Для синхронизации на ПК откройте сайт размещённого сервера. Локальные HTML-файлы продолжают работать отдельно; данные можно перенести через JSON.</p><label>Подключение<select id="psync-kind"><option value="supabase">Облако Temoraxis</option><option value="server">Свой сервер</option></select></label><label id="psync-url-label">Адрес сервера<input id="psync-url" type="url" inputmode="url" placeholder="https://planner.example.ru" autocomplete="url"></label><div id="psync-auth"><label><span id="psync-login-label">Логин</span><input id="psync-login" autocomplete="username" minlength="3" maxlength="100"></label><label>Пароль — минимум 10 символов<input id="psync-password" type="password" autocomplete="current-password" minlength="10" maxlength="256"></label><label>Код приглашения — для первого входа<input id="psync-invite" autocomplete="off"></label><div class="psync-actions"><button class="psync-primary" id="psync-login-btn">Войти</button><button id="psync-register">Создать аккаунт</button></div></div><div id="psync-connected" hidden><p id="psync-user"></p><div class="psync-actions"><button class="psync-primary" id="psync-now">Синхронизировать</button><button id="psync-logout">Выйти</button></div><p class="psync-note">Изменения отправляются автоматически после сохранения. Данные с другого устройства проверяются каждые 15 секунд, пока приложение открыто и есть интернет. Локальные данные остаются на устройстве после выхода.</p></div><div id="psync-conflict" class="psync-warning" hidden><h3>Разные изменения на устройствах</h3><p>Выберите, какую версию сохранить. Загрузка с сервера заменит локальные данные; перед этим сохранится локальная копия для восстановления.</p><div class="psync-actions"><button id="psync-pull">Загрузить с сервера</button><button id="psync-empty" hidden>Начать с пустой копии</button><button id="psync-push">Отправить данные устройства</button></div></div><button id="psync-recover" hidden>Вернуть локальную копию до последней загрузки</button><p class="psync-note">Звуковые файлы и разрешения уведомлений настраиваются на каждом устройстве отдельно.</p></section></div>`;
 document.body.appendChild(holder.firstElementChild);
 document.getElementById('psync-kind').onchange=event=>{selectedBackend=event.target.value;renderConnection();};
 document.getElementById('psync-close').onclick=closeIfOpen;
 document.getElementById('psync-backdrop').addEventListener('click',event=>{if(event.target.id==='psync-backdrop')closeIfOpen();});
 document.getElementById('psync-login-btn').onclick=()=>authenticate(false);document.getElementById('psync-register').onclick=()=>authenticate(true);
 document.getElementById('psync-now').onclick=()=>{autoPaused=false;sync();};document.getElementById('psync-pull').onclick=()=>sync('pull');document.getElementById('psync-push').onclick=()=>sync('push');
 document.getElementById('psync-empty').onclick=async()=>{if(busy)return;try{await applyDocument({tasks:[],clock:{overrides:{},sources:{},custom:[],threshold:15},specialDates:[],tags:[],startPage:null});await sync();}catch(error){setStatus(error.message);}};
 document.getElementById('psync-logout').onclick=async()=>{if(busy)return;const leaving=read(AUTH,{}),id=connectionId(leaving);busy=true;try{if(leaving.backend==='supabase')await window.TemoraxisSupabase.logout(leaving);else await api('/api/logout',{method:'POST'});}catch(_){}finally{busy=false;}if(connectionId(read(AUTH,{}))!==id){renderConnection();return;}localStorage.removeItem(AUTH);localStorage.removeItem(BASE);remoteConflict=null;document.getElementById('psync-conflict').hidden=true;renderConnection();setStatus('Вы вышли. Локальные данные сохранены.');};
 document.getElementById('psync-recover').onclick=async()=>{const saved=read(RECOVERY,null);if(!saved)return;try{await applyDocument(saved.document);if(saved.owner){write(OWNER,saved.owner);const auth=read(AUTH,{});if(auth.token&&(auth.username!==saved.owner.username||auth.url!==saved.owner.url))write(AUTH,{...auth,accountChanged:true});}autoPaused=true;setStatus('Локальная копия восстановлена. Синхронизируйте её вручную.');}catch(error){setStatus(error.message);}};
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&closeIfOpen()){event.preventDefault();event.stopImmediatePropagation();}},true);
 const grid=document.querySelector('#page-settings .settings-grid');
 if(grid){const card=document.createElement('section');card.className='settings-card settings-wide';card.innerHTML='<h2>Синхронизация устройств</h2><p class="settings-help" data-sync-summary>Войдите в аккаунт для синхронизации телефона и ПК.</p><button class="btn-secondary psync-launch">Подключить аккаунт / синхронизировать</button>';card.querySelector('button').onclick=open;grid.prepend(card);if(typeof registerSettingsCard==='function')registerSettingsCard(card,'data',-1);}
 const controls=document.querySelector('.footer-bar .controls');if(controls){const button=document.createElement('button');button.className='psync-launch';button.textContent='Синхронизация';button.onclick=open;controls.appendChild(button);}
 if(typeof Store!=='undefined'){const original=Store.set.bind(Store);Store.set=(key,value)=>{const enabled=read(KEYS.settings,{}).notifications!==false;const success=original(key,value);if(success&&(key===KEYS.tasks||key===KEYS.dates||(key===KEYS.settings&&enabled!==(value.notifications!==false))))scheduleNative(true);return success;};}
 if(!window.PlannerAndroid&&matchMedia('(pointer:coarse)').matches){const input=document.getElementById('settingsSoundsFolder');if(input){input.removeAttribute('webkitdirectory');input.accept='audio/*';input.multiple=true;document.getElementById('settingsChooseSounds').textContent='Выбрать звуки';const help=input.closest('.settings-card')?.querySelector('.settings-help');if(help)help.textContent='Выберите аудиофайлы на этом устройстве. Можно выделить несколько файлов.';}}
 if(window.PlannerAndroid){
  if(typeof PlannerAndroid.openAppMenu==='function'){
   const launch=document.createElement('button');launch.type='button';launch.className='btn-secondary';launch.dataset.nativeAppMenu='';launch.textContent='Меню приложения';launch.onclick=()=>PlannerAndroid.openAppMenu();
   const permission=document.getElementById('settingsNotificationPermission');
   if(permission)permission.parentElement.appendChild(launch);
   else if(controls)controls.appendChild(launch);
  }
  const input=document.getElementById('settingsSoundsFolder');if(input){input.removeAttribute('webkitdirectory');input.accept='audio/*';input.multiple=true;document.getElementById('settingsChooseSounds').textContent='Выбрать звуки';const help=input.closest('.settings-card')?.querySelector('.settings-help');if(help)help.textContent='Выберите аудиофайлы для прослушивания в приложении. Их можно выделить несколько сразу.';}
  const notify=document.getElementById('settingsNotificationPermission');if(notify){notify.parentElement.querySelectorAll('.settings-help').forEach(paragraph=>{if(paragraph.textContent.includes('Напоминания работают, пока планёр открыт'))paragraph.textContent='Системные напоминания запланированных задач доступны и при свёрнутом приложении. Разрешите уведомления и точные напоминания Android; ограничения энергосбережения телефона могут влиять на время срабатывания.';});notify.disabled=false;notify.textContent='Разрешить уведомления Android';const exact=document.createElement('button');exact.className='btn-secondary';exact.textContent='Разрешить точные напоминания';exact.onclick=()=>PlannerAndroid.requestExactAlarms();notify.after(exact);const note=document.createElement('p');note.className='settings-help';note.textContent='Фоновые напоминания используют системный звук и громкость Android. После изменения задач на ПК откройте приложение с интернетом: задачи загрузятся автоматически.';notify.parentElement.appendChild(note);if(PlannerAndroid.runSystemTest){const test=document.createElement('button');test.className='btn-secondary';test.textContent='Тест системы';test.onclick=()=>PlannerAndroid.runSystemTest();notify.parentElement.appendChild(test);}}
  window.addEventListener('planner-native-resume',event=>importNativeCompletions(event.detail));importNativeCompletions();scheduleNative();
 }
 renderConnection();
 if(emailCallback){open();setStatus('Ссылка подтверждения открыта. Войдите в аккаунт с email, паролем и кодом приглашения.');}
 if(read(AUTH,{}).token)sync();
 rememberDocument();
 setInterval(observeLocalChanges,500);
 setInterval(runAutoSync,15000);
 window.addEventListener('online',()=>queueAutoSync(0));
 document.addEventListener('visibilitychange',()=>{if(!document.hidden){importNativeCompletions();runAutoSync();}});
 if(location.protocol==='https:'&&!window.PlannerAndroid&&'serviceWorker'in navigator)navigator.serviceWorker.register(new URL('sw.js',location.href)).catch(()=>{});
}
window.PlannerSync={open,closeIfOpen,sync,documentSnapshot,validateDocument,applyDocument,scheduleNative};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize);else initialize();
})();

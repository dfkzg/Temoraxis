/* Temoraxis REST transport. Uses browser fetch and Supabase APIs, no bundled SDK. */
(function(){
'use strict';
function error(message,status){return Object.assign(Error(message),{status});}
function config(){
 const c=window.TemoraxisCloud||{};
 if(!/^https:\/\/[a-z0-9]+\.supabase\.co$/.test(c.url||'')||!/^sb_publishable_[A-Za-z0-9_-]+$/.test(c.publishableKey||''))throw error('Облако ещё не настроено владельцем.',503);
 return c;
}
async function request(path,{method='GET',body,token}={}){
 const c=config(),controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
 try{
  const r=await fetch(c.url+path,{method,headers:{apikey:c.publishableKey,'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},...(body===undefined?{}:{body:JSON.stringify(body)}),signal:controller.signal,cache:'no-store'});
  let data=null;try{data=await r.json();}catch(_){if(r.ok&&r.status!==204)throw error('Облако вернуло некорректный ответ.',502);}
  if(!r.ok){
   const code=data?.code||data?.error_code;
   let message=data?.msg||data?.message||data?.error_description||data?.error||'Синхронизация временно недоступна.';
   if(['PGRST202','PGRST205','42P01','42883'].includes(code))message='Хранилище синхронизации ещё не настроено владельцем.';
   else if(code==='email_not_confirmed')message='Подтвердите email по письму и войдите снова.';
   else if(code==='invalid_credentials')message='Неверный email или пароль.';
   else if(code==='email_address_not_authorized')message='Письма для этого адреса ещё не настроены владельцем сервиса.';
   else if(r.status===429)message='Слишком много попыток. Подождите и попробуйте снова.';
   throw error(message,r.status);
  }
  return data;
 }catch(e){if(e.name==='AbortError')throw error('Облако не ответило за 15 секунд.',504);throw e;}finally{clearTimeout(timer);}
}
function session(data){
 if(!data?.access_token||!data?.refresh_token||!data?.user?.id||!data?.user?.email)throw error('Облако не вернуло сессию пользователя.',401);
 return {backend:'supabase',url:config().url,token:data.access_token,refreshToken:data.refresh_token,expiresAt:data.expires_at||Math.floor(Date.now()/1000)+(data.expires_in||3600),userId:data.user.id,username:data.user.email.toLowerCase()};
}
async function authenticate(register,email,password,inviteCode){
 email=email.trim().toLowerCase();
 if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))throw error('Укажите email для входа.',400);
 if(register&&password.length<10)throw error('Пароль должен содержать минимум 10 символов.',400);
 const path=register?'/auth/v1/signup?redirect_to='+encodeURIComponent(config().appURL):'/auth/v1/token?grant_type=password';
 const result=await request(path,{method:'POST',body:{email,password}});
 if(!result?.access_token)return {confirmationRequired:true};
 const auth=session(result);
 try{await request('/rest/v1/rpc/temoraxis_join',{method:'POST',token:auth.token,body:{p_invite_code:inviteCode.trim()}});}
 catch(e){try{await logout(auth);}catch(_){}throw e;}
 return auth;
}
async function refresh(auth,save){
 if(!auth.refreshToken)throw error('Сессия истекла. Войдите снова.',401);
 let result;try{result=await request('/auth/v1/token?grant_type=refresh_token',{method:'POST',body:{refresh_token:auth.refreshToken}});}catch(e){if(e.status===400||e.status===401)throw error('Сессия истекла. Войдите снова.',401);throw e;}
 const updated=session(result);
 if(updated.userId!==auth.userId||updated.username!==auth.username)throw error('Аккаунт изменился. Войдите снова.',401);
 const merged={...auth,...updated};save(merged);return merged;
}
async function api(path,options,auth,save){
 if(auth.url!==config().url)throw error('Адрес облака изменился. Войдите снова.',401);
 if((auth.expiresAt||0)<Date.now()/1000+60)auth=await refresh(auth,save);
 async function perform(){
  if(path==='/api/sync'&&options.method==='PUT'){
   const result=await request('/rest/v1/rpc/temoraxis_push',{method:'POST',token:auth.token,body:{p_expected_revision:options.body.expectedRevision,p_document:options.body.document}});
   if(result?.conflict)throw error('Данные изменились на другом устройстве.',409);
   if(!Number.isSafeInteger(result?.revision)||result.revision<1)throw error('Облако вернуло некорректную версию.',502);
   return result;
  }
  if(path==='/api/sync'){
   if(!/^[0-9a-f-]{36}$/i.test(auth.userId||''))throw error('Некорректная сессия пользователя.',401);
   const result=await request('/rest/v1/temoraxis_documents?select=revision,document,updated_at&user_id=eq.'+encodeURIComponent(auth.userId),{token:auth.token});
   if(!Array.isArray(result)||result.length>1)throw error('Облако вернуло некорректные данные.',502);
   const row=result[0];if(!row)return {revision:0,document:null};
   if(!Number.isSafeInteger(row.revision)||row.revision<1)throw error('Облако вернуло некорректную версию.',502);
   return {revision:row.revision,document:row.document,updated:row.updated_at};
  }
  throw error('Неизвестная операция синхронизации.',400);
 }
 try{return await perform();}catch(e){if(e.status!==401)throw e;auth=await refresh(auth,save);return perform();}
}
async function logout(auth){if(auth.url!==config().url)return;return request('/auth/v1/logout?scope=local',{method:'POST',token:auth.token});}
window.TemoraxisSupabase={authenticate,api,logout};
})();

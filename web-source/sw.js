const BASE=new URL('./',self.location.href).pathname;
const CACHE_PREFIX='temoraxis-app:'+BASE+':', CACHE=CACHE_PREFIX+'v1';
const FILES=['planner.html','Start_page.html','icon.svg','icon-180.png','icon-192.png','icon-512.png','manifest.webmanifest'].map(name=>BASE+name);
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(FILES))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith(CACHE_PREFIX)&&key!==CACHE).map(key=>caches.delete(key))))));
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 if(event.request.method!=='GET'||url.origin!==location.origin||url.pathname.startsWith('/api/'))return;
 const path=url.pathname===BASE?BASE+'planner.html':url.pathname;if(!FILES.includes(path))return;
 event.respondWith(fetch(event.request).then(response=>{if(response.ok){const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(path,copy));}return response;}).catch(()=>caches.match(path).then(response=>response||Response.error())));
});

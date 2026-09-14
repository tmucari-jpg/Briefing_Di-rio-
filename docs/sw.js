const CACHE='briefing-v3';
const ASSETS=['./','./index.html','./style.css?v=3','./app.js','./manifest.json'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  const url=new URL(e.request.url);
  if(url.pathname.endsWith('/news.json')){
    e.respondWith(fetch(e.request,{cache:'no-store'}).catch(()=>caches.match('./news.json')));
    return;
  }
  e.respondWith(caches.match(e.request).then(c=>c||fetch(e.request)));
});
const CACHE='briefing-v6';
const ASSETS=['./','./index.html','./style.css?v=4','./app.js?v=5','./manifest.json?v=2','./icon.svg'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  const url=new URL(e.request.url);
  if(url.pathname.endsWith('/news.json')||url.pathname.endsWith('/news-pt.json')||url.pathname.endsWith('/news-en.json')){
    const fallback=url.pathname.endsWith('/news-en.json')?'./news-en.json':url.pathname.endsWith('/news-pt.json')?'./news-pt.json':'./news.json';
    e.respondWith(fetch(e.request,{cache:'no-store'}).then(r=>{if(r.ok){const copy=r.clone();caches.open(CACHE).then(c=>c.put(fallback,copy));}return r;}).catch(()=>caches.match(fallback)));return;
  }
  e.respondWith(caches.match(e.request).then(c=>c||fetch(e.request)));
});
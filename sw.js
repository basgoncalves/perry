const C='perry-v9',F=['./','index.html','styles.css','app.js','manifest.json','icon.svg','icon-192.png','icon-512.png','biz/plan.html','biz/bgb/','biz/bgb/book.html','biz/bgb/basilio.html','biz/bgb/gwen.html','biz/bgb/site.css','biz/bookings/','biz/bgb-icon.svg','biz/bgb-192.png'];
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(F)))});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET'||!e.request.url.startsWith(self.location.origin))return;e.respondWith(fetch(e.request).then(r=>{const c=r.clone();caches.open(C).then(x=>x.put(e.request,c));return r}).catch(()=>caches.match(e.request)))});
self.addEventListener('push',e=>{let d={};try{d=e.data.json()}catch{d={title:'Perry',body:e.data?e.data.text():''}}
 e.waitUntil(self.registration.showNotification(d.title||'Perry',{body:d.body||'',icon:'icon-192.png',badge:'icon-192.png',data:{url:d.url||'/perry/'}}))});
self.addEventListener('notificationclick',e=>{e.notification.close();const u=e.notification.data.url;
 e.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(ws=>{for(const w of ws)if(w.url.includes(u))return w.focus();return clients.openWindow(u)}))});

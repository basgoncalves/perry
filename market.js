/* Market tab — heatmap of the ~60 biggest US companies (area = market cap,
   colour = today's move) and the combined value over time.
   Data: market/data.json, refreshed by .github/workflows/market-data.yml. */
(()=>{
const CLIP=3;               // colour saturates at ±3%
let D=null, range='1Y', mChart=null;
const el=id=>document.getElementById(id);
const T=v=>{const a=Math.abs(v),s=v<0?'−':'';return a>=1e12?`${s}$${(a/1e12).toFixed(2)}T`:`${s}$${(a/1e9).toFixed(0)}B`};
const P=(v,d=2)=>v==null||isNaN(v)?'–':(v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(d)+'%';

function colour(c){
  if(c==null||isNaN(c))return '#1b2733';
  const t=Math.max(-1,Math.min(1,c/CLIP)), a=Math.abs(t);
  const base=[27,39,51], end=t<0?[200,30,45]:[18,160,90];
  const mix=base.map((b,i)=>Math.round(b+(end[i]-b)*Math.pow(a,.7)));
  return `rgb(${mix})`;
}

/* squarified treemap (Bruls et al.) — items need .v; returns rects */
function squarify(items,x,y,w,h){
  const out=[], tot=items.reduce((s,i)=>s+i.v,0); if(!tot||w<=0||h<=0)return out;
  const scale=w*h/tot; let rest=items.map(i=>({...i,a:i.v*scale}));
  while(rest.length){
    const short=Math.min(w,h); let row=[rest[0]], i=1;
    const worst=r=>{const s=r.reduce((a,b)=>a+b.a,0),mx=Math.max(...r.map(q=>q.a)),mn=Math.min(...r.map(q=>q.a));
      return Math.max(short*short*mx/(s*s),(s*s)/(short*short*mn))};
    while(i<rest.length&&worst([...row,rest[i]])<=worst(row)){row.push(rest[i]);i++}
    const s=row.reduce((a,b)=>a+b.a,0), thick=s/short; let off=0;
    for(const r of row){const len=r.a/thick;
      out.push(w>=h?{...r,x,y:y+off,w:thick,h:len}:{...r,x:x+off,y,w:len,h:thick}); off+=len}
    if(w>=h){x+=thick;w-=thick}else{y+=thick;h-=thick}
    rest=rest.slice(i);
  }
  return out;
}

function weighted(ts){const t=ts.filter(x=>x.chg!=null),c=t.reduce((s,x)=>s+x.cap,0);
  return c?t.reduce((s,x)=>s+x.chg*x.cap,0)/c:null}

function drawMap(){
  const box=el('m-map'); if(!D||!box.offsetWidth)return;
  const W=box.offsetWidth, H=Math.round(Math.min(Math.max(W*1.05,360),640));
  box.style.height=H+'px'; box.innerHTML='';
  const bySec={}; D.tiles.forEach(t=>(bySec[t.sec]=bySec[t.sec]||[]).push(t));
  const secs=Object.entries(bySec).map(([k,ts])=>({k,ts,v:ts.reduce((s,t)=>s+t.cap,0)})).sort((a,b)=>b.v-a.v);
  for(const s of squarify(secs,0,0,W,H)){
    const g=document.createElement('div'); g.className='m-sec';
    Object.assign(g.style,{left:s.x+'px',top:s.y+'px',width:s.w+'px',height:s.h+'px'});
    const hd=s.h>60&&s.w>60?16:0;
    if(hd){const l=document.createElement('div');l.className='m-sech';
      l.textContent=`${s.k} ${P(weighted(s.ts),1)}`;g.appendChild(l)}
    for(const r of squarify(s.ts.map(t=>({...t,v:t.cap})),1,hd+1,s.w-2,s.h-hd-2)){
      const d=document.createElement('button'); d.className='m-tile';
      Object.assign(d.style,{left:r.x+'px',top:r.y+'px',width:Math.max(r.w-2,0)+'px',height:Math.max(r.h-2,0)+'px',background:colour(r.chg)});
      const big=Math.min(r.w,r.h);
      const fs=Math.max(8,Math.min(22,Math.sqrt(r.w*r.h)/5.5));
      if(big>22)d.innerHTML=`<b style="font-size:${fs}px">${r.s}</b>`+(big>34?`<span style="font-size:${Math.max(8,fs*.72)}px">${P(r.chg)}</span>`:'');
      d.title=`${r.n} (${r.s}) · ${T(r.cap)} · ${P(r.chg)} today`;
      d.onclick=()=>{el('m-pick').innerHTML=`<b>${r.n}</b> ${r.s} · ${T(r.cap)} · <span class="${r.chg<0?'neg':'pos'}">${P(r.chg)}</span> today`};
      g.appendChild(d);
    }
    box.appendChild(g);
  }
}

function drawKpis(){
  const t=D.tiles, avg=weighted(t), up=t.filter(x=>x.chg>0).length, dn=t.filter(x=>x.chg<0).length;
  const srt=[...t].sort((a,b)=>a.chg-b.chg), w=srt[0], b=srt[srt.length-1];
  el('m-kpis').innerHTML=
   `<div><b>${T(t.reduce((s,x)=>s+x.cap,0))}</b><span>Combined</span></div>`+
   `<div><b class="${avg<0?'neg':'pos'}">${P(avg)}</b><span>Today</span></div>`+
   `<div><b><span class="pos">${up}</span> / <span class="neg">${dn}</span></b><span>Up / down</span></div>`;
  el('m-pick').innerHTML=`Best <b class="pos">${b.s} ${P(b.chg,1)}</b> · worst <b class="neg">${w.s} ${P(w.chg,1)}</b> · tap a tile for details`;
  el('m-asof').textContent=`Prices as of ${D.asof} close (or latest), updated ${new Date(D.updated).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})}.`;
}

function drawTimeline(){
  const pts=D.total; if(!pts.length)return;
  const end=new Date(pts[pts.length-1][0]); let start=new Date(end);
  const days={'1M':31,'3M':92,'6M':183,'1Y':365,'2Y':730,'5Y':1830}[range];
  if(range==='YTD')start=new Date(end.getFullYear(),0,1);else start.setDate(start.getDate()-days);
  const v=pts.filter(p=>new Date(p[0])>=start);
  const a=v[0][1]*1e9, z=v[v.length-1][1]*1e9, pk=Math.max(...v.map(p=>p[1]))*1e9;
  const pct=(z/a-1)*100, fromPk=(z/pk-1)*100, cls=pct<0?'neg':'pos';
  el('m-tk').innerHTML=
   `<div><b class="${cls}">${T(z-a)}</b><span>Change ${range}</span></div>`+
   `<div><b class="${cls}">${P(pct,1)}</b><span>%</span></div>`+
   `<div><b class="${fromPk<-0.05?'neg':''}">${P(fromPk,1)}</b><span>From peak</span></div>`;
  const col=pct<0?'#ff5a6a':'#3ee59a';
  if(!window.Chart)return;
  mChart?.destroy();
  const ctx=el('m-line').getContext('2d'), grad=ctx.createLinearGradient(0,0,0,260);
  grad.addColorStop(0,col+'55');grad.addColorStop(1,col+'00');
  mChart=new Chart(ctx,{type:'line',data:{labels:v.map(p=>p[0]),datasets:[{data:v.map(p=>p[1]/1000),
    borderColor:col,backgroundColor:grad,fill:true,pointRadius:0,borderWidth:2,tension:.15}]},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>' $'+c.parsed.y.toFixed(2)+'T',
        title:i=>new Date(i[0].label).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})}}},
      scales:{x:{ticks:{color:'#7d97ab',maxTicksLimit:5,maxRotation:0,
          callback(val){const d=new Date(this.getLabelForValue(val));return d.toLocaleDateString('en-GB',days&&days<=183?{day:'numeric',month:'short'}:{month:'short',year:'2-digit'})}},grid:{display:false}},
        y:{ticks:{color:'#7d97ab',callback:x=>'$'+x.toFixed(0)+'T'},grid:{color:'#16314a55'}}}}});
}

async function load(){
  if(D)return true;
  try{const r=await fetch('market/data.json',{cache:'no-cache'});D=await r.json();return true}
  catch(e){el('m-pick').textContent='No market data yet — it refreshes hourly while US markets are open.';return false}
}

window.renderMarket=async()=>{
  if(!el('tab-market').classList.contains('active'))return;
  if(!await load())return;
  drawKpis(); drawMap(); drawTimeline();
};
window.marketSummary=async()=>{
  if(!await load())return "I can't reach the market data right now, sir.";
  const t=D.tiles, avg=weighted(t), srt=[...t].sort((a,b)=>a.chg-b.chg);
  const mood=avg<=-2?"It's a rough day, sir.":avg<=-0.5?"Markets are down, sir.":avg<0.5?"A quiet day, sir.":"Markets are up, sir.";
  return `${mood} The ${t.length} biggest US companies are ${P(avg)} today, worth ${T(t.reduce((s,x)=>s+x.cap,0))} combined. Best: ${srt[srt.length-1].s} ${P(srt[srt.length-1].chg,1)}. Worst: ${srt[0].s} ${P(srt[0].chg,1)}.`;
};
document.addEventListener('click',e=>{const b=e.target.closest('#m-range button');if(!b)return;
  range=b.dataset.r;document.querySelectorAll('#m-range button').forEach(x=>x.classList.toggle('on',x===b));drawTimeline()});
let rt;addEventListener('resize',()=>{clearTimeout(rt);rt=setTimeout(()=>{if(D)drawMap()},200)});
})();

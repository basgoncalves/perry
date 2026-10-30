/* Perry Online — personal finance assistant. All data stays in this browser (localStorage). */
'use strict';
const $ = s => document.querySelector(s);
const KEY = 'perry.v1';
const CATS = ['Groceries','Eating out','Transport','Housing','Bills','Shopping','Health','Entertainment','Travel','Subscriptions','Income','Transfers','Other'];
const RULES = [
  ['Groceries', /continente|pingo doce|lidl|aldi|billa|spar|hofer|mercadona|carrefour|intermarch|auchan|rewe|penny|minipre|supermarket|grocer/i],
  ['Eating out', /restaur|caf[eé]|bar |pizza|burger|mcdonald|kfc|uber ?eats|glovo|bolt food|wolt|lieferando|starbucks|sushi|padaria|pastelaria/i],
  ['Transport', /uber|bolt|taxi|cp |comboio|metro|carris|wiener linien|[öo]bb|galp|repsol|bp |shell|fuel|parking|via verde|bus|train/i],
  ['Housing', /rent|renda|miete|landlord|mortgage|hipoteca/i],
  ['Bills', /edp|endesa|wien energie|electric|water|[áa]gua|gas |internet|meo|nos |vodafone|a1 |magenta|insurance|seguro|versicherung/i],
  ['Subscriptions', /netflix|spotify|disney|hbo|apple\.com|icloud|google|youtube|amazon prime|chatgpt|anthropic|claude|patreon|github/i],
  ['Shopping', /amazon|zalando|ikea|fnac|worten|primark|zara|h&m|decathlon|mediamarkt|aliexpress|shein/i],
  ['Health', /farm[áa]cia|pharm|apotheke|clinic|doctor|dentist|hospital|gym|ginásio/i],
  ['Entertainment', /cinema|steam|playstation|xbox|nintendo|ticket|concert|museum/i],
  ['Travel', /booking|airbnb|ryanair|tap |easyjet|lufthansa|austrian|hotel|wizz/i],
  ['Income', /salary|sal[áa]rio|gehalt|payroll|universit|vencimento/i],
  ['Transfers', /transfer|transf|mb way|revolut|wise|paypal|sepa/i],
];
// Rates checked 2026-10-30. r = gross %/yr. Edit in-app; user overrides saved locally.
const INVEST = [
  {id:'pt-bk',  g:'PT', n:'Bankinter BK Mini (12m)',          r:5.00, risk:'Very low', d:'Term deposit, min €100. New clients & new money only — promo, not renewable at this rate.'},
  {id:'pt-bai', g:'PT', n:'BAI Europa Não Mobilizável (12m)', r:3.05, risk:'Very low', d:'Term deposit, min €1,000. Cannot withdraw early.'},
  {id:'pt-nb',  g:'PT', n:'Novo Banco Novos Recursos (12m)',  r:3.00, risk:'Very low', d:'Term deposit, min €100, new money only.'},
  {id:'pt-bis', g:'PT', n:'Bison Bank Rendimento Premium (12m)',r:3.00,risk:'Very low', d:'Term deposit, min €5,000, new money only.'},
  {id:'pt-big', g:'PT', n:'Big-bank standard deposit (CGD/BCP/BPI/Santander)', r:1.50, risk:'Very low', d:'Typical untargeted rate at the large banks is well below the promo offers — estimate; check your bank.'},
  {id:'pt-ca',  g:'PT', n:'Certificados de Aforro Série F',   r:2.50, risk:'Very low', d:'State savings certificates (via CTT/AforroNet). Base rate 2.5% (Oct 2026), tied to 3m Euribor, plus small permanence bonuses. Redeemable after 3 months.'},
  {id:'pt-ot',  g:'PT', n:'Obrigações do Tesouro 10y (OT)',   r:3.15, risk:'Low',      d:'Portuguese government bonds via a broker. ~2.75% (2y), ~2.9% (5y), ~3.15% (10y). Price moves if sold before maturity.'},
  {id:'pt-otrv',g:'PT', n:'OTRV retail floating bonds',       r:3.80, risk:'Low',      d:'Retail government bonds paying 6m Euribor + spread (~3.8% gross recently). Only when a new series is issued.'},
  {id:'at-bs1', g:'AT', n:'Bundesschatz 12 months',           r:2.85, risk:'Very low', d:'Austrian Treasury direct savings (bundesschatz.at), free, from €100. Sep 2026 rate.'},
  {id:'at-bs10',g:'AT', n:'Bundesschatz 10 years',            r:3.40, risk:'Very low', d:'Fixed 10 years with the Republic of Austria. 4y: 3.00%, 6m: 2.60%.'},
  {id:'at-big', g:'AT', n:'Bigbank Festgeld (12m+)',          r:3.50, risk:'Very low', d:'Top Festgeld in Austria (Oct 2026), 12–120 months. Covered by Estonian deposit guarantee.'},
  {id:'at-kk',  g:'AT', n:'Kommunalkredit Invest (5–10y)',    r:3.40, risk:'Very low', d:'Austrian bank, Festgeld 3.00% (12m) up to 3.40% (60–120m).'},
  {id:'at-sant',g:'AT', n:'Santander BestFix (24–36m)',       r:3.00, risk:'Very low', d:'Santander Consumer Bank AT, 2.90% for 12m, 3.00% for 24–36m.'},
  {id:'at-tg',  g:'AT', n:'Bigbank Tagesgeld (promo)',        r:4.00, risk:'Very low', d:'Instant-access savings, 4.00% promo for 4 months only, then lower.'},
  {id:'mk-world',g:'MK',n:'Global stocks ETF (MSCI World)',   r:13.1, risk:'High',     d:'+13.1% over the last 12 months (to 28 Oct 2026). Long-run average closer to 7–8%; falls of 30%+ happen.'},
  {id:'mk-sp',  g:'MK', n:'US stocks ETF (S&P 500)',          r:13.7, risk:'High',     d:'+13.7% year-to-date 2026 (USD). Euro returns differ with the exchange rate.'},
  {id:'mk-gold',g:'MK', n:'Gold',                             r:-5,   risk:'Medium–high',d:'Among 2026\'s weakest assets (negative YTD). Set your own estimate — rate is a placeholder.'},
  {id:'mk-btc', g:'MK', n:'Bitcoin',                          r:-10,  risk:'Very high', d:'Among 2026\'s weakest assets (negative YTD). Extremely volatile — placeholder rate, edit it.'},
];
const FLAG={PT:'🇵🇹',AT:'🇦🇹',MK:'🌍'};
function rateOf(o){return (S.rates&&S.rates[o.id]!=null)?S.rates[o.id]:o.r}
function onChart(o){return S.inv&&S.inv[o.id]!=null?S.inv[o.id]:['pt-bk','pt-ca','pt-ot','at-bs10','at-big','mk-world'].includes(o.id)}

let S = load();
function blank(){return {tx:[],budgets:{},holdings:[],goals:[],settings:{key:'',voice:true}}}
function load(){try{return Object.assign(blank(),JSON.parse(localStorage.getItem(KEY))||{})}catch{return blank()}}
function save(){try{localStorage.setItem(KEY,JSON.stringify(S))}catch{}}
const eur = n => (n<0?'−':'')+'€'+Math.abs(n).toLocaleString('en-IE',{maximumFractionDigits:0});
const eur2 = n => (n<0?'−':'')+'€'+Math.abs(n).toLocaleString('en-IE',{minimumFractionDigits:2,maximumFractionDigits:2});
const ym = d => d.slice(0,7);
const thisMonth = () => new Date().toISOString().slice(0,7);
const categorise = desc => (RULES.find(([,re])=>re.test(desc))||['Other'])[0];
const esc = s => String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* ---------- tabs ---------- */
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>show(b.dataset.tab));
function show(t){
  document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('on',b.dataset.tab===t));
  document.querySelectorAll('.tab').forEach(s=>s.classList.toggle('active',s.id==='tab-'+t));
  render();
}

/* ---------- CSV import ---------- */
function parseCSV(text){
  const sep = (text.split('\n')[0].match(/;/g)||[]).length > (text.split('\n')[0].match(/,/g)||[]).length ? ';' : ',';
  const rows=[];let row=[],cur='',q=false;
  for(let i=0;i<text.length;i++){const c=text[i];
    if(q){if(c=='"'&&text[i+1]=='"'){cur+='"';i++}else if(c=='"')q=false;else cur+=c}
    else if(c=='"')q=true;else if(c==sep){row.push(cur);cur=''}
    else if(c=='\n'||c=='\r'){if(c=='\r'&&text[i+1]=='\n')i++;row.push(cur);rows.push(row);row=[];cur=''}
    else cur+=c}
  if(cur||row.length){row.push(cur);rows.push(row)}
  return rows.filter(r=>r.some(x=>x.trim()));
}
function num(s){if(s==null)return NaN;s=String(s).replace(/[€\s]/g,'');
  if(/,\d{1,2}$/.test(s))s=s.replace(/\./g,'').replace(',','.');else s=s.replace(/,/g,'');return parseFloat(s)}
function toISO(s){s=String(s).trim();let m;
  if(m=s.match(/^(\d{4})-(\d{2})-(\d{2})/))return m.slice(1).join('-');
  if(m=s.match(/^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})/)){let y=m[3].length==2?'20'+m[3]:m[3];return `${y}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`}
  const d=new Date(s);return isNaN(d)?null:d.toISOString().slice(0,10)}
function importCSV(text){
  const rows=parseCSV(text);if(rows.length<2)return 0;
  const h=rows[0].map(x=>x.toLowerCase().trim());
  const find=re=>h.findIndex(x=>re.test(x));
  const iD=find(/date|data|datum|booking/), iDesc=find(/desc|merchant|name|payee|details|text|movimento|buchung|verwendung/);
  const iAmt=find(/^amount|montante|valor|betrag|^value/), iOut=find(/debit|débito|out|soll|withdraw/), iIn=find(/credit|crédito|^in$|haben|deposit/);
  let n=0;
  for(const r of rows.slice(1)){
    const date=toISO(r[iD>=0?iD:0]);if(!date)continue;
    let amt=iAmt>=0?num(r[iAmt]):(num(r[iIn])||0)-(Math.abs(num(r[iOut]))||0);
    if(isNaN(amt)||amt===0)continue;
    const desc=(r[iDesc>=0?iDesc:1]||'').trim()||'—';
    if(S.tx.some(t=>t.date==date&&t.amt==amt&&t.desc==desc))continue;
    S.tx.push({id:Date.now()+Math.random(),date,desc,amt,cat:amt>0&&categorise(desc)==='Other'?'Income':categorise(desc)});n++}
  save();return n;
}
$('#csv').onchange=async e=>{const f=e.target.files[0];if(!f)return;
  const n=importCSV(await f.text());say(`Imported ${n} new transactions from ${f.name}.`,true);e.target.value='';render()};

/* ---------- spending ---------- */
function monthTx(m){return S.tx.filter(t=>ym(t.date)===m)}
function catTotals(m){const o={};monthTx(m).filter(t=>t.amt<0&&t.cat!=='Transfers').forEach(t=>o[t.cat]=(o[t.cat]||0)-t.amt);return o}
let charts={};
function chart(id,cfg){charts[id]?.destroy();if(window.Chart)charts[id]=new Chart($(id),cfg)}
window.Chart && (Chart.defaults.color='#7d97ab', Chart.defaults.borderColor='#16314a');
const PAL=['#3fd8ff','#3ee59a','#ffc24a','#ff5a6a','#b48cff','#ff8fd1','#6fa8ff','#9be15d','#ff9f43','#54e0c7','#c0c9d4','#8a7dff','#e0e070'];

function renderSpend(){
  const months=[...new Set([thisMonth(),...S.tx.map(t=>ym(t.date))])].sort().reverse();
  const sel=$('#month'),cur=sel.value||months[0];
  sel.innerHTML=months.map(m=>`<option ${m==cur?'selected':''}>${m}</option>`).join('');
  const tx=monthTx(cur).filter(t=>t.cat!=='Transfers');
  const out=-tx.filter(t=>t.amt<0).reduce((a,t)=>a+t.amt,0), inc=tx.filter(t=>t.amt>0).reduce((a,t)=>a+t.amt,0);
  $('#k-out').textContent=eur(out);$('#k-in').textContent=eur(inc);
  $('#k-net').textContent=eur(inc-out);$('#k-net').className=inc-out>=0?'pos':'neg';
  const ct=catTotals(cur),labels=Object.keys(ct).sort((a,b)=>ct[b]-ct[a]);
  chart('#c-cat',{type:'doughnut',data:{labels,datasets:[{data:labels.map(l=>ct[l]),backgroundColor:PAL,borderWidth:0}]},options:{plugins:{legend:{position:'right',labels:{boxWidth:10}}}}});
  const opts=CATS.map(c=>`<option>${c}</option>`).join('');
  $('#b-cat').innerHTML=CATS.filter(c=>!['Income','Transfers'].includes(c)).map(c=>`<option>${c}</option>`).join('');
  if(!$('#t-cat').options.length)$('#t-cat').innerHTML=opts;
  $('#budgets').innerHTML=Object.entries(S.budgets).map(([c,b])=>{const s=ct[c]||0,p=Math.min(100,s/b*100);
    return `<div class="item"><span>${esc(c)}</span><span class="${s>b?'neg':''}">${eur(s)} / ${eur(b)} <button class="x" data-b="${esc(c)}">×</button></span></div><div class="bar"><i class="${s>b?'over':''}" style="width:${p}%"></i></div>`}).join('')||'<p class="hint">No budgets yet.</p>';
  $('#txlist').innerHTML=monthTx(cur).sort((a,b)=>b.date.localeCompare(a.date)).map(t=>
    `<div class="item"><span>${esc(t.desc)}<small>${t.date} · <select data-c="${t.id}" style="width:auto;padding:2px;font-size:11px">${CATS.map(c=>`<option ${c==t.cat?'selected':''}>${c}</option>`).join('')}</select></small></span><span class="${t.amt<0?'':'pos'}">${eur2(t.amt)} <button class="x" data-t="${t.id}">×</button></span></div>`).join('')||'<p class="hint">Import a bank CSV or add a transaction.</p>';
}
$('#month').onchange=render;
$('#budgets').onclick=e=>{if(e.target.dataset.b){delete S.budgets[e.target.dataset.b];save();render()}};
$('#txlist').onclick=e=>{if(e.target.dataset.t){S.tx=S.tx.filter(t=>t.id!=e.target.dataset.t);save();render()}};
$('#txlist').onchange=e=>{const t=S.tx.find(t=>t.id==e.target.dataset.c);if(t){t.cat=e.target.value;save();render()}};
$('#f-budget').onsubmit=e=>{e.preventDefault();const a=+$('#b-amt').value;if(a>0){S.budgets[$('#b-cat').value]=a;save();$('#b-amt').value='';render()}};
$('#t-date').value=new Date().toISOString().slice(0,10);
$('#f-tx').onsubmit=e=>{e.preventDefault();const desc=$('#t-desc').value;
  S.tx.push({id:Date.now(),date:$('#t-date').value,desc,amt:+$('#t-amt').value,cat:$('#t-cat').value});
  save();$('#t-desc').value=$('#t-amt').value='';render()};
$('#t-desc').oninput=e=>{$('#t-cat').value=categorise(e.target.value)};

/* ---------- portfolio ---------- */
function portTotals(){let v=0,c=0;S.holdings.forEach(h=>{v+=h.qty*(h.price||h.cost);c+=h.qty*h.cost});return{v,c,g:v-c}}
function renderPort(){
  const {v,c,g}=portTotals();
  $('#p-val').textContent=eur(v);$('#p-cost').textContent=eur(c);
  $('#p-gain').textContent=eur(g)+(c?` (${(g/c*100).toFixed(1)}%)`:'');$('#p-gain').className=g>=0?'pos':'neg';
  chart('#c-port',{type:'doughnut',data:{labels:S.holdings.map(h=>h.sym),datasets:[{data:S.holdings.map(h=>h.qty*(h.price||h.cost)),backgroundColor:PAL,borderWidth:0}]},options:{plugins:{legend:{position:'right',labels:{boxWidth:10}}}}});
  $('#holdings').innerHTML=S.holdings.map((h,i)=>{const p=h.price||h.cost,gg=(p-h.cost)*h.qty;
    return `<div class="item"><span><b>${esc(h.sym)}</b><small>${h.qty} × ${eur2(p)} · bought ${eur2(h.cost)}${h.at?' · '+new Date(h.at).toLocaleString():''}</small></span><span class="${gg>=0?'pos':'neg'}">${eur2(gg)} <button class="x" data-h="${i}">×</button></span></div>`}).join('')||'<p class="hint">No holdings yet.</p>';
  $('#price-hint').textContent=S.settings.key?'Live prices via Finnhub (US tickers work best; EU tickers may need manual prices).':'Add a free Finnhub key in Settings for live prices, or enter prices manually.';
}
$('#holdings').onclick=e=>{if(e.target.dataset.h){S.holdings.splice(+e.target.dataset.h,1);save();render()}};
$('#f-hold').onsubmit=e=>{e.preventDefault();
  S.holdings.push({sym:$('#h-sym').value.trim().toUpperCase(),qty:+$('#h-qty').value,cost:+$('#h-cost').value,price:+$('#h-price').value||0});
  save();e.target.reset();render()};
async function refreshPrices(){
  if(!S.settings.key){say('I need a Finnhub API key in Settings to fetch live prices.',true);return}
  let ok=0;
  for(const h of S.holdings){try{const r=await fetch(`https://finnhub.io/api/v1/quote?symbol=${encodeURIComponent(h.sym)}&token=${encodeURIComponent(S.settings.key)}`);
    const j=await r.json();if(j.c>0){h.price=j.c;h.at=Date.now();ok++}}catch{}}
  save();render();say(`Updated ${ok} of ${S.holdings.length} prices.`,true);
}
$('#refresh').onclick=refreshPrices;

/* ---------- goals ---------- */
function goalETA(g){if(g.saved>=g.target)return'Reached 🎉';if(!g.month)return'Add a monthly amount to project';
  const m=Math.ceil((g.target-g.saved)/g.month),d=new Date();d.setMonth(d.getMonth()+m);
  return `~${m} months · ${d.toLocaleDateString('en-GB',{month:'short',year:'numeric'})}`}
function renderGoals(){
  $('#goals').innerHTML=S.goals.map((g,i)=>{const p=Math.min(100,g.saved/g.target*100);
    return `<div class="item"><span><b>${esc(g.name)}</b><small>${eur(g.saved)} of ${eur(g.target)} · +${eur(g.month)}/mo · ${goalETA(g)}</small></span><span><button class="btn small ghost" data-add="${i}">+ add</button> <button class="x" data-g="${i}">×</button></span></div><div class="bar"><i style="width:${p}%"></i></div>`}).join('')||'<p class="hint">No goals yet.</p>';
}
$('#goals').onclick=e=>{const d=e.target.dataset;
  if(d.g){S.goals.splice(+d.g,1);save();render()}
  if(d.add){const v=+prompt('Add how much (€)?');if(v){S.goals[+d.add].saved+=v;save();render()}}};
$('#f-goal').onsubmit=e=>{e.preventDefault();
  S.goals.push({name:$('#g-name').value,target:+$('#g-target').value,saved:+$('#g-saved').value,month:+$('#g-month').value});save();e.target.reset();render()};

/* ---------- invest ---------- */
function project(start,month,years,rate){const r=rate/100/12;let v=start,out=[start];
  for(let i=1;i<=years*12;i++){v=v*(1+r)+month;if(i%12==0)out.push(v)}return out}
function renderInvest(){
  const st=+$('#i-start').value||0,mo=+$('#i-month').value||0,y=Math.max(1,Math.min(60,+$('#i-years').value||1)),inf=+$('#i-infl').value||0;
  const tx=$('#i-tax').value==='PT'?.28:$('#i-tax').value==='AT'?.275:0,reg=$('#i-region').value;
  $('#i-yl').textContent=y;
  const list=INVEST.filter(o=>reg==='all'||o.g===reg);
  const net=o=>rateOf(o)>0?rateOf(o)*(1-tx):rateOf(o); // tax only on gains
  const labels=[...Array(y+1).keys()].map(i=>'Y'+i),paid=st+mo*12*y;
  const shown=list.filter(onChart);
  chart('#c-grow',{type:'line',data:{labels,datasets:[{label:'Paid in',data:labels.map((_,i)=>st+mo*12*i),borderColor:'#7d97ab',borderDash:[4,4],pointRadius:0},
    ...shown.map((o,i)=>({label:o.n.replace(/ \(.*\)/,''),data:project(st,mo,y,net(o)),borderColor:PAL[i%PAL.length],pointRadius:0,tension:.2}))]},
    options:{plugins:{legend:{labels:{boxWidth:10,font:{size:10}}}},scales:{y:{ticks:{callback:v=>'€'+(v/1000).toFixed(0)+'k'}}}}});
  const res=list.map(o=>({o,f:project(st,mo,y,net(o)).at(-1)})).sort((a,b)=>b.f-a.f);
  $('#grow-out').innerHTML=res.map(({o,f})=>`<div class="item"><span>${FLAG[o.g]} ${esc(o.n)}<small>${rateOf(o)}% gross · ${net(o).toFixed(2)}% after tax · risk ${o.risk}</small></span><span class="${f>=paid?'pos':'neg'}">${eur(f)}<small>gain ${eur(f-paid)} · ${eur(f/Math.pow(1+inf/100,y))} today</small></span></div>`).join('')+
    `<div class="item"><span>Total paid in</span><span>${eur(paid)}</span></div>`;
  $('#options').innerHTML=['PT','AT','MK'].filter(g=>reg==='all'||g===reg).map(g=>`<h3>${FLAG[g]} ${{PT:'Portugal',AT:'Austria',MK:'Markets (last 12 months)'}[g]}</h3>`+
    INVEST.filter(o=>o.g===g).map(o=>`<div class="opt"><label class="check"><input type="checkbox" data-on="${o.id}" ${onChart(o)?'checked':''}> <b>${esc(o.n)}</b></label>
      <div><span class="tag">Risk: ${o.risk}</span><span class="tag">Rate <input data-r="${o.id}" type="number" step="0.05" value="${rateOf(o)}" style="width:62px;padding:2px 4px;font-size:11px;display:inline">%</span></div><p>${esc(o.d)}</p></div>`).join('')).join('');
}
$('#options').addEventListener('change',e=>{const d=e.target.dataset;
  if(d.on){S.inv=S.inv||{};S.inv[d.on]=e.target.checked}
  if(d.r){S.rates=S.rates||{};S.rates[d.r]=+e.target.value}
  save();renderInvest()});
$('#i-reset').onclick=()=>{S.rates={};S.inv={};save();renderInvest()};
['#i-start','#i-month','#i-years','#i-infl','#i-tax','#i-region'].forEach(s=>$(s).oninput=$(s).onchange=renderInvest);

/* ---------- settings ---------- */
$('#s-key').value=S.settings.key;$('#s-voice').checked=S.settings.voice;
$('#s-key').onchange=e=>{S.settings.key=e.target.value.trim();save();render()};
$('#s-voice').onchange=e=>{S.settings.voice=e.target.checked;save()};
$('#export').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(S,null,1)],{type:'application/json'}));
  a.download=`perry-backup-${new Date().toISOString().slice(0,10)}.json`;a.click()};
$('#import').onchange=async e=>{try{S=Object.assign(blank(),JSON.parse(await e.target.files[0].text()));save();render();say('Backup restored.',true)}catch{alert('Not a valid Perry backup.')}};
$('#wipe').onclick=()=>{if(confirm('Erase all Perry data on this device?')){S=blank();save();render()}};
$('#demo').onclick=()=>{const m=thisMonth(),p=new Date();p.setMonth(p.getMonth()-1);const pm=p.toISOString().slice(0,7);
  const d=[['01','Salary University',2900],['02','Renda Lisboa',-950],['03','Continente',-84.2],['05','Uber',-12.4],['06','Netflix',-13.99],['08','Pingo Doce',-46.1],['09','Restaurante O Zé',-32],['11','EDP',-61.3],['12','Zara',-59.9],['14','Lidl',-38.7],['15','Spotify',-10.99],['16','Galp',-55],['18','Cinema NOS',-14]];
  for(const mm of [pm,m])d.forEach(([dd,desc,amt])=>S.tx.push({id:Math.random(),date:`${mm}-${dd}`,desc,amt:amt*(mm==pm?0.9+Math.random()*.2:1),cat:categorise(desc)}));
  S.budgets={Groceries:250,'Eating out':120,Shopping:100};
  S.holdings=[{sym:'VWCE.DE',qty:20,cost:105,price:122},{sym:'AAPL',qty:5,cost:170,price:0}];
  S.goals=[{name:'Emergency fund',target:6000,saved:2400,month:300},{name:'Trip to Japan',target:3500,saved:900,month:150}];
  save();render();say('Demo data loaded. Try asking me something.',true)};

/* ---------- Perry brain ---------- */
const log=$('#log');
function add(text,who){const d=document.createElement('div');d.className='msg '+who;d.textContent=text;log.appendChild(d);d.scrollIntoView({behavior:'smooth'})}
function speak(t){if(!S.settings.voice||!window.speechSynthesis)return;speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(t.replace(/€/g,' euros ').replace(/−/g,'minus '));u.lang='en-GB';u.rate=1.02;
  const v=speechSynthesis.getVoices().find(v=>/en-GB/.test(v.lang)&&/male|daniel|george|arthur/i.test(v.name))||speechSynthesis.getVoices().find(v=>/en-GB/.test(v.lang));if(v)u.voice=v;
  $('#core').classList.add('talk');u.onend=()=>$('#core').classList.remove('talk');speechSynthesis.speak(u)}
function say(t,quiet){add(t,'p');if(!quiet)speak(t);$('#status').textContent=t.split('\n')[0].slice(0,60)}
function monthFrom(q){const names=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
  if(/last month/.test(q)){const d=new Date();d.setMonth(d.getMonth()-1);return d.toISOString().slice(0,7)}
  const i=names.findIndex(n=>q.includes(n));if(i>=0){const y=new Date().getFullYear();return `${i>new Date().getMonth()?y-1:y}-${String(i+1).padStart(2,'0')}`}
  return thisMonth()}
function answer(raw){
  const q=raw.toLowerCase().replace(/^(hey |ok )?perry[, ]*/,'').trim();const m=monthFrom(q);
  if(/daddy'?s home/.test(q))return "Welcome home, sir. Session restore runs on the desktop Perry — open it on your PC with Ctrl+Alt+P. Here, all financial systems are online.";
  if(!q||/^(hi|hello|hey|yo)\b/.test(q))return "At your service, sir. Ask me about spending, budgets, your portfolio or goals.";
  if(/help|what can you/.test(q))return "Try:\n• How much did I spend this month?\n• Spending on groceries last month\n• Am I over budget?\n• How's my portfolio?\n• How are my goals?\n• If I invest 200 a month for 20 years?\n• Compare investment options";
  const inv=q.match(/(\d[\d.,]*)\D+(?:a |per |each )?month\D+(\d+)\s*year/);
  if(inv){const mo=num(inv[1]),y=+inv[2];return `Investing ${eur(mo)} a month for ${y} years (${eur(mo*12*y)} paid in) could grow to roughly:\n`+
    [...INVEST].map(o=>({o,f:project(0,mo,y,rateOf(o)>0?rateOf(o)*0.72:rateOf(o)).at(-1)})).sort((a,b)=>b.f-a.f).slice(0,5).map(({o,f})=>`• ${o.n}: ${eur(f)}`).join('\n')+'\n(after 28% tax, using current rates)'+"\nIllustrative only — not a forecast."}
  const cat=CATS.find(c=>q.includes(c.toLowerCase())||(c=='Eating out'&&/restaurant|food out|eat/.test(q))||(c=='Groceries'&&/food|supermarket/.test(q)));
  if(/spen|cost|paid|expens/.test(q)&&cat){const v=catTotals(m)[cat]||0,b=S.budgets[cat];
    return `You spent ${eur2(v)} on ${cat.toLowerCase()} in ${m}.`+(b?` That's ${Math.round(v/b*100)}% of your ${eur(b)} budget.`:'')}
  if(/budget|over/.test(q)){const ct=catTotals(m),over=Object.entries(S.budgets).filter(([c,b])=>(ct[c]||0)>b);
    if(!Object.keys(S.budgets).length)return "You haven't set any budgets yet, sir. Add some in the Spend tab.";
    return over.length?`Over budget in ${over.map(([c,b])=>`${c} (${eur(ct[c])} of ${eur(b)})`).join(', ')}.`:`All budgets on track for ${m}. Well done, sir.`}
  if(/biggest|top|most/.test(q)){const ct=catTotals(m),top=Object.entries(ct).sort((a,b)=>b[1]-a[1]).slice(0,3);
    return top.length?`Top spending in ${m}: `+top.map(([c,v])=>`${c} ${eur(v)}`).join(', ')+'.':'No spending recorded for that month.'}
  if(/spen|income|earn|net|save|month/.test(q)&&!/goal|invest/.test(q)){const tx=monthTx(m).filter(t=>t.cat!=='Transfers');
    const out=-tx.filter(t=>t.amt<0).reduce((a,t)=>a+t.amt,0),inc=tx.filter(t=>t.amt>0).reduce((a,t)=>a+t.amt,0);
    if(!tx.length)return `No transactions for ${m} yet. Import a bank CSV in the Spend tab.`;
    return `In ${m}: spent ${eur(out)}, income ${eur(inc)}, net ${eur(inc-out)}${inc?` (saving ${Math.round((inc-out)/inc*100)}%)`:''}.`}
  if(/portfolio|stock|holding|shares|etf/.test(q)){if(!S.holdings.length)return "No holdings yet. Add them in the Portfolio tab.";
    const {v,c,g}=portTotals(),best=[...S.holdings].sort((a,b)=>((b.price||b.cost)/b.cost)-((a.price||a.cost)/a.cost))[0];
    return `Portfolio is worth ${eur(v)}, ${g>=0?'up':'down'} ${eur(Math.abs(g))} (${(g/c*100).toFixed(1)}%). Best performer: ${best.sym}.`}
  if(/goal|target/.test(q)){if(!S.goals.length)return "No savings goals yet. Add one in the Goals tab.";
    return S.goals.map(g=>`${g.name}: ${Math.round(g.saved/g.target*100)}% — ${goalETA(g)}`).join('\n')}
  if(/best (rate|deposit)|deposit|bond|aforro|bundesschatz|festgeld/.test(q)){const t=[...INVEST].filter(o=>o.g!=='MK').sort((a,b)=>rateOf(b)-rateOf(a)).slice(0,4);show('invest');return 'Top safe rates right now:\n'+t.map(o=>`• ${FLAG[o.g]} ${o.n}: ${rateOf(o)}%`).join('\n')+'\nCheck conditions — the highest are often promos for new clients.'}
  if(/invest|option|where.*money|compare/.test(q)){show('invest');return "Here are the main options with risk, access and typical long-run returns. It's general information, not advice for your situation — a licensed advisor can tailor it to you."}
  if(/buy|sell|should i/.test(q))return "I can't tell you what to buy or sell, sir — I'm not a licensed advisor. I can show your numbers, compare options and project growth so you can decide.";
  if(/time|date/.test(q))return new Date().toLocaleString('en-GB',{weekday:'long',hour:'2-digit',minute:'2-digit',day:'numeric',month:'long'});
  return "I didn't catch that, sir. Say 'help' to see what I can do.";
}
function ask(t){if(!t.trim())return;add(t,'u');setTimeout(()=>say(answer(t)),250)}
$('#ask').onsubmit=e=>{e.preventDefault();ask($('#q').value);$('#q').value=''};
const CHIPS=['Spending this month','Am I over budget?','How\'s my portfolio?','How are my goals?','200 a month for 20 years','Compare investment options'];
$('#chips').innerHTML=CHIPS.map(c=>`<button>${c}</button>`).join('');
$('#chips').onclick=e=>{if(e.target.tagName=='BUTTON')ask(e.target.textContent)};

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
function listen(){if(!SR){say('Voice input is not supported in this browser. Chrome works best.',true);return}
  const r=new SR();r.lang='en-GB';r.interimResults=false;
  $('#mic').classList.add('on');$('#core').classList.add('listen');
  r.onresult=e=>ask(e.results[0][0].transcript);
  r.onend=()=>{$('#mic').classList.remove('on');$('#core').classList.remove('listen')};r.start()}
$('#mic').onclick=listen;$('#core').onclick=listen;

/* ---------- boot ---------- */
function render(){renderSpend();renderPort();renderGoals();renderInvest()}
render();
const h=new Date().getHours();
say(`Good ${h<12?'morning':h<18?'afternoon':'evening'}, sir. Perry online.`+(S.tx.length?'':' No data yet — load demo data in Settings or import a bank CSV.'),true);
if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js').catch(()=>{});

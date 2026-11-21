// Biz tab: BGB Bookings (embedded), Perry's accountant, and the financial plan.
// Data lives in the BGB Health Supabase project and is readable only by BGB admins.
(function () {
  const SB = 'https://gfzqvaumziuiwfrwhhes.supabase.co', KEY = 'sb_publishable_NxmiKUulD7hNH6CkUsEwIA_ki8EDWyC';
  const PRICE = { init: 120, train: 80, nutri: 80, gait: 95, coach: 150, chk: 45 };
  const SVC = { init: 'Initial assessment', train: 'Training consultation', nutri: 'Nutrition consultation', gait: 'Running video analysis', coach: 'Coaching package', chk: 'Follow-up call' };
  // 2026 Austrian values (WKO / BMF). Update every January.
  const BRACKETS = [[13539, 0], [21992, .20], [36458, .30], [70365, .40], [104859, .48], [1e6, .50], [Infinity, .55]];
  const SVS_RATE = .068 + .185 + .0153, SVS_UV = 12.95 * 12, SVS_MIN_BASE = 6613.20, SVS_MAX_BASE = 97020;
  const VAT_LIMIT = 55000, GFB_RATE = .15, GFB_CAP = 33000;
  const $ = id => document.getElementById(id);
  const eur = n => { const a = Math.abs(n), d = a < 1000 && a % 1 ? 2 : 0; return (n < 0 ? '−' : '') + '€' + a.toLocaleString('de-AT', { minimumFractionDigits: d, maximumFractionDigits: d }); };
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let db = null, session = null, bookings = [], ledger = [], loaded = false;

  // ---------- settings (this device only) ----------
  const S = Object.assign({ split: 50, salB: 0, salG: 0, svsB: 'gewerbe', svsG: 'neue' }, (() => { try { return JSON.parse(localStorage.getItem('perry.acc') || '{}'); } catch (e) { return {}; } })());
  const saveS = () => { try { localStorage.setItem('perry.acc', JSON.stringify(S)); } catch (e) {} };

  // ---------- maths ----------
  function incomeTax(x) { let t = 0, lo = 0; for (const [hi, r] of BRACKETS) { if (x > lo) t += (Math.min(x, hi) - lo) * r; lo = hi; } return t; }
  function svs(profit, mode) {
    if (mode === 'neue' && profit <= SVS_MIN_BASE) return 0;
    const base = Math.min(Math.max(profit, SVS_MIN_BASE), SVS_MAX_BASE); return base * SVS_RATE + SVS_UV;
  }
  function person(profit, salary, mode) {
    const sv = profit > 0 || mode === 'gewerbe' ? svs(Math.max(profit, 0), mode) : 0;
    let taxable = Math.max(profit - sv, 0); taxable -= Math.min(taxable, GFB_CAP) * GFB_RATE;
    if (salary > 0 && taxable <= 730) taxable = 0; else if (salary > 0 && taxable < 1460) taxable = 2 * (taxable - 730);
    const tax = incomeTax(salary + taxable) - incomeTax(salary);
    return { profit, svs: sv, tax, keep: profit - sv - tax };
  }
  const inRange = (d, [a, b]) => d >= a && d < b;
  function range(word) {
    const n = new Date(), y = n.getFullYear(), m = n.getMonth(), D = (yy, mm, dd = 1) => new Date(yy, mm, dd);
    const months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
    const w = (word || '').toLowerCase();
    if (/last month/.test(w)) return [D(y, m - 1), D(y, m), 'last month'];
    if (/this month|month/.test(w)) return [D(y, m), D(y, m + 1), 'this month'];
    if (/last year/.test(w)) return [D(y - 1, 0), D(y, 0), 'last year'];
    if (/quarter/.test(w)) { const q = Math.floor(m / 3); return [D(y, q * 3), D(y, q * 3 + 3), 'this quarter']; }
    if (/week/.test(w)) { const s = D(y, m, n.getDate() - ((n.getDay() + 6) % 7)); return [s, new Date(+s + 7 * 864e5), 'this week']; }
    if (/today/.test(w)) return [D(y, m, n.getDate()), D(y, m, n.getDate() + 1), 'today'];
    const mi = months.findIndex(x => w.includes(x)); if (mi >= 0) { const yy = mi > m ? y - 1 : y; return [D(yy, mi), D(yy, mi + 1), months[mi][0].toUpperCase() + months[mi].slice(1) + ' ' + yy]; }
    return [D(y, 0), D(y + 1, 0), 'this year'];
  }
  // Confirmed bookings that already happened count as income; ledger adds everything else.
  function totals(r) {
    const bk = bookings.filter(b => b.status === 'confirmed' && new Date(b.start_at) < new Date() && inRange(new Date(b.start_at), r));
    const pend = bookings.filter(b => b.status !== 'cancelled' && inRange(new Date(b.start_at), r) && !(b.status === 'confirmed' && new Date(b.start_at) < new Date()));
    const L = ledger.filter(x => inRange(new Date(x.day + 'T12:00'), r));
    const bkInc = bk.reduce((s, b) => s + (PRICE[b.service_id] || 0), 0);
    const inc = L.filter(x => x.kind === 'income').reduce((s, x) => s + +x.amount, 0) + bkInc;
    const exp = L.filter(x => x.kind === 'expense').reduce((s, x) => s + +x.amount, 0);
    return { bk, pend, L, bkInc, inc, exp, profit: inc - exp, pipeline: pend.reduce((s, b) => s + (PRICE[b.service_id] || 0), 0) };
  }
  function yearView() {
    const t = totals(range('year')), now = new Date(), frac = Math.max((now - new Date(now.getFullYear(), 0)) / (365 * 864e5), 1 / 12);
    const full = t.profit / frac, sh = S.split / 100;
    return { t, full, B: person(full * sh, +S.salB || 0, S.svsB), G: person(full * (1 - sh), +S.salG || 0, S.svsG), turnoverFull: t.inc / frac };
  }
  function deadlines() {
    const n = new Date(), y = n.getFullYear(), out = [];
    for (const yy of [y, y + 1]) for (const mm of [2, 5, 8, 11]) out.push([new Date(yy, mm, 0), 'SVS quarterly payment due']);
    out.push([new Date(y, 5, 30), `Income tax return for ${y - 1} (FinanzOnline)`], [new Date(y + 1, 5, 30), `Income tax return for ${y} (FinanzOnline)`]);
    return out.filter(d => d[0] >= new Date(y, n.getMonth(), n.getDate())).sort((a, b) => a[0] - b[0]);
  }
  const fmtD = d => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

  // ---------- render ----------
  function render() {
    if (!$('acc-kpis')) return;
    const signed = !!session;
    $('acc-login').hidden = signed; $('acc-main').hidden = !signed;
    if (!signed || !loaded) return;
    const v = yearView(), t = v.t, nd = deadlines()[0], vatPct = Math.min(100, t.inc / VAT_LIMIT * 100);
    const k = (b, s, c = '') => `<div class="k ${c}"><b>${b}</b><span>${s}</span></div>`;
    $('acc-kpis').innerHTML =
      k(eur(t.inc), 'Income this year') + k(eur(t.exp), 'Expenses') + k(eur(t.profit), 'Profit', t.profit < 0 ? 'neg' : '') +
      k(eur(t.profit * .27), 'Set aside for SVS (≈27%)') + k(eur(t.pipeline), 'Booked, not yet earned') +
      k(nd ? fmtD(nd[0]) : '—', nd ? nd[1] : 'Next deadline');
    $('acc-vat').innerHTML = `<div class="vat-row"><span>Small-business VAT limit (€55,000 turnover)</span><span>${eur(t.inc)} · ${vatPct.toFixed(0)}%</span></div><div class="vat-bar"><i style="width:${vatPct}%;background:${vatPct > 80 ? 'var(--amber)' : 'var(--green)'}"></i></div>`;
    const rows = [...ledger].sort((a, b) => b.day.localeCompare(a.day)).slice(0, 8);
    $('acc-ledger').innerHTML = rows.length ? rows.map(x => `<div class="lrow"><span>${x.day.slice(8)}.${x.day.slice(5, 7)}</span><span>${esc(x.category)}${x.note ? ' · ' + esc(x.note) : ''}${x.person !== 'shared' ? ' · ' + x.person : ''}</span><b class="${x.kind === 'expense' ? 'neg' : 'pos'}">${x.kind === 'expense' ? '−' : '+'}${eur(+x.amount)}</b><button data-del="${x.id}" aria-label="Delete entry">×</button></div>`).join('')
      : '<p class="sub">No entries yet. Type “add expense 29 software Canva” or “add income 120 workshop”.</p>';
  }

  // ---------- chat brain ----------
  const CATS = [['software', /software|app|canva|zoom|subscription|domain|hosting|supabase|stripe fee/], ['insurance', /insurance|versicherung/], ['marketing', /ads?|marketing|instagram|facebook|flyer|promo/], ['equipment', /equipment|laptop|camera|phone|kettlebell|band|scale/], ['accountant', /accountant|steuerberat|tax advis/], ['education', /course|book|conference|training|certificat/], ['travel', /travel|train ticket|fuel|petrol|km/], ['telecom', /internet|mobile|phone bill/], ['svs', /\bsvs\b|social insurance/]];
  const cat = s => (CATS.find(([, r]) => r.test(s)) || ['other'])[0];
  async function addEntry(kind, amount, rest) {
    const who = /gwen/i.test(rest) ? 'gwen' : /bas[ií]lio|\bme\b|\bmy\b/i.test(rest) ? 'basilio' : 'shared';
    const row = { kind, amount, category: kind === 'income' ? (cat(rest) === 'other' ? 'consultation' : cat(rest)) : cat(rest), note: rest.replace(/\b(for|on|gwen|bas[ií]lio)\b/gi, '').trim().slice(0, 200) || null, person: who };
    const { data, error } = await db.from('ledger').insert(row).select().single();
    if (error) return `I couldn't save that: ${error.message}`;
    ledger.push(data); render();
    return `Saved: ${kind === 'income' ? 'income' : 'expense'} of ${eur(amount)} under “${data.category}”${who !== 'shared' ? ' for ' + (who === 'gwen' ? 'Gwen' : 'you') : ''}. Your profit this year is now ${eur(totals(range('year')).profit)}.`;
  }
  async function answer(q) {
    if (!session) return 'Sign in first, my lord, so I can open the books.';
    const s = q.toLowerCase().trim();
    let m = s.match(/^(?:add\s+|log\s+)?(expense|cost|spent|paid|bought|income|earned|received|got paid)\s+(?:of\s+)?€?\s*(\d+(?:[.,]\d{1,2})?)\s*€?\s*(.*)$/);
    if (m) { const amt = parseFloat(m[2].replace(',', '.')); return addEntry(/income|earned|received|got paid/.test(m[1]) ? 'income' : 'expense', amt, m[3] || ''); }
    if (/undo|delete last|remove last/.test(s)) {
      const last = [...ledger].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]; if (!last) return 'There is nothing to undo.';
      const { error } = await db.from('ledger').delete().eq('id', last.id); if (error) return 'I couldn\'t delete it: ' + error.message;
      ledger = ledger.filter(x => x.id !== last.id); render(); return `Removed the last entry (${last.kind} of ${eur(+last.amount)}, ${last.category}).`;
    }
    if (/booking|client|session|upcoming|appointment/.test(s) && !/earn|income|revenue/.test(s)) {
      const up = bookings.filter(b => b.status !== 'cancelled' && new Date(b.start_at) > new Date()).sort((a, b) => a.start_at.localeCompare(b.start_at));
      if (!up.length) return 'No upcoming bookings right now.';
      return `${up.length} upcoming booking${up.length > 1 ? 's' : ''}, worth ${eur(up.reduce((x, b) => x + (PRICE[b.service_id] || 0), 0))}:\n` + up.slice(0, 5).map(b => `• ${new Date(b.start_at).toLocaleString('en-GB', { timeZone: 'Europe/Vienna', weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })} · ${SVC[b.service_id] || b.service_id} · ${b.name} (${b.status})`).join('\n');
    }
    if (/set aside|put aside|reserve|svs|social insurance/.test(s)) {
      const v = yearView();
      return `Set aside about ${eur(v.t.profit * .27)} for SVS from this year's ${eur(v.t.profit)} profit (≈27%).\nOn the current pace (≈${eur(v.full)} profit for the full year): you ≈ ${eur(v.B.svs)}, Gwen ≈ ${eur(v.G.svs)}.` +
        (S.svsB === 'gewerbe' ? '\nWith a trade licence you pay at least ≈€1,930 a year, and the SVS bills the difference about 2 years later — keep the reserve.' : '');
    }
    if (/tax|steuer|finanzamt/.test(s) && !/deadline|when|due/.test(s)) {
      const v = yearView();
      return `Estimated income tax on BGB for the full year (current pace, ${eur(v.full)} profit, split ${S.split}/${100 - S.split}):\n• You: ≈ ${eur(v.B.tax)}${+S.salB ? ' on top of your salary tax' : ''}\n• Gwen: ≈ ${eur(v.G.tax)}\nAfter SVS and tax you'd keep ≈ ${eur(v.B.keep)} and ≈ ${eur(v.G.keep)}.\nI include the 15% basic profit allowance and the €730 side-income rule. Add your salaries in the settings for a better estimate.`;
    }
    if (/vat|ust|umsatzsteuer|kleinunternehmer|limit|threshold/.test(s)) {
      const v = yearView();
      return `Turnover this year: ${eur(v.t.inc)} of the €55,000 small-business limit (${(v.t.inc / VAT_LIMIT * 100).toFixed(0)}%). On the current pace you'd reach ≈ ${eur(v.turnoverFull)} by year end — ${v.turnoverFull > VAT_LIMIT ? 'above the limit: talk to a tax adviser now about charging VAT.' : 'comfortably below, no VAT needed.'}`;
    }
    if (/deadline|due|when.*pay|calendar/.test(s)) return 'Next deadlines:\n' + deadlines().slice(0, 4).map(([d, t]) => `• ${fmtD(d)} — ${t}`).join('\n');
    if (/deduct|write off|absetz|claim/.test(s)) return 'Usually deductible for you as sole traders:\n• Software, hosting, Supabase, Stripe fees\n• Laptop, camera, training equipment (over €1,000: spread over several years)\n• Courses, books, conferences in your field\n• Professional liability insurance, accountant fees\n• SVS contributions\n• Part of internet and phone; home office (a lump sum if you have no separate room)\n• Ads and marketing\nKeep every receipt for 7 years. A tax adviser can confirm the details.';
    if (/export|csv|download/.test(s)) { exportCSV(); return 'Downloaded this year\'s ledger and confirmed bookings as a CSV file for your accountant.'; }
    if (/expense|spent|cost/.test(s)) {
      const r = range(s), t = totals(r), by = {}; t.L.filter(x => x.kind === 'expense').forEach(x => by[x.category] = (by[x.category] || 0) + +x.amount);
      return `Expenses ${r[2]}: ${eur(t.exp)}.` + (Object.keys(by).length ? '\n' + Object.entries(by).sort((a, b) => b[1] - a[1]).map(([c, a]) => `• ${c}: ${eur(a)}`).join('\n') : '');
    }
    if (/earn|income|revenue|made|turnover|profit|how.*doing|summary|overview/.test(s)) {
      const r = range(s), t = totals(r);
      return `${r[2][0].toUpperCase() + r[2].slice(1)}: income ${eur(t.inc)} (${t.bk.length} confirmed session${t.bk.length === 1 ? '' : 's'} = ${eur(t.bkInc)}, plus ${eur(t.inc - t.bkInc)} logged), expenses ${eur(t.exp)}, profit ${eur(t.profit)}.` + (t.pipeline ? `\nStill to come in that period: ${eur(t.pipeline)} from ${t.pend.length} booking${t.pend.length > 1 ? 's' : ''}.` : '') + `\nPut aside ≈ ${eur(Math.max(t.profit, 0) * .27)} for SVS.`;
    }
    return 'I can help with: “How much did I earn this month?”, “Add expense 29 software Canva”, “Add income 120 workshop for Gwen”, “How much should I set aside?”, “Estimate my tax”, “VAT limit”, “Next deadlines”, “What can I deduct?”, “Upcoming bookings”, “Export CSV”, “Undo”.';
  }
  function exportCSV() {
    const r = range('year'), t = totals(r), lines = [['date', 'type', 'amount_eur', 'category', 'note', 'person']];
    t.bk.forEach(b => lines.push([b.start_at.slice(0, 10), 'income', PRICE[b.service_id] || 0, 'booking: ' + (SVC[b.service_id] || b.service_id), b.name, 'shared']));
    t.L.forEach(x => lines.push([x.day, x.kind, x.amount, x.category, x.note || '', x.person]));
    const csv = lines.map(l => l.map(c => /[",;\n]/.test(String(c)) ? '"' + String(c).replace(/"/g, '""') + '"' : c).join(',')).join('\n');
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })); a.download = `bgb-ledger-${new Date().getFullYear()}.csv`; a.click();
  }
  function say(text, who) {
    const d = document.createElement('div'); d.className = 'msg ' + (who || 'p'); d.textContent = text;
    $('acc-log').append(d); $('acc-log').scrollTop = 1e9;
  }

  // ---------- data ----------
  async function load() {
    if (!session) { loaded = false; render(); return; }
    const [b, l] = await Promise.all([db.from('bookings').select('service_id,start_at,status,name'), db.from('ledger').select('*')]);
    if (b.error || l.error) { $('acc-note').textContent = 'Couldn\'t load the books: ' + (b.error || l.error).message + '. If the database was paused, it may take a few minutes to wake up.'; return; }
    bookings = b.data; ledger = l.data; loaded = true; $('acc-note').textContent = ''; render();
    if (!$('acc-log').children.length) say(`Good to see you, my lord. Your books are open: ${eur(totals(range('year')).profit)} profit so far this year. Ask me anything about BGB's money.`);
  }

  // ---------- wiring ----------
  function init() {
    if (!$('tab-biz') || !window.supabase) return;
    db = window.supabase.createClient(SB, KEY);
    const views = ['book', 'acc', 'plan'];
    const pick = v => { views.forEach(x => { $('biz-' + x).hidden = x !== v; }); document.querySelectorAll('#biznav button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); try { localStorage.setItem('perry.biz', v); } catch (e) {} if (v === 'acc') render(); };
    document.querySelectorAll('#biznav button').forEach(b => b.onclick = () => pick(b.dataset.v));
    let start = 'book'; try { start = localStorage.getItem('perry.biz') || 'book'; } catch (e) {}
    const qs = new URLSearchParams(location.search); if (qs.get('biz')) { start = qs.get('biz') === 'acc' ? 'acc' : 'book'; }
    pick(start);
    $('acc-google').onclick = async () => {
      const { error } = await db.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: location.origin + location.pathname + '?biz=acc' } });
      if (error) $('acc-note').textContent = error.message;
    };
    $('acc-form').onsubmit = async e => { e.preventDefault(); const q = $('acc-q').value.trim(); if (!q) return; $('acc-q').value = ''; say(q, 'u'); say(await answer(q)); };
    document.querySelectorAll('#acc-chips button').forEach(b => b.onclick = async () => { say(b.textContent, 'u'); say(await answer(b.dataset.q || b.textContent)); });
    $('acc-ledger').onclick = async e => { const b = e.target.closest('[data-del]'); if (!b) return; const { error } = await db.from('ledger').delete().eq('id', b.dataset.del); if (!error) { ledger = ledger.filter(x => x.id !== b.dataset.del); render(); } };
    for (const [id, k] of [['acc-split', 'split'], ['acc-salB', 'salB'], ['acc-salG', 'salG'], ['acc-svsB', 'svsB'], ['acc-svsG', 'svsG']]) { const el = $(id); el.value = S[k]; el.onchange = () => { S[k] = el.type === 'number' ? +el.value : el.value; saveS(); render(); }; }
    db.auth.onAuthStateChange((_ev, s) => {
      const had = !!session; session = s;
      if (!!s !== had) load();
      if (s && qs.get('biz')) { history.replaceState(null, '', location.pathname + '#biz'); window.dispatchEvent(new HashChangeEvent('hashchange')); }
    });
    db.auth.getSession().then(({ data }) => { session = data.session; load(); }).catch(() => render());
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();

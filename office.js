// Office tab: live view of Claude Code agents, read from the office server on your PC.
// Nothing leaves your network: the browser asks http://localhost:8765 directly.
(() => {
  const KEY = 'perry.office.url';
  const LABEL = {working: 'Working', waiting: 'Needs you', done: 'Done', idle: 'Idle'};
  const COL = {working: 'var(--green)', waiting: 'var(--amber)', done: 'var(--cyan)', idle: 'var(--mut)'};
  const ICON = {working: '⌨', waiting: '?', done: '✓', idle: 'z'};
  const $ = id => document.getElementById(id);
  const el = (t, c, txt) => { const e = document.createElement(t); if (c) e.className = c; if (txt != null) e.textContent = txt; return e; };
  const fmt = s => s < 60 ? Math.floor(s) + 's' : s < 3600 ? Math.floor(s / 60) + 'm' : s < 86400 ? Math.floor(s / 3600) + 'h' : Math.floor(s / 86400) + 'd';
  let url = 'http://localhost:8765', hideIdle = false, timer = null, prev = {}, first = true, lastOk = 0;
  try { url = localStorage.getItem(KEY) || url; hideIdle = localStorage.getItem(KEY + '.hide') === '1'; } catch (e) {}

  function setUrl(u) { url = (u || '').trim().replace(/\/+$/, '') || 'http://localhost:8765'; try { localStorage.setItem(KEY, url); } catch (e) {} }

  function render(d) {
    const box = $('office-rooms'); box.innerHTML = '';
    const tally = {working: 0, waiting: 0, done: 0, idle: 0}; let shown = 0;
    d.rooms.forEach(r => {
      r.agents.forEach(a => tally[a.state] = (tally[a.state] || 0) + 1);
      const agents = hideIdle ? r.agents.filter(a => a.state !== 'idle') : r.agents;
      if (!agents.length) return; shown++;
      const card = el('div', 'card office-room' + (agents.some(a => a.state === 'waiting') ? ' hot' : ''));
      const h = el('h2', null, r.name); h.append(el('span', 'office-n', agents.length + ''));
      card.append(h);
      agents.forEach(a => {
        const row = el('button', 'office-agent');
        row.style.setProperty('--c', COL[a.state]);
        const dot = el('span', 'office-dot ' + a.state, ICON[a.state]);
        const mid = el('span', 'office-mid'); mid.append(el('b', null, a.name), el('small', null, a.task || ''));
        const right = el('span', 'office-right'); right.append(el('span', 'office-st', LABEL[a.state]), el('small', null, fmt(d.now - a.last_activity)));
        row.append(dot, mid, right);
        if (!r.id.startsWith('_')) row.onclick = async () => {
          if (!confirm('Resume "' + a.name + '" in a terminal on your PC?')) return;
          try { const t = await (await fetch(url + '/open?id=' + encodeURIComponent(a.id))).text(); if (t !== 'opened') alert('Could not open: ' + t); }
          catch (e) { alert('Only works on the PC running the office.'); }
        };
        card.append(row);
      });
      box.append(card);
    });
    if (!shown) box.append(el('div', 'card sub', hideIdle ? 'Everyone is idle.' : 'No Claude Code sessions in the last few days.'));
    const k = $('office-kpis'); k.innerHTML = '';
    [['waiting', 'Need you'], ['working', 'Working'], ['done', 'Done'], ['idle', 'Idle']].forEach(([s, l]) => {
      const d2 = el('div'); const b = el('b', null, tally[s] || 0); b.style.color = COL[s]; d2.append(b, el('span', null, l)); k.append(d2);
    });
    // alert when an agent starts needing you
    d.rooms.forEach(r => r.agents.forEach(a => {
      const o = prev[a.id];
      if (!first && a.state === 'waiting' && (!o || o.state !== 'waiting') && 'Notification' in window && Notification.permission === 'granted')
        new Notification('Office: ' + r.name + ' needs you', {body: a.name + ' — ' + a.task, icon: 'icon-192.png'});
      prev[a.id] = a;
    }));
    first = false;
  }

  function status(msg, ok) { const s = $('office-status'); s.textContent = msg; s.style.color = ok ? 'var(--green)' : 'var(--amber)'; }

  async function poll() {
    clearTimeout(timer);
    if (!$('tab-office').classList.contains('active')) { timer = setTimeout(poll, 5000); return; }
    try {
      const ctl = new AbortController(); const kill = setTimeout(() => ctl.abort(), 20000);
      const r = await fetch(url + '/rooms.json', {cache: 'no-store', signal: ctl.signal});
      clearTimeout(kill);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      render(await r.json()); lastOk = Date.now();
      $('office-help').hidden = true; status('● Live · ' + url.replace(/^https?:\/\//, ''), true);
    } catch (e) {
      if (Date.now() - lastOk < 30000) { timer = setTimeout(poll, 3000); return; } // one slow or missed check: keep showing Live
      $('office-help').hidden = false;
      status('○ Office not reachable at ' + url + (lastOk ? ' (last seen ' + new Date(lastOk).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}) + ')' : '') + ' · ' + (e.name === 'AbortError' ? 'timed out' : e.message), false);
    }
    timer = setTimeout(poll, 3000);
  }

  window.addEventListener('DOMContentLoaded', () => {
    $('office-url').value = url;
    $('office-hide').checked = hideIdle;
    $('office-save').onclick = () => { setUrl($('office-url').value); $('office-url').value = url; poll(); };
    $('office-hide').onchange = e => { hideIdle = e.target.checked; try { localStorage.setItem(KEY + '.hide', hideIdle ? '1' : '0'); } catch (_) {} poll(); };
    $('office-notify').onclick = () => { if ('Notification' in window) Notification.requestPermission(); };
    $('office-full').onclick = () => window.open(url, '_blank');
    document.querySelectorAll('.tabs button[data-tab="office"]').forEach(b => b.addEventListener('click', () => setTimeout(poll, 0)));
    poll();
  });
})();

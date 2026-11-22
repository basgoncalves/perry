// Office tab: desks that show a day's stories on the 3D globe (globe.js).
// The journalist covers world news (news/today.json); the security analyst covers cyber incidents (cyber/today.json).
// Each country is green, yellow or red; grey means no story was found.
(() => {
  const COL = {red: '#ff5a6a', yellow: '#ffc24a', green: '#3ee59a', none: '#26384c'};
  const WORD = {red: 'Red', yellow: 'Yellow', green: 'Green', none: 'No story'};
  const $ = id => document.getElementById(id);
  const el = (t, c, txt) => { const e = document.createElement(t); if (c) e.className = c; if (txt != null) e.textContent = txt; return e; };
  const dot = s => { const d = el('i', 'news-dot'); d.style.background = COL[s]; return d; };
  const link = (txt, url) => { const a = el('a', 'news-src', txt); a.href = url; a.target = '_blank'; a.rel = 'noopener'; return a; };

  function desk(p, cfg) {
    let day = null, world = null, globe = null, loading = false;
    const status = c => (day.countries[c.id] || {}).s || 'none';

    function card(name, s, n) {
      const box = el('div', 'news-item'), head = el('div', 'news-head');
      head.append(dot(s), el('b', null, name), el('span', 'news-word', WORD[s])); box.append(head);
      if (n) box.append(el('p', null, n.d), link('Source: ' + n.src, n.url));
      else box.append(el('p', 'sub', cfg.empty));
      return box;
    }
    function select(c, turn) {
      const box = $(p + '-pick'); box.innerHTML = ''; box.hidden = false;
      box.append(card(c.name, status(c), day.countries[c.id]));
      $(p + '-countries').querySelectorAll('.news-row').forEach(r => r.classList.toggle('on', r.dataset.id === c.id));
      if (globe) { globe.select(c.id); if (turn) { globe.face(c.c[0], c.c[1]); $(p + '-globe').scrollIntoView({behavior: 'smooth', block: 'center'}); } }
    }
    function lists() {
      $(p + '-date').textContent = day.label;
      const lg = $(p + '-legend'); lg.innerHTML = '';
      ['red', 'yellow', 'green', 'none'].forEach(s => { const r = el('div', 'news-key'); r.append(dot(s), el('span', null, day.legend[s])); lg.append(r); });
      const top = $(p + '-top'); top.innerHTML = '';
      day.top.forEach(t => { const box = el('div', 'news-item'), head = el('div', 'news-head'); head.append(dot(t.s), el('b', null, t.t)); box.append(head, el('p', null, t.d), link('Source: ' + t.src, t.url)); top.append(box); });
      const all = $(p + '-countries'); all.innerHTML = '';
      ['red', 'yellow', 'green'].forEach(s => {
        const rows = world.filter(c => status(c) === s).sort((a, b) => a.name.localeCompare(b.name));
        if (!rows.length) return;
        all.append(el('h3', null, WORD[s] + ' · ' + rows.length));
        rows.forEach(c => { const r = el('button', 'news-row'); r.dataset.id = c.id; r.append(dot(s), el('b', null, c.name), el('small', null, day.countries[c.id].d)); r.onclick = () => select(c, true); all.append(r); });
      });
      $(p + '-note').textContent = day.compiled + ' ' + world.filter(c => status(c) !== 'none').length + ' countries have a story; the rest are grey. ' + cfg.note;
    }
    async function open() {
      if (day || loading) return; loading = true;
      try {
        [day, world] = await Promise.all([fetch(cfg.file, {cache: 'no-cache'}).then(r => r.json()), PerryGlobe.world()]);
        lists(); if (cfg.after) cfg.after(day);
        try { globe = await PerryGlobe.create($(p + '-globe'), {colorOf: c => COL[status(c)], dot: c => status(c) !== 'none', onPick: c => select(c, false), view: cfg.view}); }
        catch (e) { $(p + '-globe').hidden = true; $(p + '-globe-fail').hidden = false; }
      } catch (e) { $(p + '-date').textContent = 'Could not load this desk\'s data.'; day = null; }
      loading = false;
    }
    const d = $(p + '-desk'); if (!d) return;
    d.onclick = () => {
      const box = $(p + '-panel'), show = box.hidden; box.hidden = !show;
      d.setAttribute('aria-expanded', String(show));
      $(p + '-hint').textContent = show ? cfg.hintOpen : cfg.hint;
      if (show) open();
    };
  }

  // Cyber desk extra: security flaws known to be under attack (CISA's public list).
  const KEV = 'https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json';
  function kevList(k, live) {
    const box = $('cyber-kev'); box.innerHTML = '';
    k.items.forEach(v => {
      const it = el('div', 'news-item'), head = el('div', 'news-head');
      head.append(el('b', null, v.vendor + ' ' + v.product), el('span', 'news-word', 'Added ' + v.added)); it.append(head, el('p', null, v.what));
      const foot = el('p', 'sub', v.cve + ' · fix due ' + v.due + (v.ransomware === 'Known' ? ' · used by ransomware' : '')); it.append(foot); box.append(it);
    });
    $('cyber-kev-note').textContent = (live ? 'Live list' : 'Saved copy') + ' dated ' + k.released + ' · ' + k.count + ' flaws in total. Source: CISA Known Exploited Vulnerabilities.';
  }
  function kev() {
    fetch('cyber/kev.json', {cache: 'no-cache'}).then(r => r.json()).then(k => kevList(k, false)).catch(() => {});
    $('cyber-kev-refresh').onclick = async e => {
      const b = e.target; b.textContent = 'Checking…';
      try {
        const d = await (await fetch(KEV, {cache: 'no-store'})).json();
        const items = d.vulnerabilities.sort((a, b) => b.dateAdded.localeCompare(a.dateAdded)).slice(0, 12).map(v => ({cve: v.cveID, vendor: v.vendorProject, product: v.product, added: v.dateAdded, due: v.dueDate, ransomware: v.knownRansomwareCampaignUse, what: v.shortDescription.length > 240 ? v.shortDescription.slice(0, 237) + '…' : v.shortDescription}));
        kevList({released: d.dateReleased.slice(0, 10), count: d.count, items}, true); b.textContent = 'Updated ✓';
      } catch (err) { b.textContent = 'Could not reach the list'; }
      setTimeout(() => b.textContent = 'Check for newer', 2500);
    };
  }

  window.addEventListener('DOMContentLoaded', () => {
    desk('news', {file: 'news/today.json', view: [.35, -1.75], empty: 'No major story found for this country today.',
      note: 'Colours describe the day\'s headlines, not the country.', hint: "Tap the desk for today's news on the globe.", hintOpen: 'Tap the desk again to put the paper away.'});
    desk('cyber', {file: 'cyber/today.json', view: [.45, -1.6], empty: 'No reported cyber incident found for this country this week.',
      note: 'Colours describe reported incidents, not how secure a country is.', hint: 'Tap the desk for this week\'s cyber incidents.', hintOpen: 'Tap the desk again to lock the screen.', after: kev});
  });
})();

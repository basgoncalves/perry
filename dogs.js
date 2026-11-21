// Office tab: the dog trainer's room. Tap his desk to browse 50 dog breeds.
// The list ships with the site (dog_breeds.json), so it works on the phone without the PC.
(() => {
  const RATE = [['energy', 'Energy'], ['trainability', 'Trainability'], ['grooming', 'Grooming need'], ['shedding', 'Shedding'], ['good_with_kids', 'Good with kids']];
  const $ = id => document.getElementById(id);
  const el = (t, c, txt) => { const e = document.createElement(t); if (c) e.className = c; if (txt != null) e.textContent = txt; return e; };
  let breeds = [], picked = null;
  // Photos: looked up live from each breed's Wikipedia article (two sizes), remembered for a week.
  const PKEY = 'perry.dogs.photos', WIKI = 'https://en.wikipedia.org/';
  let photos = {};
  try { const c = JSON.parse(localStorage.getItem(PKEY) || 'null'); if (c && Date.now() - c.t < 6048e5) photos = c.p; } catch (e) {}

  async function wikiThumbs(size) {
    const u = WIKI + 'w/api.php?action=query&format=json&formatversion=2&origin=*&redirects=1&prop=pageimages&piprop=thumbnail&pilimit=50&pithumbsize=' + size +
      '&titles=' + encodeURIComponent(breeds.map(b => b.wiki).join('|'));
    const q = (await (await fetch(u)).json()).query || {};
    const hop = {}; [...(q.normalized || []), ...(q.redirects || [])].forEach(x => hop[x.from] = x.to);
    const by = {}; (q.pages || []).forEach(p => { if (p.thumbnail) by[p.title] = p.thumbnail.source; });
    const out = {};
    breeds.forEach(b => { let t = b.wiki; for (let i = 0; i < 4 && hop[t]; i++) t = hop[t]; if (by[t]) out[b.name] = by[t]; });
    return out;
  }
  async function loadPhotos() {
    if (Object.keys(photos).length) return;
    try {
      const [sm, lg] = await Promise.all([wikiThumbs(120), wikiThumbs(500)]);
      breeds.forEach(b => { if (sm[b.name] || lg[b.name]) photos[b.name] = {s: sm[b.name] || lg[b.name], l: lg[b.name] || sm[b.name]}; });
      if (!Object.keys(photos).length) return;
      try { localStorage.setItem(PKEY, JSON.stringify({t: Date.now(), p: photos})); } catch (e) {}
      list(); const cur = breeds.find(b => b.name === picked); if (cur) detail(cur);
    } catch (e) { /* offline: paw placeholders stay */ }
  }
  function photo(b, big) {
    const box = el('span', big ? 'dog-photo' : 'dog-thumb', '🐾'), p = photos[b.name];
    if (p) { const im = new Image(); im.alt = big ? b.name : ''; im.decoding = 'async';
      im.onload = () => { box.textContent = ''; box.append(im); }; im.src = big ? p.l : p.s; }
    return box;
  }

  async function load() {
    try { breeds = (await (await fetch('dog_breeds.json')).json()).breeds; }
    catch (e) { $('dog-detail').textContent = 'Could not load the breed list.'; return; }
    const sel = $('dog-group'); sel.innerHTML = '';
    ['All groups', ...[...new Set(breeds.map(b => b.group))].sort()].forEach(g => sel.append(el('option', null, g)));
    const size = $('dog-size'); size.innerHTML = '';
    ['Any size', 'Toy', 'Small', 'Medium', 'Large', 'Giant'].forEach(s => size.append(el('option', null, s)));
    sel.onchange = size.onchange = $('dog-search').oninput = list;
    $('dog-count').textContent = breeds.length;
    list();
    loadPhotos();
  }

  function list() {
    const q = $('dog-search').value.trim().toLowerCase(), g = $('dog-group').value, s = $('dog-size').value;
    const box = $('dog-list'); box.innerHTML = '';
    const hits = breeds.filter(b => (g === 'All groups' || b.group === g) && (s === 'Any size' || b.size === s) && (!q || b.name.toLowerCase().includes(q)));
    if (!hits.length) { box.append(el('p', 'sub', 'No breed matches.')); return; }
    hits.forEach(b => {
      const row = el('button', 'dog-item' + (picked === b.name ? ' on' : ''));
      row.append(photo(b), el('b', null, b.name), el('small', null, b.size + ' · ' + b.group));
      row.onclick = () => { picked = b.name; list(); detail(b); $('dog-detail').scrollIntoView({behavior: 'smooth', block: 'nearest'}); };
      box.append(row);
    });
  }

  function detail(b) {
    const d = $('dog-detail'); d.innerHTML = ''; d.hidden = false;
    d.append(photo(b, true), el('h3', null, b.name),
      el('p', 'sub', b.group + ' · ' + b.origin + ' · ' + b.size + ' · ' + b.weight_kg + ' kg · ' + b.lifespan_years + ' years'),
      el('p', 'dog-temp', b.temperament));
    RATE.forEach(([k, label]) => {
      const row = el('div', 'dog-stat'), bar = el('div', 'bar'), fill = el('i');
      fill.style.width = (b[k] / 5 * 100) + '%'; bar.append(fill);
      row.append(el('span', null, label), bar, el('span', null, b[k] + '/5')); d.append(row);
    });
    const credit = el('p', 'hint', 'Ratings are rough guides; individual dogs vary. ');
    if (photos[b.name]) { const a = el('a', null, 'Photo: Wikipedia'); a.href = WIKI + 'wiki/' + encodeURIComponent(b.wiki.replace(/ /g, '_')); a.target = '_blank'; a.rel = 'noopener'; credit.append(a); }
    d.append(credit);
  }

  window.addEventListener('DOMContentLoaded', () => {
    const desk = $('dog-desk'); if (!desk) return;
    desk.onclick = () => {
      const box = $('dog-breeds'), open = box.hidden; box.hidden = !open;
      desk.setAttribute('aria-expanded', String(open));
      $('dog-hint').textContent = open ? 'Tap the desk again to put the notes away.' : "Tap the desk to see the trainer's dog breed notes.";
      if (open && !breeds.length) load();
    };
  });
})();

// Office tab: the flight controller's desk. Live aircraft around a chosen city, drawn on the 3D globe (globe.js).
// Positions come from free community ADS-B feeds; each covers up to 250 nautical miles (about 460 km) around a point.
(() => {
  const CITIES = [['Vienna', 48.21, 16.37], ['Lisbon', 38.72, -9.14], ['London', 51.51, -.13], ['Frankfurt', 50.11, 8.68], ['Paris', 48.86, 2.35], ['Madrid', 40.42, -3.7],
    ['Istanbul', 41.01, 28.98], ['Dubai', 25.2, 55.27], ['New York', 40.71, -74.01], ['Los Angeles', 34.05, -118.24], ['São Paulo', -23.55, -46.63], ['Tokyo', 35.68, 139.69], ['Singapore', 1.35, 103.82], ['Sydney', -33.87, 151.21]];
  const NM = 250, KM = Math.round(NM * 1.852), EVERY = 15000;
  const $ = id => document.getElementById(id);
  const el = (t, c, txt) => { const e = document.createElement(t); if (c) e.className = c; if (txt != null) e.textContent = txt; return e; };

  // The feeds share one data format (ADS-B Exchange v2); OpenSky is a last resort with a small daily allowance.
  const adsb = j => (j.ac || []).filter(a => a.lat != null && a.lon != null).map(a => ({
    hex: a.hex, call: (a.flight || '').trim(), reg: a.r || '', type: a.t || '', lat: a.lat, lon: a.lon,
    ground: a.alt_baro === 'ground', alt: typeof a.alt_baro === 'number' ? a.alt_baro : 0, kt: a.gs != null ? Math.round(a.gs) : null, track: a.track != null ? Math.round(a.track) : null}));
  const SOURCES = [
    {name: 'airplanes.live', url: (la, lo) => `https://api.airplanes.live/v2/point/${la}/${lo}/${NM}`, parse: adsb},
    {name: 'adsb.lol', url: (la, lo) => `https://api.adsb.lol/v2/point/${la}/${lo}/${NM}`, parse: adsb},
    {name: 'OpenSky', url: (la, lo) => { const dy = NM / 60, dx = dy / Math.cos(la * Math.PI / 180); return `https://opensky-network.org/api/states/all?lamin=${la - dy}&lamax=${la + dy}&lomin=${lo - dx}&lomax=${lo + dx}`; },
      parse: j => (j.states || []).filter(s => s[5] != null && s[6] != null).map(s => ({hex: s[0], call: (s[1] || '').trim(), reg: '', type: '', lat: s[6], lon: s[5], ground: !!s[8],
        alt: s[7] != null ? Math.round(s[7] * 3.281) : 0, kt: s[9] != null ? Math.round(s[9] * 1.944) : null, track: s[10] != null ? Math.round(s[10]) : null}))}
  ];
  let src = 0, globe = null, planes = [], picked = null, timer = null, busy = false, here = CITIES[0], opened = false;

  async function pull() {
    for (let n = 0; n < SOURCES.length; n++) {
      const s = SOURCES[(src + n) % SOURCES.length], ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 9000);
      try {
        const r = await fetch(s.url(here[1], here[2]), {signal: ctl.signal, cache: 'no-store'}); clearTimeout(t);
        if (!r.ok) throw new Error(r.status);
        const list = s.parse(await r.json()); src = (src + n) % SOURCES.length; return {list, name: s.name};
      } catch (e) { clearTimeout(t); }
    }
    return null;
  }
  const colour = p => p.ground ? [.5, .58, .66] : p.alt < 10000 ? [1, .76, .29] : p.alt < 30000 ? [.24, .9, .6] : [.25, .85, 1];
  const height = p => p.ground ? 'on the ground' : p.alt.toLocaleString() + ' ft';

  function detail() {
    const box = $('fly-pick'), p = planes.find(x => x.hex === picked);
    if (!p) { box.hidden = true; if (globe) globe.mark(null); return; }
    box.innerHTML = ''; box.hidden = false; if (globe) globe.mark(p);
    const it = el('div', 'news-item'), head = el('div', 'news-head');
    head.append(el('b', null, p.call || p.reg || p.hex.toUpperCase()), el('span', 'news-word', p.type || 'Aircraft')); it.append(head);
    it.append(el('p', null, [height(p), p.kt != null ? p.kt + ' kt' : null, p.track != null ? 'heading ' + p.track + '°' : null, p.reg ? 'reg. ' + p.reg : null].filter(Boolean).join(' · ')));
    const a = el('a', 'news-src', 'Follow this aircraft on airplanes.live'); a.href = 'https://globe.airplanes.live/?icao=' + p.hex; a.target = '_blank'; a.rel = 'noopener'; it.append(a);
    box.append(it);
  }
  function list() {
    const box = $('fly-list'); box.innerHTML = '';
    const air = planes.filter(p => !p.ground).sort((a, b) => b.alt - a.alt);
    air.slice(0, 40).forEach(p => {
      const r = el('button', 'news-row' + (p.hex === picked ? ' on' : '')); const d = el('i', 'news-dot'); d.style.background = `rgb(${colour(p).map(v => Math.round(v * 255))})`;
      r.append(d, el('b', null, (p.call || p.reg || p.hex.toUpperCase()) + (p.type ? ' · ' + p.type : '')), el('small', null, height(p) + (p.kt != null ? ' · ' + p.kt + ' kt' : '')));
      r.onclick = () => { picked = p.hex; detail(); list(); if (globe) { globe.face(p.lon, p.lat); $('fly-globe').scrollIntoView({behavior: 'smooth', block: 'center'}); } };
      box.append(r);
    });
    if (air.length > 40) box.append(el('p', 'hint', 'Showing the 40 highest of ' + air.length + ' aircraft in the air.'));
  }
  async function refresh() {
    clearTimeout(timer);
    const live = opened && !$('fly-panel').hidden && $('tab-office').classList.contains('active') && !document.hidden;
    if (live && !busy) {
      busy = true; const got = await pull(); busy = false;
      if (got) {
        planes = got.list; if (globe) globe.setPoints(planes.map(p => ({lon: p.lon, lat: p.lat, color: colour(p)})));
        const air = planes.filter(p => !p.ground).length;
        $('fly-status').textContent = air + ' aircraft in the air within ' + KM + ' km of ' + here[0] + ' · ' + new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'}) + ' · ' + got.name;
        $('fly-status').style.color = 'var(--green)'; $('fly-fail').hidden = true; detail(); list();
      } else { $('fly-status').textContent = 'No live flight feed could be reached just now.'; $('fly-status').style.color = 'var(--amber)'; $('fly-fail').hidden = false; }
    }
    timer = setTimeout(refresh, EVERY);
  }
  function go(city) {
    here = city; picked = null; planes = []; $('fly-pick').hidden = true; $('fly-list').innerHTML = '';
    if (globe) { globe.setPoints([]); globe.mark(null); globe.face(city[2], city[1], 1.3); }
    $('fly-status').textContent = 'Looking for aircraft near ' + city[0] + '…'; $('fly-status').style.color = '';
    refresh();
  }

  async function open() {
    if (opened) { refresh(); return; } opened = true;
    const sel = $('fly-city'); CITIES.forEach((c, i) => { const o = el('option', null, c[0]); o.value = i; sel.append(o); });
    let saved = 0; try { saved = +localStorage.getItem('perry.fly.city') || 0; } catch (e) {}
    sel.value = saved in CITIES ? saved : 0; here = CITIES[sel.value];
    sel.onchange = () => { try { localStorage.setItem('perry.fly.city', sel.value); } catch (e) {} go(CITIES[sel.value]); };
    $('fly-near').onclick = () => {
      if (!navigator.geolocation) return; $('fly-status').textContent = 'Asking for your location…';
      navigator.geolocation.getCurrentPosition(p => go(['you', +p.coords.latitude.toFixed(2), +p.coords.longitude.toFixed(2)]), () => { $('fly-status').textContent = 'Location not available; pick a city instead.'; });
    };
    try {
      globe = await PerryGlobe.create($('fly-globe'), {colorOf: () => '#17293b', border: 0x3a5878, spin: false, minZ: 1.08, z: 1.3, pointSize: 7,
        onPoint: i => { picked = planes[i].hex; detail(); list(); }});
      globe.face(here[2], here[1], 1.3);
    } catch (e) { $('fly-globe').hidden = true; $('fly-globe-fail').hidden = false; }
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    go(here);
  }

  window.addEventListener('DOMContentLoaded', () => {
    const d = $('fly-desk'); if (!d) return;
    d.onclick = () => {
      const box = $('fly-panel'), show = box.hidden; box.hidden = !show;
      d.setAttribute('aria-expanded', String(show));
      $('fly-hint').textContent = show ? 'Tap the desk again to close the radar.' : 'Tap the desk to track live flights.';
      if (show) open();
    };
  });
})();

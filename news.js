// Office tab: the journalist's desk. Tap it for today's news on a 3D globe.
// Each country is green, yellow or red for the day (news/today.json); grey means no major story found.
(() => {
  const COL = {red: '#ff5a6a', yellow: '#ffc24a', green: '#3ee59a', none: '#26384c'};
  const WORD = {red: 'Red', yellow: 'Yellow', green: 'Green', none: 'No major story'};
  const W = 2048, H = 1024;
  const $ = id => document.getElementById(id);
  const el = (t, c, txt) => { const e = document.createElement(t); if (c) e.className = c; if (txt != null) e.textContent = txt; return e; };
  let day = null, world = null, globe = null, picked = null, loading = false;

  const X = lon => (lon + 180) / 360 * W, Y = lat => (90 - lat) / 180 * H;
  const status = c => (day.countries[c.id] || {}).s || 'none';

  // Rings that cross the date line are unwrapped and drawn three times (shifted a world left and right);
  // a ring that circles a pole (Antarctica) is closed along that pole.
  function trace(ctx, c) {
    ctx.beginPath();
    c.p.forEach(poly => poly.forEach(r => {
      const pts = []; let off = 0, sum = 0;
      for (let i = 0; i < r.length; i += 2) {
        if (i) { const d = r[i] - r[i - 2]; if (d > 180) off -= 360; else if (d < -180) off += 360; }
        pts.push([r[i] + off, r[i + 1]]); sum += r[i + 1];
      }
      if (Math.abs(off) > 180) { const pole = sum < 0 ? -90 : 90; pts.push([pts[pts.length - 1][0], pole], [pts[0][0], pole]); }
      for (const s of [-360, 0, 360]) { pts.forEach(([x, y], i) => i ? ctx.lineTo(X(x + s), Y(y)) : ctx.moveTo(X(x + s), Y(y))); ctx.closePath(); }
    }));
  }
  // Countries too small to see on the globe get a dot so their colour still shows.
  const tiny = c => c.a < 3;

  function paint() {
    const map = document.createElement('canvas'), ids = document.createElement('canvas');
    map.width = ids.width = W; map.height = ids.height = H;
    const m = map.getContext('2d'), k = ids.getContext('2d', {willReadFrequently: true});
    m.fillStyle = '#06111f'; m.fillRect(0, 0, W, H);
    m.strokeStyle = '#0d2236'; m.lineWidth = 1;                       // graticule
    for (let lon = -180; lon <= 180; lon += 30) { m.beginPath(); m.moveTo(X(lon), 0); m.lineTo(X(lon), H); m.stroke(); }
    for (let lat = -60; lat <= 60; lat += 30) { m.beginPath(); m.moveTo(0, Y(lat)); m.lineTo(W, Y(lat)); m.stroke(); }
    k.fillStyle = '#000'; k.fillRect(0, 0, W, H);
    const key = i => '#' + (i + 1).toString(16).padStart(6, '0');     // country index as a colour
    world.forEach((c, i) => {
      const s = status(c);
      trace(m, c); m.fillStyle = COL[s]; m.fill('evenodd');
      m.strokeStyle = picked === c.id ? '#ffffff' : '#06111f'; m.lineWidth = picked === c.id ? 3 : 1.2; m.stroke();
      trace(k, c); k.fillStyle = key(i); k.fill('evenodd');
    });
    world.forEach((c, i) => {
      if (!tiny(c) || status(c) === 'none') return;
      const x = X(c.c[0]), y = Y(c.c[1]);
      m.beginPath(); m.arc(x, y, 7, 0, 7); m.fillStyle = COL[status(c)]; m.fill();
      m.strokeStyle = picked === c.id ? '#ffffff' : '#06111f'; m.lineWidth = 2; m.stroke();
      k.beginPath(); k.arc(x, y, 9, 0, 7); k.fillStyle = key(i); k.fill();
    });
    return {map, ids: k};
  }

  async function build() {
    const T = await import('./games/three.module.min.js');
    const cv = $('news-globe'), ren = new T.WebGLRenderer({canvas: cv, antialias: true, alpha: true});
    ren.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    const scene = new T.Scene(), cam = new T.PerspectiveCamera(40, 1, .1, 20); cam.position.z = 3.1;
    let {map, ids} = paint();
    const tex = new T.CanvasTexture(map); tex.colorSpace = T.SRGBColorSpace; tex.anisotropy = ren.capabilities.getMaxAnisotropy();
    const ball = new T.Mesh(new T.SphereGeometry(1, 72, 48), new T.MeshLambertMaterial({map: tex}));
    const halo = new T.Mesh(new T.SphereGeometry(1.06, 48, 32), new T.MeshBasicMaterial({color: 0x3fd8ff, transparent: true, opacity: .08, side: T.BackSide}));
    scene.add(ball, halo, new T.AmbientLight(0xffffff, 2.1));
    const sun = new T.DirectionalLight(0xffffff, 1.5); sun.position.set(-1.5, 1.2, 2.5); scene.add(sun);
    ball.rotation.set(.35, -1.75, 0);                                 // start over Europe / Africa
    let spin = true, target = null, dirty = true;

    const size = () => { const w = cv.clientWidth; if (!w) return; ren.setSize(w, w, false); dirty = true; };
    new ResizeObserver(size).observe(cv); size();

    // drag to turn, pinch or wheel to zoom, tap to pick
    const pts = new Map(); let moved = 0, pinch = 0;
    cv.addEventListener('pointerdown', e => { cv.setPointerCapture(e.pointerId); pts.set(e.pointerId, [e.clientX, e.clientY]); moved = 0; spin = false; target = null; });
    cv.addEventListener('pointermove', e => {
      const p = pts.get(e.pointerId); if (!p) return;
      const dx = e.clientX - p[0], dy = e.clientY - p[1]; pts.set(e.pointerId, [e.clientX, e.clientY]);
      if (pts.size === 2) {
        const [a, b] = [...pts.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        if (pinch) cam.position.z = Math.min(5, Math.max(1.6, cam.position.z * pinch / d)); pinch = d;
      } else {
        const k = .0035 * cam.position.z / 3.1 * 420 / Math.max(200, cv.clientWidth);
        ball.rotation.y += dx * k * 1.6; ball.rotation.x = Math.max(-1.3, Math.min(1.3, ball.rotation.x + dy * k * 1.6)); moved += Math.abs(dx) + Math.abs(dy);
      }
      dirty = true;
    });
    const up = e => { if (!pts.has(e.pointerId)) return; const one = pts.size === 1; pts.delete(e.pointerId); pinch = 0; if (one && moved < 8 && e.type === 'pointerup') tap(e); };
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
    cv.addEventListener('wheel', e => { e.preventDefault(); cam.position.z = Math.min(5, Math.max(1.6, cam.position.z * (e.deltaY > 0 ? 1.08 : .92))); dirty = true; }, {passive: false});

    const ray = new T.Raycaster(), v2 = new T.Vector2();
    function tap(e) {
      const r = cv.getBoundingClientRect(); v2.set((e.clientX - r.left) / r.width * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(v2, cam); const hit = ray.intersectObject(ball)[0]; if (!hit) return;
      const px = Math.floor(hit.uv.x * W) % W, py = Math.min(H - 1, Math.floor((1 - hit.uv.y) * H));
      let found = null;
      for (const [ox, oy] of [[0, 0], [3, 0], [-3, 0], [0, 3], [0, -3]]) {
        const d = ids.getImageData((px + ox + W) % W, Math.max(0, Math.min(H - 1, py + oy)), 1, 1).data, i = (d[0] << 16 | d[1] << 8 | d[2]) - 1;
        if (i >= 0 && i < world.length) { found = world[i]; break; }
      }
      if (found) select(found, false);
    }

    globe = {
      repaint() { const p = paint(); ids = p.ids; tex.image = p.map; tex.needsUpdate = true; dirty = true; },
      face(c) {
        const u = (c.c[0] + 180) / 360, th = (90 - c.c[1]) * Math.PI / 180, ph = u * 2 * Math.PI;
        const x = -Math.cos(ph) * Math.sin(th), z = Math.sin(ph) * Math.sin(th);
        let ry = Math.atan2(-x, z); const cur = ball.rotation.y; ry += Math.round((cur - ry) / (2 * Math.PI)) * 2 * Math.PI;
        target = [Math.max(-1.3, Math.min(1.3, c.c[1] * Math.PI / 180)), ry]; spin = false;
      }
    };
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    (function loop() {
      requestAnimationFrame(loop);
      if (!cv.offsetParent) return;                                   // hidden tab or closed desk
      if (spin && !still) { ball.rotation.y += .0018; dirty = true; }
      if (target) {
        const dx = target[0] - ball.rotation.x, dy = target[1] - ball.rotation.y;
        if (still || Math.abs(dx) + Math.abs(dy) < .002) { ball.rotation.x = target[0]; ball.rotation.y = target[1]; target = null; }
        else { ball.rotation.x += dx * .12; ball.rotation.y += dy * .12; }
        dirty = true;
      }
      if (dirty) { ren.render(scene, cam); dirty = false; }
    })();
  }

  function card(name, s, n) {
    const box = el('div', 'news-item');
    const head = el('div', 'news-head'); const dot = el('i', 'news-dot'); dot.style.background = COL[s];
    head.append(dot, el('b', null, name), el('span', 'news-word', WORD[s])); box.append(head);
    if (n) {
      box.append(el('p', null, n.d));
      const a = el('a', 'news-src', 'Source: ' + n.src); a.href = n.url; a.target = '_blank'; a.rel = 'noopener'; box.append(a);
    } else box.append(el('p', 'sub', 'No major story found for this country today.'));
    return box;
  }

  function select(c, turn) {
    picked = c.id;
    const box = $('news-pick'); box.innerHTML = ''; box.hidden = false;
    box.append(card(c.name, status(c), day.countries[c.id]));
    document.querySelectorAll('.news-row').forEach(r => r.classList.toggle('on', r.dataset.id === c.id));
    if (globe) { globe.repaint(); if (turn) { globe.face(c); $('news-globe').scrollIntoView({behavior: 'smooth', block: 'center'}); } }
  }

  function lists() {
    $('news-date').textContent = day.label;
    const lg = $('news-legend'); lg.innerHTML = '';
    ['red', 'yellow', 'green', 'none'].forEach(s => { const r = el('div', 'news-key'); const d = el('i', 'news-dot'); d.style.background = COL[s]; r.append(d, el('span', null, day.legend[s])); lg.append(r); });
    const top = $('news-top'); top.innerHTML = '';
    day.top.forEach(t => {
      const box = el('div', 'news-item'); const head = el('div', 'news-head'); const d = el('i', 'news-dot'); d.style.background = COL[t.s];
      head.append(d, el('b', null, t.t)); const a = el('a', 'news-src', 'Source: ' + t.src); a.href = t.url; a.target = '_blank'; a.rel = 'noopener';
      box.append(head, el('p', null, t.d), a); top.append(box);
    });
    const all = $('news-countries'); all.innerHTML = '';
    ['red', 'yellow', 'green'].forEach(s => {
      const rows = world.filter(c => status(c) === s).sort((a, b) => a.name.localeCompare(b.name));
      all.append(el('h3', null, WORD[s] + ' · ' + rows.length));
      rows.forEach(c => {
        const r = el('button', 'news-row'); r.dataset.id = c.id; const d = el('i', 'news-dot'); d.style.background = COL[s];
        r.append(d, el('b', null, c.name), el('small', null, day.countries[c.id].d)); r.onclick = () => select(c, true); all.append(r);
      });
    });
    const rated = world.filter(c => status(c) !== 'none').length;
    $('news-note').textContent = day.compiled + ' ' + rated + ' countries have a story; the rest are grey. Colours describe the day\'s headlines, not the country.';
  }

  async function open() {
    if (day || loading) return; loading = true;
    try {
      [day, world] = await Promise.all([fetch('news/today.json', {cache: 'no-cache'}).then(r => r.json()), fetch('news/world.json').then(r => r.json())]);
      lists();
      try { await build(); } catch (e) { $('news-globe').hidden = true; $('news-globe-fail').hidden = false; }
    } catch (e) { $('news-date').textContent = 'Could not load today\'s news.'; day = null; }
    loading = false;
  }

  window.addEventListener('DOMContentLoaded', () => {
    const desk = $('news-desk'); if (!desk) return;
    desk.onclick = () => {
      const box = $('news-panel'), show = box.hidden; box.hidden = !show;
      desk.setAttribute('aria-expanded', String(show));
      $('news-hint').textContent = show ? 'Tap the desk again to put the paper away.' : "Tap the desk for today's news on the globe.";
      if (show) open();
    };
  });
})();

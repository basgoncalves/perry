// Shared 3D globe for the Office desks (news, cyber, flights). Uses the three.js already shipped with the game.
// PerryGlobe.world()            -> country outlines (news/world.json)
// PerryGlobe.create(canvas, o)  -> globe; o.colorOf(country) gives the fill, o.onPick(country) and o.onPoint(i) get taps.
window.PerryGlobe = (() => {
  let worldP = null, threeP = null;
  const world = () => worldP || (worldP = fetch('news/world.json').then(r => r.json()));
  const three = () => threeP || (threeP = import('./games/three.module.min.js'));
  const xyz = (lon, lat, r) => {
    const ph = (lon + 180) / 360 * 2 * Math.PI, th = (90 - lat) * Math.PI / 180;
    return [-Math.cos(ph) * Math.sin(th) * r, Math.cos(th) * r, Math.sin(ph) * Math.sin(th) * r];
  };

  async function create(cv, o) {
    const [T, W0] = await Promise.all([three(), world()]);
    const W = o.res || 2048, H = W / 2, minZ = o.minZ || 1.6;
    const X = lon => (lon + 180) / 360 * W, Y = lat => (90 - lat) / 180 * H;
    let picked = null;

    // Rings that cross the date line are unwrapped and drawn three times (shifted a world left and right);
    // a ring that circles a pole (Antarctica) is closed along that pole.
    const unwrap = r => {
      const pts = []; let off = 0, sum = 0;
      for (let i = 0; i < r.length; i += 2) {
        if (i) { const d = r[i] - r[i - 2]; if (d > 180) off -= 360; else if (d < -180) off += 360; }
        pts.push([r[i] + off, r[i + 1]]); sum += r[i + 1];
      }
      if (Math.abs(off) > 180) { const pole = sum < 0 ? -90 : 90; pts.push([pts[pts.length - 1][0], pole], [pts[0][0], pole]); }
      return pts;
    };
    const shapes = W0.map(c => c.p.map(poly => poly.map(unwrap)));    // per country: polygons of rings of [lon, lat]
    function trace(ctx, i) {
      ctx.beginPath();
      shapes[i].forEach(poly => poly.forEach(pts => { for (const s of [-360, 0, 360]) { pts.forEach(([x, y], j) => j ? ctx.lineTo(X(x + s), Y(y)) : ctx.moveTo(X(x + s), Y(y))); ctx.closePath(); } }));
    }
    // Which country is at this longitude and latitude? (even-odd ray test, trying the point a world left and right too)
    const inRing = (pts, x, y) => { let hit = false; for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) { const a = pts[i], b = pts[j]; if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) hit = !hit; } return hit; };
    function countryAt(lon, lat) {
      // a small country's dot wins right on the dot; a country's own outline wins next; a near miss of a dot counts last
      const dotNear = d => { if (o.dot) for (const c of W0) if (c.a < 3 && o.dot(c) && Math.hypot((c.c[0] - lon) * Math.cos(lat * Math.PI / 180), c.c[1] - lat) < d) return c; return null; };
      const onDot = dotNear(.45); if (onDot) return onDot;
      for (let i = 0; i < W0.length; i++) for (const poly of shapes[i]) for (const s of [0, -360, 360]) {
        let inside = false; for (const pts of poly) if (inRing(pts, lon + s, lat)) inside = !inside;
        if (inside) return W0[i];
      }
      return dotNear(1.4);
    }
    function paint() {
      const map = document.createElement('canvas'); map.width = W; map.height = H;
      const m = map.getContext('2d');
      m.fillStyle = '#06111f'; m.fillRect(0, 0, W, H);
      m.strokeStyle = '#0d2236'; m.lineWidth = W / 2048;               // graticule
      for (let lon = -180; lon <= 180; lon += 30) { m.beginPath(); m.moveTo(X(lon), 0); m.lineTo(X(lon), H); m.stroke(); }
      for (let lat = -60; lat <= 60; lat += 30) { m.beginPath(); m.moveTo(0, Y(lat)); m.lineTo(W, Y(lat)); m.stroke(); }
      W0.forEach((c, i) => {
        trace(m, i); m.fillStyle = o.colorOf(c); m.fill('evenodd');
        if (picked != null && picked === c.id) { m.strokeStyle = '#ffffff'; m.lineWidth = 3 * W / 2048; m.stroke(); }
      });
      // Countries too small to see get a dot so their colour still shows.
      if (o.dot) W0.forEach(c => {
        if (c.a >= 3 || !o.dot(c)) return;
        m.beginPath(); m.arc(X(c.c[0]), Y(c.c[1]), 7, 0, 7); m.fillStyle = o.colorOf(c); m.fill();
        m.strokeStyle = picked != null && picked === c.id ? '#ffffff' : '#06111f'; m.lineWidth = 2; m.stroke();
      });
      return map;
    }

    const ren = new T.WebGLRenderer({canvas: cv, antialias: true, alpha: true}), pr = Math.min(devicePixelRatio || 1, 2);
    ren.setPixelRatio(pr);
    const scene = new T.Scene(), cam = new T.PerspectiveCamera(40, 1, .05, 20); cam.position.z = o.z || 3.1;
    const tex = new T.CanvasTexture(paint()); tex.colorSpace = T.SRGBColorSpace; tex.anisotropy = ren.capabilities.getMaxAnisotropy();
    const ball = new T.Mesh(new T.SphereGeometry(1, 96, 64), new T.MeshLambertMaterial({map: tex}));
    const halo = new T.Mesh(new T.SphereGeometry(1.06, 48, 32), new T.MeshBasicMaterial({color: 0x3fd8ff, transparent: true, opacity: .08, side: T.BackSide}));
    scene.add(ball, halo, new T.AmbientLight(0xffffff, 2.1));
    const sun = new T.DirectionalLight(0xffffff, 1.5); sun.position.set(-1.5, 1.2, 2.5); scene.add(sun);

    // crisp borders as lines, so they stay sharp when zoomed in
    const seg = [];
    W0.forEach(c => c.p.forEach(poly => poly.forEach(r => { for (let i = 0; i + 3 < r.length; i += 2) seg.push(...xyz(r[i], r[i + 1], 1.0015), ...xyz(r[i + 2], r[i + 3], 1.0015)); })));
    const bg = new T.BufferGeometry(); bg.setAttribute('position', new T.Float32BufferAttribute(seg, 3));
    ball.add(new T.LineSegments(bg, new T.LineBasicMaterial({color: o.border || 0x06111f})));

    // points (aircraft): round dots that turn with the globe
    const dotCv = document.createElement('canvas'); dotCv.width = dotCv.height = 32;
    const dc = dotCv.getContext('2d'); dc.beginPath(); dc.arc(16, 16, 13, 0, 7); dc.fillStyle = '#fff'; dc.fill(); dc.lineWidth = 4; dc.strokeStyle = '#04101c'; dc.stroke();
    const dotTex = new T.CanvasTexture(dotCv);
    const pg = new T.BufferGeometry(), pts = new T.Points(pg, new T.PointsMaterial({size: (o.pointSize || 8) * pr, sizeAttenuation: false, vertexColors: true, map: dotTex, alphaTest: .5, transparent: true}));
    const mg = new T.BufferGeometry(), mark = new T.Points(mg, new T.PointsMaterial({size: (o.pointSize || 8) * 2 * pr, sizeAttenuation: false, color: 0xffffff, map: dotTex, alphaTest: .5, transparent: true}));
    pts.visible = mark.visible = false; pts.frustumCulled = mark.frustumCulled = false; ball.add(pts, mark);
    let pointList = [];

    const v = o.view || [.35, -1.75]; ball.rotation.set(v[0], v[1], 0);
    let spin = o.spin !== false, target = null, zTarget = null, dirty = true;
    const size = () => { const w = cv.clientWidth; if (!w) return; ren.setSize(w, w, false); dirty = true; };
    new ResizeObserver(size).observe(cv); size();

    // drag to turn, pinch or wheel to zoom, tap to pick
    const fingers = new Map(); let moved = 0, pinch = 0;
    const zoom = f => { cam.position.z = Math.min(5, Math.max(minZ, cam.position.z * f)); zTarget = null; dirty = true; };
    cv.addEventListener('pointerdown', e => { cv.setPointerCapture(e.pointerId); fingers.set(e.pointerId, [e.clientX, e.clientY]); moved = 0; spin = false; target = null; });
    cv.addEventListener('pointermove', e => {
      const p = fingers.get(e.pointerId); if (!p) return;
      const dx = e.clientX - p[0], dy = e.clientY - p[1]; fingers.set(e.pointerId, [e.clientX, e.clientY]);
      if (fingers.size === 2) { const [a, b] = [...fingers.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]); if (pinch) zoom(pinch / d); pinch = d; }
      else {
        const k = 2 * Math.tan(20 * Math.PI / 180) * (cam.position.z - 1) / Math.max(200, cv.clientWidth);   // the surface follows the finger
        ball.rotation.y += dx * k; ball.rotation.x = Math.max(-1.3, Math.min(1.3, ball.rotation.x + dy * k)); moved += Math.abs(dx) + Math.abs(dy);
      }
      dirty = true;
    });
    const up = e => { if (!fingers.has(e.pointerId)) return; const one = fingers.size === 1; fingers.delete(e.pointerId); pinch = 0; if (one && moved < 8 && e.type === 'pointerup') tap(e); };
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
    cv.addEventListener('wheel', e => { e.preventDefault(); zoom(e.deltaY > 0 ? 1.08 : .92); }, {passive: false});

    const ray = new T.Raycaster(), v2 = new T.Vector2(), v3 = new T.Vector3();
    function tap(e) {
      const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
      if (o.onPoint && pointList.length) {                             // nearest aircraft within a fingertip
        let best = -1, bd = 22; ball.updateMatrixWorld();
        pointList.forEach((p, i) => {
          v3.set(...xyz(p.lon, p.lat, 1.012)).applyMatrix4(ball.matrixWorld);
          if (v3.dot(cam.position) < v3.lengthSq()) return;            // far side of the globe
          v3.project(cam); const d = Math.hypot((v3.x + 1) / 2 * r.width - mx, (1 - v3.y) / 2 * r.height - my);
          if (d < bd) { bd = d; best = i; }
        });
        if (best >= 0) return o.onPoint(best);
      }
      if (!o.onPick) return;
      v2.set(mx / r.width * 2 - 1, -(my / r.height) * 2 + 1); ray.setFromCamera(v2, cam);
      const hit = ray.intersectObject(ball, false)[0]; if (!hit) return;
      const c = countryAt(hit.uv.x * 360 - 180, hit.uv.y * 180 - 90); if (c) o.onPick(c);
    }

    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    (function loop() {
      requestAnimationFrame(loop);
      if (!cv.offsetParent) return;                                    // hidden tab or closed desk
      if (spin && !still) { ball.rotation.y += .0018; dirty = true; }
      if (target) {
        const dx = target[0] - ball.rotation.x, dy = target[1] - ball.rotation.y;
        if (still || Math.abs(dx) + Math.abs(dy) < .002) { ball.rotation.x = target[0]; ball.rotation.y = target[1]; target = null; }
        else { ball.rotation.x += dx * .12; ball.rotation.y += dy * .12; }
        dirty = true;
      }
      if (zTarget != null) {
        const dz = zTarget - cam.position.z;
        if (still || Math.abs(dz) < .004) { cam.position.z = zTarget; zTarget = null; } else cam.position.z += dz * .12;
        dirty = true;
      }
      if (dirty) { ren.render(scene, cam); dirty = false; }
    })();

    return {
      world: W0,
      select(id) { picked = id; this.repaint(); },
      repaint() { tex.image = paint(); tex.needsUpdate = true; dirty = true; },
      face(lon, lat, z) {
        const [x, , zz] = xyz(lon, lat, 1);
        let ry = Math.atan2(-x, zz); ry += Math.round((ball.rotation.y - ry) / (2 * Math.PI)) * 2 * Math.PI;
        target = [Math.max(-1.3, Math.min(1.3, lat * Math.PI / 180)), ry]; spin = false;
        if (z) zTarget = Math.max(minZ, z);
      },
      setPoints(list) {                                                // [{lon, lat, color:[r,g,b]}]
        pointList = list; const pos = [], col = [];
        list.forEach(p => { pos.push(...xyz(p.lon, p.lat, 1.012)); col.push(...p.color); });
        pg.setAttribute('position', new T.Float32BufferAttribute(pos, 3)); pg.setAttribute('color', new T.Float32BufferAttribute(col, 3));
        pts.visible = list.length > 0; dirty = true;
      },
      mark(p) { if (!p) { mark.visible = false; dirty = true; return; } mg.setAttribute('position', new T.Float32BufferAttribute(xyz(p.lon, p.lat, 1.013), 3)); mark.visible = true; dirty = true; }
    };
  }
  return {world, create};
})();

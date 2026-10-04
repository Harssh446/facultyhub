(function () {
  const root = document.documentElement;
  const css = n => getComputedStyle(root).getPropertyValue(n).trim();

  // theme + sidebar
  const tt = document.getElementById('theme-toggle');
  if (tt) tt.addEventListener('click', () => {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next; localStorage.setItem('fh-theme', next); drawCharts();
  });
  const mb = document.getElementById('menu-btn'), sb = document.getElementById('sidebar');
  if (mb && sb) mb.addEventListener('click', () => sb.classList.toggle('open'));

  // confirm dialogs, print, copy
  document.querySelectorAll('form[data-confirm]').forEach(f => f.addEventListener('submit', e => {
    if (!confirm(f.dataset.confirm)) e.preventDefault();
  }));
  document.querySelectorAll('[data-print]').forEach(b => b.addEventListener('click', () => window.print()));
  document.querySelectorAll('[data-copy]').forEach(b => b.addEventListener('click', () => {
    const el = document.querySelector(b.dataset.copy); if (!el) return;
    const done = () => { const t = b.textContent; b.textContent = 'Copied!'; setTimeout(() => b.textContent = t, 1500); };
    if (navigator.clipboard) navigator.clipboard.writeText(el.innerText).then(done); else { alert('Select the text and copy it manually.'); }
  }));

  // attendance: set all
  document.querySelectorAll('[data-set-all]').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('input[type=radio][value="' + b.dataset.setAll + '"]').forEach(r => r.checked = true);
    updateTally();
  }));
  function updateTally() {
    const el = document.getElementById('tally'); if (!el) return;
    const c = { Present: 0, Absent: 0, Late: 0 };
    document.querySelectorAll('input[type=radio]:checked').forEach(r => c[r.value]++);
    el.textContent = c.Present + ' present · ' + c.Late + ' late · ' + c.Absent + ' absent';
  }
  document.querySelectorAll('.att-radio').forEach(r => r.addEventListener('change', updateTally));
  updateTally();

  // subject -> topic groups
  document.querySelectorAll('select[data-topic-switch]').forEach(sel => {
    const apply = () => document.querySelectorAll('.topic-group').forEach(g => {
      const show = g.dataset.subject === sel.value; g.hidden = !show;
      if (!show) g.querySelectorAll('input').forEach(i => i.checked = false);
    });
    sel.addEventListener('change', apply); apply();
  });

  // marks totals
  function gradeFor(p) { return p >= 90 ? 'A+' : p >= 80 ? 'A' : p >= 70 ? 'B+' : p >= 60 ? 'B' : p >= 50 ? 'C' : p >= 40 ? 'D' : 'F'; }
  document.querySelectorAll('table[data-total]').forEach(tb => {
    const total = +tb.dataset.total;
    tb.querySelectorAll('tr.mark-row').forEach(tr => {
      const upd = () => {
        let t = 0, any = false;
        tr.querySelectorAll('input.mk').forEach(i => {
          if (i.value !== '') { any = true; t += Math.min(Math.max(parseFloat(i.value) || 0, 0), +i.dataset.max); }
        });
        tr.querySelector('.tot').textContent = any ? String(Math.round(t * 10) / 10) : '–';
        tr.querySelector('.gr').textContent = any ? gradeFor(t / total * 100) : '–';
      };
      tr.addEventListener('input', upd); upd();
    });
  });

  // charts
  function setup(c) {
    const dpr = window.devicePixelRatio || 1, w = c.parentElement.clientWidth, h = +c.dataset.height || 240;
    c.width = w * dpr; c.height = h * dpr; c.style.width = w + 'px'; c.style.height = h + 'px';
    const x = c.getContext('2d'); x.scale(dpr, dpr); x.clearRect(0, 0, w, h); return { x, w, h };
  }
  function bar(c) {
    const labels = JSON.parse(c.dataset.labels), vals = JSON.parse(c.dataset.values);
    const max = +c.dataset.max || Math.max(...vals, 1), { x, w, h } = setup(c);
    const rot = labels.length > 7, pad = { l: 34, r: 8, t: 10, b: rot ? 54 : 40 };
    const cw = w - pad.l - pad.r, ch = h - pad.t - pad.b, bw = cw / labels.length;
    x.font = '11px system-ui'; x.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = pad.t + ch - ch * i / 4;
      x.strokeStyle = css('--line'); x.beginPath(); x.moveTo(pad.l, y); x.lineTo(w - pad.r, y); x.stroke();
      x.fillStyle = css('--muted'); x.textAlign = 'right'; x.fillText(Math.round(max * i / 4), pad.l - 6, y + 4);
    }
    vals.forEach((v, i) => {
      const bh = ch * Math.min(v, max) / max, bx = pad.l + i * bw + bw * .18;
      x.fillStyle = css('--accent'); x.fillRect(bx, pad.t + ch - bh, bw * .64, bh);
      x.fillStyle = css('--muted'); x.save();
      x.translate(pad.l + i * bw + bw / 2, pad.t + ch + 14);
      if (rot) { x.rotate(-Math.PI / 4); x.textAlign = 'right'; } else x.textAlign = 'center';
      let t = labels[i]; if (!rot && t.length > 12) t = t.slice(0, 11) + '…';
      x.fillText(t, 0, 0); x.restore();
    });
  }
  function donut(c) {
    const labels = JSON.parse(c.dataset.labels), vals = JSON.parse(c.dataset.values), colors = JSON.parse(c.dataset.colors);
    const { x, w, h } = setup(c), total = vals.reduce((a, b) => a + b, 0), r = Math.min(h / 2 - 12, w / 3);
    const cx = r + 16, cy = h / 2; let ang = -Math.PI / 2;
    x.lineWidth = r * .38;
    if (!total) { x.strokeStyle = css('--line'); x.beginPath(); x.arc(cx, cy, r * .81, 0, 7); x.stroke(); }
    vals.forEach((v, i) => {
      const a = v / (total || 1) * Math.PI * 2; x.strokeStyle = colors[i];
      x.beginPath(); x.arc(cx, cy, r * .81, ang, ang + a); x.stroke(); ang += a;
    });
    x.fillStyle = css('--text'); x.font = 'bold 22px system-ui'; x.textAlign = 'center'; x.fillText(total, cx, cy + 4);
    x.font = '11px system-ui'; x.fillStyle = css('--muted'); x.fillText('students', cx, cy + 20);
    labels.forEach((l, i) => {
      const ly = cy - labels.length * 12 + i * 26 + 10, lx = cx + r + 28;
      x.fillStyle = colors[i]; x.fillRect(lx, ly - 9, 12, 12);
      x.fillStyle = css('--text'); x.textAlign = 'left'; x.font = '13px system-ui'; x.fillText(l + ': ' + vals[i], lx + 20, ly + 2);
    });
  }
  function drawCharts() {
    document.querySelectorAll('canvas[data-chart]').forEach(c => c.dataset.chart === 'donut' ? donut(c) : bar(c));
  }
  drawCharts();
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(drawCharts, 150); });
})();
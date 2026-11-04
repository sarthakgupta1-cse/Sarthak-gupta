// Renders RezenIt carousels from a content JSON into 1080x1350 PNG slides.
// Usage: node render.js content/2026-11-04.json out/
// Output: out/<DD-MM-YY> Carousel <n>/<1..6>.png
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const W = 1080, H = 1350;
const ASSETS = path.join(__dirname, 'assets');
const dataUri = (f, mime) => `data:${mime};base64,${fs.readFileSync(path.join(ASSETS, f)).toString('base64')}`;
const MARK = dataUri('mark-t.png', 'image/png');
const LOGO = dataUri('logo-t.png', 'image/png');
const APP = dataUri('app.jpg', 'image/jpeg');

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// content is authored by us: allows <b>, &amp; etc. [[text]] -> gradient highlight
const fmt = s => String(s).replace(/\[\[(.+?)\]\]/g, '<span class="hl">$1</span>').replace(/\n/g, '<br>');

// deterministic star field, identical on every slide of a carousel
function stars(seed) {
  let x = seed; const r = () => (x = (x * 9301 + 49297) % 233280) / 233280;
  let out = '';
  for (let i = 0; i < 140; i++) {
    const s = r() < 0.9 ? 1.5 : 2.5;
    out += `<circle cx="${(r() * W).toFixed(0)}" cy="${(r() * H).toFixed(0)}" r="${s}" fill="#fff" opacity="${(0.08 + r() * 0.35).toFixed(2)}"/>`;
  }
  return `<svg class="stars" width="${W}" height="${H}">${out}</svg>`;
}

function css(t) {
  return `
  @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&display=block');
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:${W}px;height:${H}px;background:${t.bg};overflow:hidden}
  body{font-family:'Montserrat','Inter Display','Inter',sans-serif;color:#EEF1FF;-webkit-font-smoothing:antialiased}
  .slide{position:relative;width:${W}px;height:${H}px;background:${t.bg};padding:88px 92px 92px;display:flex;flex-direction:column}
  .stars{position:absolute;inset:0;z-index:0}
  .slide>*:not(.stars){position:relative;z-index:1}
  .top{display:flex;align-items:center;justify-content:space-between;height:64px}
  .brand{display:flex;align-items:center;gap:14px;font-weight:600;font-size:30px;letter-spacing:.5px;
    background:linear-gradient(90deg,${t.a1},${t.a2});-webkit-background-clip:text;color:transparent}
  .brand img{width:46px;height:58px;object-fit:contain}
  .count{font-family:'Inter';font-weight:600;font-size:24px;color:rgba(255,255,255,.55);letter-spacing:2px}
  .main{flex:1;display:flex;flex-direction:column;justify-content:center}
  .kicker{display:inline-block;align-self:flex-start;font-family:'Inter';font-weight:700;font-size:24px;letter-spacing:4px;text-transform:uppercase;
    color:${t.a1};border:2px solid ${t.a1}55;background:${t.a1}14;padding:12px 22px;border-radius:999px;margin-bottom:40px}
  .hl{background:linear-gradient(95deg,${t.a1} 0%,${t.a2} 100%);-webkit-background-clip:text;color:transparent}
  h1{font-weight:900;font-size:${t.hookSize || 104}px;line-height:1.04;letter-spacing:-2.5px}
  h2{font-weight:800;font-size:72px;line-height:1.08;letter-spacing:-1.5px;margin-bottom:36px}
  .sub{font-family:'Inter';font-weight:500;font-size:38px;line-height:1.38;color:rgba(238,241,255,.78);margin-top:44px;max-width:860px}
  .body{font-family:'Inter';font-weight:500;font-size:40px;line-height:1.42;color:rgba(238,241,255,.82)}
  .body b{color:#fff;font-weight:700}
  .num{font-weight:900;font-size:150px;line-height:1;margin-bottom:18px}
  .phase{font-family:'Inter';font-weight:700;font-size:30px;letter-spacing:3px;text-transform:uppercase;color:${t.a1};margin-bottom:20px}
  .bar{display:flex;gap:10px;margin-bottom:56px}
  .bar i{flex:1;height:10px;border-radius:6px;background:rgba(255,255,255,.12)}
  .bar i.on{background:linear-gradient(90deg,${t.a1},${t.a2})}
  ul.items{list-style:none;display:flex;flex-direction:column;gap:30px}
  ul.items li{display:flex;gap:28px;align-items:flex-start;font-family:'Inter';font-weight:500;font-size:37px;line-height:1.34;color:rgba(238,241,255,.86)}
  ul.items li .n{flex:0 0 64px;height:64px;border-radius:20px;display:flex;align-items:center;justify-content:center;
    font-family:'Montserrat';font-weight:800;font-size:30px;color:${t.bg};background:linear-gradient(135deg,${t.a1},${t.a2})}
  ul.items li b{color:#fff;font-weight:700}
  .chain{display:flex;flex-direction:column;gap:14px;margin:10px 0 44px}
  .chain div{display:flex;align-items:center;gap:22px;font-weight:800;font-size:44px}
  .chain div span.dot{width:22px;height:22px;border-radius:50%;background:linear-gradient(135deg,${t.a1},${t.a2});box-shadow:0 0 24px ${t.a2}}
  .chain .arrow{padding-left:4px;font-size:30px;color:rgba(255,255,255,.35);font-weight:600;height:26px;line-height:26px}
  .note{margin-top:44px;font-family:'Inter';font-weight:600;font-size:32px;line-height:1.4;color:#fff;
    padding:28px 34px;border-radius:24px;background:rgba(255,255,255,.06);border-left:6px solid ${t.a1}}
  .bottom{display:flex;align-items:center;justify-content:space-between;height:70px}
  .site{font-family:'Inter';font-weight:600;font-size:24px;color:rgba(255,255,255,.45);letter-spacing:1px}
  .swipe{font-family:'Inter';font-weight:700;font-size:26px;color:${t.bg};background:linear-gradient(90deg,${t.a1},${t.a2});
    padding:16px 30px;border-radius:999px;letter-spacing:.5px}
  /* CTA */
  .cta{align-items:center;text-align:center}
  .cta .logo{width:230px;height:230px;object-fit:contain;margin-bottom:6px}
  .cta h2{font-size:64px;margin:0 0 18px}
  .cta .lead{font-family:'Inter';font-weight:500;font-size:32px;line-height:1.38;color:rgba(238,241,255,.78);max-width:840px}
  .phone{position:relative;width:500px;height:470px;margin:34px 0 40px;border-radius:36px;overflow:hidden;
    border:2px solid ${t.a2}66;box-shadow:0 0 80px ${t.a2}40,0 0 0 10px rgba(255,255,255,.03)}
  .phone img{width:100%;height:100%;object-fit:cover;object-position:50% 8%}
  .btn{font-weight:800;font-size:40px;color:${t.bg};background:linear-gradient(90deg,${t.a1},${t.a2});padding:30px 64px;border-radius:999px;
    box-shadow:0 12px 50px ${t.a2}55}
  .stores{margin-top:22px;font-family:'Inter';font-weight:600;font-size:26px;color:rgba(255,255,255,.6);letter-spacing:.5px}
  `;
}

function header(t, i) {
  return `<div class="top"><div class="brand"><img src="${MARK}">RezenIt</div><div class="count">${i}/6</div></div>`;
}
function footer(t, i) {
  return `<div class="bottom"><div class="site">rezenit.com</div>${i < 6 ? `<div class="swipe">${i === 1 ? 'Swipe →' : 'Keep going →'}</div>` : ''}</div>`;
}

function slideBody(s, t, i) {
  switch (s.type) {
    case 'hook':
      return `<div class="main">${s.kicker ? `<div class="kicker">${esc(s.kicker)}</div>` : ''}<h1>${fmt(s.title)}</h1>${s.sub ? `<div class="sub">${fmt(s.sub)}</div>` : ''}</div>`;
    case 'point':
      return `<div class="main">${s.num ? `<div class="num hl">${esc(s.num)}</div>` : ''}${s.phase ? `<div class="phase">${esc(s.phase)}</div>` : ''}
        ${s.progress ? `<div class="bar">${[1,2,3,4].map(k => `<i class="${k <= s.progress ? 'on' : ''}"></i>`).join('')}</div>` : ''}
        <h2>${fmt(s.title)}</h2><div class="body">${fmt(s.body)}</div>${s.note ? `<div class="note">${fmt(s.note)}</div>` : ''}</div>`;
    case 'chain':
      return `<div class="main"><h2>${fmt(s.title)}</h2><div class="chain">${s.steps.map((x, k) =>
        `${k ? '<div class="arrow">↓</div>' : ''}<div><span class="dot"></span>${esc(x)}</div>`).join('')}</div>
        <div class="body">${fmt(s.body)}</div></div>`;
    case 'list':
      return `<div class="main"><h2>${fmt(s.title)}</h2><ul class="items">${s.items.map((x, k) =>
        `<li><span class="n">${s.marks ? esc(s.marks[k]) : k + 1}</span><span>${fmt(x)}</span></li>`).join('')}</ul>
        ${s.note ? `<div class="note">${fmt(s.note)}</div>` : ''}</div>`;
    case 'cta':
      return `<div class="main cta"><img class="logo" src="${LOGO}"><h2>${fmt(s.title)}</h2><div class="lead">${fmt(s.lead)}</div>
        <div class="phone"><img src="${APP}"></div><div class="btn">${esc(s.button || 'Download RezenIt')}</div>
        <div class="stores">${esc(s.stores || 'Available on the App Store & Google Play')}</div></div>`;
  }
  throw new Error('unknown slide type ' + s.type);
}

function html(c, s, i) {
  const t = c.theme;
  return `<!doctype html><html><head><meta charset="utf-8"><style>${css(t)}</style></head><body>
  <div class="slide">${stars(c.seed || 7)}${s.type === 'cta' ? '' : header(t, i)}${slideBody(s, t, i)}${s.type === 'cta' ? '' : footer(t, i)}</div></body></html>`;
}

(async () => {
  const [contentFile, outDir = path.join(__dirname, 'out')] = process.argv.slice(2);
  const spec = JSON.parse(fs.readFileSync(contentFile, 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  for (const [n, c] of spec.carousels.entries()) {
    if (c.slides.length !== 6) throw new Error(`carousel ${n + 1} must have 6 slides`);
    const dir = path.join(outDir, `${spec.date} Carousel ${n + 1}`);
    fs.mkdirSync(dir, { recursive: true });
    for (const [k, s] of c.slides.entries()) {
      await page.setContent(html(c, s, k + 1), { waitUntil: 'networkidle' });
      await page.evaluate(() => document.fonts.ready);
      const over = await page.evaluate(() => document.querySelector('.slide').scrollHeight > 1350);
      if (over) console.warn(`WARN overflow: carousel ${n + 1} slide ${k + 1}`);
      await page.screenshot({ path: path.join(dir, `${k + 1}.png`) });
    }
    console.log('rendered', dir);
  }
  await browser.close();
})();

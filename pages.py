# pages.py  -  EMIX v9.7.0
# شامل: LOGIN_HTML, DASHBOARD_HTML, get_public_page_html()

LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ورود · EMIX PRO</title>
<link rel="preload" href="/assets/fonts.css" as="style" onerror="this.remove()">
<link rel="stylesheet" href="/assets/fonts.css" onerror="this.remove()">
<link rel="stylesheet" href="/assets/tabler-icons.min.css" onerror="this.href='https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.19.0/dist/tabler-icons.min.css'">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" media="print" onload="this.media='all'">
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
:root{
  --bg:#0A0A0F;--bg2:#14141C;--card:rgba(20,20,28,0.72);--card-in:rgba(255,255,255,0.04);
  --accent:#8B5CF6;--accent2:#FACC15;--signal:#A855F7;
  --text:#FFFFFF;--dim:#6B7280;--mid:#9CA3AF;--border:rgba(139,92,246,0.22);
  --glow:rgba(139,92,246,.28);--glow-signal:rgba(250,204,21,.20);
  --danger:#EF4444;
}
[data-theme="light"]{
  --bg:#F5F5F7;--bg2:#FFFFFF;--card:rgba(255,255,255,0.92);--card-in:rgba(139,92,246,0.04);
  --accent:#7C3AED;--accent2:#CA8A04;--signal:#9333EA;
  --text:#0A0A0F;--dim:#6B7280;--mid:#4B5563;--border:rgba(124,58,237,0.18);
  --glow:rgba(124,58,237,.18);--glow-signal:rgba(202,138,4,.14);
}
html,body{height:100%;overflow:hidden}
body{
  font-family:'Vazirmatn',sans-serif;background:var(--bg);display:flex;align-items:center;justify-content:center;
  padding:20px;position:relative;transition:background .5s ease
}
.mono{font-family:'JetBrains Mono',ui-monospace,monospace}

/* ══════ پس‌زمینه ══════ */
.bg{position:fixed;inset:0;z-index:0;background:
  radial-gradient(ellipse 60% 46% at 18% 8%,var(--glow),transparent 68%),
  radial-gradient(ellipse 50% 40% at 88% 92%,var(--glow-signal),transparent 65%),
  var(--bg);transition:background .5s ease;animation:bgshift 14s ease-in-out infinite}
@keyframes bgshift{
  0%,100%{filter:hue-rotate(0deg) brightness(1)}
  50%{filter:hue-rotate(8deg) brightness(1.05)}
}
.grid{position:fixed;inset:0;z-index:0;background-image:
  linear-gradient(rgba(139,92,246,0.04) 1px,transparent 1px),
  linear-gradient(90deg,rgba(139,92,246,0.04) 1px,transparent 1px);
  background-size:44px 44px;
  mask-image:radial-gradient(ellipse 62% 62% at 50% 42%,black 25%,transparent 85%);
  animation:gridpan 30s linear infinite}
@keyframes gridpan{from{background-position:0 0}to{background-position:88px 88px}}

/* ذرات شناور — عنصر جدید */
.particles{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
.particle{position:absolute;border-radius:50%;background:var(--signal);opacity:0;box-shadow:0 0 10px var(--signal);animation:floatp linear infinite}
@keyframes floatp{
  0%{transform:translateY(110vh) translateX(0) scale(.4);opacity:0}
  8%{opacity:.55}
  92%{opacity:.4}
  100%{transform:translateY(-10vh) translateX(var(--drift,40px)) scale(1);opacity:0}
}

/* مسیر سیگنال — عنصر امضادار: یک خط مسیر شبکه با پالس متحرک */
.route{position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.55}
.route svg{width:100%;height:100%}
.route path{fill:none;stroke:var(--border);stroke-width:1;stroke-dasharray:2 7;stroke-linecap:round;animation:dashflow 6s linear infinite}
@keyframes dashflow{to{stroke-dashoffset:-90}}
.pulse-dot{filter:drop-shadow(0 0 6px var(--signal))}

/* ══════ سوییچ تم ══════ */
.theme-switch{position:fixed;top:22px;left:22px;z-index:50}
.theme-btn{
  width:42px;height:42px;border-radius:12px;background:var(--card);border:1px solid var(--border);
  color:var(--mid);display:flex;align-items:center;justify-content:center;font-size:18px;cursor:pointer;
  backdrop-filter:blur(16px);transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden
}
.theme-btn:hover{border-color:var(--accent);color:var(--accent2);transform:translateY(-2px)}
.theme-btn i{position:relative;z-index:1;transition:transform .45s cubic-bezier(.34,1.56,.64,1)}
.theme-btn.spin i{transform:rotate(300deg)}

/* نشان وضعیت برخط بودن گیت‌وی */
.status-badge{
  position:fixed;top:22px;right:22px;z-index:50;display:flex;align-items:center;gap:7px;
  background:var(--card);border:1px solid var(--border);border-radius:999px;padding:8px 14px 8px 12px;
  backdrop-filter:blur(16px);animation:badgein .6s cubic-bezier(.16,1,.3,1) .3s backwards
}
@keyframes badgein{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:none}}
.status-dot{width:7px;height:7px;border-radius:50%;background:var(--signal);position:relative;flex-shrink:0}
.status-dot::after{content:'';position:absolute;inset:-4px;border-radius:50%;background:var(--signal);opacity:.4;animation:ping 1.8s cubic-bezier(0,0,.2,1) infinite}
@keyframes ping{0%{transform:scale(.6);opacity:.5}75%,100%{transform:scale(2.1);opacity:0}}
.status-badge span{font-size:10.5px;color:var(--mid);letter-spacing:.03em}

/* ══════ کارت ══════ */
.wrap{position:relative;z-index:10;width:100%;max-width:392px;animation:cardIn .65s cubic-bezier(.16,1,.3,1);perspective:900px}
@keyframes cardIn{from{opacity:0;transform:translateY(20px) scale(.975)}to{opacity:1;transform:none}}
.card{
  background:var(--card);border:1px solid var(--border);border-radius:20px;padding:38px 32px 30px;
  backdrop-filter:blur(30px);box-shadow:0 30px 80px -20px rgba(0,0,0,.55),0 0 0 1px var(--card-in) inset;
  position:relative;overflow:hidden;transition:transform .35s cubic-bezier(.16,1,.3,1),box-shadow .35s ease
}
.card:hover{box-shadow:0 34px 90px -18px rgba(0,0,0,.6),0 0 0 1px var(--card-in) inset,0 0 40px -6px var(--glow-signal)}
.card::before{
  content:'';position:absolute;top:0;left:16px;right:16px;height:1px;
  background:linear-gradient(90deg,transparent,var(--signal),transparent);
  animation:sheen 4s ease-in-out infinite
}
@keyframes sheen{0%,100%{opacity:.15;transform:translateX(-40%)}50%{opacity:.9;transform:translateX(40%)}}
/* حاشیه‌ی نور چرخان جدید */
.card::after{
  content:'';position:absolute;inset:-1px;border-radius:20px;padding:1px;z-index:-1;pointer-events:none;
  background:conic-gradient(from var(--ang,0deg),transparent 0%,var(--signal) 8%,transparent 22%,transparent 100%);
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
  -webkit-mask-composite:xor;mask-composite:exclude;opacity:.5;animation:rotang 5.5s linear infinite
}
@keyframes rotang{to{--ang:360deg}}
@property --ang{syntax:'<angle>';inherits:false;initial-value:0deg}

.brand{display:flex;flex-direction:column;align-items:center;gap:12px;margin-bottom:24px;text-align:center}
.brand-img{width:64px;height:64px;border-radius:16px;overflow:hidden;border:1px solid var(--border);flex-shrink:0;position:relative;box-shadow:0 0 0 4px var(--card-in);animation:brandpulse 3.2s ease-in-out infinite}
@keyframes brandpulse{0%,100%{box-shadow:0 0 0 4px var(--card-in)}50%{box-shadow:0 0 0 6px var(--glow-signal)}}
.brand-img img{width:100%;height:100%;object-fit:cover;display:block}
.brand-name{font-size:15.5px;font-weight:800;color:var(--text);letter-spacing:-.01em}
.brand-sub{font-size:10.5px;color:var(--dim);margin-top:3px;letter-spacing:.02em}
.brand-sub .mono{color:var(--signal);font-weight:600}

h1{font-size:21px;font-weight:800;color:var(--text);margin-bottom:5px;letter-spacing:-.02em;animation:fadeup .5s cubic-bezier(.16,1,.3,1) .1s backwards}
.sub{font-size:12.5px;color:var(--mid);margin-bottom:24px;line-height:1.7;animation:fadeup .5s cubic-bezier(.16,1,.3,1) .18s backwards}
@keyframes fadeup{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}

.hint{
  display:flex;align-items:center;gap:10px;background:var(--card-in);border:1px dashed var(--border);
  border-radius:12px;padding:10px 14px;margin-bottom:22px;animation:fadeup .5s cubic-bezier(.16,1,.3,1) .24s backwards
}
.hint i{color:var(--dim);font-size:15px}
.hint-label{font-size:11px;color:var(--dim);flex:1}
.hint-val{
  font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;color:var(--signal);
  background:var(--glow-signal);border:1px solid rgba(250,204,21,0.35);padding:4px 11px;border-radius:7px;
  cursor:pointer;transition:.18s;letter-spacing:.06em
}
.hint-val:hover{filter:brightness(1.15);transform:translateY(-1px) scale(1.04)}
.hint-val:active{transform:translateY(0) scale(.96)}

.field{margin-bottom:18px;animation:fadeup .5s cubic-bezier(.16,1,.3,1) .3s backwards}
.field label{display:block;font-size:10.5px;font-weight:700;color:var(--mid);margin-bottom:8px;text-transform:uppercase;letter-spacing:.08em}
.inp-wrap{position:relative}
input[type=password],input[type=text]{
  width:100%;padding:13px 44px 13px 44px;border-radius:12px;border:1px solid var(--border);
  background:rgba(0,0,0,.18);color:var(--text);font-family:inherit;font-size:14.5px;outline:none;transition:.2s
}
[data-theme="light"] input[type=password],[data-theme="light"] input[type=text]{background:rgba(124,58,237,.04)}
input::placeholder{color:var(--dim)}
input:focus{border-color:var(--accent);background:rgba(139,92,246,.07);box-shadow:0 0 0 4px var(--glow)}
.ic-lock{position:absolute;right:15px;top:50%;transform:translateY(-50%);color:var(--dim);font-size:17px;pointer-events:none;transition:.2s}
input:focus~.ic-lock{color:var(--accent2);animation:wiggle .4s ease}
@keyframes wiggle{0%,100%{transform:translateY(-50%) rotate(0)}25%{transform:translateY(-50%) rotate(-12deg)}75%{transform:translateY(-50%) rotate(12deg)}}
.ic-eye{
  position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--dim);font-size:17px;
  cursor:pointer;padding:6px;transition:.2s;line-height:0
}
.ic-eye:hover{color:var(--accent2);transform:translateY(-50%) scale(1.15)}

.err{display:none;background:rgba(251,113,133,.08);border:1px solid rgba(251,113,133,.25);border-radius:11px;padding:11px 14px;margin-bottom:16px;font-size:12.5px;color:var(--danger);align-items:center;gap:8px;animation:shake .35s}
.err.show{display:flex}
@keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-6px)}75%{transform:translateX(6px)}}

.btn{
  width:100%;padding:13.5px;border-radius:999px;border:none;cursor:pointer;
  background:linear-gradient(135deg,#8B5CF6 0%,#A855F7 50%,#FACC15 100%);background-size:200% 200%;
  color:#fff;font-family:inherit;font-size:14.5px;font-weight:700;
  display:flex;align-items:center;justify-content:center;gap:9px;box-shadow:0 10px 26px -6px rgba(139,92,246,.5);
  transition:all .22s;position:relative;overflow:hidden;margin-top:6px;
  animation:btngrad 4s ease infinite,fadeup .5s cubic-bezier(.16,1,.3,1) .36s backwards
}
@keyframes btngrad{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
.btn::before{content:'';position:absolute;inset:0;background:linear-gradient(120deg,transparent,rgba(255,255,255,.25),transparent);width:50%;transform:translateX(-160%)}
.btn:hover::before{animation:btnsheen 1s ease}
@keyframes btnsheen{to{transform:translateX(260%)}}
.btn:hover{transform:translateY(-2px);box-shadow:0 14px 32px -6px rgba(168,85,247,.6)}
.btn:active{transform:translateY(0) scale(.98)}
.btn:disabled{opacity:.55;cursor:not-allowed;transform:none;animation:btngrad 4s ease infinite}
.btn:focus-visible,input:focus-visible,.theme-btn:focus-visible,.hint-val:focus-visible{outline:2px solid var(--signal);outline-offset:2px}

.footer{margin-top:22px;padding-top:18px;border-top:1px solid var(--border);display:flex;align-items:center;justify-content:center;gap:8px;font-size:11.5px;color:var(--dim);animation:fadeup .5s cubic-bezier(.16,1,.3,1) .42s backwards}
.footer a{color:var(--accent2);font-weight:700;text-decoration:none;display:flex;align-items:center;gap:5px;transition:.18s}
.footer a:hover{filter:brightness(1.25);transform:translateY(-1px)}

/* ══════ هشدار Caps Lock ══════ */
.caps-warn{display:none;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.3);border-radius:10px;padding:9px 13px;margin-bottom:14px;font-size:11.5px;color:#FCD34D;align-items:center;gap:8px}
.caps-warn.show{display:flex;animation:fadeup .25s ease}

/* ══════ بج‌های قابلیت — حس محصول حرفه‌ای ══════ */
.features{display:flex;gap:7px;justify-content:center;margin-top:20px;flex-wrap:wrap;animation:fadeup .5s cubic-bezier(.16,1,.3,1) .48s backwards}
.feat{display:inline-flex;align-items:center;gap:5px;font-size:9.5px;font-weight:600;color:var(--mid);background:var(--card-in);border:1px solid var(--border);border-radius:999px;padding:5px 11px;letter-spacing:.02em}
.feat i{font-size:12px;color:var(--accent2)}

@keyframes spin{to{transform:rotate(360deg)}}

@media (max-width:420px){
  .card{padding:30px 22px 24px;border-radius:18px}
  .status-badge span{display:none}
  .status-badge{padding:9px}
}
@media (prefers-reduced-motion:reduce){
  *{animation-duration:.001s !important;animation-iteration-count:1 !important}
}



</style>
</head>
<body>
<div class="bg"></div><div class="grid"></div>
<div class="particles" id="particles" aria-hidden="true"></div>
<div class="route" aria-hidden="true">
  <svg viewBox="0 0 1000 700" preserveAspectRatio="none">
    <path d="M -50 120 C 200 40, 350 220, 620 90 S 1050 40, 1100 130" />
    <path d="M -50 600 C 220 680, 420 480, 700 610 S 1000 700, 1080 560" />
    <circle class="pulse-dot" r="3" fill="var(--signal)">
      <animateMotion dur="7s" repeatCount="indefinite" path="M -50 120 C 200 40, 350 220, 620 90 S 1050 40, 1100 130" />
    </circle>
    <circle class="pulse-dot" r="2.4" fill="var(--accent2)">
      <animateMotion dur="9s" repeatCount="indefinite" path="M -50 600 C 220 680, 420 480, 700 610 S 1000 700, 1080 560" />
    </circle>
  </svg>
</div>

<div class="theme-switch">
  <button class="theme-btn" id="theme-btn" onclick="toggleTheme()" title="تغییر تم" aria-label="تغییر تم">
    <i class="ti ti-sun" id="theme-icon"></i>
  </button>
</div>
<div class="status-badge"><span class="status-dot"></span><span class="mono">GATEWAY ONLINE</span></div>

<div class="wrap" id="wrap">
  <div class="card" id="card">
    <div class="brand">
      <div class="brand-img"><svg viewBox="0 0 100 100" width="100%" height="100%" role="img" aria-label="EMIX logo"><rect width="100" height="100" fill="#030303"/><circle cx="50" cy="48" r="45" fill="#0B0B0B" stroke="#5A160E" stroke-width="2"/><circle cx="50" cy="48" r="42" fill="none" stroke="#FF3B24" stroke-width="1" opacity=".7"/><path d="M72 24H39C29 24 23 30 23 40V61C23 71 29 77 39 77H73M39 50H64C72 50 76 46 80 39" fill="none" stroke="#7A170F" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" opacity=".6"/><path d="M72 24H39C29 24 23 30 23 40V61C23 71 29 77 39 77H73M39 50H64C72 50 76 46 80 39" fill="none" stroke="#FF4028" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/><text x="50" y="91" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" font-weight="800" letter-spacing="3" fill="#FF3B24">EMIX</text></svg></div>
      <div><div class="brand-name">EMIX <span style="background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent">PRO</span></div><div class="brand-sub">Multi-Protocol Gateway <span class="mono" id="login-ver-chip">· v11</span></div></div>
    </div>
    <h1>ورود به مرکز مدیریت</h1>

    <div class="err" id="err" role="alert"><i class="ti ti-alert-circle"></i><span id="err-text"></span></div>

    <div class="caps-warn" id="caps-warn"><i class="ti ti-letter-case-upper"></i> کلید Caps Lock روشن است</div>

    <form id="form" novalidate>
      <div class="field">
        <label for="pw">رمز عبور</label>
        <div class="inp-wrap">
          <input type="password" id="pw" placeholder="رمز پیشفرض ۱۲۳۴۵۶ هستش" autofocus required autocomplete="current-password">
          <i class="ti ti-lock ic-lock"></i>
          <i class="ti ti-eye ic-eye" id="eye-toggle" onclick="togglePw()" role="button" tabindex="0" aria-label="نمایش رمز عبور"></i>
        </div>
      </div>
      <button class="btn" type="submit" id="btn"><i class="ti ti-shield-check"></i> ورود امن به داشبورد</button>
    </form>

    <div class="footer">کانال رسمی<a href="https://t.me/emixpi" target="_blank" rel="noopener"><i class="ti ti-brand-telegram"></i>@emixpi</a></div>
  </div>
</div>

<script>
/* ══════ تم روشن/تاریک ══════ */
let isDark = localStorage.getItem('rvg-login-theme') !== 'light';
function applyTheme(dark){
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  document.getElementById('theme-icon').className = 'ti ' + (dark ? 'ti-sun' : 'ti-moon');
}
function toggleTheme(){
  isDark = !isDark;
  localStorage.setItem('rvg-login-theme', isDark ? 'dark' : 'light');
  const btn = document.getElementById('theme-btn');
  btn.classList.add('spin');
  setTimeout(()=>btn.classList.remove('spin'), 420);
  applyTheme(isDark);
}
applyTheme(isDark);

function fillDefault(){
  const pw = document.getElementById('pw');
  pw.value = '123456';
  pw.focus();
}

function togglePw(){
  const pw = document.getElementById('pw');
  const eye = document.getElementById('eye-toggle');
  const show = pw.type === 'password';
  pw.type = show ? 'text' : 'password';
  eye.className = 'ti ' + (show ? 'ti-eye-off' : 'ti-eye') + ' ic-eye';
}

/* تشخیص Caps Lock — بازخورد حرفه‌ای */
document.getElementById('pw').addEventListener('keyup', e => {
  const on = e.getModifierState && e.getModifierState('CapsLock');
  document.getElementById('caps-warn').classList.toggle('show', !!on);
});
document.getElementById('pw').addEventListener('blur', () => {
  document.getElementById('caps-warn').classList.remove('show');
});

/* ذرات شناور پس‌زمینه */
(function(){
  const box = document.getElementById('particles');
  const n = 22;
  for(let i=0;i<n;i++){
    const p = document.createElement('div');
    p.className = 'particle';
    const size = 2 + Math.random()*3;
    p.style.width = size+'px';
    p.style.height = size+'px';
    p.style.left = Math.random()*100+'vw';
    p.style.setProperty('--drift', (Math.random()*80-40)+'px');
    p.style.animationDuration = (10 + Math.random()*14)+'s';
    p.style.animationDelay = (Math.random()*14)+'s';
    box.appendChild(p);
  }
})();

/* Audit fix: نسخه‌ی واقعی روی صفحه‌ی ورود (بدون احراز هویت) — قبلاً «v9.5» hardcoded بود */
(function(){
  fetch('/api/deployment-version',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(dv=>{
    const chip=document.getElementById('login-ver-chip');
    if(chip&&dv&&dv.version)chip.textContent='· v'+dv.version;
  }).catch(()=>{});
})();

/* افکت تیلت سه‌بعدی روی کارت با موس */
(function(){
  const wrap = document.getElementById('wrap');
  const card = document.getElementById('card');
  if(window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if(window.matchMedia('(hover: none)').matches) return;
  wrap.addEventListener('mousemove', (e)=>{
    const r = wrap.getBoundingClientRect();
    const x = (e.clientX - r.left)/r.width - .5;
    const y = (e.clientY - r.top)/r.height - .5;
    card.style.transform = `rotateY(${x*6}deg) rotateX(${-y*6}deg) translateZ(0)`;
  });
  wrap.addEventListener('mouseleave', ()=>{
    card.style.transform = 'rotateY(0) rotateX(0)';
  });
})();

document.getElementById('form').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = document.getElementById('btn'), err = document.getElementById('err'), et = document.getElementById('err-text');
  err.classList.remove('show'); btn.disabled = true;
  btn.innerHTML = '<i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال احراز هویت...';
  try{
    const r = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({password: document.getElementById('pw').value})});
    if(!r.ok){ const d = await r.json().catch(()=>({})); throw new Error(d.detail || 'خطا در ورود'); }
    btn.innerHTML = '<i class="ti ti-circle-check"></i> خوش آمدید';
    location.href = '/dashboard';
  }catch(e){
    et.textContent = e.message;
    err.classList.add('show');
    btn.disabled = false;
    btn.innerHTML = '<i class="ti ti-shield-check"></i> ورود امن به داشبورد';
  }
});
</script>
</body></html>"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EMIX PRO</title>
<link rel="preload" href="/assets/fonts.css" as="style" onerror="this.remove()">
<link rel="stylesheet" href="/assets/fonts.css" onerror="this.remove()">
<link rel="stylesheet" href="/assets/tabler-icons.min.css" onerror="this.href='https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.19.0/dist/tabler-icons.min.css'">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800&display=swap" media="print" onload="this.media='all'">
<script src="/assets/chart.umd.js" onerror="this.remove();var s=document.createElement('script');s.src='https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js';document.head.appendChild(s)"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  /* ═══════════════════════════════════════════════════════════════════════════
     EMIX PRO v9.9 — NixHD-inspired Design System
     پالت: مشکی عمیق + بنفش + زرد + glassmorphism
     مرجع: داشبورد NixHD — violet #8B5CF6 / yellow #FACC15 / deep black #0A0A0F
     ═══════════════════════════════════════════════════════════════════════════ */
  --bg:#0A0A0F;          /* پس‌زمینه‌ی اصلی — مشکی عمیق */
  --bg2:#14141C;        /* سایدبار/هدر تیره‌تر */
  --bg3:#1E1E28;        /* کارت‌های بالا‌تر */
  /* شیشه‌ی مات — layering تا حدی شفاف برای depth */
  --card:rgba(20,20,28,0.55);
  --card-b:rgba(139,92,246,0.16);
  --card-bh:rgba(139,92,246,0.32);
  --card-solid:#14141C;          /* کارت‌های سفید-مات */
  --card-elevated:#1E1E28;        /* هدر/تاپ‌بار */
  --glass-blur:18px;
  --glass-shadow:0 8px 32px 0 rgba(0,0,0,0.45);
  --glass-shadow-lg:0 20px 50px rgba(0,0,0,0.55);
  /* اکسنت بنفش — رنگ برند NixHD */
  --accent:#8B5CF6;
  --accent2:#FACC15;
  --accent-d:rgba(139,92,246,0.12);
  --accent-glow:rgba(139,92,246,0.32);
  --accent-violet:#A855F7;          /* درخشان‌تر برای فعال‌ها */
  /* گرادینت ویژه: violet → yellow (کارتی برای امتیاز/متریک‌های برجسته) */
  --grad-vy:linear-gradient(135deg,#A855F7 0%,#FACC15 100%);
  /* رنگ‌های وضعیت */
  --green:#22C55E;--green-bg:rgba(34,197,94,0.12);--green-t:#4ADE80;
  --red:#EF4444;--red-bg:rgba(239,68,68,0.12);--red-t:#F87171;
  --amber:#FACC15;--amber-bg:rgba(250,204,21,0.12);--amber-t:#FDE047;
  --purple:#8B5CF6;--purple-bg:rgba(139,92,246,0.16);--purple-t:#A78BFA;
  --blue:#60A5FA;--blue-bg:rgba(96,165,250,0.12);
  /* متن */
  --t1:#FFFFFF;       /* اصلی — سفید */
  --t2:#9CA3AF;       /* ثانویه — خاکستری */
  --t3:#6B7280;       /* کم‌رنگ */
  /* متریک‌ها */
  --sidebar-w:260px;--radius:16px;
  --radius-sm:10px;--radius-lg:24px;--radius-xl:32px;
  --shadow:0 8px 24px rgba(0,0,0,0.45);
  --shadow-sm:0 2px 8px rgba(0,0,0,0.30);
  --shadow-glow:0 0 24px var(--accent-glow);
  /* dot-matrix indicator (سال‌ها سالم/قطع) */
  --dot-on:var(--accent-violet);
  --dot-off:rgba(139,92,246,0.18);
}
[data-theme="light"]{
  --bg:#F5F5F7;--bg2:#FFFFFF;--bg3:#E8EAF0;
  --card:rgba(255,255,255,0.80);
  --card-b:rgba(124,58,237,0.12);
  --card-bh:rgba(124,58,237,0.26);
  --card-solid:#FFFFFF;--card-elevated:#F5F5F7;
  --accent:#7C3AED;--accent2:#CA8A04;--accent-d:rgba(124,58,237,0.10);
  --accent-glow:rgba(124,58,237,0.22);--accent-violet:#8B5CF6;
  --green:#16A34A;--green-bg:rgba(22,163,74,0.10);--green-t:#15803D;
  --red:#DC2626;--red-bg:rgba(220,38,38,0.10);--red-t:#B91C1C;
  --amber:#CA8A04;--amber-bg:rgba(202,138,4,0.10);--amber-t:#A16207;
  --purple:#7C3AED;--purple-bg:rgba(124,58,237,0.10);--purple-t:#6D28D9;
  --blue:#2563EB;--blue-bg:rgba(37,99,235,0.10);
  --t1:#0A0A0F;--t2:#4B5563;--t3:#9CA3AF;
  --shadow:0 4px 20px rgba(0,0,0,0.08);
  --shadow-sm:0 1px 4px rgba(0,0,0,0.04);
}
html,body{height:100%}
body{font-family:'Vazirmatn','Inter',sans-serif;background:var(--bg);color:var(--t1);min-height:100vh;display:flex;font-size:14px;transition:background .3s,color .3s;position:relative;overflow-x:hidden}
/* نویز و افکت جلوه‌ی شیشه‌ای روی پس‌زمینه */
body::before{content:'';position:fixed;inset:0;z-index:-1;background:
  radial-gradient(circle at 20% 30%,rgba(245,158,11,0.10) 0%,transparent 50%),
  radial-gradient(circle at 80% 70%,rgba(96,165,250,0.08) 0%,transparent 50%),
  radial-gradient(circle at 50% 100%,rgba(167,139,250,0.05) 0%,transparent 60%);
  pointer-events:none;
}
[data-theme="light"] body::before{opacity:.5}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--card-b);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--accent)}
a{color:inherit;text-decoration:none}
/* سایدبار — شیشه‌ای تیره با border ظریف */
.sidebar{width:var(--sidebar-w);min-height:100vh;background:rgba(10,10,15,0.85);backdrop-filter:blur(var(--glass-blur)) saturate(140%);-webkit-backdrop-filter:blur(var(--glass-blur)) saturate(140%);border-left:1px solid var(--card-b);display:flex;flex-direction:column;flex-shrink:0;position:fixed;right:0;top:0;bottom:0;z-index:200;transition:transform .25s cubic-bezier(.4,0,.2,1),background .3s,border-color .3s;box-shadow:-4px 0 24px rgba(0,0,0,0.20)}
[data-theme="light"] .sidebar{background:rgba(255,255,255,0.80)}
.logo{display:flex;align-items:center;gap:12px;padding:22px 18px 18px;border-bottom:1px solid var(--card-b);position:relative}
.logo::after{content:'';position:absolute;bottom:-1px;right:18px;width:36px;height:2px;background:var(--accent);border-radius:2px;box-shadow:0 0 12px var(--accent-glow)}
.logo-img{width:42px;height:42px;border-radius:12px;overflow:hidden;border:1px solid var(--card-b);box-shadow:0 0 18px var(--accent-glow),inset 0 1px 0 rgba(255,255,255,0.10);flex-shrink:0;background:linear-gradient(135deg,#0A0A0F 0%,#1E1E28 50%,#2D1B4E 100%)}
.logo-img img{width:100%;height:100%;object-fit:cover}
.logo-name{font-size:15px;font-weight:800;color:var(--t1);letter-spacing:-.01em}
.logo-sub{font-size:10px;color:var(--accent);margin-top:2px;font-weight:600;letter-spacing:.05em}
.sb-close{display:none;position:absolute;left:12px;top:22px;background:var(--accent-d);border:1px solid var(--card-b);color:var(--t2);width:30px;height:30px;border-radius:8px;font-size:16px;align-items:center;justify-content:center;cursor:pointer}
.nav-wrap{flex:1;overflow-y:auto;padding:10px 0 12px}
.nav-sec{padding:16px 18px 6px;font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--t3);font-weight:700}
.nav-it{display:flex;align-items:center;gap:10px;padding:10px 14px;color:var(--t2);font-size:13px;cursor:pointer;border-right:2px solid transparent;transition:all .18s ease;margin:2px 8px;border-radius:10px;position:relative}
.nav-it i{font-size:17px;width:20px;text-align:center;flex-shrink:0;color:var(--t3);transition:color .18s}
.nav-it:hover{background:var(--accent-d);color:var(--t1)}
.nav-it:hover i{color:var(--accent)}
.nav-it.on{background:linear-gradient(90deg,var(--accent-d) 0%,transparent 100%);color:var(--t1);border-right-color:var(--accent);font-weight:600;box-shadow:inset 0 1px 0 rgba(255,255,255,0.04)}
.nav-it.on i{color:var(--accent);text-shadow:0 0 8px var(--accent-glow)}
.nav-badge{margin-right:auto;background:var(--accent-d);color:var(--accent);font-size:9px;padding:2px 7px;border-radius:20px;font-weight:700;border:1px solid var(--card-b)}
.sb-foot{padding:14px 16px;border-top:1px solid var(--card-b);display:flex;flex-direction:column;gap:8px}
.tg-btn{display:flex;align-items:center;justify-content:center;gap:8px;background:linear-gradient(135deg,#2daee6,#1976d2);color:#fff;border-radius:10px;padding:11px;font-size:12.5px;font-weight:700;font-family:inherit;border:none;cursor:pointer;width:100%;transition:.18s;box-shadow:0 4px 14px rgba(25,118,210,0.30)}
.tg-btn:hover{filter:brightness(1.12);transform:translateY(-1px)}
.theme-btn{display:flex;align-items:center;justify-content:center;gap:7px;background:var(--accent-d);color:var(--t2);border-radius:10px;padding:9px;font-size:12px;font-weight:600;font-family:inherit;border:1px solid var(--card-b);cursor:pointer;width:100%;transition:.18s}
.theme-btn:hover{background:var(--card-b);color:var(--t1)}
.logout-btn{display:flex;align-items:center;justify-content:center;gap:7px;background:var(--red-bg);color:var(--red-t);border-radius:10px;padding:9px;font-size:12px;font-weight:600;font-family:inherit;border:1px solid rgba(239,68,68,0.20);cursor:pointer;width:100%;transition:.18s}
.logout-btn:hover{background:rgba(239,68,68,0.18);transform:translateY(-1px)}
.mob-top{display:none;position:fixed;top:0;right:0;left:0;height:56px;background:rgba(10,10,15,0.85);backdrop-filter:blur(var(--glass-blur));-webkit-backdrop-filter:blur(var(--glass-blur));border-bottom:1px solid var(--card-b);z-index:150;align-items:center;justify-content:space-between;padding:0 16px;transition:background .3s}
[data-theme="light"] .mob-top{background:rgba(255,255,255,0.80)}
.mob-top .ml{display:flex;align-items:center;gap:9px}
.mob-logo{width:30px;height:30px;border-radius:8px;overflow:hidden;border:1px solid var(--card-b)}
.mob-logo img{width:100%;height:100%;object-fit:cover}
.mob-title{color:var(--t1);font-size:14px;font-weight:800}
.mob-right{display:flex;gap:6px}
.menu-btn,.theme-mob{background:var(--accent-d);border:1px solid var(--card-b);color:var(--t2);width:36px;height:36px;border-radius:9px;font-size:18px;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:.18s}
.menu-btn:hover,.theme-mob:hover{color:var(--accent);border-color:var(--accent)}
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:190;backdrop-filter:blur(4px)}
.overlay.show{display:block;animation:fi .2s}
.main{margin-right:var(--sidebar-w);flex:1;padding:30px 32px 80px;min-width:0;transition:margin .25s;position:relative}
.pg{display:none}
.pg.on{display:block;animation:fi .25s ease}
@keyframes fi{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.topbar{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:26px;flex-wrap:wrap;gap:14px}
.tb-title{font-size:22px;font-weight:800;color:var(--t1);display:flex;align-items:center;gap:10px;letter-spacing:-.02em}
.tb-title i{color:var(--accent);font-size:22px;text-shadow:0 0 12px var(--accent-glow)}
.tb-sub{font-size:11.5px;color:var(--t3);margin-top:5px}
.tb-right{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.badge{font-size:10px;padding:3px 10px;border-radius:20px;font-weight:700;display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
.bg-green{background:var(--green-bg);color:var(--green-t);border:1px solid rgba(16,185,129,0.18)}
.bg-blue{background:var(--blue-bg);color:#7dd3fc;border:1px solid rgba(96,165,250,0.18)}
.bg-amber{background:var(--amber-bg);color:var(--amber-t);border:1px solid rgba(245,158,11,0.18)}
.bg-red{background:var(--red-bg);color:var(--red-t);border:1px solid rgba(239,68,68,0.18)}
.bg-purple{background:var(--purple-bg);color:#c4b5fd;border:1px solid rgba(167,139,250,0.18)}
.dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;display:inline-block}
.dg{background:var(--green)}.dr{background:var(--red)}.da{background:var(--amber)}.db{background:var(--accent)}
.pulse{animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin-bottom:18px}
.metric{background:var(--card);border:1px solid var(--card-b);border-radius:var(--radius);padding:18px 18px 15px;transition:all .25s;position:relative;overflow:hidden;cursor:default;backdrop-filter:blur(var(--glass-blur));-webkit-backdrop-filter:blur(var(--glass-blur));box-shadow:var(--shadow-sm)}
.metric::after{content:'';position:absolute;top:0;right:0;width:3px;height:100%;background:var(--accent);opacity:0;transition:.25s}
.metric:hover{border-color:var(--card-bh);transform:translateY(-2px);box-shadow:var(--shadow),0 0 24px var(--accent-d)}
.metric:hover::after{opacity:1}
.metric.suc::after{background:var(--green)}
.metric.dan::after{background:var(--red)}
/* ══════ صفحه ترافیک - ریدیزاین ══════ */
.traf-hero{display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr;gap:13px;margin-bottom:18px}
.traf-main-stat{background:linear-gradient(155deg,var(--bg3) 0%,var(--card) 60%);border:1px solid var(--card-b);border-radius:20px;padding:22px 24px;position:relative;overflow:hidden}
.traf-main-stat::before{content:'';position:absolute;top:-50px;left:-50px;width:200px;height:200px;background:radial-gradient(circle,var(--accent-d),transparent 70%);pointer-events:none}
.traf-main-label{font-size:10.5px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.08em;display:flex;align-items:center;gap:6px;margin-bottom:10px;position:relative;z-index:1}
.traf-main-val{font-size:34px;font-weight:800;color:var(--t1);line-height:1;letter-spacing:-.02em;display:flex;align-items:baseline;gap:6px;position:relative;z-index:1}
.traf-main-val span{font-size:14px;font-weight:500;color:var(--t3)}
.traf-trend{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:700;padding:4px 10px;border-radius:20px;margin-top:12px;position:relative;z-index:1}
.traf-trend.up{background:var(--green-bg);color:var(--green-t)}
.traf-trend.down{background:var(--red-bg);color:var(--red-t)}
.traf-mini{background:var(--card);border:1px solid var(--card-b);border-radius:20px;padding:18px 19px;display:flex;flex-direction:column;justify-content:space-between;transition:.2s}
.traf-mini:hover{border-color:var(--card-bh);transform:translateY(-2px)}
.traf-mini-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.traf-mini-icon{width:32px;height:32px;border-radius:9px;background:var(--accent-d);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:15px}
.traf-mini-icon.pk{background:var(--amber-bg);color:var(--amber)}
.traf-mini-icon.lo{background:var(--purple-bg);color:var(--purple)}
.traf-mini-label{font-size:9.5px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.traf-mini-val{font-size:21px;font-weight:800;color:var(--t1);letter-spacing:-.01em}
.traf-mini-sub{font-size:9.5px;color:var(--t3);margin-top:3px}

.traf-chart-card{background:var(--card);border:1px solid var(--card-b);border-radius:22px;padding:22px 24px 18px;box-shadow:var(--shadow);margin-bottom:16px}
.traf-chart-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;flex-wrap:wrap;gap:10px}
.traf-chart-title{font-size:14px;font-weight:800;color:var(--t1);display:flex;align-items:center;gap:8px}
.traf-chart-title i{color:var(--accent);font-size:18px}
.traf-chart-sub{font-size:10.5px;color:var(--t3);margin-top:3px}
.traf-legend{display:flex;gap:14px;align-items:center}
.traf-legend-item{display:flex;align-items:center;gap:6px;font-size:10.5px;color:var(--t2);font-weight:600}
.traf-legend-dot{width:8px;height:8px;border-radius:3px}
.traf-range-tabs{display:flex;gap:4px;background:var(--accent-d);padding:3px;border-radius:10px;border:1px solid var(--card-b)}
.traf-range-tab{padding:6px 13px;border-radius:8px;font-size:10.5px;font-weight:700;color:var(--t3);cursor:pointer;transition:.15s;border:none;background:transparent;font-family:inherit}
.traf-range-tab.on{background:var(--accent);color:#fff;box-shadow:0 2px 8px rgba(139,92,246,.35)}
.traf-chart-body{height:320px;margin-top:14px;position:relative}

/* ══════ ALPN & Fingerprint — کارت‌های جدید ══════ */
.fp-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px}
.fp-card{border:1.5px solid var(--card-b);border-radius:12px;padding:11px 8px;cursor:pointer;
  transition:.18s;text-align:center;background:rgba(0,0,0,.1);position:relative}
[data-theme="light"] .fp-card{background:#fff}
.fp-card:hover{border-color:var(--card-bh);transform:translateY(-1px)}
.fp-card.active{border-color:var(--accent);background:var(--accent-d);box-shadow:0 0 0 3px rgba(139,92,246,.1)}
.fp-card-icon{width:28px;height:28px;border-radius:8px;background:var(--accent-d);color:var(--accent);
  display:flex;align-items:center;justify-content:center;font-size:14px;margin:0 auto 6px}
.fp-card.active .fp-card-icon{background:var(--accent);color:#fff}
.fp-card-title{font-size:10.5px;font-weight:800;color:var(--t1)}
.fp-card-check{position:absolute;top:5px;left:5px;width:14px;height:14px;border-radius:50%;
  background:var(--accent);color:#fff;font-size:8px;display:flex;align-items:center;justify-content:center;
  opacity:0;transform:scale(.4);transition:.15s}
.fp-card.active .fp-card-check{opacity:1;transform:scale(1)}

.alpn-row{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}
.alpn-chip{display:flex;align-items:center;gap:6px;padding:7px 13px;border-radius:10px;
  border:1.5px solid var(--card-b);background:rgba(0,0,0,.1);cursor:pointer;transition:.15s;
  font-size:11px;font-weight:700;color:var(--t2)}
[data-theme="light"] .alpn-chip{background:#fff}
.alpn-chip:hover{border-color:var(--card-bh)}
.alpn-chip.active{border-color:var(--accent);background:var(--accent-d);color:var(--accent2)}
.alpn-chip-dot{width:14px;height:14px;border-radius:4px;border:1.5px solid var(--card-b);
  display:flex;align-items:center;justify-content:center;transition:.15s;flex-shrink:0}
.alpn-chip.active .alpn-chip-dot{background:var(--accent);border-color:var(--accent)}
.alpn-chip-dot i{font-size:9px;color:#fff;opacity:0;transform:scale(.5);transition:.15s}
.alpn-chip.active .alpn-chip-dot i{opacity:1;transform:scale(1)}

.stream-sub-label{font-size:10px;font-weight:800;color:var(--t3);text-transform:uppercase;
  letter-spacing:.06em;display:flex;align-items:center;gap:6px;margin-top:16px;margin-bottom:2px}
.stream-sub-label i{color:var(--accent);font-size:13px}

@media(max-width:900px){.traf-hero{grid-template-columns:1fr 1fr}}
@media(max-width:520px){.traf-hero{grid-template-columns:1fr}.traf-chart-body{height:260px}}
.m-icon{width:34px;height:34px;border-radius:8px;background:var(--accent-d);display:flex;align-items:center;justify-content:center;margin-bottom:11px;color:var(--accent);font-size:17px}
.m-icon.suc{background:var(--green-bg);color:var(--green)}
.m-icon.dan{background:var(--red-bg);color:var(--red)}
.m-icon.pur{background:var(--purple-bg);color:var(--purple)}
.m-label{font-size:10px;color:var(--t3);margin-bottom:4px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}
.m-val{font-size:25px;font-weight:700;color:var(--t1);line-height:1;letter-spacing:-.02em}
.m-unit{font-size:12px;font-weight:400;color:var(--t3)}
.m-sub{font-size:10px;color:var(--t3);margin-top:6px;display:flex;align-items:center;gap:3px}
.vless-box{background:linear-gradient(135deg,var(--bg3) 0%,var(--bg2) 100%);border:1px solid var(--card-b);border-radius:18px;padding:20px 22px;margin-bottom:18px;box-shadow:var(--shadow);position:relative;overflow:hidden;transition:background .3s}
.vless-box::before{content:'';position:absolute;top:-50px;left:-50px;width:180px;height:180px;background:radial-gradient(circle,var(--accent-d),transparent 70%);pointer-events:none}
.vl-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:13px;flex-wrap:wrap;gap:8px}
.vl-title{color:var(--t2);font-size:11px;display:flex;align-items:center;gap:6px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.vl-title i{color:var(--accent);font-size:15px}
.vl-code{background:rgba(0,0,0,.18);border:1px solid var(--card-b);border-radius:9px;padding:13px 15px;font-size:11px;font-family:ui-monospace,monospace;color:var(--accent2);word-break:break-all;line-height:1.8;letter-spacing:.01em}
[data-theme="light"] .vl-code{background:rgba(0,0,0,.04)}
.vl-actions{display:flex;gap:8px;margin-top:13px;flex-wrap:wrap}
.btn{font-family:inherit;font-size:12.5px;font-weight:600;border-radius:10px;padding:9px 14px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;border:none;transition:all .18s;white-space:nowrap;position:relative;overflow:hidden}
.btn i{font-size:13px}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-p{background:linear-gradient(135deg,var(--accent) 0%,var(--accent2) 100%);color:#14141C;box-shadow:0 4px 14px var(--accent-glow)}
.btn-p:hover{filter:brightness(1.08);box-shadow:0 6px 18px var(--accent-glow)}
.btn-o{background:transparent;border:1px solid var(--card-b);color:var(--t2)}
.btn-o:hover{background:var(--accent-d);border-color:var(--accent);color:var(--t1)}
.btn-g{background:linear-gradient(135deg,var(--accent) 0%,var(--accent2) 100%);color:#14141C;border:1px solid var(--accent);box-shadow:0 4px 14px var(--accent-glow)}
.btn-g:hover{filter:brightness(1.08);box-shadow:0 6px 18px var(--accent-glow)}
.btn-d{background:var(--red-bg);color:var(--red-t);border:1px solid rgba(239,68,68,.20)}
.btn-d:hover{background:rgba(239,68,68,.18)}
.btn-pur{background:var(--purple-bg);color:#c4b5fd;border:1px solid rgba(167,139,250,.20)}
.btn-pur:hover{background:rgba(167,139,250,.18)}
.btn-amber{background:var(--amber-bg);color:var(--amber-t);border:1px solid rgba(245,158,11,.20)}
.btn-amber:hover{background:rgba(245,158,11,.18)}
.btn-sm{padding:6px 10px;font-size:10.5px;border-radius:8px}
.btn-icon{width:30px;height:30px;padding:0;justify-content:center;border-radius:6px}
.card{background:var(--card);border:1px solid var(--card-b);border-radius:var(--radius);padding:18px 20px;transition:border-color .25s,background .3s,transform .25s,box-shadow .25s;backdrop-filter:blur(var(--glass-blur));-webkit-backdrop-filter:blur(var(--glass-blur));box-shadow:var(--shadow-sm)}
.card:hover{border-color:var(--card-bh)}
/* ─── ورودی‌های شیشه‌ای یکپارچه — همه‌ی input/select/textarea همین استایل را می‌گیرند ─── */
input[type=text],input[type=password],input[type=number],input[type=email],input[type=url],
input[type=tel],input[type=search],input:not([type]),select,textarea{
  width:100%;padding:10px 14px;border-radius:10px;border:1px solid var(--card-b);
  background:rgba(0,0,0,.15);color:var(--t1);font-family:inherit;font-size:12.5px;outline:none;transition:.18s;
  backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
}
[data-theme="light"] input[type=text],[data-theme="light"] input[type=password],[data-theme="light"] input[type=number],
[data-theme="light"] select,[data-theme="light"] textarea{background:rgba(255,255,255,0.80)}
input::placeholder,textarea::placeholder{color:var(--t3)}
input:focus,select:focus,textarea:focus{border-color:var(--accent);background:rgba(0,0,0,.25);box-shadow:0 0 0 3px var(--accent-d)}
[data-theme="light"] input:focus,[data-theme="light"] select:focus,[data-theme="light"] textarea:focus{background:#fff}
select{appearance:none;-webkit-appearance:none;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>");background-repeat:no-repeat;background-position:left 12px center;padding-left:32px;cursor:pointer}
[data-theme="light"] select{background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23475569' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>")}
select option{background:#0A0A0F;color:var(--t1)}
[data-theme="light"] select option{background:#fff;color:#14141C}
.card-title{font-size:12.5px;font-weight:700;color:var(--t1);margin-bottom:15px;display:flex;align-items:center;gap:7px}
.card-title i{font-size:16px;color:var(--accent)}
.ml-auto{margin-right:auto}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin-bottom:16px}
.g3{display:grid;grid-template-columns:2fr 1fr;gap:13px;margin-bottom:16px}
.mb16{margin-bottom:16px}
.sr{display:flex;align-items:center;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(139,92,246,0.05);font-size:12px}
.sr:last-child{border-bottom:none}
.sr-k{color:var(--t2);display:flex;align-items:center;gap:6px}
.sr-k i{font-size:13px;color:var(--t3)}
.sr-v{color:var(--t1);font-weight:600;font-size:11.5px}
.ch{position:relative;height:230px}
.ch-lg{position:relative;height:330px}
.ch-sm{position:relative;height:185px}
.exp-chip{font-size:9px;padding:3px 8px;border-radius:6px;font-weight:700;display:inline-flex;align-items:center;gap:3px}
.ec-ok{background:var(--green-bg);color:var(--green-t)}
.ec-warn{background:var(--amber-bg);color:var(--amber-t)}
.ec-exp{background:var(--red-bg);color:var(--red-t)}
.ec-inf{background:var(--accent-d);color:var(--accent2)}
.tog{width:19px;height:34px;border-radius:19px;background:rgba(100,116,139,0.25);position:relative;cursor:pointer;transition:.2s;flex-shrink:0;border:none}
.tog::after{content:'';position:absolute;width:13px;height:13px;border-radius:50%;background:#fff;left:3px;bottom:3px;transition:.2s;box-shadow:0 1px 3px rgba(0,0,0,.3)}
.tog.on{background:var(--green)}
.tog.on::after{bottom:18px}
.form-row{display:flex;gap:9px;flex-wrap:wrap;align-items:flex-end}
.fg{display:flex;flex-direction:column;gap:5px}
.fg label{font-size:10px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.fi,.fs{padding:9px 12px;border-radius:9px;border:1px solid var(--card-b);background:rgba(0,0,0,.18);color:var(--t1);font-family:inherit;font-size:12px;outline:none;transition:.15s;min-width:100px}
[data-theme="light"] .fi,[data-theme="light"] .fs{background:rgba(0,0,0,.04)}
.fi::placeholder{color:var(--t3)}
.fi:focus,.fs:focus{border-color:rgba(139,92,246,.45);background:rgba(0,0,0,.25);box-shadow:0 0 0 3px rgba(139,92,246,.08)}
.fs option{background:var(--bg2)}
[data-theme="light"] .fs option{background:#fff}
.cl{background:var(--accent-d);border:1px solid rgba(139,92,246,.15);border-radius:10px;padding:11px 13px;font-size:11px;color:var(--t2);display:flex;gap:9px;align-items:flex-start;line-height:1.8;margin-top:12px}
.cl i{font-size:15px;color:var(--accent);margin-top:1px;flex-shrink:0}
.cl.amber{background:var(--amber-bg);border-color:rgba(245,158,11,.2);color:var(--amber-t)}
/* ══════ پنل ساخت کانفیگ - طراحی جدید ══════ */
.create-panel{background:linear-gradient(155deg,var(--bg3) 0%,var(--card) 55%);border:1px solid var(--card-b);border-radius:22px;padding:0;overflow:hidden;box-shadow:var(--shadow);margin-bottom:16px;position:relative}
.create-panel::before{content:'';position:absolute;top:-60px;left:-60px;width:220px;height:220px;background:radial-gradient(circle,var(--accent-d),transparent 70%);pointer-events:none}
.cp-head{display:flex;align-items:center;gap:13px;padding:22px 24px 18px;position:relative;z-index:1}
.cp-head-icon{width:44px;height:44px;border-radius:13px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;color:#fff;font-size:20px;flex-shrink:0;box-shadow:0 6px 18px rgba(139,92,246,.35)}
.cp-head-text{flex:1;min-width:0}
.cp-head-title{font-size:15px;font-weight:800;color:var(--t1);letter-spacing:-.01em}
.cp-head-sub{font-size:11px;color:var(--t3);margin-top:2px}
.cp-body{padding:2px 24px 22px;position:relative;z-index:1}
.cp-row{display:grid;grid-template-columns:1.3fr 1fr;gap:14px;margin-bottom:16px}
.cp-block{background:rgba(0,0,0,.14);border:1px solid var(--card-b);border-radius:14px;padding:14px 16px}
[data-theme="light"] .cp-block{background:rgba(124,58,237,.03)}
.cp-block-label{font-size:10px;font-weight:800;color:var(--t2);text-transform:uppercase;letter-spacing:.08em;display:flex;align-items:center;gap:6px;margin-bottom:11px}
.cp-block-label i{color:var(--accent);font-size:14px}
.cp-input-full{width:100%;padding:10px 13px;border-radius:10px;border:1px solid var(--card-b);background:rgba(0,0,0,.18);color:var(--t1);font-family:inherit;font-size:12.5px;outline:none;transition:.15s}
[data-theme="light"] .cp-input-full{background:#fff}
.cp-input-full:focus{border-color:rgba(139,92,246,.5);box-shadow:0 0 0 3px rgba(139,92,246,.1)}
.cp-input-full::placeholder{color:var(--t3)}
.cp-mini-row{display:flex;gap:8px;margin-top:9px}
.cp-quota-inputs{display:flex;gap:8px}
.cp-quota-inputs .cp-input-full{flex:1}
.cp-quota-inputs select.cp-input-full{flex:0 0 76px}
.chip-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
.chip{font-size:10.5px;font-weight:700;padding:5px 12px;border-radius:8px;background:var(--accent-d);color:var(--t2);border:1px solid var(--card-b);cursor:pointer;transition:.15s;white-space:nowrap}
.chip:hover{background:rgba(139,92,246,.18);color:var(--accent2)}
.chip.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 3px 10px rgba(139,92,246,.35)}
.proto-tabs{display:flex;gap:8px;flex-wrap:wrap}
.proto-step-label{font-size:10px;font-weight:800;color:var(--t2);text-transform:uppercase;letter-spacing:.06em;display:flex;align-items:center;gap:6px;margin-bottom:9px}
.proto-step-label i{color:var(--accent);font-size:14px}

.proto-base-cards{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.proto-base-card{border:1.5px solid var(--card-b);border-radius:13px;padding:14px 12px;cursor:pointer;transition:.18s;text-align:center;position:relative;background:rgba(0,0,0,.1)}
[data-theme="light"] .proto-base-card{background:#fff}
.proto-base-card:hover{border-color:var(--card-bh);transform:translateY(-1px)}
.proto-base-card.active{border-color:var(--accent);background:var(--accent-d);box-shadow:0 0 0 3px rgba(139,92,246,.1)}
.proto-base-icon{width:34px;height:34px;border-radius:9px;background:var(--accent-d);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:17px;margin:0 auto 8px}
.proto-base-card.active .proto-base-icon{background:var(--accent);color:#fff}
.proto-base-title{font-size:12px;font-weight:800;color:var(--t1)}
.proto-base-desc{font-size:9.5px;color:var(--t3);margin-top:3px}

.proto-transport-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
.proto-t-card{border:1.5px solid var(--card-b);border-radius:13px;padding:13px 10px;cursor:pointer;transition:.18s;text-align:center;position:relative;background:rgba(0,0,0,.1)}
[data-theme="light"] .proto-t-card{background:#fff}
.proto-t-card:hover{border-color:var(--card-bh);transform:translateY(-1px)}
.proto-t-card.active{border-color:var(--accent);background:var(--accent-d);box-shadow:0 0 0 3px rgba(139,92,246,.1)}
.proto-t-icon{width:30px;height:30px;border-radius:9px;background:var(--accent-d);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:15px;margin:0 auto 7px}
.proto-t-card.active .proto-t-icon{background:var(--accent);color:#fff}
.proto-t-title{font-size:10.5px;font-weight:800;color:var(--t1)}
.proto-t-desc{font-size:9px;color:var(--t3);margin-top:3px;line-height:1.4}

@media(max-width:760px){
  .proto-transport-cards{grid-template-columns:1fr}
}
.proto-tab{flex:1;min-width:120px;display:flex;align-items:center;justify-content:center;gap:7px;
  padding:11px 10px;border-radius:12px;border:1.5px solid var(--card-b);background:rgba(0,0,0,.1);
  color:var(--t2);font-family:inherit;font-size:11.5px;font-weight:700;cursor:pointer;transition:.15s}
.proto-tab.active{border-color:var(--accent);background:var(--accent-d);color:var(--accent2);
  box-shadow:0 0 0 3px rgba(139,92,246,.1)}
.proto-submodes{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.proto-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
.proto-card{border:1.5px solid var(--card-b);border-radius:13px;padding:13px 12px;cursor:pointer;transition:.18s;text-align:center;position:relative;background:rgba(0,0,0,.1)}
[data-theme="light"] .proto-card{background:#fff}
.proto-card:hover{border-color:var(--card-bh);transform:translateY(-1px)}
.proto-card.active{border-color:var(--accent);background:var(--accent-d);box-shadow:0 0 0 3px rgba(139,92,246,.1)}
.proto-card.active .proto-card-check{opacity:1;transform:scale(1)}
.proto-card-check{position:absolute;top:7px;left:7px;width:16px;height:16px;border-radius:50%;background:var(--accent);color:#fff;font-size:10px;display:flex;align-items:center;justify-content:center;opacity:0;transform:scale(.5);transition:.18s}
.proto-card-icon{width:32px;height:32px;border-radius:9px;background:var(--accent-d);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:16px;margin:0 auto 8px}
.proto-card.active .proto-card-icon{background:var(--accent);color:#fff}
.proto-card-title{font-size:11px;font-weight:800;color:var(--t1)}
.proto-card-desc{font-size:9px;color:var(--t3);margin-top:3px;line-height:1.5}
.cp-footer{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-top:16px;border-top:1px solid var(--card-b);flex-wrap:wrap}
.cp-footer-note{display:flex;align-items:center;gap:8px;font-size:10.5px;color:var(--t3);line-height:1.7;flex:1;min-width:220px}
.cp-footer-note i{color:var(--accent);font-size:15px;flex-shrink:0}
.cp-submit-btn{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;border:none;border-radius:13px;padding:13px 26px;font-family:inherit;font-size:13px;font-weight:800;cursor:pointer;display:flex;align-items:center;gap:8px;box-shadow:0 6px 20px rgba(139,92,246,.35);transition:.18s;white-space:nowrap}
.cp-submit-btn:hover{transform:translateY(-2px);box-shadow:0 10px 26px rgba(139,92,246,.45)}
.cp-submit-btn:active{transform:translateY(0) scale(.98)}
@media(max-width:760px){
  .cp-row{grid-template-columns:1fr}
  .proto-cards{grid-template-columns:1fr}
  .cp-footer{flex-direction:column;align-items:stretch}
  .cp-submit-btn{justify-content:center}
}
/* ══════ پنل اطلاعات سرور ══════ */
.srv-panel{background:linear-gradient(155deg,var(--bg3) 0%,var(--card) 60%);border:1px solid var(--card-b);border-radius:22px;overflow:hidden;box-shadow:var(--shadow);position:relative}
.srv-panel::before{content:'';position:absolute;top:-60px;left:-60px;width:200px;height:200px;background:radial-gradient(circle,var(--accent-d),transparent 70%);pointer-events:none}
.srv-hero{display:flex;align-items:center;gap:14px;padding:22px 24px;position:relative;z-index:1;border-bottom:1px solid var(--card-b)}
.srv-hero-icon{width:50px;height:50px;border-radius:14px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;color:#fff;font-size:22px;flex-shrink:0;box-shadow:0 6px 18px rgba(139,92,246,.35)}
.srv-hero-text{flex:1;min-width:0}
.srv-hero-domain{font-size:15px;font-weight:800;color:var(--t1);word-break:break-all}
.srv-hero-sub{font-size:10.5px;color:var(--t3);margin-top:4px;display:flex;align-items:center;gap:6px}
.srv-tiles{display:grid;grid-template-columns:1fr 1fr;gap:11px;padding:20px 22px 22px;position:relative;z-index:1}
.srv-tile{display:flex;align-items:center;gap:11px;background:rgba(0,0,0,.14);border:1px solid var(--card-b);border-radius:13px;padding:12px 14px;transition:.18s}
[data-theme="light"] .srv-tile{background:rgba(124,58,237,.03)}
.srv-tile:hover{border-color:var(--card-bh);transform:translateY(-1px)}
.srv-tile-icon{width:34px;height:34px;border-radius:10px;background:var(--accent-d);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0}
.srv-tile-text{min-width:0}
.srv-tile-label{font-size:9.5px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px}
.srv-tile-val{font-size:12px;font-weight:700;color:var(--t1);word-break:break-word}

/* ══════ پنل تغییر رمز ══════ */
.pw-panel{background:linear-gradient(155deg,var(--bg3) 0%,var(--card) 60%);border:1px solid var(--card-b);border-radius:22px;overflow:hidden;box-shadow:var(--shadow);position:relative}
.pw-panel::before{content:'';position:absolute;top:-60px;right:-60px;width:200px;height:200px;background:radial-gradient(circle,var(--purple-bg),transparent 70%);pointer-events:none}
.pw-hero{display:flex;align-items:center;gap:14px;padding:22px 24px 18px;position:relative;z-index:1}
.pw-hero-icon{width:50px;height:50px;border-radius:14px;background:linear-gradient(135deg,var(--purple),#0EA5E9);display:flex;align-items:center;justify-content:center;color:#fff;font-size:22px;flex-shrink:0;box-shadow:0 6px 18px rgba(168,85,247,.35)}
.pw-hero-text{flex:1;min-width:0}
.pw-hero-title{font-size:15px;font-weight:800;color:var(--t1)}
.pw-hero-sub{font-size:10.5px;color:var(--t3);margin-top:3px}
.pw-body{padding:2px 24px 22px;position:relative;z-index:1}
.pw-field{position:relative;margin-bottom:13px}
.pw-field label{display:block;font-size:10px;font-weight:700;color:var(--t2);text-transform:uppercase;letter-spacing:.06em;margin-bottom:7px}
.pw-input{width:100%;padding:11px 42px 11px 14px;border-radius:11px;border:1px solid var(--card-b);background:rgba(0,0,0,.18);color:var(--t1);font-family:inherit;font-size:12.5px;outline:none;transition:.15s}
[data-theme="light"] .pw-input{background:#fff}
.pw-input:focus{border-color:rgba(168,85,247,.5);box-shadow:0 0 0 3px rgba(168,85,247,.1)}
.pw-eye{position:absolute;left:12px;top:34px;background:none;border:none;color:var(--t3);cursor:pointer;font-size:16px;padding:4px;display:flex}
.pw-eye:hover{color:var(--purple)}
.pw-strength{height:4px;border-radius:3px;background:var(--accent-d);margin-top:8px;overflow:hidden;display:flex;gap:3px}
.pw-strength-seg{flex:1;height:100%;border-radius:3px;background:rgba(100,116,139,.2);transition:.25s}
.pw-strength-label{font-size:9.5px;color:var(--t3);margin-top:5px;display:flex;align-items:center;gap:5px}
.pw-reqs{display:flex;flex-wrap:wrap;gap:6px;margin-top:11px;margin-bottom:16px}
.pw-req{font-size:9.5px;padding:4px 10px;border-radius:7px;background:var(--accent-d);color:var(--t3);font-weight:600;display:flex;align-items:center;gap:4px;transition:.18s}
.pw-req.met{background:var(--green-bg);color:var(--green-t)}
.pw-submit{width:100%;justify-content:center;background:linear-gradient(135deg,var(--purple),#0EA5E9);color:#fff;border:none;border-radius:12px;padding:12px;font-family:inherit;font-size:13px;font-weight:800;cursor:pointer;display:flex;align-items:center;gap:8px;box-shadow:0 6px 18px rgba(168,85,247,.32);transition:.18s}
.pw-submit:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(168,85,247,.42)}
.pw-submit:active{transform:translateY(0) scale(.98)}

/* ══════ اتصالات فعال - نسخه پیشرفته ══════ */
.conn-hero{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
.conn-hero-tile{background:var(--card);border:1px solid var(--card-b);border-radius:16px;padding:16px 18px;position:relative;overflow:hidden;transition:.2s}
.conn-hero-tile:hover{border-color:var(--card-bh);transform:translateY(-2px);box-shadow:var(--shadow)}
.conn-hero-tile::after{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--green),transparent)}
.conn-hero-icon{width:32px;height:32px;border-radius:9px;background:var(--green-bg);color:var(--green-t);display:flex;align-items:center;justify-content:center;font-size:15px;margin-bottom:10px}
.conn-hero-tile:nth-child(2) .conn-hero-icon{background:var(--accent-d);color:var(--accent)}
.conn-hero-tile:nth-child(3) .conn-hero-icon{background:var(--purple-bg);color:var(--purple)}
.conn-hero-tile:nth-child(4) .conn-hero-icon{background:var(--amber-bg);color:var(--amber)}
.conn-hero-label{font-size:9.5px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
.conn-hero-val{font-size:21px;font-weight:800;color:var(--t1);line-height:1;letter-spacing:-.02em}
.conn-hero-unit{font-size:11px;color:var(--t3);font-weight:500}

.conn-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.conn-toolbar-title{font-size:12px;font-weight:800;color:var(--t2);display:flex;align-items:center;gap:7px;text-transform:uppercase;letter-spacing:.06em}
.conn-toolbar-title i{color:var(--green);font-size:15px}
.conn-live-badge{display:flex;align-items:center;gap:6px;font-size:10.5px;font-weight:700;color:var(--green-t);background:var(--green-bg);padding:5px 12px;border-radius:20px;border:1px solid rgba(16,185,129,.2)}
.conn-live-dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 1.6s infinite}

.rt-mode-card{padding:14px 16px;border-radius:14px;border:1.5px solid var(--card-b);background:var(--bg);cursor:pointer;transition:all .18s ease;position:relative}
.rt-mode-card:hover{transform:translateY(-2px);border-color:var(--accent)}
.rt-mode-card.sel{border-color:var(--accent);background:linear-gradient(135deg,rgba(249,115,22,.12),rgba(76,201,240,.06));box-shadow:0 0 0 1px var(--accent)}
.rt-mode-title{font-size:13px;font-weight:800;margin-bottom:6px}
.rt-mode-sub{font-size:11.5px;color:var(--t3);line-height:1.8}
.rt-mode-tag{position:absolute;top:10px;left:12px;font-size:10px;font-family:monospace;color:var(--t3);opacity:.8}
.ac-card{padding:16px;border-radius:14px;border:1px solid var(--card-b);background:var(--bg)}
.ac-dev-row{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:10px;background:var(--card);margin-bottom:6px;font-size:12px}
.ac-status-chip{font-size:10px;padding:2px 8px;border-radius:20px;font-weight:700}
.conn-grid-v2{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.conn-card-v2{background:var(--card);border:1px solid var(--card-b);border-radius:18px;padding:0;overflow:hidden;transition:all .22s cubic-bezier(.4,0,.2,1);position:relative}
.conn-card-v2:hover{border-color:var(--card-bh);transform:translateY(-3px);box-shadow:0 14px 32px rgba(0,0,0,.22)}
.conn-card-v2-glow{position:absolute;top:-40px;left:-40px;width:140px;height:140px;background:radial-gradient(circle,rgba(16,185,129,.1),transparent 70%);pointer-events:none}
.conn-card-v2-top{display:flex;align-items:center;gap:12px;padding:16px 17px 13px;position:relative;z-index:1}
.conn-avatar{width:42px;height:42px;border-radius:13px;background:linear-gradient(135deg,var(--green),#0D9668);display:flex;align-items:center;justify-content:center;color:#fff;font-size:18px;flex-shrink:0;position:relative;box-shadow:0 4px 14px rgba(16,185,129,.3)}
.conn-avatar::after{content:'';position:absolute;inset:-4px;border-radius:16px;border:1.5px solid var(--green);opacity:.4;animation:breathe2 2.4s ease-in-out infinite}
@keyframes breathe2{0%,100%{transform:scale(1);opacity:.4}50%{transform:scale(1.12);opacity:0}}
.conn-card-v2-id{flex:1;min-width:0}
.conn-ip-v2{font-family:ui-monospace,monospace;font-size:14px;font-weight:800;color:var(--t1);display:flex;align-items:center;gap:6px}
.conn-ip-copy{background:none;border:none;color:var(--t3);cursor:pointer;font-size:12px;padding:2px;display:flex;transition:.15s}
.conn-ip-copy:hover{color:var(--accent)}
.conn-label-v2{font-size:10.5px;color:var(--t3);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.conn-status-pill{font-size:9px;font-weight:800;padding:4px 9px;border-radius:20px;background:var(--green-bg);color:var(--green-t);display:flex;align-items:center;gap:4px;white-space:nowrap;flex-shrink:0}
.conn-card-v2-divider{height:1px;background:linear-gradient(90deg,transparent,var(--card-b) 15%,var(--card-b) 85%,transparent);margin:0 17px}
.conn-card-v2-body{padding:14px 17px 16px}
.conn-proto-row{margin-bottom:12px}
.conn-stat-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}
.conn-stat-box{display:flex;align-items:center;gap:8px}
.conn-stat-icon{width:26px;height:26px;border-radius:8px;background:var(--accent-d);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0}
.conn-stat-icon.time{background:var(--purple-bg);color:var(--purple)}
.conn-stat-text-label{font-size:8.5px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.conn-stat-text-val{font-size:11.5px;font-weight:700;color:var(--t1);margin-top:1px}
.conn-duration-track{height:5px;border-radius:4px;background:var(--accent-d);overflow:hidden;position:relative}
.conn-duration-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--green),#3FD79C);position:relative;overflow:hidden}
.conn-duration-fill::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent);width:40%;animation:shimmer 1.8s linear infinite}
@keyframes shimmer{0%{transform:translateX(-120%)}100%{transform:translateX(280%)}}

.conn-empty-v2{text-align:center;padding:70px 20px;background:var(--card);border:1px dashed var(--card-b);border-radius:20px}
.conn-empty-v2-icon{width:64px;height:64px;border-radius:18px;background:var(--accent-d);display:flex;align-items:center;justify-content:center;font-size:28px;color:var(--t3);margin:0 auto 16px}
.conn-empty-v2-title{font-size:13.5px;font-weight:700;color:var(--t2);margin-bottom:5px}
.conn-empty-v2-sub{font-size:11px;color:var(--t3)}

@media(max-width:760px){.conn-hero{grid-template-columns:1fr 1fr}}
@media(max-width:500px){.rt-mode-card{padding:14px 16px;border-radius:14px;border:1.5px solid var(--card-b);background:var(--bg);cursor:pointer;transition:all .18s ease;position:relative}
.rt-mode-card:hover{transform:translateY(-2px);border-color:var(--accent)}
.rt-mode-card.sel{border-color:var(--accent);background:linear-gradient(135deg,rgba(249,115,22,.12),rgba(76,201,240,.06));box-shadow:0 0 0 1px var(--accent)}
.rt-mode-title{font-size:13px;font-weight:800;margin-bottom:6px}
.rt-mode-sub{font-size:11.5px;color:var(--t3);line-height:1.8}
.rt-mode-tag{position:absolute;top:10px;left:12px;font-size:10px;font-family:monospace;color:var(--t3);opacity:.8}
.ac-card{padding:16px;border-radius:14px;border:1px solid var(--card-b);background:var(--bg)}
.ac-dev-row{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:10px;background:var(--card);margin-bottom:6px;font-size:12px}
.ac-status-chip{font-size:10px;padding:2px 8px;border-radius:20px;font-weight:700}
.conn-grid-v2{grid-template-columns:1fr}}

@media(max-width:560px){.srv-tiles{grid-template-columns:1fr}}
.cl.amber i{color:var(--amber)}
.sub-box{background:rgba(168,85,247,.07);border:1px solid rgba(168,85,247,.2);border-radius:10px;padding:14px 16px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-top:11px}
.sub-url{font-family:ui-monospace,monospace;font-size:10.5px;color:#FFB199;word-break:break-all;flex:1}
.spbar{height:4px;border-radius:3px;background:var(--accent-d);margin-top:5px;overflow:hidden}
.spfill{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width 1s}
.empty{text-align:center;padding:50px 20px;color:var(--t3)}
.empty i{font-size:40px;opacity:.3;margin-bottom:12px;display:block}
.empty p{font-size:12.5px;margin-top:4px}
/* ══════ گروه‌های ساب - ریدیزاین کامل ══════ */
.subs-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.subs-search{flex:1;min-width:200px;position:relative}
.subs-search input{width:100%;padding:11px 40px 11px 15px;border-radius:12px;border:1px solid var(--card-b);background:var(--card);color:var(--t1);font-family:inherit;font-size:12.5px;outline:none;transition:.15s}
.subs-search input:focus{border-color:rgba(168,85,247,.5);box-shadow:0 0 0 3px rgba(168,85,247,.1)}
.subs-search i{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--t3);font-size:15px}

.sub-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;margin-bottom:18px}
.sub-card{background:var(--card);border:1px solid var(--card-b);border-radius:20px;padding:0;overflow:hidden;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative}
.sub-card:hover{border-color:var(--card-bh);transform:translateY(-4px);box-shadow:0 16px 36px rgba(0,0,0,.24)}
.sub-card-top{background:linear-gradient(155deg,var(--purple-bg) 0%,transparent 65%);padding:20px 20px 16px;position:relative}
.sub-card-top::before{content:'';position:absolute;top:-30px;left:-30px;width:130px;height:130px;background:radial-gradient(circle,rgba(168,85,247,.14),transparent 70%);pointer-events:none}
.sub-card-head-v2{display:flex;align-items:flex-start;gap:13px;position:relative;z-index:1}
.sub-card-icon{width:46px;height:46px;border-radius:14px;background:linear-gradient(135deg,var(--purple),#0EA5E9);display:flex;align-items:center;justify-content:center;color:#fff;font-size:20px;flex-shrink:0;box-shadow:0 6px 16px rgba(168,85,247,.35)}
.sub-card-titles{flex:1;min-width:0}
.sub-card-name-v2{font-size:15.5px;font-weight:800;color:var(--t1);letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sub-card-desc-v2{font-size:11px;color:var(--t3);margin-top:3px;line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.sub-card-lock-badge{flex-shrink:0;width:26px;height:26px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:12px}
.sub-card-lock-badge.locked{background:var(--amber-bg);color:var(--amber-t)}
.sub-card-lock-badge.open{background:var(--green-bg);color:var(--green-t)}

.sub-card-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:0;position:relative;z-index:1;margin-top:16px;background:rgba(0,0,0,.14);border:1px solid var(--card-b);border-radius:13px;overflow:hidden}
[data-theme="light"] .sub-card-stats{background:rgba(8,145,178,.03)}
.sub-card-stat{padding:11px 8px;text-align:center;border-left:1px solid var(--card-b)}
.sub-card-stat:last-child{border-left:none}
.sub-card-stat-val{font-size:15px;font-weight:800;color:var(--t1);line-height:1.2}
.sub-card-stat-label{font-size:8.5px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-top:4px}

.sub-card-url-row{margin:14px 20px 0;background:rgba(168,85,247,.08);border:1px dashed rgba(168,85,247,.25);border-radius:11px;padding:9px 12px;display:flex;align-items:center;gap:8px}
.sub-card-url-text{font-family:ui-monospace,monospace;font-size:9.5px;color:#FFB199;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sub-card-url-copy{background:none;border:none;color:var(--purple);cursor:pointer;font-size:13px;padding:3px;display:flex;flex-shrink:0;transition:.15s}
.sub-card-url-copy:hover{color:#FFB199;transform:scale(1.1)}

.sub-card-bottom{padding:14px 20px 18px;display:flex;gap:7px;flex-wrap:wrap}
.sub-card-bottom .btn{flex:1;justify-content:center;min-width:fit-content}

.subs-empty-v2{text-align:center;padding:70px 20px;background:var(--card);border:1px dashed var(--card-b);border-radius:20px;grid-column:1/-1}
.subs-empty-v2-icon{width:64px;height:64px;border-radius:18px;background:var(--purple-bg);display:flex;align-items:center;justify-content:center;font-size:28px;color:var(--purple);margin:0 auto 16px}
.subs-empty-v2-title{font-size:13.5px;font-weight:700;color:var(--t2);margin-bottom:5px}
.subs-empty-v2-sub{font-size:11px;color:var(--t3)}

/* ══════ مودال ساخت گروه - نسخه فشرده ══════ */
.modal-v2{background:var(--card);border:1px solid var(--card-b);border-radius:22px;padding:0;max-width:430px;width:calc(100% - 32px);max-height:92vh;overflow-y:auto;position:relative;animation:fi .2s ease;box-shadow:0 24px 70px rgba(0,0,0,.5)}
.modal-v2-head{background:linear-gradient(155deg,rgba(168,85,247,.14) 0%,transparent 65%);padding:18px 22px 14px;position:relative;overflow:hidden}
.modal-v2-head::before{content:'';position:absolute;top:-50px;left:-50px;width:160px;height:160px;background:radial-gradient(circle,rgba(168,85,247,.2),transparent 70%);pointer-events:none}
.modal-v2-close{position:absolute;top:14px;left:14px;background:var(--accent-d);border:1px solid var(--card-b);color:var(--t2);width:30px;height:30px;border-radius:9px;font-size:15px;display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:2;transition:.15s}
.modal-v2-close:hover{background:var(--red-bg);color:var(--red-t);border-color:rgba(239,68,68,.25)}
.modal-v2-icon{width:42px;height:42px;border-radius:13px;background:linear-gradient(135deg,var(--purple),#0EA5E9);display:flex;align-items:center;justify-content:center;color:#fff;font-size:19px;margin-bottom:10px;position:relative;z-index:1;box-shadow:0 8px 18px rgba(168,85,247,.4)}
.modal-v2-title{font-size:15.5px;font-weight:800;color:var(--t1);position:relative;z-index:1;letter-spacing:-.01em}
.modal-v2-sub{font-size:10.5px;color:var(--t3);margin-top:3px;position:relative;z-index:1;line-height:1.6}
.modal-v2-body{padding:16px 22px 20px;border-top:1px solid var(--card-b)}
.modal-v2-field{margin-bottom:11px}
.modal-v2-field label{display:flex;align-items:center;gap:5px;font-size:9.5px;font-weight:800;color:var(--t2);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
.modal-v2-field label i{color:var(--purple);font-size:13px}
.modal-v2-input-wrap{position:relative}
.modal-v2-input-wrap>i{position:absolute;right:13px;top:50%;transform:translateY(-50%);color:var(--t3);font-size:14px;pointer-events:none;transition:.15s;z-index:1}
.modal-v2-input{width:100%;padding:9px 38px 9px 13px;border-radius:11px;border:1px solid var(--card-b);background:rgba(0,0,0,.2);color:var(--t1);font-family:inherit;font-size:12.5px;outline:none;transition:.18s}
[data-theme="light"] .modal-v2-input{background:rgba(8,145,178,.04)}
.modal-v2-input::placeholder{color:var(--t3)}
.modal-v2-input:focus{border-color:rgba(168,85,247,.55);box-shadow:0 0 0 3px rgba(168,85,247,.12);background:rgba(0,0,0,.28)}
[data-theme="light"] .modal-v2-input:focus{background:#fff}
.modal-v2-input:focus~i{color:var(--purple)}
.modal-v2-hint{background:rgba(139,92,246,.08);border:1px solid rgba(139,92,246,.18);border-radius:11px;padding:9px 12px;font-size:10px;color:var(--t2);display:flex;gap:7px;align-items:flex-start;line-height:1.6;margin-top:2px}
.modal-v2-hint i{font-size:14px;color:var(--accent);margin-top:1px;flex-shrink:0}
.modal-v2-footer{display:flex;gap:8px;margin-top:15px}
.sdev-grid{display:flex;flex-direction:column;gap:10px;margin-top:4px}
.sdev-card{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:14px;background:var(--card-in);border:1px solid var(--border);text-decoration:none;transition:all .2s cubic-bezier(.4,0,.2,1)}
.sdev-card:hover{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 8px 20px -8px rgba(0,0,0,.35)}
.sdev-card-p{border-color:rgba(245,158,11,.35);background:rgba(245,158,11,.06)}
.sdev-card-p:hover{border-color:#F59E0B}
.sdev-ic{width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;flex-shrink:0;box-shadow:0 4px 12px -2px rgba(0,0,0,.35)}
.sdev-txt{display:flex;flex-direction:column;gap:2px;flex:1;min-width:0}
.sdev-t{font-size:13.5px;font-weight:600;color:var(--text)}
.sdev-s{font-size:11px;color:var(--mid)}
.sdev-go{font-size:15px;color:var(--dim);flex-shrink:0}
.modal-v2-btn-cancel{flex:.75;justify-content:center;padding:10px;border-radius:11px;background:transparent;border:1px solid var(--card-b);color:var(--t2);font-family:inherit;font-size:12px;font-weight:700;cursor:pointer;transition:.15s;display:flex;align-items:center}
.modal-v2-btn-cancel:hover{background:var(--accent-d);color:var(--t1)}
.modal-v2-btn-submit{flex:1;justify-content:center;padding:10px;border-radius:11px;background:linear-gradient(135deg,var(--purple),#0EA5E9);color:#fff;border:none;font-family:inherit;font-size:12px;font-weight:800;cursor:pointer;display:flex;align-items:center;gap:6px;box-shadow:0 6px 18px rgba(168,85,247,.4);transition:.18s}
.modal-v2-btn-submit:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(168,85,247,.5)}
.modal-v2-btn-submit:active{transform:translateY(0) scale(.98)}

/* ══════ مودال انتخاب کانفیگ - نسخه پیشرفته ══════ */
.lmodal-head{background:linear-gradient(155deg,var(--accent-d) 0%,transparent 70%);padding:22px 24px 18px;position:relative;border-bottom:1px solid var(--card-b)}
.lmodal-icon-row{display:flex;align-items:center;gap:12px;position:relative;z-index:1}
.lmodal-icon{width:44px;height:44px;border-radius:13px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;color:#fff;font-size:19px;flex-shrink:0;box-shadow:0 6px 16px rgba(139,92,246,.35)}
.lmodal-title-v2{font-size:14.5px;font-weight:800;color:var(--t1)}
.lmodal-sub-v2{font-size:10.5px;color:var(--t3);margin-top:2px}
.lmodal-search{margin-top:14px;position:relative}
.lmodal-search input{width:100%;padding:10px 38px 10px 13px;border-radius:11px;border:1px solid var(--card-b);background:rgba(0,0,0,.2);color:var(--t1);font-family:inherit;font-size:12px;outline:none}
[data-theme="light"] .lmodal-search input{background:#fff}
.lmodal-search input:focus{border-color:rgba(139,92,246,.5);box-shadow:0 0 0 3px rgba(139,92,246,.1)}
.lmodal-search i{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--t3);font-size:14px}
.lmodal-quickbar{display:flex;gap:8px;margin-top:11px;position:relative;z-index:1}
.lmodal-qbtn{font-size:10px;font-weight:700;padding:5px 11px;border-radius:8px;background:var(--accent-d);color:var(--accent2);border:1px solid var(--card-b);cursor:pointer;transition:.15s;font-family:inherit}
.lmodal-qbtn:hover{background:rgba(139,92,246,.2)}
.lmodal-count{margin-right:auto;font-size:10.5px;color:var(--t3);display:flex;align-items:center}

.lmodal-list{padding:10px 14px;max-height:360px;overflow-y:auto}
/* مودال مدیریت کانفیگ‌های گروه - لایه‌بندی flex برای حذف دوبل اسکرول */
#modal-links .modal-v2{overflow:hidden !important}
#modal-links .lmodal-list{max-height:none;flex:1;min-height:0}
.lrow-v2{display:flex;align-items:center;gap:11px;padding:11px 12px;border-radius:13px;cursor:pointer;transition:.15s;margin-bottom:4px;border:1px solid transparent}
.lrow-v2:hover{background:var(--accent-d)}
.lrow-v2.checked{background:rgba(139,92,246,.1);border-color:rgba(139,92,246,.25)}
.lrow-v2-check{width:20px;height:20px;border-radius:7px;border:2px solid var(--card-b);flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:.15s;background:rgba(0,0,0,.14)}
.lrow-v2.checked .lrow-v2-check{background:var(--accent);border-color:var(--accent)}
.lrow-v2-check i{font-size:12px;color:#fff;opacity:0;transform:scale(.5);transition:.15s}
.lrow-v2.checked .lrow-v2-check i{opacity:1;transform:scale(1)}
.lrow-v2-avatar{width:34px;height:34px;border-radius:10px;background:var(--accent-d);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0}
.lrow-v2.checked .lrow-v2-avatar{background:var(--accent);color:#fff}
.lrow-v2-info{flex:1;min-width:0}
.lrow-v2-name{font-size:12.5px;font-weight:700;color:var(--t1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lrow-v2-meta{font-size:9.5px;color:var(--t3);margin-top:2px;display:flex;align-items:center;gap:6px}
.lrow-v2-status{font-size:9px;font-weight:800;padding:3px 9px;border-radius:20px;flex-shrink:0;white-space:nowrap}
.lrow-v2-status.on{background:var(--green-bg);color:var(--green-t)}
.lrow-v2-status.off{background:var(--red-bg);color:var(--red-t)}

.lmodal-footer{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:16px 24px;border-top:1px solid var(--card-b)}
.lmodal-footer-info{font-size:10.5px;color:var(--t3);display:flex;align-items:center;gap:6px}
.lmodal-footer-info i{color:var(--accent)}
.lmodal-footer-btns{display:flex;gap:8px}

@media(max-width:500px){.sub-grid{grid-template-columns:1fr}.sub-card-stats{grid-template-columns:repeat(3,1fr)}}

.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:500;align-items:center;justify-content:center;backdrop-filter:blur(4px)}
.modal-bg.open{display:flex}
.modal{background:var(--card);border:1px solid var(--card-b);border-radius:20px;padding:28px 26px;max-width:520px;width:calc(100% - 32px);max-height:90vh;overflow-y:auto;position:relative;animation:fi .2s ease}
.modal-close{position:absolute;top:14px;left:14px;background:var(--accent-d);border:1px solid var(--card-b);color:var(--t2);width:30px;height:30px;border-radius:8px;font-size:16px;display:flex;align-items:center;justify-content:center;cursor:pointer;border:none}
.modal-title{font-size:16px;font-weight:700;color:var(--t1);margin-bottom:18px;display:flex;align-items:center;gap:8px}
.modal-title i{color:var(--accent)}
.lrow{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid rgba(139,92,246,.05)}
.lrow:last-child{border-bottom:none}
.lrow-check{width:16px;height:16px;border-radius:4px;cursor:pointer;accent-color:var(--accent)}
.lrow-label{flex:1;font-size:12px;color:var(--t1)}
.lrow-badge{font-size:9px;padding:2px 7px;border-radius:5px;background:var(--green-bg);color:var(--green-t);font-weight:700}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%) translateY(40px);background:var(--card);border:1px solid var(--card-b);color:var(--t1);border-radius:10px;padding:10px 18px;font-size:12.5px;opacity:0;transition:all .25s;z-index:999;pointer-events:none;display:flex;align-items:center;gap:8px;box-shadow:var(--shadow);white-space:nowrap}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.ok{border-color:rgba(16,185,129,.3);background:var(--green-bg);color:var(--green-t)}
.toast.err{border-color:rgba(239,68,68,.3);background:var(--red-bg);color:var(--red-t)}
/* ══════ نوار اعلان‌های همگانی ══════ */
.ann-banner-wrap{display:flex;flex-direction:column;gap:10px;margin-bottom:18px}
.ann-card{position:relative;display:flex;gap:13px;background:var(--card);border:1px solid var(--card-b);border-radius:16px;padding:15px 44px 15px 17px;box-shadow:var(--shadow);animation:fi .25s ease;overflow:hidden}
.ann-card::before{content:'';position:absolute;top:0;right:0;width:4px;height:100%}
.ann-card.news::before{background:var(--accent)}
.ann-card.ad::before{background:var(--purple)}
.ann-card.warning::before{background:var(--amber)}
.ann-card.urgent::before{background:var(--red)}
.ann-icon{width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.ann-card.news .ann-icon{background:var(--accent-d);color:var(--accent2)}
.ann-card.ad .ann-icon{background:var(--purple-bg);color:var(--purple)}
.ann-card.warning .ann-icon{background:var(--amber-bg);color:var(--amber-t)}
.ann-card.urgent .ann-icon{background:var(--red-bg);color:var(--red-t)}
.ann-body{flex:1;min-width:0}
.ann-title{font-size:13px;font-weight:700;color:var(--t1);margin-bottom:4px}
.ann-text{font-size:12px;color:var(--t2);line-height:1.8}
.ann-img{max-width:100%;border-radius:10px;margin-top:10px;border:1px solid var(--card-b);display:block}
.ann-close{position:absolute;top:10px;left:10px;width:24px;height:24px;border-radius:7px;background:var(--accent-d);border:none;color:var(--t3);font-size:13px;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:.15s}
.ann-close:hover{background:var(--red-bg);color:var(--red-t)}
.dash-footer{border-top:1px solid var(--card-b);margin-top:14px;padding-top:14px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}
.df-text{font-size:10px;color:var(--t3)}
.df-link{font-size:11.5px;color:var(--accent2);display:flex;align-items:center;gap:5px;font-weight:600}

.info-strip{display:flex;align-items:center;background:var(--card);border:1px solid var(--card-b);border-radius:16px;padding:16px 22px;margin-bottom:16px;gap:0;flex-wrap:wrap;box-shadow:var(--shadow)}
.info-item{display:flex;flex-direction:column;gap:6px;flex:1;min-width:130px;padding:0 18px;position:relative}
.info-item:not(:first-child)::before{content:'';position:absolute;right:0;top:2px;bottom:2px;width:1px;background:var(--card-b)}
.info-item-label{font-size:10.5px;color:var(--t3);font-weight:700}
.info-item-val{display:flex;align-items:center;gap:7px;font-size:15px;font-weight:800;color:var(--t1);letter-spacing:-.01em}
.info-item-val i{color:var(--accent);font-size:16px}
.info-item-val .info-badge{font-size:11px;font-weight:800;background:var(--green-bg);color:var(--green-t);padding:2px 9px;border-radius:20px}
@media(max-width:760px){.info-strip{gap:14px}.info-item{min-width:45%;padding:0 0 10px}.info-item:not(:first-child)::before{display:none}}

/* ══════ کانفیگ‌ها - طراحی ردیفی حرفه‌ای ══════ */
.cfg-grid{display:flex;flex-direction:column;gap:10px}
.cfg-card{background:var(--card);border:1px solid var(--card-b);border-radius:14px;padding:0;transition:all .2s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden}
.cfg-card:hover{border-color:var(--card-bh);box-shadow:0 6px 24px rgba(0,0,0,.18)}
.cfg-card.is-off{opacity:.6}
.cfg-card.is-exp{opacity:.78}
.cfg-row{display:flex;align-items:center;gap:16px;padding:14px 18px}
.cfg-status-dot{width:9px;height:9px;border-radius:50%;background:var(--green);flex-shrink:0;box-shadow:0 0 0 3px var(--green-bg)}
.cfg-card.is-off .cfg-status-dot{background:var(--red);box-shadow:0 0 0 3px var(--red-bg)}
.cfg-card.is-exp .cfg-status-dot{background:var(--amber);box-shadow:0 0 0 3px var(--amber-bg)}
.cfg-identity{display:flex;flex-direction:column;gap:3px;min-width:150px;flex-shrink:0}
.cfg-label{font-size:13.5px;font-weight:700;color:var(--t1);display:flex;align-items:center;gap:7px}
.cfg-sub-meta{display:flex;align-items:center;gap:8px;font-size:10px;color:var(--t3)}
.cfg-uuid-mini{font-family:ui-monospace,monospace;font-size:9.5px;color:var(--accent2);background:var(--accent-d);padding:2px 7px;border-radius:5px;cursor:pointer;transition:.15s}
.cfg-uuid-mini:hover{background:rgba(139,92,246,.2)}
.cfg-divider-v{width:1px;align-self:stretch;background:var(--card-b);flex-shrink:0}
.cfg-usage-col{flex:1;min-width:160px;display:flex;flex-direction:column;gap:5px}
.ubar{height:5px;border-radius:4px;background:rgba(139,92,246,0.1);overflow:hidden}
.ubar-f{height:100%;border-radius:4px;transition:width .4s ease}
.utxt{font-size:10px;color:var(--t3);display:flex;justify-content:space-between}
.cfg-exp-col{flex-shrink:0;min-width:110px}
.cfg-badges-col{display:flex;flex-direction:column;gap:5px;flex-shrink:0;align-items:flex-end}
.cfg-actions{display:flex;gap:5px;flex-shrink:0}
.proto-chip{font-size:9px;padding:3px 8px;border-radius:6px;font-weight:700;white-space:nowrap}
.pc-ws{background:var(--accent-d);color:var(--accent2)}
.pc-xhttp{background:var(--purple-bg);color:#FFB199}
.pc-ultra{background:var(--green-bg);color:var(--green-t)}
.pc-ss{background:var(--purple-bg);color:#FFB199}
.cfg-sub-tag{font-size:9.5px;color:var(--t3);display:flex;align-items:center;gap:4px;white-space:nowrap}
.cfg-sub-tag i{color:var(--purple);font-size:11px}
.tog{width:19px;height:30px;border-radius:19px;background:rgba(100,116,139,0.25);position:relative;cursor:pointer;transition:.2s;flex-shrink:0;border:none}
.tog::after{content:'';position:absolute;width:13px;height:13px;border-radius:50%;background:#fff;left:3px;top:3px;transition:.2s;box-shadow:0 1px 3px rgba(0,0,0,.3)}
.tog.on::after{top:14px}
.tog.on{background:var(--green)}

/* ── انتخاب گروهی کانفیگ‌ها ── */
.cfg-check{width:19px;height:19px;border-radius:6px;border:2px solid var(--card-b);flex-shrink:0;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:.15s;background:rgba(0,0,0,.14)}
.cfg-check:hover{border-color:var(--accent)}
.cfg-check.checked{background:var(--accent);border-color:var(--accent)}
.cfg-check i{font-size:11px;color:#fff;opacity:0;transform:scale(.5);transition:.15s}
.cfg-check.checked i{opacity:1;transform:scale(1)}
.cfg-card.selected{border-color:rgba(139,92,246,.5);box-shadow:0 0 0 2px rgba(139,92,246,.14)}
.links-selectall{display:flex;align-items:center;gap:7px;font-size:11px;color:var(--t3);cursor:pointer;user-select:none;padding:6px 4px;transition:.15s}
.links-selectall:hover{color:var(--t1)}
.links-bulkbar{display:none;align-items:center;gap:12px;background:var(--card);border:1px solid rgba(139,92,246,.3);border-radius:14px;padding:10px 16px;margin-bottom:12px;animation:bulkbarIn .18s ease}
.links-bulkbar.show{display:flex}
@keyframes bulkbarIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:translateY(0)}}
.links-bulkbar-count{font-size:12px;font-weight:700;color:var(--t1);display:flex;align-items:center;gap:6px;white-space:nowrap}
.links-bulkbar-count i{color:var(--accent)}
.links-bulkbar-actions{display:flex;gap:8px;margin-right:auto;flex-wrap:wrap}

/* ══════════════ صفحه‌ی نود — اتصال چند پنل به هم ══════════════ */
/* امضای بصری این بخش: نقشه‌ی «صورت‌فلکی» — نقطه‌ها (پنل‌ها) با خط‌چین متحرک (لینک نود) به هم وصل می‌شوند */
@keyframes nodeflow{to{stroke-dashoffset:-120}}
@keyframes nodering{0%{transform:scale(.86);opacity:.85}100%{transform:scale(1.45);opacity:0}}
@keyframes nodefloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}

.node-hero{position:relative;overflow:hidden;border-radius:18px;border:1px solid var(--card-b);
  background:linear-gradient(160deg,rgba(139,92,246,.11) 0%,rgba(168,85,247,.07) 48%,var(--card) 100%);
  padding:18px 20px 16px;margin-bottom:14px;isolation:isolate}
.node-hero-net{position:absolute;inset:0;z-index:0;opacity:.65;pointer-events:none}
.node-hero-net svg{width:100%;height:100%}
.node-hero-net .nh-line{stroke:var(--card-bh);stroke-width:1.1;fill:none;stroke-dasharray:2 7;animation:nodeflow 7s linear infinite}
.node-hero-net .nh-dot{fill:var(--accent2)}
.node-hero-top{position:relative;z-index:1;display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}
.node-hero-title{display:flex;align-items:center;gap:14px}
.node-hero-icon{width:48px;height:48px;border-radius:15px;flex-shrink:0;position:relative;
  background:linear-gradient(135deg,var(--accent),var(--purple));display:flex;align-items:center;justify-content:center;
  color:#fff;font-size:22px;box-shadow:0 10px 22px -4px rgba(124,58,237,.45);animation:nodefloat 4.5s ease-in-out infinite}
.node-hero-icon::after{content:'';position:absolute;inset:-6px;border-radius:18px;border:1.5px solid rgba(34,211,238,.4);animation:nodering 2.6s ease-out infinite}
.node-hero .tb-title{font-size:18px}
.node-hero .tb-sub{max-width:420px}
.node-hero-metrics{position:relative;z-index:1;display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin-top:16px}
/* ─── ریسپانسیو بخش گیمینگ/ZEUS — جلوگیری از overlap و overflow موبایل ─── */
@media(max-width:900px){.node-hero-metrics{grid-template-columns:repeat(2,1fr)}}
@media(max-width:520px){
  .node-hero-metrics{grid-template-columns:1fr}
  .node-hero-top{flex-direction:column;align-items:flex-start;gap:10px}
  .node-metric-val{font-size:13px !important;word-break:break-all}
  #gaming-scan-table table{font-size:10px}
  #gaming-scan-table th,#gaming-scan-table td{padding:4px 4px !important}
  #pg-gaming pre{max-height:200px;font-size:9px}
  #gaming-loc-list-box>div{width:100%}
}
.node-metric{background:rgba(0,0,0,.14);border:1px solid var(--card-b);border-radius:12px;padding:10px 12px;transition:.2s}
.node-metric:hover{border-color:var(--card-bh);transform:translateY(-2px)}
.node-metric-top{display:flex;align-items:center;gap:7px;margin-bottom:8px}
.node-metric-top i{font-size:14px;color:var(--accent2)}
.node-metric-label{font-size:9.5px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.05em}
.node-metric-val{font-size:19px;font-weight:800;color:var(--t1);letter-spacing:-.02em;line-height:1}
.node-metric-sub{font-size:9.5px;color:var(--t3);margin-top:6px}

/* ── کلیدهای صادرشده (مینیمال) ── */
.node-keys-card{position:relative;border-radius:16px;padding:1px;background:linear-gradient(135deg,rgba(139,92,246,.28),rgba(168,85,247,.2));margin-bottom:16px}
.node-keys-card>.card{border-radius:15px;margin:0;border:none;background:var(--card)}
.node-key-row{display:flex;align-items:center;gap:11px;padding:11px 8px;border-bottom:1px solid rgba(139,92,246,.07);transition:.15s}
.node-key-row:last-child{border-bottom:none}
.node-key-row:hover{background:rgba(139,92,246,.035)}
.node-key-row.off{opacity:.55}
.node-key-dot{width:7px;height:7px;border-radius:50%;background:var(--green);flex-shrink:0;box-shadow:0 0 0 3px var(--green-bg)}
.node-key-row.off .node-key-dot{background:var(--t3);box-shadow:0 0 0 3px rgba(0,0,0,.12)}
.node-key-body{min-width:0;flex:1;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.node-key-label{font-size:11.5px;font-weight:700;color:var(--t1);display:flex;align-items:center;gap:6px;white-space:nowrap;flex-shrink:0}
.node-key-label i{font-size:11px;color:var(--accent2)}
.node-key-val{font-family:ui-monospace,Menlo,monospace;font-size:10px;color:var(--t3);direction:ltr;
  background:rgba(0,0,0,.16);border:1px solid var(--card-b);border-radius:7px;padding:4px 10px;cursor:pointer;
  flex:1;min-width:90px;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;transition:.15s;
  display:inline-flex;align-items:center;gap:5px;line-height:1.6}
.node-key-val:hover{color:var(--t1);border-color:var(--accent)}
.node-key-val i{font-size:9.5px;color:var(--accent2);flex-shrink:0}
.node-key-state{font-size:9.5px;color:var(--t3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:1}
.node-key-perms{display:flex;gap:4px;align-items:center;margin-top:6px;flex-wrap:wrap}
.node-perm-ic{width:19px;height:19px;border-radius:6px;background:var(--accent-d);color:var(--accent2);display:flex;align-items:center;justify-content:center;font-size:10px}
.node-perm-ic.off{background:rgba(0,0,0,.14);color:var(--t3);opacity:.45}
.node-perm-ic.manage{background:var(--amber-bg);color:var(--amber-t)}
.node-key-meta{font-size:9.5px;color:var(--t3);margin-right:auto;text-align:left;white-space:nowrap}
.node-key-actions{display:flex;gap:5px;flex-shrink:0;margin-right:auto}
@media(max-width:640px){
  .node-key-row{align-items:flex-start;flex-wrap:wrap}
  .node-key-body{flex-direction:column;align-items:flex-start;gap:5px}
  .node-key-val{max-width:100%;width:100%}
  .node-key-actions{margin-right:0;width:100%;justify-content:flex-end}
}

/* ── گرید نودهای متصل (طراحی جدید) ── */
.nodes-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}
.node-card{background:var(--card);border:1px solid var(--card-b);border-radius:18px;overflow:hidden;
  display:flex;flex-direction:column;transition:.25s cubic-bezier(.2,.8,.3,1);position:relative;isolation:isolate}
.node-card::before{content:'';position:absolute;inset:0;z-index:0;opacity:0;transition:.25s;
  background:radial-gradient(120% 90% at 0% 0%,rgba(139,92,246,.08),transparent 60%)}
.node-card:hover{transform:translateY(-4px);border-color:var(--card-bh);box-shadow:0 16px 32px -14px rgba(0,0,0,.35)}
.node-card:hover::before{opacity:1}
.node-card-bar{height:3px;background:linear-gradient(90deg,var(--green),var(--accent2),var(--purple));background-size:200% 100%;animation:nodebarflow 4s linear infinite}
@keyframes nodebarflow{to{background-position:-200% 0}}
.node-card.is-off .node-card-bar{background:var(--t3);opacity:.3;animation:none}
.node-card.is-err .node-card-bar{background:var(--red);animation:none}
.node-card.is-off{opacity:.6}
.node-card.is-err{border-color:rgba(239,68,68,.3)}
.node-card-body{position:relative;z-index:1;padding:17px 18px 15px;display:flex;flex-direction:column;gap:15px}

.node-head{display:flex;align-items:flex-start;gap:12px}
.node-avatar{width:42px;height:42px;border-radius:13px;display:flex;align-items:center;justify-content:center;flex-shrink:0;position:relative;
  background:linear-gradient(135deg,var(--accent),var(--purple));box-shadow:0 6px 16px -4px rgba(124,58,237,.4)}
.node-avatar i{font-size:19px;color:#fff}
.node-card.is-off .node-avatar,.node-card.is-err .node-avatar{background:linear-gradient(135deg,var(--t3),#555);box-shadow:none}
.node-card.is-err .node-avatar{background:linear-gradient(135deg,var(--red),#B91C1C)}
.node-avatar.online::after{content:'';position:absolute;inset:-4px;border-radius:15px;border:1.5px solid var(--green);opacity:.7;animation:nodering 2.2s ease-out infinite}
.node-avatar-dot{position:absolute;bottom:-2px;left:-2px;width:12px;height:12px;border-radius:50%;background:var(--green);border:2.5px solid var(--card);box-shadow:0 0 0 1px rgba(16,185,129,.3)}
.node-card.is-off .node-avatar-dot{background:var(--t3)}
.node-card.is-err .node-avatar-dot{background:var(--red)}
.node-titles{min-width:0;flex:1;padding-top:1px}
.node-name{font-size:13.5px;font-weight:800;color:var(--t1);display:flex;align-items:center;gap:7px;flex-wrap:wrap;letter-spacing:-.01em}
.node-host{font-size:10px;color:var(--t3);direction:ltr;text-align:right;word-break:break-all;margin-top:4px;
  display:inline-flex;align-items:center;gap:4px;font-family:ui-monospace,Menlo,monospace;cursor:pointer;transition:.15s}
.node-host:hover{color:var(--t2)}
.node-host i{font-size:10px;color:var(--t3);flex-shrink:0}
.node-meta{font-size:9.5px;color:var(--t3);display:flex;align-items:center;gap:5px;margin-top:6px}
.node-meta i{font-size:10px;color:var(--accent2)}
.node-err{background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);border-radius:10px;padding:9px 11px;font-size:10.5px;color:var(--red-t);line-height:1.7;word-break:break-word;display:flex;gap:7px;align-items:flex-start}
.node-err i{margin-top:1px;flex-shrink:0}

.node-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.node-stat{background:rgba(0,0,0,.15);border:1px solid transparent;border-radius:12px;padding:11px 6px;text-align:center;transition:.18s}
.node-stat:hover{background:rgba(0,0,0,.25);border-color:var(--card-b);transform:translateY(-1px)}
.node-stat i{font-size:12px;color:var(--accent2);margin-bottom:5px;display:block}
.node-stat-val{font-size:12.5px;font-weight:800;color:var(--t1);letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.node-stat-label{font-size:8.5px;color:var(--t3);margin-top:3px}

.node-perms{display:flex;flex-wrap:wrap;gap:6px}
.node-perm{display:flex;align-items:center;gap:5px;font-size:9.5px;color:var(--t3);background:rgba(0,0,0,.12);border:1px solid var(--card-b);border-radius:18px;padding:4px 9px 4px 5px;cursor:pointer;user-select:none;transition:.15s}
.node-perm:hover{border-color:var(--accent);color:var(--t2)}
.node-perm.on{color:var(--t1);border-color:rgba(139,92,246,.35);background:var(--accent-d)}
.node-perm .cfg-check{width:13px;height:13px;border-radius:4px;border-width:2px}
.node-perm .cfg-check i{font-size:7.5px}

.node-foot{display:flex;align-items:center;gap:8px;border-top:1px solid var(--card-b);padding:11px 17px;background:rgba(0,0,0,.12);position:relative;z-index:1}
.node-foot .btn{flex:1;justify-content:center}
.node-origin{background:linear-gradient(135deg,rgba(168,85,247,.18),rgba(202,138,4,.12));color:#FFB199;padding:3px 9px;border-radius:20px;border:1px solid rgba(168,85,247,.25);font-weight:700;font-size:10px;display:inline-flex;align-items:center;gap:4px}

/* ── دسترسی‌ها در مودال ساخت کلید: کاشی‌های انتخابی ── */
.nk-perm-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.nk-perm-tile{display:flex;align-items:center;gap:10px;padding:11px 12px;border-radius:13px;border:1px solid var(--card-b);background:rgba(0,0,0,.16);cursor:pointer;transition:.16s;user-select:none}
.nk-perm-tile:hover{border-color:var(--accent);transform:translateY(-1px)}
.nk-perm-tile.on{border-color:rgba(139,92,246,.5);background:var(--accent-d)}
.nk-perm-tile .nk-perm-tile-ic{width:30px;height:30px;border-radius:9px;background:rgba(0,0,0,.22);display:flex;align-items:center;justify-content:center;color:var(--t3);font-size:14px;flex-shrink:0;transition:.16s}
.nk-perm-tile.on .nk-perm-tile-ic{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff}
.nk-perm-tile-txt{min-width:0}
.nk-perm-tile-name{font-size:11px;font-weight:700;color:var(--t1)}
.nk-perm-tile-desc{font-size:9px;color:var(--t3);margin-top:2px;line-height:1.45}
.nk-perm-tile.manage{grid-column:1/-1;margin-top:2px;border-top:1px dashed var(--card-b);padding-top:14px;position:relative}
.nk-perm-tile.manage::before{content:'دسترسی نوشتن';position:absolute;top:-8px;right:12px;background:var(--card);padding:0 6px;font-size:8.5px;font-weight:800;color:var(--t3);letter-spacing:.04em;line-height:1.4;z-index:1}
.nk-perm-tile.manage.on{border-color:rgba(245,158,11,.55);background:var(--amber-bg)}
.nk-perm-tile.manage.on .nk-perm-tile-ic{background:linear-gradient(135deg,var(--amber),#D97706)}

/* ── پیش‌نمایش هاست در مودال اتصال ── */
.nc-host-chip{display:inline-flex;align-items:center;gap:7px;background:var(--accent-d);border:1px solid var(--card-b);
  border-radius:20px;padding:7px 13px;font-size:11px;color:var(--t2);direction:ltr;font-family:ui-monospace,Menlo,monospace;margin-top:8px}
.nc-host-chip i{color:var(--accent2);font-size:13px}

/* ── نمای خالی اختصاصی نود ── */
.node-empty-illust{width:74px;height:74px;margin:0 auto 16px;position:relative}
.node-empty-illust svg{width:100%;height:100%}
.node-empty-illust .ne-line{stroke:var(--card-bh);stroke-width:1.4;stroke-dasharray:3 6;fill:none;animation:nodeflow 5s linear infinite}
.node-empty-illust .ne-dot{fill:var(--accent2)}
.node-empty-illust .ne-dot.mid{fill:var(--purple)}

@media(max-width:880px){
  .cfg-row{flex-wrap:wrap}
  .cfg-divider-v{display:none}
  .cfg-usage-col{min-width:100%;order:5}
}

/* ── زیر ۷۶۸px: تبدیل کامل به کارت موبایل ── */
@media(max-width:768px){
  .cfg-grid{display:grid;grid-template-columns:1fr;gap:13px}
  .cfg-card{border-radius:16px}
  .cfg-row{flex-direction:column;align-items:stretch;gap:12px;padding:16px}
  .cfg-row-top{display:flex;align-items:center;justify-content:space-between;gap:10px}
  .cfg-identity{min-width:0;flex:1}
  .cfg-usage-col{min-width:0}
  .cfg-exp-col{min-width:0}
  .cfg-badges-col{flex-direction:row;align-items:center;flex-wrap:wrap}
  .cfg-actions{flex-wrap:wrap;border-top:1px solid var(--card-b);padding-top:10px;margin-top:2px;width:100%}
}

/* ══════ اتصالات فعال با IP ══════ */
.conn-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.conn-card{background:var(--card);border:1px solid var(--card-b);border-radius:16px;padding:15px 17px;transition:.2s;position:relative;overflow:hidden}
.conn-card:hover{border-color:var(--card-bh);transform:translateY(-1px)}
.conn-card::before{content:'';position:absolute;top:0;right:0;width:3px;height:100%;background:var(--green)}
.conn-ip-row{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.conn-ip-icon{width:32px;height:32px;border-radius:9px;background:var(--green-bg);color:var(--green-t);display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0}
.conn-ip{font-family:ui-monospace,monospace;font-size:13px;font-weight:700;color:var(--t1)}
.conn-label{font-size:10.5px;color:var(--t3);margin-top:1px}
.conn-meta{display:flex;justify-content:space-between;align-items:center;font-size:10px;color:var(--t3);padding-top:10px;border-top:1px solid var(--card-b)}

/* ══════ لاگ فعالیت‌ها ══════ */
.log-timeline{display:flex;flex-direction:column}
.log-item{display:flex;gap:12px;padding:11px 0;border-bottom:1px solid rgba(139,92,246,.05);position:relative}
.log-item:last-child{border-bottom:none}
.log-ic{width:30px;height:30px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0}
.log-ic.ok{background:var(--green-bg);color:var(--green-t)}
.log-ic.err{background:var(--red-bg);color:var(--red-t)}
.log-ic.warn{background:var(--amber-bg);color:var(--amber-t)}
.log-ic.info{background:var(--accent-d);color:var(--accent2)}
.log-body{flex:1;min-width:0}
.log-msg{font-size:12.5px;color:var(--t1);line-height:1.6}
.log-time{font-size:9.5px;color:var(--t3);margin-top:2px;display:flex;align-items:center;gap:5px}
.log-kind{font-size:8.5px;padding:1px 7px;border-radius:10px;background:var(--accent-d);color:var(--accent2);font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.erow{padding:9px 0;border-bottom:1px solid rgba(139,92,246,.05)}
.erow:last-child{border-bottom:none}
.etime{color:var(--t3);font-size:9.5px;margin-bottom:3px;display:flex;align-items:center;gap:4px}
.emsg{color:var(--red-t);font-family:ui-monospace,monospace;background:var(--red-bg);padding:6px 9px;border-radius:6px;word-break:break-all;font-size:10.5px}

@media(max-width:1050px){
  .sidebar{transform:translateX(100%)}
  .sidebar.open{transform:translateX(0);box-shadow:-10px 0 40px rgba(0,0,0,.4)}
  .sb-close{display:flex}
  .main{margin-right:0;padding-top:70px}
  .mob-top{display:flex}
  .metrics{grid-template-columns:1fr 1fr}
  .g2,.g3{grid-template-columns:1fr}
}
@media(max-width:500px){
  .metrics{grid-template-columns:1fr}
  .main{padding:62px 12px 50px}
  .sub-grid,.cfg-grid,.conn-grid{grid-template-columns:1fr}
}
/* ══════ نسخه و بروزرسانی — دیزاین جدید ══════ */
.upd-hero{background:linear-gradient(150deg,var(--bg3) 0%,var(--card) 65%);border:1px solid var(--card-b);border-radius:24px;padding:26px 26px 22px;position:relative;overflow:hidden;box-shadow:var(--shadow);margin-bottom:16px}
.upd-hero-glow{position:absolute;top:-70px;left:-70px;width:260px;height:260px;background:radial-gradient(circle,rgba(139,92,246,.14),transparent 70%);pointer-events:none}
.upd-hero-top{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;position:relative;z-index:1;flex-wrap:wrap;margin-bottom:14px}
.upd-hero-cur{display:flex;align-items:center;gap:14px}
.upd-hero-icon{width:52px;height:52px;border-radius:16px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;color:#fff;font-size:24px;flex-shrink:0;box-shadow:0 8px 22px rgba(139,92,246,.35)}
.upd-hero-label{font-size:10.5px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}
.upd-hero-ver{font-size:26px;font-weight:800;color:var(--t1);letter-spacing:-.02em}
.upd-hero-desc{font-size:12.5px;color:var(--t2);line-height:1.8;position:relative;z-index:1;margin-bottom:14px;background:rgba(0,0,0,.14);border:1px solid var(--card-b);border-radius:12px;padding:12px 14px}
[data-theme="light"] .upd-hero-desc{background:rgba(124,58,237,.03)}
.upd-hero-meta{display:flex;gap:8px;flex-wrap:wrap;position:relative;z-index:1}
.upd-meta-chip{display:flex;align-items:center;gap:6px;font-size:10.5px;font-weight:700;color:var(--t2);background:var(--accent-d);border:1px solid var(--card-b);padding:6px 12px;border-radius:20px}
.upd-meta-chip i{color:var(--accent);font-size:13px}
.upd-pill{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:800;padding:6px 14px;border-radius:20px}
.upd-pill-blue{background:var(--accent-d);color:var(--accent2)}
.upd-pill-green{background:var(--green-bg);color:var(--green-t)}
.upd-pill-amber{background:var(--amber-bg);color:var(--amber-t)}
.upd-dot{width:6px;height:6px;border-radius:50%;background:currentColor;animation:pulse 1.6s infinite}

.upd-latest-card{background:linear-gradient(120deg,var(--amber) 0%,#D97706 100%);border-radius:22px;padding:20px 24px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:16px;box-shadow:0 12px 32px rgba(245,158,11,.28);position:relative;overflow:hidden}
.upd-latest-card::before{content:'';position:absolute;top:-40px;left:-40px;width:180px;height:180px;background:radial-gradient(circle,rgba(255,255,255,.18),transparent 70%);pointer-events:none}
.upd-latest-left{display:flex;align-items:center;gap:14px;position:relative;z-index:1;min-width:220px}
.upd-latest-icon{width:48px;height:48px;border-radius:14px;background:rgba(255,255,255,.22);display:flex;align-items:center;justify-content:center;color:#fff;font-size:22px;flex-shrink:0}
.upd-latest-title{font-size:13px;font-weight:800;color:#fff;opacity:.92}
.upd-latest-ver{font-size:18px;font-weight:800;color:#fff;margin-top:2px}
.upd-latest-desc{font-size:11.5px;color:rgba(255,255,255,.88);margin-top:4px;line-height:1.7;max-width:440px}
.upd-install-btn{background:#fff;color:#B45309;border:none;border-radius:14px;padding:13px 24px;font-family:inherit;font-size:13.5px;font-weight:800;cursor:pointer;display:flex;align-items:center;gap:8px;box-shadow:0 6px 18px rgba(0,0,0,.18);transition:.18s;position:relative;z-index:1;white-space:nowrap}
.upd-install-btn:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(0,0,0,.24)}
.upd-install-btn:active{transform:translateY(0) scale(.98)}
.upd-install-btn:disabled{opacity:.6;cursor:not-allowed;transform:none}

.upd-progress-card{background:var(--card);border:1px solid var(--card-b);border-radius:18px;padding:18px 20px;margin-bottom:16px;box-shadow:var(--shadow)}
.upd-progress-head{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.upd-progress-icon{width:38px;height:38px;border-radius:11px;background:var(--accent-d);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.upd-progress-title{font-size:13px;font-weight:800;color:var(--t1)}
.upd-progress-txt{font-size:10.5px;color:var(--t3);margin-top:2px}
.upd-progress-pct{font-size:16px;font-weight:800;color:var(--accent2);flex-shrink:0}
.upd-progress-track{height:8px;border-radius:6px;background:var(--accent-d);overflow:hidden}
.upd-progress-fill{height:100%;border-radius:6px;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .4s ease;position:relative;overflow:hidden}
.upd-progress-fill::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.4),transparent);width:40%;animation:shimmer 1.6s linear infinite}

.upd-log-card{background:var(--card);border:1px solid var(--card-b);border-radius:18px;padding:18px 20px;margin-bottom:20px;box-shadow:var(--shadow)}
.upd-log-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.upd-log-title{font-size:12.5px;font-weight:800;color:var(--t1);display:flex;align-items:center;gap:7px}
.upd-log-title i{color:var(--accent);font-size:16px}
.upd-log-box{background:rgba(0,0,0,.3);border:1px solid var(--card-b);border-radius:12px;padding:14px 16px;max-height:240px;overflow-y:auto;font-family:ui-monospace,monospace;font-size:10.5px;line-height:2}
[data-theme="light"] .upd-log-box{background:rgba(0,0,0,.03)}
.upd-log-empty{color:var(--t3)}
.upd-log-line{color:var(--t2);white-space:pre-wrap;word-break:break-all}
.upd-log-line.err{color:var(--red-t)}
.upd-log-line.ok{color:var(--green-t)}

.upd-history-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.upd-history-title{font-size:13px;font-weight:800;color:var(--t1);display:flex;align-items:center;gap:7px}
.upd-history-title i{color:var(--accent);font-size:17px}

.upd-timeline{position:relative;display:flex;flex-direction:column;gap:0}
.upd-timeline::before{content:'';position:absolute;top:8px;bottom:8px;right:19px;width:2px;background:linear-gradient(180deg,var(--card-b),transparent)}
.upd-item{display:flex;gap:16px;padding:0 0 20px;position:relative}
.upd-item:last-child{padding-bottom:0}
.upd-item-dot-wrap{position:relative;z-index:1;flex-shrink:0}
.upd-item-dot{width:40px;height:40px;border-radius:13px;background:var(--card);border:2px solid var(--green);display:flex;align-items:center;justify-content:center;color:var(--green-t);font-size:17px;box-shadow:var(--shadow)}
.upd-item.err .upd-item-dot{border-color:var(--red);color:var(--red-t)}
.upd-item-card{flex:1;background:var(--card);border:1px solid var(--card-b);border-radius:16px;padding:14px 17px;transition:.18s;min-width:0}
.upd-item-card:hover{border-color:var(--card-bh);transform:translateY(-1px)}
.upd-item-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.upd-item-versions{font-size:13.5px;font-weight:800;color:var(--t1);display:flex;align-items:center;gap:8px}
.upd-item-versions .arrow{color:var(--t3);font-size:14px}
.upd-item-versions .to{color:var(--accent2)}
.upd-item-time{font-size:10px;color:var(--t3);display:flex;align-items:center;gap:5px;white-space:nowrap}
.upd-item-desc{font-size:11.5px;color:var(--t2);line-height:1.8;margin-top:6px}
.upd-item-badge{font-size:9px;font-weight:800;padding:3px 9px;border-radius:20px;flex-shrink:0}
.upd-item-badge.ok{background:var(--green-bg);color:var(--green-t)}
.upd-item-badge.err{background:var(--red-bg);color:var(--red-t)}
.upd-item-err-box{margin-top:8px;background:var(--red-bg);border:1px solid rgba(239,68,68,.2);border-radius:9px;padding:8px 11px;font-size:10.5px;color:var(--red-t);font-family:ui-monospace,monospace;word-break:break-all}
.upd-history-empty{text-align:center;padding:50px 20px;color:var(--t3);background:var(--card);border:1px dashed var(--card-b);border-radius:18px}
.upd-history-empty i{font-size:36px;opacity:.35;margin-bottom:10px;display:block}

/* ══════ پشتیبانی کاربر — ری‌دیزاین ══════ */
.sup-wrap{max-width:1450px;background:var(--card);border:1px solid var(--card-b);border-radius:24px;overflow:hidden;box-shadow:var(--shadow);position:relative}
.sup-wrap::before{content:'';position:absolute;top:-60px;left:-60px;width:200px;height:200px;background:radial-gradient(circle,var(--accent-d),transparent 70%);pointer-events:none;z-index:0}
.sup-head{display:flex;align-items:center;gap:13px;padding:18px 22px;border-bottom:1px solid var(--card-b);background:linear-gradient(155deg,var(--accent-d) 0%,transparent 75%);position:relative;z-index:1}
.sup-head-icon{width:42px;height:42px;border-radius:13px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;color:#fff;font-size:19px;flex-shrink:0;box-shadow:0 6px 16px rgba(139,92,246,.35);position:relative}
.sup-head-icon::after{content:'';position:absolute;inset:-5px;border-radius:16px;border:1.5px solid var(--accent);opacity:.4;animation:supBreathe 2.4s ease-in-out infinite}
@keyframes supBreathe{0%,100%{transform:scale(1);opacity:.4}50%{transform:scale(1.1);opacity:0}}
.sup-head-text{flex:1;min-width:0}
.sup-head-title{font-size:14.5px;font-weight:800;color:var(--t1);letter-spacing:-.01em}
.sup-head-sub{font-size:10.5px;color:var(--t3);margin-top:3px;display:flex;align-items:center;gap:6px}
.sup-head-sub .sdot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 1.6s infinite;flex-shrink:0}
.sup-close-btn{background:var(--red-bg);color:var(--red-t);border:1px solid rgba(239,68,68,.2);border-radius:10px;padding:8px 14px;font-family:inherit;font-size:11px;font-weight:700;cursor:pointer;display:flex;align-items:center;gap:6px;transition:.15s}
.sup-close-btn:hover{background:rgba(239,68,68,.2);transform:translateY(-1px)}
.sup-blocked-banner{background:var(--red-bg);color:var(--red-t);font-size:11.5px;font-weight:700;padding:11px 22px;display:flex;align-items:center;gap:8px;border-bottom:1px solid var(--card-b);position:relative;z-index:1}
 
#support-msgs{height:370px;overflow-y:auto;display:flex;flex-direction:column;gap:2px;padding:20px;background:var(--bg2);position:relative;z-index:1;scroll-behavior:smooth}
#support-msgs::-webkit-scrollbar{width:5px}
#support-msgs::-webkit-scrollbar-thumb{background:var(--card-b);border-radius:3px}
 
.sup-date-sep{text-align:center;font-size:9.5px;color:var(--t3);font-weight:700;margin:14px 0 10px;position:relative}
.sup-date-sep span{background:var(--bg2);padding:0 12px;position:relative;z-index:1}
.sup-date-sep::before{content:'';position:absolute;top:50%;right:0;left:0;height:1px;background:var(--card-b);z-index:0}
 
.sup-msg-row{display:flex;align-items:flex-end;gap:8px;margin-bottom:10px;max-width:100%}
.sup-msg-row.client{margin-right:0;margin-left:auto;flex-direction:row-reverse}
.sup-msg-row.admin{margin-left:0; display: flex; justify-content: left}
.sup-avatar{width:26px;height:26px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;margin-bottom:2px}
.sup-avatar.admin{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff}
.sup-avatar.client{background:var(--purple-bg);color:var(--purple)}
.sup-msg{padding:10px 15px;border-radius:16px;font-size:12.8px;line-height:1.75;word-break:break-word;position:relative;box-shadow:0 1px 2px rgba(0,0,0,.06)}
.sup-msg.client{background:var(--accent);color:#fff;border-bottom-right-radius:5px}
.sup-msg.admin{background:var(--card);color:var(--t1);border:1px solid var(--card-b);border-bottom-left-radius:5px}
.sup-msg .sup-time{display:flex;align-items:center;gap:4px;font-size:9px;opacity:.68;margin-top:5px;justify-content:flex-end}
.sup-msg .sup-time i{font-size:12px}
.sup-msg.client .sup-time i.seen{color:#fff}
 
.sup-empty{color:var(--t3);font-size:12px;text-align:center;padding:60px 20px;display:flex;flex-direction:column;align-items:center;gap:12px}
.sup-empty i{font-size:38px;opacity:.35}
.sup-empty b{color:var(--t2);font-size:13px;font-weight:700}
 
.sup-input-row{display:flex;gap:10px;padding:16px 18px;background:var(--card);border-top:1px solid var(--card-b);position:relative;z-index:1}
.sup-input-row input{margin-bottom:0;border-radius:13px;padding:12px 16px}
.sup-input-row button{border-radius:13px;padding:0 18px;display:flex;align-items:center;justify-content:center}
.sup-input-row.disabled{opacity:.55;pointer-events:none}
 
.sup-new-badge{display:inline-flex;align-items:center;gap:4px;background:var(--red);color:#fff;font-size:9px;font-weight:800;padding:2px 8px;border-radius:20px;margin-right:6px;animation:pulse 1.6s infinite}

/* ══════ مودال ساخت کانفیگ - نسخه حرفه‌ای ══════ */
.cm-modal{max-width:620px;width:calc(100% - 32px);padding:0;border-radius:24px;overflow:hidden;
  max-height:92vh;display:flex;flex-direction:column}
/* مودال‌هایی که به‌جای cm-head/cm-body از ساختار modal-v2-head/modal-v2-body استفاده می‌کنند
   هم باید داخل cm-modal درست اسکرول شوند و هدرشان فشرده/همپوشان نشود */
.cm-modal.modal-v2 .modal-v2-head{flex-shrink:0}
.cm-modal.modal-v2 .modal-v2-body{flex:1;overflow-y:auto;min-height:0}
.cm-head{background:linear-gradient(155deg,rgba(139,92,246,.14) 0%,transparent 70%);
  padding:26px 28px 20px;position:relative;border-bottom:1px solid var(--card-b);flex-shrink:0}
.cm-head::before{content:'';position:absolute;top:-60px;left:-60px;width:200px;height:200px;
  background:radial-gradient(circle,rgba(139,92,246,.18),transparent 70%);pointer-events:none}
.cm-head-row{display:flex;align-items:center;gap:14px;position:relative;z-index:1}
.cm-head-icon{width:46px;height:46px;border-radius:14px;background:linear-gradient(135deg,var(--accent),var(--accent2));
  display:flex;align-items:center;justify-content:center;color:#fff;font-size:21px;flex-shrink:0;
  box-shadow:0 8px 20px rgba(139,92,246,.35)}
.cm-head-title{font-size:16.5px;font-weight:800;color:var(--t1);letter-spacing:-.01em}
.cm-head-sub{font-size:11px;color:var(--t3);margin-top:3px}
.cm-close{position:absolute;top:18px;left:18px;background:rgba(0,0,0,.18);border:1px solid var(--card-b);
  color:var(--t2);width:32px;height:32px;border-radius:10px;font-size:15px;display:flex;align-items:center;
  justify-content:center;cursor:pointer;z-index:2;transition:.15s}
.cm-close:hover{background:var(--red-bg);color:var(--red-t);border-color:rgba(239,68,68,.25)}

.cm-body{padding:22px 28px 8px;overflow-y:auto;flex:1}
.cm-section{margin-bottom:20px}
.cm-section-label{font-size:10.5px;font-weight:800;color:var(--t3);text-transform:uppercase;
  letter-spacing:.08em;display:flex;align-items:center;gap:6px;margin-bottom:10px}
.cm-section-label i{color:var(--accent);font-size:14px}

.cm-field{margin-bottom:14px}
.cm-field label{display:block;font-size:11px;font-weight:700;color:var(--t2);margin-bottom:7px}
.cm-input{width:100%;padding:11px 14px;border-radius:11px;border:1px solid var(--card-b);
  background:rgba(0,0,0,.18);color:var(--t1);font-family:inherit;font-size:12.8px;outline:none;transition:.15s}
[data-theme="light"] .cm-input{background:rgba(124,58,237,.03)}
.cm-input:focus{border-color:rgba(139,92,246,.5);box-shadow:0 0 0 3px rgba(139,92,246,.1)}
.cm-input::placeholder{color:var(--t3)}
.cm-row2{display:grid;grid-template-columns:1fr 1fr;gap:12px}

/* ── آکاردئون کشویی انتخاب پروتکل / ترابرد ── */
.cm-dd{border:1px solid var(--card-b);border-radius:14px;overflow:hidden;background:rgba(0,0,0,.1);transition:.18s}
[data-theme="light"] .cm-dd{background:#fff}
.cm-dd.open{border-color:var(--card-bh);box-shadow:0 0 0 3px rgba(139,92,246,.08)}
.cm-dd-trigger{display:flex;align-items:center;gap:12px;padding:13px 15px;cursor:pointer;user-select:none}
.cm-dd-icon{width:38px;height:38px;border-radius:11px;background:var(--accent-d);color:var(--accent);
  display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;transition:.18s}
.cm-dd-text{flex:1;min-width:0}
.cm-dd-title{font-size:13px;font-weight:800;color:var(--t1)}
.cm-dd-desc{font-size:10px;color:var(--t3);margin-top:2px}
.cm-dd-chev{color:var(--t3);font-size:16px;transition:transform .2s;flex-shrink:0}
.cm-dd.open .cm-dd-chev{transform:rotate(180deg);color:var(--accent)}

.cm-dd-panel{display:grid;grid-template-rows:0fr;transition:grid-template-rows .22s ease}
.cm-dd.open .cm-dd-panel{grid-template-rows:1fr}
.cm-dd-panel-inner{overflow:hidden}
.cm-dd-list{border-top:1px solid var(--card-b);padding:6px}
.cm-opt{display:flex;align-items:center;gap:11px;padding:10px 11px;border-radius:10px;cursor:pointer;transition:.14s;margin-bottom:2px}
.cm-opt:hover{background:var(--accent-d)}
.cm-opt.sel{background:rgba(139,92,246,.12)}
.cm-opt-radio{width:18px;height:18px;border-radius:50%;border:2px solid var(--card-b);flex-shrink:0;
  display:flex;align-items:center;justify-content:center;transition:.14s}
.cm-opt.sel .cm-opt-radio{border-color:var(--accent)}
.cm-opt-radio::after{content:'';width:9px;height:9px;border-radius:50%;background:var(--accent);
  transform:scale(0);transition:.14s}
.cm-opt.sel .cm-opt-radio::after{transform:scale(1)}
.cm-opt-icon{width:30px;height:30px;border-radius:9px;background:var(--accent-d);color:var(--accent);
  display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0}
.cm-opt.sel .cm-opt-icon{background:var(--accent);color:#fff}
.cm-opt-text{flex:1;min-width:0}
.cm-opt-title{font-size:12px;font-weight:700;color:var(--t1)}
.cm-opt-desc{font-size:9.5px;color:var(--t3);margin-top:1px}
.cm-opt-tag{font-size:8.5px;font-weight:800;padding:2px 7px;border-radius:6px;background:var(--green-bg);
  color:var(--green-t);flex-shrink:0}

.cm-pills{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
.cm-pill{padding:6px 13px;border-radius:20px;font-size:10.5px;font-weight:700;color:var(--t2);
  background:transparent;border:1px solid var(--card-b);cursor:pointer;transition:.15s;font-family:inherit}
.cm-pill:hover{background:var(--accent-d)}
.cm-pill.active{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 3px 10px rgba(139,92,246,.3)}

.cm-note{font-size:10.5px;color:var(--t3);display:flex;align-items:flex-start;gap:7px;
  background:var(--accent-d);border-radius:10px;padding:10px 13px;line-height:1.7;margin-top:4px}
.cm-note i{color:var(--accent);font-size:14px;flex-shrink:0;margin-top:1px}

.cm-footer{display:flex;gap:10px;padding:16px 28px;border-top:1px solid var(--card-b);flex-shrink:0;
  background:var(--card)}

/* ── تم اختصاصی فیروزه‌ای برای مودال Bot TCP Proxy (تمایز بصری از بقیه مودال‌ها) ── */
#modal-bot-tcp-proxy .cm-head{background:linear-gradient(155deg,rgba(139,92,246,.16) 0%,transparent 70%)}
#modal-bot-tcp-proxy .cm-head::before{background:radial-gradient(circle,rgba(139,92,246,.2),transparent 70%)}
#modal-bot-tcp-proxy .cm-head-icon{background:linear-gradient(135deg,#14b8a6,#0d9488);box-shadow:0 8px 20px rgba(139,92,246,.35)}
#modal-bot-tcp-proxy .cm-section-label i{color:#14b8a6}
#modal-bot-tcp-proxy .cm-pill.active{background:#14b8a6;border-color:#14b8a6;box-shadow:0 3px 10px rgba(139,92,246,.3)}
#modal-bot-tcp-proxy .cm-input:focus{border-color:rgba(139,92,246,.5);box-shadow:0 0 0 3px rgba(139,92,246,.1)}
#modal-bot-tcp-proxy #btp-status-note{background:var(--accent-d);border:1px solid var(--card-b);border-radius:12px;padding:12px 14px;transition:.2s}
#modal-bot-tcp-proxy #btp-status-note.st-run{background:rgba(139,92,246,.1);border-color:rgba(139,92,246,.3)}
#modal-bot-tcp-proxy #btp-status-note.st-run #btp-status-icon{color:#14b8a6}
#modal-bot-tcp-proxy #btp-status-note.st-ok{background:var(--green-bg);border-color:rgba(34,197,94,.3)}
#modal-bot-tcp-proxy #btp-status-note.st-ok #btp-status-icon{color:var(--green-t)}
#modal-bot-tcp-proxy #btp-status-note.st-err{background:var(--red-bg);border-color:rgba(239,68,68,.3)}
#modal-bot-tcp-proxy #btp-status-note.st-err #btp-status-icon{color:var(--red-t)}
#modal-bot-tcp-proxy #btp-status-note.st-warn{background:var(--amber-bg);border-color:rgba(245,158,11,.3)}
#modal-bot-tcp-proxy #btp-status-note.st-warn #btp-status-icon{color:var(--amber-t)}
#modal-bot-tcp-proxy #btp-status-text{color:var(--t1);font-weight:600}
#modal-bot-tcp-proxy #btp-ping-status-note{background:var(--accent-d);border:1px solid var(--card-b);border-radius:12px;padding:12px 14px;transition:.2s}
#modal-bot-tcp-proxy #btp-ping-status-note.st-run{background:rgba(139,92,246,.1);border-color:rgba(139,92,246,.3)}
#modal-bot-tcp-proxy #btp-ping-status-note.st-run #btp-ping-status-icon{color:#14b8a6}
#modal-bot-tcp-proxy #btp-ping-status-note.st-ok{background:var(--green-bg);border-color:rgba(34,197,94,.3)}
#modal-bot-tcp-proxy #btp-ping-status-note.st-ok #btp-ping-status-icon{color:var(--green-t)}
#modal-bot-tcp-proxy #btp-ping-status-note.st-err{background:var(--red-bg);border-color:rgba(239,68,68,.3)}
#modal-bot-tcp-proxy #btp-ping-status-note.st-err #btp-ping-status-icon{color:var(--red-t)}
#modal-bot-tcp-proxy #btp-ping-status-text{color:var(--t1);font-weight:600}
.cm-btn-cancel{flex:.55;justify-content:center;padding:12px;border-radius:12px;background:transparent;
  border:1px solid var(--card-b);color:var(--t2);font-family:inherit;font-size:12.5px;font-weight:700;
  cursor:pointer;transition:.15s;display:flex;align-items:center}
.cm-btn-cancel:hover{background:var(--accent-d);color:var(--t1)}
.cm-btn-submit{flex:1;justify-content:center;padding:12px;border-radius:12px;
  background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;border:none;
  font-family:inherit;font-size:13px;font-weight:800;cursor:pointer;display:flex;align-items:center;
  gap:7px;box-shadow:0 6px 18px rgba(139,92,246,.4);transition:.18s}
.cm-btn-submit:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(139,92,246,.5)}
.cm-btn-submit:active{transform:translateY(0) scale(.98)}

/* دسکتاپ بزرگ‌تر */
@media(min-width:900px){
  .cm-modal{max-width:680px}
  .cm-body{padding:24px 34px 8px}
  .cm-head{padding:28px 34px 22px}
  .cm-footer{padding:18px 34px}
  #modal-bot-tcp-proxy .cm-modal{max-width:560px}
}

/* موبایل = باتم‌شیت */
@media(max-width:640px){
  #modal-create-link.modal-bg{align-items:flex-end}
  .cm-modal{max-width:100%;width:100%;border-radius:22px 22px 0 0;max-height:90vh;
    animation:cmSlideUp .28s cubic-bezier(.32,.72,0,1)}
  .cm-row2{grid-template-columns:1fr}
  .cm-head{padding:20px 18px 16px}
  .cm-body{padding:18px 18px 6px}
  .cm-footer{padding:14px 18px 18px}
}
@keyframes cmSlideUp{from{transform:translateY(100%)}to{transform:translateY(0)}}

</style>
<style>
/* ═══════════════════════════════════════════════════════════════
   EMIX — Glass Redesign (neon red/orange glassmorphism)
   اين لايه فقط استايل را عوض مي‌كند؛ تمام IDها و هوك‌هاي JS دست‌نخورده‌اند
   ═══════════════════════════════════════════════════════════════ */
html{background:var(--bg)}
body{background:transparent}
body::before{
  content:'';position:fixed;inset:0;z-index:-2;pointer-events:none;
  background:
    radial-gradient(ellipse 52% 42% at 12% 6%,rgba(139,92,246,.15),transparent 66%),
    radial-gradient(ellipse 46% 40% at 92% 90%,rgba(168,85,247,.12),transparent 63%),
    radial-gradient(ellipse 34% 30% at 78% 12%,rgba(202,138,4,.08),transparent 62%),
    var(--bg);
  transition:background .3s;
}
body::after{
  content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.55;
  background-image:
    linear-gradient(rgba(139,92,246,0.035) 1px,transparent 1px),
    linear-gradient(90deg,rgba(139,92,246,0.035) 1px,transparent 1px);
  background-size:46px 46px;
  mask-image:radial-gradient(ellipse 72% 72% at 50% 38%,black 18%,transparent 90%);
}
[data-theme="light"] body::before{
  background:
    radial-gradient(ellipse 52% 42% at 12% 6%,rgba(124,58,237,.10),transparent 66%),
    radial-gradient(ellipse 46% 40% at 92% 90%,rgba(202,138,4,.07),transparent 63%),
    var(--bg);
}
[data-theme="light"] body::after{opacity:.4}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(139,92,246,.35);border-radius:3px}

/* ── سايدبار شيشه‌اي با هاله‌ي نئوني ── */
.sidebar{background:rgba(15,12,20,0.66);backdrop-filter:blur(26px);-webkit-backdrop-filter:blur(26px);border-left:1px solid rgba(139,92,246,.16);box-shadow:0 0 46px -20px rgba(139,92,246,.4)}
[data-theme="light"] .sidebar{background:rgba(255,255,255,0.7);box-shadow:0 0 46px -22px rgba(124,58,237,.25)}
.logo{border-bottom-color:rgba(139,92,246,.12)}
.logo-img{border-color:rgba(139,92,246,.35);box-shadow:0 0 18px -2px rgba(139,92,246,.5)}
.logo-sub,.nav-sec{color:#7E5F56}
.nav-it{border-radius:11px;margin:1px 10px;padding:9px 12px}
.nav-it:hover{background:rgba(139,92,246,.10);color:#E8C9C0}
.nav-it.on{background:linear-gradient(135deg,rgba(139,92,246,.24),rgba(202,138,4,.10));color:#fff;border-right:2px solid #8B5CF6;box-shadow:0 0 22px -6px rgba(139,92,246,.55),inset 0 0 0 1px rgba(139,92,246,.28)}
[data-theme="light"] .nav-it.on{background:linear-gradient(135deg,rgba(124,58,237,.16),rgba(202,138,4,.06));color:#B23A1C;box-shadow:inset 0 0 0 1px rgba(124,58,237,.22)}
.nav-badge{background:rgba(139,92,246,.2);color:#FFB199}
.sb-foot{border-top-color:rgba(139,92,246,.12)}
.mob-top{background:rgba(15,12,20,0.8);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid rgba(139,92,246,.15)}
[data-theme="light"] .mob-top{background:rgba(255,255,255,0.82)}
.menu-btn,.theme-mob,.sb-close{background:rgba(139,92,246,.10);border-color:rgba(139,92,246,.2);color:#D9A99B}

/* ── سطوح شيشه‌اي ── */
.card,.metric,.traf-mini,.traf-chart-card,.vless-box,.conn-hero,.srv-panel,.pw-panel,.node-hero,.sup-wrap,.links-bulkbar{
  background:rgba(22,18,28,0.55);
  backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);
  border:1px solid rgba(255,255,255,0.07);
  box-shadow:0 18px 50px -24px rgba(0,0,0,.65),inset 0 1px 0 rgba(255,255,255,.05);
}
[data-theme="light"] .card,[data-theme="light"] .metric,[data-theme="light"] .traf-mini,[data-theme="light"] .traf-chart-card,[data-theme="light"] .vless-box,[data-theme="light"] .conn-hero,[data-theme="light"] .srv-panel,[data-theme="light"] .pw-panel,[data-theme="light"] .node-hero,[data-theme="light"] .sup-wrap,[data-theme="light"] .links-bulkbar{background:rgba(255,255,255,0.78)}
.card:hover,.metric:hover,.traf-mini:hover{border-color:rgba(139,92,246,.35);box-shadow:0 18px 50px -24px rgba(0,0,0,.65),0 0 30px -12px rgba(139,92,246,.35),inset 0 1px 0 rgba(255,255,255,.05)}
.metric::after{background:linear-gradient(180deg,#8B5CF6,#E8590C)}
.traf-main-stat{background:linear-gradient(155deg,rgba(30,22,34,0.8) 0%,rgba(20,20,28,0.55) 60%);backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px)}
.traf-main-stat::before{background:radial-gradient(circle,rgba(139,92,246,.18),transparent 70%)}
.m-icon,.traf-mini-icon,.cp-head-icon,.mob-logo,.srv-tile-icon,.node-metric-icon{background:rgba(139,92,246,.12);color:#FF7A4D}
.traf-mini-icon.pk{background:rgba(202,138,4,.14);color:#FACC15}
.traf-mini-icon.lo{background:rgba(168,85,247,.12);color:#FFB199}
.metric.suc::after{background:linear-gradient(180deg,#10B981,#059669)}
.metric.dan::after{background:linear-gradient(180deg,#EF4444,#B91C1C)}

/* ── دكمه‌هاي قرصي قرمز-نارنجي ── */
.btn-p{background:linear-gradient(135deg,#8B5CF6,#FACC15);border-radius:999px;border:none;box-shadow:0 6px 22px -6px rgba(139,92,246,.55);color:#fff}
.btn-p:hover{background:linear-gradient(135deg,#FF5C3F,#FF9A55);box-shadow:0 10px 28px -6px rgba(139,92,246,.7);color:#fff}
.btn-o{border-radius:999px}
.btn-g{background:rgba(139,92,246,.12);color:#FFB199;border:1px solid rgba(139,92,246,.25);border-radius:999px}
.btn-g:hover{background:rgba(139,92,246,.22);color:#FFD1C2}
.btn-pur{background:rgba(168,85,247,.12);color:#FFB199;border:1px solid rgba(168,85,247,.28);border-radius:999px}
.btn-pur:hover{background:rgba(168,85,247,.22)}
.btn-sm{border-radius:999px}
.btn-icon{border-radius:999px}
.chip{border-radius:999px;border-color:rgba(139,92,246,.22)}
.chip.active{background:linear-gradient(135deg,#8B5CF6,#FACC15);border-color:#8B5CF6;color:#fff;box-shadow:0 4px 14px -3px rgba(139,92,246,.55)}
.cp-submit-btn,.modal-v2-btn-submit{background:linear-gradient(135deg,#8B5CF6,#FACC15);border-radius:999px;box-shadow:0 6px 20px -6px rgba(139,92,246,.5)}
.cp-submit-btn:hover,.modal-v2-btn-submit:hover{box-shadow:0 10px 26px -6px rgba(139,92,246,.6)}
.pw-submit{background:linear-gradient(135deg,#8B5CF6,#FACC15);border-radius:999px;box-shadow:0 6px 20px -6px rgba(139,92,246,.5)}
.pw-submit:hover{box-shadow:0 10px 24px -6px rgba(139,92,246,.6)}

/* ── نوارهاي پيشرفت: گراديان نارنجي→قرمز ── */
.spbar,.ubar{background:rgba(139,92,246,.14)}
.spfill,.ubar-f{background:linear-gradient(90deg,#FACC15,#8B5CF6)}
.upd-progress-track{background:rgba(139,92,246,.14)}
.upd-progress-fill{background:linear-gradient(90deg,#FACC15,#8B5CF6)}
.tog{background:rgba(168,85,247,.28)}
.tog.on{background:linear-gradient(135deg,#8B5CF6,#FACC15)}
.traf-range-tab.on{background:linear-gradient(135deg,#8B5CF6,#FACC15);box-shadow:0 2px 10px -2px rgba(139,92,246,.5)}

/* ── كارتهاي انتخاب پروتكل/ترنسپورت ── */
.proto-base-card.active,.proto-t-card.active,.proto-card.active,.fp-card.active,.alpn-chip.active{
  border-color:#8B5CF6;background:rgba(139,92,246,.12);box-shadow:0 0 0 3px rgba(139,92,246,.12),0 0 18px -6px rgba(139,92,246,.4)
}
.proto-base-card.active .proto-base-icon,.proto-t-card.active .proto-t-icon,.proto-card.active .proto-icon,.fp-card.active .fp-card-icon{background:linear-gradient(135deg,#8B5CF6,#FACC15);color:#fff}
.proto-tab.active{border-color:#8B5CF6;background:rgba(139,92,246,.12);color:#FFB199;box-shadow:0 0 0 3px rgba(139,92,246,.1)}
.fp-card-icon,.proto-base-icon,.proto-t-icon{background:rgba(139,92,246,.12);color:#FF7A4D}
.fi:focus,.fs:focus{border-color:rgba(139,92,246,.5);background:rgba(0,0,0,.25);box-shadow:0 0 0 3px rgba(139,92,246,.12)}
.cp-input-full:focus{border-color:rgba(139,92,246,.5);box-shadow:0 0 0 3px rgba(139,92,246,.12)}

/* ── پنلها و مودال‌ها ── */
.create-panel{background:linear-gradient(155deg,rgba(28,20,32,0.85) 0%,rgba(20,20,28,0.6) 55%);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border-color:rgba(139,92,246,.16)}
[data-theme="light"] .create-panel{background:linear-gradient(155deg,rgba(255,255,255,0.9) 0%,rgba(255,255,255,0.72) 55%)}
.cp-block,.fi,.fs,.cp-input-full,.vl-code{background:rgba(0,0,0,.22)}
[data-theme="light"] .cp-block{background:rgba(124,58,237,.03)}
.cp-head-icon{background:linear-gradient(135deg,#8B5CF6,#FACC15);box-shadow:0 6px 20px -4px rgba(139,92,246,.5)}
.modal-v2,.cm-modal{background:rgba(20,20,28,0.85);backdrop-filter:blur(26px);-webkit-backdrop-filter:blur(26px);border:1px solid rgba(139,92,246,.18)}
[data-theme="light"] .modal-v2,[data-theme="light"] .cm-modal{background:rgba(255,255,255,0.94)}
.modal-bg{backdrop-filter:blur(6px)}
.modal-v2-icon,.cm-head-icon{background:linear-gradient(135deg,#8B5CF6,#FACC15);box-shadow:0 6px 20px -4px rgba(139,92,246,.5)}
.cm-close,.modal-v2-close{background:rgba(139,92,246,.12);color:#D9A99B;border-color:rgba(139,92,246,.2)}

/* ── سربرگ و جعبه‌ي VLESS ── */
.tb-title{color:#FFF}
.tb-title i{color:#FF6A45;text-shadow:0 0 14px rgba(139,92,246,.6)}
.tb-sub{color:#8A6A60}
.vless-box{background:linear-gradient(135deg,rgba(28,20,32,0.85) 0%,rgba(16,13,21,0.6) 100%);border-color:rgba(139,92,246,.16)}
.vless-box::before{background:radial-gradient(circle,rgba(139,92,246,.2),transparent 70%)}
.vl-title i{color:#FF6A45}
.vl-code{color:#FFB199;border-color:rgba(139,92,246,.16)}
.badge.bg-blue,.badge.bg-purple{background:rgba(139,92,246,.12);color:#FFB199}
.badge.bg-amber{background:rgba(202,138,4,.14);color:#FFC06B}
.cl{background:rgba(139,92,246,.08);border-color:rgba(139,92,246,.2)}
.cl i{color:#FF6A45}
.sub-url,.df-link{color:#FFB199;border-color:rgba(139,92,246,.2);background:rgba(139,92,246,.07)}

/* ── هدرهاي كارت و سكشن‌ها ── */
.card-title i{color:#FF6A45}
.conn-hero-title,.srv-hero-title,.node-hero-title{color:#FFF}
.srv-hero-domain{color:#FFB199}
.info-item-val{color:#FFD1C2}

/* Responsive hardening: no horizontal bleed, correct mobile drawer */
html,body{max-width:100%;overflow-x:hidden}
@media(max-width:1050px){
  .sidebar{transform:translateX(calc(100% + 60px)) !important}
  .sidebar.open{transform:translateX(0) !important;box-shadow:-10px 0 44px rgba(0,0,0,.5),0 0 46px -20px rgba(139,92,246,.4)}
  .topbar .tb-title{font-size:16px}
}
.log-timeline i{color:#FF6A45}

/* ═══════════════════════════════════════════════════════════════════════════
   NixHD Signature Touches — dot-matrix indicators + premium gradient cards
   ═══════════════════════════════════════════════════════════════════════════ */
.dot-matrix{display:flex;gap:3px;flex-wrap:wrap;padding:8px 0}
.dot-matrix .d{width:6px;height:6px;border-radius:50%;background:var(--dot-off);transition:background .2s,box-shadow .2s}
.dot-matrix .d.on{background:var(--dot-on);box-shadow:0 0 6px var(--accent-glow)}
.dot-matrix .d.warn{background:var(--amber);box-shadow:0 0 6px var(--amber-bg)}
.dot-matrix .d.off{background:var(--red);box-shadow:0 0 6px var(--red-bg)}

/* Premium gradient card — for hero metrics + best-link displays */
.card-vy{background:var(--grad-vy);color:#0A0A0F;border:none;box-shadow:0 12px 36px rgba(139,92,246,0.32),0 4px 12px rgba(250,204,21,0.20)}
.card-vy .vy-eyebrow{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;opacity:.7}
.card-vy .vy-num{font-size:42px;font-weight:800;letter-spacing:-.03em;line-height:1}
.card-vy .vy-label{font-size:12px;opacity:.75;margin-top:4px}

/* Glow pulse for active nav items */
.nav-it.on{box-shadow:inset 0 1px 0 rgba(255,255,255,0.04),0 0 18px rgba(139,92,246,0.18)}
.nav-it.on i{text-shadow:0 0 12px var(--accent-glow)}

/* Premium metric card with violet left edge */
.metric{position:relative;overflow:hidden}
.metric::before{content:'';position:absolute;top:0;right:0;width:100%;height:2px;background:linear-gradient(90deg,transparent,var(--accent-violet),var(--accent2),transparent);opacity:.6;transition:opacity .25s}
.metric:hover::before{opacity:1}

/* Buttons — NixHD feel: violet base, yellow glow */
.btn-g{position:relative;overflow:hidden;transition:transform .2s,box-shadow .2s,filter .2s}
.btn-g::after{content:'';position:absolute;inset:0;background:linear-gradient(135deg,transparent 0%,rgba(250,204,21,0.18) 50%,transparent 100%);opacity:0;transition:opacity .25s;pointer-events:none}
.btn-g:hover::after{opacity:1}
.btn-g:hover{transform:translateY(-1px);box-shadow:0 8px 24px var(--accent-glow),0 0 0 1px var(--accent-violet)}

/* Inputs — NixHD glass inputs with violet focus ring */
input:focus,select:focus,textarea:focus{border-color:var(--accent-violet) !important;background:rgba(139,92,246,0.06) !important;box-shadow:0 0 0 4px var(--accent-glow) !important}

/* Sidebar — slightly darker for depth, with subtle violet edge */
.sidebar{background:rgba(10,10,15,0.92) !important;border-left-color:rgba(139,92,246,0.12) !important}
[data-theme="light"] .sidebar{background:rgba(255,255,255,0.92) !important}
.mob-top{background:rgba(10,10,15,0.92) !important;border-bottom-color:rgba(139,92,246,0.12) !important}
[data-theme="light"] .mob-top{background:rgba(255,255,255,0.92) !important}

/* Premium card hover — violet glow + slight lift */
.card:hover{border-color:rgba(139,92,246,0.28) !important;box-shadow:0 24px 64px -16px rgba(0,0,0,0.6),0 0 0 1px rgba(139,92,246,0.18) inset,0 0 32px -8px var(--accent-glow) !important}

/* Status badges — pill shape with glow */
.badge{box-shadow:0 0 0 1px rgba(139,92,246,0.08) inset}
.badge.ok{box-shadow:0 0 0 1px rgba(34,197,94,0.18) inset,0 0 12px rgba(34,197,94,0.18)}
.badge.err{box-shadow:0 0 0 1px rgba(239,68,68,0.18) inset,0 0 12px rgba(239,68,68,0.18)}

/* VPN Pro cards — distinct violet/yellow accent */
.vpn-card{position:relative;overflow:hidden}
.vpn-card::after{content:'';position:absolute;top:0;right:0;width:120px;height:120px;background:radial-gradient(circle at top right,var(--accent-glow),transparent 70%);pointer-events:none;opacity:.6}
.vpn-wg-card::after{background:radial-gradient(circle at top right,rgba(139,92,246,0.20),transparent 70%)}
.vpn-ovpn-card::after{background:radial-gradient(circle at top right,rgba(250,204,21,0.20),transparent 70%)}

/* VPN Pro inputs — login-page style (icon + wiggle on focus) */
.vpn-field{display:flex;flex-direction:column}
.vpn-field>label{font-size:10.5px;font-weight:700;color:var(--t2);margin-bottom:7px;text-transform:uppercase;letter-spacing:.06em;display:flex;align-items:center;gap:6px}
.vpn-input-wrap{position:relative;display:flex;align-items:center}
.vpn-input-ic{position:absolute;right:11px;top:50%;transform:translateY(-50%);color:var(--t3);font-size:15px;pointer-events:none;transition:color .2s,transform .2s;z-index:1}
.vpn-input{
  width:100%;padding:12px 38px 12px 14px;border-radius:12px;border:1px solid var(--card-b);
  background:rgba(0,0,0,.22);color:var(--t1);font-family:'Vazirmatn',ui-monospace,monospace;font-size:12.5px;
  outline:none;transition:border-color .2s,background .2s,box-shadow .2s;direction:ltr;text-align:left;
}
[data-theme="light"] .vpn-input{background:rgba(139,92,246,.04)}
.vpn-input::placeholder{color:var(--t3);opacity:.7}
.vpn-input:focus{border-color:var(--accent-violet);background:rgba(139,92,246,.07);box-shadow:0 0 0 4px var(--accent-glow)}
.vpn-input:focus~.vpn-input-ic{color:var(--accent2);animation:vpnWiggle .4s ease}
@keyframes vpnWiggle{0%,100%{transform:translateY(-50%) rotate(0)}25%{transform:translateY(-50%) rotate(-12deg)}75%{transform:translateY(-50%) rotate(12deg)}}
.vpn-textarea{
  width:100%;min-height:140px;padding:12px 14px;border-radius:12px;border:1px solid var(--card-b);
  background:rgba(0,0,0,.22);color:var(--t1);font-family:ui-monospace,'JetBrains Mono',monospace;font-size:11px;
  outline:none;transition:border-color .2s,background .2s,box-shadow .2s;direction:ltr;text-align:left;resize:vertical;line-height:1.6;
}
[data-theme="light"] .vpn-textarea{background:rgba(139,92,246,.04)}
.vpn-textarea:focus{border-color:var(--accent-violet);background:rgba(139,92,246,.07);box-shadow:0 0 0 4px var(--accent-glow)}
.vpn-textarea::placeholder{color:var(--t3);opacity:.65}

/* VPN empty-state — gentle call-to-action */
.vpn-empty-state{transition:opacity .25s,transform .25s}
.vpn-empty-state.hidden{opacity:0;transform:translateY(-4px);pointer-events:none;height:0;padding:0;margin:0;overflow:hidden;border:none}

/* Trojan/Link health badge — NixHD style */
.cfg-sub-tag{transition:all .18s ease}
.cfg-sub-tag:hover{transform:translateY(-1px)}

/* ═══════════════════════════════════════════════════════════════════════════
   Experimental Section — Responsive Grid (mobile-first)
   ▸ auto-fit/minmax → cards natively collapse on narrow screens
   ▸ header badge wraps below title on small screens
   ▸ sub-sections two-column on desktop, single-column on mobile
   ▸ feature cards stack with smaller padding on phones
   ═══════════════════════════════════════════════════════════════════════════ */
.exp-features-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(min(320px,100%),1fr));
  gap:14px;
  margin-bottom:24px;
}
.exp-subsections{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:18px;
  margin-top:20px;
}
.exp-stealth-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(min(280px,100%),1fr));
  gap:10px;
}
.exp-action-btn{
  width:100%;
  text-align:right;
  justify-content:flex-start;
  font-size:12px;
}
.exp-recheck-btn{
  width:100%;
  display:flex;
  align-items:center;
  justify-content:center;
  gap:8px;
  padding:12px 16px;
}

/* Tablet */
@media(max-width:900px){
  .exp-features-grid{gap:10px}
  .exp-subsections{gap:14px}
  .exp-stealth-grid{gap:8px}
}

/* Mobile — single column, tighter padding, full-width buttons */
@media(max-width:640px){
  .exp-features-grid{
    grid-template-columns:1fr;
    gap:10px;
    margin-bottom:18px;
  }
  .exp-subsections{
    grid-template-columns:1fr;
    gap:14px;
    margin-top:14px;
  }
  .exp-stealth-grid{
    grid-template-columns:1fr;
    gap:8px;
  }
  .exp-sub-card{padding:16px !important}
  #pg-experimental .page-hdr h1{font-size:20px}
  #pg-experimental .page-hdr p{font-size:11.5px;line-height:1.55}
  #exp-warning{padding:12px 14px}
  #exp-warning > div:last-child > div:last-child{font-size:11px;line-height:1.55}
  #exp-warning code{font-size:10px;padding:1px 5px}
}

/* Extra small phones */
@media(max-width:380px){
  .exp-sub-card{padding:12px !important}
  .exp-action-btn{font-size:11px;padding:8px 10px}
  #pg-experimental .page-hdr h1{font-size:18px}
  #pg-experimental .page-hdr i.ti-flask{font-size:22px}
}

</style>
<style>
/* ═══════════════════════════════════════════════════════════════════════════
   EMIX Motion Layer — لایه‌ی روان‌سازی (فقط کیفیت حرکت؛ بدون تغییر طراحی)
   ▸ این بلاک صرفاً انیمیشن/ترنزیشن اضافه می‌کند؛ هیچ رنگ/چیدمانی را override نمی‌کند
   ▸ اگر حذف شود، پنل دقیقاً مثل قبل کار می‌کند
   ═══════════════════════════════════════════════════════════════════════════ */

/* ── ۱) حرکت نرم سراسری ── */
html{scroll-behavior:smooth}
body,.pg,.card,.cfg-card,.btn,.nav-it,.cm-modal,
.cfg-sub-tag,.proto-chip,.ubar-f,.tog,.info-item
{transition-timing-function:cubic-bezier(.32,.72,0,1)}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.001s !important;transition-duration:.001s !important;scroll-behavior:auto !important}
}

/* ── ۲) کارت‌های کانفیگ: شناور شدن نرم و بازخورد لمسی ── */
.cfg-card{will-change:transform}
.cfg-card:hover{transform:translateY(-2px);box-shadow:0 10px 34px -14px rgba(139,92,246,.22),var(--shadow)}
.cfg-card:active{transform:translateY(0) scale(.997)}
.cfg-card.selected{transform:translateY(-1px)}

/* ── ۳) دکمه‌ها: بازخورد فشار نرم‌تر (طراحی موجود دست‌نخورده) ── */
.btn{position:relative}
.btn:disabled{opacity:.55;cursor:not-allowed;filter:saturate(.6)}
.btn-icon{transition:transform .18s cubic-bezier(.32,.72,0,1),filter .18s,opacity .18s,background .18s,border-color .18s,color .18s}
.btn-icon:not(:disabled):hover i{transform:scale(1.12)}
.btn-icon i{transition:transform .18s cubic-bezier(.32,.72,0,1)}
.btn-icon:not(:disabled):active{transform:scale(.9)}

/* ── ۴) بج پینگ: تغییر رنگ نرم + پاپ ظریف هنگام نتیجه ── */
.cfg-sub-tag{transition:color .35s,background .35s,border-color .35s}
.ping-pop{animation:pingPop .45s cubic-bezier(.34,1.56,.64,1)}
@keyframes pingPop{0%{transform:scale(.8);opacity:.4}60%{transform:scale(1.06)}100%{transform:scale(1);opacity:1}}
.ping-dot{width:6px;height:6px;border-radius:50%;background:currentColor;flex-shrink:0;animation:pingPulse 1.2s ease-in-out infinite}
@keyframes pingPulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(.72)}}

/* ── ۵) حالت بارگذاری پینگ: سه‌نقطه‌ی موجی به‌جای متن خشک ── */
.ping-wave{display:inline-flex;gap:2.5px;align-items:center;margin-right:2px}
.ping-wave span{width:3.5px;height:3.5px;border-radius:50%;background:currentColor;animation:pingWave 1s ease-in-out infinite}
.ping-wave span:nth-child(2){animation-delay:.15s}
.ping-wave span:nth-child(3){animation-delay:.3s}
@keyframes pingWave{0%,100%{transform:translateY(0);opacity:.45}50%{transform:translateY(-3.5px);opacity:1}}

/* ── ۶) توست: ورود فنری ── */
.toast.show{animation:toastIn .38s cubic-bezier(.34,1.4,.64,1)}
@keyframes toastIn{from{opacity:0;transform:translateX(-50%) translateY(26px) scale(.92)}to{opacity:1;transform:translateX(-50%) translateY(0) scale(1)}}
.toast.warn{border-color:rgba(245,158,11,.3);background:var(--amber-bg);color:var(--amber-t)}

/* ── ۷) سوییچ بین صفحات: محو نرم ── */
.pg.on{animation:pgIn .3s cubic-bezier(.32,.72,0,1)}
@keyframes pgIn{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:none}}

/* ── ۸) نوار پیشرفت پینگ روی دکمه‌ی «تست همه» ── */
#ping-all-btn{overflow:hidden;position:relative}
#ping-all-btn .ping-prog{position:absolute;inset:0;background:linear-gradient(90deg,transparent,var(--accent-d),transparent);transform:translateX(-100%);pointer-events:none}
#ping-all-btn.running .ping-prog{animation:progSweep 1.1s linear infinite}
@keyframes progSweep{to{transform:translateX(100%)}}

/* ── ۹) اعداد: شمارش نرم (کلاس کمکی JS) ── */
.num-tick{display:inline-block;transition:transform .2s cubic-bezier(.34,1.56,.64,1)}
.num-tick.tick{transform:translateY(-2px) scale(1.08)}

/* ── ۱۰) سوییچ فعال/غیرفعال: حرکت نرم‌تر ── */
.tog{transition:background .3s,border-color .3s,box-shadow .3s}
.tog::after{transition:bottom .3s cubic-bezier(.34,1.56,.64,1),transform .3s cubic-bezier(.34,1.56,.64,1),background .3s}
.tog:active::after{transform:scale(1.15)}

/* ── ۱۱) کارت‌های داخل صفحه: ورود پلکانی ظریف (فقط هنگام ورود به صفحه) ── */
body.cascade #links-grid .cfg-card{animation:cardCascade .4s cubic-bezier(.32,.72,0,1) backwards}
body.cascade #links-grid .cfg-card:nth-child(1){animation-delay:.02s}
body.cascade #links-grid .cfg-card:nth-child(2){animation-delay:.05s}
body.cascade #links-grid .cfg-card:nth-child(3){animation-delay:.08s}
body.cascade #links-grid .cfg-card:nth-child(4){animation-delay:.11s}
body.cascade #links-grid .cfg-card:nth-child(5){animation-delay:.14s}
body.cascade #links-grid .cfg-card:nth-child(6){animation-delay:.17s}
body.cascade #links-grid .cfg-card:nth-child(n+7){animation-delay:.2s}
@keyframes cardCascade{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}

/* ── ۱۲) Command Palette (Ctrl+K) ── */
#cp-overlay{position:fixed;inset:0;z-index:1200;background:rgba(0,0,0,.55);backdrop-filter:blur(6px);display:none;align-items:flex-start;justify-content:center;padding-top:12vh}
#cp-overlay.open{display:flex;animation:cpFade .18s ease}
@keyframes cpFade{from{opacity:0}to{opacity:1}}
#cp-box{width:100%;max-width:560px;background:var(--bg2);border:1px solid var(--card-b);border-radius:16px;box-shadow:0 30px 80px -20px rgba(0,0,0,.7),0 0 40px -12px rgba(139,92,246,.25);overflow:hidden;animation:cpIn .22s cubic-bezier(.32,.72,0,1)}
@keyframes cpIn{from{opacity:0;transform:translateY(-14px) scale(.98)}to{opacity:1;transform:none}}
#cp-input-wrap{display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--card-b)}
#cp-input-wrap i{color:var(--t3);font-size:17px}
#cp-input{flex:1;background:none;border:none;outline:none;color:var(--t1);font-family:inherit;font-size:14px}
#cp-input::placeholder{color:var(--t3)}
#cp-kbd{font-size:9.5px;color:var(--t3);background:var(--bg3);border:1px solid var(--card-b);border-radius:6px;padding:2px 7px;font-family:monospace}
#cp-list{max-height:340px;overflow-y:auto;padding:8px}
.cp-group{padding:8px 10px 4px;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--t3);font-weight:700}
.cp-item{display:flex;align-items:center;gap:11px;padding:9.5px 12px;border-radius:10px;cursor:pointer;transition:background .12s}
.cp-item:hover,.cp-item.sel{background:var(--accent-d)}
.cp-item>i{font-size:16px;color:var(--accent2);width:20px;text-align:center;flex-shrink:0}
.cp-item .cp-txt{flex:1;min-width:0}
.cp-item .cp-title{font-size:12.5px;color:var(--t1);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cp-item .cp-sub{font-size:9.5px;color:var(--t3);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cp-item .cp-hint{font-size:9px;color:var(--t3);background:var(--bg3);border:1px solid var(--card-b);border-radius:5px;padding:1px 6px;flex-shrink:0}
#cp-empty{padding:26px;text-align:center;color:var(--t3);font-size:12px}
#cp-foot{display:flex;gap:14px;padding:9px 16px;border-top:1px solid var(--card-b);font-size:9.5px;color:var(--t3)}
#cp-foot b{color:var(--t2);font-weight:600}
@media(max-width:600px){#cp-overlay{padding-top:6vh}}
</style>
</head>
<body>
<div class="toast" id="toast"></div>

<!-- ══════ Command Palette (Ctrl+K) ══════ -->
<div id="cp-overlay" onclick="if(event.target===this)cpClose()">
  <div id="cp-box" role="dialog" aria-label="پالت فرمان">
    <div id="cp-input-wrap">
      <i class="ti ti-search"></i>
      <input id="cp-input" type="text" placeholder="جستجو یا فرمان... (مثلاً: ساخت کانفیگ، تست همه، پل ایران)" autocomplete="off">
      <span id="cp-kbd">ESC</span>
    </div>
    <div id="cp-list"></div>
    <div id="cp-foot">
      <span><b>↑↓</b> جابه‌جایی</span>
      <span><b>Enter</b> اجرا</span>
      <span><b>Ctrl+K</b> باز/بسته</span>
    </div>
  </div>
</div>

<div class="modal-bg" id="modal-create-link">
  <div class="modal-v2 cm-modal">
    <button class="cm-close" onclick="closeModal('modal-create-link')"><i class="ti ti-x"></i></button>
    <div class="cm-head">
      <div class="cm-head-row">
        <div class="cm-head-icon" id="cm-head-icon"><i class="ti ti-square-rounded-plus"></i></div>
        <div>
          <div class="cm-head-title" id="cm-head-title">ساخت کانفیگ جدید</div>
          <div class="cm-head-sub" id="cm-head-sub">تنظیمات کامل پروتکل، ترابرد و محدودیت‌ها در یک صفحه</div>
        </div>
      </div>
    </div>

    <div class="cm-body">

      <!-- اطلاعات پایه -->
      <div class="cm-section">
        <div class="cm-section-label"><i class="ti ti-id-badge-2"></i> اطلاعات پایه</div>
        <div class="cm-field"><label>نام کانفیگ</label>
          <input class="cm-input" id="nl-label" placeholder="مثلاً: کاربر علی">
        </div>
        <div class="cm-field" id="nl-target-wrap" style="display:none">
          <label><i class="ti ti-topology-star-3"></i> پنل مقصد</label>
          <select class="cm-input" id="nl-target" onchange="onNlTargetChange()"><option value="">این پنل</option></select>
        </div>
        <div class="cm-row2">
          <div class="cm-field" id="nl-sub-wrap"><label>گروه ساب</label>
            <select class="cm-input" id="nl-sub"><option value="">— بدون گروه —</option></select>
          </div>
          <div class="cm-field"><label>یادداشت (اختیاری)</label>
            <input class="cm-input" id="nl-note" placeholder="توضیح کوتاه">
          </div>
        </div>
      </div>

      <!-- بخش ۱: پایه -->
      <div class="cm-section">
        <div class="cm-section-label"><i class="ti ti-plug-connected"></i> پروتکل پایه</div>
        <div class="cm-dd open" id="dd-base">
          <div class="cm-dd-trigger" onclick="cmToggleDD('dd-base')">
            <div class="cm-dd-icon" id="dd-base-icon"><i class="ti ti-bolt"></i></div>
            <div class="cm-dd-text">
              <div class="cm-dd-title">پروتکل پایه — <span id="dd-base-current">VLESS</span></div>
              <div class="cm-dd-desc" id="dd-base-current-desc">سبک، سریع و پرکاربردترین گزینه</div>
            </div>
            <i class="ti ti-chevron-down cm-dd-chev"></i>
          </div>
          <div class="cm-dd-panel"><div class="cm-dd-panel-inner"><div class="cm-dd-list">
            <div class="cm-opt sel" data-base="vless" onclick="cmSelectBase('vless',this)">
              <div class="cm-opt-radio"></div>
              <div class="cm-opt-icon"><i class="ti ti-bolt"></i></div>
              <div class="cm-opt-text"><div class="cm-opt-title">VLESS</div><div class="cm-opt-desc">سبک، سریع و پرکاربردترین گزینه</div></div>
              <span class="cm-opt-tag">پیشنهادی</span>
            </div>
            <div class="cm-opt" data-base="trojan" onclick="cmSelectBase('trojan',this)">
              <div class="cm-opt-radio"></div>
              <div class="cm-opt-icon"><i class="ti ti-shield-lock"></i></div>
              <div class="cm-opt-text"><div class="cm-opt-title">Trojan</div><div class="cm-opt-desc">شبیه‌سازی ترافیک HTTPS معمولی</div></div>
            </div>
            <div class="cm-opt" data-base="shadowsocks" onclick="cmSelectBase('shadowsocks',this)">
              <div class="cm-opt-radio"></div>
              <div class="cm-opt-icon"><i class="ti ti-shield-lock-filled"></i></div>
              <div class="cm-opt-text"><div class="cm-opt-title">Shadowsocks</div><div class="cm-opt-desc">رمزنگاری AEAD مستقیم، بدون نیاز به TLS خارجی</div></div>
              <span class="cm-opt-tag" style="background:var(--purple-bg);color:#FFB199">AEAD</span>
            </div>
            <div class="cm-opt" data-base="telproxy" onclick="cmSelectBase('telproxy',this)">
              <div class="cm-opt-radio"></div>
              <div class="cm-opt-icon"><i class="ti ti-brand-telegram"></i></div>
              <div class="cm-opt-text"><div class="cm-opt-title">Telegram Proxy</div><div class="cm-opt-desc">پروکسی MTProto مستقیم روی یک پورت TCP اختصاصی</div></div>
              <span class="cm-opt-tag" style="background:var(--purple-bg);color:var(--purple-t)">MTProto</span>
            </div>
          </div></div></div>
        </div>
      </div>
      
      <!-- بخش ۲: استریم (ترابرد + فینگرپرینت + ALPN) — فقط برای VLESS/Trojan -->
      <div class="cm-section" id="stream-section">
        <div class="cm-section-label"><i class="ti ti-transfer"></i> استریم</div>
      
        <div class="cm-dd" id="dd-transport">
          <div class="cm-dd-trigger" onclick="cmToggleDD('dd-transport')">
            <div class="cm-dd-icon" id="dd-transport-icon"><i class="ti ti-link"></i></div>
            <div class="cm-dd-text">
              <div class="cm-dd-title">نوع ترابرد — <span id="dd-transport-current">WebSocket</span></div>
              <div class="cm-dd-desc" id="dd-transport-current-desc">پایدار و سازگار با همه شرایط شبکه</div>
            </div>
            <i class="ti ti-chevron-down cm-dd-chev"></i>
          </div>
          <div class="cm-dd-panel"><div class="cm-dd-panel-inner"><div class="cm-dd-list">
            <div class="cm-opt sel" data-t="ws" onclick="cmSelectTransport('ws',this)">
              <div class="cm-opt-radio"></div>
              <div class="cm-opt-icon"><i class="ti ti-link"></i></div>
              <div class="cm-opt-text"><div class="cm-opt-title">WebSocket</div><div class="cm-opt-desc">پایدار و سازگار با همه شرایط شبکه</div></div>
            </div>
            <div class="cm-opt" data-t="xhttp-packet-up" onclick="cmSelectTransport('xhttp-packet-up',this)">
              <div class="cm-opt-radio"></div>
              <div class="cm-opt-icon"><i class="ti ti-package"></i></div>
              <div class="cm-opt-text"><div class="cm-opt-title">XHTTP · packet-up</div><div class="cm-opt-desc">سازگاری بالا با CDN و پروکسی‌ها</div></div>
            </div>
            <div class="cm-opt" data-t="xhttp-stream-up" onclick="cmSelectTransport('xhttp-stream-up',this)">
              <div class="cm-opt-radio"></div>
              <div class="cm-opt-icon"><i class="ti ti-rocket"></i></div>
              <div class="cm-opt-text"><div class="cm-opt-title">XHTTP · stream-up</div><div class="cm-opt-desc">تاخیر پایین‌تر برای اتصال‌های پرسرعت</div></div>
            </div>
          </div></div></div>
        </div>
      
        <div style="height:10px"></div>
      
        <div class="stream-sub-label"><i class="ti ti-transfer-vertical"></i> ALPN</div>
        <div class="alpn-row" id="alpn-pills">
          <div class="alpn-chip active" data-alpn="h2" onclick="cmToggleAlpn('h2',this)">
            <span class="alpn-chip-dot"><i class="ti ti-check"></i></span> h2
          </div>
          <div class="alpn-chip active" data-alpn="http/1.1" onclick="cmToggleAlpn('http/1.1',this)">
            <span class="alpn-chip-dot"><i class="ti ti-check"></i></span> http/1.1
          </div>
          <div class="alpn-chip" data-alpn="h3" onclick="cmToggleAlpn('h3',this)">
            <span class="alpn-chip-dot"><i class="ti ti-check"></i></span> h3
          </div>
        </div>
        <div class="cm-pills" style="margin-top:6px">
          <span class="cm-pill active" onclick="cmAlpnPreset(['h2','http/1.1'],this)">استاندارد</span>
          <span class="cm-pill" onclick="cmAlpnPreset(['h2'],this)">مدرن (h2)</span>
          <span class="cm-pill" onclick="cmAlpnPreset(['http/1.1'],this)">قدیمی (http/1.1)</span>
          <span class="cm-pill" onclick="cmAlpnPreset(['h2','http/1.1','h3'],this)">همه</span>
        </div>
        
        <div class="stream-sub-label"><i class="ti ti-fingerprint"></i> Fingerprint (TLS Client Hello)</div>
        <div class="fp-grid" id="fp-pills">
          <div class="fp-card active" data-fp="chrome" onclick="cmSetFp('chrome',this)">
            <div class="fp-card-check"><i class="ti ti-check"></i></div>
            <div class="fp-card-icon"><i class="ti ti-brand-chrome"></i></div>
            <div class="fp-card-title">Chrome</div>
          </div>
          <div class="fp-card" data-fp="firefox" onclick="cmSetFp('firefox',this)">
            <div class="fp-card-check"><i class="ti ti-check"></i></div>
            <div class="fp-card-icon"><i class="ti ti-brand-firefox"></i></div>
            <div class="fp-card-title">Firefox</div>
          </div>
          <div class="fp-card" data-fp="ios" onclick="cmSetFp('ios',this)">
            <div class="fp-card-check"><i class="ti ti-check"></i></div>
            <div class="fp-card-icon"><i class="ti ti-brand-apple"></i></div>
            <div class="fp-card-title">iOS / Safari</div>
          </div>
        </div>
        
        <input type="hidden" id="nl-alpn" value="h2,http/1.1">
        <input type="hidden" id="nl-fp" value="chrome">
      
        <input type="hidden" id="nl-proto" value="vless-ws">
        <div class="cm-note" style="margin-top:12px" id="transport-note"></div>
      </div>

      <!-- این سه بخش عمداً خارج از stream-section هستند: وقتی Telegram Proxy یا Shadowsocks
           انتخاب می‌شود stream-section مخفی می‌شود، اگر این بخش‌ها داخلش می‌ماندند با آن مخفی
           می‌شدند حتی وقتی display خودشان block/flex تنظیم می‌شد. -->
      <div class="cm-note" style="margin-top:12px;display:none" id="mtproto-note"></div>

      <div class="cm-section" id="ss-cipher-field" style="display:none;margin-bottom:0">
        <div class="cm-section-label"><i class="ti ti-key"></i> الگوریتم رمزنگاری</div>
        <div class="cm-pills">
          <span class="cm-pill active" data-ss-cipher="chacha20-ietf-poly1305" onclick="cmSetSsCipher('chacha20-ietf-poly1305',this)">ChaCha20-Poly1305</span>
          <span class="cm-pill" data-ss-cipher="aes-256-gcm" onclick="cmSetSsCipher('aes-256-gcm',this)">AES-256-GCM</span>
        </div>
        <input type="hidden" id="nl-ss-cipher" value="chacha20-ietf-poly1305">
        <div class="cm-note" style="margin-top:10px">
          <i class="ti ti-info-circle"></i>
          <span>پسورد به‌صورت خودکار و امن ساخته می‌شود؛ لینک <b>ss://</b> بعد از ساخت کانفیگ در دسترس است.</span>
        </div>
      </div>

      <!-- ── SNI Spoofing (per-link, opt-in) ──────────────────────────────────
           Hidden for MTProto (uses FakeTLS domain — SNI spoofing not applicable)
           Hidden for Shadowsocks (v2ray-plugin host= is shared between WS Host
           and TLS SNI — changing it would break routing through CDN edge).
           Visible for: VLESS-WS, VLESS-XHTTP, Trojan-WS, Trojan-XHTTP. -->
      <div class="cm-section" id="sni-spoof-field" style="display:block;margin-bottom:0">
        <div class="cm-section-label"><i class="ti ti-mask"></i> SNI Spoofing (جعل SNI در TLS Handshake)</div>
        <div class="cm-row2" style="align-items:center;gap:10px">
          <label class="tog-wrap" style="display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none">
            <span class="tog" id="nl-spoof-toggle" onclick="cmToggleSpoof()"></span>
            <span style="font-size:12px;font-weight:600;color:var(--t2)">🎭 فعال‌سازی SNI جعلی</span>
          </label>
        </div>
        <div id="nl-spoof-controls" style="display:none;margin-top:10px">
          <div class="cm-row2" style="gap:8px">
            <input class="cm-input" id="nl-spoof-sni" type="text" placeholder="www.google.com" style="direction:ltr;text-align:left;font-family:monospace">
            <select class="cm-input" id="nl-spoof-preset" onchange="cmSpoofPreset(this)" style="flex:.5">
              <option value="">— انتخاب سریع —</option>
              <option value="www.google.com">www.google.com</option>
              <option value="www.cloudflare.com">www.cloudflare.com</option>
              <option value="docs.google.com">docs.google.com</option>
              <option value="drive.google.com">drive.google.com</option>
              <option value="images.unsplash.com">images.unsplash.com</option>
              <option value="api.github.com">api.github.com</option>
              <option value="mail.yahoo.com">mail.yahoo.com</option>
              <option value="www.microsoft.com">www.microsoft.com</option>
              <option value="www.amazon.com">www.amazon.com</option>
              <option value="speedtest.net">speedtest.net</option>
            </select>
          </div>
          <div class="cm-note" style="margin-top:8px">
            <i class="ti ti-info-circle"></i>
            <span>SNI جعلی در هندشیک TLS ارسال می‌شود. درخروجی «پل چندلوکیشن v2 → ردیاب SNI» می‌توانی <b>با مدرک زنده</b> ببینی هندشیک واقعاً قبول می‌شود یا نه — آزمون با هندشیک واقعی TLS انجام می‌شود، نه حدس.</span>
          </div>
          <div id="nl-spoof-cdn-warn" class="cm-note" style="margin-top:8px;display:none;background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.25);border-radius:10px">
            <i class="ti ti-info-circle" style="color:#10B981"></i>
            <span style="color:#10B981"><b>حالت مستقیم:</b> بدون CDN، پارامتر <code style="background:rgba(0,0,0,.3);padding:1px 4px;border-radius:3px;color:#10B981">allowInsecure=1</code> به لینک اضافه می‌شود. کلاینت بررسی cert را رد می‌کند → SNI جعلی در TLS Handshake ارسال می‌شود → DPI گول می‌خورد. برای حداکثر استتار، <code style="background:rgba(0,0,0,.3);padding:1px 4px;border-radius:3px;color:#10B981">EMIX_CDN_DOMAIN</code> را در Railway تنظیم کنید (حالت CDN امن‌تر است).</span>
          </div>
        </div>
        <input type="hidden" id="nl-spoof-enabled" value="0">
      </div>

      <div class="cm-section" id="mtproto-port-field" style="display:none;margin-bottom:0">
        <!-- Audit fix: ویجت auto-domain حذف شد — استایل ناقص (کاما به‌جای سمی‌کالن) داشت،
             عناصر دکمه/وضعیتش وجود نداشتند و JS آن (autoGetMtprotoDomain و…) به‌هم می‌ریخت.
             مسیر واقعی دریافت دامنه عمومی: توکن Railway را در تنظیمات TCP Proxy وارد کنید. -->
        <div class="cm-row2">
          <div class="cm-field">
            <label><i class="ti ti-route" style="color:var(--accent);margin-left:4px"></i>پورت TCP</label>
            <input class="cm-input" id="nl-mtproto-port" type="number" min="1" max="65535" placeholder="خالی = خودکار">
          </div>
          <div class="cm-field">
            <label><i class="ti ti-server-2" style="color:var(--accent);margin-left:4px"></i>Fake TLS SNI</label>
            <input class="cm-input" id="nl-mtproto-domain" type="text" placeholder="www.cloudflare.com" oninput="cmClearSniPills()">
          </div>
        </div>
        <div class="cm-pills" style="margin-top:-4px;margin-bottom:10px">
          <span class="cm-pill active" onclick="cmSetSni('www.cloudflare.com',this)"><i class="ti ti-brand-cloudflare" style="margin-left:3px"></i>www.cloudflare.com</span>
          <span class="cm-pill" onclick="cmSetSni('www.google.com',this)">www.google.com</span>
          <span class="cm-pill" onclick="cmSetSni('www.microsoft.com',this)">www.microsoft.com</span>
          <span class="cm-pill" onclick="cmSetSni('www.amazon.com',this)">www.amazon.com</span>
        </div>
        <div class="cm-row2">
          <div class="cm-field">
            <label><i class="ti ti-world-bolt" style="color:var(--accent);margin-left:4px"></i>دامنه‌ی عمومی TCP Proxy</label>
            <input class="cm-input" id="nl-mtproto-public-host" type="text" placeholder="xxxx.proxy.rlwy.net">
          </div>
          <div class="cm-field">
            <label><i class="ti ti-plug-connected" style="color:var(--accent);margin-left:4px"></i>پورت عمومی TCP Proxy</label>
            <input class="cm-input" id="nl-mtproto-public-port" type="number" min="1" max="65535" placeholder="مثلاً 12345">
          </div>
        </div>
        <div style="font-size:11px;opacity:.7;margin:-4px 0 10px;line-height:1.7">
          اگر TCP Proxy را خودت از داشبورد Railway ساخته‌ای، دامنه و پورت عمومی‌اش را اینجا وارد کن
          (همانی که به پورت داخلی بالا map شده). بدون این، لینک از بیرون کار نمی‌کند.
        </div>
        <div class="cm-note" style="margin-top:0">
        </div>
      </div>


      <!-- محدودیت‌ها -->
      <div class="cm-section">
        <div class="cm-section-label"><i class="ti ti-adjustments"></i> محدودیت‌ها</div>
        <div class="cm-field">
          <label>سهمیه ترافیک</label>
          <div class="cm-row2">
            <input class="cm-input" id="nl-val" type="number" min="0" step="0.1" placeholder="0 = نامحدود">
            <select class="cm-input" id="nl-unit"><option value="GB">GB</option><option value="MB" selected>MB</option></select>
          </div>
          <div class="cm-pills">
            <span class="cm-pill" onclick="cmQuota(0,'GB',this)">نامحدود</span>
            <span class="cm-pill" onclick="cmQuota(500,'MB',this)">۵۰۰MB</span>
            <span class="cm-pill active" onclick="cmQuota(1,'GB',this)">۱GB</span>
            <span class="cm-pill" onclick="cmQuota(5,'GB',this)">۵GB</span>
            <span class="cm-pill" onclick="cmQuota(10,'GB',this)">۱۰GB</span>
            <span class="cm-pill" onclick="cmQuota(50,'GB',this)">۵۰GB</span>
          </div>
        </div>
        <div class="cm-field" style="margin-bottom:4px">
          <label>انقضا</label>
          <input class="cm-input" id="nl-exp" type="number" min="0" step="1" placeholder="روز · 0 = نامحدود">
          <div class="cm-pills">
            <span class="cm-pill" onclick="cmExpiry(0,this)">نامحدود</span>
            <span class="cm-pill" onclick="cmExpiry(7,this)">۷ روز</span>
            <span class="cm-pill active" onclick="cmExpiry(30,this)">۳۰ روز</span>
            <span class="cm-pill" onclick="cmExpiry(90,this)">۹۰ روز</span>
          </div>
        </div>
      </div>

    </div>

    <div class="cm-footer">
      <button class="cm-btn-cancel" onclick="closeModal('modal-create-link')">انصراف</button>
      <button class="cm-btn-submit" id="cm-submit-btn" onclick="createLink()"><i class="ti ti-link-plus" id="cm-submit-icon"></i> <span id="cm-submit-text">ساخت کانفیگ</span></button>    </div>
  </div>
</div>

<!-- مودال بروزرسانی -->
<div class="modal-bg" id="modal-update" style="z-index:9999">
  <div class="modal-v2" style="max-width:460px">
    <div class="modal-v2-head" style="background:linear-gradient(155deg,rgba(139,92,246,.16) 0%,transparent 65%)">
      <button class="modal-v2-close" onclick="closeModal('modal-update')"><i class="ti ti-x"></i></button>
      <div class="modal-v2-icon" style="background:linear-gradient(135deg,var(--accent),var(--accent2))"><i class="ti ti-cloud-download"></i></div>
      <div class="modal-v2-title">بروزرسانی جدید موجود است</div>
      <div class="modal-v2-sub">نسخه‌ی جدید <span id="update-modal-version">—</span> آماده نصب است</div>
    </div>
    <div class="modal-v2-body">
      <div class="cl" style="margin-top:0">
        <i class="ti ti-info-circle"></i>
        <span id="update-modal-desc">توضیحات بروزرسانی...</span>
      </div>
      <div class="modal-v2-footer">
        <button class="btn btn-o" onclick="dismissUpdate()" style="flex:.6">انصراف</button>
        <button class="btn btn-p" onclick="startUpdateFromModal()" style="flex:1;justify-content:center"><i class="ti ti-download"></i> نصب بروزرسانی</button>
      </div>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-support-dev" style="z-index:9999">
  <div class="modal-v2" style="max-width:440px">
    <div class="modal-v2-head" style="background:linear-gradient(155deg,rgba(236,72,153,.16) 0%,transparent 65%)">
      <div class="modal-v2-icon" style="background:linear-gradient(135deg,#EC4899,#F472B6)"><i class="ti ti-heart"></i></div>
      <div class="modal-v2-title">حمایت از سازنده</div>
      <div class="modal-v2-sub">اگه این پروژه به دردت خورد، یه حمایت کوچیک انگیزه‌مون رو چند برابر می‌کنه</div>
    </div>
    <div class="modal-v2-body">
      <div class="sdev-grid">
        <a href="https://github.com/EMIXPI/EMIX" target="_blank" rel="noopener" class="sdev-card">
          <span class="sdev-ic" style="background:linear-gradient(135deg,#24292F,#444D56)">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="#fff"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.09 3.29 9.4 7.86 10.93.57.1.78-.25.78-.55 0-.27-.01-1.17-.02-2.12-3.2.7-3.88-1.36-3.88-1.36-.52-1.34-1.28-1.7-1.28-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.08-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.02 11.02 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.64 1.59.24 2.76.12 3.05.74.8 1.19 1.82 1.19 3.08 0 4.41-2.7 5.38-5.27 5.67.42.36.78 1.07.78 2.15 0 1.56-.01 2.81-.01 3.19 0 .3.21.66.79.55A10.52 10.52 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z"/></svg>
          </span>
          <span class="sdev-txt">
            <span class="sdev-t">استار در گیت‌هاب</span>
            <span class="sdev-s">حمایت رایگان با یه ستاره ⭐</span>
          </span>
          <i class="ti ti-external-link sdev-go"></i>
        </a>
        <a href="https://t.me/emixpi" target="_blank" rel="noopener" class="sdev-card">
          <span class="sdev-ic" style="background:linear-gradient(135deg,#2AABEE,#229ED9)">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="#fff"><path d="M23.05 3.6 19.6 20.4c-.26 1.15-.94 1.43-1.9.9l-5.26-3.88-2.54 2.44c-.28.28-.52.52-1.06.52l.38-5.4L19.1 6.2c.42-.38-.1-.6-.65-.22L6.6 13.4 1.4 11.76c-1.14-.36-1.16-1.14.24-1.68L21.6 2.36c.94-.34 1.77.22 1.45 1.24Z"/></svg>
          </span>
          <span class="sdev-txt">
            <span class="sdev-t">عضویت در تلگرام</span>
            <span class="sdev-s">آپدیت‌ها و اخبار پروژه</span>
          </span>
          <i class="ti ti-external-link sdev-go"></i>
        </a>
      </div>
      <div class="modal-v2-footer">
        <button class="btn btn-o" id="support-dev-dismiss-btn" onclick="handleSupportDevDismiss()" style="flex:1;justify-content:center">ولم کن حوصله این کار‌ها رو ندارم</button>
      </div>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-links">
  <div class="modal-v2" style="max-width:520px;display:flex;flex-direction:column;max-height:88vh;overflow:hidden">
    <div class="lmodal-head" style="flex-shrink:0">
      <button class="modal-v2-close" onclick="closeModal('modal-links')"><i class="ti ti-x"></i></button>
      <div class="lmodal-icon-row">
        <div class="lmodal-icon"><i class="ti ti-link-plus"></i></div>
        <div>
          <div class="lmodal-title-v2">مدیریت کانفیگ‌های <span id="modal-sub-name" style="color:var(--accent2)">—</span></div>
          <div class="lmodal-sub-v2">کانفیگ‌هایی که می‌خواهید در این گروه باشند را انتخاب کنید</div>
        </div>
      </div>
      <div class="lmodal-search">
        <i class="ti ti-search"></i>
        <input type="text" id="lmodal-search-inp" placeholder="جستجوی کانفیگ..." oninput="filterLmodal(this.value)">
      </div>
      <div class="lmodal-quickbar">
        <button class="lmodal-qbtn" onclick="lmodalSelectAll(true)"><i class="ti ti-checks"></i> انتخاب همه</button>
        <button class="lmodal-qbtn" onclick="lmodalSelectAll(false)"><i class="ti ti-x"></i> لغو همه</button>
        <span class="lmodal-count" id="lmodal-count">۰ انتخاب شده</span>
      </div>
    </div>
    <div class="lmodal-list" id="modal-links-body" style="flex:1;overflow-y:auto;min-height:0;max-height:none">در حال بارگذاری...</div>
    <div class="lmodal-footer" style="flex-shrink:0">
      <div class="lmodal-footer-info"><i class="ti ti-info-circle"></i> تغییرات بلافاصله اعمال می‌شود</div>
      <div class="lmodal-footer-btns">
        <button class="btn btn-o" onclick="closeModal('modal-links')">بستن</button>
        <button class="btn btn-p" id="modal-save-btn" onclick="saveSubLinks()"><i class="ti ti-check"></i> ذخیره</button>
      </div>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-ad-tag">
  <div class="modal-v2 cm-modal" style="max-width:460px">
    <button class="cm-close" onclick="closeModal('modal-ad-tag')"><i class="ti ti-x"></i></button>

    <div class="cm-head">
      <div class="cm-head-row">
        <div class="cm-head-icon" style="background:linear-gradient(135deg,var(--purple),#0EA5E9)"><i class="ti ti-speakerphone"></i></div>
        <div>
          <div class="cm-head-title">تبلیغ کانال روی پروکسی</div>
          <div class="cm-head-sub" id="at-label-sub">تنظیم ad-tag برای <span id="at-cfg-name" style="color:var(--accent2)">—</span></div>
        </div>
      </div>
    </div>

    <div class="cm-body">
      <div class="cm-section">
        <div class="cm-section-label"><i class="ti ti-tag"></i> کد تبلیغ (ad_tag)</div>
        <div class="cm-field" style="margin-bottom:8px">
          <input class="cm-input" id="at-tag" placeholder="مثلاً: 3AB4C5D6E7F8...">
        </div>
        <div class="cm-note">
          <i class="ti ti-info-circle"></i>
          <span>این کد را از ربات <b>@MTProxybot</b> در تلگرام دریافت کنید (با ارسال دستور <b>/newproxy</b> و ثبت لینک پروکسی). با تنظیم این کد، هر بار کاربر از این پروکسی استفاده کند، تبلیغ کانال شما در تلگرامش نمایش داده می‌شود.</span>
        </div>
        <div class="cm-note" style="background:var(--amber-bg);color:var(--amber-t);margin-top:8px">
          <i class="ti ti-alert-triangle"></i>
          <span>با ثبت یا تغییر کد، پروکسی برای چند ثانیه ری‌استارت می‌شود و اتصال کاربران فعلی به‌طور موقت قطع خواهد شد.</span>
        </div>
      </div>
    </div>

    <div class="cm-footer">
      <button class="cm-btn-cancel" onclick="closeModal('modal-ad-tag')">انصراف</button>
      <button class="cm-btn-submit" id="at-submit-btn" onclick="submitAdTag()">
        <i class="ti ti-check"></i> ذخیره و اعمال
      </button>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-mt-info">
  <div class="modal-v2 cm-modal" style="max-width:480px">
    <button class="cm-close" onclick="closeModal('modal-mt-info')"><i class="ti ti-x"></i></button>

    <div class="cm-head">
      <div class="cm-head-row">
        <div class="cm-head-icon" style="background:linear-gradient(135deg,var(--accent),var(--accent2))"><i class="ti ti-info-circle"></i></div>
        <div>
          <div class="cm-head-title">اطلاعات پروکسی تلگرام</div>
          <div class="cm-head-sub">مشخصات <span id="mti-cfg-name" style="color:var(--accent2)">—</span></div>
        </div>
      </div>
    </div>

    <div class="cm-body">
      <div class="cm-section">
        <div class="cm-section-label"><i class="ti ti-key"></i> سکرت (مناسب برای ثبت در ربات‌ها)</div>
        <div class="cm-field" style="margin-bottom:8px">
          <div class="cm-input" id="mti-secret" style="font-family:ui-monospace,monospace;font-size:11.5px;word-break:break-all;user-select:all;cursor:text">—</div>
        </div>
        <button class="btn btn-g" style="width:100%;justify-content:center" onclick="cpMtiField('mti-secret','سکرت کپی شد ✓')"><i class="ti ti-copy"></i> کپی سکرت</button>
        <div class="cm-note" style="margin-top:10px">
          <i class="ti ti-info-circle"></i>
          <span>این نسخه‌ی خالص سکرت است (بدون پیشوند fake-TLS و دامنه) — همان مقداری که ربات‌هایی مثل <b>@MTProxybot</b> برای ثبت پروکسی و دریافت لینک تبلیغ (ad_tag) نیاز دارند.</span>
        </div>
      </div>

      <div class="cm-section" style="margin-bottom:6px">
        <div class="cm-section-label"><i class="ti ti-link"></i> لینک کامل پروکسی</div>
        <div class="cm-field" style="margin-bottom:8px">
          <div class="cm-input" id="mti-link" style="font-family:ui-monospace,monospace;font-size:11px;word-break:break-all;user-select:all;cursor:text">—</div>
        </div>
        <button class="btn btn-p" style="width:100%;justify-content:center" onclick="cpMtiField('mti-link','لینک کپی شد ✓')"><i class="ti ti-copy"></i> کپی لینک کامل</button>
      </div>
    </div>

    <div class="cm-footer">
      <button class="cm-btn-cancel" style="flex:1;justify-content:center" onclick="closeModal('modal-mt-info')">بستن</button>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-domain-gen">
  <div class="modal-v2 cm-modal" style="max-width:460px">
    <button class="cm-close" onclick="closeModal('modal-domain-gen')"><i class="ti ti-x"></i></button>
    <div class="cm-head">
      <div class="cm-head-row">
        <div class="cm-head-icon"><i class="ti ti-repeat"></i></div>
        <div>
          <div class="cm-head-title">تولید انبوه دامنه</div>
          <div class="cm-head-sub">ساخت چند TCP Proxy روی Railway برای گرفتن چند دامنه‌ی متفاوت</div>
        </div>
      </div>
    </div>
    <div class="cm-body">
      <div class="cm-section" id="dg-token-section">
        <div class="cm-section-label"><i class="ti ti-key"></i> احراز هویت</div>
        <div class="cm-field">
          <label>Railway API Token</label>
          <input class="cm-input" id="dg-token" type="password" placeholder="توکن اکانت یا پروژه‌ی Railway">
        </div>
        <div class="cm-row2">
          <div class="cm-field" style="margin-bottom:0">
            <label>پورت داخلی اپلیکیشن (اختیاری)</label>
            <input class="cm-input" id="dg-port" type="number" placeholder="پیش‌فرض: پورت خودِ پنل">
          </div>
          <div class="cm-field" style="margin-bottom:0">
            <label>تعداد دامنه‌ی مورد نیاز</label>
            <input class="cm-input" id="dg-count" type="number" min="1" value="10">
          </div>
        </div>
      </div>
      <div class="cm-section" id="dg-token-saved-section" style="display:none">
        <div class="cm-note" style="margin-top:0">
          <i class="ti ti-shield-check"></i>
          <span>توکن Railway از قبل ذخیره شده و نیازی به وارد کردن دوباره نیست.
          <a href="javascript:void(0)" onclick="dgChangeToken()" style="color:var(--accent2);font-weight:700">تغییر توکن</a></span>
        </div>
      </div>
      <div class="cm-section" style="margin-bottom:6px">
        <div class="cm-section-label"><i class="ti ti-activity"></i> وضعیت اجرا</div>
        <div class="cm-note" id="dg-status-note">
          <i class="ti ti-info-circle" id="dg-status-icon"></i>
          <span id="dg-status-text">هنوز شروع نشده</span>
        </div>
        <div class="upd-log-box" id="dg-log-box" style="margin-top:10px;max-height:170px;display:none">
          <p class="upd-log-empty">لاگی موجود نیست</p>
        </div>
        <div id="dg-results" style="display:flex;flex-direction:column;gap:6px;margin-top:10px"></div>
      </div>
    </div>
    <div class="cm-footer">
      <button class="cm-btn-cancel" onclick="closeModal('modal-domain-gen')">بستن</button>
      <button class="cm-btn-cancel" id="dg-stop-btn" style="display:none;color:var(--red-t);border-color:rgba(239,68,68,.25)" onclick="stopDomainGen()">
        <i class="ti ti-player-stop"></i> توقف
      </button>
      <button class="cm-btn-submit" id="dg-start-btn" onclick="startDomainGen()">
        <i class="ti ti-player-play"></i> شروع ساخت
      </button>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-bot-tcp-proxy">
  <div class="modal-v2 cm-modal" style="max-width:560px">
    <button class="cm-close" onclick="btpCloseModal()"><i class="ti ti-x"></i></button>

    <div class="cm-head">
      <div class="cm-head-row">
        <div class="cm-head-icon"><i class="ti ti-server-2"></i></div>
        <div>
          <div class="cm-head-title">ساخت TCP Proxy اختصاصی</div>
          <div class="cm-head-sub">اتصال خودکار به Railway و ساخت پروکسی تلگرام</div>
        </div>
      </div>
    </div>

    <div class="cm-body">
      <!-- مرحله ۱: توکن و پورت -->
      <div id="btp-step-input">
        <div class="cm-section">
          <div class="cm-section-label"><i class="ti ti-key"></i> اطلاعات لازم</div>
          <div class="cm-field">
            <label>Railway API Token</label>
            <input class="cm-input" id="btp-token" type="password" placeholder="توکن اکانت یا پروژه‌ی Railway">
          </div>
          <div class="cm-field" id="btp-token-saved-note" style="display:none;margin-bottom:14px">
            <div class="cm-note" style="margin:0">
              <i class="ti ti-shield-check"></i>
              <span>توکن قبلی روی سرور ذخیره است؛ لازم نیست دوباره وارد کنی.
              <a href="javascript:void(0)" onclick="btpChangeToken()" style="color:var(--accent2);font-weight:700">تغییر توکن</a></span>
            </div>
          </div>
          <div class="cm-field" style="margin-bottom:0">
            <label>پورت</label>
            <input class="cm-input" id="btp-port" type="number" placeholder="مثلاً پورت داخلی پروکسی تلگرام">
          </div>
        </div>
      </div>

      <!-- مرحله ۲: هشدار خاموش کردن VPN -->
      <div id="btp-step-vpn" style="display:none;text-align:center;padding:10px 0">
        <i class="ti ti-shield-off" style="font-size:40px;color:var(--amber-t)"></i>
        <div style="font-weight:700;font-size:15px;margin-top:12px">اگر VPN روی این دستگاه روشن است، خاموشش کن</div>
        <div style="color:var(--t3);font-size:12.5px;margin-top:6px">برای این‌که تست اتصال درست انجام شود، باید بدون VPN باشی.</div>
      </div>

      <!-- مرحله ۳: پینگ‌گیری واقعی از دامنه‌ها -->
      <div id="btp-step-ping" style="display:none">
        <div class="cm-note" id="btp-ping-status-note">
          <i class="ti ti-loader-2" id="btp-ping-status-icon" style="animation:spin 1s linear infinite"></i>
          <span id="btp-ping-status-text">در حال تست دامنه‌ها...</span>
        </div>
        <div id="btp-ping-list" style="display:flex;flex-direction:column;gap:5px;margin-top:12px;max-height:260px;overflow-y:auto"></div>
      </div>

      <!-- مرحله ۴: در حال ساخت پروکسی -->
      <div id="btp-step-search" style="display:none">
        <div class="cm-note" id="btp-status-note">
          <i class="ti ti-info-circle" id="btp-status-icon"></i>
          <span id="btp-status-text">در حال جست‌وجو...</span>
        </div>
        <div id="btp-found-list" style="display:flex;flex-direction:column;gap:6px;margin-top:12px;max-height:260px;overflow-y:auto"></div>
      </div>

      <!-- مرحله ۵: نتیجه‌ی نهایی -->
      <div id="btp-step-done" style="display:none;text-align:center;padding:6px 0">
        <i class="ti ti-circle-check" style="font-size:40px;color:var(--green-t)"></i>
        <div style="font-weight:700;font-size:15px;margin-top:12px">پروکسی تلگرام ساخته شد</div>
        <div id="btp-done-domain" style="font-family:ui-monospace,monospace;font-size:12.5px;color:var(--t2);margin-top:8px"></div>
        <div id="btp-done-link-wrap" style="display:none;margin-top:14px">
          <div class="cm-field" style="margin-bottom:0">
            <input class="cm-input" id="btp-done-link" readonly style="text-align:left;direction:ltr;font-family:ui-monospace,monospace;font-size:11.5px">
          </div>
          <button class="btn btn-g" style="margin-top:8px" onclick="btpCopyLink()"><i class="ti ti-copy"></i> کپی لینک پروکسی</button>
        </div>
      </div>
    </div>

    <div class="cm-footer">
      <button class="cm-btn-cancel" id="btp-cancel-btn" onclick="btpCloseModal()">انصراف</button>
      <button class="cm-btn-cancel" id="btp-stop-btn" style="display:none;color:var(--red-t);border-color:rgba(239,68,68,.25)" onclick="stopBotTcpProxy()">
        <i class="ti ti-player-stop"></i> توقف
      </button>
      <button class="cm-btn-submit" id="btp-continue-btn" style="display:none">ادامه</button>
      <button class="cm-btn-submit" id="btp-start-btn" onclick="startBotTcpProxy()">
        <i class="ti ti-player-play"></i> شروع
      </button>
      <button class="cm-btn-submit" id="btp-close-done-btn" style="display:none" onclick="btpCloseModal()">بستن</button>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-zeus-proxy">
  <div class="modal-v2 cm-modal" style="max-width:500px">
    <button class="cm-close" onclick="zpCloseModal()"><i class="ti ti-x"></i></button>

    <div class="cm-head">
      <div class="cm-head-row">
        <div class="cm-head-icon"><i class="ti ti-bolt"></i></div>
        <div>
          <div class="cm-head-title">پروکسی Zeus</div>
          <div class="cm-head-sub">SOCKS5 اختصاصی با محدودیت حجم، انقضا و کنترل اتصال</div>
        </div>
      </div>
    </div>

    <!-- این مودال فقط برای ساخت است؛ بعد از ساخت، پروکسی مثل بقیه‌ی کانفیگ‌ها توی لیست نمایش داده می‌شود -->
    <div class="cm-body">
      <!-- مرحله ۱: توکن + کانفیگ -->
      <div id="zp-step-input">
        <div class="cm-section">
          <div class="cm-section-label"><i class="ti ti-key"></i> توکن Railway</div>
          <div class="cm-field">
            <label>Railway API Token</label>
            <input class="cm-input" id="zp-token" type="password" placeholder="توکن اکانت یا پروژه‌ی Railway">
          </div>
          <div class="cm-field" id="zp-token-saved-note" style="display:none;margin-bottom:0">
            <div class="cm-note" style="margin:0">
              <i class="ti ti-shield-check"></i>
              <span>توکن قبلی روی سرور ذخیره است (مشترک با Bot TCP Proxy)؛ لازم نیست دوباره وارد کنی.
              <a href="javascript:void(0)" onclick="zpChangeToken()" style="color:var(--accent2);font-weight:700">تغییر توکن</a></span>
            </div>
          </div>
        </div>

        <!-- ── کانفیگ‌های پروکسی ── -->
        <div class="cm-section" style="margin-top:10px">
          <div class="cm-section-label"><i class="ti ti-settings"></i> کانفیگ پروکسی</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
            <div class="cm-field" style="margin:0">
              <label>محدودیت حجم (GB)</label>
              <input class="cm-input" id="zp-cfg-traffic" type="number" min="0" step="0.5" placeholder="مثلاً 10 — صفر = نامحدود">
            </div>
            <div class="cm-field" style="margin:0">
              <label>انقضا (روز)</label>
              <input class="cm-input" id="zp-cfg-days" type="number" min="0" step="1" placeholder="مثلاً 30 — صفر = بی‌انقضا">
            </div>
          </div>
          <div class="cm-field" style="margin-top:8px;margin-bottom:0">
            <label>حداکثر اتصال همزمان per IP</label>
            <input class="cm-input" id="zp-cfg-maxip" type="number" min="0" step="1" placeholder="مثلاً 3 — صفر = نامحدود">
          </div>
        </div>
      </div>

      <!-- مرحله ۲: در حال ساخت -->
      <div id="zp-step-building" style="display:none;text-align:center;padding:14px 0">
        <i class="ti ti-loader-2" style="font-size:34px;color:var(--accent);animation:spin 1s linear infinite"></i>
        <div style="font-weight:700;font-size:14.5px;margin-top:12px">در حال ساخت پروکسی...</div>
        <div style="color:var(--t3);font-size:12px;margin-top:4px">سرور SOCKS5 داخلی بالا می‌آید و TCP Proxy روی Railway ساخته می‌شود</div>
      </div>

      <!-- خطا -->
      <div id="zp-step-error" style="display:none">
        <div class="cm-note" style="background:var(--red-bg);border-color:rgba(239,68,68,.3)">
          <i class="ti ti-alert-triangle" style="color:var(--red-t)"></i>
          <span id="zp-error-text"></span>
        </div>
      </div>
    </div>

    <div class="cm-footer">
      <button class="cm-btn-cancel" id="zp-cancel-btn" onclick="zpCloseModal()">انصراف</button>
      <button class="cm-btn-submit" id="zp-start-btn" onclick="zpStart()">
        <i class="ti ti-player-play"></i> ساخت پروکسی
      </button>
    </div>
  </div>
</div>

<!-- مدیریت/ویرایش پروکسی Zeus — از روی کارت آن در لیست کانفیگ‌ها باز می‌شود -->
<div class="modal-bg" id="modal-zeus-manage">
  <div class="modal-v2 cm-modal" style="max-width:500px">
    <button class="cm-close" onclick="zpCloseManage()"><i class="ti ti-x"></i></button>

    <div class="cm-head">
      <div class="cm-head-row">
        <div class="cm-head-icon"><i class="ti ti-bolt"></i></div>
        <div>
          <div class="cm-head-title">مدیریت پروکسی Zeus</div>
          <div class="cm-head-sub">آمار مصرف و ویرایش کانفیگ</div>
        </div>
      </div>
    </div>

    <div class="cm-body">
      <div style="padding:6px 0">
        <div style="text-align:center">
          <i class="ti ti-circle-check" style="font-size:38px;color:var(--green-t)"></i>
          <div style="font-weight:700;font-size:15px;margin-top:10px">پروکسی Zeus فعال است</div>
          <div style="color:var(--t3);font-size:12px;margin-top:4px">این رشته را در فیلد user_socks5 پنل Zeus قرار بده</div>
          <div class="cm-field" style="margin-top:12px;margin-bottom:0">
            <input class="cm-input" id="zp-done-config" readonly style="text-align:left;direction:ltr;font-family:ui-monospace,monospace;font-size:11px">
          </div>
          <button class="btn btn-g" style="margin-top:7px" onclick="zpCopyConfig()"><i class="ti ti-copy"></i> کپی کانفیگ</button>
        </div>

        <!-- آمار لایو -->
        <div style="margin-top:14px;background:var(--card2,var(--card));border-radius:10px;padding:12px 14px">
          <div style="font-weight:700;font-size:12.5px;margin-bottom:8px;color:var(--t2)"><i class="ti ti-chart-bar"></i> آمار مصرف</div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;text-align:center">
            <div>
              <div style="font-size:11px;color:var(--t3)">مصرف حجم</div>
              <div style="font-weight:700;font-size:13px" id="zp-stat-traffic">—</div>
            </div>
            <div>
              <div style="font-size:11px;color:var(--t3)">زمان مانده</div>
              <div style="font-weight:700;font-size:13px" id="zp-stat-expiry">—</div>
            </div>
            <div>
              <div style="font-size:11px;color:var(--t3)">اتصال فعال</div>
              <div style="font-weight:700;font-size:13px" id="zp-stat-conns">—</div>
            </div>
          </div>
          <!-- نوار حجم -->
          <div id="zp-traffic-bar-wrap" style="margin-top:9px;display:none">
            <div style="height:6px;background:var(--border2,#333);border-radius:3px;overflow:hidden">
              <div id="zp-traffic-bar" style="height:100%;background:var(--accent);border-radius:3px;transition:width .4s"></div>
            </div>
            <div style="font-size:10px;color:var(--t3);margin-top:3px;text-align:left" id="zp-traffic-bar-label"></div>
          </div>
        </div>

        <!-- ویرایش کانفیگ زنده -->
        <div style="margin-top:10px;background:var(--card2,var(--card));border-radius:10px;padding:12px 14px">
          <div style="font-weight:700;font-size:12.5px;margin-bottom:8px;color:var(--t2)"><i class="ti ti-adjustments"></i> تنظیم کانفیگ (اعمال فوری)</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
            <div class="cm-field" style="margin:0">
              <label style="font-size:11px">حجم (GB) — صفر=نامحدود</label>
              <input class="cm-input" id="zp-edit-traffic" type="number" min="0" step="0.5">
            </div>
            <div class="cm-field" style="margin:0">
              <label style="font-size:11px">انقضا (روز) — صفر=بی‌انقضا</label>
              <input class="cm-input" id="zp-edit-days" type="number" min="0" step="1">
            </div>
          </div>
          <div class="cm-field" style="margin-top:8px;margin-bottom:8px">
            <label style="font-size:11px">حداکثر اتصال per IP — صفر=نامحدود</label>
            <input class="cm-input" id="zp-edit-maxip" type="number" min="0" step="1">
          </div>
          <button class="btn btn-g" style="width:100%;justify-content:center" onclick="zpSaveConfig()">
            <i class="ti ti-device-floppy"></i> ذخیره کانفیگ
          </button>
        </div>
      </div>
    </div>

    <div class="cm-footer">
      <button class="cm-btn-cancel" onclick="zpCloseManage()">بستن</button>
      <button class="btn" id="zp-delete-btn" style="background:var(--red-bg);color:var(--red-t);border:1px solid rgba(239,68,68,.3);border-radius:8px;padding:0 14px;font-size:13px;font-weight:600;cursor:pointer" onclick="zpDelete()">
        <i class="ti ti-trash"></i> حذف پروکسی
      </button>
    </div>
  </div>
</div>

<!-- آی‌پی‌های متصل به پروکسی Zeus — هر آی‌پی صرف‌نظر از تعداد اتصال‌هایش فقط یک بار شمرده می‌شود -->
<div class="modal-bg" id="modal-zeus-ips">
  <div class="modal-v2 cm-modal" style="max-width:420px">
    <button class="cm-close" onclick="zpCloseIps()"><i class="ti ti-x"></i></button>
    <div class="cm-head">
      <div class="cm-head-row">
        <div class="cm-head-icon"><i class="ti ti-network"></i></div>
        <div>
          <div class="cm-head-title">آی‌پی‌های متصل</div>
          <div class="cm-head-sub" id="zp-ips-sub">هر آی‌پی یک بار شمرده می‌شود</div>
        </div>
      </div>
    </div>
    <div class="cm-body">
      <div id="zp-ips-list" style="display:flex;flex-direction:column;gap:6px"></div>
      <div class="empty" id="zp-ips-empty" style="display:none;padding:20px 0;text-align:center">
        <i class="ti ti-plug-off" style="font-size:26px;color:var(--t3)"></i>
        <p style="margin-top:8px;font-size:12.5px;color:var(--t3)">در حال حاضر هیچ آی‌پی متصل نیست</p>
      </div>
    </div>
    <div class="cm-footer">
      <button class="cm-btn-submit" style="width:100%;justify-content:center" onclick="zpCloseIps()">بستن</button>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-domain-scan">
  <div class="modal-v2 cm-modal" style="max-width:480px">
    <button class="cm-close" onclick="closeModal('modal-domain-scan')"><i class="ti ti-x"></i></button>
    <div class="cm-head">
      <div class="cm-head-row">
        <div class="cm-head-icon"><i class="ti ti-search"></i></div>
        <div>
          <div class="cm-head-title">جستجوی دامنه‌ی دلخواه</div>
          <div class="cm-head-sub">دامنه‌های موردنظرت رو وارد کن، هر بار Enter بزن</div>
        </div>
      </div>
    </div>
    <div class="cm-body">
      <div class="cm-section" id="ds-token-section">
        <div class="cm-field">
          <label>Railway API Token</label>
          <input class="cm-input" id="ds-token" type="password" placeholder="در صورتی که قبلاً ذخیره نشده">
        </div>
      </div>
      <div class="cm-section">
        <div class="cm-field">
          <label>افزودن دامنه</label>
          <input class="cm-input" id="ds-domain-inp" placeholder="مثلاً nozomi.proxy.rlwy.net و Enter بزن"
                 onkeydown="if(event.key==='Enter'){event.preventDefault();dsAddDomain()}">
        </div>
        <div class="cm-pills" id="ds-domain-chips"></div>
      </div>
      <div class="cm-section" style="margin-bottom:6px">
        <div class="cm-note" id="ds-status-note">
          <i class="ti ti-info-circle"></i> <span id="ds-status-text">هنوز شروع نشده</span>
        </div>
        <div class="upd-log-box" id="ds-log-box" style="margin-top:10px;max-height:170px;display:none">
          <p class="upd-log-empty">لاگی موجود نیست</p>
        </div>
      </div>
    </div>
    <div class="cm-footer">
      <button class="cm-btn-cancel" onclick="closeModal('modal-domain-scan')">بستن</button>
      <button class="cm-btn-cancel" id="ds-stop-btn" style="display:none;color:var(--red-t)" onclick="stopDomainScan()"><i class="ti ti-player-stop"></i> توقف</button>
      <button class="cm-btn-submit" id="ds-start-btn" onclick="startDomainScan()"><i class="ti ti-player-play"></i> شروع اسکن</button>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-suggest-domain">
  <div class="modal-v2 cm-modal" style="max-width:420px">
    <button class="cm-close" onclick="closeModal('modal-suggest-domain')"><i class="ti ti-x"></i></button>
    <div class="cm-head">
      <div class="cm-head-row">
        <div class="cm-head-icon" style="background:linear-gradient(135deg,var(--purple),#0EA5E9)"><i class="ti ti-send"></i></div>
        <div>
          <div class="cm-head-title">پیشنهاد دامنه به اپراتور</div>
          <div class="cm-head-sub">دامنه‌ای که سراغ داری رو برای بررسی بفرست</div>
        </div>
      </div>
    </div>
    <div class="cm-body">
      <div class="cm-field">
        <label>دامنه‌ی پیشنهادی</label>
        <input class="cm-input" id="sg-domain" placeholder="مثلاً: nozomi.proxy.rlwy.net">
      </div>
      <div class="cm-field" style="margin-bottom:6px">
        <label>یادداشت (اختیاری)</label>
        <input class="cm-input" id="sg-note" placeholder="مثلاً: با فیلترشکن X کار می‌کنه">
      </div>
      <div class="cm-note" id="sg-status-note">
        <i class="ti ti-info-circle"></i> <span id="sg-status-text">هنوز ارسال نشده</span>
      </div>
    </div>
    <div class="cm-footer">
      <button class="cm-btn-cancel" onclick="closeModal('modal-suggest-domain')">انصراف</button>
      <button class="cm-btn-submit" id="sg-submit-btn" onclick="submitDomainSuggestion()">
        <i class="ti ti-send"></i> ارسال پیشنهاد
      </button>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-create-sub">
  <div class="modal-v2">
    <div class="modal-v2-head">
      <button class="modal-v2-close" onclick="closeModal('modal-create-sub')"><i class="ti ti-x"></i></button>
      <div class="modal-v2-icon"><i class="ti ti-folder-plus"></i></div>
      <div class="modal-v2-title">ساخت گروه جدید</div>
      <div class="modal-v2-sub">یک صفحه پابلیک مجزا برای مدیریت کانفیگ‌ها بسازید</div>
    </div>
    <div class="modal-v2-body">
      <div class="modal-v2-field">
        <label><i class="ti ti-tag"></i> نام گروه</label>
        <input class="modal-v2-input" id="ns-name" placeholder="مثلاً: کانال تلگرام">
      </div>
      <div class="modal-v2-field" id="ns-target-wrap" style="display:none">
        <label><i class="ti ti-topology-star-3"></i> پنل مقصد</label>
        <select class="modal-v2-input" id="ns-target"><option value="">این پنل</option></select>
      </div>
      <div class="modal-v2-field">
        <label><i class="ti ti-align-left"></i> توضیحات (اختیاری)</label>
        <input class="modal-v2-input" id="ns-desc" placeholder="توضیح کوتاه درباره این گروه">
      </div>
      <div class="modal-v2-field" style="margin-bottom:0">
        <label><i class="ti ti-lock"></i> رمز صفحه پابلیک (اختیاری)</label>
        <input class="modal-v2-input" id="ns-pw" type="password" placeholder="خالی بگذارید = بدون رمز">
      </div>
      <div class="cl" style="margin-top:14px"><i class="ti ti-info-circle"></i><span>صفحه پابلیک این گروه با یک لینک منحصر‌به‌فرد در اینترنت در دسترس خواهد بود.</span></div>
      <div class="modal-v2-footer">
        <button class="btn btn-o" onclick="closeModal('modal-create-sub')" style="flex:.6">انصراف</button>
        <button class="btn btn-pur" onclick="createSub()"><i class="ti ti-folder-plus"></i> ساخت گروه</button>
      </div>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-node-key">
  <div class="modal-v2 cm-modal" style="max-width:560px">
    <div class="modal-v2-head">
      <button class="modal-v2-close" onclick="closeModal('modal-node-key')"><i class="ti ti-x"></i></button>
      <div class="modal-v2-icon"><i class="ti ti-key"></i></div>
      <div class="modal-v2-title">ساخت کلید اتصال</div>
      <div class="modal-v2-sub">این کلید را در پنل دیگر، بخش «متصل کردن» وارد کنید</div>
    </div>
    <div class="modal-v2-body">
      <div class="modal-v2-field">
        <label><i class="ti ti-tag"></i> برچسب کلید (اختیاری)</label>
        <input class="modal-v2-input" id="nk-label" placeholder="مثلاً: پنل تهران">
      </div>
      <div class="modal-v2-field">
        <label><i class="ti ti-shield-check"></i> دسترسی‌های این کلید</label>
        <div class="nk-perm-grid" id="nk-perms">
          <div class="nk-perm-tile on" data-perm="usage" onclick="toggleNkPerm(this)">
            <div class="nk-perm-tile-ic"><i class="ti ti-transfer"></i></div>
            <div class="nk-perm-tile-txt"><div class="nk-perm-tile-name">مصرف</div><div class="nk-perm-tile-desc">حجم و اتصال‌های فعال</div></div>
          </div>
          <div class="nk-perm-tile on" data-perm="links" onclick="toggleNkPerm(this)">
            <div class="nk-perm-tile-ic"><i class="ti ti-link"></i></div>
            <div class="nk-perm-tile-txt"><div class="nk-perm-tile-name">کانفیگ‌ها</div><div class="nk-perm-tile-desc">فهرست لینک‌های ساخته‌شده</div></div>
          </div>
          <div class="nk-perm-tile on" data-perm="subs" onclick="toggleNkPerm(this)">
            <div class="nk-perm-tile-ic"><i class="ti ti-folders"></i></div>
            <div class="nk-perm-tile-txt"><div class="nk-perm-tile-name">گروه‌های ساب</div><div class="nk-perm-tile-desc">فهرست گروه‌بندی‌ها</div></div>
          </div>
          <div class="nk-perm-tile on" data-perm="requests" onclick="toggleNkPerm(this)">
            <div class="nk-perm-tile-ic"><i class="ti ti-arrows-exchange"></i></div>
            <div class="nk-perm-tile-txt"><div class="nk-perm-tile-name">درخواست‌ها</div><div class="nk-perm-tile-desc">تعداد ریکوئست و خطا</div></div>
          </div>
          <div class="nk-perm-tile" data-perm="logs" onclick="toggleNkPerm(this)">
            <div class="nk-perm-tile-ic"><i class="ti ti-history"></i></div>
            <div class="nk-perm-tile-txt"><div class="nk-perm-tile-name">لاگ‌ها</div><div class="nk-perm-tile-desc">تاریخچه‌ی فعالیت پنل</div></div>
          </div>
          <div class="nk-perm-tile manage" data-perm="manage" onclick="toggleNkPerm(this)">
            <div class="nk-perm-tile-ic"><i class="ti ti-writing"></i></div>
            <div class="nk-perm-tile-txt"><div class="nk-perm-tile-name">ویرایش/حذف از راه دور</div><div class="nk-perm-tile-desc">تغییر کانفیگ‌های این پنل</div></div>
          </div>
        </div>
      </div>
      <div class="modal-v2-field">
        <label><i class="ti ti-lock"></i> رمز روی توکن (اختیاری)</label>
        <input class="modal-v2-input" id="nk-password" type="password" placeholder="خالی بگذارید = بدون رمز">
      </div>
      <div id="nk-result" style="display:none">
        <div class="vl-code" id="nk-key" style="margin-top:6px">—</div>
        <div style="display:flex;gap:8px;margin-top:10px">
          <button class="btn btn-p" onclick="cpText('nk-key')"><i class="ti ti-copy"></i> کپی کلید</button>
        </div>
      </div>
      <div class="cl amber"><i class="ti ti-shield-lock"></i><span>این کلید فقط به بخش‌های تیک‌خورده دسترسی می‌دهد؛ بدون «ویرایش/حذف از راه دور»، دارنده‌ی کلید فقط می‌تواند بخواند. هر زمان می‌توانید از لیست پایین غیرفعال یا حذفش کنید.</span></div>
      <div class="modal-v2-footer">
        <button class="btn btn-o" onclick="closeModal('modal-node-key')" style="flex:.6">بستن</button>
        <button class="btn btn-p" id="nk-gen-btn" onclick="genNodeKey()"><i class="ti ti-key"></i> ساخت کلید</button>
      </div>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-node-connect">
  <div class="modal-v2 cm-modal" style="max-width:560px">
    <div class="modal-v2-head" style="background:linear-gradient(155deg,rgba(34,197,94,.16) 0%,transparent 65%)">
      <button class="modal-v2-close" onclick="closeModal('modal-node-connect')"><i class="ti ti-x"></i></button>
      <div class="modal-v2-icon" style="background:linear-gradient(135deg,var(--green),#15803D)"><i class="ti ti-plug-connected"></i></div>
      <div class="modal-v2-title">متصل شدن به یک نود</div>
      <div class="modal-v2-sub">کلیدی که پنل مقابل ساخته را اینجا پیست کنید</div>
    </div>
    <div class="modal-v2-body">
      <div class="modal-v2-field">
        <label><i class="ti ti-key"></i> کلید اتصال</label>
        <textarea class="modal-v2-input" id="nc-key" rows="3" style="resize:vertical;direction:ltr;font-family:ui-monospace,Menlo,monospace;font-size:11px" placeholder="rvg-..." oninput="previewNodeKey()"></textarea>
        <div class="nc-host-chip"><i class="ti ti-server-2"></i><span id="nc-host-preview">دامنه‌ی پنل مقابل اینجا نمایش داده می‌شود</span></div>
      </div>
      <div class="modal-v2-field">
        <label><i class="ti ti-tag"></i> نام نمایشی نود (اختیاری)</label>
        <input class="modal-v2-input" id="nc-label" placeholder="مثلاً: نود آلمان">
      </div>
      <div class="modal-v2-field" style="margin-bottom:0">
        <label><i class="ti ti-lock"></i> رمز نود (فقط اگر روی این توکن رمز گذاشته شده)</label>
        <input class="modal-v2-input" id="nc-password" type="password" placeholder="اگر رمز نمی‌دانید خالی بگذارید">
      </div>
      <div class="cl"><i class="ti ti-info-circle"></i><span>دامنه‌ی پنل مقابل از داخل خود کلید خوانده می‌شود. بعد از اتصال می‌توانید با تیک‌ها مشخص کنید کدام اطلاعات ادغام و استفاده شود.</span></div>
      <div id="nc-error" style="display:none;align-items:flex-start;gap:7px;margin-top:11px;background:var(--red-bg);border:1px solid rgba(239,68,68,.3);border-radius:11px;padding:9px 12px;font-size:11px;color:var(--red-t);line-height:1.6"><i class="ti ti-alert-circle" style="font-size:14px;margin-top:1px;flex-shrink:0"></i><span></span></div>
      <div class="modal-v2-footer">
        <button class="btn btn-o" onclick="closeModal('modal-node-connect')" style="flex:.6">انصراف</button>
        <button class="btn btn-g" id="nc-btn" onclick="connectNode()"><i class="ti ti-plug-connected"></i> اتصال</button>
      </div>
    </div>
  </div>
</div>
<div class="modal-bg" id="modal-edit-link">
  <div class="modal-v2 cm-modal">
    <div class="modal-v2-head">
      <button class="modal-v2-close" onclick="closeModal('modal-edit-link')"><i class="ti ti-x"></i></button>
      <div class="modal-v2-icon"><i class="ti ti-edit"></i></div>
      <div class="modal-v2-title">ویرایش کانفیگ</div>
      <div class="modal-v2-sub">مشخصات کانفیگ انتخاب‌شده را تغییر دهید</div>
    </div>
    <div class="modal-v2-body">
      <input type="hidden" id="el-uuid">
      <input type="hidden" id="el-node-id">
      <div class="fg" id="el-node-notice" style="display:none;margin-bottom:13px"></div>
      <div class="modal-v2-field"><label><i class="ti ti-tag"></i> عنوان</label><input class="modal-v2-input" id="el-label"></div>
      <div class="form-row" style="display:flex;gap:10px">
        <div class="modal-v2-field" style="flex:1"><label><i class="ti ti-database"></i> سهمیه (0 = نامحدود)</label><input class="modal-v2-input" id="el-val" type="number" min="0" step="0.1"></div>
        <div class="modal-v2-field" style="flex:.6"><label><i class="ti ti-ruler"></i> واحد</label><select class="modal-v2-input fs" id="el-unit"><option value="GB">GB</option><option value="MB">MB</option></select></div>
      </div>
      <div class="modal-v2-field"><label><i class="ti ti-calendar-time"></i> انقضا (روز از الان، 0 = بدون تغییر/نامحدود)</label><input class="modal-v2-input" id="el-exp" type="number" min="0" step="1"></div>
      <div class="modal-v2-field" style="margin-bottom:0"><label><i class="ti ti-note"></i> یادداشت</label><input class="modal-v2-input" id="el-note"></div>
      <div class="modal-v2-hint" style="margin-top:11px"><i class="ti ti-info-circle"></i><span>برای حفظ انقضای فعلی، فیلد انقضا را صفر بگذارید.</span></div>
      <div class="modal-v2-footer">
        <button class="modal-v2-btn-cancel" onclick="closeModal('modal-edit-link')">انصراف</button>
        <button class="modal-v2-btn-submit" onclick="saveEditLink()"><i class="ti ti-check"></i> ذخیره تغییرات</button>
      </div>
    </div>
  </div>
</div>
<div class="mob-top">
  <div class="ml">
    <div class="mob-logo"><svg viewBox="0 0 100 100" width="100%" height="100%" role="img" aria-label="EMIX logo"><rect width="100" height="100" fill="#030303"/><circle cx="50" cy="48" r="45" fill="#0B0B0B" stroke="#5A160E" stroke-width="2"/><circle cx="50" cy="48" r="42" fill="none" stroke="#FF3B24" stroke-width="1" opacity=".7"/><path d="M72 24H39C29 24 23 30 23 40V61C23 71 29 77 39 77H73M39 50H64C72 50 76 46 80 39" fill="none" stroke="#7A170F" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" opacity=".6"/><path d="M72 24H39C29 24 23 30 23 40V61C23 71 29 77 39 77H73M39 50H64C72 50 76 46 80 39" fill="none" stroke="#FF4028" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/><text x="50" y="91" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" font-weight="800" letter-spacing="3" fill="#FF3B24">EMIX</text></svg></div>
    <span class="mob-title">EMIX</span>
  </div>
  <div class="mob-right">
    <button class="theme-mob" id="theme-mob-btn" onclick="toggleTheme()"><i class="ti ti-sun" id="theme-mob-icon"></i></button>
    <button class="menu-btn" id="open-sb"><i class="ti ti-menu-2"></i></button>
  </div>
</div>
<div class="overlay" id="overlay"></div>
<aside class="sidebar" id="sb">
  <button class="sb-close" id="close-sb"><i class="ti ti-x"></i></button>
  <div class="logo">
    <div class="logo-img"><svg viewBox="0 0 100 100" width="100%" height="100%" role="img" aria-label="EMIX logo"><rect width="100" height="100" fill="#030303"/><circle cx="50" cy="48" r="45" fill="#0B0B0B" stroke="#5A160E" stroke-width="2"/><circle cx="50" cy="48" r="42" fill="none" stroke="#FF3B24" stroke-width="1" opacity=".7"/><path d="M72 24H39C29 24 23 30 23 40V61C23 71 29 77 39 77H73M39 50H64C72 50 76 46 80 39" fill="none" stroke="#7A170F" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" opacity=".6"/><path d="M72 24H39C29 24 23 30 23 40V61C23 71 29 77 39 77H73M39 50H64C72 50 76 46 80 39" fill="none" stroke="#FF4028" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/><text x="50" y="91" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" font-weight="800" letter-spacing="3" fill="#FF3B24">EMIX</text></svg></div>
    <div><div class="logo-name">EMIX</div><div class="logo-sub" id="logo-ver-chip">Gateway · v11</div></div>
  </div>
  <div class="nav-wrap">
    <div class="nav-sec">پنل</div>
    <div class="nav-it on" data-pg="overview"><i class="ti ti-layout-dashboard"></i> داشبورد</div>
    <div class="nav-it" data-pg="links"><i class="ti ti-link-plus"></i> کانفیگ‌ها <span class="nav-badge" id="links-nb">0</span></div>
    <div class="nav-it" data-pg="builder" style="background:linear-gradient(135deg,rgba(167,139,250,.16),rgba(139,92,246,.08))"><i class="ti ti-wand" style="color:#A78BFA"></i> ✨ ساخت کانفیگ <span class="nav-badge" style="background:#A78BFA;color:#fff">یکپارچه</span></div>
    <div class="nav-it" data-pg="bridge"><i class="ti ti-flag"></i> پل ایران <span class="nav-badge" id="bridge-nb" style="display:none">فعال</span></div>
    <div class="nav-it" data-pg="zeus"><i class="ti ti-bolt" style="color:var(--amber-t)"></i> ⚡ ZEUS Pro <span class="nav-badge" id="zeus-nb" style="background:var(--amber-t);color:#fff">جدید</span></div>
    <div class="nav-it" data-pg="gaming"><i class="ti ti-device-gamepad-2" style="color:#4cc9f0"></i> 🎮 گیمینگ <span class="nav-badge" id="gaming-nb" style="background:#4cc9f0;color:#08131f">پینگ</span></div>
    <div class="nav-it" data-pg="multiloc" style="background:linear-gradient(135deg,rgba(16,185,129,.15),rgba(76,201,240,.08))"><i class="ti ti-world" style="color:#10B981"></i> 🌐 پل چندلوکیشن <span class="nav-badge" id="ml-nb" style="background:#10B981;color:#fff">v2</span></div>
    <!-- Audit fix: VPN Pro بازگردانده شد با برچسب صادقانه — پنل فقط control-plane
         است (روی Railway امکان میزبانی WG/OpenVPN runtime نیست؛ مدیریت نود VPS
         و تولید کانفیگ کلاینت واقعی است). تولید کلیدها حالا در restart هم می‌ماند. -->
    <div class="nav-it" data-pg="vpn"><i class="ti ti-shield-lock" style="color:#4ADE80"></i> 🛡 VPN Pro <span class="nav-badge" id="vpn-nb" style="background:#4ADE80;color:#14141C">WG+OVPN · کنترل-پلن</span></div>
    <div class="nav-it" data-pg="routing"><i class="ti ti-route" style="color:#F97316"></i> 🇮🇷 مسیریابی هوشمند <span class="nav-badge" id="routing-nb" style="background:#F97316;color:#fff">Direct</span></div>
    <div class="nav-it" data-pg="iranproxy"><i class="ti ti-flag" style="color:#EF4444"></i> 🇮🇷 پروکسی ایران <span class="nav-badge" id="iranproxy-nb" style="display:none">—</span></div>
    <div class="nav-it" data-pg="accounts"><i class="ti ti-users" style="color:#38BDF8"></i> 👤 حساب‌ها <span class="nav-badge" id="accounts-nb">0</span></div>
    <div class="nav-it" data-pg="subgroups"><i class="ti ti-folders"></i> گروه‌های ساب <span class="nav-badge" id="subs-nb">0</span></div>
    <div class="nav-it" data-pg="subscriptions"><i class="ti ti-rss"></i> سابسکریپشن</div>
    <div class="nav-it" data-pg="traffic"><i class="ti ti-chart-area"></i> ترافیک</div>
    <div class="nav-it" data-pg="connections"><i class="ti ti-plug-connected"></i> اتصالات <span class="nav-badge" id="conns-nb">0</span></div>
    <div class="nav-it" data-pg="nodes"><i class="ti ti-topology-star-3"></i> نود <span class="nav-badge" id="nodes-nb">0</span></div>
    <div class="nav-sec">سیستم</div>
    <div class="nav-it" data-pg="backup"><i class="ti ti-database-export"></i> بکاپ‌گیری</div>
    <div class="nav-it" data-pg="updates"><i class="ti ti-cloud-download"></i> نسخه و بروزرسانی <span class="nav-badge" id="update-nb" style="display:none">1</span></div>
    <div class="nav-it" data-pg="support"><i class="ti ti-headset"></i> پشتیبانی <span class="nav-badge" id="support-nb" style="display:none">●</span></div>
    <div class="nav-it" data-pg="logs"><i class="ti ti-history"></i> لاگ فعالیت‌ها</div>
    <div class="nav-it" data-pg="errors"><i class="ti ti-alert-triangle"></i> خطاها</div>
    <div class="nav-it" data-pg="diag"><i class="ti ti-activity-heartbeat" style="color:#10B981"></i> 🩺 سلامت و تشخیص</div>
    <div class="nav-it" data-pg="settings"><i class="ti ti-settings"></i> تنظیمات</div>
    <div class="nav-it" data-pg="experimental" style="background:linear-gradient(135deg,rgba(139,92,246,.18),rgba(250,204,21,.10));border-top:1px solid rgba(139,92,246,.3);margin-top:8px"><i class="ti ti-flask" style="color:#8B5CF6"></i> 🧪 بخش آزمایشی <span class="nav-badge" id="exp-nb" style="background:#8B5CF6;color:#fff">جدید</span></div>
    <div class="nav-it" data-pg="unified-configs"><i class="ti ti-grid-dots" style="color:#FACC15"></i> 🎯 همه‌ی کانفیگ‌ها</div>
  </div>
  <div class="sb-foot">
    <button class="theme-btn" onclick="toggleTheme()"><i class="ti ti-moon" id="theme-icon"></i> <span id="theme-label">تم روشن</span></button>
    <a class="tg-btn" href="https://t.me/emixpi" target="_blank" rel="noopener"><i class="ti ti-brand-telegram"></i> @emixpi</a>
    <button class="logout-btn" id="logout-btn"><i class="ti ti-logout"></i> خروج</button>
  </div>
</aside>
<main class="main">
<div class="ann-banner-wrap" id="ann-banner-wrap"></div>
<section class="pg on" id="pg-overview">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-layout-dashboard"></i> داشبورد</div><div class="tb-sub" id="last-upd">در حال بارگذاری...</div></div>
    <div class="tb-right">
      <span class="badge bg-green"><span class="dot dg pulse"></span> فعال</span>
      <span class="badge bg-blue" id="uptime-badge">—</span>
      <button class="btn btn-p btn-sm" onclick="refreshAll()"><i class="ti ti-refresh"></i> رفرش</button>
    </div>
  </div>

  <!-- هشدار volume — فقط وقتی دیتا دائمی نیست نمایش داده می‌شود -->
  <div id="volume-warn" class="card" style="margin-bottom:14px;border:1px solid var(--amber-t);display:none">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <i class="ti ti-database-off" style="font-size:22px;color:var(--amber-t)"></i>
      <div style="flex:1;min-width:220px">
        <div style="font-weight:700;font-size:12.5px;color:var(--amber-t)">⚠ دیتای شما هنوز دائمی نیست — حجم (Volume) متصل نشده</div>
        <div style="font-size:11px;color:var(--t3);margin-top:3px">بدون volume، با هر دیپلوی یا ری‌استارت، همه‌ی کانفیگ‌ها و تنظیمات پاک می‌شوند. با یک کلیک volume بسازید (نیازمند توکن Railway که قبلاً ذخیره شده).</div>
      </div>
      <button class="btn btn-g" onclick="ensureVolume(this)"><i class="ti ti-database-plus"></i> ساخت خودکار Volume</button>
    </div>
  </div>

  <!-- کارت سلامت کلی سیستم -->
  <div class="card" style="margin-bottom:14px">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px">
      <i class="ti ti-heartbeat" style="font-size:20px;color:var(--green-t)"></i>
      <div style="flex:1;min-width:180px">
        <div style="font-weight:700;font-size:13px">سلامت کلی پنل</div>
        <div style="font-size:11px;color:var(--t3)">بررسی همه‌ی بخش‌ها تا خروجی: ماژول‌ها، دیتا، پروکسی‌ها، گیت‌وی کلادفلر و پل</div>
      </div>
      <button class="btn btn-g" id="health-all-btn" onclick="runHealthAll(this)"><i class="ti ti-stethoscope"></i> بررسی سلامت همه‌چیز</button>
    </div>
    <div id="health-all-result" style="display:none"></div>
  </div>

  <div class="metrics">
    <div class="metric"><div class="m-icon"><i class="ti ti-plug-connected"></i></div><div class="m-label">اتصالات فعال</div><div class="m-val" id="m-conns">—</div><div class="m-sub"><span class="dot dg pulse"></span> WebSocket / XHTTP زنده</div></div>
    <div class="metric"><div class="m-icon"><i class="ti ti-transfer"></i></div><div class="m-label">کل ترافیک</div><div class="m-val" id="m-traffic">—<span class="m-unit">MB</span></div><div class="m-sub">از راه‌اندازی</div></div>
    <div class="metric suc"><div class="m-icon suc"><i class="ti ti-link"></i></div><div class="m-label">کانفیگ فعال</div><div class="m-val" id="m-alinks">—</div><div class="m-sub" id="m-lsub">از کل</div></div>
    <div class="metric pur"><div class="m-icon pur"><i class="ti ti-folders"></i></div><div class="m-label">گروه‌های ساب</div><div class="m-val" id="m-subs">—</div><div class="m-sub">فعال</div></div>
  </div>
  <div class="vless-box">
    <div class="vl-header">
      <div class="vl-title"><i class="ti ti-link"></i> لینک پیش‌فرض (بدون محدودیت)</div>
      <span class="badge bg-blue"><span class="dot db"></span> TLS 443 · WS</span>
    </div>
    <div class="vl-code" id="vless-main">در حال دریافت...</div>
    <div class="vl-actions">
      <button class="btn btn-p" onclick="cpText('vless-main')"><i class="ti ti-copy"></i> کپی</button>
      <button class="btn btn-g" onclick="qrFor('vless-main')"><i class="ti ti-qrcode"></i> QR</button>
      <button class="btn btn-o" onclick="navTo('links')"><i class="ti ti-link-plus"></i> کانفیگ محدود</button>
      <button class="btn btn-pur" onclick="navTo('subgroups')"><i class="ti ti-folders"></i> گروه‌های ساب</button>
    </div>
  </div>

  <!-- ═══ کارت دسترسی سریع به ZEUS Pro ═══ -->
  <div class="zeus-quick" style="margin-top:18px;background:linear-gradient(135deg,rgba(245,158,11,.10),rgba(139,92,246,.06));border:1px solid var(--amber-t);border-radius:14px;padding:18px;display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;animation:fadeup .5s cubic-bezier(.16,1,.3,1) .15s backwards">
    <div style="display:flex;align-items:center;gap:14px;flex:1;min-width:240px">
      <div style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#FACC15,#EF4444);display:flex;align-items:center;justify-content:center;flex-shrink:0">
        <i class="ti ti-bolt" style="font-size:26px;color:#fff"></i>
      </div>
      <div>
        <div style="font-size:15px;font-weight:800;color:var(--t1);display:flex;align-items:center;gap:8px">
          ⚡ ZEUS Pro — تنظیمات حرفه‌ای
          <span class="badge bg-amber" style="font-size:9px">جدید</span>
        </div>
        <div style="font-size:12px;color:var(--t3);margin-top:3px;line-height:1.6">
          انتخاب ISP همراه اول/ایرانسل/مخابرات + TLS Mask پیشرفته + حالت هوشمند + قفل لاگین
        </div>
      </div>
    </div>
    <button class="btn btn-p" style="background:linear-gradient(135deg,#FACC15,#EF4444);font-weight:700;padding:11px 18px" onclick="navTo('zeus')">
      <i class="ti ti-arrow-left"></i> ورود به ZEUS Pro
    </button>
  </div>
  <div class="g3">
    <div class="card"><div class="card-title"><i class="ti ti-chart-area"></i> ترافیک ساعتی (MB)</div><div class="ch"><canvas id="ch1"></canvas></div></div>
    <div class="card"><div class="card-title"><i class="ti ti-chart-donut"></i> توزیع</div><div class="ch-sm"><canvas id="ch2"></canvas></div></div>
  </div>
  <div class="g2">
    <div class="card">
      <div class="card-title"><i class="ti ti-activity"></i> وضعیت سرویس <span class="ml-auto" style="font-size:9.5px;color:var(--t3)">زنده از Diagnostics</span></div>
      <!-- Audit fix: قبلاً ۶ ردیف «فعال» hardcoded بود (بدون هیچ API).
           حالا همه‌ی مقادیر از /api/diagnostics (واقعی) می‌آیند. -->
      <div class="sr"><span class="sr-k"><i class="ti ti-shield-check"></i> UUID Auth</span><span class="sr-v" style="color:var(--green-t)">● فعال · لایه‌ی relay</span></div>
      <div class="sr"><span class="sr-k"><i class="ti ti-keyframe"></i> موتور سلامت شبکه</span><span class="sr-v" id="svc-health">—</span></div>
      <div class="sr"><span class="sr-k"><i class="ti ti-route"></i> گره‌های تحت مدیریت</span><span class="sr-v" id="svc-nodes">—</span></div>
      <div class="sr"><span class="sr-k"><i class="ti ti-cpu"></i> ران‌تایم‌های تحت نظارت</span><span class="sr-v" id="svc-runtimes">—</span></div>
      <div class="sr"><span class="sr-k"><i class="ti ti-clock-play"></i> جاب‌های پس‌زمینه</span><span class="sr-v" id="svc-jobs">—</span></div>
      <div class="sr"><span class="sr-k"><i class="ti ti-database"></i> پایداری داده</span><span class="sr-v" id="svc-persist">—</span></div>
      <div class="sr"><span class="sr-k"><i class="ti ti-list-tree"></i> ترکیب‌های معتبر پروتکل×حمل‌ونقل</span><span class="sr-v" id="svc-transports">—</span></div>
      <div class="sr"><span class="sr-k"><i class="ti ti-clock"></i> آپتایم</span><span class="sr-v" id="uptime-inline">—</span></div>
      <div class="sr" style="flex-direction:column;align-items:flex-start;gap:4px">
        <div style="width:100%;display:flex;justify-content:space-between"><span class="sr-k"><i class="ti ti-gauge"></i> بار نسبی</span><span class="sr-v" id="bw-pct">—%</span></div>
        <div class="spbar" style="width:100%"><div class="spfill" id="bw-bar" style="width:0%"></div></div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">
        <i class="ti ti-trophy" style="color:var(--amber-t)"></i> پیشنهاد هوشمند — سریع‌ترین کانفیگ
        <span class="ml-auto"><button class="btn btn-g btn-sm" onclick="bestConfigTest(this)"><i class="ti ti-bolt"></i> تست زنده</button></span>
      </div>
      <div id="best-list"><div class="sr"><span class="sr-k" style="color:var(--t3)">دکمه‌ی «تست زنده» را بزنید تا همه‌ی کانفیگ‌ها تست شوند و سریع‌ترین‌ها رتبه‌بندی شوند</span></div></div>
    </div>
  </div>
  <div class="dash-footer">
    <span class="df-text">EMIX PRO · <span id="footer-ver">v11</span> · Railway · ZEUS + گیمینگ + ضدد ضریب + چندلوکیشن</span>
    <a class="df-link" href="https://t.me/emixpi" target="_blank"><i class="ti ti-brand-telegram"></i> t.me/emixpi</a>
  </div>
</section>
<section class="pg" id="pg-links">
  <div class="topbar">
    <div style="display:flex;justify-content:flex-end;gap:8px;margin-bottom:16px;flex-wrap:wrap">
      <button class="btn btn-p" onclick="openModal('modal-create-link')">
        <i class="ti ti-square-rounded-plus"></i> ساخت کانفیگ جدید
      </button>
      <button class="btn btn-g" style="margin-right:14px" onclick="openModal('modal-bot-tcp-proxy');btpCheckTokenState()">
        <i class="ti ti-server-2"></i> Bot tcp proxy
      </button>
      <button class="btn btn-g" id="zeus-nav-btn" style="margin-right:8px" onclick="openModal('modal-zeus-proxy');zpCheckTokenState()">
        <i class="ti ti-bolt"></i> Zeus proxy
      </button>
      <button class="btn btn-g" id="ping-all-btn" style="margin-right:8px" onclick="pingAllLinks(this)">
        <i class="ti ti-activity-heartbeat"></i> تست پینگ همه
      </button>
    </div>
    <div class="tb-right">
      <label class="links-selectall" id="links-selectall-wrap" style="display:none">
        <div class="cfg-check" id="links-selectall-check" onclick="toggleSelectAllLinks()"><i class="ti ti-check"></i></div>
        انتخاب همه
      </label>
      <span class="badge bg-blue" id="links-pg-cnt">۰ کانفیگ</span>
    </div>
  </div>

  <div class="links-bulkbar" id="links-bulkbar">
    <div class="links-bulkbar-count"><i class="ti ti-checks"></i> <span id="links-bulkbar-n">۰</span> کانفیگ انتخاب شده</div>
    <div class="links-bulkbar-actions">
      <button class="btn btn-sm btn-g" onclick="clearLinkSelection()"><i class="ti ti-x"></i> لغو انتخاب</button>
      <button class="btn btn-sm btn-d" onclick="bulkDeleteLinks()"><i class="ti ti-trash"></i> حذف انتخاب‌شده‌ها</button>
    </div>
  </div>

  <div class="info-strip">
    <div class="info-item">
      <!-- Audit fix: split up/down در stats وجود ندارد؛ برچسب به داده‌ی واقعی (ترافیک این ساعت) تغییر کرد -->
      <span class="info-item-label">ترافیک این ساعت</span>
      <span class="info-item-val"><i class="ti ti-clock-bolt"></i> <span id="info-sent-recv">0 B</span></span>
    </div>
    <div class="info-item">
      <span class="info-item-label">مصرف ۲۴ ساعت اخیر</span>
      <span class="info-item-val"><i class="ti ti-chart-pie"></i> <span id="info-usage">0 B</span></span>
    </div>
    <div class="info-item">
      <span class="info-item-label">مصرف کل از ابتدا</span>
      <span class="info-item-val"><i class="ti ti-history"></i> <span id="info-alltime">0 B</span></span>
    </div>
    <div class="info-item">
      <span class="info-item-label">تعداد این‌باندها</span>
      <span class="info-item-val"><i class="ti ti-list-details"></i> <span id="info-inbounds">0</span></span>
    </div>
    <div class="info-item">
      <span class="info-item-label">کلاینت‌ها</span>
      <span class="info-item-val"><i class="ti ti-users"></i> <span class="info-badge" id="info-clients">0</span></span>
    </div>
  </div>

  <div class="cfg-grid" id="links-grid"></div>
  <div class="empty" id="links-empty" style="display:none"><i class="ti ti-link-off"></i><p>هنوز کانفیگی وجود ندارد</p></div>
</section>

<!-- ════════════════════════ پل ایران ════════════════════════ -->
<section class="pg" id="pg-bridge">
  <div class="node-hero" style="margin-bottom:18px">
    <div class="node-hero-top">
      <div class="node-hero-title">
        <div class="node-hero-icon"><i class="ti ti-flag"></i></div>
        <div>
          <div class="tb-title">پل ایران — مصرف داخلی + شتاب‌دهی</div>
          <div class="tb-sub">ضریب ۲.۷ اپراتور فقط روی ترافیک بین‌المللی اعمال می‌شود؛ با این پل، مسیر شما داخلی می‌شود</div>
        </div>
      </div>
      <div class="tb-right">
        <span class="badge bg-blue" id="bridge-status-badge">غیرفعال</span>
      </div>
    </div>
    <div class="node-hero-metrics">
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-route"></i><span class="node-metric-label">مسیر بدون پل</span></div>
        <div class="node-metric-val" style="font-size:15px">گوشی ──✈──► Railway</div>
        <div class="node-metric-sub" style="color:var(--red-t)">بین‌المللی · ضریب ۲.۷</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-flag"></i><span class="node-metric-label">مسیر با پل</span></div>
        <div class="node-metric-val" style="font-size:15px">گوشی ─► ایران ─► Railway</div>
        <div class="node-metric-sub" style="color:var(--green-t)">داخلی · ضریب ۱ + سرعت بهتر</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-bolt"></i><span class="node-metric-label">وضعیت پل</span></div>
        <div class="node-metric-val" id="bridge-metric-status">—</div>
        <div class="node-metric-sub" id="bridge-metric-sub">تست نشده</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-clock-pause"></i><span class="node-metric-label">تاخیر پل</span></div>
        <div class="node-metric-val" id="bridge-metric-ms">—</div>
        <div class="node-metric-sub">هندشیک TLS از مسیر پل</div>
      </div>
    </div>
  </div>

  <!-- انتخاب روش پل -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-routes"></i> انتخاب روش پل</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px" id="br-mode-cards">
    <div class="card br-mode-card" id="br-mode-vps" onclick="brSetMode('vps')" style="cursor:pointer">
      <div style="display:flex;align-items:center;gap:12px">
        <div style="width:44px;height:44px;border-radius:12px;background:var(--accent-d);display:flex;align-items:center;justify-content:center;flex-shrink:0"><i class="ti ti-server-2" style="font-size:22px;color:var(--accent2)"></i></div>
        <div style="flex:1">
          <div style="font-weight:700;font-size:13.5px">🖥 سرور شخصی ایران (VPS)</div>
          <div style="font-size:10.5px;color:var(--t3);margin-top:3px">کنترل کامل · پورت دلخواه · مناسب مصرف سنگین</div>
        </div>
        <div class="br-mode-check" style="width:20px;height:20px;border-radius:50%;border:2px solid var(--t3);display:flex;align-items:center;justify-content:center"><i class="ti ti-check" style="font-size:12px;opacity:0"></i></div>
      </div>
      <div style="font-size:10px;color:var(--t3);margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
        <span class="cfg-sub-tag">هزینه: VPS ماهانه</span>
        <span class="cfg-sub-tag">پهنای باند: نامحدود VPS</span>
        <span class="cfg-sub-tag">راه‌اندازی: ۳ دقیقه</span>
      </div>
    </div>
    <div class="card br-mode-card" id="br-mode-cdn" onclick="brSetMode('cdn')" style="cursor:pointer">
      <div style="display:flex;align-items:center;gap:12px">
        <div style="width:44px;height:44px;border-radius:12px;background:var(--green-bg);display:flex;align-items:center;justify-content:center;flex-shrink:0"><i class="ti ti-cloud" style="font-size:22px;color:var(--green-t)"></i></div>
        <div style="flex:1">
          <div style="font-weight:700;font-size:13.5px">🌐 CDN ایرانی (نیازمند پلن پولی + دامنه)</div>
          <div style="font-size:10.5px;color:var(--t3);margin-top:3px">ترافیک از لبه‌ی اروان داخل ایران رد می‌شود · برای مبدأ خارجی باید کیف پول شارژ شود</div>
        </div>
        <div class="br-mode-check" style="width:20px;height:20px;border-radius:50%;border:2px solid var(--t3);display:flex;align-items:center;justify-content:center"><i class="ti ti-check" style="font-size:12px;opacity:0"></i></div>
      </div>
      <div style="font-size:10px;color:var(--t3);margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
        <span class="cfg-sub-tag">هزینه: پولی (شارژ کیف پول)</span>
        <span class="cfg-sub-tag">دامنه اختصاصی لازم است</span>
        <span class="cfg-sub-tag">استتار: عالی</span>
      </div>
    </div>
  </div>

  <!-- راهنمای حالت CDN (اروان) -->
  <div class="card" id="br-cdn-guide" style="margin-bottom:18px;display:none">
    <div class="card-title"><i class="ti ti-cloud" style="color:var(--green-t)"></i> راه‌اندازی با ابر آروان (پلن پولی)</div>
    <div style="display:flex;flex-direction:column;gap:10px">
      <div class="cl"><i class="ti ti-circle-number-1" style="color:var(--green-t)"></i><span>در <b>arvancloud.ir</b> ثبت‌نام کنید، کیف پول را شارژ کنید و یک <b>دامنه‌ی اختصاصی</b> ثبت کنید (دامنه‌ی وورکر رایگان اروان فقط صفحه‌ی Hello, World! برمی‌گرداند و به مبدأ خارجی فوروارد نمی‌شود)</span></div>
      <div class="cl"><i class="ti ti-circle-number-2" style="color:var(--green-t)"></i><span>نیم‌سرورهای دامنه را به نیم‌سرورهای اروان تغییر دهید، سپس رکورد زیر بسازید: <b style="direction:ltr;display:inline-block">CNAME: sub → your-panel.up.railway.app</b> با پروکسی (ابر) <b>روشن</b></span></div>
      <div class="cl"><i class="ti ti-circle-number-3" style="color:var(--green-t)"></i><span>در تنظیمات CDN اروان: <b>WebSocket را فعال</b> کنید و گزینه‌ی <b>بازنویسی هدر Host به مبدأ</b> را روشن کنید + گواهی SSL را فعال کنید</span></div>
      <div class="cl"><i class="ti ti-circle-number-4" style="color:var(--green-t)"></i><span>همان دامنه (مثلاً <b style="direction:ltr;display:inline-block">sub.yourdomain.ir</b>) را در فرم زیر وارد و ذخیره کنید — ترافیک شما داخلی محاسبه می‌شود</span></div>
      <div class="cl amber"><i class="ti ti-alert-triangle"></i><span>اگر می‌خواهید <b>رایگان</b> و بدون خرید سرور پل داشته باشید، از <b>گیت‌وی کلادفلر</b> در تب «گیمینگ» استفاده کنید — وورکر رایگان با ۱۰۰ هزار درخواست در روز و اسکنر IP داخلی. برای پل اروان، پلن پولی + دامنه لازم است.</span></div>
    </div>
  </div>

  <!-- راهنمای حالت VPS -->
  <div id="br-vps-guide" style="display:none">
    <div class="conn-toolbar" style="margin-bottom:14px">
      <div class="conn-toolbar-title"><i class="ti ti-terminal-2"></i> راه‌اندازی سرور ایران (۳ دقیقه)</div>
    </div>
    <div class="card" style="margin-bottom:18px">
      <div class="card-title">
        <i class="ti ti-script"></i> اسکریپت نصب خودکار
        <span class="ml-auto" style="display:flex;gap:6px">
          <button class="btn btn-g btn-sm" onclick="brCopyScript()"><i class="ti ti-copy"></i> کپی اسکریپت</button>
          <button class="btn btn-g btn-sm" onclick="brShowNginx()"><i class="ti ti-brand-nginx"></i> نسخه nginx</button>
        </span>
      </div>
      <div style="display:flex;flex-direction:column;gap:10px">
        <div class="cl"><i class="ti ti-circle-number-1"></i><span>یک سرور مجازی داخل ایران بگیرید (هر VPS ارزان ایرانی با ترافیک نامحدود کافی است)</span></div>
        <div class="cl"><i class="ti ti-circle-number-2"></i><span>اسکریپت زیر را با دسترسی root روی آن اجرا کنید — socat و سرویس systemd خودکار نصب می‌شود</span></div>
        <div class="cl"><i class="ti ti-circle-number-3"></i><span>آدرس سرور را در فرم زیر ذخیره کنید و دکمه «تست پل» را بزنید</span></div>
        <pre id="br-script" style="background:var(--bg);border:1px solid var(--card-b);border-radius:10px;padding:14px;font-size:11px;direction:ltr;text-align:left;overflow-x:auto;max-height:260px;overflow-y:auto;font-family:monospace"></pre>
      </div>
    </div>
  </div>

  <!-- فرم تنظیم پل -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-server-2"></i> تنظیم پل <span id="br-mode-label" style="font-size:10px;color:var(--t3)">(حالت: سرور شخصی)</span></div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-settings"></i> <span id="br-form-title">آدرس سرور داخل ایران</span></div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end">
      <div class="fg" style="flex:1;min-width:220px">
        <label id="br-host-label">آدرس سرور ایران (IP یا دامنه)</label>
        <input id="br-host" placeholder="VPS: 185.51.x.x · CDN: sub.yourdomain.ir" style="width:100%;direction:ltr;text-align:left">
      </div>
      <div class="fg" style="width:110px" id="br-port-wrap">
        <label>پورت پل</label>
        <input id="br-port" type="number" value="443" list="cdn-ports" style="width:100%;direction:ltr;text-align:left">
        <datalist id="cdn-ports">
          <option value="443"><option value="8443"><option value="2053"><option value="2083"><option value="2087"><option value="2096">
        </datalist>
      </div>
      <button class="btn btn-p" onclick="brSaveConfig(this)"><i class="ti ti-device-floppy"></i> ذخیره</button>
      <button class="btn btn-g" onclick="brTestBridge(this)"><i class="ti ti-activity"></i> تست پل</button>
      <button class="btn btn-blue" onclick="brTestCNAME(this)"><i class="ti ti-link"></i> تست CNAME اروان</button>
    </div>
    <div class="cl" style="margin-top:10px" id="br-form-note"><i class="ti ti-info-circle"></i><span>پورت پیش‌فرض ۴۴۳ است. اگر ISP پورت ۴۴۳ سرور شما را نمی‌بندد همان ۴۴۳ بهتر است؛ در غیر این صورت هر پورت دلخواه را روی سرور باز کنید و همین‌جا وارد کنید.</span></div>
  </div>

  <!-- واقعیت‌های فنی: چرا جعل/کلوک تنها کافی نیست -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-flask"></i> چرا «جعل داده» و «کلوک» به‌تنهایی ضریب را حذف نمی‌کنند؟</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div style="overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:11.5px">
        <thead>
          <tr style="border-bottom:1px solid var(--card-b)">
            <th style="text-align:right;padding:9px 8px;color:var(--t3);font-size:10px">روش</th>
            <th style="text-align:center;padding:9px 8px;color:var(--t3);font-size:10px">ضریب صورت‌حساب</th>
            <th style="text-align:center;padding:9px 8px;color:var(--t3);font-size:10px">استتار از DPI</th>
            <th style="text-align:center;padding:9px 8px;color:var(--t3);font-size:10px">نیاز به سرور</th>
          </tr>
        </thead>
        <tbody>
          <tr style="border-bottom:1px solid var(--card-b)">
            <td style="padding:9px 8px">اتصال مستقیم به Railway</td>
            <td style="padding:9px 8px;text-align:center;color:var(--red-t)">۲.۷ ❌</td>
            <td style="padding:9px 8px;text-align:center;color:var(--amber-t)">متوسط</td>
            <td style="padding:9px 8px;text-align:center">—</td>
          </tr>
          <tr style="border-bottom:1px solid var(--card-b)">
            <td style="padding:9px 8px">جعل هدر / SNI spoofing</td>
            <td style="padding:9px 8px;text-align:center;color:var(--red-t)">۲.۷ ❌</td>
            <td style="padding:9px 8px;text-align:center;color:var(--red-t)">کم</td>
            <td style="padding:9px 8px;text-align:center">—</td>
          </tr>
          <tr style="border-bottom:1px solid var(--card-b)">
            <td style="padding:9px 8px">Cloak / Reality خالی</td>
            <td style="padding:9px 8px;text-align:center;color:var(--red-t)">۲.۷ ❌</td>
            <td style="padding:9px 8px;text-align:center;color:var(--green-t)">عالی</td>
            <td style="padding:9px 8px;text-align:center;color:var(--amber-t)">✅ سرور</td>
          </tr>
          <tr style="border-bottom:1px solid var(--card-b)">
            <td style="padding:9px 8px">پل VPS ایران</td>
            <td style="padding:9px 8px;text-align:center;color:var(--green-t)">۱ ✅</td>
            <td style="padding:9px 8px;text-align:center;color:var(--amber-t)">خوب</td>
            <td style="padding:9px 8px;text-align:center;color:var(--amber-t)">✅ سرور</td>
          </tr>
          <tr>
            <td style="padding:9px 8px">⭐ CDN ایرانی (ابَر آروان)</td>
            <td style="padding:9px 8px;text-align:center;color:var(--green-t)">۱ ✅</td>
            <td style="padding:9px 8px;text-align:center;color:var(--green-t)">عالی</td>
            <td style="padding:9px 8px;text-align:center;color:var(--amber-t)">پلن پولی + دامنه</td>
          </tr>
          <tr style="background:var(--green-bg)">
            <td style="padding:9px 8px;font-weight:700">🆕 گیت‌وی کلادفلر (تب گیمینگ)</td>
            <td style="padding:9px 8px;text-align:center;color:var(--amber-t)">داخلی تا لبه</td>
            <td style="padding:9px 8px;text-align:center;color:var(--green-t);font-weight:700">عالی</td>
            <td style="padding:9px 8px;text-align:center;color:var(--green-t);font-weight:700">رایگان (۱۰۰k/روز)</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px;margin-top:12px">
      <div class="cl"><i class="ti ti-shield-off" style="color:var(--red-t)"></i><span><b>چرا جعل کار نمی‌کند؟</b> ضریب ۲.۷ بر اساس <b>آی‌پی مقصد</b> محاسبه می‌شود، نه محتوای پکت‌ها. اپراتور فقط می‌بیند که به یک آی‌پی خارجی TCP زدی — هر چیزی که داخل پکت‌ها نوشته شده باشد. پس جعل هدر، SNI spoofing و padding فقط DPI را گول می‌زنند، نه سیستم صورت‌حساب.</span></div>
      <div class="cl"><i class="ti ti-shield-check" style="color:var(--green-t)"></i><span><b>پس «مسیر ایرانی» چطور ممکن است؟</b> باید مقصدِ واقعیِ TCP یک آی‌پی <b>داخلی</b> باشد. CDN ایرانی دقیقاً همین کار را می‌کند: واقعاً به یک سایت/سرویس ایرانی وصل می‌شوی (هزاران سایت واقعی روی همان آی‌پی‌های اروان هستند) — پس هم صورت‌حساب داخلی می‌شود، هم ترافیک شما از نظر DPI کاملاً عادی و شبیه مرور یک سایت ایرانی معمولی است. این همان استتاری است که می‌خواستی، بدون هیچ جعلی!</span></div>
    </div>
  </div>

  <!-- محاسبه‌گر صرفه‌جویی -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-calculator"></i> محاسبه‌گر صرفه‌جویی</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center">
      <div class="fg" style="flex:1;min-width:180px">
        <label>مصرف ماهانه تونل شما (گیگابایت)</label>
        <input id="br-calc-gb" type="range" min="1" max="100" value="10" style="width:100%;accent-color:var(--accent)">
        <div style="text-align:center;font-weight:700;font-size:15px;margin-top:4px"><span id="br-calc-gb-val">۱۰</span> GB</div>
      </div>
      <div style="flex:2;min-width:260px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
        <div style="background:var(--red-bg);border:1px solid rgba(239,68,68,.2);border-radius:12px;padding:12px;text-align:center">
          <div style="font-size:9.5px;color:var(--t3)">بدون پل (×۲.۷)</div>
          <div style="font-size:17px;font-weight:800;color:var(--red-t);margin-top:4px" id="br-calc-without">۲۷ GB</div>
          <div style="font-size:9px;color:var(--t3)">صورت‌حساب اپراتور</div>
        </div>
        <div style="background:var(--green-bg);border:1px solid rgba(16,185,129,.2);border-radius:12px;padding:12px;text-align:center">
          <div style="font-size:9.5px;color:var(--t3)">با پل (×۱)</div>
          <div style="font-size:17px;font-weight:800;color:var(--green-t);margin-top:4px" id="br-calc-with">۱۰ GB</div>
          <div style="font-size:9px;color:var(--t3)">صورت‌حساب اپراتور</div>
        </div>
        <div style="background:var(--accent-d);border:1px solid var(--card-b);border-radius:12px;padding:12px;text-align:center">
          <div style="font-size:9.5px;color:var(--t3)">صرفه‌جویی</div>
          <div style="font-size:17px;font-weight:800;color:var(--accent2);margin-top:4px" id="br-calc-save">۱۷ GB</div>
          <div style="font-size:9px;color:var(--t3)">در ماه (۶۳٪)</div>
        </div>
      </div>
    </div>
  </div>

  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-link"></i> کانفیگ‌های پل‌دار <span class="badge bg-blue" id="bridge-links-cnt">۰</span></div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div id="bridge-links-list"><div class="empty"><i class="ti ti-flag-off"></i><p>ابتدا آدرس پل را ذخیره کنید</p></div></div>
    <div class="cl amber" style="margin-top:10px"><i class="ti ti-alert-triangle"></i><span>دکمه‌ی <b>فعالیت</b> کنار هر کانفیگ، پینگ واقعی «از مسیر پل» می‌گیرد — همان مسیری که کلاینت می‌رود. اگر این تست سبز باشد، کلاینت‌ها هم قطعاً جواب می‌گیرند.</span></div>
  </div>

  <!-- آی‌پی‌های تمیز -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-radar-2"></i> آی‌پی‌های تمیز لبه‌ی CDN <span class="badge bg-purple" id="cip-cnt">۰</span></div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title">
      <i class="ti ti-radar-2" style="color:var(--purple)"></i> اسکن لبه‌های اروان
      <span class="ml-auto" style="display:flex;gap:6px;flex-wrap:wrap">
        <button class="btn btn-g btn-sm" onclick="cipScanArvan(this)"><i class="ti ti-radar"></i> اسکن آروان</button>
        <button class="btn btn-g btn-sm" onclick="cipScanBrowser(this)"><i class="ti ti-speedometer"></i> اسکن از مرورگر من</button>
      </span>
    </div>
    <div id="cip-list"><div class="sr"><span class="sr-k" style="color:var(--t3)">«اسکن آروان» IPهای معتبر را از سمت سرور پیدا می‌کند؛ سپس «اسکن از مرورگر من» تاخیر واقعی هر IP را از اینترنت خودتان می‌سنجد</span></div></div>
    <div class="cl" style="margin-top:10px"><i class="ti ti-info-circle"></i><span>آی‌پی تمیز = جایگزینی «آدرس اتصال» لینک با IP سریع، در حالی که host/sni همان دامنه‌ی پل می‌ماند. اگر ISP شما بعضی IPهای اروان را کند کرده، با این روش از IP سریع‌تر وصل می‌شوید.</span></div>
  </div>

  <!-- پورت‌های لبه -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-plug"></i> پورت‌های آماده‌ی اتصال</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title">
      <i class="ti ti-plug"></i> پورت‌های سالم پروتکل
      <span class="ml-auto"><button class="btn btn-g btn-sm" onclick="portTestAll(this)"><i class="ti ti-speedometer"></i> تست پورت‌ها از مرورگر</button></span>
    </div>
    <div style="display:flex;gap:14px;flex-wrap:wrap">
      <div style="flex:1;min-width:220px">
        <div style="font-size:10px;font-weight:700;color:var(--green-t);margin-bottom:6px"><i class="ti ti-lock"></i> TLS (رمزنگاری‌شده)</div>
        <div id="ports-tls" style="display:flex;gap:6px;flex-wrap:wrap"></div>
      </div>
      <div style="flex:1;min-width:220px">
        <div style="font-size:10px;font-weight:700;color:var(--amber-t);margin-bottom:6px"><i class="ti ti-lock-open"></i> غیر TLS</div>
        <div id="ports-plain" style="display:flex;gap:6px;flex-wrap:wrap"></div>
      </div>
    </div>
    <div class="cl" style="margin-top:10px"><i class="ti ti-info-circle"></i><span>کانفیگ‌های پنل با security=tls ساخته می‌شوند؛ پورت اصلی ۴۴۳ است. پورت‌های دیگر فقط زمانی معتبرند که پل CDN فعال باشد و لبه، آن پورت را سرو کند — با «تست پورت‌ها» از مرورگر خودتان بررسی کنید.</span></div>
  </div>
</section>

<!-- ════════════════════════ تنظیمات حرفه‌ای ZEUS ════════════════════════ -->
<section class="pg" id="pg-zeus">
  <div class="node-hero" style="margin-bottom:18px">
    <div class="node-hero-top">
      <div class="node-hero-title">
        <div class="node-hero-icon"><i class="ti ti-bolt"></i></div>
        <div>
          <div class="tb-title">تنظیمات حرفه‌ای — ISP + TLS Mask + Smart + Security</div>
          <div class="tb-sub">پیاده‌سازی ویژگی‌های پنل ZEUS به‌صورت ماژول کاملاً جدا از هسته‌ی EMIX</div>
        </div>
      </div>
      <div class="tb-right">
        <span class="badge bg-amber" id="zeus-status-badge">بارگذاری...</span>
      </div>
    </div>
    <div class="node-hero-metrics">
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-device-mobile"></i><span class="node-metric-label">ISP انتخابی</span></div>
        <div class="node-metric-val" id="zeus-isp-name" style="font-size:15px">—</div>
        <div class="node-metric-sub" id="zeus-isp-best-proto">پروتکل پیشنهادی: —</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-shield-lock"></i><span class="node-metric-label">TLS Mask</span></div>
        <div class="node-metric-val" id="zeus-tls-status">—</div>
        <div class="node-metric-sub" id="zeus-tls-sni-metric">SNI: —</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-brain"></i><span class="node-metric-label">حالت هوشمند</span></div>
        <div class="node-metric-val" id="zeus-smart-status">—</div>
        <div class="node-metric-sub" id="zeus-smart-best">بهترین کانفیگ: —</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-lock"></i><span class="node-metric-label">قفل‌سازی لاگین</span></div>
        <div class="node-metric-val" id="zeus-security-status">—</div>
        <div class="node-metric-sub" id="zeus-security-rule">حداکثر تلاش: —</div>
      </div>
    </div>
  </div>

  <!-- ۱) انتخاب ISP -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-device-mobile"></i> انتخاب سرویس‌دهنده اینترنت (ISP)</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-wifi"></i> ISP شما کدام است؟</div>
    <div style="font-size:11.5px;color:var(--t3);margin-bottom:14px">با انتخاب ISP، توصیه‌گر پروتکل متناسب با شبکه‌ی شما نمایش داده می‌شود. این فقط توصیه‌ست و لینک‌ها را تغییر نمی‌دهد.</div>
    <div id="zeus-isp-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px">
      <!-- توسط JS پر می‌شود -->
    </div>
    <div id="zeus-isp-detail" style="margin-top:14px;padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);display:none">
      <div style="font-weight:700;font-size:13px;margin-bottom:8px" id="zeus-isp-detail-title">—</div>
      <div style="font-size:12px;color:var(--t2);margin-bottom:8px" id="zeus-isp-detail-rationale">—</div>
      <ul id="zeus-isp-detail-tips" style="margin:0;padding-right:18px;font-size:11.5px;color:var(--t3);list-style:disc"></ul>
    </div>
  </div>

  <!-- ۲) تنظیمات TLS Mask -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-shield-lock"></i> تنظیمات پیشرفته TLS Mask <span class="badge bg-purple" id="zeus-tls-badge" style="display:none">فعال</span></div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title">
      <i class="ti ti-settings"></i> SNI سفارشی + Fragment + Cipher Suites
      <span class="ml-auto" style="display:flex;align-items:center;gap:8px">
        <span style="font-size:11px;color:var(--t3)">فعال‌سازی:</span>
        <label class="toggle" style="position:relative;display:inline-block;width:36px;height:20px;cursor:pointer">
          <input type="checkbox" id="zeus-tls-toggle" style="opacity:0;width:0;height:0">
          <span class="toggle-slider" style="position:absolute;inset:0;background:var(--t3);border-radius:20px;transition:.3s"></span>
        </label>
      </span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px">
      <div>
        <label style="font-size:11.5px;color:var(--t2);display:block;margin-bottom:6px">SNI سفارشی (دامنه جعلی به جای دامنه اصلی)</label>
        <input type="text" id="zeus-tls-sni" placeholder="www.speedtest.net" style="width:100%;direction:ltr;text-align:left;font-family:monospace">
      </div>
      <div>
        <label style="font-size:11.5px;color:var(--t2);display:block;margin-bottom:6px">Cipher Suites (TLS 1.3)</label>
        <input type="text" id="zeus-tls-cipher" placeholder="TLS_AES_256_GCM_SHA384:..." style="width:100%;direction:ltr;text-align:left;font-family:monospace;font-size:10.5px">
      </div>
      <div>
        <label style="font-size:11.5px;color:var(--t2);display:block;margin-bottom:6px">Fragment Length (تعداد بایت‌های هر پکت)</label>
        <input type="text" id="zeus-tls-frag-len" placeholder="5-94" style="width:100%;direction:ltr;text-align:left;font-family:monospace">
      </div>
      <div>
        <label style="font-size:11.5px;color:var(--t2);display:block;margin-bottom:6px">Fragment Delay (ms)</label>
        <input type="text" id="zeus-tls-frag-dly" placeholder="0" style="width:100%;direction:ltr;text-align:left;font-family:monospace">
      </div>
    </div>
    <div class="cl amber" style="margin-top:12px"><i class="ti ti-alert-triangle"></i><span><b>هشدار:</b> Fragment و SNI spoofing فقط DPI را گول می‌زنند، نه صورت‌حساب اپراتور را. برای صورت‌حساب داخلی از پل CDN اروان استفاده کنید. این تنظیمات در سمت کلاینت Xray اعمال می‌شوند (خروجی JSON Fragment در پایین صفحه).</span></div>
    <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
      <button class="btn btn-g" onclick="zeusSaveTlsMask()"><i class="ti ti-check"></i> ذخیره تنظیمات</button>
      <button class="btn btn-pur" onclick="zeusShowMaskedLinks()"><i class="ti ti-link"></i> لینک‌های Mask-شده</button>
      <button class="btn btn-blue" onclick="zeusShowFragmentJson()"><i class="ti ti-code"></i> خروجی JSON Fragment</button>
    </div>
  </div>

  <!-- ۳) حالت هوشمند -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-brain"></i> حالت هوشمند (Smart Mode)</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title">
      <i class="ti ti-robot"></i> انتخاب خودکار بهترین کانفیگ لحظه‌ای
      <span class="ml-auto" style="display:flex;align-items:center;gap:8px">
        <span style="font-size:11px;color:var(--t3)">فعال‌سازی:</span>
        <label class="toggle" style="position:relative;display:inline-block;width:36px;height:20px;cursor:pointer">
          <input type="checkbox" id="zeus-smart-toggle" style="opacity:0;width:0;height:0">
          <span class="toggle-slider" style="position:absolute;inset:0;background:var(--t3);border-radius:20px;transition:.3s"></span>
        </label>
      </span>
    </div>
    <div style="font-size:11.5px;color:var(--t3);margin-top:8px">وقتی روشن باشد، پنل همه‌ی کانفیگ‌ها را تست می‌کند و کم‌تاخیرترین را به‌عنوان پیشنهاد لحظه‌ای نشان می‌دهد.</div>
    <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
      <button class="btn btn-g" onclick="zeusSmartRecommend()"><i class="ti ti-trophy"></i> تست اکنون و معرفی بهترین</button>
    </div>
    <div id="zeus-smart-result" style="margin-top:14px;padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);display:none">
      <div style="font-weight:700;font-size:13px;margin-bottom:8px">بهترین کانفیگ لحظه‌ای</div>
      <div id="zeus-smart-result-content">—</div>
    </div>
  </div>

  <!-- ۴) قفل‌سازی لاگین -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-lock"></i> قفل‌سازی لاگین (Security Rate-Limit)</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title">
      <i class="ti ti-shield-check"></i> محدودسازی تلاش‌های ورود
      <span class="ml-auto" style="display:flex;align-items:center;gap:8px">
        <span style="font-size:11px;color:var(--t3)">فعال‌سازی:</span>
        <label class="toggle" style="position:relative;display:inline-block;width:36px;height:20px;cursor:pointer">
          <input type="checkbox" id="zeus-security-toggle" style="opacity:0;width:0;height:0">
          <span class="toggle-slider" style="position:absolute;inset:0;background:var(--t3);border-radius:20px;transition:.3s"></span>
        </label>
      </span>
    </div>
    <div style="font-size:11.5px;color:var(--t3);margin-top:8px">میان‌افزار روی /api/login اعمال می‌شود؛ IPهایی که بیش از حد مجاز تلاش کنند به‌طور موقت بلاک می‌شوند.</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:14px">
      <div>
        <label style="font-size:11.5px;color:var(--t2);display:block;margin-bottom:6px">حداقل طول پسورد</label>
        <input type="number" id="zeus-sec-min-len" placeholder="8" min="4" max="64" style="width:100%;direction:ltr;text-align:left;font-family:monospace">
      </div>
      <div>
        <label style="font-size:11.5px;color:var(--t2);display:block;margin-bottom:6px">فاصله‌ی تلاش‌ها (ms)</label>
        <input type="number" id="zeus-sec-interval" placeholder="1000" min="100" style="width:100%;direction:ltr;text-align:left;font-family:monospace">
      </div>
      <div>
        <label style="font-size:11.5px;color:var(--t2);display:block;margin-bottom:6px">حداکثر تعداد تلاش</label>
        <input type="number" id="zeus-sec-max" placeholder="5" min="1" max="100" style="width:100%;direction:ltr;text-align:left;font-family:monospace">
      </div>
    </div>
    <div style="margin-top:12px">
      <label style="font-size:11.5px;color:var(--t2);display:block;margin-bottom:6px">مدت بلاک پس از تجاوز (ms)</label>
      <input type="number" id="zeus-sec-lockout" placeholder="60000" min="1000" step="1000" style="width:100%;direction:ltr;text-align:left;font-family:monospace">
    </div>
    <div class="cl" style="margin-top:12px"><i class="ti ti-info-circle"></i><span>این قفل‌سازی فقط روی اندپوینت /api/login اعمال می‌شود و جریان احراز هویت اصلی EMIX را تغییر نمی‌دهد. اگر ماژول غیرفعال شود، همه‌ی IPهای بلاک‌شده آزاد می‌شوند.</span></div>
    <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
      <button class="btn btn-g" onclick="zeusSaveSecurity()"><i class="ti ti-check"></i> ذخیره تنظیمات</button>
      <button class="btn btn-blue" onclick="zeusSecurityCheck()"><i class="ti ti-activity"></i> بررسی وضعیت میان‌افزار</button>
    </div>
    <div id="zeus-security-result" style="margin-top:14px;padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);display:none">
      <div id="zeus-security-result-content">—</div>
    </div>
  </div>
</section>

<!-- ══════════════════════ مرکز گیمینگ EMIX ══════════════════════ -->
<section class="pg" id="pg-gaming">
  <div class="node-hero" style="margin-bottom:18px">
    <div class="node-hero-top">
      <div class="node-hero-title">
        <div class="node-hero-icon" style="background:rgba(76,201,240,.15);color:#4cc9f0"><i class="ti ti-device-gamepad-2"></i></div>
        <div>
          <div class="tb-title">مرکز گیمینگ — بهترین پینگ و پایداری</div>
          <div class="tb-sub">اسکنر IP کلادفلر + مسیر PoP + کانفیگ‌های tuned برای بازی + مولتی‌لوکیشن</div>
        </div>
      </div>
      <div class="tb-right">
        <span class="badge" id="gaming-status-badge">بارگذاری...</span>
      </div>
    </div>
    <div class="node-hero-metrics">
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-bolt"></i><span class="node-metric-label">بهترین IP</span></div>
        <div class="node-metric-val" id="gaming-best-ip" style="font-size:15px;direction:ltr">—</div>
        <div class="node-metric-sub" id="gaming-best-ms">تأخیر: —</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-building-broadcast-tower"></i><span class="node-metric-label">PoP کلادفلر شما</span></div>
        <div class="node-metric-val" id="gaming-colo" style="font-size:15px">—</div>
        <div class="node-metric-sub" id="gaming-colo-city">شهر: —</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-flag"></i><span class="node-metric-label">لوکیشن خروج</span></div>
        <div class="node-metric-val" id="gaming-loc-count" style="font-size:15px">—</div>
        <div class="node-metric-sub" id="gaming-loc-list">—</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-server-2"></i><span class="node-metric-label">گیت‌وی کلادفلر</span></div>
        <div class="node-metric-val" id="gaming-worker-status" style="font-size:15px">—</div>
        <div class="node-metric-sub" id="gaming-worker-domain-label" style="direction:ltr;text-align:left;overflow:hidden;text-overflow:ellipsis">—</div>
      </div>
    </div>
  </div>

  <!-- ۱) راه‌اندازی گیت‌وی -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-cloud-cog"></i> گیت‌وی کلادفلر و ورودی‌ها</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-cloud"></i> Worker کلادفلر (Gateway)</div>
    <div style="font-size:11.5px;color:var(--t3);margin-bottom:14px;line-height:1.9">
      معماری: <b style="direction:ltr;display:inline-block">کاربر → بهترین IP کلادفلر (یا VPS ایران) → Worker → لوکیشن → اینترنت</b><br>
      کد Worker در فایل <code style="direction:ltr;display:inline-block">cf_gateway_worker.js</code> مخزن است — در <b>dash.cloudflare.com → Workers & Pages → Create Worker</b> پیست و Deploy کن، بعد دامنه‌ی workers.dev را اینجا ذخیره کن. توکن اختیاری است و فقط برای افزودن لوکیشن لازم است (در Cloudflare → Settings → Variables → EMIX_TOKEN).
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px">
      <div><label style="font-size:11px;color:var(--t3)">دامنه‌ی Worker (workers.dev)</label>
        <input id="gaming-worker-domain" placeholder="emix-gateway.username.workers.dev" style="width:100%;direction:ltr;text-align:left;font-family:monospace"></div>
      <div><label style="font-size:11px;color:var(--t3)">توکن EMIX_TOKEN (اختیاری — برای لوکیشن)</label>
        <input id="gaming-worker-token" type="password" placeholder="••••••••" style="width:100%;direction:ltr;text-align:left;font-family:monospace"></div>
      <div><label style="font-size:11px;color:var(--t3)">IP سرور ایران VPS (ورودی پایدار — اختیاری)</label>
        <input id="gaming-vps-ip" placeholder="185.164.73.192" style="width:100%;direction:ltr;text-align:left;font-family:monospace"></div>
      <div><label style="font-size:11px;color:var(--t3)">پورت VPS</label>
        <input id="gaming-vps-port" type="number" value="443" style="width:100%;direction:ltr;text-align:left;font-family:monospace"></div>
    </div>
    <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
      <button class="btn btn-g" onclick="gamingSaveConfig()"><i class="ti ti-check"></i> ذخیره تنظیمات</button>
      <button class="btn btn-blue" onclick="gamingCheckWorker()"><i class="ti ti-radar-2"></i> تست سلامت گیت‌وی + تشخیص PoP</button>
    </div>
    <div id="gaming-worker-result" style="margin-top:14px;padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);display:none;font-size:12px;line-height:1.9"></div>
  </div>

  <!-- ۲) اسکنر IP -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-radar"></i> اسکنر IP کلادفلر (سمت مرورگر شما)</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-signal-4g"></i> پیدا کردن سریع‌ترین IP آنیکست</div>
    <div style="font-size:11.5px;color:var(--t3);margin-bottom:14px;line-height:1.8">
      این اسکنر <b>از مرورگر خودتان</b> IPهای کلادفلر را تست می‌کند — چون فقط تأخیرِ مسیر «شما → لبه‌ی کلادفلر» مهم است، نه مسیر سرور پنل. هر IP سه بار پروب می‌شود؛ کمینه = پینگ واقعی، پراکندگی = jitter. نتایج بر اساس کمترین تأخیر رتبه‌بندی می‌شوند و بهترین IP برای ساخت کانفیگ گیمینگ ذخیره می‌شود.
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      <button class="btn btn-g" id="gaming-scan-btn" onclick="gamingStartScan()"><i class="ti ti-radar-2"></i> شروع اسکن (~۱ دقیقه)</button>
      <span id="gaming-scan-progress" style="font-size:11.5px;color:var(--t3)">آماده</span>
    </div>
    <div id="gaming-scan-table" style="margin-top:14px;max-height:320px;overflow:auto;display:none">
      <table style="width:100%;border-collapse:collapse;font-size:11.5px">
        <thead><tr style="text-align:right;color:var(--t3)">
          <th style="padding:6px 8px">#</th><th style="padding:6px 8px">IP</th><th style="padding:6px 8px">کمینه (ms)</th>
          <th style="padding:6px 8px">میانگین (ms)</th><th style="padding:6px 8px">Jitter (ms)</th><th style="padding:6px 8px">وضعیت</th>
        </tr></thead>
        <tbody id="gaming-scan-tbody"></tbody>
      </table>
    </div>
    <div id="gaming-scan-summary" style="margin-top:12px;font-size:12px;display:none"></div>
  </div>

  <!-- ۳) اینباندهای گیت‌وی (مولتی‌ورودی روی خود وورکر — بدون خرید سرور) -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-door-enter"></i> اینباندهای گیت‌وی — چند ورودی روی خودِ وورکر (بدون سرور اضافه)</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-door-enter"></i> اینباندهای ورودی (Entry Points)</div>
    <div style="font-size:11.5px;color:var(--t3);margin-bottom:14px;line-height:1.8">
      هر IP آنیکست کلادفلر = یک ورودی مستقل به <b>همان وورکر</b> — مثل داشتن چند سرور ورودی، بدون خرید هیچ سروری. اینباند موردنظر را تست کنید و با کلیک روی «استفاده»، IP آن در فیلد ساخت کانفیگ قرار می‌گیرد.
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px">
      <button class="btn btn-g" onclick="gamingLoadInbounds(this)"><i class="ti ti-plug-connected"></i> تست و نمایش اینباندها</button>
      <span id="gaming-inbounds-summary" style="font-size:11px;color:var(--t3)"></span>
    </div>
    <div id="gaming-inbounds-list" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px"></div>
  </div>

  <!-- ۳-ب) لوکیشن‌های خروج — بازطراحی کامل -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-world"></i> لوکیشن‌های خروج — چند کشور، رایگان</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-flag"></i> لوکیشن‌های خروج (خروجیِ ترافیک = IP کشور هدف)</div>
    <div style="font-size:11.5px;color:var(--t3);margin-bottom:14px;line-height:1.9">
      <b>خروجی ترافیک شما الان از بک‌اند اصلی (Railway آمریکا) است.</b> برای اینکه خروجی به کشور دیگری برود، باید یک سرور خروج کوچک در آن کشور باشد —
      اما نگران نباش: <b>۳ راه واقعاً رایگان</b> برای همین پروژه ساخته شده:
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin-top:10px">
        <div style="padding:10px 12px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b)">
          <b style="color:var(--green-t)">۱. بسته‌ی سرور خروج رایگان ⭐</b><br>
          <span style="font-size:10.5px">پنل برایت یک سرور VLESS مینیمال با UUID خودت می‌سازد؛ روی Railway خودت (رژیون فرانکفورت/سنگاپور) یا Koyeb بدون کارت deploy می‌کنی — ۵ دقیقه کار دارد</span>
        </div>
        <div style="padding:10px 12px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b)">
          <b style="color:var(--blue-t)">۲. Oracle Cloud همیشه‌رایگان</b><br>
          <span style="font-size:10.5px">سرور مجازی کامل و دائمی در دبی/فرانکفورت — بهترین پینگ برای بازی؛ فقط یک‌بار ثبت‌نام می‌خواهد</span>
        </div>
        <div style="padding:10px 12px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b)">
          <b style="color:var(--purple-t)">۳. دامنه‌ی اختصاصی</b><br>
          <span style="font-size:10.5px">هر سروری که WS سرو کند (حتی VPS ارزان) با یک دامنه معتبر، اینجا قابل ثبت است — کاستوم همیشه باز است</span>
        </div>
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:14px">
      <button class="btn btn-blue" onclick="gamingExitWizard(this)"><i class="ti ti-package-export"></i> بسته‌ی سرور خروج رایگان (۵ دقیقه)</button>
      <button class="btn btn-g" onclick="gamingRefreshLocations(false,true)"><i class="ti ti-refresh"></i> دریافت + تست سلامت لوکیشن‌ها</button>
    </div>
    <div id="gaming-loc-list-box" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px"></div>

    <!-- قالب‌های آماده لوکیشن -->
    <div style="font-size:12px;font-weight:700;margin-bottom:8px"><i class="ti ti-layout-grid"></i> قالب‌های آماده — کلیک کن تا فرم پایین خودکار پر شود</div>
    <div id="gaming-loc-templates" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px;margin-bottom:16px"></div>

    <!-- فرم افزودن (پیش‌پر با لوکیشن‌های سالم) -->
    <div style="font-size:12px;font-weight:700;margin-bottom:8px"><i class="ti ti-plus"></i> افزودن لوکیشن جدید (پیش‌فرض سالم — قابل ویرایش)</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px">
      <div><label style="font-size:11px;color:var(--t3)">کد لوکیشن (انگلیسی)</label>
        <input id="gaming-loc-name" value="de" placeholder="de" style="width:100%;direction:ltr;text-align:left;font-family:monospace"></div>
      <div><label style="font-size:11px;color:var(--t3)">نام نمایشی</label>
        <input id="gaming-loc-label" value="آلمان — فرانکفورت" placeholder="آلمان — فرانکفورت" style="width:100%"></div>
      <div><label style="font-size:11px;color:var(--t3)">پرچم (ایموجی)</label>
        <input id="gaming-loc-flag" value="🇩🇪" placeholder="🇩🇪" style="width:100%"></div>
      <div style="grid-column:span 2"><label style="font-size:11px;color:var(--t3)">دامنه‌ی بک‌اند (با TLS معتبر)</label>
        <input id="gaming-loc-upstream" value="emix-pro-production.up.railway.app" placeholder="emix-pro-production.up.railway.app" style="width:100%;direction:ltr;text-align:left;font-family:monospace"></div>
    </div>
    <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
      <button class="btn btn-g" onclick="gamingAddLocation()"><i class="ti ti-plus"></i> افزودن لوکیشن</button>
      <span style="font-size:10.5px;color:var(--t3);align-self:center">کد چند حرفی انگلیسی مثل tr / ru / de / ae — بعداً در ساخت کانفیگ انتخاب می‌شود. مقادیر پیش‌فرض سالم‌اند — برای خروج واقعی، یک exit node deploy کنید.</span>
    </div>
    <!-- ویزارد بسته‌ی خروج -->
    <div id="gaming-exit-wizard" style="margin-top:16px;display:none"></div>
  </div>

  <!-- ۳.۵) حقیقت مسیر و خروج — CONTROL PLANE / EXIT NODE / REAL EGRESS -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-route"></i> حقیقت مسیر و خروج — کنترل‌پلین / نود خروج / IP خروج واقعی</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-compass"></i> مسیر و IP خروج — چه چیزی واقعاً تأیید شده است؟</div>
    <div style="font-size:11px;color:var(--t3);margin-bottom:12px;line-height:1.9">
      <b>اندپوینت ≠ مسیر ≠ خروج.</b> آدرس/SNI/Hostname فقط تعیین می‌کنند کلاینت <b>به کجا وصل</b> شود؛ IP خروج را فقط نودی تغییر می‌دهد که ترافیک واقعاً از آن عبور می‌کند (نود خروج/ریلی).
      <b style="color:var(--amber-t)">تغییر IP سفارشی یا SNI هرگز IP خروج را عوض نمی‌کند.</b>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:12px">
      <div style="padding:12px;background:var(--bg);border-radius:12px;border:1px solid var(--card-b)">
        <div style="font-size:10px;color:var(--t3);margin-bottom:4px"><i class="ti ti-server-2"></i> CONTROL PLANE — کنترل‌پلین</div>
        <div id="eg-cp-host" style="font-size:12px;font-weight:700;direction:ltr;text-align:left;font-family:monospace">—</div>
        <div id="eg-cp-note" style="font-size:10px;color:var(--t3);margin-top:4px">Railway = میزبان پنل و برنامه</div>
      </div>
      <div style="padding:12px;background:var(--bg);border-radius:12px;border:1px solid var(--card-b)">
        <div style="font-size:10px;color:var(--t3);margin-bottom:4px"><i class="ti ti-door-exit"></i> EXIT NODE — نود خروج</div>
        <div id="eg-exit-node" style="font-size:12px;font-weight:700">تنظیم نشده</div>
        <div id="eg-exit-note" style="font-size:10px;color:var(--t3);margin-top:4px">بدون نود خروج، ترافیک از همین نود (کنترل‌پلین) خارج می‌شود</div>
      </div>
      <div style="padding:12px;background:var(--bg);border-radius:12px;border:1px solid var(--card-b)">
        <div style="font-size:10px;color:var(--t3);margin-bottom:4px"><i class="ti ti-world"></i> REAL EGRESS — IP خروج واقعی</div>
        <div id="eg-real-ip" style="font-size:12px;font-weight:700;direction:ltr;text-align:left;font-family:monospace">—</div>
        <div id="eg-real-sub" style="font-size:10px;color:var(--t3);margin-top:4px">فقط با اندازه‌گیری واقعی تأیید می‌شود — نه با مقدار تنظیم‌شده</div>
      </div>
      <div style="padding:12px;background:var(--bg);border-radius:12px;border:1px solid var(--card-b)">
        <div style="font-size:10px;color:var(--t3);margin-bottom:4px"><i class="ti ti-statuschange"></i> STATUS — وضعیت مسیر</div>
        <div><span class="badge bg-blue" id="eg-status-badge">UNKNOWN</span></div>
        <div id="eg-status-note" style="font-size:10px;color:var(--t3);margin-top:4px">DIRECT = خروج از همین نود · RELAY = عبور از ریل‌لی · VERIFIED = تأییدشده با مدرک</div>
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      <button class="btn btn-blue" onclick="verifyPanelEgress(this)"><i class="ti ti-radar-2"></i> اندازه‌گیری IP خروج پنل (با مدرک)</button>
      <span id="eg-verify-result" style="font-size:11px;color:var(--t3)"></span>
    </div>
  </div>

  <!-- ۴) ضد ضریب (Anti-DPI) + تولید کانفیگ گیمینگ -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-trophy"></i> ضد ضریب + کانفیگ گیمینگ</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-shield-lock"></i> ضد ضریب (Anti-DPI) — جعل دیتا برای دور زدن مهار سرعت</div>
    <div style="font-size:11.5px;color:var(--t3);margin-bottom:12px;line-height:1.9">
      <b>«ضریب» یعنی چه؟</b> فیلترینگ DPI با دیدن امضای handshake تونل، آن جریان را با QoS مهار می‌کند و سرعت چند برابر کم می‌شود. EMIX پنج لایه جعل دارد:
      <b>۱) fragment تصادفی</b> (ClientHello به تکه‌های کوچک متغیر می‌شکند و امضای DPI بازسازی نمی‌شود) ·
      <b>۲) uTLS</b> (اثر انگشت TLS دقیقاً مثل مرورگر واقعی) ·
      <b>۳) ترنسپورت XHTTP</b> (الگوی ترافیک مثل HTTP عادی، بدون امضای Upgrade وب‌سوکت) ·
      <b>۴) حالت ایرانسل مخصوص</b> (fragment تهاجمی 8-40 بایت + اثر انگشت Safari) ·
      <b>۵) XHTTP+ایرانسل</b> (وقتی WS روی ایرانسل وصل نمی‌شود).
      <br><b style="color:var(--amber-t)">📱 اگر روی همراه‌اول عالی ولی روی ایرانسل کار نمی‌کند:</b> حالت «ایرانسل» یا «ایرانسل-XHTTP» را انتخاب کنید — برای ایرانسل بهینه‌سازی شده است.
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:12px">
      <div><label style="font-size:11px;color:var(--t3)">حالت ضد ضریب</label>
        <select id="gaming-anti-mode" style="width:100%">
          <option value="balanced">⚖ متعادل — پیشنهادی (fragment 40-120 + کروم)</option>
          <option value="stealth">🛡 حداکثری — ضد ضریب (fragment ریز 20-80 + فایرفاکس)</option>
          <option value="speed">⚡ حداکثر سرعت (بدون fragment — همراه‌اول)</option>
          <option value="irancell">📱 ایرانسل — ضد ضریب مخصوص (fragment 8-40 + Safari)</option>
          <option value="irancell-xhttp">📱 ایرانسل + XHTTP — حداکثری (وقتی WS وصل نمی‌شود)</option>
        </select></div>
      <div><label style="font-size:11px;color:var(--t3)">ترنسپورت (نوع ترافیک)</label>
        <select id="gaming-transport" style="width:100%">
          <option value="ws">WebSocket — پایدار و سازگار</option>
          <option value="xhttp-stream-up">XHTTP stream-up — بیشترین جعل ترافیک</option>
          <option value="xhttp-packet-up">XHTTP packet-up — ضد DPI پکت‌محور</option>
        </select></div>
    </div>
    <div id="gaming-anti-desc" style="font-size:11px;color:var(--t2);padding:10px 12px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);margin-bottom:14px;line-height:1.8"></div>
    <div style="font-size:12px;font-weight:700;margin:14px 0 8px"><i class="ti ti-bolt"></i> ساخت کانفیگ tuned برای بازی</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:12px">
      <div><label style="font-size:11px;color:var(--t3)">ورودی (Entry)</label>
        <select id="gaming-entry" style="width:100%">
          <option value="panel">🖥 مستقیم پنل — بدون وورکر (سریع‌ترین اگر مستقیم در دسترس است)</option>
          <option value="direct" selected>☁ مستقیم کلادفلر — ضد فیلتر</option>
          <option value="vps">🇮🇷 VPS ایران — پایدارترین (ضد قطعی)</option>
        </select></div>
      <div><label style="font-size:11px;color:var(--t3)">کشور خروج (Route) — فقط با نود خروج واقعی</label>
        <select id="gaming-location" style="width:100%"><option value="auto">auto — Railway (کنترل‌پلین)</option></select></div>
      <div><label style="font-size:11px;color:var(--t3)">آدرس اندپوینت (ورودی — نه IP خروج)</label>
        <input id="gaming-override-ip" placeholder="آدرس اتصال کلاینت — IP خروج را عوض نمی‌کند" style="width:100%;direction:ltr;text-align:left;font-family:monospace"></div>
    </div>
    <div style="font-size:11px;color:var(--t3);margin-bottom:10px">کانفیگ گیمینگ = بدون mux + fragment ضد DPI + tcpNoDelay + TCP Fast Open + اولویت IPv4 — همه در لینک یا JSON اعمال می‌شوند. <b>نمی‌دانید کدام مسیر برایتان سریع‌تر است؟ اول «مقایسه‌ی مسیرها» را بزنید.</b> اگر سرعت‌تان بعد از مدتی افت کرد، حالت را روی «حداکثری» و ترنسپورت را XHTTP بگذارید. <b style="color:var(--amber-t)">روی ایرانسل، حالت «ایرانسل» را امتحان کنید.</b></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn btn-blue" onclick="gamingCheckExitIP(this)"><i class="ti ti-world"></i> بررسی IP خروج واقعی</button>
      <button class="btn btn-blue" onclick="gamingCompare(this)"><i class="ti ti-scale"></i> مقایسه‌ی مسیرها (پنل vs گیت‌وی)</button>
      <button class="btn btn-g" onclick="gamingGenLinks()"><i class="ti ti-link"></i> تولید لینک‌ها</button>
      <button class="btn btn-g" onclick="gamingGenJson()"><i class="ti ti-code"></i> JSON کامل Xray (بهترین برای گیمینگ)</button>
    </div>
    <div id="gaming-exit-result" style="margin-top:14px;display:none"></div>
    <div id="gaming-compare-result" style="margin-top:14px;display:none"></div>
    <div id="gaming-links-result" style="margin-top:14px;display:none"></div>
    <div id="gaming-json-result" style="margin-top:14px;display:none"></div>
  </div>

  <!-- ۵) پریست بازی‌ها -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-trophy"></i> راهنمای بازی‌ها — سرور کجاست و چه مسیری بزنم؟</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-gamepad"></i> پریست‌های بازی</div>
    <div id="gaming-presets-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px">
      <!-- توسط JS پر می‌شود -->
    </div>
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════════
     ✨ PHASE 38+ — Unified Config Builder (ساخت کانفیگ)
     تنها صفحه‌ی واحد ساخت کانفیگ — همه‌ی گزینه‌ها از
     /api/config-builder/capabilities می‌آیند (قابلیت‌محور؛ هیچ فرضی در JS هاردکد
     نشده). پیش‌نمایش از همان کامپایلر کانونی است؛ ترکیب نامعتبر ساخته نمی‌شود.
     ════════════════════════════════════════════════════════════════════════════ -->
<section class="pg" id="pg-builder">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-wand" style="color:#A78BFA"></i> ساخت کانفیگ — سازنده‌ی یکپارچه</div><div class="tb-sub">قابلیت‌ها از بک‌اند · ترکیب‌های نامعتبر رد می‌شوند · خروجی فقط از کامپایلر کانونی</div></div>
    <div class="tb-right"><span class="badge bg-purple" id="bld-caps-badge">…</span><button class="btn btn-o btn-sm" onclick="loadBuilderPage()"><i class="ti ti-refresh"></i> رفرش</button></div>
  </div>

  <div class="g2 bld-grid" style="align-items:start">
    <div class="card" style="margin-bottom:18px">
      <div class="card-title"><i class="ti ti-list-check"></i> مراحل ساخت</div>

      <div class="bld-step"><div class="bld-step-label">۱ · پروتکل</div><div id="bld-protocols" class="bld-chips"></div><div id="bld-proto-hint" class="bld-hint"></div></div>
      <div class="bld-step"><div class="bld-step-label">۲ · نود</div><div id="bld-nodes" class="bld-nodes"></div><div id="bld-node-detail" class="bld-hint"></div></div>
      <div class="bld-step"><div class="bld-step-label">۳ · ترنسپورت</div><div id="bld-transports" class="bld-chips"></div><div id="bld-tr-hint" class="bld-hint"></div></div>
      <div class="bld-step"><div class="bld-step-label">۴ · امنیت (Security)</div><div id="bld-security" class="bld-chips"></div></div>
      <div class="bld-step"><div class="bld-step-label">۵ · Endpoint Profile (TLS/اندپوینت — نه مسیریابی)</div>
        <select id="bld-ep" class="cm-input" onchange="builderOnEpChange()"></select>
        <div id="bld-ep-custom" style="display:none;gap:8px;margin-top:8px">
          <input id="bld-ep-address" class="cm-input" placeholder="آدرس اندپوینت (ورودی)" style="direction:ltr;text-align:left;font-family:monospace">
          <input id="bld-ep-sni" class="cm-input" placeholder="SNI (اختیاری — معنای TLS، نه جغرافیا)" style="direction:ltr;text-align:left;font-family:monospace">
          <input id="bld-ep-port" class="cm-input" type="number" value="443" placeholder="پورت" style="direction:ltr">
        </div>
        <div class="bld-hint">SNI فقط معنای TLS/اندپوینت دارد — هرگز مسیریابی، هرگز خروج جغرافیایی، هرگز «IP ایران» نیست.</div>
      </div>
      <div class="bld-step"><div class="bld-step-label">۶ · مسیریابی (Routing Policy)</div><div id="bld-routing" class="bld-modes"></div><div id="bld-routing-hint" class="bld-hint"></div></div>
      <div class="bld-step"><div class="bld-step-label">۷ · خروجی کلاینت</div><div id="bld-clients" class="bld-chips"></div><div id="bld-client-hint" class="bld-hint"></div></div>
      <div class="bld-step"><div class="bld-step-label">نام و برچسب</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
          <input id="bld-name" class="cm-input" placeholder="نام کانفیگ (تاریخچه)">
          <input id="bld-remark" class="cm-input" placeholder="remark" style="direction:ltr;text-align:left;font-family:monospace">
        </div>
      </div>
      <div class="bld-actions">
        <button class="btn btn-o" id="bld-preview-btn" onclick="builderPreview(this)"><i class="ti ti-eye"></i> پیش‌نمایش و اعتبارسنجی</button>
        <button class="btn btn-p" id="bld-gen-btn" onclick="builderGenerate(this)"><i class="ti ti-wand"></i> ساخت نهایی</button>
      </div>
    </div>

    <div class="card" style="margin-bottom:18px">
      <div class="card-title"><i class="ti ti-eye"></i> پیش‌نمایش و خروجی (از کامپایلر کانونی)</div>
      <div id="bld-validation"></div>
      <div id="bld-outputs"></div>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><i class="ti ti-history"></i> کانفیگ‌های ساخته‌شده</div>
    <div id="bld-history"><div class="bld-hint">—</div></div>
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════════
     🇮🇷 PHASE 38+ §13 — پروکسی ایران (IRAN_PROXY / Iran Gateway)
     متفاوت از IRAN_DIRECT: خروج واقعی از یک گیت‌وی ایرانیِ اثبات‌شده.
     IP دستی = فقط CONFIGURED؛ فقط شواهد شبکه‌ای = VERIFIED_IRAN_EGRESS.
     ════════════════════════════════════════════════════════════════════════════ -->
<section class="pg" id="pg-iranproxy">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-flag" style="color:#EF4444"></i> 🇮🇷 پروکسی ایران — گیت‌وی ایرانی واقعی</div><div class="tb-sub">ترافیک مقاصد ایرانی از گیت‌وی اثبات‌شده · مقاصد بین‌المللی از نود خروج</div></div>
    <div class="tb-right"><span class="badge bg-amber" id="igw-state-badge">—</span><button class="btn btn-o btn-sm" onclick="loadIranProxyPage()"><i class="ti ti-refresh"></i> رفرش</button></div>
  </div>

  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-info-circle"></i> IRAN_PROXY چیست؟ (و چه نیست)</div>
    <div class="bld-hint" style="margin:10px 0">
      <b>IRAN_DIRECT</b>: سرور ایرانی لازم ندارد — ترافیک ایرانی مستقیم از ISP خود کاربر (USER_ISP) خارج می‌شود.<br>
      <b>IRAN_PROXY</b>: مسیر <span style="direction:ltr;display:inline-block;font-family:monospace">Client → EMIX Entry/Relay → گیت‌وی ایران → اینترنت ایران</span> — به یک گیت‌وی ایرانی <b>واقعی و اثبات‌شده</b> نیاز دارد.<br>
      ⛔ IP دستی، SNI، hostname، Cloudflare و لوکیشن Railway <b>هیچ‌کدام</b> خروج ایرانی را اثبات نمی‌کنند — فقط اندازه‌گیری شبکه‌ای (VERIFIED_IRAN_EGRESS).
    </div>
  </div>

  <div class="g2" style="align-items:start">
    <div class="card" style="margin-bottom:18px">
      <div class="card-title"><i class="ti ti-plus"></i> افزودن / ویرایش گیت‌وی</div>
      <div class="bld-form2">
        <input id="igw-name" class="cm-input" placeholder="نام گیت‌وی (مثلاً Tehran-GW)">
        <input id="igw-endpoint" class="cm-input" placeholder="آدرس (hostname/IP)" style="direction:ltr;text-align:left;font-family:monospace">
        <input id="igw-port" class="cm-input" type="number" value="443" placeholder="پورت" style="direction:ltr">
        <select id="igw-protocol" class="cm-input">
          <option value="http">HTTP Forward Proxy (قابل اثبات)</option>
          <option value="socks5">SOCKS5 (قابل اثبات)</option>
          <option value="emix-worker">EMIX Worker (/exit-check)</option>
          <option value="custom">سایر / بدون پروب (egress مجهول می‌ماند)</option>
        </select>
        <input id="igw-user" class="cm-input" placeholder="نام کاربری (اختیاری)" style="direction:ltr;text-align:left;font-family:monospace">
        <input id="igw-pass" class="cm-input" placeholder="رمز گیت‌وی (اختیاری — هرگز لاگ نمی‌شود)" style="direction:ltr;text-align:left;font-family:monospace">
        <input id="igw-notes" class="cm-input" placeholder="توضیح (اختیاری)">
        <button class="btn btn-p" onclick="iranGwSave(this)"><i class="ti ti-device-floppy"></i> ذخیره گیت‌وی</button>
      </div>
    </div>
    <div class="card" style="margin-bottom:18px">
      <div class="card-title"><i class="ti ti-flag-check"></i> گیت‌وی‌ها و وضعیت اثبات</div>
      <div id="igw-list"><div class="bld-hint">—</div></div>
    </div>
  </div>
</section>

<style>
/* ── Config Builder + Iran Gateway (scoped prefixes bld-/igw-) ─────────── */
.bld-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:1080px){.bld-grid{grid-template-columns:1fr}}
.bld-step{margin:14px 0;padding-bottom:6px;border-bottom:1px dashed var(--card-b)}
.bld-step-label{font-size:12px;color:var(--t3);margin-bottom:8px;font-weight:700}
.bld-chips{display:flex;flex-wrap:wrap;gap:8px}
.bld-chip{padding:8px 14px;border-radius:12px;border:1px solid var(--card-b);background:rgba(139,92,246,.06);cursor:pointer;font-size:13px;transition:.15s}
.bld-chip:hover{border-color:var(--accent)}
.bld-chip.sel{border-color:var(--accent);background:rgba(139,92,246,.18);box-shadow:0 0 0 1px var(--accent)}
.bld-chip.off{opacity:.4;cursor:not-allowed}
.bld-chip .st{font-size:10px;opacity:.8}
.bld-hint{font-size:11.5px;color:var(--t3);margin-top:8px;line-height:1.9}
.bld-nodes{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
.bld-node{padding:10px 12px;border-radius:12px;border:1px solid var(--card-b);cursor:pointer;transition:.15s}
.bld-node:hover{border-color:var(--accent)}
.bld-node.sel{border-color:var(--accent);background:rgba(139,92,246,.15)}
.bld-node .nm{font-weight:700;font-size:13px}
.bld-node .meta{font-size:11px;color:var(--t3);margin-top:4px;line-height:1.8}
.bld-modes{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.bld-mode{padding:10px 12px;border-radius:12px;border:1px solid var(--card-b);cursor:pointer;transition:.15s}
.bld-mode:hover{border-color:var(--accent)}
.bld-mode.sel{border-color:var(--accent);background:rgba(139,92,246,.15)}
.bld-mode .nm{font-weight:700;font-size:13px}
.bld-mode .meta{font-size:11px;color:var(--t3);margin-top:4px;line-height:1.8}
.bld-actions{display:flex;gap:10px;margin-top:16px}
.bld-out{margin:12px 0;padding:10px;border-radius:10px;background:rgba(0,0,0,.25);border:1px solid var(--card-b)}
.bld-out code{display:block;direction:ltr;text-align:left;font-family:'JetBrains Mono',monospace;font-size:11px;word-break:break-all;color:var(--t2);white-space:pre-wrap}
.bld-valid-ok{padding:10px 12px;border-radius:10px;background:rgba(16,185,129,.12);border:1px solid rgba(16,185,129,.4);font-size:12.5px}
.bld-valid-bad{padding:10px 12px;border-radius:10px;background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.4);font-size:12.5px;line-height:2}
.bld-hist{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-top:10px}
.bld-hcard{padding:12px;border-radius:12px;border:1px solid var(--card-b);background:var(--card)}
.bld-hcard .nm{font-weight:700}
.bld-hcard .meta{font-size:11px;color:var(--t3);margin:6px 0;line-height:1.9}
.igw-state{display:inline-block;padding:2px 10px;border-radius:8px;font-size:11px;font-weight:700}
.igw-ok{background:rgba(16,185,129,.2);color:#34d399}
.igw-warn{background:rgba(245,158,11,.2);color:#fbbf24}
.igw-bad{background:rgba(239,68,68,.2);color:#f87171}
.igw-info{background:rgba(59,130,246,.2);color:#60a5fa}
.bld-form2{display:grid;gap:10px;margin-top:10px}
/* ── IRAN DIRECT builder assets (ird-) ───────────────────────────────── */
.ird-assets{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.ird-asset{display:inline-flex;align-items:center;gap:8px;padding:7px 12px;border-radius:12px;border:1px solid var(--card-b);background:rgba(249,115,22,.06);cursor:pointer;font-size:12px;transition:.15s;direction:ltr}
.ird-asset:hover{border-color:var(--accent)}
.ird-asset.sel{border-color:var(--accent);background:rgba(249,115,22,.16);box-shadow:0 0 0 1px var(--accent)}
.ird-asset .addr{font-family:'JetBrains Mono',monospace;font-size:11.5px;word-break:break-all}
.ird-asset .st{font-size:10px;opacity:.9}
.ird-asset .pbtn{cursor:pointer;font-size:12px;line-height:1}
.ird-asset .xbtn{cursor:pointer;color:#f87171;font-size:13px;line-height:1}
</style>

<script>
/* ════════════════════════════════════════════════════════════════════════
   Config Builder + Iran Gateway page logic (isolated script block — a syntax
   error in one block must never kill the dashboard; see pages.py:4627 note).
   Rendering is 100% capability-driven: /api/config-builder/capabilities.
   No protocol-support assumptions are hardcoded in JavaScript.
   ════════════════════════════════════════════════════════════════════════ */
var BLD_CAPS=null, BLD_EPS=[], BLD_SEL={protocol:'',transport:'',security:'',node:'panel',ep:'',routing:'ALL_VPN',client:'xray-json'};

async function loadBuilderPage(){
  try{
    var r=await authF('/api/config-builder/capabilities');
    if(!r.ok){netErr(r,'سازنده‌ی کانفیگ');return}
    BLD_CAPS=await r.json();
    document.getElementById('bld-caps-badge').textContent=BLD_CAPS.nodes.length+' نود · '+Object.keys(BLD_CAPS.clients).length+' خروجی';
    bldRenderProtocols(); bldRenderNodes(); bldRenderRouting(); bldRenderClients();
    bldLoadEndpointProfiles(); bldLoadHistory();
  }catch(e){netErr(e,'سازنده‌ی کانفیگ')}
}

function bldRenderProtocols(){
  var host=document.getElementById('bld-protocols'); if(!host)return;
  host.innerHTML='';
  (BLD_CAPS.protocols||[]).forEach(function(p){
    var d=document.createElement('div');
    d.className='bld-chip'+(p.selectable?'':' off')+(BLD_SEL.protocol===p.protocol?' sel':'');
    d.innerHTML=p.protocol+(p.selectable?'':' <span class="st">('+p.readiness+')</span>');
    if(p.selectable){d.onclick=function(){BLD_SEL.protocol=p.protocol;BLD_SEL.transport='';bldRenderProtocols();bldRenderTransports()}}
    host.appendChild(d);
  });
  var hint=document.getElementById('bld-proto-hint');
  if(hint){var bp=(BLD_CAPS.protocols||[]).filter(function(p){return !p.selectable});
    hint.textContent=bp.length?('پروتکل‌های دیگر فقط تولید لینک/کانفیگ هستند (BETA — بدون ران‌تایم در پنل): '+bp.map(function(p){return p.protocol}).join(', ')):'';}
  bldRenderTransports();
}

function bldNodeProtocols(){
  var node=(BLD_CAPS.nodes||[]).filter(function(n){return n.node_id===BLD_SEL.node})[0];
  return (node&&node.protocols)||[];
}

function bldRenderTransports(){
  var host=document.getElementById('bld-transports'); if(!host)return;
  host.innerHTML='';
  var list=bldNodeProtocols().filter(function(x){return !BLD_SEL.protocol||x.protocol===BLD_SEL.protocol});
  var seen={};
  list.forEach(function(x){
    if(seen[x.transport])return; seen[x.transport]=1;
    var d=document.createElement('div');
    var ok=(x.status==='SUPPORTED');
    d.className='bld-chip'+(ok?'':' off')+(BLD_SEL.transport===x.transport?' sel':'');
    d.innerHTML=x.transport+' <span class="st">'+(ok?'':'('+x.status+')</span>');
    if(ok){d.onclick=function(){BLD_SEL.transport=x.transport;BLD_SEL.security=x.security;bldRenderTransports();bldRenderSecurity()}}
    host.appendChild(d);
  });
  var hint=document.getElementById('bld-tr-hint');
  if(hint){
    var bad=list.filter(function(x){return x.status!=='SUPPORTED'}).map(function(x){return x.transport+' ('+x.status+(x.reason?': '+x.reason:'')+')'});
    hint.textContent=bad.length?('ناموجود روی این نود/دیپلوی: '+bad.join(' · ')):'';
  }
  bldRenderSecurity();
}

function bldRenderSecurity(){
  var host=document.getElementById('bld-security'); if(!host)return;
  host.innerHTML='';
  var list=bldNodeProtocols().filter(function(x){return (!BLD_SEL.protocol||x.protocol===BLD_SEL.protocol)&&(!BLD_SEL.transport||x.transport===BLD_SEL.transport)});
  var seen={};
  list.forEach(function(x){
    if(seen[x.security])return; seen[x.security]=1;
    var d=document.createElement('div');
    d.className='bld-chip'+(BLD_SEL.security===x.security?' sel':'');
    d.textContent=x.security;
    d.onclick=function(){BLD_SEL.security=x.security;bldRenderSecurity()};
    host.appendChild(d);
  });
}

function bldRenderNodes(){
  var host=document.getElementById('bld-nodes'); if(!host)return;
  host.innerHTML='';
  (BLD_CAPS.nodes||[]).forEach(function(n){
    var d=document.createElement('div');
    d.className='bld-node'+(BLD_SEL.node===n.node_id?' sel':'');
    var eg=n.egress||{};
    var egBadge=eg.classification==='VERIFIED_EGRESS'?'<span class="igw-state igw-ok">EGRESS ✓</span>':(eg.classification==='CONFIGURED_ONLY'?'<span class="igw-state igw-warn">CONFIGURED</span>':'<span class="igw-state igw-info">UNKNOWN</span>');
    d.innerHTML='<div class="nm">'+esc(n.name||n.node_id)+'</div><div class="meta">'+esc(n.role||'')+' · '+esc(n.state||'')+'<br>UDP: '+esc(String(n.udp))+' '+egBadge+'</div>';
    d.onclick=function(){BLD_SEL.node=n.node_id;BLD_SEL.transport='';bldRenderNodes()};
    host.appendChild(d);
    var det=document.getElementById('bld-node-detail');
    if(det&&BLD_SEL.node===n.node_id){
      det.innerHTML='نود انتخابی: <b>'+esc(n.name||n.node_id)+'</b> — '+esc(n.deployment_label||'')+'<br>'+
        'TCP: '+esc(String(n.tcp))+' · UDP: '+esc(String(n.udp))+' · TLS: '+esc(String(n.tls))+' — '+esc(n.state_note||'')+
        (eg.classification==='VERIFIED_EGRESS'?('<br>خروج اثبات‌شده: '+esc(eg.public_ip||'?')+' → '+esc(eg.country||'')):'');
    }
  });
}

function bldRenderRouting(){
  var host=document.getElementById('bld-routing'); if(!host)return;
  host.innerHTML='';
  (BLD_CAPS.routing_policies||[]).forEach(function(p){
    var d=document.createElement('div');
    d.className='bld-mode'+(BLD_SEL.routing===p.policy?' sel':'');
    var legs=p.legs&&p.legs.iran?('<span style="direction:ltr;display:inline-block">🇮🇷→'+esc(p.legs.iran)+' · 🌍→'+esc(p.legs.international)+'</span>'):'admin-defined';
    d.innerHTML='<div class="nm">'+esc(p.policy)+'</div><div class="meta">'+legs+'<br>'+esc(p.egress||'')+'</div>';
    d.onclick=function(){BLD_SEL.routing=p.policy;bldRenderRouting()};
    host.appendChild(d);
  });
  var hint=document.getElementById('bld-routing-hint');
  var gw=BLD_CAPS.iran_gateway||{};
  if(hint){hint.innerHTML='گیت‌وی ایران: <b>'+esc(gw.state||'UNCONFIGURED')+'</b>'+(gw.verified_count?(' ('+gw.verified_count+' اثبات‌شده)'):'')+' — IRAN_PROXY بدون گیت‌وی اثبات‌شده ساخته نمی‌شود.'}
}

function bldRenderClients(){
  var host=document.getElementById('bld-clients'); if(!host)return;
  host.innerHTML='';
  Object.keys(BLD_CAPS.clients||{}).forEach(function(k){
    var c=BLD_CAPS.clients[k];
    var d=document.createElement('div');
    d.className='bld-chip'+(BLD_SEL.client===k?' sel':'');
    d.innerHTML=k+' <span class="st">('+(c.split_tunnel==='SPLIT_TUNNEL_SUPPORTED'?'split ✓':'بدون split')+')</span>';
    d.onclick=function(){BLD_SEL.client=k;bldRenderClients()};
    host.appendChild(d);
  });
  var hint=document.getElementById('bld-client-hint');
  if(hint){var c=BLD_CAPS.clients[BLD_SEL.client]||{};
    hint.textContent=c.routing_rules?String(c.routing_rules):''}
}

async function bldLoadEndpointProfiles(){
  try{
    var r=await authF('/api/endpoint-profiles');
    if(!r.ok){netErr(r,'Endpoint Profiles');return}
    var j=await r.json();
    BLD_EPS=j.profiles||j||[];
    var sel=document.getElementById('bld-ep'); if(!sel)return;
    sel.innerHTML='<option value="">استاندارد (panel host)</option><option value="__custom__">اندپوینت سفارشی…</option>';
    BLD_EPS.forEach(function(p){var o=document.createElement('option');o.value=p.id;o.textContent=p.name+' — '+(p.address||'')+(p.sni?(' / SNI:'+p.sni):'');sel.appendChild(o)});
  }catch(e){netErr(e,'Endpoint Profiles')}
}

function builderOnEpChange(){
  var sel=document.getElementById('bld-ep');
  BLD_SEL.ep=sel.value;
  document.getElementById('bld-ep-custom').style.display=(sel.value==='__custom__')?'grid':'none';
}

function bldPayload(){
  var custom=(BLD_SEL.ep==='__custom__');
  return {
    name:document.getElementById('bld-name').value||'',
    remark:document.getElementById('bld-remark').value||'EMIX',
    protocol:BLD_SEL.protocol, transport:BLD_SEL.transport, security:BLD_SEL.security,
    node_id:BLD_SEL.node,
    endpoint_profile_id:(custom?'':BLD_SEL.ep),
    custom_address:custom?document.getElementById('bld-ep-address').value:'',
    custom_sni:custom?document.getElementById('bld-ep-sni').value:'',
    custom_port:custom?(parseInt(document.getElementById('bld-ep-port').value)||443):443,
    routing_policy:BLD_SEL.routing, client_format:BLD_SEL.client
  };
}

function bldBusy(btn,on){if(!btn)return;btn.disabled=on;var i=btn.querySelector('i');if(i){i.className=on?'ti ti-loader-2 spin':'ti '+(btn.id==='bld-gen-btn'?'ti-wand':'ti-eye')}}

function bldRenderResult(j){
  var v=document.getElementById('bld-validation'), o=document.getElementById('bld-outputs');
  if(!j.ok){
    v.innerHTML='<div class="bld-valid-bad">⛔ <b>INVALID</b> — مرحله: '+esc(j.stage||'?')+'<br>'+ (j.errors||[]).map(esc).join('<br>') +'</div>';
    o.innerHTML=''; return;
  }
  v.innerHTML='<div class="bld-valid-ok">✓ <b>VALID</b> — '+esc(j.preview.protocol)+' / '+esc(j.preview.transport)+' / '+esc(j.preview.security)+' · نود: '+esc(j.preview.node.label||j.preview.node.node_id)+' · مسیریابی: '+esc(j.preview.routing)+(j.credential_placeholder?' · (credential پیش‌نمایش: جای‌نگهدار)':'')+'</div>';
  var out=j.outputs||{}; var h='';
  if(out.uri){h+='<div class="bld-out"><b>URI</b> <button class="btn btn-sm btn-o" onclick="bldCopy(this)">کپی</button> <button class="btn btn-sm btn-o" onclick="showQR(window.__bldUri)">QR</button><code>'+esc(out.uri)+'</code></div>';window.__bldUri=out.uri}
  if(out.xray_json){h+='<div class="bld-out"><b>Xray JSON</b><code>'+esc(JSON.stringify(out.xray_json,null,1))+'</code></div>'}
  if(out.subscription){h+='<div class="bld-out"><b>Subscription (base64)</b><code>'+esc(out.subscription)+'</code></div>'}
  var rd=j.preview&&j.preview.routing_detail;
  if(rd&&rd.legs){
    h+='<div class="bld-out"><b>مسیریابی (explainable)</b><br>';
    Object.keys(rd.legs).forEach(function(k){h+=esc(k)+' → '+esc(rd.legs[k].decision)+' · خروج: '+esc(rd.legs[k].egress)+'<br>'});
    if(rd.iran_gateway){h+='گیت‌وی ایران: '+esc(rd.iran_gateway.verdict||'')+'<br>'}
    if(rd.split_rules){h+='قواعد split-tunnel: '+rd.split_rules.rules.length+' قاعده ('+esc(rd.split_rules.mechanism||'')+')'}
    h+='</div>';
  }
  if(out.split_rules){h+='<div class="bld-hint">قواعد split-tunnel در JSON خروجی گنجانده شد (GEOIP:ir + CIDR از دیتاست اثبات‌شده)</div>'}
  o.innerHTML=h;
}

function bldCopy(btn){if(window.__bldUri){navigator.clipboard.writeText(window.__bldUri).then(function(){toast('کپی شد ✓','ok')})}}

async function builderPreview(btn){
  bldBusy(btn,true);
  try{
    var r=await authF('/api/config-builder/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bldPayload())});
    var j=await r.json(); bldRenderResult(j);
    if(!j.ok)toast('ترکیب نامعتبر — ساخته نشد','err');
  }catch(e){netErr(e,'پیش‌نمایش کانفیگ')}finally{bldBusy(btn,false)}
}

async function builderGenerate(btn){
  bldBusy(btn,true);
  try{
    var r=await authF('/api/config-builder/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bldPayload())});
    var j=await r.json(); bldRenderResult(j);
    if(j.ok){toast('کانفیگ ساخته شد ✓','ok');bldLoadHistory()}else{toast('ساخت ناموفق — '+((j.errors||[''])[0]).slice(0,60),'err')}
  }catch(e){netErr(e,'ساخت کانفیگ')}finally{bldBusy(btn,false)}
}

async function bldLoadHistory(){
  try{
    var r=await authF('/api/config-builder/history');
    if(!r.ok)return;
    var j=await r.json();
    var host=document.getElementById('bld-history'); if(!host)return;
    if(!(j.history||[]).length){host.innerHTML='<div class="bld-hint">هنوز کانفیگی ساخته نشده — اولین را با «ساخت نهایی» بسازید.</div>';return}
    host.className='bld-hist';
    host.innerHTML=j.history.map(function(h){
      return '<div class="bld-hcard"><div class="nm">'+esc(h.name)+' <span class="igw-state igw-ok">'+esc(h.status)+'</span></div>'+
      '<div class="meta">'+esc(h.protocol)+' / '+esc(h.transport)+' / '+esc(h.security)+' · نود: '+esc(h.node)+' · مسیریابی: '+esc(h.routing)+'<br>'+esc(h.created_at_iso||'')+' · checksum: '+esc((h.checksum||'').slice(0,10))+'</div>'+
      '<button class="btn btn-sm btn-o" onclick="bldHistView(\''+h.history_id+'\')">مشاهده/کپی</button> '+
      '<button class="btn btn-sm btn-o" onclick="bldHistRegen(\''+h.history_id+'\')">بازسازی</button> '+
      '<button class="btn btn-sm btn-d" onclick="bldHistDel(\''+h.history_id+'\')">حذف</button></div>';
    }).join('');
  }catch(e){netErr(e,'تاریخچه‌ی کانفیگ')}
}

async function bldHistView(id){
  try{
    var r=await authF('/api/config-builder/history/'+id+'?reveal=1');
    if(!r.ok){toast('یافت نشد','err');return}
    var j=await r.json(); var e=j.entry||{};
    window.__bldUri=e.uri||'';
    var v=document.getElementById('bld-validation'), o=document.getElementById('bld-outputs');
    v.innerHTML='<div class="bld-valid-ok">✓ کانفیگ: <b>'+esc(e.name)+'</b> — '+esc((e.outputs_summary||{}).protocol||'')+' · '+esc((e.outputs_summary||{}).transport||'')+'</div>';
    o.innerHTML=e.uri?('<div class="bld-out"><b>URI</b> <button class="btn btn-sm btn-o" onclick="bldCopy(this)">کپی</button> <button class="btn btn-sm btn-o" onclick="showQR(window.__bldUri)">QR</button><code>'+esc(e.uri)+'</code></div>'):'<div class="bld-hint">URI در تاریخچه ذخیره نشده — از «بازسازی» استفاده کنید</div>';
  }catch(err){netErr(err,'مشاهده‌ی کانفیگ')}
}

async function bldHistRegen(id){
  try{
    var r=await authF('/api/config-builder/history/'+id+'/regenerate',{method:'POST'});
    var j=await r.json();
    if(j.ok){bldRenderResult(j);toast('بازسازی شد'+(j.deterministic_match?' (checksum یکسان ✓)':''),'ok');bldLoadHistory()}else{toast('بازسازی ناموفق','err')}
  }catch(e){netErr(e,'بازسازی کانفیگ')}
}

async function bldHistDel(id){
  if(!confirm('این کانفیگ از تاریخچه حذف شود؟'))return;
  try{
    var r=await authF('/api/config-builder/history/'+id,{method:'DELETE'});
    if(r.ok){toast('حذف شد','ok');bldLoadHistory()}else{toast('حذف ناموفق','err')}
  }catch(e){netErr(e,'حذف کانفیگ')}
}

/* ── Iran Gateway (پروکسی ایران) ───────────────────────────────────────── */
var IGW_STATES_FA={UNCONFIGURED:'پیکربندی‌نشده',CONFIGURED:'ثبت‌شده (غیراثباتی)',REACHABLE:'در دسترس',HEALTHY:'سلامت',DEGRADED:'کهنه',UNREACHABLE:'غیرقابل‌دسترس',VERIFIED_IRAN_EGRESS:'خروج ایران اثبات‌شده ✓',ROUTE_MISMATCH:'عدم‌تطابق مسیر',UNSUPPORTED:'غیرقابل‌اثبات',UNKNOWN:'مجهول'};
function igwBadge(st){
  var cls=(st==='VERIFIED_IRAN_EGRESS')?'igw-ok':(st==='ROUTE_MISMATCH'||st==='UNREACHABLE'||st==='DEGRADED')?'igw-bad':(st==='REACHABLE'||st==='HEALTHY')?'igw-warn':'igw-info';
  return '<span class="igw-state '+cls+'">'+esc(IGW_STATES_FA[st]||st)+'</span>';
}

async function loadIranProxyPage(){
  try{
    var r=await authF('/api/iran-gateway');
    if(!r.ok){netErr(r,'پروکسی ایران');return}
    var j=await r.json();
    var b=document.getElementById('igw-state-badge');
    if(b){b.textContent=IGW_STATES_FA[j.state]||j.state; b.className='badge '+(j.state==='VERIFIED_IRAN_EGRESS'?'bg-green':(j.state==='UNCONFIGURED'?'bg-amber':'bg-blue'))}
    var host=document.getElementById('igw-list'); if(!host)return;
    if(!(j.gateways||[]).length){host.innerHTML='<div class="bld-hint">گیت‌وی‌ای ثبت نشده — IRAN_PROXY بدون گیت‌وی واقعی ساخته نمی‌شود (IRAN_DIRECT نیازی به سرور ایران ندارد).</div>';return}
    host.innerHTML=j.gateways.map(function(g){
      return '<div class="bld-hcard" style="margin:8px 0"><div class="nm">'+esc(g.name)+' '+igwBadge(g.state)+'</div>'+
      '<div class="meta" style="direction:ltr;text-align:left;font-family:monospace">'+esc(g.endpoint)+':'+esc(String(g.port))+' · '+esc(g.protocol)+(g.auth_configured?' · 🔑':'')+'</div>'+
      '<div class="bld-hint">'+esc(g.state_reason||'')+(g.last_egress&&g.last_egress.public_ip?('<br>آخرین خروج اندازه‌گیری‌شده: '+esc(g.last_egress.public_ip)+' → '+esc(g.last_egress.country_code||'?')):'')+'</div>'+
      '<button class="btn btn-sm btn-p" onclick="iranGwCheck(\''+g.gateway_id+'\',this)">بررسی و اثبات خروج</button> '+
      '<button class="btn btn-sm btn-d" onclick="iranGwDel(\''+g.gateway_id+'\')">حذف</button></div>';
    }).join('');
  }catch(e){netErr(e,'پروکسی ایران')}
}

async function iranGwSave(btn){
  bldBusy(btn,true);
  try{
    var body={name:document.getElementById('igw-name').value,endpoint:document.getElementById('igw-endpoint').value,
      port:parseInt(document.getElementById('igw-port').value)||443,protocol:document.getElementById('igw-protocol').value,
      auth_username:document.getElementById('igw-user').value,auth_password:document.getElementById('igw-pass').value,
      notes:document.getElementById('igw-notes').value};
    var r=await authF('/api/iran-gateway',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    var j=await r.json();
    if(j.ok){toast('گیت‌وی ذخیره شد — وضعیت: CONFIGURED (هنوز اثبات‌نشده) ✓','ok');loadIranProxyPage()}
    else{toast((j.errors||['خطا'])[0],'err')}
  }catch(e){netErr(e,'ذخیره‌ی گیت‌وی')}finally{bldBusy(btn,false)}
}

async function iranGwCheck(id,btn){
  if(btn){btn.disabled=true;btn.innerHTML='<i class="ti ti-loader-2 spin"></i> در حال اثبات…'}
  try{
    var r=await authF('/api/iran-gateway/'+id+'/check',{method:'POST'});
    var j=await r.json();
    if(j.state==='VERIFIED_IRAN_EGRESS')toast('خروج ایرانی اثبات شد ✓ ('+(j.egress&&j.egress.public_ip)+')','ok');
    else if(j.state==='ROUTE_MISMATCH')toast('ROUTE_MISMATCH — خروج اندازه‌گیری‌شده ایران نیست!','err');
    else toast('وضعیت: '+(IGW_STATES_FA[j.state]||j.state),'warn');
    loadIranProxyPage();
  }catch(e){netErr(e,'بررسی گیت‌وی');if(btn){btn.disabled=false;btn.textContent='بررسی'}}
}

async function iranGwDel(id){
  if(!confirm('گیت‌وی حذف شود؟'))return;
  try{
    var r=await authF('/api/iran-gateway/'+id,{method:'DELETE'});
    if(r.ok){toast('حذف شد','ok');loadIranProxyPage()}
  }catch(e){netErr(e,'حذف گیت‌وی')}
}
</script>

<script>
/* ════════════════════════════════════════════════════════════════════════
   🇮🇷 IRAN DIRECT — ساخت کانفیگ با IP سالم + هندشیک (بلاک ایزوله)
   آینه‌ی «ساخت کانفیگ» با مسیریابی ثابت IRAN_DIRECT. رندر ۱۰۰٪
   قابلیت‌محور از /api/config-builder/capabilities؛ ساخت کانفیگ فقط از
   API کانونی config-builder (preview/generate) — هیچ emitter در JS نیست.
   IP دستی = CONFIGURED_ENDPOINT؛ SNI = فقط معنای TLS.
   ════════════════════════════════════════════════════════════════════════ */
var IRD_CAPS=null, IRD_ASSETS={ips:[],handshakes:[]};
var IRD_SEL={protocol:'',transport:'',security:'',node:'panel',client:'xray-json',ip_id:'',hs_id:''};

async function irdLoad(){
  try{
    var r=await authF('/api/config-builder/capabilities');
    if(r.ok)IRD_CAPS=await r.json();
    var a=await authF('/api/iran-direct/assets');
    if(a.ok)IRD_ASSETS=await a.json();
    irdRenderProtocols(); irdRenderNodes(); irdRenderClients(); irdRenderAssets(); irdLoadHistory();
  }catch(e){netErr(e,'IRAN DIRECT')}
}

async function irdRefreshAssets(){
  try{
    var a=await authF('/api/iran-direct/assets');
    if(a.ok){IRD_ASSETS=await a.json(); irdRenderAssets()}
  }catch(e){}
}

function irdBusy(btn,on){if(!btn)return;btn.disabled=on;var i=btn.querySelector('i');if(i){if(!btn.dataset.icon)btn.dataset.icon=i.className;i.className=on?'ti ti-loader-2 spin':btn.dataset.icon}}

/* ── Steps 1-4: قابلیت‌محور (همان منبع سازنده‌ی کانونی) ──────────────── */
function irdRenderProtocols(){
  var host=document.getElementById('ird-protocols'); if(!host)return;
  if(!IRD_SEL.protocol){
    var first=(IRD_CAPS&&IRD_CAPS.protocols||[]).filter(function(p){return p.selectable})[0];
    if(first)IRD_SEL.protocol=first.protocol;
  }
  host.innerHTML='';
  (IRD_CAPS&&IRD_CAPS.protocols||[]).forEach(function(p){
    var d=document.createElement('div');
    d.className='bld-chip'+(p.selectable?'':' off')+(IRD_SEL.protocol===p.protocol?' sel':'');
    d.innerHTML=esc(p.protocol)+(p.selectable?'':' <span class="st">('+esc(p.readiness)+')</span>');
    if(p.selectable){d.onclick=function(){IRD_SEL.protocol=p.protocol;IRD_SEL.transport='';irdRenderProtocols()}}
    host.appendChild(d);
  });
  var hint=document.getElementById('ird-proto-hint');
  if(hint){var bp=(IRD_CAPS&&IRD_CAPS.protocols||[]).filter(function(p){return !p.selectable});
    hint.textContent=bp.length?('پروتکل‌های دیگر فقط تولید لینک/کانفیگ (BETA — بدون ران‌تایم پنل): '+bp.map(function(p){return p.protocol}).join(', ')):'';}
  irdRenderTransports();
}

function irdNodeProtocols(){
  var node=(IRD_CAPS&&IRD_CAPS.nodes||[]).filter(function(n){return n.node_id===IRD_SEL.node})[0];
  return (node&&node.protocols)||[];
}

function irdRenderTransports(){
  var host=document.getElementById('ird-transports'); if(!host)return;
  host.innerHTML='';
  var list=irdNodeProtocols().filter(function(x){return !IRD_SEL.protocol||x.protocol===IRD_SEL.protocol});
  var supported=list.filter(function(x){return x.status==='SUPPORTED'});
  if(!IRD_SEL.transport&&supported.length)IRD_SEL.transport=supported[0].transport;
  var seen={};
  list.forEach(function(x){
    if(seen[x.transport])return; seen[x.transport]=1;
    var ok=(x.status==='SUPPORTED');
    var d=document.createElement('div');
    d.className='bld-chip'+(ok?'':' off')+(IRD_SEL.transport===x.transport?' sel':'');
    d.innerHTML=esc(x.transport)+' <span class="st">'+(ok?'':'('+esc(x.status)+')</span>');
    if(ok){d.onclick=function(){IRD_SEL.transport=x.transport;IRD_SEL.security=x.security;irdRenderTransports()}}
    host.appendChild(d);
  });
  var hint=document.getElementById('ird-tr-hint');
  if(hint){
    var bad=list.filter(function(x){return x.status!=='SUPPORTED'}).map(function(x){return x.transport+' ('+x.status+(x.reason?': '+x.reason:'')+')'});
    hint.textContent=bad.length?('ناموجود روی این نود/دیپلوی: '+bad.join(' · ')):'';
  }
  irdRenderSecurity();
}

function irdRenderSecurity(){
  var host=document.getElementById('ird-security'); if(!host)return;
  host.innerHTML='';
  var list=irdNodeProtocols().filter(function(x){return (!IRD_SEL.protocol||x.protocol===IRD_SEL.protocol)&&(!IRD_SEL.transport||x.transport===IRD_SEL.transport)});
  if(!IRD_SEL.security&&list.length)IRD_SEL.security=list[0].security;
  var seen={};
  list.forEach(function(x){
    if(seen[x.security])return; seen[x.security]=1;
    var d=document.createElement('div');
    d.className='bld-chip'+(IRD_SEL.security===x.security?' sel':'');
    d.textContent=x.security;
    d.onclick=function(){IRD_SEL.security=x.security;irdRenderSecurity()};
    host.appendChild(d);
  });
}

function irdRenderNodes(){
  var host=document.getElementById('ird-nodes'); if(!host)return;
  host.innerHTML='';
  (IRD_CAPS&&IRD_CAPS.nodes||[]).forEach(function(n){
    var d=document.createElement('div');
    d.className='bld-node'+(IRD_SEL.node===n.node_id?' sel':'');
    var eg=n.egress||{};
    var egBadge=eg.classification==='VERIFIED_EGRESS'?'<span class="igw-state igw-ok">EGRESS ✓</span>':(eg.classification==='CONFIGURED_ONLY'?'<span class="igw-state igw-warn">CONFIGURED</span>':'<span class="igw-state igw-info">UNKNOWN</span>');
    d.innerHTML='<div class="nm">'+esc(n.name||n.node_id)+'</div><div class="meta">'+esc(n.role||'')+' · '+esc(n.state||'')+'<br>UDP: '+esc(String(n.udp))+' '+egBadge+'</div>';
    d.onclick=function(){IRD_SEL.node=n.node_id;IRD_SEL.transport='';irdRenderNodes()};
    host.appendChild(d);
    var det=document.getElementById('ird-node-detail');
    if(det&&IRD_SEL.node===n.node_id){
      det.innerHTML='نود انتخابی: <b>'+esc(n.name||n.node_id)+'</b> — '+esc(n.deployment_label||'')+'<br>'+
        'TCP: '+esc(String(n.tcp))+' · UDP: '+esc(String(n.udp))+' · TLS: '+esc(String(n.tls))+' — '+esc(n.state_note||'')+
        (eg.classification==='VERIFIED_EGRESS'?('<br>خروج اثبات‌شده: '+esc(eg.public_ip||'?')+' → '+esc(eg.country||'')):'');
    }
  });
  irdRenderTransports();   /* تغییر نود ⇒ بازرندر ترنسپورت‌ها (قابلیت نود جدید) */
}

function irdRenderClients(){
  var host=document.getElementById('ird-clients'); if(!host)return;
  var clients=(IRD_CAPS&&IRD_CAPS.clients)||{};
  if(!clients[IRD_SEL.client]){
    var k=Object.keys(clients).filter(function(x){return clients[x].split_tunnel==='SPLIT_TUNNEL_SUPPORTED'})[0];
    if(k)IRD_SEL.client=k;
  }
  host.innerHTML='';
  Object.keys(clients).forEach(function(k){
    var cl=clients[k];
    var splitOk=(cl.split_tunnel==='SPLIT_TUNNEL_SUPPORTED');
    var d=document.createElement('div');
    d.className='bld-chip'+(splitOk?'':' off')+(IRD_SEL.client===k?' sel':'');
    d.innerHTML=esc(k)+' <span class="st">'+(splitOk?'split ✓':'بدون split ⛔')+'</span>';
    if(splitOk){d.onclick=function(){IRD_SEL.client=k;irdRenderClients()}}
    host.appendChild(d);
  });
  var hint=document.getElementById('ird-client-hint');
  if(hint){hint.innerHTML='IRAN_DIRECT نیازمند کلاینتی است که قواعد split-tunnel را واقعاً اعمال کند — فرمت‌های ساده‌ی URI/subscription صادقانه غیرفعال‌اند (<b>SPLIT_TUNNEL_NOT_SUPPORTED</b>).'+' خروجی Xray JSON شامل قواعد GEOIP:ir + CIDR دیتاست ایران است.'}
}

/* ── Steps 5-6: دارایی‌ها (IP سالم + هندشیک) ─────────────────────────── */
function irdRenderAssets(){
  var hip=document.getElementById('ird-ips'), hhs=document.getElementById('ird-hss');
  if(hip){
    if(!(IRD_ASSETS.ips||[]).length){hip.innerHTML='<div class="bld-hint">IP سالمی ذخیره نشده — با دکمه‌ی «ذخیره در لیست» اضافه کن، یا مستقیم در فیلد بالا تایپ کن.</div>'}
    else{
      hip.innerHTML='';
      IRD_ASSETS.ips.forEach(function(ip){
        var d=document.createElement('div');
        d.className='ird-asset'+(ip.id===IRD_SEL.ip_id?' sel':'');
        var pr=ip.last_probe||{};
        var prBadge=pr.state==='TLS_VERIFIED'?' <span class="st" style="color:#34d399">TLS ✓ '+(pr.tls_ms||'?')+'ms</span>':(pr.state==='TCP_REACHABLE'?' <span class="st" style="color:#fbbf24">TCP '+(pr.tcp_ms||'?')+'ms</span>':(pr.state==='UNREACHABLE'?' <span class="st" style="color:#f87171">UNREACHABLE</span>':''));
        d.innerHTML='<span class="addr">'+esc(ip.address)+((ip.port&&ip.port!==443)?':'+esc(String(ip.port)):'')+'</span>'+prBadge+(ip.use_count?' <span class="st">×'+toFa(ip.use_count)+'</span>':'')+' <span class="pbtn" title="تست از سرور پنل">⚡</span><span class="xbtn" title="حذف">✕</span>';
        d.onclick=function(ev){
          var t=ev.target||ev.srcElement; var cls=(t&&t.className)||'';
          if(cls.indexOf('xbtn')>=0){irdDelIp(ip.id);return}
          if(cls.indexOf('pbtn')>=0){irdProbeIp(ip.id);return}
          IRD_SEL.ip_id=ip.id;
          var ii=document.getElementById('ird-ip-input'); if(ii)ii.value=ip.address;
          var pp=document.getElementById('ird-port'); if(pp)pp.value=ip.port||443;
          irdRenderAssets();
        };
        hip.appendChild(d);
      });
    }
  }
  if(hhs){
    if(!(IRD_ASSETS.handshakes||[]).length){hhs.innerHTML='<div class="bld-hint">هندشیکی ذخیره نشده — دامنه‌ی هندشیک را اضافه کن یا مستقیم تایپ کن.</div>'}
    else{
      hhs.innerHTML='';
      IRD_ASSETS.handshakes.forEach(function(hs){
        var d=document.createElement('div');
        d.className='ird-asset'+(hs.id===IRD_SEL.hs_id?' sel':'');
        d.innerHTML='<span class="addr">'+esc(hs.sni)+'</span>'+(hs.use_count?' <span class="st">×'+toFa(hs.use_count)+'</span>':'')+' <span class="xbtn" title="حذف">✕</span>';
        d.onclick=function(ev){
          var t=ev.target||ev.srcElement; var cls=(t&&t.className)||'';
          if(cls.indexOf('xbtn')>=0){irdDelHs(hs.id);return}
          IRD_SEL.hs_id=hs.id;
          var hi=document.getElementById('ird-hs-input'); if(hi)hi.value=hs.sni;
          irdRenderAssets();
        };
        hhs.appendChild(d);
      });
    }
  }
}

async function irdAddIp(btn){
  var inp=document.getElementById('ird-ip-input');
  var v=(inp.value||'').trim();
  if(!v){toast('IP سالم را وارد کنید','err');return}
  irdBusy(btn,true);
  try{
    var r=await authF('/api/iran-direct/ips',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address:v,port:parseInt(document.getElementById('ird-port').value)||443})});
    var j=await r.json().catch(function(){return{}});
    if(r.ok){IRD_SEL.ip_id=(j.asset||{}).id;await irdRefreshAssets();toast('IP سالم ذخیره شد ✓','ok')}
    else toast(j.detail||'IP نامعتبر است','err');
  }catch(e){netErr(e,'ذخیره‌ی IP')}finally{irdBusy(btn,false)}
}

async function irdDelIp(id){
  if(!confirm('این IP حذف شود؟'))return;
  try{
    var r=await authF('/api/iran-direct/ips/'+id,{method:'DELETE'});
    if(r.ok){if(IRD_SEL.ip_id===id)IRD_SEL.ip_id='';toast('حذف شد','ok');irdRefreshAssets()}
  }catch(e){netErr(e,'حذف IP')}
}

async function irdAddHs(btn){
  var inp=document.getElementById('ird-hs-input');
  var v=(inp.value||'').trim();
  if(!v){toast('هندشیک (دامنه) را وارد کنید','err');return}
  irdBusy(btn,true);
  try{
    var r=await authF('/api/iran-direct/handshakes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sni:v})});
    var j=await r.json().catch(function(){return{}});
    if(r.ok){IRD_SEL.hs_id=(j.asset||{}).id;await irdRefreshAssets();toast('هندشیک ذخیره شد ✓','ok')}
    else toast(j.detail||'هندشیک نامعتبر است (باید دامنه باشد)','err');
  }catch(e){netErr(e,'ذخیره‌ی هندشیک')}finally{irdBusy(btn,false)}
}

async function irdDelHs(id){
  if(!confirm('این هندشیک حذف شود؟'))return;
  try{
    var r=await authF('/api/iran-direct/handshakes/'+id,{method:'DELETE'});
    if(r.ok){if(IRD_SEL.hs_id===id)IRD_SEL.hs_id='';toast('حذف شد','ok');irdRefreshAssets()}
  }catch(e){netErr(e,'حذف هندشیک')}
}

async function irdProbeIp(id){
  toast('در حال تست از سرور پنل…','');
  try{
    var hs=(document.getElementById('ird-hs-input').value||'').trim();
    var r=await authF('/api/iran-direct/ips/'+id+'/probe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sni:hs})});
    var j=await r.json();
    var p=j.probe||{};
    if(p.state==='TLS_VERIFIED')toast('TLS با هندشیک تأیید شد ✓ ('+p.tls_ms+'ms — اندازه‌گیری از سرور پنل)','ok');
    else if(p.state==='TCP_REACHABLE')toast('TCP در دسترس ('+p.tcp_ms+'ms — از سرور پنل؛ TLS با این هندشیک تأیید نشد)','warn');
    else toast('از سرور پنل در دسترس نیست ('+(p.error||p.tls_error||'?')+')','err');
    await irdRefreshAssets();
  }catch(e){netErr(e,'تست IP')}
}

/* ── Payload — همان API کانونی؛ routing ثابت IRAN_DIRECT ────────────── */
function irdPayload(){
  var ip=(document.getElementById('ird-ip-input').value||'').trim();
  var hs=(document.getElementById('ird-hs-input').value||'').trim();
  var address=ip||hs;   /* فقط هندشیک؟ → همان دامنه، آدرس اتصال هم هست */
  return {
    name:document.getElementById('ird-name').value||'',
    remark:document.getElementById('ird-remark').value||'EMIX',
    protocol:IRD_SEL.protocol, transport:IRD_SEL.transport, security:IRD_SEL.security,
    node_id:IRD_SEL.node, endpoint_profile_id:'',
    custom_address:address, custom_sni:hs,
    custom_port:parseInt(document.getElementById('ird-port').value)||443,
    routing_policy:'IRAN_DIRECT', client_format:IRD_SEL.client
  };
}

async function irdMarkUse(){
  try{
    var body={ip_id:IRD_SEL.ip_id||'', handshake_id:IRD_SEL.hs_id||''};
    if(body.ip_id||body.handshake_id)await authF('/api/iran-direct/use',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  }catch(e){}
}

function irdRenderResult(j){
  var v=document.getElementById('ird-validation'), o=document.getElementById('ird-outputs');
  if(!v||!o)return;
  if(!j.ok){
    v.innerHTML='<div class="bld-valid-bad">⛔ <b>INVALID</b> — مرحله: '+esc(j.stage||'?')+'<br>'+(j.errors||[]).map(esc).join('<br>')+'</div>';
    o.innerHTML=''; return;
  }
  v.innerHTML='<div class="bld-valid-ok">✓ <b>VALID</b> — '+esc(j.preview.protocol)+' / '+esc(j.preview.transport)+' / '+esc(j.preview.security)+' · نود: '+esc((j.preview.node||{}).label||(j.preview.node||{}).node_id||'?')+' · مسیریابی: <b>IRAN_DIRECT</b>'+(j.credential_placeholder?' · (credential پیش‌نمایش: جای‌نگهدار)':'')+'</div>';
  var out=j.outputs||{}; var h='';
  if(out.uri){h+='<div class="bld-out"><b>URI</b> <button class="btn btn-sm btn-o" onclick="irdCopy(this)">کپی</button> <button class="btn btn-sm btn-o" onclick="showQR(window.__irdUri)">QR</button><code>'+esc(out.uri)+'</code></div>';window.__irdUri=out.uri}
  if(out.xray_json){h+='<div class="bld-out"><b>Xray JSON</b> <button class="btn btn-sm btn-o" onclick="irdDlJson()">دانلود فایل</button><code>'+esc(JSON.stringify(out.xray_json,null,1))+'</code></div>';window.__irdJson=out.xray_json}
  var rd=j.preview&&j.preview.routing_detail;
  if(rd&&rd.legs){
    h+='<div class="bld-out"><b>مسیریابی IRAN_DIRECT (explainable)</b><br>';
    Object.keys(rd.legs).forEach(function(k){h+=esc(k)+' → '+esc(rd.legs[k].decision)+' · خروج: '+esc(rd.legs[k].egress)+'<br>'});
    if(rd.split_rules){h+='قواعد split-tunnel: '+rd.split_rules.rules.length+' قاعده ('+esc(rd.split_rules.mechanism||'')+') — در خروجی JSON گنجانده شد'}
    h+='</div>';
  }
  o.innerHTML=h;
}

function irdCopy(btn){if(window.__irdUri){navigator.clipboard.writeText(window.__irdUri).then(function(){toast('URI کپی شد ✓','ok')})}}

function irdDlJson(){
  try{
    var blob=new Blob([JSON.stringify(window.__irdJson,null,2)],{type:'application/json'});
    var a=document.createElement('a');a.href=URL.createObjectURL(blob);
    a.download=((document.getElementById('ird-name').value||'emix-iran-direct')+'.json');
    a.click();setTimeout(function(){URL.revokeObjectURL(a.href)},1000);
  }catch(e){toast('دانلود ناموفق','err')}
}

async function irdPreview(btn){
  irdBusy(btn,true);
  try{
    var r=await authF('/api/config-builder/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(irdPayload())});
    var j=await r.json(); irdRenderResult(j);
    if(!j.ok)toast('ترکیب نامعتبر — ساخته نشد','err');
  }catch(e){netErr(e,'پیش‌نمایش IRAN DIRECT')}finally{irdBusy(btn,false)}
}

async function irdGenerate(btn){
  var p=irdPayload();
  if(!p.custom_address){toast('حداقل یکی از IP سالم یا هندشیک را وارد/انتخاب کن','err');return}
  irdBusy(btn,true);
  try{
    var r=await authF('/api/config-builder/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
    var j=await r.json(); irdRenderResult(j);
    if(j.ok){toast('کانفیگ IRAN_DIRECT ساخته شد ✓','ok');irdMarkUse();irdLoadHistory()}
    else toast('ساخت ناموفق — '+(((j.errors||[''])[0])+'').slice(0,70),'err');
  }catch(e){netErr(e,'ساخت کانفیگ IRAN DIRECT')}finally{irdBusy(btn,false)}
}

/* ── History (تاریخچه‌ی مشترک کانونی — فیلتر IRAN_DIRECT) ───────────── */
async function irdLoadHistory(){
  try{
    var r=await authF('/api/config-builder/history');
    if(!r.ok)return;
    var j=await r.json();
    var rows=(j.history||[]).filter(function(h){return h.routing==='IRAN_DIRECT'});
    var host=document.getElementById('ird-history'); if(!host)return;
    if(!rows.length){host.className='';host.innerHTML='<div class="bld-hint">هنوز کانفیگ IRAN_DIRECT نساخته‌ای — اولین را با «ساخت نهایی و تحویل» بساز.</div>';return}
    host.className='bld-hist';
    host.innerHTML=rows.map(function(h){
      return '<div class="bld-hcard"><div class="nm">'+esc(h.name)+' <span class="igw-state igw-ok">'+esc(h.status)+'</span></div>'+
      '<div class="meta">'+esc(h.protocol)+' / '+esc(h.transport)+' / '+esc(h.security)+' · نود: '+esc(h.node)+' · <b>IRAN_DIRECT</b><br>'+esc(h.created_at_iso||'')+' · checksum: '+esc((h.checksum||'').slice(0,10))+'</div>'+
      '<button class="btn btn-sm btn-o" onclick="irdHistView(\''+h.history_id+'\')">مشاهده/کپی</button> '+
      '<button class="btn btn-sm btn-o" onclick="irdHistRegen(\''+h.history_id+'\')">بازسازی</button> '+
      '<button class="btn btn-sm btn-d" onclick="irdHistDel(\''+h.history_id+'\')">حذف</button></div>';
    }).join('');
  }catch(e){netErr(e,'تاریخچه‌ی IRAN DIRECT')}
}

async function irdHistView(id){
  try{
    var r=await authF('/api/config-builder/history/'+id+'?reveal=1');
    if(!r.ok){toast('یافت نشد','err');return}
    var j=await r.json(); var e=j.entry||{};
    window.__irdUri=e.uri||'';
    var v=document.getElementById('ird-validation'), o=document.getElementById('ird-outputs');
    v.innerHTML='<div class="bld-valid-ok">✓ کانفیگ: <b>'+esc(e.name)+'</b> — '+esc((e.outputs_summary||{}).protocol||'')+' · '+esc((e.outputs_summary||{}).transport||'')+' · IRAN_DIRECT</div>';
    o.innerHTML=e.uri?('<div class="bld-out"><b>URI</b> <button class="btn btn-sm btn-o" onclick="irdCopy(this)">کپی</button> <button class="btn btn-sm btn-o" onclick="showQR(window.__irdUri)">QR</button><code>'+esc(e.uri)+'</code></div>'):'<div class="bld-hint">URI در تاریخچه ذخیره نشده — از «بازسازی» استفاده کن</div>';
  }catch(err){netErr(err,'مشاهده‌ی کانفیگ')}
}

async function irdHistRegen(id){
  try{
    var r=await authF('/api/config-builder/history/'+id+'/regenerate',{method:'POST'});
    var j=await r.json();
    if(j.ok){irdRenderResult(j);toast('بازسازی شد'+(j.deterministic_match?' (checksum یکسان ✓)':''),'ok');irdLoadHistory()}else toast('بازسازی ناموفق','err');
  }catch(e){netErr(e,'بازسازی کانفیگ')}
}

async function irdHistDel(id){
  if(!confirm('این کانفیگ از تاریخچه حذف شود؟'))return;
  try{
    var r=await authF('/api/config-builder/history/'+id,{method:'DELETE'});
    if(r.ok){toast('حذف شد','ok');irdLoadHistory()}else toast('حذف ناموفق','err');
  }catch(e){netErr(e,'حذف کانفیگ')}
}
</script>

<!-- ════════════════════════════════════════════════════════════════════════════
     🇮🇷 PHASE 38 / P17 — مسیریابی هوشمند (Split Tunneling صادقانه)
     مقصدهای ایرانی → DIRECT از ISP خود کاربر (USER_ISP)
     مقصدهای بین‌المللی → VPN از نود خروج EMIX
     هیچ برچسب/ادعایی بدون شواهد واقعی نمایش داده نمی‌شود.
     ════════════════════════════════════════════════════════════════════════════ -->
<section class="pg" id="pg-routing">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-route" style="color:#F97316"></i> مسیریابی هوشمند — عبور مستقیم ترافیک داخلی</div><div class="tb-sub">ترافیک ایرانی از ISP خودت · ترافیک بین‌المللی از تونل EMIX</div></div>
    <div class="tb-right"><span class="badge bg-amber" id="routing-mode-badge">—</span><button class="btn btn-o btn-sm" onclick="loadRoutingPage()"><i class="ti ti-refresh"></i> رفرش</button></div>
  </div>

  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-split-route"></i> حالت مسیریابی شبکه (Network Routing Mode)</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin:12px 0">
      <div id="rt-mode-allvpn" class="rt-mode-card" onclick="routingSetMode('ALL_VPN')">
        <div class="rt-mode-title">🌍 همه‌ی ترافیک از VPN</div>
        <div class="rt-mode-sub">همه‌ی مقصدها (داخلی و بین‌المللی) از تونل EMIX عبور می‌کنند</div>
        <div class="rt-mode-tag" id="rt-tag-allvpn">ALL_VPN</div>
      </div>
      <div id="rt-mode-irandirect" class="rt-mode-card" onclick="routingSetMode('IRAN_DIRECT')">
        <div class="rt-mode-title">🇮🇷 ترافیک ایرانی مستقیم</div>
        <div class="rt-mode-sub">مقصدهای ایرانی مستقیم از ISP خودت (بدون VPN) · مقاصدهای بین‌المللی از نود EMIX</div>
        <div class="rt-mode-tag" id="rt-tag-irandirect">IRAN_DIRECT</div>
      </div>
    </div>
    <div id="rt-mode-detail" style="font-size:12px;line-height:2;padding:12px 14px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b)"></div>
    <div style="font-size:11px;color:var(--t3);margin-top:10px;line-height:1.9">
      <b>چطور کار می‌کند؟</b> موتور مسیریابی، IP مقصد را با پایگاه پیشوندهای ایران (RIPEstat — <span id="rt-prefix-count">—</span> پیشوند) تطبیق می‌دهد؛ تطابق ⇒ مسیر DIRECT و خروج از ISP خود کاربر (<b>USER_ISP</b>)؛ عدم تطابق ⇒ تونل VPN.
      تصمیم بر اساس <b>IP نهایی بعد از DNS</b> است — نه پسوند دامنه. کلادفلر و ریلی هرگز به‌عنوان خروج ایرانی طبقه‌بندی نمی‌شوند.
    </div>
  </div>

  <!-- ════════════════════════════════════════════════════════════════════════
       🇮🇷 IRAN DIRECT — ساخت کانفیگ با IP سالم + هندشیک (آینه‌ی «ساخت کانفیگ»)
       مسیریابی ثابت IRAN_DIRECT · اندپوینت از دارایی‌های کاربر ·
       خروجی فقط از کامپایلر کانونی (config-builder API) — صفر emitter در JS.
       ════════════════════════════════════════════════════════════════════════ -->
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-wand" style="color:#F97316"></i> 🇮🇷 ساخت کانفیگ IRAN_DIRECT — IP سالم + هندشیک</div>
    <div class="bld-hint" style="margin:6px 0 0">
      دقیقاً مثل «ساخت کانفیگ» — با این تفاوت که مسیریابی ثابت <b>IRAN_DIRECT</b> است (ترافیک داخلی از ISP خودت · <b>USER_ISP</b> · ترافیک بین‌المللی از تونل EMIX) و اندپوینت اتصال از <b>IP سالم</b> و <b>هندشیک</b>ِ خودت ساخته می‌شود. IP دستی فقط <b>CONFIGURED_ENDPOINT</b> است و SNI فقط معنای TLS دارد — نه مسیریابی، نه خروج جغرافیایی.
    </div>
    <div class="g2 bld-grid" style="align-items:start;margin-top:12px">
      <div>
        <div class="bld-step"><div class="bld-step-label">۱ · پروتکل</div><div id="ird-protocols" class="bld-chips"></div><div id="ird-proto-hint" class="bld-hint"></div></div>
        <div class="bld-step"><div class="bld-step-label">۲ · نود (سرویس پشت اندپوینت)</div><div id="ird-nodes" class="bld-nodes"></div><div id="ird-node-detail" class="bld-hint"></div></div>
        <div class="bld-step"><div class="bld-step-label">۳ · ترنسپورت</div><div id="ird-transports" class="bld-chips"></div><div id="ird-tr-hint" class="bld-hint"></div></div>
        <div class="bld-step"><div class="bld-step-label">۴ · امنیت (Security)</div><div id="ird-security" class="bld-chips"></div></div>
        <div class="bld-step"><div class="bld-step-label">۵ · IP سالم (آدرس اتصال — Address)</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <input id="ird-ip-input" class="cm-input" placeholder="IP سالم — مثل 104.17.1.1 یا دامنه" style="flex:1;min-width:200px;direction:ltr;text-align:left;font-family:monospace">
            <button class="btn btn-o btn-sm" onclick="irdAddIp(this)"><i class="ti ti-plus"></i> ذخیره در لیست</button>
          </div>
          <div id="ird-ips" class="ird-assets"></div>
          <div class="bld-hint">IP دستی = فقط اندپوینت پیکربندی‌شده. «سالم‌بودن از دید ISP خودت» را باید از مرورگر خودت تست کنی — تست سرور پنل فقط «در دسترس بودن از پنل» را می‌سنجد.</div>
        </div>
        <div class="bld-step"><div class="bld-step-label">۶ · هندشیک (SNI/Host)</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <input id="ird-hs-input" class="cm-input" placeholder="دامنه هندشیک — مثل bridge.example.com" style="flex:1;min-width:200px;direction:ltr;text-align:left;font-family:monospace">
            <button class="btn btn-o btn-sm" onclick="irdAddHs(this)"><i class="ti ti-plus"></i> ذخیره در لیست</button>
          </div>
          <div id="ird-hss" class="ird-assets"></div>
          <div class="bld-hint">هندشیک باید <b>دامنه</b> باشد (نه IP). اگر اندپوینتت IP است، هندشیک الزامی است — SNI فقط معنای TLS/اندپوینت دارد و هرگز روی خروج ترافیک داخلی (USER_ISP) اثری ندارد. اگر فقط هندشیک وارد کنی، همان دامنه به‌عنوان آدرس اتصال هم استفاده می‌شود.</div>
        </div>
        <div class="bld-step"><div class="bld-step-label">۷ · پورت اتصال</div><input id="ird-port" class="cm-input" type="number" value="443" style="direction:ltr;max-width:140px"></div>
        <div class="bld-step"><div class="bld-step-label">۸ · خروجی کلاینت</div><div id="ird-clients" class="bld-chips"></div><div id="ird-client-hint" class="bld-hint"></div></div>
        <div class="bld-step"><div class="bld-step-label">نام و برچسب</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
            <input id="ird-name" class="cm-input" placeholder="نام کانفیگ (تاریخچه)">
            <input id="ird-remark" class="cm-input" placeholder="EMIX" style="direction:ltr;text-align:left;font-family:monospace">
          </div>
        </div>
        <div class="bld-actions">
          <button class="btn btn-o" id="ird-preview-btn" onclick="irdPreview(this)"><i class="ti ti-eye"></i> پیش‌نمایش و اعتبارسنجی</button>
          <button class="btn btn-p" id="ird-gen-btn" onclick="irdGenerate(this)"><i class="ti ti-wand"></i> ساخت نهایی و تحویل</button>
        </div>
      </div>
      <div>
        <div style="font-weight:700;font-size:13px;margin:12px 0 8px"><i class="ti ti-eye"></i> پیش‌نمایش و خروجی (از کامپایلر کانونی)</div>
        <div id="ird-validation"></div>
        <div id="ird-outputs"></div>
      </div>
    </div>
  </div>

  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-history"></i> کانفیگ‌های IRAN_DIRECT ساخته‌شده</div>
    <div id="ird-history"><div class="bld-hint">—</div></div>
  </div>

  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-flask"></i> ابزار تشخیص مسیر (Test Route)</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0">
      <input id="rt-test-input" placeholder="دامنه یا IP — مثلاً example.ir یا 5.10.0.1" style="flex:1;min-width:220px;direction:ltr;text-align:left;font-family:monospace">
      <button class="btn btn-g" onclick="routingTestRoute()"><i class="ti ti-radar-2"></i> تست مسیر</button>
    </div>
    <div id="rt-test-result" style="display:none"></div>
  </div>

  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px">
    <div class="card">
      <div class="card-title"><i class="ti ti-database"></i> پایگاه پیشوندهای ایران</div>
      <div id="rt-dataset-body" style="font-size:12px;line-height:2.1">در حال بارگذاری…</div>
      <div style="display:flex;gap:8px;margin-top:10px">
        <button class="btn btn-blue btn-sm" onclick="routingUpdateRules(this)"><i class="ti ti-cloud-download"></i> به‌روزرسانی اتمی از RIPEstat</button>
      </div>
      <div id="rt-rules-result" style="display:none;margin-top:10px;font-size:11.5px"></div>
    </div>
    <div class="card">
      <div class="card-title"><i class="ti ti-chart-pie"></i> حسابداری ترافیک (تفکیک واقعی)</div>
      <div id="rt-traffic-body" style="font-size:12px;line-height:2.1">در حال بارگذاری…</div>
      <div style="font-size:11px;color:var(--t3);margin-top:8px;line-height:1.8">دسته‌بندی بر اساس منطق مسیر/مقصد است — <b>نه</b> پسوند دامنه (.ir).</div>
    </div>
    <div class="card">
      <div class="card-title"><i class="ti ti-plug-connected"></i> پشتیبانی Split Tunnel در کلاینت‌ها</div>
      <div id="rt-split-body" style="font-size:12px;line-height:2.1">در حال بارگذاری…</div>
    </div>
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════════
     👤 PHASE 38 / P2+P3 — حساب‌ها، دستگاه‌ها و سابسکریپشن‌ها
     Account → Subscription → Config → Route → Node → Verified Egress
     محدودیت‌ها backend-side اعمال می‌شوند (نه فقط UI).
     ════════════════════════════════════════════════════════════════════════════ -->
<section class="pg" id="pg-accounts">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-users" style="color:#38BDF8"></i> حساب‌ها، دستگاه‌ها و اشتراک‌ها</div><div class="tb-sub">مدیریت کاربران با محدودیت‌های واقعی سمت سرور</div></div>
    <div class="tb-right"><span class="badge bg-blue" id="accounts-count">—</span><button class="btn btn-o btn-sm" onclick="loadAccountsPage()"><i class="ti ti-refresh"></i> رفرش</button></div>
  </div>

  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-user-plus"></i> ساخت حساب جدید</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:10px 0">
      <div><label style="font-size:11px;color:var(--t3)">نام کاربری</label><input id="ac-username" placeholder="username" style="width:100%;direction:ltr"></div>
      <div><label style="font-size:11px;color:var(--t3)">رمز عبور (حداقل ۸ کاراکتر)</label><input id="ac-password" type="password" placeholder="••••••••" style="width:100%;direction:ltr"></div>
      <div><label style="font-size:11px;color:var(--t3)">سهمیه ترافیک (GB — خالی = نامحدود)</label><input id="ac-quota" type="number" placeholder="" style="width:100%;direction:ltr"></div>
      <div><label style="font-size:11px;color:var(--t3)">انقضا (روز — خالی = بی‌نهایت)</label><input id="ac-expiry" type="number" placeholder="" style="width:100%;direction:ltr"></div>
      <div><label style="font-size:11px;color:var(--t3)">حداکثر دستگاه</label><input id="ac-maxdev" type="number" value="5" style="width:100%;direction:ltr"></div>
      <div><label style="font-size:11px;color:var(--t3)">حداکثر سشن همزمان</label><input id="ac-maxses" type="number" value="3" style="width:100%;direction:ltr"></div>
    </div>
    <button class="btn btn-g" onclick="accountsCreate()"><i class="ti ti-user-plus"></i> ایجاد حساب</button>
    <div style="font-size:11px;color:var(--t3);margin-top:8px;line-height:1.8">رمزها با PBKDF2-SHA256 هش می‌شوند · توکن دستگاه فقط یک‌بار نمایش داده می‌شود و لاگ نمی‌شود.</div>
  </div>

  <div id="ac-list" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px"></div>
  <div id="ac-empty" style="display:none;text-align:center;padding:40px 0;color:var(--t3)">
    <i class="ti ti-users" style="font-size:40px;opacity:.4"></i>
    <div style="margin-top:8px;font-size:13px">هنوز حسابی ساخته نشده — اولین حساب را از فرم بالا بسازید</div>
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════════
     🌐 MULTI-LOC v2 — پل هوشمند چندلوکیشن (Worker-Terminated Egress)
     معماری: کاربر → IP آنیکست CF (colo انتخابی) → Worker v2 (/vl)
              ├─ حالت «خروج CF» : تونل داخل وورکر ختم می‌شود → خروج از colo اجرا
              └─ حالت «تونل»     : /loc/{name} → Railway (پایدار)
     ════════════════════════════════════════════════════════════════════════════ -->
<section class="pg" id="pg-multiloc">
  <div class="node-hero" style="margin-bottom:18px">
    <div class="node-hero-top">
      <div class="node-hero-title">
        <div class="node-hero-icon" style="background:rgba(16,185,129,.15);color:#10B981"><i class="ti ti-world"></i></div>
        <div>
          <div class="tb-title">پل چندلوکیشن v2 — خروج واقعی از لبه‌ی کلادفلر</div>
          <div class="tb-sub">کانفیگ‌های پل‌شده‌ی چند کشور بدون هیچ سرور اضافه + دیباگ فوق پیشرفته با مدرک زنده</div>
        </div>
      </div>
      <div class="tb-right">
        <span class="badge" id="ml-status-badge">بارگذاری...</span>
      </div>
    </div>
    <div class="node-hero-metrics">
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-cloud-bolt"></i><span class="node-metric-label">Worker گیت‌وی</span></div>
        <div class="node-metric-val" id="ml-worker-ver" style="font-size:15px;direction:ltr">—</div>
        <div class="node-metric-sub" id="ml-worker-domain-lbl" style="direction:ltr;text-align:left;overflow:hidden;text-overflow:ellipsis">—</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-flame"></i><span class="node-metric-label">حالت خروج CF (WTE)</span></div>
        <div class="node-metric-val" id="ml-wte-status" style="font-size:15px">—</div>
        <div class="node-metric-sub" id="ml-wte-sub">تونل داخل وورکر ختم می‌شود</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-flag"></i><span class="node-metric-label">لوکیشن‌های تاییدشده</span></div>
        <div class="node-metric-val" id="ml-loc-count" style="font-size:15px">—</div>
        <div class="node-metric-sub" id="ml-loc-sub">با هندشیک واقعی TLS اثبات‌شده</div>
      </div>
      <div class="node-metric">
        <div class="node-metric-top"><i class="ti ti-direction-horizontal"></i><span class="node-metric-label">آخرین خروج تست‌شده</span></div>
        <div class="node-metric-val" id="ml-egress-last" style="font-size:15px">—</div>
        <div class="node-metric-sub" id="ml-egress-sub">مدرک زنده از /egress-test</div>
      </div>
    </div>
  </div>

  <!-- ۱) وضعیت و راه‌اندازی وورکر v2 -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-cloud-cog"></i> گیت‌وی کلادفلر v2 (WTE) و سینک خودکار</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-cloud-bolt"></i> Worker v2 — سرور VLESS داخل وورکر</div>
    <div style="font-size:11.5px;color:var(--t3);margin-bottom:12px;line-height:1.9">
      <b>چی‌کار می‌کند؟</b> تونل VLESS همین‌جا داخل وورکر کلادفلر خاتمه می‌یابد و ترافیک از <b>همان colo</b> که کاربر وارد شده به اینترنت می‌رود
      — یعنی سایت‌ها IP کلادفلرِ آن region را می‌بینند، <b>نه IP ریلوی آمستردام</b>. هر «لوکیشن» = یک IP ورودی آنیکست؛ بدون خرید هیچ سروری.
      <span style="color:var(--amber-t)">اگر وورکر هنوز v1.x است، کد v2 را با یک Paste آپگرید کن (۲ دقیقه):</span>
    </div>
    <div id="ml-worker-upgrade" style="display:none;margin-bottom:14px;padding:14px;background:rgba(250,204,21,.06);border:1px solid rgba(250,204,21,.3);border-radius:10px;font-size:12px;line-height:2">
      <b style="color:var(--amber-t)">آپگرید وورکر به v2 (فقط یک بار):</b><br>
      ۱) <b>dash.cloudflare.com → Workers &amp; Pages</b> → وورکر emix-gateway را باز کن → <b>Edit code</b><br>
      ۲) کل کد را پاک کن و کد v2 زیر را Paste کن → <b>Save and Deploy</b><br>
      ۳) اگر KV بایند نکرده‌ای: Settings → Bindings → KV namespace با نام <code>LOCATIONS</code> بساز و متصل کن<br>
      ۴) متغیر <code>EMIX_TOKEN</code> را مثل قبل نگه دار (برای سینک UUID از پنل)<br>
      <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
        <button class="btn btn-pur" onclick="mlCopyWorkerCode()"><i class="ti ti-clipboard-copy"></i> کپی کد کامل Worker v2</button>
        <a class="btn btn-o" href="/api/multiloc/worker-code" target="_blank" id="ml-worker-code-link" style="display:none">دانلود</a>
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn btn-blue" onclick="mlStatus(true)"><i class="ti ti-radar-2"></i> تست گیت‌وی</button>
      <button class="btn btn-g" onclick="mlSyncWorker(this)"><i class="ti ti-refresh-sync"></i> سینک UUIDها به وورکر</button>
      <span id="ml-sync-result" style="font-size:11.5px;color:var(--t3);align-self:center"></span>
    </div>
  </div>

  <!-- ۲) اسکن colo — دیباگ فوق پیشرفته -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-radar"></i> اسکنر لوکیشن — نقشه‌ی تاییدشده‌ی IP → PoP (مدرک زنده)</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-signal-4g"></i> اسکن و صحت‌سنجی IPهای کلادفلر</div>
    <div style="font-size:11.5px;color:var(--t3);margin-bottom:14px;line-height:1.8">
      هر IP با <b>هندشیک TLS واقعی + GET /cdn-cgi/trace</b> پروب می‌شود؛ فقط IPهایی که واقعاً دامنه‌ی وورکر شما را سرو کنند و coloشان خوانده شود نگه داشته می‌شوند.
      نتیجه: لیست لوکیشن‌های <b>سالم و آماده</b> با RTT — هیچ IP تاییدنشده‌ای به کاربر داده نمی‌شود.
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      <button class="btn btn-g" id="ml-scan-btn" onclick="mlScan(this,false)"><i class="ti ti-radar-2"></i> اسکن سریع (~۳۰ ثانیه)</button>
      <button class="btn btn-blue" id="ml-scan-deep-btn" onclick="mlScan(this,true)"><i class="ti ti-radar"></i> اسکن عمیق (~۹۰ ثانیه)</button>
      <span id="ml-scan-progress" style="font-size:11.5px;color:var(--t3)">آماده</span>
    </div>
    <div id="ml-loc-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px;margin-top:14px"></div>
    <div id="ml-scan-stats" style="margin-top:12px;font-size:11.5px;color:var(--t3)"></div>
  </div>

  <!-- ۳) سازنده‌ی ساده‌ی کانفیگ‌های پل -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-link-plus"></i> سازنده‌ی کانفیگ‌های پل — فقط چند کلیک</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-wand"></i> ساخت کانفیگ‌های چندلوکیشن</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin-bottom:12px">
      <div>
        <label style="font-size:11px;color:var(--t3)">کانفیگ پایه</label>
        <select id="ml-cfg-sel" style="width:100%" class="cm-input"></select>
      </div>
      <div>
        <label style="font-size:11px;color:var(--t3)">حالت خروج</label>
        <select id="ml-mode-sel" style="width:100%" class="cm-input">
          <option value="worker" selected>خروج CF — جعل خروجی (سایت‌ها IP کلادفلر می‌بینند)</option>
          <option value="railway">تونل پایدار — خروج Railway (مثل قبل)</option>
        </select>
      </div>
      <div>
        <label style="font-size:11px;color:var(--t3)">لوکیشن‌ها</label>
        <select id="ml-colo-sel" style="width:100%" class="cm-input">
          <option value="all" selected>همه‌ی لوکیشن‌های تاییدشده</option>
          <option value="auto">فقط Auto (نزدیک‌ترین PoP به ISP)</option>
        </select>
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn btn-p" onclick="mlBuild(this)"><i class="ti ti-magic-wand"></i> ساخت کانفیگ‌های پل</button>
      <button class="btn btn-g" id="ml-copy-all-btn" style="display:none" onclick="mlCopyAll()"><i class="ti ti-clipboard-copy"></i> کپی همه</button>
      <span id="ml-build-result" style="font-size:11.5px;color:var(--t3);align-self:center"></span>
    </div>
    <div id="ml-links-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;margin-top:14px"></div>
    <textarea id="ml-links-raw" style="display:none;width:100%;margin-top:12px;direction:ltr;text-align:left;font-family:monospace;font-size:11px;height:150px" readonly></textarea>
  </div>

  <!-- ۴) SNI-Trace — دیباگ فوق پیشرفته‌ی جعل SNI -->
  <div class="conn-toolbar" style="margin-bottom:14px">
    <div class="conn-toolbar-title"><i class="ti ti-mask"></i> SNI-Trace — اثبات زنده‌ی جعل SNI (نه حدس)</div>
  </div>
  <div class="card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-bug"></i> ردیاب SNI جعلی</div>
    <div style="font-size:11.5px;color:var(--t3);margin-bottom:12px;line-height:1.8">
      پنل با SNI جعلی شما <b>واقعاً</b> به ingress ریلوی و لبه‌ی کلادفلر هندشیک TLS می‌زند و نتیجه را با مدرک نشان می‌دهد:
      آیا هندشیک کامل شد؟ لایه‌ی HTTP با Host درست رسید؟ پس DPI دقیقاً چه SNI‌ای می‌بیند؟
      برای فعال‌سازی، در «ساخت کانفیگ» گزینه‌ی 🎭 SNI جعلی را روشن کن — لینک خروجی sni جعلی + allowInsecure خواهد داشت.
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <input class="cm-input" id="ml-sni-input" placeholder="www.microsoft.com" style="flex:1;min-width:220px;direction:ltr;text-align:left;font-family:monospace">
      <button class="btn btn-pur" onclick="mlSniTrace(this)"><i class="ti ti-route"></i> تست زنده</button>
    </div>
    <div id="ml-sni-result" style="margin-top:14px;display:none"></div>
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════════
     VPN PRO — WireGuard و OpenVPN
     پروتکل‌های مستقل از VLESS/Trojan — کاربر سرور خودش را deploy می‌کند
     ════════════════════════════════════════════════════════════════════════════ -->
<section class="pg" id="pg-vpn">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-shield-lock"></i> VPN Pro — WireGuard &amp; OpenVPN</div><div class="tb-sub">پروتکل‌های کلاسیک — روی سرور VPS خودتان deploy کنید، کانفیگ کلاینت را پنل تولید می‌کند</div></div>
    <div class="tb-right">
      <span class="badge bg-green" id="vpn-status-badge">بارگذاری...</span>
    </div>
  </div>

  <!-- ۱) کارت معرفی و مزایا -->
  <div class="card" style="margin-bottom:18px;background:linear-gradient(155deg,rgba(245,158,11,0.06) 0%,var(--card) 60%);border:1px solid var(--card-b)">
    <div class="card-title"><i class="ti ti-info-circle" style="color:var(--accent)"></i> درباره‌ی WireGuard و OpenVPN</div>
    <div style="font-size:12px;color:var(--t2);line-height:1.9">
      <b>WireGuard</b> مدرن‌ترین پروتکل VPN است — رمزنگاری ChaCha20، سرعت بالا، تأخیر کم. مناسب برای گیمینگ و یوتیوب. <b>OpenVPN</b> قدیمی‌تر ولی به‌شدت سازگار و امن است — برای شبکه‌های شرکت و شرایطی که WireGuard بلاک شده.
      <br><b style="color:var(--amber-t)">تفاوت با VLESS/Trojan:</b> این پروتکل‌ها روی UDP/TCP با TLS واقعی کار می‌کنند (نه WebSocket). روی CDN/Worker قابل عبور نیستند — سرور باید مستقیم (VPS) باشد.
      <br><b>پیشنهاد:</b> یک VPS رایگان Oracle Cloud (Always Free، ۴ هسته ARM) در دبی/آمستردام بگیرید و اسکریپت آماده‌ی پنل را اجرا کنید.
    </div>
  </div>

  <!-- ۲) کارت WireGuard -->
  <div class="card vpn-card vpn-wg-card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-key" style="color:var(--accent)"></i> WireGuard — تولید و مدیریت کانفیگ</div>

    <!-- empty-state: وقتی هنوز سروری ست نشده، راهنمایی واضح نشان بده -->
    <div id="wg-empty-state" class="vpn-empty-state" style="margin-bottom:14px;padding:14px 16px;background:rgba(139,92,246,0.06);border:1px dashed rgba(139,92,246,0.30);border-radius:14px;display:flex;gap:11px;align-items:flex-start">
      <i class="ti ti-server-off" style="color:var(--accent2);font-size:22px;flex-shrink:0;margin-top:2px"></i>
      <div style="flex:1;font-size:11.5px;line-height:1.8">
        <b style="color:var(--accent2)">سرور WireGuard هنوز تنظیم نشده.</b><br>
        روی <b>«اسکریپت راه‌اندازی سرور»</b> بزنید تا دستورات آماده برای VPS را بگیرید، سپس مقادیر برگشتی (آدرس، پورت، کلید عمومی) را اینجا وارد کنید. <b>یا</b> اگر VPS ندارید، یک VPS رایگان Oracle Cloud (Always Free) بگیرید.
        <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn btn-sm btn-g" onclick="vpnShowServerScript(this)"><i class="ti ti-server"></i> گرفتن اسکریپت سرور</button>
          <button class="btn btn-sm btn-blue" onclick="vpnShowServerKey(this)"><i class="ti ti-key"></i> تولید کلید سرور</button>
        </div>
      </div>
    </div>

    <div style="font-size:12px;font-weight:700;margin-bottom:10px;color:var(--t1)">۱) مشخصات سرور</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:12px">
      <div class="vpn-field"><label>آدرس سرور (IP / دامنه)</label>
        <div class="vpn-input-wrap"><i class="ti ti-world vpn-input-ic"></i><input id="wg-endpoint" class="vpn-input" placeholder="vpn.example.com"></div></div>
      <div class="vpn-field"><label>پورت UDP</label>
        <div class="vpn-input-wrap"><i class="ti ti-port vpn-input-ic"></i><input id="wg-port" type="number" value="51820" class="vpn-input"></div></div>
      <div class="vpn-field" style="grid-column:span 2"><label>کلید عمومی سرور (Public Key)</label>
        <div class="vpn-input-wrap"><i class="ti ti-key vpn-input-ic"></i><input id="wg-server-pub" placeholder="ServerPublicKeyBase64=" class="vpn-input"></div></div>
    </div>

    <div style="font-size:12px;font-weight:700;margin:14px 0 10px;color:var(--t1)">۲) تنظیمات کلاینت (پیش‌فرض سالم — قابل ویرایش)</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:14px">
      <div class="vpn-field"><label>IP کلاینت (CIDR)</label>
        <div class="vpn-input-wrap"><i class="ti ti-address-book vpn-input-ic"></i><input id="wg-client-ip" value="10.7.0.2/32" class="vpn-input"></div></div>
      <div class="vpn-field"><label>DNS</label>
        <div class="vpn-input-wrap"><i class="ti ti-dns vpn-input-ic"></i><input id="wg-dns" value="1.1.1.1, 1.0.0.1" class="vpn-input"></div></div>
      <div class="vpn-field"><label>Keepalive (ثانیه)</label>
        <div class="vpn-input-wrap"><i class="ti ti-clock vpn-input-ic"></i><input id="wg-keepalive" type="number" value="25" class="vpn-input"></div></div>
      <div class="vpn-field"><label>MTU</label>
        <div class="vpn-input-wrap"><i class="ti ti-arrows-shuffle vpn-input-ic"></i><input id="wg-mtu" type="number" value="1280" class="vpn-input"></div></div>
    </div>

    <div style="font-size:12px;font-weight:700;margin:14px 0 10px;color:var(--t1)">۳) کلید کلاینت (اگر نداری، تولید کن)</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
      <button class="btn btn-blue" onclick="vpnGenerateClientKeys(this)"><i class="ti ti-key"></i> تولید کلید کلاینت جدید</button>
      <button class="btn btn-o" onclick="vpnShowServerScript(this)"><i class="ti ti-server"></i> اسکریپت راه‌اندازی سرور</button>
      <button class="btn btn-o" onclick="vpnShowServerKey(this)"><i class="ti ti-key"></i> تولید کلید سرور</button>
    </div>
    <div id="wg-keypair-result" style="margin-bottom:14px;display:none"></div>

    <div style="font-size:12px;font-weight:700;margin:14px 0 10px;color:var(--t1)">۴) تولید کانفیگ کلاینت</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
      <button class="btn btn-g" onclick="vpnGenerateWGConfig(this)"><i class="ti ti-file-export"></i> تولید فایل .conf</button>
      <button class="btn btn-amber" onclick="vpnGenerateWGQR(this)"><i class="ti ti-qrcode"></i> QR کد</button>
      <button class="btn btn-o" onclick="vpnTestWG(this)"><i class="ti ti-plug"></i> تست سلامت سرور</button>
    </div>
    <div id="wg-config-result" style="display:none"></div>
    <div id="wg-qr-result" style="display:none;margin-top:12px"></div>
    <div id="wg-health-result" style="display:none;margin-top:12px"></div>
  </div>

  <!-- ۳) کارت OpenVPN -->
  <div class="card vpn-card vpn-ovpn-card" style="margin-bottom:18px">
    <div class="card-title"><i class="ti ti-lock-access" style="color:var(--accent2)"></i> OpenVPN — مدیریت کانفیگ با Cert واقعی</div>

    <!-- empty-state -->
    <div id="ovpn-empty-state" class="vpn-empty-state" style="margin-bottom:14px;padding:14px 16px;background:rgba(250,204,21,0.06);border:1px dashed rgba(250,204,21,0.30);border-radius:14px;display:flex;gap:11px;align-items:flex-start">
      <i class="ti ti-file-import" style="color:var(--accent2);font-size:22px;flex-shrink:0;margin-top:2px"></i>
      <div style="flex:1;font-size:11.5px;line-height:1.8">
        <b style="color:var(--accent2)">هنوز کانفیگ OpenVPN نداری.</b><br>
        روی سرور VPS خود دستور <code dir="ltr">curl -O https://git.io/vpn -o openvpn-install.sh</code> را اجرا کن، فایل <code dir="ltr">emix-client.ovpn</code> تولید شده را اینجا paste کن، یا از <b>«اسکریپت راه‌اندازی سرور»</b> کمک بگیر.
        <div style="margin-top:8px">
          <button class="btn btn-sm btn-g" onclick="vpnShowOVPNServerScript(this)"><i class="ti ti-server"></i> گرفتن اسکریپت سرور</button>
        </div>
      </div>
    </div>

    <div style="font-size:12px;font-weight:700;margin-bottom:10px;color:var(--t1)">روش ۱ — paste کردن فایل .ovpn کامل از سرور</div>
    <div style="font-size:11px;color:var(--t3);margin-bottom:8px;line-height:1.7">
      اگر از angristan یا یک نصب‌کننده‌ی OpenVPN استفاده کردید، فایل <code dir="ltr">emix-client.ovpn</code> حاوی <code dir="ltr">&lt;ca&gt;</code> و <code dir="ltr">&lt;cert&gt;</code> و <code dir="ltr">&lt;key&gt;</code> است. آن را اینجا paste کن — پنل آن را پارس می‌کند و از اول می‌سازد.
    </div>
    <textarea id="ovpn-inline-config" placeholder="client
dev tun
proto tcp
remote vpn.example.com 1194
...
&lt;ca&gt;
-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----
&lt;/ca&gt;
&lt;cert&gt;
...
&lt;/cert&gt;
&lt;key&gt;
...
&lt;/key&gt;" class="vpn-textarea"></textarea>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;margin-bottom:18px">
      <button class="btn btn-g" onclick="vpnParseOVPNInline(this)"><i class="ti ti-file-import"></i> پارس و ذخیره</button>
      <button class="btn btn-o" onclick="vpnShowOVPNServerScript(this)"><i class="ti ti-server"></i> اسکریپت راه‌اندازی سرور</button>
    </div>

    <div style="font-size:12px;font-weight:700;margin:18px 0 10px;color:var(--t1)">روش ۲ — وارد کردن دستی مشخصات</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:12px">
      <div class="vpn-field"><label>آدرس سرور</label>
        <div class="vpn-input-wrap"><i class="ti ti-world vpn-input-ic"></i><input id="ovpn-endpoint" placeholder="vpn.example.com" class="vpn-input"></div></div>
      <div class="vpn-field"><label>پورت</label>
        <div class="vpn-input-wrap"><i class="ti ti-port vpn-input-ic"></i><input id="ovpn-port" type="number" value="1194" class="vpn-input"></div></div>
      <div class="vpn-field"><label>پروتکل</label>
        <div class="vpn-input-wrap"><i class="ti ti-bolt vpn-input-ic"></i><select id="ovpn-protocol" class="vpn-input">
          <option value="tcp" selected>TCP (سازگارتر — از CDN هم عبور می‌کند)</option>
          <option value="udp">UDP (سریع‌تر — مناسب گیمینگ)</option>
        </select></div>
      </div>
    </div>
    <div style="font-size:11px;color:var(--t3);margin-bottom:10px;line-height:1.7">
      برای OpenVPN نیازی به ساخت کلید در پنل نیست — از فایل .ovpn که سرور تولید کرده استفاده کن. بالا رو روش ۱ استفاده کن.
    </div>

    <div style="font-size:12px;font-weight:700;margin:14px 0 10px;color:var(--t1)">تولید فایل کانفیگ کلاینت</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
      <button class="btn btn-g" onclick="vpnGenerateOVPNConfig(this)"><i class="ti ti-file-export"></i> تولید فایل .ovpn</button>
      <button class="btn btn-o" onclick="vpnTestOVPN(this)"><i class="ti ti-plug"></i> تست سلامت سرور</button>
    </div>
    <div id="ovpn-config-result" style="display:none"></div>
    <div id="ovpn-health-result" style="display:none;margin-top:12px"></div>
  </div>

  <!-- ۴) راهنمای راه‌اندازی سریع -->
  <div class="card" style="margin-bottom:18px;background:linear-gradient(155deg,rgba(52,211,153,0.06) 0%,var(--card) 60%)">
    <div class="card-title"><i class="ti ti-bulb" style="color:#4ADE80"></i> راهنمای سریع — از کجا شروع کنم؟</div>
    <div style="font-size:12px;color:var(--t2);line-height:2.1">
      <b>۱)</b> یک VPS رایگان Oracle Cloud (Dubai یا Amsterdam، Always Free) بگیرید — <a href="https://cloud.oracle.com" target="_blank" style="color:var(--accent);text-decoration:underline">cloud.oracle.com</a>
      <br><b>۲)</b> Ubuntu 22.04 نصب کنید و با SSH وارد شوید
      <br><b>۳ — برای WireGuard:</b> در پنل بالا، روی «اسکریپت راه‌اندازی سرور» بزنید — اسکریپت آماده را کپی کنید، در VPS اجرا کنید (<code dir="ltr">bash emix-wg-server-setup.sh</code>). کلید عمومی سرور را برگردانید و در فیلد بالا وارد کنید.
      <br><b>۳ — برای OpenVPN:</b> روی «اسکریپت راه‌اندازی سرور» در بخش OpenVPN بزنید، در VPS اجرا کنید. فایل <code dir="ltr">/root/emix-client.ovpn</code> را کپی کنید و در textarea بالا paste کنید.
      <br><b>۴)</b> پورت UDP 51820 (WG) یا TCP 1194 (OVPN) را در فایروال سرور و Oracle Security List باز کنید.
      <br><b>۵)</b> دکمه «تولید فایل .conf/.ovpn» را بزنید — فایل را در کلاینت WireGuard یا OpenVPN وارد کنید.
    </div>
  </div>
</section>

<section class="pg" id="pg-subgroups">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-folders"></i> گروه‌های ساب</div><div class="tb-sub">هر گروه یک صفحه پابلیک مجزا با کانفیگ‌های خودش دارد</div></div>
    <div class="tb-right">
      <span class="badge bg-purple" id="subs-pg-cnt">۰ گروه</span>
      <button class="btn btn-pur" onclick="openCreateSubModal()"><i class="ti ti-folder-plus"></i> گروه جدید</button>
    </div>
  </div>
  <div class="subs-toolbar">
    <div class="subs-search">
      <i class="ti ti-search"></i>
      <input type="text" id="subs-search-inp" placeholder="جستجو در گروه‌ها..." oninput="filterSubs(this.value)">
    </div>
  </div>
  <div class="sub-grid" id="subs-grid">
    <div class="subs-empty-v2"><div class="subs-empty-v2-icon"><i class="ti ti-folders"></i></div><div class="subs-empty-v2-title">هنوز گروهی وجود ندارد</div><div class="subs-empty-v2-sub">یک گروه جدید بسازید تا کانفیگ‌ها را دسته‌بندی کنید</div></div>
  </div>
</section>
<section class="pg" id="pg-subscriptions">
  <div class="topbar"><div><div class="tb-title"><i class="ti ti-rss"></i> سابسکریپشن</div><div class="tb-sub">لینک‌های اشتراک برای اپ‌های v2ray</div></div></div>
  <div class="g2">
    <div class="card">
      <div class="card-title"><i class="ti ti-rss"></i> سابسکریپشن تکی (هر کانفیگ)</div>
      <p style="font-size:11.5px;color:var(--t3);line-height:1.8;margin-bottom:12px">هر کانفیگ URL سابسکریپشن مخصوص دارد. از کارت کانفیگ روی آیکون <i class="ti ti-rss"></i> کلیک کنید.</p>
    </div>
    <div class="card">
      <div class="card-title"><i class="ti ti-database"></i> سابسکریپشن کامل (ادمین)</div>
      <p style="font-size:11.5px;color:var(--t3);line-height:1.8;margin-bottom:4px">شامل تمام کانفیگ‌های فعال.</p>
      <div class="sub-box"><span class="sub-url" id="sub-all-url">در حال دریافت...</span><div style="display:flex;gap:6px"><button class="btn btn-sm btn-g" onclick="cpSubAll()"><i class="ti ti-copy"></i></button><button class="btn btn-sm btn-g" onclick="window.open(location.protocol+'//'+location.host+'/sub-all')"><i class="ti ti-external-link"></i></button></div></div>
      <div class="cl amber" style="margin-top:11px"><i class="ti ti-alert-triangle"></i><span>این آدرس فقط در مرورگری که به پنل وارد شده کار می‌کند (نیاز به کوکی سشن).</span></div>
    </div>
  </div>
  <div class="card">
    <div class="card-title"><i class="ti ti-folders"></i> لینک سابسکریپشن گروه‌ها</div>
    <div id="sub-groups-list">در حال بارگذاری...</div>
  </div>
</section>
<section class="pg" id="pg-traffic">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-chart-area"></i> ترافیک</div><div class="tb-sub">تحلیل و مانیتورینگ مصرف پهنای باند</div></div>
    <div class="tb-right"><button class="btn btn-p btn-sm" onclick="refreshAll()"><i class="ti ti-refresh"></i> رفرش</button></div>
  </div>

  <div class="traf-hero">
    <div class="traf-main-stat">
      <div class="traf-main-label"><i class="ti ti-database"></i> کل ترافیک مصرفی</div>
      <div class="traf-main-val" id="t-traffic">—<span>MB</span></div>
      <div class="traf-trend up" id="t-trend"><i class="ti ti-trending-up"></i> <span id="t-trend-val">—</span></div>
    </div>
    <div class="traf-mini">
      <div class="traf-mini-top"><div class="traf-mini-icon"><i class="ti ti-arrow-up-right"></i></div><span class="traf-mini-label">میانگین ساعتی</span></div>
      <div><div class="traf-mini-val" id="t-avg">—</div><div class="traf-mini-sub">MB در ساعت</div></div>
    </div>
    <div class="traf-mini">
      <div class="traf-mini-top"><div class="traf-mini-icon pk"><i class="ti ti-chart-bar"></i></div><span class="traf-mini-label">پیک مصرف</span></div>
      <div><div class="traf-mini-val" id="t-peak">—</div><div class="traf-mini-sub" id="t-peak-time">بالاترین ساعت</div></div>
    </div>
    <div class="traf-mini">
      <div class="traf-mini-top"><div class="traf-mini-icon lo"><i class="ti ti-clock-hour-4"></i></div><span class="traf-mini-label">کمترین مصرف</span></div>
      <div><div class="traf-mini-val" id="t-low">—</div><div class="traf-mini-sub">MB در ساعت</div></div>
    </div>
  </div>

  <div class="traf-chart-card">
    <div class="traf-chart-head">
      <div>
        <div class="traf-chart-title"><i class="ti ti-activity"></i> روند مصرف ترافیک</div>
        <div class="traf-chart-sub">بر اساس مگابایت در هر ساعت</div>
      </div>
      <div class="traf-legend">
        <div class="traf-legend-item"><span class="traf-legend-dot" style="background:var(--accent)"></span> مصرف</div>
        <div class="traf-legend-item"><span class="traf-legend-dot" style="background:var(--amber)"></span> میانگین</div>
      </div>
    </div>
    <div class="traf-chart-body"><canvas id="ch3"></canvas></div>
  </div>
</section>
<section class="pg" id="pg-connections">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-plug-connected"></i> اتصالات فعال</div><div class="tb-sub">مانیتورینگ زنده‌ی آی‌پی و ترافیک هر اتصال</div></div>
    <div class="tb-right"><span class="badge bg-green" id="conns-live">—</span><button class="btn btn-p btn-sm" onclick="refreshAll()"><i class="ti ti-refresh"></i> رفرش</button></div>
  </div>

  <div class="conn-hero">
    <div class="conn-hero-tile">
      <div class="conn-hero-icon"><i class="ti ti-plug-connected"></i></div>
      <div class="conn-hero-label">اتصالات زنده</div>
      <div class="conn-hero-val" id="ch-count">—</div>
    </div>
    <div class="conn-hero-tile">
      <div class="conn-hero-icon"><i class="ti ti-transfer"></i></div>
      <div class="conn-hero-label">مجموع ترافیک لحظه‌ای</div>
      <div class="conn-hero-val" id="ch-traffic">—</div>
    </div>
    <div class="conn-hero-tile">
      <div class="conn-hero-icon"><i class="ti ti-clock"></i></div>
      <div class="conn-hero-label">میانگین مدت اتصال</div>
      <div class="conn-hero-val" id="ch-avgdur">—</div>
    </div>
    <div class="conn-hero-tile">
      <div class="conn-hero-icon"><i class="ti ti-map-pin"></i></div>
      <div class="conn-hero-label">آی‌پی‌های یکتا</div>
      <div class="conn-hero-val" id="ch-uniq">—</div>
    </div>
  </div>

  <div class="conn-toolbar">
    <div class="conn-toolbar-title"><i class="ti ti-list-details"></i> لیست اتصالات</div>
    <div class="conn-live-badge"><span class="conn-live-dot"></span> بروزرسانی خودکار هر ۵ ثانیه</div>
  </div>

  <div class="conn-grid-v2" id="conns-grid"></div>
  <div class="conn-empty-v2" id="conns-empty" style="display:none">
    <div class="conn-empty-v2-icon"><i class="ti ti-plug-off"></i></div>
    <div class="conn-empty-v2-title">هیچ اتصال فعالی نیست</div>
    <div class="conn-empty-v2-sub">به محض اتصال کلاینت‌ها، اینجا نمایش داده می‌شوند</div>
  </div>
</section>
<section class="pg" id="pg-nodes">
  <div class="node-hero">
    <div class="node-hero-net">
      <svg viewBox="0 0 600 90" preserveAspectRatio="none">
        <path class="nh-line" d="M20,70 C140,10 220,80 340,25 S520,60 580,15"></path>
        <path class="nh-line" d="M60,20 C160,75 260,15 380,60 S500,20 560,55" style="animation-duration:9s"></path>
        <circle class="nh-dot" cx="20" cy="70" r="2.6"></circle>
        <circle class="nh-dot" cx="340" cy="25" r="2.6"></circle>
        <circle class="nh-dot" cx="580" cy="15" r="2.6"></circle>
        <circle class="nh-dot" cx="60" cy="20" r="2.2"></circle>
        <circle class="nh-dot" cx="380" cy="60" r="2.2"></circle>
        <circle class="nh-dot" cx="560" cy="55" r="2.2"></circle>
      </svg>
    </div>
    <div class="node-hero-top">
      <div class="node-hero-title">
        <div class="node-hero-icon"><i class="ti ti-topology-star-3"></i></div>
        <div>
          <div class="tb-title">نود</div>
          <div class="tb-sub">چند پنل EMIX را به هم متصل کنید تا کانفیگ‌ها و مصرف‌شان یکی شود</div>
        </div>
      </div>
      <div class="tb-right">
        <span class="badge bg-blue" id="nodes-pg-cnt">۰ نود</span>
        <button class="btn btn-p btn-sm" onclick="openNodeKeyModal()"><i class="ti ti-key"></i> ساخت کلید</button>
        <button class="btn btn-g btn-sm" onclick="openNodeConnectModal()"><i class="ti ti-plug-connected"></i> متصل کردن</button>
        <button class="btn btn-o btn-sm" onclick="loadNodes(true)"><i class="ti ti-refresh"></i> رفرش</button>
      </div>
    </div>
    <div class="node-hero-metrics">
      <div class="node-metric"><div class="node-metric-top"><i class="ti ti-transfer"></i><span class="node-metric-label">مصرف ترکیبی</span></div><div class="node-metric-val" id="na-used">—</div><div class="node-metric-sub" id="na-used-sub">این پنل + نودها</div></div>
      <div class="node-metric"><div class="node-metric-top"><i class="ti ti-link"></i><span class="node-metric-label">کانفیگ ترکیبی</span></div><div class="node-metric-val" id="na-links">—</div><div class="node-metric-sub" id="na-links-sub">از کل</div></div>
      <div class="node-metric"><div class="node-metric-top"><i class="ti ti-folders"></i><span class="node-metric-label">ساب‌ ترکیبی</span></div><div class="node-metric-val" id="na-subs">—</div><div class="node-metric-sub" id="na-subs-sub">این پنل + نودها</div></div>
      <div class="node-metric"><div class="node-metric-top"><i class="ti ti-arrows-exchange"></i><span class="node-metric-label">درخواست ترکیبی</span></div><div class="node-metric-val" id="na-reqs">—</div><div class="node-metric-sub" id="na-reqs-sub">این پنل + نودها</div></div>
    </div>
  </div>

  <div class="node-keys-card">
    <div class="card">
      <div class="card-title"><i class="ti ti-key"></i> کلیدهای صادرشده <span class="ml-auto badge bg-blue" id="nk-cnt">۰</span></div>
      <div id="nk-list">—</div>
      <div class="cl amber"><i class="ti ti-alert-triangle"></i><span>دسترسی هر کلید همان چیزی است که هنگام ساخت برایش تیک زده‌اید. کلید را فقط به پنل مورد اعتماد خودتان بدهید و در صورت شک، غیرفعالش کنید یا برای همیشه حذفش کنید.</span></div>
    </div>
  </div>

  <div class="conn-toolbar">
    <div class="conn-toolbar-title"><i class="ti ti-topology-ring"></i> نودهای متصل</div>
    <div class="conn-live-badge"><span class="conn-live-dot"></span> <span id="nodes-online-txt">—</span></div>
  </div>
  <div class="nodes-grid" id="nodes-grid"></div>
  <div class="conn-empty-v2" id="nodes-empty" style="display:none">
    <div class="node-empty-illust">
      <svg viewBox="0 0 100 100">
        <path class="ne-line" d="M22,78 L50,30"></path>
        <path class="ne-line" d="M78,78 L50,30" style="animation-duration:4s"></path>
        <path class="ne-line" d="M22,78 L78,78" style="animation-duration:6s"></path>
        <circle class="ne-dot mid" cx="50" cy="30" r="6"></circle>
        <circle class="ne-dot" cx="22" cy="78" r="5"></circle>
        <circle class="ne-dot" cx="78" cy="78" r="5"></circle>
      </svg>
    </div>
    <div class="conn-empty-v2-title">هنوز به نودی متصل نیستید</div>
    <div class="conn-empty-v2-sub">در پنل دیگر «ساخت کلید» را بزنید، کلید را کپی کنید و اینجا با «متصل کردن» وارد کنید</div>
  </div>
</section>
<section class="pg" id="pg-logs">

  <div class="topbar"><div><div class="tb-title"><i class="ti ti-history"></i> لاگ فعالیت‌ها</div><div class="tb-sub">تاریخچه‌ی کامل رخدادهای پنل</div></div><div class="tb-right"><button class="btn btn-p btn-sm" onclick="loadActivity()"><i class="ti ti-refresh"></i></button></div></div>
  <div class="card"><div class="log-timeline" id="logs-list">—</div><div class="empty" id="logs-empty" style="display:none"><i class="ti ti-history-toggle"></i><p>هنوز لاگی ثبت نشده</p></div></div>
</section>
<section class="pg" id="pg-errors">
  <div class="topbar"><div><div class="tb-title"><i class="ti ti-alert-triangle"></i> خطاها</div></div><div class="tb-right"><span class="badge bg-red" id="errs-badge">۰</span><button class="btn btn-p btn-sm" onclick="refreshAll()"><i class="ti ti-refresh"></i></button></div></div>
  <div class="card"><div class="card-title"><i class="ti ti-bug"></i> لاگ خطاها</div><div id="errs-full">—</div></div>
</section>

<section class="pg" id="pg-diag">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-activity-heartbeat"></i> سلامت و تشخیص (Diagnostics Center)</div>
      <div class="tb-sub">موتور سلامت شبکه + سیستم جاب‌ها + خطاهای ساختاریافته — همه بر پایه‌ی تست واقعی، بدون عدد ساختگی</div></div>
    <div class="tb-right"><button class="btn btn-p btn-sm" onclick="loadDiagPage()"><i class="ti ti-refresh"></i> بازخوانی</button>
      <button class="btn btn-sm" onclick="diagProbeAll()"><i class="ti ti-bolt"></i> تست همه‌ی کانفیگ‌ها</button></div>
  </div>

  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:12px" id="diag-health-cards">—</div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px" class="diag-grid">
    <div class="card">
      <div class="card-title"><i class="ti ti-heart-rate-monitor"></i> وضعیت سلامت کانفیگ‌ها (تست واقعی End-to-End)</div>
      <div id="diag-health-body">—</div>
    </div>
    <div class="card">
      <div class="card-title"><i class="ti ti-list-check"></i> جاب‌های پس‌زمینه</div>
      <div id="diag-jobs-body">—</div>
    </div>
    <div class="card">
      <div class="card-title"><i class="ti ti-server-2"></i> زیرساخت (App / Persistence / Protocols)</div>
      <div id="diag-sys-body">—</div>
    </div>
    <div class="card">
      <div class="card-title"><i class="ti ti-shield-check"></i> کیفیت IP</div>
      <div id="diag-ipq-body">—</div>
    </div>
  </div>

  <div class="card" style="margin-top:12px">
    <div class="card-title"><i class="ti ti-bug"></i> خطاهای ساختاریافته اخیر (کد / کامپوننت / شدت)</div>
    <div id="diag-err-body">—</div>
  </div>
</section>

<style>
.diag-grid{grid-template-columns:1fr 1fr}
@media(max-width:900px){.diag-grid{grid-template-columns:1fr}}
.diag-hc{background:var(--card);border:1px solid var(--card-b);border-radius:14px;padding:14px;text-align:center}
.diag-hc .n{font-size:26px;font-weight:800;margin-bottom:2px}
.diag-hc .l{font-size:10.5px;color:var(--t3);letter-spacing:.08em}
.diag-st-HEALTHY{color:#10B981}.diag-st-DEGRADED{color:#F59E0B}.diag-st-UNREACHABLE{color:#EF4444}.diag-st-INVALID{color:#6B7280}.diag-st-UNKNOWN{color:#8B5CF6}
.diag-tb{width:100%;border-collapse:collapse;font-size:12px}
.diag-tb th{text-align:right;color:var(--t3);font-size:10.5px;padding:6px 8px;border-bottom:1px solid var(--card-b);white-space:nowrap}
.diag-tb td{padding:7px 8px;border-bottom:1px solid rgba(255,255,255,.04);white-space:nowrap}
.diag-pill{display:inline-block;padding:2px 9px;border-radius:20px;font-size:10px;font-weight:700}
</style>

<script>
async function loadDiagPage(){
  try{
    // Audit fix (CRITICAL): این خط در v11.0.0-arch با خطای syntax واقعی
    // (const s, dg, js, iq] — بدون bracket باز) کل script block را
    // می‌کشت و Diagnostics Center در production هرگز لود نمی‌شد.
    // + fetch خام → authF تا انقضای session به login redirect شود.
    const [hs, dg, js, iq] = await Promise.all([
      authF('/api/health/summary').then(r=>r.ok?r.json():null).catch(()=>null),
      authF('/api/diagnostics').then(r=>r.ok?r.json():null).catch(()=>null),
      authF('/api/jobs/status').then(r=>r.ok?r.json():null).catch(()=>null),
      authF('/api/ip-quality/summary').then(r=>r.ok?r.json():null).catch(()=>null),
    ]);
    // health state cards
    const hc = document.getElementById('diag-health-cards');
    if(hs){
      const states = [['HEALTHY','سالم','ti-circle-check'],['DEGRADED','ضعیف','ti-alert-triangle'],['UNREACHABLE','در دسترس نیست','ti-plug-x'],['INVALID','نامعتبر','ti-ban'],['UNKNOWN','تست نشده','ti-help']];
      hc.innerHTML = states.map(([k,fa])=>`<div class="diag-hc"><div class="n diag-st-${k}">${hs.by_state?.[k]??0}</div><div class="l">${fa}</div></div>`).join('')
      + `<div class="diag-hc"><div class="n">${hs.tracked??0}</div><div class="l">در مجموع</div></div>`;
    } else { hc.textContent='موتور سلامت در دسترس نیست'; }
    // health details + formula
    const hb = document.getElementById('diag-health-body');
    if(hs){
      hb.innerHTML = `<div style="font-size:11.5px;color:var(--t3);margin-bottom:8px">فرمول امتیاز: ${hs.formula||''}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        ${Object.entries(hs.by_state||{}).map(([k,v])=>`<span class="diag-pill diag-st-${k}" style="background:var(--accent-d)">${k}: ${v}</span>`).join('')}
      </div>
      <div style="margin-top:8px;font-size:11px;color:var(--t3)">هر کانفیگ با یک پروتکل‌کلاینت واقعی از مسیر عمومی تست می‌شود (WS/TLS + هدر پروتکل + خروج). کانفیگ جدید هیچ‌وقت «سالم» متولد نمی‌شود — فقط تست واقعی.</div>`;
    } else { hb.textContent='—'; }
    // jobs table
    const jb = document.getElementById('diag-jobs-body');
    if(js && js.jobs){
      jb.innerHTML = `<div style="margin-bottom:6px;font-size:11px;color:var(--t3)">Supervisor: <b>${js.supervisor}</b>${js.uptime_s!=null?' · '+Math.round(js.uptime_s)+'s':''}</div>
      <div style="overflow-x:auto"><table class="diag-tb"><tr><th>جاب</th><th>وضعیت</th><th>اجرا</th><th>خطا</th><th>آخرین اجرا</th><th>ms</th></tr>
      ${js.jobs.map(j=>`<tr><td>${j.name}</td><td class="diag-st-${j.last_status==='OK'?'HEALTHY':j.last_status==='FAILED'?'UNREACHABLE':'UNKNOWN'}">${j.last_status}</td><td>${j.run_count}</td><td>${j.fail_count}</td><td>${j.last_run?new Date(j.last_run*1000).toLocaleTimeString('fa-IR'):'—'}</td><td>${j.last_duration_ms??'—'}</td></tr>`).join('')}</table></div>`;
    } else { jb.textContent='—'; }
    // system checks
    const sb = document.getElementById('diag-sys-body');
    if(dg && dg.checks){
      const rows = [];
      const push=(name,data)=>{ if(!data) return; const st=data.status||data.supervisor||'OK';
        rows.push(`<tr><td>${name}</td><td>${st}</td><td style="white-space:normal;direction:ltr;text-align:left">${(data.error||data.note||'').toString().slice(0,80)}</td></tr>`); };
      push('App',dg.checks.app); push('Persistence',dg.checks.persistence);
      push('Protocols',dg.checks.protocols?{status:'OK',note:(dg.checks.protocols.registered||0)+' registered'}:null);
      sb.innerHTML='<table class="diag-tb"><tr><th>بخش</th><th>وضعیت</th><th>توضیح</th></tr>'+rows.join('')+'</table>';
    } else { sb.textContent='—'; }
    // ip quality
    const ib = document.getElementById('diag-ipq-body');
    if(iq && iq.by_classification){
      ib.innerHTML = Object.entries(iq.by_classification).filter(([,v])=>v>0).map(([k,v])=>
        `<span class="diag-pill" style="background:var(--accent-d);color:var(--t2)">${k}: ${v}</span>`).join(' ') || '<span style="color:var(--t3);font-size:12px">هنوز IP‌ای اسکن نشده — از تب گیمینگ یا /api/ip-quality استفاده کنید</span>';
      ib.insertAdjacentHTML('beforeend','<div style="margin-top:6px;font-size:11px;color:var(--t3)">طبقه‌بندی فقط با شواهد واقعی (TLS/ASN/Reputation) — «Clean» بدون دلیل صادر نمی‌شود.</div>');
    } else { ib.textContent='—'; }
    // structured errors
    const eb = document.getElementById('diag-err-body');
    if(dg && dg.recent_errors && dg.recent_errors.length){
      eb.innerHTML='<div style="overflow-x:auto"><table class="diag-tb"><tr><th>زمان</th><th>کد</th><th>کامپوننت</th><th>شدت</th><th>پیام</th></tr>'
      + dg.recent_errors.map(e=>`<tr><td>${(e.timestamp_iso||'').slice(11,19)}</td><td style="direction:ltr">${e.code}</td><td style="direction:ltr">${e.component}</td><td>${e.severity}</td><td style="white-space:normal;direction:ltr;text-align:left;max-width:420px;overflow:hidden;text-overflow:ellipsis">${(e.message||'').slice(0,110)}</td></tr>`).join('')+'</table></div>';
    } else { eb.innerHTML='<span style="color:var(--t3)">خطای ساختاریافته‌ای ثبت نشده</span>'; }
  }catch(e){ console.error('diag load failed', e); }
}
async function diagProbeAll(){
  try{
    const r = await authF('/api/exp/route/configs/probe-all',{method:'POST'});
    const j = await r.json();
    if(j.ok!==false){ loadDiagPage(); }
  }catch(e){ console.error(e); }
}
</script>
<section class="pg" id="pg-updates">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-cloud-download"></i> نسخه و بروزرسانی</div><div class="tb-sub">مدیریت نسخه‌ی پنل و تاریخچه‌ی کامل بروزرسانی‌ها</div></div>
    <div class="tb-right"><button class="btn btn-p btn-sm" onclick="loadVersion()"><i class="ti ti-refresh"></i> بررسی مجدد</button></div>
  </div>

  <div class="upd-hero" id="upd-hero">
    <div class="upd-hero-glow"></div>
    <div class="upd-hero-top">
      <div class="upd-hero-cur">
        <div class="upd-hero-icon"><i class="ti ti-package"></i></div>
        <div>
          <div class="upd-hero-label">نسخه‌ی نصب‌شده</div>
          <div class="upd-hero-ver" id="ver-current">—</div>
        </div>
      </div>
      <div class="upd-hero-status" id="ver-status-badge">
        <span class="upd-pill upd-pill-blue"><span class="upd-dot"></span> در حال بررسی...</span>
      </div>
    </div>
    <div class="upd-hero-desc" id="ver-current-desc">—</div>
    <div class="upd-hero-meta">
      <span class="upd-meta-chip"><i class="ti ti-brand-github"></i> <span id="ver-repo">—</span></span>
      <span class="upd-meta-chip"><i class="ti ti-git-branch"></i> <span id="ver-branch">—</span></span>
    </div>
  </div>

  <div class="upd-latest-card" id="upd-latest-card" style="display:none">
    <div class="upd-latest-left">
      <div class="upd-latest-icon"><i class="ti ti-sparkles"></i></div>
      <div>
        <div class="upd-latest-title">نسخه‌ی جدید موجود است</div>
        <div class="upd-latest-ver">نسخه‌ی <span id="ver-latest-num">—</span></div>
        <div class="upd-latest-desc" id="ver-latest-desc">—</div>
      </div>
    </div>
    <button class="upd-install-btn" id="update-btn" onclick="startUpdate()">
      <i class="ti ti-download"></i> نصب بروزرسانی
    </button>
  </div>

  <div class="upd-progress-card" id="update-progress-wrap" style="display:none">
    <div class="upd-progress-head">
      <div class="upd-progress-icon"><i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i></div>
      <div style="flex:1">
        <div class="upd-progress-title">در حال نصب بروزرسانی...</div>
        <div class="upd-progress-txt" id="update-progress-txt">در حال آماده‌سازی...</div>
      </div>
      <div class="upd-progress-pct" id="update-progress-pct">0%</div>
    </div>
    <div class="upd-progress-track"><div class="upd-progress-fill" id="update-progress-bar" style="width:0%"></div></div>
  </div>

  <div class="upd-log-card">
    <div class="upd-log-head">
      <div class="upd-log-title"><i class="ti ti-terminal-2"></i> لاگ زنده‌ی نصب</div>
      <button class="btn btn-o btn-sm" onclick="loadUpdateLog()"><i class="ti ti-refresh"></i> بروزرسانی لاگ</button>
    </div>
    <div class="upd-log-box" id="update-log-box">
      <p class="upd-log-empty">لاگی موجود نیست</p>
    </div>
  </div>

  <div class="upd-history-head">
    <div class="upd-history-title"><i class="ti ti-history"></i> تاریخچه‌ی بروزرسانی‌ها</div>
    <span class="badge bg-blue" id="upd-history-count">۰ مورد</span>
  </div>
  <div class="upd-timeline" id="upd-history-list">
    <div class="upd-history-empty"><i class="ti ti-history-toggle"></i><p>هنوز هیچ بروزرسانی‌ای ثبت نشده</p></div>
  </div>
</section>
<section class="pg" id="pg-support">
  <div class="sup-wrap">
    <div class="sup-head">
      <div class="sup-head-icon"><i class="ti ti-headset"></i></div>
      <div class="sup-head-text">
        <div class="sup-head-title">پشتیبانی EMIX</div>
        <div class="sup-head-sub"><span class="sdot"></span> معمولاً در کمتر از چند ساعت پاسخ داده می‌شود</div>
      </div>
    </div>
    <div id="sup-blocked-banner" class="sup-blocked-banner" style="display:none">
      <i class="ti ti-lock"></i> دسترسی شما به ارسال پیام توسط پشتیبانی محدود شده است.
    </div>
    <div id="support-msgs"></div>
    <div class="sup-input-row" id="sup-input-row">
      <input class="fi" id="support-inp" placeholder="پیام خود را بنویسید..." style="flex:1" onkeydown="if(event.key==='Enter')sendSupportMsg()">
      <button class="btn btn-p" onclick="sendSupportMsg()"><i class="ti ti-send-2"></i></button>
    </div>
  </div>
</section>
<section class="pg" id="pg-backup">
  <div class="topbar">
    <div><div class="tb-title"><i class="ti ti-database-export"></i> بکاپ‌گیری و بازیابی</div><div class="tb-sub">دانلود کامل اطلاعات پنل یا بازگردانی از یک فایل بکاپ قبلی</div></div>
  </div>
  <div class="g2">
    <div class="card">
      <div class="card-title"><i class="ti ti-download"></i> دانلود بکاپ</div>
      <p style="font-size:11.5px;color:var(--t3);line-height:1.9;margin-bottom:14px">
        یک فایل JSON شامل تمام کانفیگ‌ها، گروه‌های ساب و رمز عبور (هش‌شده) دانلود می‌شود. این فایل را جایی امن نگه دارید.
      </p>
      <button class="btn btn-p" onclick="downloadBackup()"><i class="ti ti-cloud-download"></i> دانلود فایل بکاپ</button>
      <div class="cl" style="margin-top:14px"><i class="ti ti-info-circle"></i><span>این فایل شامل سکرت‌های پروکسی تلگرام هم هست؛ آن را در اختیار افراد غیرقابل‌اعتماد قرار ندهید.</span></div>
    </div>
    <div class="card">
      <div class="card-title"><i class="ti ti-upload"></i> بازیابی از بکاپ</div>
      <p style="font-size:11.5px;color:var(--t3);line-height:1.9;margin-bottom:14px">
        فایل بکاپی که قبلاً دانلود کرده‌اید را انتخاب کنید تا تمام کانفیگ‌ها و گروه‌ها روی این پنل بازیابی شوند (مثلاً بعد از نصب یک پنل جدید).
      </p>
      <div class="fg" style="margin-bottom:12px">
        <label>فایل بکاپ (JSON)</label>
        <input type="file" id="restore-file" accept="application/json,.json" class="fi" style="width:100%;padding:9px 12px">
      </div>
      <div class="sr" style="border:none;padding:0 0 12px">
        <span class="sr-k"><i class="ti ti-key"></i> رمز عبور فایل بکاپ هم بازگردانی شود؟</span>
        <button class="tog" id="restore-pw-tog" onclick="this.classList.toggle('on')"></button>
      </div>
      <button class="btn btn-d" onclick="restoreBackup()" id="restore-btn"><i class="ti ti-database-import"></i> شروع بازیابی</button>
      <div class="cl amber" style="margin-top:14px"><i class="ti ti-alert-triangle"></i><span>بازیابی، تمام کانفیگ‌ها و گروه‌های فعلی پنل را با اطلاعات فایل بکاپ جایگزین می‌کند و این کار غیرقابل بازگشت است.</span></div>
    </div>
  </div>
</section>
<section class="pg" id="pg-settings">
  <div class="topbar"><div><div class="tb-title"><i class="ti ti-settings"></i> تنظیمات</div></div></div>
  <div class="g2">
    <div class="srv-panel">
      <div class="srv-hero">
        <div class="srv-hero-icon"><i class="ti ti-server-2"></i></div>
        <div class="srv-hero-text">
          <div class="srv-hero-domain" id="set-host">—</div>
          <div class="srv-hero-sub"><span class="dot dg pulse"></span> آنلاین · Railway</div>
        </div>
      </div>
      <div class="srv-tiles">
        <div class="srv-tile"><div class="srv-tile-icon"><i class="ti ti-route"></i></div><div class="srv-tile-text"><div class="srv-tile-label">پورت</div><div class="srv-tile-val">443 (TLS)</div></div></div>
        <div class="srv-tile"><div class="srv-tile-icon"><i class="ti ti-versions"></i></div><div class="srv-tile-text"><div class="srv-tile-label">نسخه</div><div class="srv-tile-val" id="srv-version-val">v9.7.0</div></div></div>
        <div class="srv-tile"><div class="srv-tile-icon"><i class="ti ti-brand-fastapi"></i></div><div class="srv-tile-text"><div class="srv-tile-label">فریم‌ورک</div><div class="srv-tile-val">FastAPI + Uvicorn</div></div></div>
        <div class="srv-tile"><div class="srv-tile-icon"><i class="ti ti-cloud"></i></div><div class="srv-tile-text"><div class="srv-tile-label">پلتفرم</div><div class="srv-tile-val">Railway</div></div></div>
        <div class="srv-tile" style="grid-column:1/-1"><div class="srv-tile-icon"><i class="ti ti-device-floppy"></i></div><div class="srv-tile-text"><div class="srv-tile-label">ذخیره‌سازی</div><div class="srv-tile-val">JSON File (/data)</div></div></div>
      </div>
      <div class="sr" style="border:none;padding:14px 0 0;margin-top:6px;border-top:1px solid var(--bd)">
        <span class="sr-k"><i class="ti ti-bolt-off"></i> توقف کامل لاگ‌گیری (برای بیشترین سرعت ممکن)</span>
        <button class="tog" id="disable-logging-tog" onclick="toggleLoggingSetting()"></button>
      </div>
      <div class="cl" style="margin-top:8px"><i class="ti ti-info-circle"></i><span>با فعال‌کردن این گزینه، هیچ لاگ و خطایی (نه در فایل، نه در پنل) ثبت نمی‌شود؛ فقط برای زمانی که همه‌چیز پایدار است و سرعت اولویت دارد روشنش کنید.</span></div>
    </div>
    <div class="pw-panel">
      <div class="pw-hero">
        <div class="pw-hero-icon"><i class="ti ti-key"></i></div>
        <div class="pw-hero-text">
          <div class="pw-hero-title">تغییر رمز عبور</div>
          <div class="pw-hero-sub">رمز قوی انتخاب کنید و آن را جایی امن نگه دارید</div>
        </div>
      </div>
      <div class="pw-body">
        <div class="pw-field">
          <label>رمز فعلی</label>
          <input class="pw-input" type="password" id="cp-cur" placeholder="رمز فعلی را وارد کنید">
          <button class="pw-eye" type="button" onclick="togglePwField('cp-cur',this)"><i class="ti ti-eye"></i></button>
        </div>
        <div class="pw-field" style="margin-bottom:6px">
          <label>رمز جدید</label>
          <input class="pw-input" type="password" id="cp-new" placeholder="حداقل ۴ کاراکتر" oninput="checkPwStrength(this.value)">
          <button class="pw-eye" type="button" onclick="togglePwField('cp-new',this)"><i class="ti ti-eye"></i></button>
        </div>
        <div class="pw-strength" id="pw-strength-bar">
          <div class="pw-strength-seg"></div><div class="pw-strength-seg"></div><div class="pw-strength-seg"></div><div class="pw-strength-seg"></div>
        </div>
        <div class="pw-strength-label" id="pw-strength-label"><i class="ti ti-shield"></i> قدرت رمز</div>
        <div class="pw-reqs">
          <span class="pw-req" id="req-len"><i class="ti ti-circle-dashed"></i> حداقل ۴ کاراکتر</span>
          <span class="pw-req" id="req-num"><i class="ti ti-circle-dashed"></i> شامل عدد</span>
          <span class="pw-req" id="req-case"><i class="ti ti-circle-dashed"></i> حروف بزرگ/کوچک</span>
        </div>
        <div class="pw-field" style="margin-bottom:18px">
          <label>تکرار رمز جدید</label>
          <input class="pw-input" type="password" id="cp-cf" placeholder="تکرار رمز جدید">
          <button class="pw-eye" type="button" onclick="togglePwField('cp-cf',this)"><i class="ti ti-eye"></i></button>
        </div>
        <button class="pw-submit" onclick="changePw()"><i class="ti ti-shield-check"></i> ذخیره رمز جدید</button>
      </div>
    </div>
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════════════════════
     بخش آزمایشی (Experimental Section) — تمام فیچرهای جدید در اینجا قرار دارند
     حالت: AUTO-ENABLED — بعد از هر deploy خودکار فعال است.
     برای غیرفعال‌کردن: EMIX_EXPERIMENTAL=0 یا EMIX_ENABLE_<FEATURE>=0
     ════════════════════════════════════════════════════════════════════════════ -->
<section class="pg" id="pg-experimental">
  <div class="page-hdr" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:12px">
    <div style="min-width:0;flex:1">
      <h1 style="font-size:24px;font-weight:800;color:#8B5CF6;display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <i class="ti ti-flask" style="font-size:28px"></i> بخش آزمایشی (Experimental)
      </h1>
      <p style="color:var(--t3);font-size:13px;margin-top:4px">تمام فیچرهای جدید — auto-enabled بعد از deploy. برای غیرفعال‌کردن: <code style="background:rgba(0,0,0,.3);padding:2px 6px;border-radius:4px;color:#8B5CF6">EMIX_EXPERIMENTAL=0</code> یا <code style="background:rgba(0,0,0,.3);padding:2px 6px;border-radius:4px;color:#8B5CF6">EMIX_ENABLE_&lt;FEATURE&gt;=0</code></p>
    </div>
    <div id="exp-status-badge" style="padding:8px 16px;border-radius:12px;background:rgba(139,92,246,.1);border:1px solid rgba(139,92,246,.3);font-weight:700;font-size:13px;color:#8B5CF6;flex-shrink:0">Loading...</div>
  </div>

  <!-- Info Banner (auto-enabled) -->
  <div id="exp-warning" style="padding:14px 18px;background:linear-gradient(135deg,rgba(16,185,129,.08),rgba(139,92,246,.08));border:1px solid rgba(16,185,129,.3);border-radius:14px;margin-bottom:20px;display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap">
    <i class="ti ti-circle-check" style="font-size:22px;color:#10B981;flex-shrink:0"></i>
    <div style="flex:1;min-width:200px">
      <div style="font-weight:700;color:#10B981;margin-bottom:4px">بخش آزمایشی خودکار فعال است</div>
      <div style="font-size:12px;color:var(--t2);line-height:1.6">
        بعد از هر redeploy در Railway، کل بخش آزمایشی و همه‌ی فیچرها (به جز مواردی که به setup اضافی نیاز دارند) خودکار فعال می‌شوند.<br>
        استثناها (که باید صریحاً فعال شوند):
        <code style="background:rgba(0,0,0,.3);padding:2px 6px;border-radius:4px;color:#FACC15">ip_whitelist</code>
        (نیاز به <code style="background:rgba(0,0,0,.3);padding:2px 6px;border-radius:4px;color:#FACC15">EMIX_ADMIN_IPS</code>)،
        <code style="background:rgba(0,0,0,.3);padding:2px 6px;border-radius:4px;color:#FACC15">totp_2fa</code>
        (نیاز به <code style="background:rgba(0,0,0,.3);padding:2px 6px;border-radius:4px;color:#FACC15">EMIX_TOTP_SECRET</code>)،
        <code style="background:rgba(0,0,0,.3);padding:2px 6px;border-radius:4px;color:#FACC15">telegram_bot</code>
        (نیاز به <code style="background:rgba(0,0,0,.3);padding:2px 6px;border-radius:4px;color:#FACC15">EMIX_BOT_TOKEN</code>).
      </div>
    </div>
  </div>

  <!-- Features Grid -->
  <div id="exp-features-grid" class="exp-features-grid">
    <div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--t3)">
      <i class="ti ti-loader-2" style="font-size:32px;animation:spin 1s linear infinite"></i>
      <div style="margin-top:8px;font-size:13px">در حال بارگذاری...</div>
    </div>
  </div>

  <!-- Sub-sections -->
  <div class="exp-subsections">
    <div class="card exp-sub-card" style="padding:20px">
      <h3 style="font-size:16px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        <i class="ti ti-bolt" style="color:#8B5CF6"></i> ابزارهای ویرایش لینک
      </h3>
      <p style="font-size:12px;color:var(--t3);margin-bottom:14px;line-height:1.6">
        این ابزارها روی لینک‌های موجود (VLESS/Trojan) اعمال می‌شوند و واقعاً کار می‌کنند.
        لینک موجود خود را کپی کنید و در اینجا پردازش کنید.
      </p>
      <div style="display:flex;flex-direction:column;gap:8px">
        <button class="btn btn-o exp-action-btn" onclick="expEmitLink('finalmask')" style="text-align:right"><i class="ti ti-mask"></i> FinalMask (TLS fragmentation)</button>
        <button class="btn btn-o exp-action-btn" onclick="expEmitLink('utls')" style="text-align:right"><i class="ti ti-fingerprint"></i> uTLS fingerprint</button>
      </div>
      <div style="margin-top:12px;padding:10px 12px;border-radius:10px;background:rgba(250,204,21,.06);border:1px solid rgba(250,204,21,.2)">
        <div style="font-size:11px;color:#FACC15;line-height:1.6">
          <i class="ti ti-info-circle"></i>
          <b>نکته:</b> پروتکل‌های VMess، Reality، SS-2022 نیاز به سرور مجزا دارند (xray-core).
          EMIX فقط VLESS/Trojan/Shadowsocks/MTProto را به‌صورت واقعی هاست می‌کند.
          لینک تولیدی برای این پروتکل‌ها فقط فرمت لینک است و متصل نمی‌شود.
          برای استفاده، یک سرور xray-core جداگانه راه‌اندازی کنید.
        </div>
      </div>
    </div>

    <div class="card exp-sub-card" style="padding:20px">
      <h3 style="font-size:16px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        <i class="ti ti-rss" style="color:#FACC15"></i> فرمت‌های سابسکریپشن
      </h3>
      <p style="font-size:12px;color:var(--t3);margin-bottom:14px;line-height:1.6">
        خروجی subscription در چند فرمت برای پشتیبانی همه‌ی کلاینت‌ها (v2rayN/sing-box/Clash.Meta).
      </p>
      <div style="display:flex;flex-direction:column;gap:8px">
        <button class="btn btn-o exp-action-btn" onclick="expSub('raw')" style="text-align:right"><i class="ti ti-file-text"></i> raw (پیش‌فرض)</button>
        <button class="btn btn-o exp-action-btn" onclick="expSub('json')" style="text-align:right"><i class="ti ti-braces"></i> JSON (v2rayN/sing-box)</button>
        <button class="btn btn-o exp-action-btn" onclick="expSub('clash')" style="text-align:right"><i class="ti ti-code"></i> Clash.Meta YAML</button>
        <button class="btn btn-o exp-action-btn" onclick="expSub('encrypted')" style="text-align:right"><i class="ti ti-lock"></i> Encrypted (base64)</button>
      </div>
    </div>
  </div>

  <!-- Stealth Section -->
  <div class="card" style="padding:20px;margin-top:18px;border:1px solid rgba(139,92,246,.3)">
    <h3 style="font-size:16px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <i class="ti ti-ghost" style="color:#8B5CF6"></i> بخش استتار و جعل (Stealth/Disguise)
      <span style="font-size:11px;background:rgba(139,92,246,.2);color:#8B5CF6;padding:2px 8px;border-radius:8px;font-weight:600">مجزا</span>
    </h3>
    <p style="font-size:12px;color:var(--t3);margin-bottom:14px;line-height:1.6">
      متدهای استتار/جعل داده — هر یک toggle-based، بدون تأثیر در کد اصلی.
      این متدها فقط param های جعل را به لینک اضافه می‌کنند؛ اجرای واقعی آن‌ها در کلاینت (xray-core 26+) است.
    </p>
    <div id="exp-stealth-grid" class="exp-stealth-grid">
      <div style="grid-column:1/-1;text-align:center;padding:20px;color:var(--t3);font-size:12px">بارگذاری...</div>
    </div>
  </div>

  <!-- Anti-DPI Recheck -->
  <div class="card" style="padding:20px;margin-top:18px;border:1px solid rgba(250,204,21,.3)">
    <h3 style="font-size:16px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <i class="ti ti-shield-check" style="color:#FACC15"></i> بررسی مجدد کانفیگ‌های ضد-DPI
    </h3>
    <p style="font-size:12px;color:var(--t3);margin-bottom:14px;line-height:1.6">
      همه‌ی کانفیگ‌های ضد-DPI (XHTTP/Reality/WS با TLS) را با پینگ واقعی تست می‌کند.
    </p>
    <button class="btn btn-pur exp-recheck-btn" onclick="expRecheckAntiDPI()" style="background:linear-gradient(135deg,#8B5CF6,#FACC15);color:#fff;font-weight:700;width:100%">
      <i class="ti ti-refresh"></i> بررسی مجدد همه‌ی کانفیگ‌های ضد-DPI
    </button>
    <div id="exp-antidpi-result" style="margin-top:14px"></div>
  </div>
</section>

<!-- Unified Configs View (Phase 8) — همه‌ی کانفیگ‌ها در یک view مرکزی -->
<section class="pg" id="pg-unified-configs">
  <div class="page-hdr" style="margin-bottom:20px">
    <h1 style="font-size:24px;font-weight:800;color:#FACC15;display:flex;align-items:center;gap:10px">
      <i class="ti ti-grid-dots" style="font-size:28px"></i> همه‌ی کانفیگ‌ها (Unified)
    </h1>
    <p style="color:var(--t3);font-size:13px;margin-top:4px">نمایش مرکزی همه‌ی کانفیگ‌ها از همه‌ی بخش‌های پنل — با type badge و سلامت.</p>
  </div>

  <div style="display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap">
    <button class="btn btn-o" onclick="filterUnifiedConfigs('all')">همه</button>
    <button class="btn btn-o" onclick="filterUnifiedConfigs('links')">کانفیگ‌های اصلی</button>
    <button class="btn btn-o" onclick="filterUnifiedConfigs('subscriptions')">ساب‌گروپ‌ها</button>
    <button class="btn btn-o" onclick="filterUnifiedConfigs('nodes')">نودها</button>
    <button class="btn btn-o" onclick="filterUnifiedConfigs('vpn-pro')">VPN Pro</button>
    <button class="btn btn-o" onclick="filterUnifiedConfigs('experimental')">آزمایشی</button>
  </div>

  <div id="unified-configs-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px">
    <div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--t3)">
      <i class="ti ti-loader-2" style="font-size:32px;animation:spin 1s linear infinite"></i>
      <div style="margin-top:8px;font-size:13px">بارگذاری...</div>
    </div>
  </div>
</section>
</main>
<script>
let isDark=localStorage.getItem('rvg-theme')!=='light';
let updateAvailable = false;
let updateVersion = '';
let updateDescription = '';

function dismissUpdate() {
  sessionStorage.setItem('rvg-update-dismissed', 'true');
  closeModal('modal-update');
}

function startUpdateFromModal() {
  closeModal('modal-update');
  startUpdate(); // تابع موجود
}
function applyTheme(dark){
  document.documentElement.setAttribute('data-theme',dark?'dark':'light');
  const icon=dark?'ti-sun':'ti-moon',label=dark?'تم روشن':'تم تاریک';
  document.getElementById('theme-icon').className='ti '+icon;
  document.getElementById('theme-label').textContent=label;
  const mobI=document.getElementById('theme-mob-icon');if(mobI)mobI.className='ti '+icon;
}

function toggleTheme(){isDark=!isDark;localStorage.setItem('rvg-theme',isDark?'dark':'light');applyTheme(isDark)}
applyTheme(isDark);
// ── Audit fix (§50 frontend error handling): هیچ catch ای بی‌صدا نیست ──
// netErr: خطای شبکه/لودر را throttled به کاربر نشان می‌دهد (هر ۳۰s یک‌بار
// برای هر context — تا pollingهای ۲/۵ ثانیه‌ای spam نکنند).
const _netErrShown = {};
function netErr(e, ctx){
  console.error('['+ctx+']', e);
  const now = Date.now();
  if(_netErrShown[ctx] && now - _netErrShown[ctx] < 30000) return;
  _netErrShown[ctx] = now;
  try{ toast('⚠ خطا در دریافت «'+ctx+'» — اتصال یا نشست را بررسی کنید','err'); }catch(_e){}
}

function toast(msg,type=''){
  const t=document.getElementById('toast');
  t.textContent=msg;t.className='toast show'+(type?' '+type:'');
  setTimeout(()=>t.classList.remove('show'),2400);
}

/* ══════ Command Palette (Ctrl+K) ══════ */
let cpItems=[],cpSel=0,cpOpen=false;
function cpActions(){
  return [
    {t:'ساخت کانفیگ جدید',s:'ایجاد کانفیگ در صفحه کانفیگ‌ها',i:'ti-square-rounded-plus',run:()=>{navTo('links');setTimeout(()=>openModal('modal-create-link'),350)}},
    {t:'تست پینگ همه کانفیگ‌ها',s:'بررسی سلامت همه به‌صورت هم‌زمان',i:'ti-activity-heartbeat',run:()=>{navTo('links');setTimeout(()=>{const b=document.getElementById('ping-all-btn');if(b)pingAllLinks(b)},350)}},
    {t:'پیشنهاد هوشمند — سریع‌ترین کانفیگ',s:'تست زنده و رتبه‌بندی همه کانفیگ‌ها',i:'ti-trophy',run:()=>{navTo('overview');setTimeout(()=>bestConfigTest(),400)}},
    {t:'صفحه کانفیگ‌ها',s:'مدیریت لینک‌ها',i:'ti-link-plus',run:()=>navTo('links')},
    {t:'پل ایران',s:'مصرف داخلی + شتاب‌دهی',i:'ti-flag',run:()=>navTo('bridge')},
    {t:'تنظیمات حرفه‌ای',s:'ISP + TLS Mask + Smart + Security',i:'ti-bolt',run:()=>navTo('zeus')},
    {t:'اتصالات زنده',s:'مانیتورینگ لحظه‌ای',i:'ti-plug-connected',run:()=>navTo('connections')},
    {t:'ترافیک',s:'نمودار مصرف',i:'ti-chart-area',run:()=>navTo('traffic')},
    {t:'نودها',s:'مدیریت نودهای متصل',i:'ti-topology-star-3',run:()=>navTo('nodes')},
    {t:'گروه‌های ساب',s:'مدیریت گروه‌ها',i:'ti-folders',run:()=>navTo('subgroups')},
    {t:'تنظیمات',s:'تنظیمات پنل',i:'ti-settings',run:()=>navTo('settings')},
    {t:'لاگ فعالیت‌ها',s:'گزارش رویدادها',i:'ti-history',run:()=>navTo('logs')},
  ];
}
function cpBuild(){
  const q=document.getElementById('cp-input').value.trim().toLowerCase();
  const acts=cpActions().filter(a=>!q||a.t.toLowerCase().includes(q)||a.s.toLowerCase().includes(q));
  const links=q?allLinksList.filter(l=>l.label.toLowerCase().includes(q)||l.uuid.toLowerCase().includes(q)).slice(0,8):[];
  let html='';
  if(acts.length){html+='<div class="cp-group">فرمان‌ها</div>';html+=acts.map((a,ix)=>`<div class="cp-item" data-k="a${ix}"><i class="ti ${a.i}"></i><div class="cp-txt"><div class="cp-title">${a.t}</div><div class="cp-sub">${a.s}</div></div><span class="cp-hint">اجرا</span></div>`).join('')}
  if(links.length){html+='<div class="cp-group">کانفیگ‌ها</div>';html+=links.map((l,ix)=>`<div class="cp-item" data-k="l${ix}"><i class="ti ti-link"></i><div class="cp-txt"><div class="cp-title">${esc(l.label)}</div><div class="cp-sub">${l.uuid.slice(0,13)}… · ${l.protocol}</div></div><span class="cp-hint">مشاهده</span></div>`).join('')}
  if(!acts.length&&!links.length){html='<div id="cp-empty"><i class="ti ti-search-off" style="font-size:22px;display:block;margin-bottom:8px"></i>نتیجه‌ای یافت نشد</div>'}
  document.getElementById('cp-list').innerHTML=html;
  cpItems={acts,links};cpSel=0;cpHighlight();
  document.querySelectorAll('#cp-list .cp-item').forEach(el=>{
    el.onclick=()=>cpRun(el.dataset.k);
    el.onmouseenter=()=>{cpSel=[...document.querySelectorAll('#cp-list .cp-item')].indexOf(el);cpHighlight()};
  });
}
function cpHighlight(){
  document.querySelectorAll('#cp-list .cp-item').forEach((el,ix)=>el.classList.toggle('sel',ix===cpSel));
  const sel=document.querySelector('#cp-list .cp-item.sel');
  if(sel)sel.scrollIntoView({block:'nearest'});
}
function cpRun(key){
  if(!key)return;
  const src=key[0],ix=+key.slice(1);
  const item=src==='a'?cpItems.acts[ix]:cpItems.links[ix];
  if(!item)return;
  cpClose();
  if(src==='a'){item.run()}
  else{
    navTo('links');
    setTimeout(()=>{
      const card=document.querySelector(`#links-grid .cfg-card[data-uuid="${item.uuid}"]`);
      if(card){card.scrollIntoView({behavior:'smooth',block:'center'});card.style.boxShadow='0 0 0 2px var(--accent)';setTimeout(()=>card.style.boxShadow='',2200)}
    },500);
  }
}
function cpOpenShow(){
  cpOpen=true;document.getElementById('cp-overlay').classList.add('open');
  const inp=document.getElementById('cp-input');inp.value='';cpBuild();setTimeout(()=>inp.focus(),50);
}
function cpClose(){cpOpen=false;document.getElementById('cp-overlay').classList.remove('open')}
document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();cpOpen?cpClose():cpOpenShow();return}
  if(!cpOpen)return;
  if(e.key==='Escape'){e.preventDefault();cpClose()}
  else if(e.key==='ArrowDown'){e.preventDefault();const n=document.querySelectorAll('#cp-list .cp-item').length;if(n){cpSel=(cpSel+1)%n;cpHighlight()}}
  else if(e.key==='ArrowUp'){e.preventDefault();const n=document.querySelectorAll('#cp-list .cp-item').length;if(n){cpSel=(cpSel-1+n)%n;cpHighlight()}}
  else if(e.key==='Enter'){e.preventDefault();cpRun(document.querySelector('#cp-list .cp-item.sel')?.dataset.k)}
});
document.getElementById('cp-input').addEventListener('input',cpBuild);
function fmtB(b){if(!b||b===0)return '0 B';if(b<1024)return b+' B';if(b<1024**2)return (b/1024).toFixed(1)+' KB';if(b<1024**3)return (b/1024**2).toFixed(2)+' MB';return (b/1024**3).toFixed(2)+' GB'}
function toFa(n){return String(n).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d])}
function esc(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function daysLeft(exp){if(!exp)return null;return Math.ceil((new Date(exp)-Date.now())/(864e5))}
function expChip(exp,expired){
  if(expired)return '<span class="exp-chip ec-exp"><i class="ti ti-calendar-x"></i> منقضی</span>';
  if(!exp)return '<span class="exp-chip ec-inf"><i class="ti ti-infinity"></i> نامحدود</span>';
  const d=daysLeft(exp);
  if(d<=0)return '<span class="exp-chip ec-exp"><i class="ti ti-calendar-x"></i> منقضی</span>';
  if(d<=3)return `<span class="exp-chip ec-warn"><i class="ti ti-alert-triangle"></i> ${toFa(d)} روز مانده</span>`;
  return `<span class="exp-chip ec-ok"><i class="ti ti-calendar-check"></i> ${toFa(d)} روز مانده</span>`;
}
function protoBadge(p){
  const m={
    'shadowsocks':['Shadowsocks','pc-ss'],
    'vless-ws':['VLESS · WS','pc-ws'],
    'xhttp-packet-up':['VLESS · XHTTP packet-up','pc-xhttp'],
    'xhttp-stream-up':['VLESS · XHTTP stream-up','pc-xhttp'],
    'trojan-ws':['Trojan · WS','pc-trojan'],
    'trojan-xhttp-packet-up':['Trojan · XHTTP packet-up','pc-trojan'],
    'trojan-xhttp-stream-up':['Trojan · XHTTP stream-up','pc-trojan'],
    'mtproto':['Telegram Proxy · MTProto','pc-trojan'],
  };
  const v=m[p]||['ناشناخته','pc-ws'];
  return `<span class="proto-chip ${v[1]}">${v[0]}</span>`;
}
async function checkAuth(){try{const r=await fetch('/api/me');const d=await r.json();if(!d.authenticated)location.href='/login';}catch(e){location.href='/login'}}
async function logout(){try{await fetch('/api/logout',{method:'POST'})}catch(e){}location.href='/login'}
document.getElementById('logout-btn').addEventListener('click',logout);
async function authF(url,opts={},skipAuthRedirect=false){
  const r=await fetch(url,opts);
  if(r.status===401 && !skipAuthRedirect){location.href='/login';throw new Error('unauthorized')}
  return r;
}
function setQuota(val,unit,el){
  document.getElementById('nl-val').value = val===0?'':val;
  document.getElementById('nl-unit').value = unit;
  document.querySelectorAll('#quota-chips .qc-pill').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
}
function setExpiry(days,el){
  document.getElementById('nl-exp').value = days===0?'':days;
  document.querySelectorAll('#exp-chips .qc-pill').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
}
function selectProto(val,el){
  document.getElementById('nl-proto').value = val;
  document.querySelectorAll('.proto-card').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
}
const sb=document.getElementById('sb'),overlay=document.getElementById('overlay');
function openSb(){sb.classList.add('open');overlay.classList.add('show')}
function closeSb(){sb.classList.remove('open');overlay.classList.remove('show')}
document.getElementById('open-sb').addEventListener('click',openSb);
document.getElementById('close-sb').addEventListener('click',closeSb);
overlay.addEventListener('click',closeSb);
function navTo(name){
  document.querySelectorAll('.nav-it').forEach(n=>n.classList.toggle('on',n.dataset.pg===name));
  document.querySelectorAll('.pg').forEach(p=>p.classList.toggle('on',p.id==='pg-'+name));
  // ورود پلکانی کارت‌ها فقط هنگام سوییچ صفحه
  if(name==='links'){document.body.classList.add('cascade');setTimeout(()=>document.body.classList.remove('cascade'),650)}
  const loaders={links:loadLinks,bridge:loadBridgePage,connections:loadConns,errors:loadErrs,subscriptions:loadSubsPage,subgroups:loadSubs,logs:loadActivity,updates:loadVersion,support:loadSupportMsgs,nodes:loadNodesPage,zeus:loadZeusPage,gaming:loadGamingPage,multiloc:loadMultilocPage,vpn:loadVPNPage,experimental:loadExperimentalPage,'unified-configs':loadUnifiedConfigsPage,diag:loadDiagPage,routing:loadRoutingPage,accounts:loadAccountsPage,builder:loadBuilderPage,iranproxy:loadIranProxyPage};  if(loaders[name])loaders[name]();
  closeSb();window.scrollTo({top:0,behavior:'smooth'});
}
document.querySelectorAll('.nav-it').forEach(el=>el.addEventListener('click',()=>navTo(el.dataset.pg)));
function openModal(id){
  document.getElementById(id).classList.add('open');
  // When opening create-link modal, initialize protocol sections
  // (otherwise SNI spoofing + other sections stay display:none from HTML)
  if(id === 'modal-create-link'){
    setTimeout(()=>{
      const sel = document.querySelector('#dd-base .cm-opt.sel');
      if(sel){
        cmSelectBase(sel.dataset.base, sel);
      } else {
        // Fallback: default to vless
        const vlessOpt = document.querySelector('#dd-base .cm-opt[data-base="vless"]');
        if(vlessOpt) cmSelectBase('vless', vlessOpt);
      }
    }, 50);
  }
}
function closeModal(id){document.getElementById(id).classList.remove('open')}
let supportDevDismissCount=0;
const supportDevDismissTexts=['د اخه مگه دست خودته:(','نکن مشتی نداریمااااا'];
function handleSupportDevDismiss(){
  supportDevDismissCount++;
  if(supportDevDismissCount>=3){
    closeModal('modal-support-dev');
    localStorage.setItem('rvg-support-dev-seen','true');
    return;
  }
  document.getElementById('support-dev-dismiss-btn').textContent=supportDevDismissTexts[supportDevDismissCount-1];
}
let prevTraf=0,ch1,ch2,ch3;
async function fetchStats(){
  try{
    const r=await authF('/stats'),d=await r.json();
    document.getElementById('m-conns').textContent=d.active_connections;
    document.getElementById('conns-nb').textContent=d.active_connections;
    document.getElementById('m-traffic').innerHTML=d.total_traffic_mb.toFixed(1)+'<span class="m-unit">MB</span>';
    document.getElementById('m-alinks').textContent=d.active_links??'—';
    document.getElementById('m-lsub').textContent='از '+d.links_count+' کانفیگ';
    document.getElementById('m-subs').textContent=d.subs_count??'—';
    document.getElementById('errs-badge').textContent=d.total_errors+' خطا';
    document.getElementById('uptime-inline').textContent=d.uptime;
    document.getElementById('uptime-badge').textContent='Railway · '+d.uptime;
    document.getElementById('last-upd').textContent='آخرین بروزرسانی: '+new Date().toLocaleTimeString('fa-IR');
    document.getElementById('conns-live').innerHTML='<span class="dot dg pulse"></span> '+d.active_connections+' اتصال';
    document.getElementById('t-traffic').innerHTML=d.total_traffic_mb.toFixed(1)+'<span class="m-unit">MB</span>';
    const delta=d.total_traffic_mb-prevTraf,pct=Math.min(100,Math.round((delta/50)*100));
    document.getElementById('bw-pct').textContent=pct+'%';
    document.getElementById('bw-bar').style.width=pct+'%';
    prevTraf=d.total_traffic_mb;
    if(d.hourly){
      const labels=Object.keys(d.hourly).sort(),vals=labels.map(k=>+(d.hourly[k]/1024**2).toFixed(2));
      const avgAll=vals.length?vals.reduce((a,b)=>a+b,0)/vals.length:0;
      const avgLine=vals.map(()=>+avgAll.toFixed(2));
      if(ch1){ch1.data.labels=labels;ch1.data.datasets[0].data=vals;ch1.update();}
      if(ch3){ch3.data.labels=labels;ch3.data.datasets[0].data=vals;ch3.data.datasets[1].data=avgLine;ch3.update();}
      if(vals.length){
        const peak=Math.max(...vals),low=Math.min(...vals),peakIdx=vals.indexOf(peak);
        // Audit fix: info-strip — ترافیک این ساعت و ۲۴ ساعت اخیر (داده‌ی واقعی
        // از /stats.hourly؛ قبلاً این دو عنصر هرگز آپدیت نمی‌شدند و «0 B» فیک می‌ماندند)
        try{
          const curHour=labels[labels.length-1],lastMB=vals[vals.length-1]||0;
          document.getElementById('info-sent-recv').textContent=fmtB(lastMB*1024**2);
          const last24=vals.slice(-24).reduce((a,b)=>a+b,0);
          document.getElementById('info-usage').textContent=fmtB(last24*1024**2);
        }catch(_e){}
        document.getElementById('t-avg').innerHTML=avgAll.toFixed(2)+'<span class="m-unit">MB</span>';
        document.getElementById('t-peak').innerHTML=peak.toFixed(2)+'<span class="m-unit">MB</span>';
        document.getElementById('t-peak-time').textContent=labels[peakIdx]?('ساعت '+labels[peakIdx]):'بالاترین ساعت';
        document.getElementById('t-low').innerHTML=low.toFixed(2)+'<span class="m-unit">MB</span>';
        const trendEl=document.getElementById('t-trend'),trendVal=document.getElementById('t-trend-val');
        if(vals.length>=2){
          const prev=vals[vals.length-2],last=vals[vals.length-1];
          const diffPct=prev>0?((last-prev)/prev*100):(last>0?100:0);
          const up=diffPct>=0;
          trendEl.classList.toggle('up',up);trendEl.classList.toggle('down',!up);
          trendEl.querySelector('i').className='ti '+(up?'ti-trending-up':'ti-trending-down');
          trendVal.textContent=(up?'+':'')+diffPct.toFixed(1)+'%';
        }else{
          trendVal.textContent='—';
        }
      }else{
        document.getElementById('t-avg').textContent='—';
        document.getElementById('t-peak').textContent='—';
        document.getElementById('t-low').textContent='—';
        document.getElementById('t-trend-val').textContent='—';
      }
    }
    renderErrs(d.recent_errors||[]);
  }catch(e){console.error(e)}
}

// ── Audit fix (zero-fake-features): وضعیت سرویس + نمودار توزیع، از داده‌ی واقعی ──
// قبلاً: کارت وضعیت ۶ ردیف «فعال» hardcoded داشت و نمودار توزیع [55,35,10] ثابت بود.
// حالا: /api/diagnostics (موتور سلامت/گره‌ها/ران‌تایم/جاب/پایداری/ترکیب‌ها) + /api/links (توزیع پروتکل).
async function loadOverviewReal(){
  try{
    const r=await authF('/api/diagnostics');
    if(r.status===401){return}
    const d=await r.json();
    const c=d.checks||{};
    const set=(id,txt,color)=>{const el=document.getElementById(id);if(el){el.textContent=txt;if(color)el.style.color=color}};
    const G='var(--green-t)',A='var(--amber-t)',R='var(--red-t)';
    // Network Health
    try{
      const h=(c.network_health&&c.network_health.summary)||c.network_health||{};
      const tracked=h.tracked??0, by=h.by_state||{};
      const healthy=(by.HEALTHY||0), unk=(by.UNKNOWN||0);
      set('svc-health', tracked?`${healthy} سالم / ${tracked} ردیابی‌شده`:'— (هنوز پروب نشده)', tracked?G:'var(--t3)');
    }catch(_e){set('svc-health','—','var(--t3)')}
    // Nodes
    try{
      const n=c.nodes||{};
      set('svc-nodes', `${n.nodes??0} گره · ${((n.by_state||{}).ONLINE||0)} آنلاین`, G);
    }catch(_e){set('svc-nodes','—','var(--t3)')}
    // Runtimes
    try{
      const rt=c.runtimes||{}; const list=rt.runtimes||[];
      const failed=list.filter(x=>(x.state||'')==='FAILED').length;
      set('svc-runtimes', `${list.length} ران‌تایم${failed?` · ${failed} FAILED`:''}`, failed?R:G);
    }catch(_e){set('svc-runtimes','—','var(--t3)')}
    // Jobs
    try{
      const j=c.jobs||{}; const sup=j.supervisor==='RUNNING'?G:R;
      set('svc-jobs', `${j.supervisor==='RUNNING'?'فعال':'متوقف'} · ${(j.jobs||[]).length} جاب`, sup);
    }catch(_e){set('svc-jobs','—','var(--t3)')}
    // Persistence
    try{
      const p=c.persistence||{};
      const ok=p.writable!==false;
      set('svc-persist', ok?`قابل نوشتن · ${p.links??0} کانفیگ`:'⚠ Volume قابل نوشتن نیست', ok?G:A);
    }catch(_e){set('svc-persist','—','var(--t3)')}
    // Transports
    try{
      const t=c.transports||{};
      set('svc-transports', `${t.valid_combos??0} معتبر · ${t.experimental??0} آزمایشی`, G);
    }catch(_e){set('svc-transports','—','var(--t3)')}
  }catch(e){console.error('loadOverviewReal failed:',e)}
  // توزیع واقعی پروتکل‌ها از /api/links
  try{
    const r=await authF('/api/links');
    if(r.status===401){return}
    const j=await r.json();
    const links=(j.links||j)||[];
    const byProto={};
    for(const l of links){const p=l.protocol||'other';byProto[p]=(byProto[p]||0)+1}
    const labels=Object.keys(byProto),vals=labels.map(k=>byProto[k]);
    if(ch2&&vals.length){
      const palette=['#8B5CF6','#10B981','#FACC15','#38BDF8','#FB7185','#A3E635','#F97316','#22D3EE'];
      ch2.data.labels=labels;
      ch2.data.datasets[0].data=vals;
      ch2.data.datasets[0].backgroundColor=labels.map((_,i)=>palette[i%palette.length]);
      ch2.update();
    }else if(ch2){
      ch2.data.labels=['کانفیگی موجود نیست'];
      ch2.data.datasets[0].data=[1];
      ch2.update();
    }
  }catch(e){console.error('distribution failed:',e)}
}
function renderErrs(errs){
  const el=document.getElementById('errs-full');if(!el)return;
  if(!errs.length){el.innerHTML='<div style="color:var(--green-t);padding:10px;font-size:12px;display:flex;align-items:center;gap:5px"><i class="ti ti-circle-check"></i> هیچ خطایی نیست</div>';return}
  el.innerHTML=errs.slice().reverse().map(e=>`<div class="erow"><div class="etime"><i class="ti ti-clock"></i>${new Date(e.time).toLocaleString('fa-IR')}</div><div class="emsg">${esc(e.error)}${e.url?' — '+esc(e.url):''}</div></div>`).join('');
}
async function loadActivity(){
  try{
    const r=await authF('/api/activity'),d=await r.json();
    const logs=(d.logs||[]).slice().reverse();
    const el=document.getElementById('logs-list'),em=document.getElementById('logs-empty');
    if(!logs.length){el.innerHTML='';em.style.display='block';return}
    em.style.display='none';
    const icMap={ok:'ti-circle-check',err:'ti-circle-x',warn:'ti-alert-triangle',info:'ti-info-circle'};
    const kindFa={link:'کانفیگ',sub:'گروه',auth:'ورود',connection:'اتصال',system:'سیستم'};
    el.innerHTML=logs.map(l=>`
      <div class="log-item">
        <div class="log-ic ${l.level}"><i class="ti ${icMap[l.level]||'ti-info-circle'}"></i></div>
        <div class="log-body">
          <div class="log-msg">${esc(l.message)}</div>
          <div class="log-time"><i class="ti ti-clock"></i> ${new Date(l.time).toLocaleString('fa-IR')} <span class="log-kind">${kindFa[l.kind]||l.kind}</span></div>
        </div>
      </div>
    `).join('');
  }catch(e){netErr(e,'لاگ فعالیت‌ها')}
}
let allSubsList=[],allLinksList=[],onlineNodesList=[];
/* ══════ تست پینگ و سلامت کانفیگ‌ها ══════ */
async function clientRtt(){
  // سنجش RTT واقعی مرورگر → سرور (۲ بار، حداقل مقدار)
  const ts=[];
  for(let i=0;i<2;i++){
    const t0=performance.now();
    try{ await fetch('/api/ping',{cache:'no-store'}); ts.push(Math.round(performance.now()-t0)); }catch(e){}
  }
  return ts.length?Math.min(...ts):null;
}
function pingWaveHtml(){return '<span class="ping-wave"><span></span><span></span><span></span></span>'}
function pingMsClass(ms){return ms==null?'var(--green)':ms<500?'var(--green)':ms<1200?'var(--amber)':'var(--red)'}
function pingBadgeHtml(l){
  const p=l.last_ping;
  if(!p) return `<span class="cfg-sub-tag" id="pb-${l.uuid}" style="color:var(--t3);cursor:pointer" onclick="pingLink('${l.uuid}',this)" title="تست نشده — کلیک برای تست"><i class="ti ti-activity"></i> تست نشده</span>`;
  const tip=`تست: ${p.test||''}\nهدف: ${p.target||''}\nWS: ${p.ws_ms!=null?Math.round(p.ws_ms)+'ms':'—'}\nتونل: ${p.e2e_ms!=null?Math.round(p.e2e_ms)+'ms':'—'}\n${p.detail||''}\n${p.checked_at?new Date(p.checked_at).toLocaleString('fa-IR'):''}`;
  if(p.ok){
    const ms=p.e2e_ms!=null?Math.round(p.e2e_ms):null;
    return `<span class="cfg-sub-tag" id="pb-${l.uuid}" style="color:${pingMsClass(ms)};cursor:pointer" onclick="pingLink('${l.uuid}',this)" title="${tip}"><i class="ti ti-activity"></i> تونل ${ms!=null?toFa(ms)+'ms':'✓'}</span>`;
  }
  return `<span class="cfg-sub-tag" id="pb-${l.uuid}" style="color:var(--red-t);cursor:pointer" onclick="pingLink('${l.uuid}',this)" title="${tip}"><i class="ti ti-wifi-off"></i> قطع</span>`;
}
function renderPingBadge(uuid,d,rtt){
  const el=document.getElementById('pb-'+uuid);
  if(!el) return;
  if(d&&d.ok){
    const ms=d.e2e_ms!=null?Math.round(d.e2e_ms):null;
    el.style.color=pingMsClass(ms);
    el.innerHTML=`<i class="ti ti-activity"></i> تونل ${ms!=null?toFa(ms)+'ms':'✓'}${rtt!=null?' · من '+toFa(rtt)+'ms':''}`;
    el.title=`WS: ${d.ws_ms!=null?Math.round(d.ws_ms)+'ms':'—'} | تونل: ${d.e2e_ms!=null?Math.round(d.e2e_ms)+'ms':'—'} | پینگ شما: ${rtt!=null?rtt+'ms':'—'}`;
  }else{
    el.style.color='var(--red-t)';
    el.innerHTML=`<i class="ti ti-wifi-off"></i> قطع`;
    el.title=(d&&d.detail)?d.detail:'تست ناموفق';
  }
  // پاپ ظریف هنگام رسیدن نتیجه
  el.classList.remove('ping-pop');
  void el.offsetWidth; // ری‌استارت انیمیشن
  el.classList.add('ping-pop');
}
function pingLoading(uuid){
  const el=document.getElementById('pb-'+uuid);
  if(el){el.style.color='var(--t3)';el.innerHTML=pingWaveHtml()+' تست'}
}
async function pingLink(uuid,btn){
  const ic=btn?btn.querySelector('i'):null;
  const el0=document.getElementById('pb-'+uuid);
  if(el0) el0.dataset.userActive='1';  // جلوگیری از overwrite توسط auto-ping
  pingLoading(uuid);
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite'}
  try{
    const [rtt,r]=await Promise.all([clientRtt(),authF(`/api/links/${uuid}/ping`,{method:'POST'})]);
    const d=await r.json();
    renderPingBadge(uuid,d,rtt);
    if(d.ok) toast(`تونل سالم — ${d.e2e_ms!=null?Math.round(d.e2e_ms)+'ms':''}${rtt!=null?' · پینگ شما '+rtt+'ms':''}`,'ok');
    else toast('تست ناموفق: '+(d.detail||'نامشخص'),'err');
  }catch(e){
    const el=document.getElementById('pb-'+uuid);
    if(el){el.style.color='var(--red-t)';el.innerHTML='<i class="ti ti-wifi-off"></i> خطا'}
    toast('خطا در تست پینگ','err');
  }finally{
    if(el0) delete el0.dataset.userActive;
    if(ic){ic.className='ti ti-activity';ic.style.animation=''}
  }
}
async function pingNodeLink(uuid,btn,nodeId){
  const ic=btn?btn.querySelector('i'):null;
  pingLoading(uuid);
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite'}
  try{
    const r=await authF(`/api/nodes/${nodeId}/links/${uuid}/ping`,{method:'POST'});
    const d=await r.json();
    renderPingBadge(uuid,d,null);
    if(d.ok) toast(`تونل نود سالم — ${d.e2e_ms!=null?Math.round(d.e2e_ms)+'ms':''}`,'ok');
    else toast('تست ناموفق: '+(d.detail||'نامشخص'),'err');
  }catch(e){
    const el=document.getElementById('pb-'+uuid);
    if(el){el.style.color='var(--red-t)';el.innerHTML='<i class="ti ti-wifi-off"></i> خطا'}
    toast('خطا در تست پینگ نود','err');
  }finally{
    if(ic){ic.className='ti ti-activity';ic.style.animation=''}
  }
}
/* ══════ توربو 0-RTT — تست A/B خودکار ══════ */
async function bestConfigTest(btn){
  const box=document.getElementById('best-list');
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite'}
  if(btn)btn.disabled=true;
  if(box)box.innerHTML='<div class="sr"><span class="sr-k" style="color:var(--t3)"><i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال تست همه‌ی کانفیگ‌ها از مسیر عمومی...</span></div>';
  try{
    const r=await authF('/api/links/best',{method:'POST'});
    const d=await r.json();
    if(!box)return;
    const medals=['🥇','🥈','🥉','۴','۵'];
    if(!d.ranking||!d.ranking.length){
      box.innerHTML='<div class="sr"><span class="sr-k" style="color:var(--red-t)">کانفیگ سالمی برای رتبه‌بندی یافت نشد</span></div>';
      return;
    }
    box.innerHTML=d.ranking.map((c,ix)=>{
      const ms=Math.round(c.total_ms);
      const color=ms<500?'var(--green-t)':ms<1200?'var(--amber-t)':'var(--red-t)';
      return `<div class="sr" style="cursor:pointer" onclick="navTo('links');setTimeout(()=>{const el=document.querySelector('#links-grid .cfg-card[data-uuid=&quot;${c.uuid}&quot;]');if(el){el.scrollIntoView({behavior:'smooth',block:'center'});el.style.boxShadow='0 0 0 2px var(--accent)';setTimeout(()=>el.style.boxShadow='',2000)}},500)">
        <span class="sr-k" style="gap:7px"><span style="font-size:13px">${medals[ix]||''}</span> ${esc(c.label)}</span>
        <span class="sr-v" style="color:${color};font-weight:700">${toFa(ms)}ms</span>
      </div>`;
    }).join('')+`<div class="sr"><span class="sr-k" style="color:var(--t3);font-size:10px">${toFa(d.healthy)} از ${toFa(d.total)} کانفیگ سالم · ${new Date(d.checked_at).toLocaleTimeString('fa-IR')}</span></div>`;
    toast(`سریع‌ترین: ${d.ranking[0].label} — ${Math.round(d.ranking[0].total_ms)}ms`,'ok');
  }catch(e){
    if(box)box.innerHTML='<div class="sr"><span class="sr-k" style="color:var(--red-t)">خطا در تست — دوباره تلاش کنید</span></div>';
    toast('خطا در توصیه‌گر','err');
  }finally{
    if(ic){ic.className='ti ti-bolt';ic.style.animation=''}
    if(btn)btn.disabled=false;
  }
}
async function turboTest(uuid,btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite'}
  if(btn)btn.disabled=true;
  try{
    const r=await authF(`/api/turbo/links/${uuid}/ab`,{method:'POST'});
    const d=await r.json();
    if(!r.ok){toast(d.detail||'توربو در دسترس نیست','err');return}
    if(!d.ok){toast('تست توربو ناموفق بود: '+((d.turbo&&d.turbo.ok===false&&'تونل توربو پاسخ نداد')||'نامشخص'),'err');return}
    const n=Math.round(d.normal.total_ms||0),t=Math.round(d.turbo.total_ms||0);
    const imp=d.improvement_ms!=null?Math.round(d.improvement_ms):null;
    if(d.turbo_url){
      try{await navigator.clipboard.writeText(d.turbo_url)}catch(e){}
    }
    // در شبکه‌ی محلی تفاوت ~۰ است؛ در اینترنت واقعی صرفه‌جویی یک RTT کامل است
    const impTxt=(imp!=null&&imp>5)?` — ${toFa(imp)}ms بهتر`:' — در اینترنت واقعی ≈ یک RTT سریع‌تر';
    toast(`🚀 توربو ${toFa(t)}ms · عادی ${toFa(n)}ms${impTxt} · لینک توربو کپی شد`,'ok');
  }catch(e){
    toast('خطا در تست توربو','err');
  }finally{
    if(ic){ic.className='ti ti-rocket';ic.style.animation=''}
    if(btn)btn.disabled=false;
  }
}
async function pingAllLinks(btn){
  const targets=allLinksList.filter(l=>!l._nodeId);
  if(!targets.length){toast('کانفیگ محلی برای تست وجود ندارد','err');return}
  const ic=btn.querySelector('i');
  const label=btn.innerHTML;
  ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';
  btn.disabled=true;
  btn.classList.add('running');
  targets.forEach(l=>pingLoading(l.uuid));
  let done=0,ok=0,bad=0;
  const CONC=3; // هم‌زمانی — آپدیت زنده‌ی بج‌ها بدون فشار به سرور
  async function worker(list){
    for(const l of list){
      try{
        const r=await authF(`/api/links/${l.uuid}/ping`,{method:'POST'});
        const d=await r.json();
        l.last_ping=d;
        renderPingBadge(l.uuid,d,null);
        if(d.ok) ok++; else bad++;
      }catch(e){
        bad++;
        const el=document.getElementById('pb-'+l.uuid);
        if(el){el.style.color='var(--red-t)';el.innerHTML='<i class="ti ti-wifi-off"></i> خطا'}
      }
      done++;
      btn.innerHTML=`<i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> تست ${toFa(done)}/${toFa(targets.length)} <span class="ping-prog"></span>`;
    }
  }
  // تقسیم لیست بین worker ها برای پیشرفت هم‌زمان
  const queues=Array.from({length:Math.min(CONC,targets.length)},(_,i)=>targets.filter((_,j)=>j%CONC===i));
  try{
    await Promise.all(queues.map(q=>worker(q)));
    toast(`تست کامل شد — ${toFa(ok)} سالم، ${toFa(bad)} قطع`,bad?'warn':'ok');
  }finally{
    btn.classList.remove('running');
    btn.disabled=false;
    ic.style.animation='';
    btn.innerHTML=label;
  }
}
/* ══════ پل ایران — مصرف داخلی + شتاب‌دهی ══════ */
let bridgeScriptCache='';
let bridgeMode='vps';
function brSetMode(mode){
  bridgeMode=mode;
  const vps=document.getElementById('br-mode-vps'),cdn=document.getElementById('br-mode-cdn');
  // ظاهر انتخاب
  [vps,cdn].forEach(c=>{c.style.borderColor='var(--card-b)';const chk=c.querySelector('.br-mode-check');chk.style.borderColor='var(--t3)';chk.querySelector('i').style.opacity=0;chk.style.background='transparent'});
  const sel=mode==='vps'?vps:cdn;
  sel.style.borderColor='var(--accent)';const chk=sel.querySelector('.br-mode-check');chk.style.borderColor='var(--accent)';chk.style.background='var(--accent)';chk.querySelector('i').style.opacity=1;chk.querySelector('i').style.color='#fff';
  // نمایش/پنهان‌سازی راهنماها
  document.getElementById('br-cdn-guide').style.display=mode==='cdn'?'':'none';
  document.getElementById('br-vps-guide').style.display=mode==='vps'?'':'none';
  // متن‌های فرم
  document.getElementById('br-mode-label').textContent=mode==='cdn'?'(حالت: CDN ایرانی — رایگان)':'(حالت: سرور شخصی)';
  document.getElementById('br-form-title').textContent=mode==='cdn'?'دامنه‌ی پشت CDN ایرانی':'آدرس سرور داخل ایران';
  document.getElementById('br-host-label').textContent=mode==='cdn'?'دامنه‌ی شما روی ابر آروان (مثلاً sub.yourdomain.ir)':'آدرس سرور ایران (IP یا دامنه)';
  document.getElementById('br-port-wrap').style.display=mode==='cdn'?'':'none';
  document.getElementById('br-form-note').style.display=mode==='cdn'?'none':'';
  if(mode==='cdn'){
    const pi=document.getElementById('br-port');
    if(![443,2053,2083,2087,2096,8443].includes(parseInt(pi.value)))pi.value=443;
    pi.setAttribute('list','cdn-ports');
  }else{document.getElementById('br-port').removeAttribute('list')}
}
function brCalc(){
  const gb=parseInt(document.getElementById('br-calc-gb').value)||10;
  const without=Math.round(gb*2.7*10)/10;
  const save=Math.round((without-gb)*10)/10;
  const pct=Math.round((save/without)*100);
  document.getElementById('br-calc-gb-val').textContent=toFa(gb);
  document.getElementById('br-calc-without').textContent=toFa(without)+' GB';
  document.getElementById('br-calc-with').textContent=toFa(gb)+' GB';
  document.getElementById('br-calc-save').textContent=toFa(save)+' GB';
  const saveBox=document.getElementById('br-calc-save').closest('div[style*="accent-d"]');
  if(saveBox)saveBox.lastElementChild.textContent='در ماه ('+toFa(pct)+'٪)';
}
async function loadBridgePage(){
  try{
    const [cr,sr]=await Promise.all([authF('/api/bridge/config'),authF('/api/bridge/script').catch(()=>null)]);
    const cfg=await cr.json();
    bridgeMode=cfg.mode||'vps';
    brSetMode(bridgeMode);
    document.getElementById('br-host').value=cfg.bridge_host||'';
    document.getElementById('br-port').value=cfg.bridge_port||443;
    if(sr&&sr.ok){bridgeScriptCache=await sr.text();document.getElementById('br-script').textContent=bridgeScriptCache}
    const badge=document.getElementById('bridge-status-badge');
    const nb=document.getElementById('bridge-nb');
    if(cfg.bridge_host){badge.textContent='فعال';badge.className='badge bg-green';nb.style.display=''}
    else{badge.textContent='غیرفعال';badge.className='badge bg-blue';nb.style.display='none'}
    brCalc();
    if(cfg.bridge_host) await brLoadLinks();
  }catch(e){console.error(e)}
}
async function brSaveConfig(btn){
  const host=document.getElementById('br-host').value.trim();
  const port=parseInt(document.getElementById('br-port').value)||443;
  if(!host){toast('آدرس پل را وارد کنید','err');return}
  if(bridgeMode==='cdn'&&!host.includes('.')){toast('در حالت CDN باید دامنه وارد کنید (نه IP)','err');return}
  const ic=btn.querySelector('i');ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';btn.disabled=true;
  try{
    const r=await authF('/api/bridge/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:bridgeMode,bridge_host:host,bridge_port:port})});
    const d=await r.json();
    if(!r.ok){toast(d.detail||'خطا در ذخیره','err');return}
    toast('تنظیمات پل ذخیره شد','ok');
    // رفرش اسکریپت با پورت جدید (فقط حالت VPS)
    if(bridgeMode==='vps'){
      const sr=await authF('/api/bridge/script');
      if(sr.ok){bridgeScriptCache=await sr.text();document.getElementById('br-script').textContent=bridgeScriptCache}
    }
    await loadBridgePage();
  }catch(e){toast('خطا در ذخیره','err')}
  finally{ic.className='ti ti-device-floppy';ic.style.animation='';btn.disabled=false}
}
async function brTestBridge(btn){
  const host=document.getElementById('br-host').value.trim();
  if(!host){toast('ابتدا آدرس پل را ذخیره کنید','err');return}
  const ic=btn.querySelector('i');ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';btn.disabled=true;
  document.getElementById('bridge-metric-status').textContent='در حال تست...';
  document.getElementById('bridge-metric-sub').textContent=bridgeMode==='cdn'?'اتصال TLS به لبه‌ی CDN ایران':'اتصال TLS از مسیر پنل → سرور ایران → پنل';
  try{
    const r=await authF('/api/bridge/test',{method:'POST'});
    const d=await r.json();
    const st=document.getElementById('bridge-metric-status'),sub=document.getElementById('bridge-metric-sub'),ms=document.getElementById('bridge-metric-ms');
    if(d.ok){
      st.textContent=d.stage==='full-tunnel'?'سالم ✓✓':'TLS ✓';st.style.color='var(--green-t)';
      ms.textContent=d.ms!=null?toFa(Math.round(d.ms))+'ms':'✓';
      sub.textContent=d.detail||'زنجیره کامل کار می‌کند';
      toast('پل سالم است — '+d.detail,'ok');
    }else if(d.stage==='cname-missing' || d.stage==='preflight-dns' || d.stage==='preflight-error'){
      st.textContent='CNAME اروان';st.style.color='var(--amber-t)';
      ms.textContent='⚠️';
      sub.innerHTML=(d.detail||'CNAME اروان به‌درستی تنظیم نشده').replace(/\n/g,'<br>');
      toast('CNAME اروان به Railway وصل نیست — '+d.detail,'err');
    }else{
      st.textContent=d.stage==='ws-rejected'?'تنظیم اروان لازم':d.stage==='tls'?'TLS قطع':'تونل قطع';st.style.color='var(--red-t)';
      ms.textContent=d.ms!=null?toFa(Math.round(d.ms))+'ms':'—';
      sub.textContent=d.detail||'تست ناموفق';
      toast('تست پل: '+d.detail,'err');
    }
  }catch(e){
    document.getElementById('bridge-metric-status').textContent='خطا';
    toast('خطا در تست پل','err');
  }finally{ic.className='ti ti-activity';ic.style.animation='';btn.disabled=false}
}
async function brTestCNAME(btn){
  const ic=btn.querySelector('i');ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';btn.disabled=true;
  try{
    const r=await authF('/api/bridge/preflight');
    const d=await r.json();
    const st=document.getElementById('bridge-metric-status'),sub=document.getElementById('bridge-metric-sub'),ms=document.getElementById('bridge-metric-ms');
    if(d.ok){
      if(d.stage==='cname-ok'){
        st.textContent='CNAME ✓';st.style.color='var(--green-t)';
        ms.textContent='✓';
        sub.textContent=d.detail||'دامنه به Railway وصله';
        toast(d.detail,'ok');
      }else{
        st.textContent='بررسی...';st.style.color='var(--t3)';
        ms.textContent='?';
        sub.textContent=d.detail||'پاسخ غیرمنتظره';
        toast(d.detail,'info');
      }
    }else{
      st.textContent='CNAME ✗';st.style.color='var(--amber-t)';
      ms.textContent='⚠️';
      sub.innerHTML=(d.detail||'CNAME تنظیم نشده').replace(/\n/g,'<br>');
      toast('CNAME تنظیم نشده — '+d.detail,'err');
    }
  }catch(e){
    toast('خطا در تست CNAME','err');
  }finally{ic.className='ti ti-link';ic.style.animation='';btn.disabled=false}
}
async function brLoadLinks(){
  const list=document.getElementById('bridge-links-list');
  try{
    const [br,lr]=await Promise.all([authF('/api/bridge/links'),authF('/api/links')]);
    const d=await br.json();
    const live={};
    try{(await lr.json()).links.forEach(x=>live[x.uuid]=x)}catch(e){}
    const links=d.links||[];
    document.getElementById('bridge-links-cnt').textContent=toFa(links.length)+' کانفیگ';
    if(!links.length){
      list.innerHTML='<div class="empty"><i class="ti ti-flag-off"></i><p>کانفیگ فعالی برای پل‌دادن وجود ندارد</p></div>';
      return;
    }
    list.innerHTML=links.map(l=>{
      const bp=(live[l.uuid]||{}).last_bridge_ping;
      let badge='';
      if(bp){
        const ms=bp.e2e_ms!=null?Math.round(bp.e2e_ms):null;
        badge=bp.ok
          ?`<span class="cfg-sub-tag" id="bpb-${l.uuid}" style="color:${ms!=null&&ms<500?'var(--green-t)':ms!=null&&ms<1200?'var(--amber-t)':'var(--red-t)'};cursor:pointer" onclick="brPingLink('${l.uuid}',this)" title="${esc(bp.detail||'')}"><i class="ti ti-route"></i> پل ${ms!=null?toFa(ms)+'ms':'✓'}</span>`
          :`<span class="cfg-sub-tag" id="bpb-${l.uuid}" style="color:var(--red-t);cursor:pointer" onclick="brPingLink('${l.uuid}',this)" title="${esc(bp.detail||'تست ناموفق')}"><i class="ti ti-route-off"></i> پل قطع</span>`;
      }else{
        badge=`<span class="cfg-sub-tag" id="bpb-${l.uuid}" style="color:var(--t3);cursor:pointer" onclick="brPingLink('${l.uuid}',this)" title="تست نشده — کلیک برای تست از مسیر پل"><i class="ti ti-route"></i> تست پل</span>`;
      }
      return `
      <div style="display:flex;align-items:center;gap:10px;padding:11px 4px;border-bottom:1px solid var(--card-b);flex-wrap:wrap">
        ${protoBadge(l.protocol)}
        ${bridgeMode==='cdn'?'<span class="cfg-sub-tag" style="color:var(--green-t)"><i class="ti ti-cloud"></i> CDN</span>':'<span class="cfg-sub-tag" style="color:var(--accent2)"><i class="ti ti-server-2"></i> VPS</span>'}
        ${badge}
        <div style="flex:1;min-width:140px">
          <div style="font-weight:600;font-size:12.5px">${esc(l.label)}</div>
          <div style="font-size:9.5px;color:var(--t3);direction:ltr;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:420px">${esc(l.bridged)}</div>
        </div>
        <div style="display:flex;gap:6px">
          <button class="btn btn-sm btn-g btn-icon" onclick="brPingLink('${l.uuid}',this)" title="تست پینگ واقعی از مسیر پل (مثل کلاینت)"><i class="ti ti-activity"></i></button>
          <button class="btn btn-sm btn-g btn-icon" onclick="navigator.clipboard.writeText('${esc(l.bridged)}').then(()=>toast('لینک پل‌دار کپی شد','ok'))" title="کپی لینک پل‌دار"><i class="ti ti-copy"></i></button>
          <button class="btn btn-sm btn-g btn-icon" onclick="showQR('${esc(l.bridged)}')" title="QR"><i class="ti ti-qrcode"></i></button>
          <button class="btn btn-sm btn-g btn-icon" onclick="navigator.clipboard.writeText('${esc(l.original)}').then(()=>toast('لینک اصلی کپی شد','ok'))" title="لینک اصلی (بدون پل)"><i class="ti ti-external-link"></i></button>
        </div>
      </div>`;
    }).join('');
  }catch(e){
    list.innerHTML='<div class="empty"><i class="ti ti-alert-triangle"></i><p>خطا در دریافت لینک‌ها</p></div>';
  }
}
async function brPingLink(uuid,btn){
  const ic=btn?btn.querySelector('i'):null;
  const badge=document.getElementById('bpb-'+uuid);
  if(badge){badge.style.color='var(--t3)';badge.innerHTML='<span class="ping-wave"><span></span><span></span><span></span></span> تست'}
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite'}
  try{
    const r=await authF(`/api/bridge/links/${uuid}/ping`,{method:'POST'});
    const d=await r.json();
    const el=document.getElementById('bpb-'+uuid);
    if(el){
      if(d.ok){
        const ms=d.e2e_ms!=null?Math.round(d.e2e_ms):null;
        el.style.color=ms!=null&&ms<500?'var(--green-t)':ms!=null&&ms<1200?'var(--amber-t)':'var(--red-t)';
        el.innerHTML=`<i class="ti ti-route"></i> پل ${ms!=null?toFa(ms)+'ms':'✓'}`;
        el.title=d.detail||'';
      }else{
        el.style.color='var(--red-t)';
        el.innerHTML=`<i class="ti ti-route-off"></i> پل قطع`;
        el.title=d.detail||'تست ناموفق';
      }
      el.classList.remove('ping-pop');void el.offsetWidth;el.classList.add('ping-pop');
    }
    if(d.ok) toast(`پل سالم — ${d.e2e_ms!=null?Math.round(d.e2e_ms)+'ms':''}`,'ok');
    else toast('تست پل ناموفق — '+(d.detail||'').slice(0,150),'err');
  }catch(e){
    if(badge){badge.style.color='var(--red-t)';badge.innerHTML='<i class="ti ti-route-off"></i> خطا'}
    toast('خطا در تست پل','err');
  }finally{
    if(ic){ic.className='ti ti-activity';ic.style.animation=''}
  }
}
function brCopyScript(){
  if(!bridgeScriptCache)return;
  navigator.clipboard.writeText(bridgeScriptCache).then(()=>toast('اسکریپت نصب کپی شد — روی سرور ایران اجرایش کنید','ok'));
}

/* ══════ تنظیمات حرفه‌ای ZEUS — ISP + TLS Mask + Smart + Security ══════ */
let zeusIspList=[];
let zeusCurrentIsp='smart';
function zeusToggleSet(toggleId,enabled){
  const el=document.getElementById(toggleId);
  if(!el)return;
  el.checked=!!enabled;
  const slider=el.nextElementSibling;
  if(slider){
    slider.style.background=enabled?'var(--accent)':'var(--t3)';
  }
}
async function loadZeusPage(){
  try{
    const r=await authF('/api/zeus/config');
    if(!r.ok){toast('خطا در بارگذاری تنظیمات حرفه‌ای','err');return}
    const cfg=await r.json();
    zeusIspList=cfg.available_isps||[];
    zeusCurrentIsp=cfg.isp||'smart';
    // status badge
    const sb=document.getElementById('zeus-status-badge');
    sb.textContent='بارگذاری شد';sb.className='badge bg-green';
    // ۱) ISP رندر
    zeusRenderIspGrid();
    zeusShowIspDetail(zeusCurrentIsp);
    document.getElementById('zeus-isp-name').textContent=(cfg.isp_meta&&cfg.isp_meta.label)||zeusCurrentIsp;
    document.getElementById('zeus-isp-best-proto').textContent='پروتکل پیشنهادی: '+(cfg.isp_meta&&cfg.isp_meta.best_protocol||'—');
    // ۲) TLS Mask
    const tm=cfg.tls_mask||{};
    zeusToggleSet('zeus-tls-toggle',tm.enabled);
    document.getElementById('zeus-tls-sni').value=tm.custom_sni||'';
    document.getElementById('zeus-tls-cipher').value=tm.cipher_suites||'';
    document.getElementById('zeus-tls-frag-len').value=tm.fragment_length||'';
    document.getElementById('zeus-tls-frag-dly').value=tm.fragment_delay||'';
    document.getElementById('zeus-tls-status').textContent=tm.enabled?'فعال':'غیرفعال';
    document.getElementById('zeus-tls-sni-metric').textContent='SNI: '+(tm.custom_sni||'—');
    document.getElementById('zeus-tls-badge').style.display=tm.enabled?'inline-block':'none';
    // ۳) Smart Mode
    const sm=cfg.smart_mode||{};
    zeusToggleSet('zeus-smart-toggle',sm.enabled);
    document.getElementById('zeus-smart-status').textContent=sm.enabled?'فعال':'غیرفعال';
    // ۴) Security
    const sc=cfg.security||{};
    zeusToggleSet('zeus-security-toggle',sc.enabled);
    document.getElementById('zeus-sec-min-len').value=sc.min_password_length||8;
    document.getElementById('zeus-sec-interval').value=sc.attempt_interval_ms||1000;
    document.getElementById('zeus-sec-max').value=sc.max_attempts||5;
    document.getElementById('zeus-sec-lockout').value=sc.lockout_ms||60000;
    document.getElementById('zeus-security-status').textContent=sc.enabled?'فعال':'غیرفعال';
    document.getElementById('zeus-security-rule').textContent='حداکثر تلاش: '+(sc.max_attempts||5);
  }catch(e){console.error('loadZeusPage',e);toast('خطا در بارگذاری صفحه‌ی تنظیمات حرفه‌ای','err')}
}
function zeusRenderIspGrid(){
  const grid=document.getElementById('zeus-isp-grid');
  if(!grid||!zeusIspList.length)return;
  grid.innerHTML=zeusIspList.map(isp=>`
    <div class="card br-mode-card" id="zeus-isp-${isp.id}" onclick="zeusSelectIsp('${isp.id}')" style="cursor:pointer;padding:12px">
      <div style="display:flex;align-items:center;gap:10px">
        <div style="width:36px;height:36px;border-radius:10px;background:var(--accent-d);display:flex;align-items:center;justify-content:center;flex-shrink:0">
          <i class="ti ${isp.icon||'ti-device-mobile'}" style="font-size:18px;color:${isp.color||'var(--accent2)'}"></i>
        </div>
        <div style="flex:1">
          <div style="font-weight:700;font-size:12px">${isp.label}</div>
          <div style="font-size:9.5px;color:var(--t3);margin-top:2px">پینگ: ${isp.expected_ping_ms||'—'}</div>
        </div>
        <div class="br-mode-check" style="width:18px;height:18px;border-radius:50%;border:2px solid var(--t3);display:flex;align-items:center;justify-content:center">
          <i class="ti ti-check" style="font-size:10px;opacity:0"></i>
        </div>
      </div>
    </div>
  `).join('');
  zeusUpdateIspSelection();
}
function zeusUpdateIspSelection(){
  zeusIspList.forEach(isp=>{
    const el=document.getElementById('zeus-isp-'+isp.id);
    if(!el)return;
    const selected=isp.id===zeusCurrentIsp;
    el.style.borderColor=selected?'var(--accent)':'var(--card-b)';
    const chk=el.querySelector('.br-mode-check');
    if(chk){
      chk.style.borderColor=selected?'var(--accent)':'var(--t3)';
      chk.style.background=selected?'var(--accent)':'transparent';
      const icon=chk.querySelector('i');if(icon){icon.style.opacity=selected?1:0;icon.style.color='#fff'}
    }
  });
}
function zeusShowIspDetail(ispId){
  const isp=zeusIspList.find(x=>x.id===ispId);
  const box=document.getElementById('zeus-isp-detail');
  if(!isp||!box){return}
  box.style.display='';
  document.getElementById('zeus-isp-detail-title').textContent=isp.label+' — پروتکل پیشنهادی: '+(isp.best_protocol||'—');
  document.getElementById('zeus-isp-detail-rationale').textContent=isp.rationale||'';
  const ul=document.getElementById('zeus-isp-detail-tips');
  ul.innerHTML=(isp.tips||[]).map(t=>`<li style="margin-bottom:4px">${t}</li>`).join('');
}
async function zeusSelectIsp(ispId){
  try{
    const r=await authF('/api/zeus/isp',{method:'POST',body:JSON.stringify({isp:ispId})});
    if(!r.ok){toast('خطا در ذخیره‌ی ISP','err');return}
    const j=await r.json();
    zeusCurrentIsp=ispId;
    zeusUpdateIspSelection();
    zeusShowIspDetail(ispId);
    document.getElementById('zeus-isp-name').textContent=j.meta.label;
    document.getElementById('zeus-isp-best-proto').textContent='پروتکل پیشنهادی: '+(j.meta.best_protocol||'—');
    toast('ISP روی '+j.meta.label+' تنظیم شد','ok');
  }catch(e){console.error('zeusSelectIsp',e);toast('خطا در ارتباط با سرور','err')}
}
async function zeusSaveTlsMask(){
  const enabled=document.getElementById('zeus-tls-toggle').checked;
  const custom_sni=document.getElementById('zeus-tls-sni').value.trim();
  const cipher_suites=document.getElementById('zeus-tls-cipher').value.trim();
  const fragment_length=document.getElementById('zeus-tls-frag-len').value.trim();
  const fragment_delay=document.getElementById('zeus-tls-frag-dly').value.trim();
  try{
    const r=await authF('/api/zeus/tls-mask',{method:'POST',body:JSON.stringify({enabled,custom_sni,cipher_suites,fragment_length,fragment_delay})});
    if(!r.ok){toast('خطا در ذخیره','err');return}
    const j=await r.json();
    zeusToggleSet('zeus-tls-toggle',j.tls_mask.enabled);
    document.getElementById('zeus-tls-status').textContent=j.tls_mask.enabled?'فعال':'غیرفعال';
    document.getElementById('zeus-tls-sni-metric').textContent='SNI: '+(j.tls_mask.custom_sni||'—');
    document.getElementById('zeus-tls-badge').style.display=j.tls_mask.enabled?'inline-block':'none';
    toast('تنظیمات TLS Mask ذخیره شد','ok');
  }catch(e){toast('خطا در ارتباط','err')}
}
async function zeusShowMaskedLinks(){
  try{
    const r=await authF('/api/zeus/tls-mask/links');
    if(!r.ok){toast('خطا','err');return}
    const j=await r.json();
    if(!j.enabled){toast('ابتدا TLS Mask را فعال کنید','err');return}
    if(!j.links||!j.links.length){toast('هیچ کانفیگی برای ساخت لینک Mask-شده وجود ندارد','err');return}
    const links=j.links.map(l=>`<div style="margin-bottom:10px;padding:8px;background:var(--bg);border-radius:8px;border:1px solid var(--card-b)">
      <div style="font-weight:700;font-size:11.5px;margin-bottom:4px">${esc(l.label)} <span class="badge bg-blue" style="font-size:9px">${l.protocol}</span></div>
      <div style="font-family:monospace;font-size:9.5px;direction:ltr;text-align:left;word-break:break-all;background:var(--card);padding:6px;border-radius:6px;color:var(--green-t)">${esc(l.masked)}</div>
      <button class="btn btn-sm btn-g" style="margin-top:6px" onclick="navigator.clipboard.writeText('${l.masked.replace(/'/g,"\\'")}').then(()=>toast('لینک کپی شد','ok'))"><i class="ti ti-copy"></i> کپی</button>
    </div>`).join('');
    openModalGeneric('لینک‌های Mask-شده (SNI: '+esc(j.sni)+')',links);
  }catch(e){toast('خطا در ارتباط','err')}
}
async function zeusShowFragmentJson(){
  try{
    const r=await authF('/api/zeus/tls-mask/fragment-json');
    if(!r.ok){toast('خطا','err');return}
    const j=await r.json();
    const pretty=JSON.stringify(j,null,2);
    openModalGeneric('JSON Fragment + TLS Settings (برای کپی در Xray کلاینت)',
      '<div style="font-size:11px;color:var(--t3);margin-bottom:8px">این JSON را در فایل config.json کلاینت Xray (در بخش streamSettings.outbound) قرار دهید</div>'+
      '<pre style="background:var(--bg);padding:14px;border-radius:8px;font-size:10px;direction:ltr;text-align:left;overflow-x:auto;max-height:400px;font-family:monospace;border:1px solid var(--card-b)">'+esc(pretty)+'</pre>'+
      '<button class="btn btn-g" style="margin-top:10px" onclick="navigator.clipboard.writeText('+JSON.stringify(JSON.stringify(pretty))+').then(()=>toast(\'کپی شد\',\'ok\'))"><i class="ti ti-copy"></i> کپی JSON</button>'
    );
  }catch(e){toast('خطا در ارتباط','err')}
}
async function zeusSmartRecommend(){
  const btn=event?.target?.closest('button');
  if(btn){btn.disabled=true;btn.innerHTML='<i class="ti ti-loader ti-spin"></i> در حال تست...'}
  try{
    const r=await authF('/api/zeus/smart/recommend');
    if(!r.ok){toast('خطا در تست','err');return}
    const j=await r.json();
    const box=document.getElementById('zeus-smart-result');
    const content=document.getElementById('zeus-smart-result-content');
    box.style.display='';
    if(j.best){
      const b=j.best;
      content.innerHTML='<div style="display:flex;align-items:center;gap:10px">'+
        '<div style="width:40px;height:40px;border-radius:50%;background:var(--green-bg);display:flex;align-items:center;justify-content:center"><i class="ti ti-trophy" style="color:var(--green-t);font-size:20px"></i></div>'+
        '<div style="flex:1"><div style="font-weight:700;font-size:13px">'+esc(b.label)+'</div>'+
        '<div style="font-size:11px;color:var(--t3)">پروتکل: '+b.protocol+' · تاخیر کل: '+toFa(b.total_ms)+' ms</div></div>'+
        '<button class="btn btn-sm btn-g" onclick="navigator.clipboard.writeText(\\\'\\\').then(()=>toast(\'لینک در صفحه کانفیگ‌ها قابل کپی است\',\'ok\'))"><i class="ti ti-link"></i> کانفیگ</button></div>';
      document.getElementById('zeus-smart-best').textContent='بهترین: '+b.label+' ('+b.total_ms+'ms)';
      toast('بهترین کانفیگ: '+b.label+' با '+b.total_ms+'ms','ok');
    }else{
      content.innerHTML='<div style="color:var(--t3);font-size:12px;text-align:center;padding:10px">هیچ کانفیگ سالمی یافت نشد — '+toFa(j.checked)+' کانفیگ تست شد</div>';
      document.getElementById('zeus-smart-best').textContent='بهترین: پیدا نشد';
      toast('هیچ کانفیگ سالمی یافت نشد','err');
    }
  }catch(e){toast('خطا در ارتباط','err')}
  finally{if(btn){btn.disabled=false;btn.innerHTML='<i class="ti ti-trophy"></i> تست اکنون و معرفی بهترین'}}
}
async function zeusSaveSmart(){
  const enabled=document.getElementById('zeus-smart-toggle').checked;
  const interval_ms=parseInt(document.getElementById('zeus-smart-interval')?.value||'1000');
  const accuracy=parseInt(document.getElementById('zeus-smart-accuracy')?.value||'4');
  try{
    const r=await authF('/api/zeus/smart',{method:'POST',body:JSON.stringify({enabled,interval_ms,accuracy})});
    if(!r.ok)return;
    const j=await r.json();
    zeusToggleSet('zeus-smart-toggle',j.smart_mode.enabled);
    document.getElementById('zeus-smart-status').textContent=j.smart_mode.enabled?'فعال':'غیرفعال';
    toast('حالت هوشمند '+(j.smart_mode.enabled?'فعال':'خاموش')+' شد','ok');
  }catch(e){toast('خطا','err')}
}
async function zeusSaveSecurity(){
  const enabled=document.getElementById('zeus-security-toggle').checked;
  const min_password_length=parseInt(document.getElementById('zeus-sec-min-len').value)||8;
  const attempt_interval_ms=parseInt(document.getElementById('zeus-sec-interval').value)||1000;
  const max_attempts=parseInt(document.getElementById('zeus-sec-max').value)||5;
  const lockout_ms=parseInt(document.getElementById('zeus-sec-lockout').value)||60000;
  try{
    const r=await authF('/api/zeus/security',{method:'POST',body:JSON.stringify({enabled,min_password_length,attempt_interval_ms,max_attempts,lockout_ms})});
    if(!r.ok){toast('خطا در ذخیره','err');return}
    const j=await r.json();
    zeusToggleSet('zeus-security-toggle',j.security.enabled);
    document.getElementById('zeus-security-status').textContent=j.security.enabled?'فعال':'غیرفعال';
    document.getElementById('zeus-security-rule').textContent='حداکثر تلاش: '+j.security.max_attempts;
    toast('تنظیمات امنیت ذخیره شد','ok');
  }catch(e){toast('خطا در ارتباط','err')}
}
async function zeusSecurityCheck(){
  try{
    const r=await authF('/api/zeus/security/check',{method:'POST'});
    if(!r.ok)return;
    const j=await r.json();
    const box=document.getElementById('zeus-security-result');
    const content=document.getElementById('zeus-security-result-content');
    box.style.display='';
    content.innerHTML='<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:11.5px">'+
      '<div><div style="color:var(--t3);margin-bottom:4px">میان‌افزار</div><div style="font-weight:700">'+(j.middleware_active?'<span style="color:var(--green-t)">فعال</span>':'<span style="color:var(--red-t)">غیرفعال</span>')+'</div></div>'+
      '<div><div style="color:var(--t3);margin-bottom:4px">IPهای بلاک‌شده</div><div style="font-weight:700">'+toFa(j.currently_blocked_count)+'</div></div>'+
      '<div><div style="color:var(--t3);margin-bottom:4px">حداکثر تلاش</div><div style="font-weight:700">'+toFa(j.rules.max_attempts)+'</div></div>'+
      '<div><div style="color:var(--t3);margin-bottom:4px">فاصله‌ی تلاش‌ها</div><div style="font-weight:700">'+toFa(j.rules.attempt_interval_ms)+' ms</div></div>'+
      '<div><div style="color:var(--t3);margin-bottom:4px">مدت بلاک</div><div style="font-weight:700">'+toFa(j.rules.lockout_ms)+' ms</div></div>'+
      '<div><div style="color:var(--t3);margin-bottom:4px">حداقل طول پسورد</div><div style="font-weight:700">'+toFa(j.rules.min_password_length)+'</div></div>'+
    '</div>';
    toast('وضعیت میان‌افزار بررسی شد','ok');
  }catch(e){toast('خطا','err')}
}

/* ═════════════════ مرکز گیمینگ — اسکنر IP + لوکیشن + کانفیگ گیمینگ ═════════════════ */
let gamingCfg={},gamingScanBusy=false;

/* ═════════════════ زیرساخت: Volume خودکار + سلامت کلی ═════════════════ */
async function checkVolumeBanner(){
  try{
    const r=await authF('/api/system/infra/status');
    if(!r.ok)return;
    const j=await r.json();
    const w=document.getElementById('volume-warn');
    if(w&&j.on_railway&&!j.volume_mounted){w.style.display=''}
  }catch(e){}
}
async function ensureVolume(btn){
  const ic=btn.querySelector('i');ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';btn.disabled=true;
  try{
    const r=await authF('/api/system/infra/ensure-volume',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const j=await r.json().catch(()=>({ok:false,error:'پاسخ نامعتبر'}));
    if(j.ok){
      toast(j.message||'Volume ساخته شد','ok');
      document.getElementById('volume-warn').style.display='none';
    }else{toast(j.error||'خطا در ساخت volume','err')}
  }catch(e){toast('خطا','err')}
  finally{ic.className='ti ti-database-plus';ic.style.animation='';btn.disabled=false}
}
async function runHealthAll(btn){
  const ic=btn.querySelector('i');ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';btn.disabled=true;
  const box=document.getElementById('health-all-result');
  box.style.display='';box.innerHTML='<div style="font-size:12px;color:var(--t3);padding:8px"><i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال بررسی همه‌ی بخش‌ها (تا ۴۵ ثانیه)...</div>';
  try{
    const r=await authF('/api/system/health-all');
    if(!r.ok){box.innerHTML='<span style="color:var(--red-t);font-size:12px">خطا در دریافت گزارش سلامت</span>';return}
    const j=await r.json();
    const secs=Object.entries(j.sections||{});
    const rowHtml=(label,s)=>{
      const ok=s.ok;
      const col=ok?'var(--green-t)':'var(--red-t)';
      const icon=ok?'<i class="ti ti-circle-check"></i>':'<i class="ti ti-circle-x"></i>';
      let extra='';
      if(s.error)extra+=` — <span style="color:var(--t3)">${s.error}</span>`;
      if(s.detail&&typeof s.detail==='string')extra+=` — <span style="color:var(--t3)">${s.detail}</span>`;
      if(s.mounted===false&&s.ok===false)extra='';
      const lat=s.latency_ms!=null?` <span class="badge bg-blue" style="font-size:9.5px">${toFa(s.latency_ms)}ms</span>`:'';
      return `<div style="display:flex;align-items:center;gap:8px;padding:7px 10px;background:var(--bg);border-radius:8px;border:1px solid var(--card-b);margin-bottom:6px">
        <span style="color:${col}">${icon}</span>
        <div style="flex:1;font-size:12px"><b>${label}</b><span style="font-size:11px;color:var(--t2)">${extra}</span></div>
        ${lat}
        <span class="badge ${ok?'bg-green':'bg-red'}" style="font-size:9.5px">${ok?'سالم':'مشکل'}</span>
      </div>`;
    };
    const labels={'panel':'هسته‌ی پنل','volume':'دیتای دائمی (Volume)','links':'کانفیگ‌ها','mtproto':'پروسه‌های MTProto','tcp_proxies':'TCP Proxies ریلوی','cf_gateway':'گیت‌وی کلادفلر','bridge':'پل ایران','module:zeus_features':'ماژول ZEUS Pro','module:gaming_boost':'ماژول مرکز گیمینگ','module:bridge_boost':'ماژول پل ایران','module:turbo_boost':'ماژول توربو','module:clean_ip_boost':'ماژول آی‌پی تمیز','module:link_health':'ماژول تست پینگ'};
    let html=`<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
      <span class="badge ${j.ok?'bg-green':'bg-red'}">${j.ok?'همه‌چیز سالم ✓':'مشکلاتی پیدا شد'}</span>
      <span style="font-size:11px;color:var(--t3)">${toFa(secs.filter(([_,s])=>s.ok).length)} از ${toFa(secs.length)} بخش سالم</span>
    </div>`;
    // بخش‌های مهم اول
    const order=['panel','volume','links','mtproto','tcp_proxies','cf_gateway','bridge'];
    const rest=secs.filter(([k])=>!order.includes(k)&&!k.startsWith('module:'));
    const mods=secs.filter(([k])=>k.startsWith('module:'));
    for(const k of order){const f=secs.find(([kk])=>kk===k);if(f)html+=rowHtml(labels[k]||k,f[1])}
    if(mods.length){
      const modOk=mods.filter(([_,s])=>s.ok).length;
      html+=`<div style="display:flex;align-items:center;gap:8px;padding:7px 10px;background:var(--bg);border-radius:8px;border:1px solid var(--card-b);margin-bottom:6px">
        <span style="color:${modOk===mods.length?'var(--green-t)':'var(--amber-t)'}"><i class="ti ti-plug-connected"></i></span>
        <div style="flex:1;font-size:12px"><b>ماژول‌های افزونه</b><span style="font-size:11px;color:var(--t3)"> — ${toFa(modOk)}/${toFa(mods.length)} بارگذاری کامل</span></div>
        <span class="badge ${modOk===mods.length?'bg-green':'bg-amber'}" style="font-size:9.5px">${modOk===mods.length?'سالم':'ناقص'}</span>
      </div>`;
    }
    box.innerHTML=html;
    toast(j.ok?'همه‌ی بخش‌ها سالم هستند':'برخی بخش‌ها مشکل دارند — جزئیات در کارت',j.ok?'ok':'err');
  }catch(e){box.innerHTML='<span style="color:var(--red-t);font-size:12px">خطا در بررسی سلامت</span>'}
  finally{ic.className='ti ti-stethoscope';ic.style.animation='';btn.disabled=false}
}
/* تست همه‌ی کانفیگ‌ها از مسیر گیت‌وی کلادفلر (پینگ واقعی خروجی) */
async function pingAllViaWorker(){
  try{
    const r=await authF('/api/links/ping-all?via=worker',{method:'POST'});
    if(!r.ok){toast('خطا','err');return}
    const j=await r.json();
    toast(`تست از مسیر گیت‌وی: ${toFa(j.ok)} از ${toFa(j.total)} سالم`,j.ok>0?'ok':'err');
  }catch(e){toast('خطا','err')}
}
const COLO_NAMES={IST:'استانبول 🇹🇷',FRA:'فرانکفورت 🇩🇪',MRS:'مارسی 🇫🇷',BAH:'بحرین 🇧🇭',DXB:'دبی 🇦🇪',AMS:'آمستردام 🇳🇱',LHR:'لندن 🇬🇧',CDG:'پاریس 🇫🇷',MIL:'میلان 🇮🇹',VIE:'وین 🇦🇹',WAW:'ورشو 🇵🇱',KIV:'کیشیناو 🇲🇩',DME:'مسکو 🇷🇺',TAS:'تاشکند 🇺🇿',ALA:'آلماتی 🇰🇿',SIN:'سنگاپور 🇸🇬',DXB2:'دبی۲',TLV:'تل‌آویو',DOH:'دوحه 🇶🇦',KWI:'کویت 🇰🇼'};

/* ═════════════════ پل چندلوکیشن v2 — MultiLoc (WTE) ═════════════════ */
let mlLinksCache=[],mlStatusCache=null;
async function loadMultilocPage(){ await mlStatus(false); await mlLoadLocations(false); mlFillCfgSelect(); }
async function mlStatus(toastIt){
  try{
    const r=await authF('/api/multiloc/status');
    if(!r.ok)throw new Error('status '+r.status);
    const j=await r.json();mlStatusCache=j;
    const sb=document.getElementById('ml-status-badge');
    const ready=j.ready&&j.worker&&j.worker.supports_wte;
    sb.textContent=j.ready?(j.worker.supports_wte?'آماده — WTE فعال':'وورکر v1 — آپگرید لازم'):'Worker تنظیم نشده';
    sb.className='badge '+(ready?'bg-green':(j.ready?'bg-amber':'bg-red'));
    document.getElementById('ml-worker-ver').textContent=(j.worker&&j.worker.version)||'—';
    document.getElementById('ml-worker-domain-lbl').textContent=j.worker_domain||'—';
    const wte=document.getElementById('ml-wte-status');
    if(j.worker&&j.worker.supports_wte){wte.textContent='فعال ✓';wte.style.color='var(--green-t)';document.getElementById('ml-wte-sub').textContent='سرور VLESS داخل وورکر — خروج از colo';}
    else{wte.textContent='غیرفعال';wte.style.color='var(--amber-t)';document.getElementById('ml-wte-sub').textContent='کد v2 وورکر را Paste کن';}
    document.getElementById('ml-worker-upgrade').style.display=(j.worker&&j.worker.supports_wte||!j.ready)?'none':'';
    if(j.locations_cached){document.getElementById('ml-loc-count').textContent=toFa(j.locations_cached)+' لوکیشن';}
    if(toastIt)toast(ready?'گیت‌وی WTE آماده است ✓':'وضعیت گیت‌وی به‌روز شد',ready?'ok':'info');
  }catch(e){ const sb=document.getElementById('ml-status-badge');sb.textContent='خطا';sb.className='badge bg-red'; if(toastIt)toast('خطا در وضعیت مولتی‌لوک: '+(e.message||''),'err'); }
}
async function mlScan(btn,deep){
  const pr=document.getElementById('ml-scan-progress');
  const old=btn.innerHTML;btn.disabled=true;pr.textContent='در حال اسکن — هندشیک واقعی TLS...';
  try{
    const r=await authF('/api/multiloc/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({deep:!!deep})});
    if(!r.ok)throw new Error((await r.json().catch(()=>({}))).error||('HTTP '+r.status));
    const j=await r.json();
    if(!j.ok){toast(j.error||'اسکن ناموفق','err');pr.textContent='ناموفق';return}
    mlRenderLocations(j.locations,j.stats);
    pr.textContent='انجام شد ✓ '+toFa(j.stats.colos)+' colo از '+toFa(j.stats.probed)+' IP';
    document.getElementById('ml-loc-count').textContent=toFa(j.locations.length)+' لوکیشن';
    toast('اسکن کامل شد — '+toFa(j.stats.colos)+' لوکیشن تایید شد ✓','ok');
  }catch(e){pr.textContent='خطا';toast('اسکن ناموفق: '+(e.message||''),'err');}
  finally{btn.disabled=false;btn.innerHTML=old;}
}
async function mlLoadLocations(render){
  try{
    const r=await authF('/api/multiloc/locations');
    if(!r.ok)return;
    const j=await r.json();
    if(j.ok&&j.locations){mlRenderLocations(j.locations,j.stats);}
  }catch(e){}
}
function mlRenderLocations(locs,stats){
  const g=document.getElementById('ml-loc-grid');if(!g)return;
  g.innerHTML=locs.map(l=>{
    const rtt=l.rtt_ms?toFa(Math.round(l.rtt_ms))+' ms':'—';
    const ip=(l.best_ip||'—');
    return `<div class="card" style="margin:0;padding:12px;border:1px solid var(--card-b)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <b style="font-size:13px">${l.flag} ${esc(l.city)}</b>
        <span class="badge ${l.key==='auto'?'bg-blue':'bg-green'}" style="font-size:10px">${l.colo?esc(l.colo):'AUTO'}</span>
      </div>
      <div style="font-size:11px;color:var(--t3);direction:ltr;text-align:left;font-family:monospace;overflow:hidden;text-overflow:ellipsis">${esc(ip)}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px">
        <span style="font-size:11px;color:var(--t3)">RTT: <b style="color:var(--green-t)">${rtt}</b></span>
        <button class="btn btn-o btn-sm" style="font-size:10px;padding:4px 10px" onclick="mlEgress('${esc(l.key)}',this)">تست خروج</button>
      </div>
      <div id="ml-eg-${esc(l.key)}" style="font-size:10.5px;color:var(--t3);margin-top:6px;display:none"></div>
    </div>`;
  }).join('')||'<div style="font-size:11.5px;color:var(--t3);padding:8px">هنوز اسکنی ثبت نشده — دکمه‌ی اسکن را بزن</div>';
  if(stats){document.getElementById('ml-scan-stats').innerHTML=`پروب: ${toFa(stats.probed)} · سالم: ${toFa(stats.alive)} · coloهای یکتا: ${toFa(stats.colos)} · مرده: ${toFa(stats.dead)} — <b>RTT از دید سرور پنل</b> (از ISP خودت با /cdn-cgi/trace روی همان IP قابل بازبینی است)`;}
}
async function mlEgress(key,btn){
  const box=document.getElementById('ml-eg-'+key);if(!box)return;
  const old=btn.innerHTML;btn.disabled=true;btn.innerHTML='...';
  try{
    const r=await authF('/api/multiloc/egress-check?ip='+encodeURIComponent(key==='auto'?'auto':key));
    const j=await r.json();
    box.style.display='block';
    if(j.ok){
      // فقط IP اندازه‌گیری‌شده نمایش داده می‌شود — هرگز IP تنظیم‌شده/پین‌شده
      box.innerHTML=`${egBadge('VERIFIED_EGRESS')} <b style="color:var(--green-t)">IP خروج (اندازه‌گیری‌شده): ${esc(j.exit_ip||'?')}</b> · ${esc(j.exit_country||j.colo_country||'?')} ${j.exit_city?('— '+esc(j.exit_city)):''} ${j.exit_asn?('<span dir="ltr">· '+esc(j.exit_asn)+'</span>'):''} <span style="opacity:.6">(${esc(j.colo||'?')})</span>`;
      document.getElementById('ml-egress-last').textContent=(j.exit_country||'?')+' · '+(j.exit_ip||'?');
      document.getElementById('ml-egress-sub').textContent=(j.measurement_source||j.note?('مدرک زنده از /egress-test'):'مدرک زنده از /egress-test');
    } else {
      box.innerHTML='<b style="color:var(--amber-t)">'+esc(j.error||'تست ناموفق — وورکر v2 لازم است')+'</b>';
    }
  }catch(e){box.style.display='block';box.innerHTML='<b style="color:var(--red-t)">خطا</b>';}
  finally{btn.disabled=false;btn.innerHTML=old;}
}
function mlFillCfgSelect(){
  const sel=document.getElementById('ml-cfg-sel');if(!sel)return;
  const cands=allLinksList.filter(l=>!l._nodeId&&(((l.protocol||'').startsWith('vless'))||((l.protocol||'').startsWith('trojan'))));
  const list=cands.length?cands:allLinksList.filter(l=>!l._nodeId);
  sel.innerHTML='<option value="">همه‌ی کانفیگ‌های مجاز ('+toFa(list.length)+')</option>'+list.map(l=>`<option value="${esc(l.uuid)}">${esc(l.label)} · ${esc((l.protocol||'').toUpperCase())}</option>`).join('');
}
async function mlBuild(btn){
  const uuid=document.getElementById('ml-cfg-sel').value||null;
  const mode=document.getElementById('ml-mode-sel').value;
  const coloSel=document.getElementById('ml-colo-sel').value;
  const colos=coloSel==='auto'?['auto']:null;
  const old=btn.innerHTML;btn.disabled=true;btn.innerHTML='<i class="ti ti-loader ti-spin"></i> در حال ساخت...';
  try{
    const r=await authF('/api/multiloc/links',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uuid,mode,colos})});
    if(!r.ok)throw new Error((await r.json().catch(()=>({}))).error||('HTTP '+r.status));
    const j=await r.json();
    if(!j.ok){toast(j.error||'ساخت ناموفق','err');return}
    mlLinksCache=j.links;
    const grid=document.getElementById('ml-links-grid');
    grid.innerHTML=j.links.map((l,i)=>`
      <div class="card" style="margin:0;padding:12px;border:1px solid var(--card-b)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <b style="font-size:12.5px">${l.flag} ${esc(l.city)} ${l.colo?('· <span style="font-size:10px;opacity:.7">'+esc(l.colo)+'</span>'):''}</b>
          <span class="badge ${l.exit.includes('Cloudflare')?'bg-green':'bg-blue'}" style="font-size:9.5px">${esc(l.exit)}</span>
        </div>
        <div style="font-size:10px;color:var(--t3);margin-bottom:6px">${esc(l.label)} · ${esc((l.protocol||'').toUpperCase())} ${l.rtt_ms?('· '+toFa(Math.round(l.rtt_ms))+'ms'):''}</div>
        <div style="display:flex;gap:6px">
          <button class="btn btn-g btn-sm" style="font-size:10px;padding:4px 10px;flex:1" onclick="mlCopyOne(${i},this)"><i class="ti ti-clipboard-copy"></i> کپی لینک</button>
          <button class="btn btn-o btn-sm" style="font-size:10px;padding:4px 8px" onclick="navigator.clipboard.writeText('https://${esc(location.host)}/sub/'+encodeURIComponent('${esc(j.links[i].uuid)}'))" title="کپی لینک ساب"><i class="ti ti-rss"></i></button>
        </div>
      </div>`).join('');
    document.getElementById('ml-copy-all-btn').style.display='';
    document.getElementById('ml-links-raw').style.display='';
    document.getElementById('ml-links-raw').value=j.links.map(l=>l.url).join('\n');
    document.getElementById('ml-build-result').textContent=toFa(j.count)+' کانفیگ پل ساخته شد ✓'+(j.auto_sync?(' · '+j.auto_sync):'');
    toast(toFa(j.count)+' کانفیگ '+j.mode_label+' ساخته شد ✓','ok');
  }catch(e){toast('ساخت ناموفق: '+(e.message||''),'err');}
  finally{btn.disabled=false;btn.innerHTML=old;}
}
function mlCopyOne(i,btn){ navigator.clipboard.writeText(mlLinksCache[i].url).then(()=>toast('لینک '+mlLinksCache[i].city+' کپی شد ✓','ok')).catch(()=>toast('کپی ناموفق','err')); }
function mlCopyAll(){ navigator.clipboard.writeText(mlLinksCache.map(l=>l.url).join('\n')).then(()=>toast('همه‌ی '+toFa(mlLinksCache.length)+' لینک کپی شد ✓','ok')).catch(()=>toast('کپی ناموفق','err')); }
async function mlSyncWorker(btn){
  const res=document.getElementById('ml-sync-result');const old=btn.innerHTML;btn.disabled=true;res.textContent='در حال سینک...';
  try{
    const r=await authF('/api/multiloc/sync-worker',{method:'POST'});
    const j=await r.json();
    if(j.ok){res.innerHTML=`<b style="color:var(--green-t)">✓ ${toFa(j.pushed||j.synced||0)} UUID سینک شد${j.pools?(' · '+toFa(Object.keys(j.pools||{}).length)+' استخر IP'):''}</b>`;toast('سینک وورکر کامل شد ✓','ok');}
    else{res.innerHTML='<b style="color:var(--amber-t)">'+esc(j.error||'سینک ناموفق')+'</b>';}
  }catch(e){res.innerHTML='<b style="color:var(--red-t)">خطا</b>';}
  finally{btn.disabled=false;btn.innerHTML=old;}
}
async function mlCopyWorkerCode(){
  try{
    const r=await authF('/api/multiloc/worker-code');
    if(!r.ok)throw new Error('HTTP '+r.status);
    const code=await r.text();
    await navigator.clipboard.writeText(code);
    toast('کد کامل Worker v2 کپی شد — در Edit Code وورکر Paste کن و Deploy کن ✓','ok');
  }catch(e){toast('کپی ناموفق — از لینک دانلود استفاده کن','err');}
}
async function mlSniTrace(btn){
  const inp=document.getElementById('ml-sni-input');
  const sni=(inp.value||'').trim();
  const box=document.getElementById('ml-sni-result');
  if(!sni||!sni.includes('.')){toast('یک دامنه‌ی معتبر وارد کنید','err');return}
  const old=btn.innerHTML;btn.disabled=true;btn.innerHTML='<i class="ti ti-loader ti-spin"></i> تست زنده...';
  try{
    const r=await authF('/api/multiloc/sni-trace',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sni})});
    const j=await r.json();
    box.style.display='block';
    let h='<div style="padding:12px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);font-size:11.5px;line-height:2">';
    h+=`<b>دامنه‌ی جعلی: <code style="direction:ltr;display:inline-block">${esc(j.spoof_sni||sni)}</code></b><br>`;
    const t=j.tests||{};
    if(t.panel_control)h+=`کنترل (SNI واقعی پنل): ${t.panel_control.tls_ok?'<b style="color:var(--green-t)">هندشیک ✓</b>':'<b style="color:var(--red-t)">✗</b>'} ${t.panel_control.http?('· '+esc(t.panel_control.http)):'<br>'}<br>`;
    if(t.railway_fake_sni)h+=`جعل مستقیم به ریلوی (SNI=${esc(j.spoof_sni)}): ${t.railway_fake_sni.tls_ok&&t.railway_fake_sni.http&&String(t.railway_fake_sni.http).includes('200')?'<b style="color:var(--green-t)">هندشیک + HTTP 200 ✓</b>':'<b style="color:var(--red-t)">ناموفق</b>'} ${t.railway_fake_sni.error?('· '+esc(t.railway_fake_sni.error)):'<br>'}<br>`;
    if(t.cloudflare_fake_sni)h+=`جعل به لبه‌ی کلادفلر: ${t.cloudflare_fake_sni.tls_ok&&String(t.cloudflare_fake_sni.http||'').includes('200')?'<b style="color:var(--green-t)">قابل fronting ✓</b>':'<b style="color:var(--amber-t)"> rout نمی‌شود (طبیعی)</b>'}<br>`;
    (j.verdicts||[]).forEach(v=>{h+=`<div style="margin-top:8px;padding:8px;border-radius:8px;background:${v.ok?'rgba(16,185,129,.08)':'rgba(250,204,21,.08)'}"><b style="color:${v.ok?'var(--green-t)':'var(--amber-t)'}">${v.ok?'✓':'⚠'} ${esc(v.mode)}</b> — ${esc(v.msg)}</div>`;});
    h+='</div>';
    box.innerHTML=h;
  }catch(e){box.style.display='block';box.innerHTML='<b style="color:var(--red-t)">خطا در تست</b>';}
  finally{btn.disabled=false;btn.innerHTML=old;}
}
async function loadGamingPage(){
  try{
    const r=await authF('/api/gaming/config');
    if(!r.ok){toast('خطا در بارگذاری مرکز گیمینگ','err');return}
    gamingCfg=await r.json();
    const sb=document.getElementById('gaming-status-badge');
    sb.textContent=gamingCfg.ready?'آماده':'نیاز به تنظیم';
    sb.className='badge '+(gamingCfg.ready?'bg-green':'bg-amber');
    document.getElementById('gaming-worker-domain').value=gamingCfg.worker_domain||'';
    document.getElementById('gaming-vps-ip').value=gamingCfg.vps_ip||'';
    document.getElementById('gaming-vps-port').value=gamingCfg.vps_port||443;
    document.getElementById('gaming-worker-status').textContent=gamingCfg.ready?'فعال':'تنظیم نشده';
    document.getElementById('gaming-worker-domain-label').textContent=gamingCfg.worker_domain||'—';
    document.getElementById('gaming-best-ip').textContent=gamingCfg.best_ip||'—';
    document.getElementById('gaming-best-ms').textContent=gamingCfg.best_ip_ms?('تأخیر: '+toFa(Math.round(gamingCfg.best_ip_ms))+' ms'):(gamingCfg.last_scan_ts?('اسکن قدیمی — دوباره اسکن کن'):'هنوز اسکن نشده');
    // حالت ضد ضریب + ترنسپورت از config
    const am=document.getElementById('gaming-anti-mode');
    if(am&&gamingCfg.anti_dpi_mode)am.value=gamingCfg.anti_dpi_mode;
    const tr=document.getElementById('gaming-transport');
    if(tr&&gamingCfg.transport)tr.value=gamingCfg.transport;
    gamingUpdateAntiDesc();
    if(am)am.onchange=()=>{gamingUpdateAntiDesc();gamingSavePrefs()};
    if(tr)tr.onchange=()=>{gamingSavePrefs()};
    gamingRenderPresets();
    gamingRenderLocTemplates();
    if(gamingCfg.ready){gamingRefreshLocations(true,false);gamingLoadInbounds(null)}
    loadEgressSummary();
    if(gamingCfg.best_ip){document.getElementById('gaming-override-ip').value=gamingCfg.best_ip}
  }catch(e){console.error('loadGamingPage',e);toast('خطا در بارگذاری مرکز گیمینگ','err')}
}
/* ══════════════════════════════════════════════════════════════════════════
   PHASE 38 — مسیریابی هوشمند (pg-routing) + حساب‌ها (pg-accounts)
   همه‌ی ادعاها از API واقعی می‌آیند؛ هیچ چیز hardcode نیست.
   ══════════════════════════════════════════════════════════════════════════ */
let rtPolicy='ALL_VPN';
async function loadRoutingPage(){
  try{
    const [pol, st] = await Promise.all([
      authF('/api/domestic/policy').then(r=>r.ok?r.json():null),
      authF('/api/domestic/status').then(r=>r.ok?r.json():null)
    ]);
    if(pol){
      rtPolicy=pol.active_policy;
      routingRenderMode();
      const d=document.getElementById('rt-mode-detail');
      if(d){
        const iran = pol.active_policy==='IRAN_DIRECT';
        d.innerHTML = iran
          ? '<b style="color:#F97316">🇮🇷 مقصدهای ایرانی:</b> DIRECT از ISP خود کاربر (خروج: USER_ISP — VPN دور زده می‌شود)<br><b style="color:#38BDF8">🌍 مقصدهای بین‌المللی:</b> VPN از نود خروج EMIX انتخاب‌شده<br><b style="color:var(--t3)">مجهول:</b> طبق سیاست پیش‌فرض (VPN)'
          : '<b style="color:#38BDF8">🌍 همه‌ی ترافیک:</b> از تونل EMIX عبور می‌کند (داخلی و بین‌المللی)<br><b style="color:var(--t3)">حالت «مستقیم ایرانی» برای عبور ترافیک داخلی از ISP خودتان در دسترس است.</b>';
        if(pol.dns&&pol.dns.recommended){d.innerHTML+='<div style="font-size:11px;color:var(--t3);margin-top:6px">DNS توصیه‌شده: '+esc(pol.dns.recommended)+'</div>'}
      }
    }
    if(st){
      const ds=st.dataset||{};
      document.getElementById('rt-prefix-count').textContent=toFa(ds.prefix_count||0);
      document.getElementById('rt-dataset-body').innerHTML=
        '<div>پیشوندها: <b>'+toFa(ds.prefix_count||0)+'</b> (IPv4+IPv6)</div>'+
        '<div>منبع: <b style="direction:ltr;display:inline-block">'+esc(ds.source_name||ds.source||'—')+'</b></div>'+
        '<div>نسخه: <b>'+(ds.version?toFa(new Date(ds.version*1000).toLocaleDateString('fa-IR')):'—')+'</b></div>'+
        '<div>آخرین دریافت: <b>'+(ds.fetched_at?toFa(new Date(ds.fetched_at*1000).toLocaleString('fa-IR')):'—')+'</b></div>'+
        '<div>checksum: <b style="font-family:monospace;font-size:10px;direction:ltr;display:inline-block">'+esc((ds.checksum||'—').slice(0,16))+'…</b></div>'+
        '<div>اعتماد: <b>'+esc(ds.confidence||'UNKNOWN')+'</b></div>';
      const ta=st.traffic_accounting||{};
      document.getElementById('rt-traffic-body').innerHTML=
        '<div>🇮🇷 DOMESTIC_DIRECT: <b>'+fmtB(ta.DOMESTIC_DIRECT?tva(ta.DOMESTIC_DIRECT):0)+'</b> · '+toFa((ta.DOMESTIC_DIRECT&&ta.DOMESTIC_DIRECT.connections)||0)+' اتصال</div>'+
        '<div>🌍 INTERNATIONAL_VPN: <b>'+fmtB(ta.INTERNATIONAL_VPN?tva(ta.INTERNATIONAL_VPN):0)+'</b> · '+toFa((ta.INTERNATIONAL_VPN&&ta.INTERNATIONAL_VPN.connections)||0)+' اتصال</div>'+
        '<div>❓ UNKNOWN: <b>'+fmtB(ta.UNKNOWN?tva(ta.UNKNOWN):0)+'</b></div>';
      const sm=st.split_tunnel_clients||{};
      let rows='';
      for(const [c,v] of Object.entries(sm)){
        rows+='<div>'+esc(c)+': <span class="badge '+(v==='SPLIT_TUNNEL_SUPPORTED'?'bg-green':'bg-amber')+'">'+(v==='SPLIT_TUNNEL_SUPPORTED'?'پشتیبانی می‌شود':'SPLIT_TUNNEL_NOT_SUPPORTED')+'</span></div>';
      }
      document.getElementById('rt-split-body').innerHTML=rows+'<div style="font-size:10.5px;color:var(--t3);margin-top:6px">تنها کلاینت‌هایی که واقعاً قادر به اعمال قواعد مسیر در سطح route هستند پشتیبانی می‌شوند — بقیه صادقانه NOT_SUPPORTED گزارش می‌شوند.</div>';
    }
  }catch(e){netErr(e,'loadRoutingPage')}
  irdLoad();   /* 🇮🇷 IRAN DIRECT builder (IP سالم + هندشیک) — بلاک ایزوله */
}
function tva(row){return (row.bytes_sent||0)+(row.bytes_received||0)}
function routingRenderMode(){
  document.getElementById('rt-mode-allvpn').classList.toggle('sel',rtPolicy==='ALL_VPN');
  document.getElementById('rt-mode-irandirect').classList.toggle('sel',rtPolicy==='IRAN_DIRECT');
  const b=document.getElementById('routing-mode-badge');
  b.textContent=rtPolicy==='IRAN_DIRECT'?'IRAN_DIRECT':'ALL_VPN';
  b.className='badge '+(rtPolicy==='IRAN_DIRECT'?'bg-amber':'bg-blue');
}
async function routingSetMode(mode){
  if(mode!=='ALL_VPN'&&mode!=='IRAN_DIRECT')return;
  try{
    const r=await authF('/api/domestic/policy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({policy:mode})});
    if(!r.ok){const j=await r.json().catch(()=>({}));toast(j.error||('خطا در تغییر حالت'),'err');return}
    rtPolicy=mode;routingRenderMode();loadRoutingPage();
    toast('حالت مسیریابی: '+mode,'ok');
  }catch(e){netErr(e,'routingSetMode')}
}
async function routingTestRoute(){
  const inp=document.getElementById('rt-test-input');
  const dest=(inp.value||'').trim();
  const out=document.getElementById('rt-test-result');
  if(!dest){toast('یک دامنه یا IP وارد کنید','err');return}
  out.style.display='block';out.innerHTML='<div style="font-size:12px;color:var(--t3)">در حال تست مسیر…</div>';
  try{
    const r=await authF('/api/domestic/test-route',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({destination:dest})});
    if(!r.ok){out.innerHTML='<div class="badge bg-red">خطا در تست مسیر</div>';return}
    const v=await r.json();
    const clsColor={'IRAN_DOMESTIC':'bg-amber','NON_IRAN':'bg-blue','UNKNOWN':'bg-gray'}[v.classification]||'bg-gray';
    const decColor={'DIRECT':'bg-green','VPN':'bg-blue','BLOCK':'bg-red'}[v.decision]||'bg-gray';
    out.innerHTML=
      '<div style="padding:14px;background:var(--bg);border-radius:12px;border:1px solid var(--card-b);font-size:12px;line-height:2.2">'+
      '<div>مقصد: <b style="direction:ltr;display:inline-block">'+esc(v.destination)+'</b></div>'+
      '<div>IP حل‌شده: <b style="direction:ltr;font-family:monospace">'+esc(v.resolved_ip||'—')+'</b> <span style="color:var(--t3)">('+esc(v.resolved_by||'')+')</span></div>'+
      '<div>طبقه‌بندی: <span class="badge '+clsColor+'">'+esc(v.classification)+'</span>'+(v.matched_prefix?' <span style="font-family:monospace;font-size:10.5px;color:var(--t3);direction:ltr;display:inline-block">'+esc(v.matched_prefix)+'</span>':'')+'</div>'+
      '<div>قاعده اعمال‌شده: <b>'+esc(v.policy_name||'')+'</b> <span style="color:var(--t3);font-size:11px">{iran:'+esc((v.policy||{}).iran)+', intl:'+esc((v.policy||{}).international)+', unknown:'+esc((v.policy||{}).unknown)+'}</span></div>'+
      '<div>تصمیم مسیر: <span class="badge '+decColor+'">'+esc(v.decision)+'</span></div>'+
      '<div>VPN دور زده شد؟ <b>'+(v.vpn_bypassed?'بله (BYPASSED)':'نه (از تونل)')+'</b></div>'+
      '<div>خروج واقعی: <b style="color:'+(v.egress==='USER_ISP'?'#F97316':'#38BDF8')+'">'+esc(v.egress)+'</b> <span style="color:var(--t3);font-size:11px">'+esc(v.egress_note||'')+'</span></div>'+
      (v.domestic_status?'<div>وضعیت داخلی: <b>'+esc(v.domestic_status)+'</b></div>':'')+
      (v.notes&&v.notes.length?('<div style="color:var(--amber-t);font-size:11px">'+v.notes.map(esc).join(' · ')+'</div>'):'')+
      '</div>';
  }catch(e){netErr(e,'routingTestRoute')}
}
async function routingUpdateRules(btn){
  const out=document.getElementById('rt-rules-result');
  if(btn){btn.disabled=true;btn.innerHTML='در حال به‌روزرسانی…'}
  try{
    const r=await authF('/api/domestic/rules/update',{method:'POST'});
    const j=await r.json().catch(()=>({}));
    out.style.display='block';
    if(j.ok){out.innerHTML='<span class="badge bg-green">موفق</span> '+toFa(j.applied||0)+' پیشوند اعمال شد (نسخه '+toFa(j.version||'')+')';loadRoutingPage()}
    else{out.innerHTML='<span class="badge bg-amber">ناموفق</span> '+esc(j.error||'')+' — <b>دیتاست قبلی حفظ شد</b>'}
  }catch(e){netErr(e,'routingUpdateRules')}
  finally{if(btn){btn.disabled=false;btn.innerHTML='<i class="ti ti-cloud-download"></i> به‌روزرسانی اتمی از RIPEstat'}}
}

/* ── حساب‌ها ─────────────────────────────────────────────────────────────── */
async function loadAccountsPage(){
  try{
    const r=await authF('/api/accounts');
    if(!r.ok){toast('خطا در بارگذاری حساب‌ها','err');return}
    const j=await r.json();
    const list=j.accounts||[];
    document.getElementById('accounts-count').textContent=toFa(list.length)+' حساب';
    document.getElementById('accounts-nb').textContent=toFa(list.length);
    const wrap=document.getElementById('ac-list');const empty=document.getElementById('ac-empty');
    if(!list.length){wrap.innerHTML='';empty.style.display='block';return}
    empty.style.display='none';
    wrap.innerHTML=list.map(a=>accountsRenderCard(a)).join('');
    list.forEach(a=>accountLoadDetail(a.id));
  }catch(e){netErr(e,'loadAccountsPage')}
}
function accountsRenderCard(a){
  const statusChip=a.status==='ACTIVE'?'<span class="ac-status-chip" style="background:rgba(74,222,128,.15);color:#4ADE80">ACTIVE</span>':'<span class="ac-status-chip" style="background:rgba(239,68,68,.15);color:#F87171">DISABLED</span>';
  const quota=a.traffic_quota_bytes
    ?'<div>مصرف: <b>'+fmtB(a.used_bytes)+'</b> از '+fmtB(a.traffic_quota_bytes)+(a.quota_used_pct!=null?' ('+toFa(a.quota_used_pct)+'٪)':'')+(a.over_quota?' <span class="badge bg-red">QUOTA_EXCEEDED</span>':'')+'</div>'
    :'<div>مصرف: <b>'+fmtB(a.used_bytes)+'</b> (نامحدود)</div>';
  const expiry=a.expires_at_iso?'<div>انقضا: <b>'+toFa(a.expires_at_iso)+'</b>'+(a.expired?' <span class="badge bg-red">EXPIRED</span>':'')+'</div>':'<div>انقضا: بی‌نهایت</div>';
  return '<div class="ac-card" id="ac-'+esc(a.id)+'">'+
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'+
      '<div style="font-weight:800;font-size:14px"><i class="ti ti-user"></i> '+esc(a.username)+'</div>'+statusChip+
    '</div>'+
    '<div style="font-size:12px;line-height:2;color:var(--t2)">'+
      '<div style="font-family:monospace;font-size:10px;color:var(--t3);direction:ltr">'+esc(a.id)+'</div>'+
      quota+expiry+
      '<div>سقف دستگاه: <b>'+toFa(a.max_devices)+'</b> · سقف سشن: <b>'+toFa(a.max_concurrent_sessions)+'</b></div>'+
    '</div>'+
    '<div id="ac-dev-'+esc(a.id)+'" style="margin-top:10px"><div style="font-size:11px;color:var(--t3)">در حال بارگذاری دستگاه‌ها…</div></div>'+
    '<div id="ac-sub-'+esc(a.id)+'" style="margin-top:8px"></div>'+
    '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:12px">'+
      (a.status==='ACTIVE'
        ?'<button class="btn btn-o btn-sm" onclick="accountSetStatus(\''+a.id+'\',\'DISABLED\')"><i class="ti ti-ban"></i> غیرفعال</button>'
        :'<button class="btn btn-o btn-sm" onclick="accountSetStatus(\''+a.id+'\',\'ACTIVE\')"><i class="ti ti-check"></i> فعال</button>')+
      '<button class="btn btn-blue btn-sm" onclick="accountAddDevice(\''+a.id+'\')"><i class="ti ti-device-mobile-plus"></i> دستگاه جدید</button>'+
      '<button class="btn btn-g btn-sm" onclick="accountAddSub(\''+a.id+'\')"><i class="ti ti-rss"></i> اشتراک جدید</button>'+
    '</div></div>';
}
async function accountsCreate(){
  const u=document.getElementById('ac-username').value.trim();
  const p=document.getElementById('ac-password').value;
  const q=parseFloat(document.getElementById('ac-quota').value)||null;
  const e=parseFloat(document.getElementById('ac-expiry').value)||null;
  const md=parseInt(document.getElementById('ac-maxdev').value)||5;
  const ms=parseInt(document.getElementById('ac-maxses').value)||3;
  if(!u||!p||p.length<8){toast('نام کاربری و رمز (حداقل ۸ کاراکتر) الزامی است','err');return}
  try{
    const r=await authF('/api/accounts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p,traffic_quota_gb:q,expires_in_days:e,max_devices:md,max_concurrent_sessions:ms})});
    if(!r.ok){const j=await r.json().catch(()=>({}));toast(j.error||'خطا در ایجاد حساب','err');return}
    toast('حساب ساخته شد','ok');
    document.getElementById('ac-username').value='';document.getElementById('ac-password').value='';
    loadAccountsPage();
  }catch(err){netErr(err,'accountsCreate')}
}
async function accountSetStatus(id,status){
  try{
    const r=await authF('/api/accounts/'+id+'/status?status='+status,{method:'POST'});
    if(!r.ok){toast('خطا در تغییر وضعیت','err');return}
    toast('وضعیت: '+status,'ok');loadAccountsPage();
  }catch(e){netErr(e,'accountSetStatus')}
}
async function accountAddDevice(id){
  const name=prompt('نام دستگاه:','my-phone');if(name===null)return;
  const platform=prompt('پلتفرم (android/ios/windows/…):','android')||'unknown';
  try{
    const r=await authF('/api/accounts/'+id+'/devices',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,platform})});
    const j=await r.json().catch(()=>({}));
    if(!r.ok){toast(j.error||'خطا در ثبت دستگاه','err');return}
    if(j.access_token){
      const box=document.getElementById('ac-dev-'+id);
      box.insertAdjacentHTML('afterbegin','<div style="padding:10px;border:1px dashed var(--accent);border-radius:10px;margin-bottom:8px;font-size:12px"><b>توکن دستگاه (فقط همین یک‌بار نمایش داده می‌شود):</b><div style="font-family:monospace;direction:ltr;margin-top:6px;user-select:all">'+esc(j.access_token)+'</div><div style="font-size:10.5px;color:var(--t3);margin-top:4px">این توکن در لاگ‌ها ذخیره نمی‌شود — الان کپی کنید.</div></div>');
    }
    toast('دستگاه ثبت شد','ok');
  }catch(e){netErr(e,'accountAddDevice')}
}
async function deviceRevoke(id,accId){
  if(!confirm('این دستگاه باطل (revoke) شود؟'))return;
  try{
    const r=await authF('/api/devices/'+id+'/revoke',{method:'POST'});
    if(!r.ok){toast('خطا در ابطال دستگاه','err');return}
    toast('دستگاه باطل شد','ok');accountLoadDetail(accId);
  }catch(e){netErr(e,'deviceRevoke')}
}
async function accountAddSub(id){
  const days=parseFloat(prompt('مدت اشتراک (روز — خالی = بی‌نهایت):','30'));if(days===null&&days!==null)0;
  const routePolicy=confirm('سیاست مسیر: IRAN_DIRECT؟\n(OK = ایرانی مستقیم · Cancel = ALL_VPN)')?'IRAN_DIRECT':'ALL_VPN';
  try{
    const r=await authF('/api/accounts/'+id+'/subscriptions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expires_in_days:isNaN(days)?null:days,route_policy:routePolicy})});
    const j=await r.json().catch(()=>({}));
    if(!r.ok){toast(j.error||'خطا در ایجاد اشتراک','err');return}
    toast('اشتراک ساخته شد','ok');accountLoadDetail(id);
  }catch(e){netErr(e,'accountAddSub')}
}
async function accountLoadDetail(id){
  try{
    const r=await authF('/api/accounts/'+id);
    if(!r.ok)return;
    const a=await r.json();
    const devBox=document.getElementById('ac-dev-'+id);
    if(devBox&&a.devices){
      devBox.innerHTML='<div style="font-size:12px;font-weight:700;margin-bottom:6px"><i class="ti ti-devices"></i> دستگاه‌ها ('+toFa(a.devices.length)+')</div>'+
        (a.devices.length?a.devices.map(d=>
          '<div class="ac-dev-row">'+
          '<i class="ti ti-device-mobile" style="color:'+(d.revoked?'var(--t3)':'#38BDF8')+'"></i>'+
          '<b>'+esc(d.name)+'</b><span style="color:var(--t3);font-size:10.5px">'+esc(d.platform)+'</span>'+
          '<span style="flex:1"></span>'+
          (d.revoked?'<span class="badge bg-red">REVOKED</span>':(d.connection_state==='CONNECTED'?'<span class="badge bg-green">CONNECTED</span>':'<span style="font-size:10.5px;color:var(--t3)">'+(d.last_seen_iso?('آخرین اتصال: '+toFa(d.last_seen_iso)):'بدون اتصال')+'</span>'))+
          (d.revoked?'':'<button class="btn btn-o btn-sm" style="padding:2px 8px" onclick="deviceRevoke(\''+d.device_id+'\',\''+id+'\')"><i class="ti ti-ban"></i></button>')+
          '</div>').join(''):'<div style="font-size:11px;color:var(--t3)">بدون دستگاه</div>');
    }
    const subBox=document.getElementById('ac-sub-'+id);
    if(subBox&&a.subscriptions){
      subBox.innerHTML='<div style="font-size:12px;font-weight:700;margin-bottom:6px"><i class="ti ti-rss"></i> اشتراک‌ها ('+toFa(a.subscriptions.length)+')</div>'+
        (a.subscriptions.length?a.subscriptions.map(s=>{
          const c={'ACTIVE':'bg-green','EXPIRED':'bg-amber','REVOKED':'bg-red','SUSPENDED':'bg-amber','DRAINING':'bg-blue'}[s.status]||'bg-gray';
          return '<div class="ac-dev-row" style="font-size:11px"><span class="badge '+c+'">'+esc(s.status)+'</span>'+
          '<span style="font-family:monospace;direction:ltr;font-size:10px">'+esc(s.subscription_id)+'</span>'+
          '<span style="flex:1"></span><span style="color:var(--t3)">'+esc(s.route_policy)+' · '+esc(s.protocol)+'</span>'+
          (s.expires_at_iso?('<span style="color:var(--t3)">تا '+toFa(s.expires_at_iso)+'</span>'):'')+'</div>';
        }).join(''):'<div style="font-size:11px;color:var(--t3)">بدون اشتراک</div>');
    }
  }catch(e){netErr(e,'accountLoadDetail')}
}

/* توضیح داینامیک حالت ضد ضریب */
function gamingUpdateAntiDesc(){
  const box=document.getElementById('gaming-anti-desc');
  if(!box)return;
  const modes=gamingCfg.anti_dpi_modes||{};
  const m=modes[document.getElementById('gaming-anti-mode').value]||modes.balanced||{};
  const trans=(gamingCfg.transport_options||{})[document.getElementById('gaming-transport').value]||{};
  box.innerHTML='<b>'+m.label+'</b> — '+(m.desc||'')+'<br><b>'+ (trans.label||'') +'</b> — '+(trans.desc||'');
}
async function gamingSavePrefs(){
  try{
    const body={anti_dpi_mode:document.getElementById('gaming-anti-mode').value,
      transport:document.getElementById('gaming-transport').value};
    await authF('/api/gaming/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  }catch(e){/* بی‌صدا */}
}
/* ─── قالب‌های لوکیشن رایگان ─── */
function gamingRenderLocTemplates(){
  const grid=document.getElementById('gaming-loc-templates');
  if(!grid)return;
  const tpls=gamingCfg.location_templates||{};
  const keys=Object.keys(tpls);
  if(!keys.length){grid.innerHTML='';return}
  grid.innerHTML=keys.map(k=>{
    const t=tpls[k];
    const isWiz=!!t.wizard;
    return `<div style="padding:12px;background:var(--bg);border-radius:12px;border:1px solid ${isWiz?'var(--green-t)':'var(--card-b)'}">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <span style="font-size:18px">${t.flag||'📍'}</span>
        <div style="flex:1;font-weight:700;font-size:11.5px;line-height:1.5">${t.label}</div>
      </div>
      <div style="font-size:10.5px;color:var(--t2);line-height:1.7;margin-bottom:8px">${t.region_hint||''} · <b>${t.best_for||''}</b></div>
      <div style="font-size:10px;color:var(--green-t);margin-bottom:8px"><i class="ti ti-gift"></i> ${t.free||''}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        ${isWiz?`<button class="btn btn-sm btn-blue" onclick="gamingExitWizard(null)"><i class="ti ti-package-export"></i> بسته بساز</button>`:''}
        <button class="btn btn-sm btn-g" onclick="gamingUseLocTemplate('${k}')"><i class="ti ti-forms"></i> پرکردن فرم</button>
        <button class="btn btn-sm" onclick="gamingShowTplSteps('${k}',this)"><i class="ti ti-list-check"></i> راهنما</button>
      </div>
      <div class="gaming-tpl-steps" style="display:none;margin-top:10px;font-size:10.5px;color:var(--t3);line-height:2">
        <ol style="margin:0;padding-right:16px;list-style:persian">${(t.steps||[]).map(s=>`<li>${s}</li>`).join('')}</ol>
      </div>
    </div>`}).join('');
}
function gamingShowTplSteps(key,btn){
  const card=btn.closest('div[class]');
  const box=btn.parentElement.parentElement.querySelector('.gaming-tpl-steps');
  if(box){box.style.display=box.style.display==='none'?'':'none'}
}
function gamingUseLocTemplate(key){
  const t=(gamingCfg.location_templates||{})[key];
  if(!t){toast('قالب پیدا نشد','err');return}
  const set=(id,v)=>{const el=document.getElementById(id);if(el)el.value=v};
  set('gaming-loc-name',t.code||key);
  set('gaming-loc-label',(t.label||'').replace(/^[^\s—]+\s—\s/,''));
  set('gaming-loc-flag',t.flag&&t.flag.length<=4?t.flag:'📍');
  if(t.wizard){document.getElementById('gaming-loc-upstream').value='';document.getElementById('gaming-loc-upstream').placeholder='بعد از deploy بسته، دامنه‌ی xxx.up.railway.app را اینجا بگذار';}
  toast('قالب «'+t.label+'» در فرم پر شد — بعد از deploy فقط دامنه را اضافه کن','ok');
  document.getElementById('gaming-loc-name').scrollIntoView({behavior:'smooth',block:'center'});
}
function gamingRenderPresets(){
  const grid=document.getElementById('gaming-presets-grid');
  if(!grid)return;
  const p=gamingCfg.presets||{};
  grid.innerHTML=Object.entries(p).map(([k,g])=>`
    <div style="padding:14px;background:var(--bg);border-radius:12px;border:1px solid var(--card-b)">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <span style="font-size:20px">${g.icon}</span>
        <div><div style="font-weight:700;font-size:12.5px">${g.label}</div>
        <div style="font-size:10.5px;color:var(--t3)">${(g.server_regions||[]).join(' · ')}</div></div>
      </div>
      <div style="font-size:11px;color:var(--t2);line-height:1.7;margin-bottom:8px">${g.why}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
        <span class="badge bg-blue" style="font-size:10px">${g.est_ping_direct}</span>
        <span class="badge bg-purple" style="font-size:10px">پیشنهاد: ${g.best_location==='tr'?'ترکیه 🇹🇷':'auto 🌍'}</span>
      </div>
      <ul style="margin:0;padding-right:16px;font-size:10.5px;color:var(--t3);list-style:disc;line-height:1.8">${(g.tips||[]).map(t=>`<li>${t}</li>`).join('')}</ul>
    </div>`).join('');
}
async function gamingSaveConfig(){
  try{
    const body={worker_domain:document.getElementById('gaming-worker-domain').value.trim(),
      vps_ip:document.getElementById('gaming-vps-ip').value.trim(),
      vps_port:parseInt(document.getElementById('gaming-vps-port').value)||443,
      anti_dpi_mode:document.getElementById('gaming-anti-mode').value,
      transport:document.getElementById('gaming-transport').value};
    const tok=document.getElementById('gaming-worker-token').value.trim();
    if(tok)body.worker_token=tok;
    const r=await authF('/api/gaming/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok){toast('ذخیره ناموفق','err');return}
    const j=await r.json();
    if(j.ok){toast('تنظیمات گیمینگ ذخیره شد','ok');loadGamingPage()}else{toast(j.error||'خطا','err')}
  }catch(e){toast('خطا','err')}
}
async function gamingCheckWorker(){
  try{
    const r=await authF('/api/gaming/status');
    if(!r.ok){toast('خطا در تست گیت‌وی','err');return}
    const j=await r.json();
    const box=document.getElementById('gaming-worker-result');
    box.style.display='';
    if(!j.ok){
      document.getElementById('gaming-colo').textContent='—';
      box.innerHTML='<span style="color:var(--red-t)">✗</span> '+(j.error||'گیت‌وی در دسترس نیست');
      document.getElementById('gaming-worker-status').textContent='خطا';
      return;
    }
    document.getElementById('gaming-worker-status').textContent='سالم ✓';
    const locs=j.locations||[];
    document.getElementById('gaming-loc-count').textContent=toFa(locs.length)+' لوکیشن';
    document.getElementById('gaming-loc-list').textContent=locs.map(l=>(l.flag||'')+' '+l.name).join('، ')||'—';
    gamingFillLocSelect(locs);
    // PoP از دید خود مرورگر کاربر (کال مستقیم به worker — CORS باز است)
    let browserPop='—',browserCity='';
    try{
      const wd=(document.getElementById('gaming-worker-domain').value||'').trim();
      if(wd){
        const br=await fetch('https://'+wd+'/gateway-status',{cache:'no-store'});
        if(br.ok){const bj=await br.json();
          browserPop=COLO_NAMES[bj.colo]||bj.colo||'—';browserCity=bj.city||'';}
      }
    }catch(e){browserPop='نامشخص'}
    document.getElementById('gaming-colo').textContent=browserPop;
    document.getElementById('gaming-colo-city').textContent='شهر: '+(browserCity||'—');
    box.innerHTML='<span style="color:var(--green-t)">✓ گیت‌وی سالم</span> — نسخه <b dir="ltr">'+(j.version||'?')+'</b><br>'+
      'PoP مرورگر شما: <b>'+browserPop+'</b>'+(browserCity?' ('+browserCity+')':'')+'<br>'+
      'KV متصل: '+(j.kv_bound?'<span style="color:var(--green-t)">بله</span>':'<span style="color:var(--amber-t)">خیر — لوکیشن داینامیک غیرفعال</span>')+
      ' · توکن: '+(j.token_set?'<span style="color:var(--green-t)">ست شده</span>':'<span style="color:var(--amber-t)">ست نشده</span>')+'<br>'+
      'لوکیشن‌ها: '+locs.map(l=>`<span class="badge bg-blue" style="font-size:10px;margin:2px">${l.flag||''} ${l.name}</span>`).join(' ');
    toast('گیت‌وی تست شد','ok');
  }catch(e){toast('خطا','err')}
}
/* ══════ حقیقت مسیر و خروج — CONTROL PLANE / EXIT NODE / REAL EGRESS ══════ */
const EG_CLASS_FA={VERIFIED_EGRESS:['bg-green','خروج تأییدشده (اندازه‌گیری واقعی)'],
                   CONFIGURED_ONLY:['bg-amber','فقط تنظیم‌شده — بدون اندازه‌گیری'],
                   UNKNOWN:['bg-blue','نامشخص — تأیید نشده']};
function egBadge(cls){const b=EG_CLASS_FA[cls]||EG_CLASS_FA.UNKNOWN;return `<span class="badge ${b[0]}" style="font-size:10px">${b[1]}</span>`}
const LAT_FA={control_plane_rtt:'RTT کنترل‌پلین (مرورگر→پنل)',node_rtt:'RTT نود (پنل→وورکر/نود)',
              route_rtt:'RTT مسیر (وورکر→upstream→IP-check)',protocol_handshake_rtt:'RTT هندشیک پروتکل'};
async function loadEgressSummary(){
  try{
    const r=await authF('/api/egress/summary');
    if(!r.ok)return;
    const j=await r.json();
    if(!j.ok)return;
    const cp=(j.control_plane||{}),pe=(cp.egress||{}),ev=(pe.egress||{});
    const h=document.getElementById('eg-cp-host');if(h)h.textContent=cp.host||'—';
    const en=document.getElementById('eg-exit-node');
    if(en){
      const exits=j.exit_nodes||[];
      en.textContent=exits.length?(exits[0].label||exits[0].name)+' (+ '+toFa(exits.length-1)+' نود دیگر)':'تنظیم نشده';
    }
    const nt=document.getElementById('eg-exit-note');
    if(nt)nt.textContent=(j.exit_nodes_count?('نودهای خروج: '+toFa(j.exit_nodes_count)+' — اتصال از مسیر ریل‌لی'):'بدون نود خروج، ترافیک از همین نود (کنترل‌پلین) خارج می‌شود');
    const ip=document.getElementById('eg-real-ip');
    if(ip)ip.textContent=ev.public_ip||'— (اندازه‌گیری نشده)';
    const sb=document.getElementById('eg-real-sub');
    if(sb)sb.textContent=ev.public_ip?((ev.country||ev.country_code||'?')+' · '+(ev.isp||'?')+' · '+(ev.ip_family||'')+' · منبع: '+(ev.measurement_source||'?')):'فقط با اندازه‌گیری واقعی تأیید می‌شود — نه با مقدار تنظیم‌شده';
    const st=document.getElementById('eg-status-badge');
    if(st){
      const cls=pe.classification||'UNKNOWN';
      st.textContent=cls==='VERIFIED_EGRESS'?'VERIFIED':'DIRECT';
      st.className='badge '+(EG_CLASS_FA[cls]||['bg-blue',''])[0];
    }
    const sn=document.getElementById('eg-status-note');
    if(sn)sn.textContent=cp.note?('کنترل‌پلین: '+cp.host):'';
  }catch(e){console.warn('loadEgressSummary',e)}
}
async function verifyPanelEgress(btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const out=document.getElementById('eg-verify-result');
  try{
    const r=await authF('/api/egress/verify?target=panel');
    const j=await r.json();
    if(j&&j.ok!==undefined&&j.classification){
      const ev=j.egress||{};
      if(out)out.innerHTML=ev.public_ip?('<b dir="ltr" style="font-family:monospace">'+ev.public_ip+'</b> · '+(ev.country||ev.country_code||'?')+' · '+(ev.isp||'?')+' · '+(ev.ip_family||'')+' <span style="color:var(--t3)">('+(ev.measurement_source||'?')+')</span> '+egBadge(j.classification)):(egBadge(j.classification)+(j.error?(' — '+(j.error||'').slice(0,80)):''));
      loadEgressSummary();
      toast('IP خروج پنل اندازه‌گیری شد','ok');
    }
  }catch(e){if(out)out.textContent='خطا در اندازه‌گیری';toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-radar-2';ic.style.animation='';if(btn)btn.disabled=false}}
}
function gamingFillLocSelect(locs){
  const sel=document.getElementById('gaming-location');
  if(!sel)return;
  const cur=sel.value;
  // ✨ حقیقت مسیر: فقط لوکیشن‌هایی که upstream غیر-ریلوی دارند «نود خروج واقعی»‌اند؛
  // بقیه فقط نام مسیر هستند — خروجشان از Railway (کنترل‌پلین) است.
  sel.innerHTML='<option value="auto">🌍 auto — Railway (کنترل‌پلین) — خروج از همین نود</option>'+locs.filter(l=>l.name!=='auto')
    .map(l=>{
      const isRail=(l.upstream||'').includes('railway.app');
      const pend=l.pending||isRail;
      const tag=pend?' ⚠ بدون نود خروج — خروج: Railway (کنترل‌پلین)':' ✓ نود خروج واقعی (تأییدشده)';
      return `<option value="${l.name}">${l.flag||''} ${l.label||l.name}${tag}</option>`;
    }).join('');
  if(cur)sel.value=cur;
}
/* ─── بررسی IP خروج واقعی برای لوکیشن انتخابی — از موتور حقیقت خروج ─── */
const LOC_CC={tr:'TR',de:'DE',nl:'NL',fr:'FR',ae:'AE',ru:'RU',us:'US',uk:'GB',sg:'SG',
              fi:'FI',se:'SE',ch:'CH',at:'AT',es:'ES',it:'IT',pl:'PL',ro:'RO',
              bg:'BG',cz:'CZ',hu:'HU',md:'MD',am:'AM',az:'AZ',kz:'KZ',uz:'UZ'};
async function gamingCheckExitIP(btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const out=document.getElementById('gaming-exit-result');
  if(out){out.style.display='block';out.innerHTML='<span style="color:var(--t3)"><i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> اعتبارسنجی ۹ مرحله‌ای مسیر: رزولو → اتصال → تأیید نود → تأیید مسیر → اندازه‌گیری خروج واقعی → مقایسه...</span>'}
  try{
    const loc=document.getElementById('gaming-location').value||'auto';
    const wd=(document.getElementById('gaming-worker-domain').value||'').trim();
    if(!wd){toast('اول دامنه‌ی وورکر را در تنظیمات گیمینگ وارد کنید','err');return}
    // انتظار کاربر = کشورِ انتخابی (کلید ۲ حرفی لوکیشن) — موتور مقایسه می‌کند:
    // expected != observed → ROUTE_MISMATCH (هرگز HEALTHY دروغ نمی‌زند)
    const expC=(loc!=='auto'&&loc.length===2)?(LOC_CC[loc]||loc.toUpperCase()):null;
    const r=await authF('/api/egress/validate-route',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:loc,expected_country:expC})});
    const j=await r.json();
    if(!out)return;
    renderRouteVerdict(out,j,wd);
    if(j.ok){toast(`IP خروج: ${((j.egress||{}).egress||{}).public_ip||'نامشخص'} (${((j.egress||{}).egress||{}).country_code||'?'})`,'ok')}
    else if(j.route_health==='ROUTE_MISMATCH'){toast('عدم تطابق مسیر: کشور خروج با انتظار فرق دارد','err')}
    else if(j.route_health==='NO_EXIT_NODE_AVAILABLE'){toast('نود خروج واقعی برای این لوکیشن ثبت نشده','err')}
  }catch(e){
    if(out)out.innerHTML=`<div style="color:var(--red-t)"><i class="ti ti-alert-circle"></i> خطا: ${e.message||e}</div>`;
    toast('خطا در اعتبارسنجی مسیر','err');
  }finally{
    if(ic){ic.className='ti ti-world';ic.style.animation='';if(btn)btn.disabled=false}
  }
}
function renderRouteVerdict(out,j,wd){
  const ev=((j.egress||{}).egress)||{};
  const cls=(j.egress||{}).classification||'UNKNOWN';
  const rh=j.route_health||'UNKNOWN';
  const exitStr=ev.public_ip?`<b dir="ltr" style="font-family:monospace;color:var(--accent2)">${ev.public_ip}</b>`:'<span style="color:var(--red-t)">اندازه‌گیری نشد</span>';
  const locStr=[ev.country,ev.city].filter(Boolean).join(' / ')||(ev.country_code||'نامشخص');
  const asnStr=ev.asn||'—';
  const famStr=ev.ip_family||'—';
  const ispStr=ev.isp||'نامشخص';
  const rhBadge=({HEALTHY:'bg-green',ROUTE_MISMATCH:'bg-red',NO_EXIT_NODE_AVAILABLE:'bg-amber',UNREACHABLE:'bg-red',UNKNOWN:'bg-blue'})[rh]||'bg-blue';
  const rhFa=({HEALTHY:'مسیر سالم',ROUTE_MISMATCH:'عدم تطابق مسیر',NO_EXIT_NODE_AVAILABLE:'نود خروج موجود نیست',UNREACHABLE:'مسیر در دسترس نیست',UNKNOWN:'نامشخص'})[rh]||rh;
  const latRows=(j.latencies||[]).map(l=>`<div>⏱ ${LAT_FA[l.measure]||l.measure}: <b>${l.ms!=null?(toFa(Math.round(l.ms))+'ms'):'—'}</b></div>`).join('');
  const cmp=(j.comparison||{});
  const mismatch=(rh==='ROUTE_MISMATCH'&&cmp.reasons)?`<div style="margin-top:10px;padding:10px 12px;background:rgba(251,113,133,0.08);border:1px solid rgba(251,113,133,0.30);border-radius:10px;font-size:11px;line-height:1.7"><b style="color:var(--red-t)">✗ ROUTE_MISMATCH — عدم تطابق مسیر:</b><br>${cmp.reasons.map(x=>'<span dir="ltr">'+esc(String(x))+'</span>').join('<br>')}<br><span style="color:var(--t3)">این مسیر HEALTHY گزارش نمی‌شود تا وقتی مشاهده با انتظار بخورد.</span></div>`:'';
  const noExit=(rh==='NO_EXIT_NODE_AVAILABLE')?`<div style="margin-top:10px;padding:10px 12px;background:rgba(250,204,21,0.08);border:1px solid rgba(250,204,21,0.20);border-radius:10px;font-size:11px;line-height:1.7"><b style="color:var(--amber-t)">⚠ NO_EXIT_NODE_AVAILABLE — نود خروج واقعی ثبت نشده.</b><br>ترافیک از Railway (کنترل‌پلین) خارج می‌شود. برای خروج واقعی از این کشور، upstream این لوکیشن را در وورکر به یک VPS در همان کشور تغییر دهید.<button class="btn btn-sm btn-g" style="margin-top:8px" onclick="gamingShowUpstreamGuide()"><i class="ti ti-book-2"></i> راهنمای تنظیم VPS خروج</button></div>`:'';
  const steps=(j.steps||[]).map(s=>`<div style="display:flex;gap:6px;align-items:center;font-size:10.5px"><i class="ti ${s.ok?'ti-circle-check':'ti-circle-x'}" style="color:${s.ok?'var(--green-t)':'var(--red-t)'}"></i><b style="font-family:monospace;direction:ltr">${s.name}</b><span style="color:var(--t3)">${esc(String(s.detail||'').slice(0,90))}</span></div>`).join('');
  out.innerHTML=`
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px">
      <span class="badge ${rhBadge}" style="font-size:10px">${rhFa}</span>
      ${egBadge(cls)}
      <span style="font-size:11px;color:var(--t3)">لوکیشن: <b>${j.location||'auto'}</b></span>
    </div>
    <div style="font-size:11.5px;line-height:1.9">
      <div>🌐 IP خروج (اندازه‌گیری‌شده): ${exitStr}</div>
      <div>📍 کشور/شهر: <b>${locStr}</b></div>
      <div>🏢 ISP: <span dir="ltr">${ispStr}</span> · ASN: <span dir="ltr">${asnStr}</span> · ${famStr}</div>
      ${latRows}
      <div style="font-size:10px;color:var(--t3);margin-top:6px">مدرک: منبع اندازه‌گیری <code dir="ltr" style="font-size:10px">${ev.measurement_source||'—'}</code>${ev.checked_at?(' · زمان: '+new Date(ev.checked_at*1000).toLocaleTimeString()):''}</div>
    </div>
    ${mismatch}${noExit}
    ${steps?`<details style="margin-top:8px"><summary style="font-size:10.5px;color:var(--t3);cursor:pointer">مراحل اعتبارسنجی (۹ مرحله)</summary><div style="margin-top:6px;padding:8px;background:var(--bg);border-radius:8px">${steps}</div></details>`:''}
  `;
}
function gamingShowUpstreamGuide(){
  const m=document.createElement('div');
  m.className='modal-overlay';
  m.onclick=(e)=>{if(e.target===m)m.remove()};
  m.innerHTML=`
    <div class="modal-box" style="max-width:680px">
      <div class="modal-head">
        <div class="modal-title"><i class="ti ti-server"></i> راهنمای تنظیم VPS خروج واقعی</div>
        <button class="modal-x" onclick="this.closest('.modal-overlay').remove()">✕</button>
      </div>
      <div class="modal-body" style="font-size:12px;line-height:1.9">
        <div style="padding:11px 13px;background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.20);border-radius:12px;margin-bottom:14px">
          <b style="color:var(--accent2)">چرا؟</b> گیت‌وی کلادفلر فقط یک پروکسی است. IP خروج = IP upstream است. اگر upstream Railway باشد، خروج همیشه آمستردام است. برای خروج واقعی از کشور X، باید یک سرور در کشور X داشته باشید.
        </div>
        <b>۱) یک VPS در کشور موردنظر بگیرید:</b><br>
        <ul style="margin:6px 0 14px 18px">
          <li><b>ترکیه</b> — ParsPack, اوبونتو, آوا популярных</li>
          <li><b>دبی</b> — Oracle Cloud Always Free (رایگان، ۴ هسته ARM)</li>
          <li><b>آمستردام/فرانکفورت</b> — Hetzner, Contabo, Vultr</li>
          <li><b>سنگاپور</b> — Vultr, DigitalOcean</li>
        </ul>
        <b>۲) EMIX backend را روی VPS دیپلوی کنید:</b><br>
        <code dir="ltr" style="display:block;background:var(--bg);padding:8px;border-radius:8px;margin:6px 0;font-size:10.5px">git clone https://github.com/EMIXPI/EMIX-PRO.git<br>cd EMIX-PRO<br>pip install -r requirements.txt<br>python -m main</code>
        <b>۳) upstream آن لوکیشن را در وورکر به‌روز کنید:</b><br>
        <code dir="ltr" style="display:block;background:var(--bg);padding:8px;border-radius:8px;margin:6px 0;font-size:10.5px">curl -X POST https://YOUR-WORKER.workers.dev/admin/locations \\
  -H "X-EMIX-Token: YOUR-WORKER-ADMIN-TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"tr","label":"ترکیه — استانبول","flag":"🇹🇷","upstream":"your-vps.example.com","note":"VPS ترک واقعی"}'</code>
        <div style="margin:8px 0 12px;padding:10px 12px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);border-radius:10px;font-size:11px">
          <b style="color:#f59e0b">امنیت:</b> توکن ادمین وورکر را هرگز در پنل یا کد embed نکنید — فقط از Secrets وورکر (wrangler secret) بخوانید و curl را در ترمینال خودتان اجرا کنید.
        </div>
        <b>۴) دوباره «بررسی IP خروج» را بزنید — حالا باید کشور ترکیه را ببینید.</b>
        <div style="margin-top:14px;padding:10px 12px;background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.20);border-radius:10px;font-size:11px">
          <b style="color:var(--green-t)">نکته:</b> اگر فقط می‌خواهید نزدیک‌تر به ایران باشید (نه خروج واقعی)، می‌توانید روی «auto» بگذارید و PoP کلادفلر استانبول کار می‌کند — ولی IP خروج هنوز Railway است.
        </div>
      </div>
    </div>`;
  document.body.appendChild(m);
}

/* ─── اینباندهای گیت‌وی — چند ورودی روی خود وورکر ─── */
async function gamingLoadInbounds(btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const list=document.getElementById('gaming-inbounds-list');
  const sum=document.getElementById('gaming-inbounds-summary');
  try{
    const r=await authF('/api/gaming/inbounds');
    if(!r.ok){if(sum)sum.textContent='خطا در دریافت اینباندها';return}
    const j=await r.json();
    if(!j.ok){if(sum)sum.textContent=j.error||'خطا';return}
    const ibs=j.inbounds||[];
    if(sum)sum.textContent=toFa(j.healthy_count||0)+' از '+toFa(ibs.length)+' اینباند سالم';
    list.innerHTML=ibs.map(ib=>{
      const ok=ib.healthy;
      const col=ok?'var(--green-t)':'var(--red-t)';
      const icon=ok?'ti-circle-check':'ti-circle-x';
      const lat=ib.connect_ms!=null?toFa(Math.round(ib.connect_ms))+'ms':(ib.latency_ms!=null?toFa(Math.round(ib.latency_ms))+'ms (اسکن)':'—');
      const latJit=(ib.jitter_ms!=null&&ib.type==='ip')?' · jitter '+toFa(Math.round(ib.jitter_ms))+'ms':'';
      return `<div style="padding:12px;background:var(--bg);border-radius:12px;border:1px solid ${ok?'var(--card-b)':'rgba(251,113,133,.35)'}">
        <div style="display:flex;align-items:center;gap:7px;margin-bottom:7px">
          <i class="ti ${icon}" style="color:${col};font-size:15px"></i>
          <div style="flex:1;font-weight:700;font-size:11.5px">${ib.label}</div>
          <span class="badge ${ok?'bg-green':'bg-red'}" style="font-size:9px">${ok?'سالم':'قطع'}</span>
        </div>
        <div dir="ltr" style="font-size:10px;font-family:monospace;color:var(--t2);text-align:left;word-break:break-all">${ib.entry}:${ib.port}</div>
        <div style="font-size:10px;color:var(--t3);margin-top:5px">${lat}${latJit} · ${ib.note||''}</div>
        <button class="btn btn-sm btn-g" style="width:100%;margin-top:8px" onclick="gamingUseInbound('${ib.entry}')"><i class="ti ti-check"></i> استفاده در ساخت کانفیگ</button>
      </div>`}).join('');
    toast('اینباندها تست شد: '+toFa(j.healthy_count||0)+' سالم','ok');
  }catch(e){if(sum)sum.textContent='خطا';toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-plug-connected';ic.style.animation='';if(btn)btn.disabled=false}}
}
function gamingUseInbound(entry){
  if(!entry)return;
  const isIp=/^\d+\.\d+\.\d+\.\d+$/.test(entry);
  document.getElementById('gaming-override-ip').value=isIp?entry:'';
  const sel=document.getElementById('gaming-entry');
  if(sel){
    if(isIp){sel.value='direct'}
    else if(entry.includes('.workers.dev')){sel.value='direct'}
    // دامنه‌ی پنل یا VPS؟ گزینه‌ی متناظر
    else if(document.getElementById('gaming-vps-ip')&&entry===document.getElementById('gaming-vps-ip').value.trim()){sel.value='vps'}
  }
  toast(isIp?('IP «'+entry+'» در فیلد ساخت کانفیگ قرار گرفت'):'ورودی خودکار (دامنه‌ی گیت‌وی) انتخاب شد — حالا «تولید لینک‌ها» را بزن','ok');
  document.getElementById('gaming-entry').scrollIntoView({behavior:'smooth',block:'center'});
}
async function gamingRefreshLocations(silent,check){
  try{
    const r=await authF('/api/gaming/locations'+(check?'?check=1':''));
    if(!r.ok)return;
    const j=await r.json();
    if(!j.ok){if(!silent)toast(j.error||'خطا در دریافت لوکیشن‌ها','err');return}
    const locs=j.locations||[];
    const health={};
    (j.location_health||[]).forEach(h=>{health[h.name]=h});
    const box=document.getElementById('gaming-loc-list-box');
    if(box){
      box.innerHTML=locs.map(l=>{
        const h=health[l.name];
        let badge='<span class="badge bg-blue" style="font-size:9px">؟</span>';
        if(h){badge=h.ok?('<span class="badge bg-green" style="font-size:9px">سالم '+toFa(Math.round(h.latency_ms||0))+'ms</span>'):('<span class="badge bg-red" style="font-size:9px">قطع</span>')}
        else if(l.name==='auto'){badge='<span class="badge bg-green" style="font-size:9px">پیش‌فرض</span>'}
        return `<div style="display:flex;align-items:center;gap:8px;padding:9px 12px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);font-size:11.5px;flex-wrap:wrap">
          <span style="font-size:16px">${l.flag||''}</span>
          <div><div style="font-weight:700">${l.label||l.name}</div>
          <div dir="ltr" style="font-size:10px;color:var(--t3);font-family:monospace">${l.upstream}</div></div>
          ${badge}
          ${l.name!=='auto'?`<button class="btn btn-sm btn-d" style="margin-right:auto" onclick="gamingDelLocation('${l.name}')"><i class="ti ti-trash"></i></button>`:''}
        </div>`}).join('')||'<div style="font-size:11px;color:var(--t3);padding:8px">هنوز لوکیشنی ثبت نشده — از قالب‌های بالا یکی را شروع کن</div>';
    }
    document.getElementById('gaming-loc-count').textContent=toFa(locs.length)+' لوکیشن';
    document.getElementById('gaming-loc-list').textContent=locs.map(l=>(l.flag||'')+' '+l.name).join('، ')||'—';
    gamingFillLocSelect(locs);
    if(!silent)toast(check?('تست سلامت انجام شد: '+toFa((j.location_health||[]).filter(h=>h.ok).length)+' از '+toFa(locs.length)+' سالم'):'لوکیشن‌ها دریافت شد','ok');
  }catch(e){}
}
async function gamingAddLocation(){
  const name=document.getElementById('gaming-loc-name').value.trim().toLowerCase();
  const label=document.getElementById('gaming-loc-label').value.trim();
  const flag=document.getElementById('gaming-loc-flag').value.trim()||'📍';
  const upstream=document.getElementById('gaming-loc-upstream').value.trim().toLowerCase();
  if(!name||!upstream){toast('کد لوکیشن و دامنه‌ی بک‌اند لازم است — اگر هنوز سرور خروج نساختی، اول «بسته‌ی سرور خروج رایگان» را بزن','err');return}
  try{
    const r=await authF('/api/gaming/locations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,label,flag,upstream})});
    const j=await r.json().catch(()=>({ok:false,error:'پاسخ نامعتبر'}));
    if(j.ok){toast('لوکیشن «'+name+'» اضافه شد ✓','ok');document.getElementById('gaming-loc-upstream').value='';gamingRefreshLocations(true,true)}else{toast(j.error||'خطا','err')}
  }catch(e){toast('خطا','err')}
}
async function gamingDelLocation(name){
  try{
    const r=await authF('/api/gaming/locations/'+encodeURIComponent(name),{method:'DELETE'});
    const j=await r.json().catch(()=>({ok:false}));
    if(j.ok){toast('لوکیشن حذف شد','ok');gamingRefreshLocations(true,false)}else{toast(j.error||'خطا','err')}
  }catch(e){toast('خطا','err')}
}
/* ─── ویزارد بسته‌ی سرور خروج رایگان ─── */
async function gamingExitWizard(btn){
  const box=document.getElementById('gaming-exit-wizard');
  if(!box)return;
  if(btn){const ic=btn.querySelector('i');if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite'}}
  box.style.display='';
  box.innerHTML='<div style="padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);font-size:12px"><i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال ساخت بسته با UUID شما...</div>';
  try{
    const r=await authF('/api/gaming/exit-blueprint');
    if(!r.ok){box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">خطا در ساخت بسته</div>';return}
    const j=await r.json();
    if(!j.ok){box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">✗ '+(j.error||'خطا')+'</div>';return}
    const fileCard=(fname,content)=>`<div style="margin-bottom:10px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span class="badge bg-blue" style="font-size:10px;direction:ltr">${fname}</span>
        <button class="btn btn-sm btn-g" style="margin-right:auto" onclick="gamingCopyFile(this)" data-fc="${encodeURIComponent(content)}"><i class="ti ti-copy"></i> کپی</button>
      </div>
      <pre dir="ltr" style="font-size:9.5px;font-family:monospace;max-height:160px;overflow:auto;background:var(--card-in);padding:8px;border-radius:8px;white-space:pre-wrap;direction:ltr;text-align:left">${content.replace(/</g,'&lt;').slice(0,4000)}</pre>
    </div>`;
    box.innerHTML=`
    <div style="padding:16px;background:var(--bg);border-radius:12px;border:1px solid var(--green-t)">
      <div style="font-weight:800;font-size:13px;margin-bottom:6px"><i class="ti ti-package-export" style="color:var(--green-t)"></i> بسته‌ی سرور خروج رایگان — آماده شد!</div>
      <div style="font-size:11.5px;color:var(--t2);line-height:1.9;margin-bottom:12px">
        UUID کانفیگ «${j.label}» داخل فایل‌ها پخت شده: <b dir="ltr" style="font-family:monospace">${j.uuid}</b><br>
        این سرور کوچک روی هر پلتفرم رایگان deploy می‌شود و خروجی ترافیک شما به آن کشور می‌رود.
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
        <a class="btn btn-blue" href="/api/gaming/exit-blueprint?format=zip" style="text-decoration:none"><i class="ti ti-download"></i> دانلود ZIP کامل</a>
        <button class="btn btn-g" onclick="gamingUseLocTemplate('railway-exit')"><i class="ti ti-forms"></i> پرکردن فرم لوکیشن</button>
      </div>
      <div style="font-weight:700;font-size:12px;margin-bottom:8px">مراحل (۵ دقیقه):</div>
      <ol style="margin:0 0 14px;padding-right:18px;font-size:11.5px;color:var(--t2);line-height:2;list-style:persian">
        ${(j.steps||[]).map(s=>`<li>${s}</li>`).join('')}
      </ol>
      <div style="font-weight:700;font-size:12px;margin-bottom:8px">فایل‌های بسته (کپی کن یا ZIP را دانلود کن):</div>
      ${Object.entries(j.files||{}).map(([f,c])=>fileCard(f,c)).join('')}
    </div>`;
    toast('بسته‌ی خروج ساخته شد — UUID شما داخلش پخت شده','ok');
  }catch(e){box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">خطا در ساخت بسته</div>'}
  finally{if(btn){const ic=btn.querySelector('i');if(ic){ic.className='ti ti-package-export';ic.style.animation=''}}}
}
function gamingCopyFile(btn){
  const c=decodeURIComponent(btn.dataset.fc||'');
  if(!c){toast('فایل خالی است','err');return}
  navigator.clipboard.writeText(c).then(()=>toast('فایل کپی شد','ok')).catch(()=>toast('کپی ناموفق','err'));
}
/* ─── اسکنر IP سمت مرورگر — چند روش پروب + abort فوری (ضد کرش، ضد فیلتر) ───
   روش‌ها به ترتیب تلاش:
     ۱) fetch no-cors به /cdn-cgi/trace (سبک و سریع)
     ۲) Image ping (fallback کلاسیک — روی همه‌ی مرورگرها کار می‌کند)
     ۳) WebSocket upgrade (به‌عنوان آخرین تلاش)
   اگر همه‌ی روش‌ها ناموفق بودند، IP فیلتر در نظر گرفته می‌شود. */
function gamingProbe(ip,timeout){
  return new Promise(res=>{
    let settled=false;
    const ctrl=(typeof AbortController!=='undefined')?new AbortController():null;
    const t0=performance.now();
    let imgs=[];
    const cleanup=()=>{imgs.forEach(im=>{try{im.src='';im.onload=null;im.onerror=null}catch(e){}});imgs=[]};
    const done=(v)=>{if(settled)return;settled=true;clearTimeout(timer);try{ctrl&&ctrl.abort()}catch(e){};cleanup();res(v)};
    const timer=setTimeout(()=>done(null),timeout);
    const success=()=>done(performance.now()-t0);
    const fail=()=>{if(settled)return;const dt=performance.now()-t0;done(dt>40&&dt<timeout?dt:null)};

    // ۱) روش fetch no-cors به یک مسیر سبک کلادفلر
    try{
      fetch('https://'+ip+'/cdn-cgi/trace?_='+Math.random().toString(36).slice(2,8),
        {mode:'no-cors',cache:'no-store',redirect:'manual',signal:ctrl?ctrl.signal:undefined})
        .then(success)
        .catch(()=>{});
    }catch(e){}

    // ۲) Image fallback — رویداد onload روی یک image cross-origin یعنی TCP+TLS بالا آمده
    try{
      const im=new Image();
      im.onload=success;
      im.onerror=()=>{if(settled)return;/* سرور پاسخ داد (حتی 404) یعنی TCP بالا است */success()};
      im.src='https://'+ip+'/favicon.ico?_='+Math.random().toString(36).slice(2,10);
      imgs.push(im);
      // image اضافی برای fallback
      const im2=new Image();
      im2.onload=success;
      im2.onerror=success;
      im2.src='https://'+ip+'/__emix_probe?_='+Date.now();
      imgs.push(im2);
    }catch(e){}

    // ۳) WebSocket fallback (آخرین تلاش) — فقط اگر دو روش اول در 200ms اول پاسخ ندادند
    setTimeout(()=>{
      if(settled)return;
      try{
        const ws=new WebSocket('wss://'+ip+'/?_='+Math.random().toString(36).slice(2,6));
        ws.onopen=success;
        ws.onerror=()=>{if(settled)return;const dt=performance.now()-t0;done(dt>200&&dt<timeout?dt:null)};
        // قطع زودهنگام
        setTimeout(()=>{try{ws.close()}catch(e){}},Math.min(timeout,800));
      }catch(e){/* WebSocket ساخته نشد */}
    },200);

    // اگر هیچ‌کدام پاسخ نداد، در timeout انجام می‌شود
  });
}
let gamingScanAbort=false;
async function gamingStartScan(){
  if(gamingScanBusy){toast('اسکن در حال اجراست','err');return}
  gamingScanBusy=true;gamingScanAbort=false;
  const btn=document.getElementById('gaming-scan-btn');
  const prog=document.getElementById('gaming-scan-progress');
  const tbody=document.getElementById('gaming-scan-tbody');
  const table=document.getElementById('gaming-scan-table');
  const sum=document.getElementById('gaming-scan-summary');
  btn.disabled=false;btn.innerHTML='<i class="ti ti-player-stop"></i> توقف اسکن';btn.onclick=()=>{gamingScanAbort=true;toast('اسکن متوقف می‌شود...','ok')};
  const results={};let doneCount=0,total=0,failedCount=0;
  try{
    const r=await authF('/api/gaming/candidates');
    if(!r.ok){toast('خطا در دریافت IPهای کاندید','err');return}
    const ips=(await r.json()).ips||[];total=ips.length;
    table.style.display='';tbody.innerHTML='';
    prog.textContent='در حال اسکن '+toFa(total)+' IP با روش چندگانه (fetch+image+ws)...';
    // دسته‌های ۸تایی + مکث کوتاه — سبک برای مرورگر/موبایل
    for(let i=0;i<ips.length&&!gamingScanAbort;i+=8){
      const batch=ips.slice(i,i+8);
      await Promise.all(batch.map(async ip=>{
        try{
          const samples=[];
          for(let round=0;round<2&&!gamingScanAbort;round++){
            const ms=await gamingProbe(ip,2500);
            if(ms!==null&&ms<2400)samples.push(ms);
            else if(ms===null)failedCount++;
            await new Promise(s=>setTimeout(s,40));
          }
          if(samples.length>=1){
            const min=Math.min(...samples),avg=samples.reduce((a,b)=>a+b,0)/samples.length;
            const jitter=samples.length>1?(Math.max(...samples)-Math.min(...samples)):0;
            results[ip]={ip,min,avg,jitter,n:samples.length};
          }
        }catch(e){/* این IP رد شد — بقیه ادامه */}
        doneCount++;
      }));
      try{gamingRenderScanTable(results)}catch(e){}
      const pct=total?Math.round(doneCount/total*100):0;
      const failPct=doneCount?Math.round(failedCount/doneCount*100):0;
      prog.textContent=(gamingScanAbort?'متوقف‌شده در ':'پیشرفت: ')+toFa(doneCount)+' از '+toFa(total)+' ('+toFa(pct)+'٪) · '+toFa(failPct)+'٪ رد شده';
      if(!gamingScanAbort&&i+8<ips.length){await new Promise(s=>setTimeout(s,100))}
    }
    const ranked=Object.values(results).sort((a,b)=>a.min-b.min);
    if(!ranked.length){
      sum.style.display='';sum.innerHTML='<span style="color:var(--red-t)">هیچ IP پاسخ نداد — احتمالاً ISP رنج کلادفلر را محدود کرده؛ از ورودی VPS ایران یا «مستقیم پنل» استفاده کنید</span>';
    }else{
      try{
        const sr=await authF('/api/gaming/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({results:ranked.slice(0,25)})});
        if(sr.ok){const sj=await sr.json();
          document.getElementById('gaming-best-ip').textContent=sj.best||'—';
          document.getElementById('gaming-best-ms').textContent=sj.best_ms?('تأخیر: '+toFa(Math.round(sj.best_ms))+' ms'):'—';
          if(sj.best){document.getElementById('gaming-override-ip').value=sj.best}
        }
      }catch(e){/* ثبت ناموفق — نتایج محلی هنوز نمایش داده می‌شوند */}
      sum.style.display='';
      sum.innerHTML='🏆 بهترین IP: <b dir="ltr" style="font-family:monospace">'+ranked[0].ip+'</b> با تأخیر <b>'+toFa(Math.round(ranked[0].min))+' ms</b> — با دکمه «تولید لینک‌ها» کانفیگ گیمینگ بسازید.';
    }
    toast(gamingScanAbort?'اسکن متوقف شد — نتایج تا اینجا حفظ شد':'اسکن تمام شد','ok');
  }catch(e){console.error('gamingStartScan',e);toast('خطا در اسکن — نتایج جزئی حفظ شد','err')}
  finally{
    gamingScanBusy=false;
    gamingScanAbort=false;
    btn.innerHTML='<i class="ti ti-radar-2"></i> شروع اسکن (~۱ دقیقه)';
    btn.onclick=()=>gamingStartScan();
    prog.textContent='آماده';
  }
}
function gamingRenderScanTable(results){
  const tbody=document.getElementById('gaming-scan-tbody');
  if(!tbody)return;
  const ranked=Object.values(results||{}).filter(r=>r&&typeof r.min==='number'&&r.ip)
    .sort((a,b)=>a.min-b.min).slice(0,20);
  if(!ranked.length){
    tbody.innerHTML='<tr><td colspan="6" style="padding:18px;text-align:center;color:var(--t3);font-size:11.5px">هنوز نتیجه‌ای دریافت نشده — اسکن در حال اجراست. اگر همه‌ی IPها رد شدند، ISP شما رنج کلادفلر را محدود کرده. از ورودی VPS ایران یا «مستقیم پنل» استفاده کنید.</td></tr>';
    return;
  }
  tbody.innerHTML=ranked.map((r,i)=>{
    const color=r.min<120?'var(--green-t)':r.min<250?'var(--amber-t)':'var(--red-t)';
    return `<tr style="border-top:1px solid var(--card-b)">
      <td style="padding:6px 8px;color:var(--t3)">${toFa(i+1)}</td>
      <td style="padding:6px 8px;direction:ltr;text-align:left;font-family:monospace">${r.ip}</td>
      <td style="padding:6px 8px;font-weight:700;color:${color}">${toFa(Math.round(r.min))}</td>
      <td style="padding:6px 8px">${toFa(Math.round(r.avg||r.min))}</td>
      <td style="padding:6px 8px;color:${(r.jitter||0)<80?'var(--green-t)':'var(--amber-t)'}">${toFa(Math.round(r.jitter||0))}</td>
      <td style="padding:6px 8px">${r.n>=2?'<span class="badge bg-green" style="font-size:9.5px">پایدار</span>':'<span class="badge bg-amber" style="font-size:9.5px">'+toFa(r.n)+'/۲</span>'}</td>
    </tr>`}).join('');
}

/* ════════════════════════════════════════════════════════════════════════════
   VPN Pro — WireGuard & OpenVPN JavaScript Functions
   ════════════════════════════════════════════════════════════════════════════ */
let vpnCfg={};
async function loadVPNPage(){
  try{
    const [wgR,ovpnR]=await Promise.all([
      authF('/api/wg/status'),
      authF('/api/ovpn/status')
    ]);
    if(wgR.ok){
      const wg=await wgR.json();
      vpnCfg.wg=wg;
      const sb=document.getElementById('vpn-status-badge');
      if(sb){sb.textContent=wg.cryptography_available?'آماده':'نیاز به کتابخانه';sb.className='badge '+(wg.cryptography_available?'bg-green':'bg-amber')}
      if(wg.server_endpoint)document.getElementById('wg-endpoint').value=wg.server_endpoint;
      if(wg.server_port)document.getElementById('wg-port').value=wg.server_port;
      if(wg.server_pubkey)document.getElementById('wg-server-pub').value=wg.server_pubkey;
      if(wg.client_ip)document.getElementById('wg-client-ip').value=wg.client_ip;
      if(wg.dns)document.getElementById('wg-dns').value=wg.dns;
      if(wg.keepalive)document.getElementById('wg-keepalive').value=wg.keepalive;
      if(wg.mtu)document.getElementById('wg-mtu').value=wg.mtu;
      // empty-state: اگر سرور ست شده، کادر راهنما را پنهان کن
      const wgEmpty=document.getElementById('wg-empty-state');
      if(wgEmpty && (wg.server_endpoint || wg.server_pubkey)){
        wgEmpty.classList.add('hidden');
      }
    }
    if(ovpnR.ok){
      const ovpn=await ovpnR.json();
      vpnCfg.ovpn=ovpn;
      if(ovpn.server_endpoint)document.getElementById('ovpn-endpoint').value=ovpn.server_endpoint;
      if(ovpn.server_port)document.getElementById('ovpn-port').value=ovpn.server_port;
      if(ovpn.protocol)document.getElementById('ovpn-protocol').value=ovpn.protocol;
      // empty-state: اگر کانفیگ OVPN ست شده، کادر راهنما را پنهان کن
      const ovpnEmpty=document.getElementById('ovpn-empty-state');
      if(ovpnEmpty && (ovpn.server_endpoint || ovpn.has_inline_certs)){
        ovpnEmpty.classList.add('hidden');
      }
    }
  }catch(e){console.error('loadVPNPage',e);toast('خطا در بارگذاری VPN Pro','err')}
}
async function vpnSaveWGConfig(){
  try{
    const body={
      server_endpoint:document.getElementById('wg-endpoint').value.trim(),
      server_port:parseInt(document.getElementById('wg-port').value)||51820,
      server_pubkey:document.getElementById('wg-server-pub').value.trim(),
      client_ip:document.getElementById('wg-client-ip').value.trim(),
      dns:document.getElementById('wg-dns').value.trim(),
      keepalive:parseInt(document.getElementById('wg-keepalive').value)||25,
      mtu:parseInt(document.getElementById('wg-mtu').value)||1280,
    };
    const r=await authF('/api/wg/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    return r.ok;
  }catch(e){return false}
}
async function vpnGenerateClientKeys(btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const box=document.getElementById('wg-keypair-result');
  try{
    const r=await authF('/api/wg/keypair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:'client'})});
    const j=await r.json();
    if(j.ok){
      box.style.display='';
      box.innerHTML=`<div style="padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--green-t);font-size:12px;line-height:2">
        <div style="font-weight:700;margin-bottom:8px;color:var(--green-t)">✓ کلید کلاینت تولید شد</div>
        <div><b>Private (خصوصی):</b> <code dir="ltr" style="font-family:monospace;word-break:break-all">${j.private}</code></div>
        <div><b>Public (عمومی):</b> <code dir="ltr" style="font-family:monospace;word-break:break-all">${j.public}</code></div>
        <div style="margin-top:8px;font-size:11px;color:var(--t3)">این کلیدها در پنل ذخیره شدند. کلید عمومی را در فایل کانفیگ سرور (Peer section) قرار دهید.</div>
      </div>`;
      toast('کلید کلاینت تولید شد','ok');
    }else{
      toast(j.error||'خطا در تولید کلید','err');
    }
  }catch(e){toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-key';ic.style.animation='';if(btn)btn.disabled=false}}
}
async function vpnShowServerKey(btn){
  // نمایش کلید سرور از طریق generate keypair with role=server
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const box=document.getElementById('wg-keypair-result');
  try{
    const r=await authF('/api/wg/keypair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:'server'})});
    const j=await r.json();
    if(j.ok){
      box.style.display='';
      box.innerHTML=`<div style="padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--accent);font-size:12px;line-height:2">
        <div style="font-weight:700;margin-bottom:8px;color:var(--accent)">🔑 کلید سرور تولید شد</div>
        <div><b>Private (خصوصی — فقط در سرور):</b> <code dir="ltr" style="font-family:monospace;word-break:break-all">${j.private}</code></div>
        <div><b>Public (عمومی — در پنل وارد کن):</b> <code dir="ltr" style="font-family:monospace;word-break:break-all">${j.public}</code></div>
        <button class="btn btn-sm btn-g" style="margin-top:8px" onclick="document.getElementById('wg-server-pub').value='${j.public}';toast('کلید عمومی سرور در فیلد بالا قرار گرفت','ok')"><i class="ti ti-arrow-up"></i> قرار دادن در فیلد</button>
      </div>`;
      toast('کلید سرور تولید شد','ok');
    }else{
      toast(j.error||'خطا','err');
    }
  }catch(e){toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-key';ic.style.animation='';if(btn)btn.disabled=false}}
}
async function vpnShowServerScript(btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const box=document.getElementById('wg-keypair-result');
  try{
    const r=await authF('/api/wg/server-script');
    const j=await r.json();
    if(j.ok){
      box.style.display='';
      box.innerHTML=`<div style="padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);font-size:12px">
        <div style="font-weight:700;margin-bottom:8px"><i class="ti ti-server" style="color:var(--accent)"></i> اسکریپت راه‌اندازی WireGuard Server</div>
        <div style="font-size:11px;color:var(--t3);margin-bottom:8px;line-height:1.7">این اسکریپت را در VPS Linux اجرا کن — WireGuard server با UUID شما پخت شده. بعد از اجرا، IP سرور و کلید عمومی سرور را در فیلدهای بالا وارد کن.</div>
        <button class="btn btn-sm btn-g" onclick="vpnCopyText(this,${JSON.stringify(j.script)})"><i class="ti ti-copy"></i> کپی اسکریپت</button>
        <pre dir="ltr" style="font-size:9.5px;font-family:monospace;max-height:200px;overflow:auto;background:var(--bg3);padding:10px;border-radius:8px;white-space:pre-wrap;margin-top:10px;text-align:left">${j.script.replace(/</g,'&lt;').slice(0,3000)}</pre>
      </div>`;
      toast('اسکریپت ساخته شد','ok');
    }else{
      toast(j.error||'خطا','err');
    }
  }catch(e){toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-server';ic.style.animation='';if(btn)btn.disabled=false}}
}
async function vpnGenerateWGConfig(btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const ok=await vpnSaveWGConfig();
  const box=document.getElementById('wg-config-result');
  try{
    if(!ok){box.style.display='';box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">ذخیره تنظیمات ناموفق</div>';return}
    const r=await authF('/api/wg/client-conf');
    const j=await r.json();
    if(j.ok){
      box.style.display='';
      const h=j.health||{};
      const healthBadge=h.ok?'<span class="badge bg-green" style="font-size:10px">سالم</span>':'<span class="badge bg-red" style="font-size:10px">قطع</span>';
      box.innerHTML=`<div style="padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--green-t);font-size:12px">
        <div style="font-weight:700;margin-bottom:8px;color:var(--green-t)">✓ کانفیگ کلاینت WireGuard ساخته شد</div>
        <div style="margin-bottom:8px">تست سلامت سرور (TCP): ${healthBadge}${h.ok?'':' — '+(h.error||'')}</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
          <button class="btn btn-sm btn-g" onclick="vpnCopyText(this,${JSON.stringify(j.config)})"><i class="ti ti-copy"></i> کپی فایل .conf</button>
          <a class="btn btn-sm btn-blue" href="data:text/plain;charset=utf-8,${encodeURIComponent(j.config)}" download="${j.filename}" style="text-decoration:none"><i class="ti ti-download"></i> دانلود فایل</a>
        </div>
        <div style="font-size:10.5px;color:var(--t3);margin-bottom:8px">${j.note||''}</div>
        <pre dir="ltr" style="font-size:10.5px;font-family:monospace;background:var(--bg3);padding:10px;border-radius:8px;white-space:pre-wrap;text-align:left">${j.config.replace(/</g,'&lt;')}</pre>
      </div>`;
      toast('کانفیگ WG ساخته شد','ok');
    }else{
      box.style.display='';box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">✗ '+(j.error||'خطا')+'</div>';
      toast(j.error||'خطا','err');
    }
  }catch(e){box.style.display='';box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">خطا</div>';toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-file-export';ic.style.animation='';if(btn)btn.disabled=false}}
}
async function vpnGenerateWGQR(btn){
  // تولید QR از کانفیگ WG با استفاده از API کتابخانه‌ی qrcode.js
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const box=document.getElementById('wg-qr-result');
  try{
    const ok=await vpnSaveWGConfig();
    if(!ok){box.style.display='';box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">ذخیره ناموفق</div>';return}
    const r=await authF('/api/wg/client-conf');
    const j=await r.json();
    if(j.ok&&j.config){
      box.style.display='';
      // QR محلی (backend خود پنل) — قبلاً api.qrserver.com شخص ثالث بود که credential می‌فرستاد
      const qrUrl='/api/qr?data='+encodeURIComponent(j.config);
      box.innerHTML=`<div style="padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);text-align:center">
        <div style="font-weight:700;margin-bottom:10px">📷 QR کد کانفیگ WireGuard</div>
        <img src="${qrUrl}" alt="QR Code" style="border-radius:8px;border:1px solid var(--card-b);max-width:300px">
        <div style="font-size:10.5px;color:var(--t3);margin-top:8px">در اپ WireGuard موبایل: «Scan QR Code» را بزن</div>
      </div>`;
      toast('QR ساخته شد','ok');
    }else{
      toast(j.error||'خطا در تولید QR','err');
    }
  }catch(e){toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-qrcode';ic.style.animation='';if(btn)btn.disabled=false}}
}
async function vpnTestWG(btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const box=document.getElementById('wg-health-result');
  try{
    const ok=await vpnSaveWGConfig();
    if(!ok){box.style.display='';box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">ذخیره ناموفق</div>';return}
    const r=await authF('/api/wg/client-conf');
    const j=await r.json();
    if(j.ok){
      const h=j.health||{};
      box.style.display='';
      if(h.ok){
        box.innerHTML=`<div style="padding:12px;background:var(--green-bg);border:1px solid var(--green-t);border-radius:10px;font-size:12px;color:var(--green-t)"><i class="ti ti-circle-check"></i> سرور پاسخ داد — اتصال TCP به ${document.getElementById('wg-endpoint').value}:${document.getElementById('wg-port').value} برقرار شد. برای تست واقعی WG، از کلاینت استفاده کنید.</div>`;
      }else{
        box.innerHTML=`<div style="padding:12px;background:var(--red-bg);border:1px solid var(--red-t);border-radius:10px;font-size:12px;color:var(--red-t)"><i class="ti ti-circle-x"></i> سرور در دسترس نیست — ${h.error||'اتصال برقرار نشد'}. مطمئن شو پورت ${document.getElementById('wg-port').value} UDP در فایروال باز است و سرور اجرا شده.</div>`;
      }
    }else{
      box.style.display='';box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">✗ '+(j.error||'خطا')+'</div>';
    }
  }catch(e){toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-plug';ic.style.animation='';if(btn)btn.disabled=false}}
}
async function vpnParseOVPNInline(btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const ta=document.getElementById('ovpn-inline-config');
  const cfg=ta?ta.value.trim():'';
  if(!cfg){toast('فایل .ovpn را paste کنید','err');if(ic){ic.className='ti ti-file-import';ic.style.animation=''};if(btn)btn.disabled=false;return}
  const box=document.getElementById('ovpn-config-result');
  try{
    const r=await authF('/api/ovpn/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({inline_config:cfg})});
    const j=await r.json();
    if(j.ok){
      // فرم‌ها را با اطلاعات پارس‌شده پر کن
      const ovpn=vpnCfg.ovpn||{};
      if(ovpn.server_endpoint)document.getElementById('ovpn-endpoint').value=ovpn.server_endpoint;
      if(ovpn.server_port)document.getElementById('ovpn-port').value=ovpn.server_port;
      if(ovpn.protocol)document.getElementById('ovpn-protocol').value=ovpn.protocol;
      box.style.display='';
      box.innerHTML=`<div style="padding:12px;background:var(--green-bg);border:1px solid var(--green-t);border-radius:10px;font-size:12px;color:var(--green-t)"><i class="ti ti-circle-check"></i> فایل .ovpn پارس شد. سرور: ${ovpn.server_endpoint||'—'}:${ovpn.server_port||'—'} (${(ovpn.protocol||'tcp').toUpperCase()}). CA/Cert/Key استخراج شد.</div>`;
      toast('فایل .ovpn پارس شد','ok');
    }else{
      box.style.display='';box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">✗ '+(j.error||'خطا')+'</div>';
      toast(j.error||'خطا','err');
    }
  }catch(e){toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-file-import';ic.style.animation='';if(btn)btn.disabled=false}}
}
async function vpnShowOVPNServerScript(btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const box=document.getElementById('ovpn-config-result');
  try{
    const r=await authF('/api/ovpn/server-script');
    const j=await r.json();
    if(j.ok){
      box.style.display='';
      box.innerHTML=`<div style="padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);font-size:12px">
        <div style="font-weight:700;margin-bottom:8px"><i class="ti ti-server" style="color:var(--accent)"></i> اسکریپت راه‌اندازی OpenVPN Server</div>
        <div style="font-size:11px;color:var(--t3);margin-bottom:8px;line-height:1.7">این اسکریپت در VPS Linux اجرا کن — OpenVPN server با angristan نصب می‌شود و فایل کانفیگ کلاینت در <code dir="ltr">/root/emix-client.ovpn</code> ساخته می‌شود.</div>
        <button class="btn btn-sm btn-g" onclick="vpnCopyText(this,${JSON.stringify(j.script)})"><i class="ti ti-copy"></i> کپی اسکریپت</button>
        <pre dir="ltr" style="font-size:9.5px;font-family:monospace;max-height:200px;overflow:auto;background:var(--bg3);padding:10px;border-radius:8px;white-space:pre-wrap;margin-top:10px;text-align:left">${j.script.replace(/</g,'&lt;')}</pre>
      </div>`;
      toast('اسکریپت ساخته شد','ok');
    }else{
      toast(j.error||'خطا','err');
    }
  }catch(e){toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-server';ic.style.animation='';if(btn)btn.disabled=false}}
}
async function vpnGenerateOVPNConfig(btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const box=document.getElementById('ovpn-config-result');
  try{
    // ذخیره مشخصات
    const body={
      server_endpoint:document.getElementById('ovpn-endpoint').value.trim(),
      server_port:parseInt(document.getElementById('ovpn-port').value)||1194,
      protocol:document.getElementById('ovpn-protocol').value,
    };
    await authF('/api/ovpn/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const r=await authF('/api/ovpn/client-conf');
    const j=await r.json();
    if(j.ok){
      const h=j.health||{};
      const healthBadge=h.ok?'<span class="badge bg-green" style="font-size:10px">سالم</span>':'<span class="badge bg-red" style="font-size:10px">قطع</span>';
      box.style.display='';
      box.innerHTML=`<div style="padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--green-t);font-size:12px">
        <div style="font-weight:700;margin-bottom:8px;color:var(--green-t)">✓ کانفیگ OpenVPN ساخته شد</div>
        <div style="margin-bottom:8px">تست سلامت سرور (TCP): ${healthBadge}${h.ok?'':' — '+(h.error||'')}</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
          <button class="btn btn-sm btn-g" onclick="vpnCopyText(this,${JSON.stringify(j.config)})"><i class="ti ti-copy"></i> کپی فایل .ovpn</button>
          <a class="btn btn-sm btn-blue" href="data:text/plain;charset=utf-8,${encodeURIComponent(j.config)}" download="${j.filename}" style="text-decoration:none"><i class="ti ti-download"></i> دانلود فایل</a>
        </div>
        <pre dir="ltr" style="font-size:10.5px;font-family:monospace;background:var(--bg3);padding:10px;border-radius:8px;white-space:pre-wrap;text-align:left;max-height:300px;overflow:auto">${j.config.replace(/</g,'&lt;')}</pre>
      </div>`;
      toast('کانفیگ OpenVPN ساخته شد','ok');
    }else{
      box.style.display='';box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">✗ '+(j.error||'خطا')+'</div>';
      toast(j.error||'خطا','err');
    }
  }catch(e){toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-file-export';ic.style.animation='';if(btn)btn.disabled=false}}
}
async function vpnTestOVPN(btn){
  const ic=btn?btn.querySelector('i'):null;
  if(ic){ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';if(btn)btn.disabled=true}
  const box=document.getElementById('ovpn-health-result');
  try{
    const body={
      server_endpoint:document.getElementById('ovpn-endpoint').value.trim(),
      server_port:parseInt(document.getElementById('ovpn-port').value)||1194,
      protocol:document.getElementById('ovpn-protocol').value,
    };
    await authF('/api/ovpn/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const r=await authF('/api/ovpn/client-conf');
    const j=await r.json();
    if(j.ok){
      const h=j.health||{};
      box.style.display='';
      if(h.ok){
        box.innerHTML=`<div style="padding:12px;background:var(--green-bg);border:1px solid var(--green-t);border-radius:10px;font-size:12px;color:var(--green-t)"><i class="ti ti-circle-check"></i> سرور پاسخ داد — اتصال TCP به ${document.getElementById('ovpn-endpoint').value}:${document.getElementById('ovpn-port').value} برقرار شد.</div>`;
      }else{
        box.innerHTML=`<div style="padding:12px;background:var(--red-bg);border:1px solid var(--red-t);border-radius:10px;font-size:12px;color:var(--red-t)"><i class="ti ti-circle-x"></i> سرور در دسترس نیست — ${h.error||'اتصال برقرار نشد'}</div>`;
      }
    }else{
      box.style.display='';box.innerHTML='<div style="padding:12px;color:var(--red-t);font-size:12px">✗ '+(j.error||'خطا')+'</div>';
    }
  }catch(e){toast('خطا','err')}
  finally{if(ic){ic.className='ti ti-plug';ic.style.animation='';if(btn)btn.disabled=false}}
}
function vpnCopyText(btn,text){
  if(!text){toast('متن خالی است','err');return}
  navigator.clipboard.writeText(text).then(()=>toast('متن کپی شد','ok')).catch(()=>toast('کپی ناموفق','err'));
}
/* ─── تولید کانفیگ گیمینگ ─── */
async function gamingCompare(btn){
  const ic=btn.querySelector('i');ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';btn.disabled=true;
  const box=document.getElementById('gaming-compare-result');
  box.style.display='';box.innerHTML='<div style="font-size:12px;color:var(--t3);padding:8px"><i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال تست هر دو مسیر (تا ۳۰ ثانیه)...</div>';
  try{
    const r=await authF('/api/gaming/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    if(!r.ok){box.innerHTML='<span style="color:var(--red-t);font-size:12px">خطا در مقایسه</span>';return}
    const j=await r.json();
    if(!j.ok){box.innerHTML='<div style="padding:10px;font-size:12px;color:var(--red-t)">✗ '+(j.error||'خطا')+'</div>';return}
    const p=j.results.panel_direct||{},g=j.results.cf_gateway||{};
    const row=(title,rr,recommended)=>{
      const ok=rr.ok;
      const ms=ok&&rr.total_ms?toFa(Math.round(rr.total_ms))+' ms':'—';
      return `<div style="flex:1;min-width:200px;padding:12px;background:var(--bg);border-radius:10px;border:1.5px solid ${recommended?'var(--green-t)':'var(--card-b)'}">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
          <span style="font-weight:700;font-size:12px">${title}</span>
          ${recommended?'<span class="badge bg-green" style="font-size:9px;margin-right:auto">✓ پیشنهاد</span>':''}
        </div>
        <div style="font-size:19px;font-weight:800;color:${ok?'var(--green-t)':'var(--red-t)'}">${ms}</div>
        <div style="font-size:10px;color:var(--t3);margin-top:4px">${ok?'RTT هندشیک پروتکل (WS+E2E) ✓':(rr.detail||'در دسترس نیست').slice(0,80)}</div>
      </div>`};
    box.innerHTML='<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px">'+
      row('🖥 مسیر مستقیم پنل',p,j.winner==='panel')+
      row('☁ گیت‌وی کلادفلر',g,j.winner==='gateway')+
      '</div>'+
      '<div style="padding:10px 12px;background:var(--card-in);border-radius:10px;font-size:12px;line-height:1.8"><i class="ti ti-info-circle" style="color:var(--accent2)"></i> '+j.advice+'</div>';
    toast('مقایسه انجام شد','ok');
  }catch(e){box.innerHTML='<span style="color:var(--red-t);font-size:12px">خطا</span>';toast('خطا','err')}
  finally{ic.className='ti ti-scale';ic.style.animation='';btn.disabled=false}
}
function gamingCopyLink(btn){
  const u=decodeURIComponent(btn.dataset.gl||'');
  if(!u){toast('لینک خالی است','err');return}
  navigator.clipboard.writeText(u).then(()=>toast('لینک گیمینگ کپی شد','ok')).catch(()=>toast('کپی ناموفق — دستی انتخاب و کپی کنید','err'));
}
async function gamingGenLinks(){
  try{
    const body={entry:document.getElementById('gaming-entry').value,
      location:document.getElementById('gaming-location').value,
      ip:document.getElementById('gaming-override-ip').value.trim(),
      mode:document.getElementById('gaming-anti-mode').value,
      transport:document.getElementById('gaming-transport').value};
    const r=await authF('/api/gaming/links',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json().catch(()=>({ok:false}));
    const box=document.getElementById('gaming-links-result');
    box.style.display='';
    if(!j.ok){box.innerHTML='<div style="padding:12px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);font-size:12px;color:var(--red-t)">✗ '+(j.error||'خطا')+'</div>';return}
    const rw=j.route_warning?('<div style="margin-bottom:10px;padding:10px 12px;background:rgba(250,204,21,0.08);border:1px solid rgba(250,204,21,0.25);border-radius:10px;font-size:11px;line-height:1.7"><b style="color:var(--amber-t)">⚠ '+esc(j.route_warning.code||'NO_EXIT_NODE_AVAILABLE')+'</b> — '+esc(j.route_warning.message||'')+'</div>'):'';
    const note=(j.egress&&j.egress.endpoint_note)?('<div style="margin-bottom:10px;font-size:10.5px;color:var(--t3);line-height:1.7"><i class="ti ti-info-circle"></i> '+esc(j.egress.endpoint_note)+'</div>'):'';
    box.innerHTML='<div style="padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);font-size:12px">'+
      '<div style="margin-bottom:10px;color:var(--t3)">'+j.entry+' · مسیر: <b>'+j.location+'</b> · ضد ضریب: <b>'+(j.mode_label||'')+'</b> · ترنسپورت: <b>'+(j.transport_label||'')+'</b></div>'+
      rw+note+
      (j.links||[]).map(l=>{
        const rt=l.route||{};
        const cls=(rt.egress||{}).classification||'UNKNOWN';
        const exitInfo='<span style="font-size:10px;color:var(--t3)">خروج: <b>'+(l.exit||'—')+'</b> '+egBadge(cls)+' <span dir="ltr" style="font-family:monospace">['+(rt.route_status||'?')+']</span></span>';
        return `<div style="margin-bottom:10px;padding:10px;background:var(--card-in);border-radius:8px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap">
          <span class="badge bg-blue" style="font-size:10px">${l.protocol}</span><b>${l.label}</b>
          ${exitInfo}
          <button class="btn btn-sm btn-g" style="margin-right:auto" data-gl="${encodeURIComponent(l.gaming)}" onclick="gamingCopyLink(this)"><i class="ti ti-copy"></i> کپی لینک گیمینگ</button>
        </div>
        <div dir="ltr" style="font-size:10px;font-family:monospace;color:var(--t3);word-break:break-all;direction:ltr;text-align:left">${l.gaming}</div>
      </div>`}).join('')+'</div>';
    toast('لینک‌های گیمینگ با حالت '+(j.mode_label||'')+' ساخته شد','ok');
  }catch(e){toast('خطا','err')}
}
async function gamingGenJson(){
  try{
    const body={entry:document.getElementById('gaming-entry').value,
      location:document.getElementById('gaming-location').value,
      ip:document.getElementById('gaming-override-ip').value.trim(),
      mode:document.getElementById('gaming-anti-mode').value,
      transport:document.getElementById('gaming-transport').value};
    const r=await authF('/api/gaming/xray-json',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json().catch(()=>({ok:false}));
    const box=document.getElementById('gaming-json-result');
    box.style.display='';
    if(!j.ok){box.innerHTML='<div style="padding:12px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);font-size:12px;color:var(--red-t)">✗ '+(j.error||'خطا')+'</div>';return}
    const txt=JSON.stringify(j.xray,null,2);
    box.innerHTML='<div style="padding:14px;background:var(--bg);border-radius:10px;border:1px solid var(--card-b);font-size:12px">'+
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><b>JSON گیمینگ — '+j.label+'</b>'+
      '<button class="btn btn-sm btn-g" style="margin-right:auto" id="gaming-json-copy"><i class="ti ti-copy"></i> کپی JSON</button></div>'+
      '<div style="font-size:10.5px;color:var(--t3);margin-bottom:8px">در v2rayNG: تنظیمات ← از کلیپ‌بورد import · شامل fragment ضد ضریب + بدون mux + tcpNoDelay + اثر انگشت مرورگر</div>'+
      '<pre dir="ltr" style="font-size:10px;font-family:monospace;max-height:300px;overflow:auto;background:var(--card-in);padding:10px;border-radius:8px;white-space:pre-wrap">'+txt.replace(/</g,'&lt;')+'</pre></div>';
    const cpBtn=document.getElementById('gaming-json-copy');
    if(cpBtn)cpBtn.onclick=()=>navigator.clipboard.writeText(txt).then(()=>toast('JSON کپی شد','ok'));
    toast('JSON گیمینگ ساخته شد','ok');
  }catch(e){toast('خطا','err')}
}
function openModalGeneric(title,bodyHtml){
  // استفاده از modal موجود (modal-create-link قبلاً تعریف شده) اگر نبود، یک div ساده
  let m=document.getElementById('modal-generic');
  if(!m){
    m=document.createElement('div');
    m.id='modal-generic';
    m.className='modal';
    m.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.55);display:none;align-items:center;justify-content:center;z-index:9999;padding:20px';
    m.innerHTML='<div class="modal-card" style="background:var(--card);border-radius:14px;padding:20px;max-width:560px;width:100%;max-height:80vh;overflow-y:auto"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px"><div style="font-weight:700;font-size:13.5px" id="modal-generic-title"></div><button class="btn btn-sm" onclick="document.getElementById(\'modal-generic\').style.display=\'none\'"><i class="ti ti-x"></i></button></div><div id="modal-generic-body" style="font-size:11.5px"></div></div>';
    document.body.appendChild(m);
  }
  document.getElementById('modal-generic-title').textContent=title;
  document.getElementById('modal-generic-body').innerHTML=bodyHtml;
  m.style.display='flex';
}
// اتصال سوییچ‌ها به ذخیره‌ی خودکار
document.addEventListener('change',e=>{
  if(e.target.id==='zeus-tls-toggle'){zeusSaveTlsMask()}
  else if(e.target.id==='zeus-smart-toggle'){zeusSaveSmart()}
  else if(e.target.id==='zeus-security-toggle'){zeusSaveSecurity()}
});

/* ══════ آی‌پی‌های تمیز — اسکن اروان + اسکن مرورگر + لینک IP-دار ══════ */
let cipValid=[];   // IPهای تاییدشده سمت سرور
let cipLatency={}; // تاخیر اندازه‌گیری‌شده از مرورگر
async function cipScanArvan(btn){
  const ic=btn.querySelector('i');ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';btn.disabled=true;
  const list=document.getElementById('cip-list');
  list.innerHTML='<div class="sr"><span class="sr-k" style="color:var(--t3)"><i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال نمونه‌گیری از رنج‌های رسمی اروان و اعتبارسنجی SNI...</span></div>';
  try{
    const r=await authF('/api/clean-ips/arvan?limit=32',{method:'GET'});
    const d=await r.json();
    if(!r.ok){list.innerHTML=`<div class="sr"><span class="sr-k" style="color:var(--red-t)">${esc(d.detail||'خطا در اسکن')}</span></div>`;toast(d.detail||'خطا در اسکن اروان','err');return}
    cipValid=d.valid||[];
    document.getElementById('cip-cnt').textContent=toFa(cipValid.length)+' آی‌پی';
    if(!cipValid.length){
      list.innerHTML='<div class="sr"><span class="sr-k" style="color:var(--amber-t)">هیچ آی‌پی از رنج‌های اروان دامنه‌ی شما را سرو نکرد — رکورد CDN در اروان را بررسی کنید</span></div>';
      return;
    }
    cipRender();
    toast(`${toFa(cipValid.length)} آی‌پی معتبر پیدا شد — حالا «اسکن از مرورگر من» را بزنید`,'ok');
  }catch(e){toast('خطا در اسکن اروان','err');list.innerHTML='<div class="sr"><span class="sr-k" style="color:var(--red-t)">خطا در اسکن</span></div>'}
  finally{ic.className='ti ti-radar';ic.style.animation='';btn.disabled=false}
}
function cipRender(){
  const list=document.getElementById('cip-list');
  const items=cipValid.map(v=>{
    const lat=cipLatency[v.ip];
    let latHtml='<span class="cfg-sub-tag" style="color:var(--t3)">تست نشده</span>';
    if(lat==='fail')latHtml='<span class="cfg-sub-tag" style="color:var(--red-t)">قطع</span>';
    else if(lat!=null)latHtml=`<span class="cfg-sub-tag" style="color:${lat<400?'var(--green-t)':lat<900?'var(--amber-t)':'var(--red-t)'};font-weight:700">${toFa(Math.round(lat))}ms</span>`;
    return `<div class="sr">
      <span class="sr-k mono" style="direction:ltr;gap:8px"><i class="ti ti-world"></i> ${v.ip} ${lat!=null&&lat!=='fail'&&lat===cipBest()? '<span style="font-size:11px">🥇</span>':''}</span>
      <span style="display:flex;gap:6px;align-items:center">
        ${latHtml}
        <button class="btn btn-sm btn-g btn-icon" onclick="cipCopyLinks('${v.ip}')" title="لینک‌های همه‌ی کانفیگ‌ها با این آی‌پی"><i class="ti ti-copy"></i></button>
      </span>
    </div>`;
  }).join('');
  list.innerHTML=items||'<div class="sr"><span class="sr-k" style="color:var(--t3)">ابتدا «اسکن آروان» را بزنید</span></div>';
}
function cipBest(){
  const valid=Object.entries(cipLatency).filter(([k,v])=>typeof v==='number').sort((a,b)=>a[1]-b[1]);
  return valid.length?+valid[0][0]:null;
}
async function cipScanBrowser(btn){
  if(!cipValid.length){toast('ابتدا «اسکن آروان» را بزنید','err');return}
  const ic=btn.querySelector('i');ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';btn.disabled=true;
  toast(`در حال سنجش تاخیر ${toFa(cipValid.length)} آی‌پی از اینترنت شما...`,'ok');
  // سنجش موازی (محدود) با fetch no-cors — زمان کامل TCP+TLS+HTTP
  const CONC=6;
  const queue=[...cipValid];
  async function worker(){
    while(queue.length){
      const v=queue.shift();
      const t0=performance.now();
      try{
        await Promise.race([
          fetch(`https://${v.ip}/`,{mode:'no-cors',cache:'no-store'}),
          new Promise((_,rej)=>setTimeout(()=>rej(),5000))
        ]);
        cipLatency[v.ip]=performance.now()-t0;
      }catch(e){
        cipLatency[v.ip]='fail';
      }
      cipRender();
    }
  }
  try{await Promise.all(Array.from({length:Math.min(CONC,cipValid.length)},worker))}
  finally{ic.className='ti ti-speedometer';ic.style.animation='';btn.disabled=false}
  const ok=Object.values(cipLatency).filter(v=>typeof v==='number');
  if(ok.length){
    const best=Object.entries(cipLatency).filter(([k,v])=>typeof v==='number').sort((a,b)=>a[1]-b[1])[0];
    toast(`🥇 سریع‌ترین برای شما: ${best[0]} — ${Math.round(best[1])}ms (دکمه‌ی کپی کنارش = لینک‌ها با این IP)`,'ok');
  }else{
    toast('هیچ آی‌پی از مرورگر شما پاسخ نداد','err');
  }
}
async function cipCopyLinks(ip){
  try{
    const r=await authF(`/api/clean-ips/links?ip=${ip}`);
    const d=await r.json();
    if(!d.links||!d.links.length){toast('لینکی برای این آی‌پی ساخته نشد','err');return}
    const all=d.links.map(l=>l.link).join('\n');
    await navigator.clipboard.writeText(all);
    toast(`${toFa(d.links.length)} لینک با آی‌پی ${ip} کپی شد`,'ok');
  }catch(e){toast('خطا در ساخت لینک‌های IP','err')}
}

/* ══════ تست پورت‌ها از مرورگر ══════ */
const PORTS_TLS=[443,2053,2083,2087,2096,8443];
const PORTS_PLAIN=[80,8080,8880,2052,2086,2095];
function portChip(p,cls){
  return `<span class="cfg-sub-tag port-chip" data-port="${p}" style="cursor:pointer;font-weight:700;${cls}">${p} <b style="font-weight:400;font-size:8.5px;color:var(--t3)">ms?</b></span>`;
}
function portRender(){
  document.getElementById('ports-tls').innerHTML=PORTS_TLS.map(p=>portChip(p,'color:var(--green-t)')).join('');
  document.getElementById('ports-plain').innerHTML=PORTS_PLAIN.map(p=>portChip(p,'color:var(--amber-t)')).join('');
}
async function portTestAll(btn){
  const host=document.getElementById('br-host').value.trim();
  if(!host){toast('ابتدا آدرس پل را وارد کنید','err');return}
  const ic=btn.querySelector('i');ic.className='ti ti-loader-2';ic.style.animation='spin 1s linear infinite';btn.disabled=true;
  const all=[...PORTS_TLS,...PORTS_PLAIN];
  async function testPort(p){
    const chip=document.querySelector(`.port-chip[data-port="${p}"]`);
    if(chip){chip.style.opacity='.5';chip.querySelector('b').textContent='...'}
    const t0=performance.now();
    try{
      await Promise.race([
        fetch(`https://${host}:${p}/`,{mode:'no-cors',cache:'no-store'}),
        new Promise((_,rej)=>setTimeout(()=>rej(),4000))
      ]);
      const ms=Math.round(performance.now()-t0);
      if(chip){chip.style.opacity='1';chip.querySelector('b').textContent=toFa(ms)+'ms';chip.style.borderColor='var(--green)'}
    }catch(e){
      if(chip){chip.style.opacity='.35';chip.querySelector('b').textContent='✗';chip.style.textDecoration='line-through'}
    }
  }
  try{await Promise.all(all.map(testPort))}
  finally{ic.className='ti ti-speedometer';ic.style.animation='';btn.disabled=false}
  toast('تست پورت‌ها از اینترنت شما کامل شد','ok');
}
setTimeout(portRender,0);
// لیسنر محاسبه‌گر صرفه‌جویی
setTimeout(()=>{const s=document.getElementById('br-calc-gb');if(s)s.addEventListener('input',brCalc)},0);
async function brShowNginx(){
  try{
    const r=await authF('/api/bridge/script?fmt=nginx');
    if(r.ok){bridgeScriptCache=await r.text();document.getElementById('br-script').textContent=bridgeScriptCache;toast('نسخه nginx نمایش داده شد','ok')}
  }catch(e){toast('خطا در دریافت نسخه nginx','err')}
}
async function loadLinks(){
  try{
    const [lr,sr,nr,zr]=await Promise.all([authF('/api/links'),authF('/api/subs'),authF('/api/nodes/aggregate').catch(()=>null),authF('/api/zeus-proxy/status').catch(()=>null)]);
    const {links: localLinks=[]}=await lr.json();
    const {subs=[]}=await sr.json();
    try{ zeusStatus = zr ? await zr.json() : null; }catch(e){ zeusStatus = null; }
    document.getElementById('zeus-nav-btn').style.display = (zeusStatus && zeusStatus.phase==='done') ? 'none' : '';
    let nodeLinks=[];
    onlineNodesList=[];
    if(nr && nr.ok){
      try{
        const nd=await nr.json();
        (nd.nodes||[]).forEach(n=>{
          if(n.disabled||!n.online) return;
          onlineNodesList.push(n);
          (n.links||[]).forEach(l=>nodeLinks.push({...l,_nodeId:n.node_id,_nodeName:n.label||'نود'}));
        });
      }catch(e){}
    }
    const links=[...localLinks,...nodeLinks];
    // هشدار یک‌باره: اگر دامنه‌ی عمومی Railway فعال نباشد، لینک‌ها روی localhost می‌مانند
    if(!window.__domainWarned&&localLinks.some(l=>(l.vless_link||'').includes('@localhost:')||(l.vless_link||'').includes('@127.0.0.1:'))){
      window.__domainWarned=true;
      toast('دامنه‌ی عمومی فعال نیست — Railway → Settings → Networking → Generate Domain','warn');
    }
    allSubsList=subs;allLinksList=links;
    document.getElementById('info-inbounds').textContent = toFa(links.length);
    document.getElementById('info-clients').textContent = toFa(links.filter(l=>l.active).length);
    document.getElementById('info-alltime').textContent = fmtB(links.reduce((s,l)=>s+l.used_bytes,0));
    const nlSub=document.getElementById('nl-sub');
    nlSub.innerHTML='<option value="">— بدون گروه —</option>'+subs.map(s=>`<option value="${esc(s.sub_id)}">${esc(s.name)}</option>`).join('');
    const nlTarget=document.getElementById('nl-target'), nlTargetWrap=document.getElementById('nl-target-wrap');
    if(nlTarget){
      nlTarget.innerHTML='<option value="">این پنل</option>'+onlineNodesList.map(n=>`<option value="${esc(n.node_id)}">${esc(n.label||'نود')}</option>`).join('');
      if(nlTargetWrap) nlTargetWrap.style.display = onlineNodesList.length ? '' : 'none';
    }
    document.getElementById('links-nb').textContent=links.length;
    document.getElementById('links-pg-cnt').textContent=toFa(links.length)+' کانفیگ';
    const lsumBadge=document.getElementById('lsummary-badge'); if(lsumBadge)lsumBadge.textContent=toFa(links.length);
    const liveUuids=new Set(links.map(l=>l.uuid));
    [...selectedLinkUuids].forEach(u=>{if(!liveUuids.has(u))selectedLinkUuids.delete(u)});
    document.getElementById('links-selectall-wrap').style.display=links.length?'flex':'none';
    const zeusExists = !!(zeusStatus && zeusStatus.phase==='done' && zeusStatus.result);
    const grid=document.getElementById('links-grid'),empty=document.getElementById('links-empty');
    if(!links.length && !zeusExists){grid.innerHTML='';empty.style.display='block';const ls1=document.getElementById('lsummary');if(ls1)ls1.innerHTML='<div class="empty"><i class="ti ti-link-off"></i><p>کانفیگی وجود ندارد</p></div>';updateBulkBar();return}
    empty.style.display='none';
    const subMap=Object.fromEntries(subs.map(s=>[s.sub_id,s.name]));
    grid.innerHTML=(zeusExists?zeusCardHtml(zeusStatus):'')+links.map(l=>{
  const isNode=!!l._nodeId;
  const lim=l.limit_bytes===0?'∞':fmtB(l.limit_bytes);
  const pct=l.limit_bytes===0?0:Math.min(100,l.used_bytes/l.limit_bytes*100);
  const bc=pct>90?'var(--red)':pct>70?'var(--amber)':'var(--accent)';
  const allowed=l.active&&!l.expired;
  const cardCls=(!l.active?'is-off':(l.expired?'is-exp':''))+(isNode?' is-node':'');
  const isMt = l.protocol === 'mtproto';
  const adBtn = isMt
    ? `<button class="btn btn-sm btn-pur btn-icon" onclick="openAdTagModal('${l.uuid}','${esc(l.label)}','${esc(l.ad_tag||'')}')" title="تنظیم تبلیغ کانال"><i class="ti ti-speakerphone"></i></button>`
    : '';
  const idChip = isMt
    ? `<span class="cfg-uuid-mini" onclick="navigator.clipboard.writeText('${esc(l.mtproto_secret||'')}').then(()=>toast('سکرت کپی شد ✓','ok'))" title="سکرت کامل: ${esc(l.mtproto_secret||'')}"><i class="ti ti-key"></i> ${esc((l.mtproto_secret||'').slice(0,10))}…</span>`
    : `<span class="cfg-uuid-mini" onclick="navigator.clipboard.writeText('${l.uuid}').then(()=>toast('UUID کپی شد','ok'))" title="${l.uuid}"><i class="ti ti-fingerprint"></i> ${l.uuid.slice(0,10)}…</span>`;
  const nodeBadge = isNode ? `<span class="node-origin" style="margin-left:6px"><i class="ti ti-topology-star-3"></i> نود: ${esc(l._nodeName)}</span>` : '';
  return `<div class="cfg-card ${cardCls} ${selectedLinkUuids.has(l.uuid)?'selected':''}" data-uuid="${l.uuid}">
    <div class="cfg-row">
      ${isNode?'<span style="width:18px;flex-shrink:0"></span>':`<div class="cfg-check ${selectedLinkUuids.has(l.uuid)?'checked':''}" onclick="toggleLinkSelect('${l.uuid}',this)"><i class="ti ti-check"></i></div>`}
      <span class="cfg-status-dot ${allowed?'pulse':''}"></span>
      <div class="cfg-identity">
        <div class="cfg-label">${esc(l.label)} ${nodeBadge}</div>
        <div class="cfg-sub-meta">
          ${idChip}
          <span>${new Date(l.created_at).toLocaleDateString('fa-IR')}</span>
        </div>
      </div>
      <div class="cfg-divider-v"></div>
      <div class="cfg-usage-col">
        <div class="ubar"><div class="ubar-f" style="width:${pct}%;background:${bc}"></div></div>
        <div class="utxt"><span>${fmtB(l.used_bytes)}</span><span>از ${lim}</span></div>
      </div>
      <div class="cfg-divider-v"></div>
      <div class="cfg-exp-col">${expChip(l.expires_at,l.expired)}</div>
      <div class="cfg-divider-v"></div>
      <div class="cfg-badges-col">
        ${protoBadge(l.protocol)}
        ${pingBadgeHtml(l)}
        ${l.spoof_sni_enabled && l.spoof_sni ? `<span class="cfg-sub-tag" style="background:linear-gradient(135deg,rgba(139,92,246,.18),rgba(250,204,21,.12));color:#FFD1C2;padding:3px 9px;border-radius:20px;border:1px solid rgba(139,92,246,.25);font-weight:700" title="SNI جعلی فعال — SNI ارسالی در TLS Handshake: ${esc(l.spoof_sni)}"><i class="ti ti-mask" style="color:#FFD1C2"></i> 🎭 ${esc(l.spoof_sni)}</span>` : ''}
        ${isMt && l.ad_tag ? `<span class="cfg-sub-tag" style="background:linear-gradient(135deg,rgba(168,85,247,.18),rgba(202,138,4,.12));color:#FFB199;padding:3px 9px;border-radius:20px;border:1px solid rgba(168,85,247,.25);font-weight:700"><i class="ti ti-speakerphone" style="color:#FFB199"></i> تبلیغ فعال</span>` : ''}
        ${isMt && l.mtproto_public_host ? `<span class="cfg-sub-tag"><i class="ti ti-route"></i> ${esc(l.mtproto_public_host)}:${l.mtproto_public_port}</span>` : ''}
        ${isMt && !l.mtproto_public_host && l.mtproto_public_pending ? `<span class="cfg-sub-tag" style="color:var(--amber-t)"><i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال ساخت TCP Proxy عمومی...</span>` : ''}
        ${isMt && !l.mtproto_public_host && !l.mtproto_public_pending && !l.mtproto_manual_port ? `<span class="cfg-sub-tag" style="color:var(--red-t)"><i class="ti ti-alert-triangle"></i> بدون TCP Proxy عمومی — لینک کار نمی‌کند</span>` : ''}
        ${l.sub_id&&allSubsList.find(s=>s.sub_id===l.sub_id)?`<span class="cfg-sub-tag"><i class="ti ti-folder"></i> ${esc(allSubsList.find(s=>s.sub_id===l.sub_id).name)}</span>`:''}
      </div>
      <div class="cfg-divider-v"></div>
      <div class="cfg-actions">
        <div class="cfg-actions">
        <button class="tog${allowed?' on':''}" onclick="toggleActive('${l.uuid}',${!l.active}${isNode?`,'${l._nodeId}'`:''})" title="فعال/غیرفعال"></button>
        ${!isNode?adBtn:''}
        ${!isNode?`<button class="btn btn-sm btn-g btn-icon" onclick="pingLink('${l.uuid}',this)" title="تست پینگ و سلامت تونل"><i class="ti ti-activity"></i></button>`:`<button class="btn btn-sm btn-g btn-icon" onclick="pingNodeLink('${l.uuid}',this,'${l._nodeId}')" title="تست پینگ روی نود"><i class="ti ti-activity"></i></button>`}
        ${!isNode&&(l.protocol==='vless-ws'||l.protocol==='trojan-ws')?`<button class="btn btn-sm btn-g btn-icon" onclick="turboTest('${l.uuid}',this)" title="تست توربو 0-RTT — یک RTT کمتر در هر اتصال + کپی لینک توربو"><i class="ti ti-rocket"></i></button>`:''}
        <button class="btn btn-sm btn-g btn-icon" onclick="navigator.clipboard.writeText('${esc(l.vless_link)}').then(()=>toast('لینک کپی شد','ok'))" title="کپی لینک"><i class="ti ti-copy"></i></button>
        ${isMt
          ? `<button class="btn btn-sm btn-g btn-icon" onclick="openMtInfoModal('${esc(l.label)}','${esc(l.mtproto_secret||'')}','${esc(l.vless_link)}',${!!l.mtproto_public_host})" title="اطلاعات پروکسی"><i class="ti ti-info-circle"></i></button>`
          : `<button class="btn btn-sm btn-g btn-icon" onclick="navigator.clipboard.writeText('${esc(l.sub_url)}').then(()=>toast('Sub کپی شد','ok'))" title="Sub URL"><i class="ti ti-rss"></i></button>
        <button class="btn btn-sm btn-g btn-icon" onclick="showQR('${esc(l.vless_link)}')" title="QR"><i class="ti ti-qrcode"></i></button>`
        }
        ${!isNode?`<button class="btn btn-sm btn-amber btn-icon" onclick="openEditLink('${l.uuid}')" title="ویرایش"><i class="ti ti-edit"></i></button>`:`<button class="btn btn-sm btn-amber btn-icon" onclick="openEditLink('${l.uuid}','${l._nodeId}')" title="ویرایش از راه دور"><i class="ti ti-edit"></i></button>`}
        <button class="btn btn-sm btn-g btn-icon" onclick="resetUsage('${l.uuid}'${isNode?`,'${l._nodeId}'`:''})" title="ریست مصرف"><i class="ti ti-rotate"></i></button>
        <button class="btn btn-sm btn-d btn-icon" onclick="deleteLink('${l.uuid}'${isNode?`,'${l._nodeId}'`:''})" title="حذف"><i class="ti ti-trash"></i></button>
      </div>
      </div>
    </div>
  </div>`;
}).join('');
    const ls2=document.getElementById('lsummary'); if(ls2)ls2.innerHTML=links.slice(0,6).map(l=>`<div class="sr"><span class="sr-k" style="gap:5px"><i class="ti ${l.expired?'ti-calendar-x':l.active?'ti-circle-check':'ti-circle-x'}" style="color:${l.expired?'var(--amber)':l.active?'var(--green)':'var(--red)'}"></i>${esc(l.label)}</span><span class="sr-v" style="font-size:10px">${fmtB(l.used_bytes)} / ${l.limit_bytes===0?'∞':fmtB(l.limit_bytes)}</span></div>`).join('');
    updateBulkBar();
    // ── Auto-ping background ───────────────────────────────────────────
    // بدون وقفه روی UI — هم‌زمان با ۳ concurrent، با ۱.۵ ثانیه تأخیر
    // تا گرافیک اولیه کامل رندر شود.
    if(!window.__autoPingScheduled){
      window.__autoPingScheduled = true;
      setTimeout(()=>{ autoPingAll(localLinks.map(l=>l.uuid)); }, 1500);
    }
  }catch(e){netErr(e,'لیست کانفیگ‌ها')}
}

// ════════════════════════════════════════════════════════════════════════════
// autoPingAll — پینگ خودکار همه‌ی کانفیگ‌های محلی پس از بارگذاری داشبورد
// نتیجه: همه‌ی بج‌های پینگ بدون دخالت کاربر، آپدیت می‌شوند.
// ════════════════════════════════════════════════════════════════════════════
async function autoPingAll(uuids){
  if(!uuids || !uuids.length) return;
  // روی رویدارها، هر ۶۰ ثانیه تکرار می‌کنیم
  if(window.__autoPingTimer){ clearTimeout(window.__autoPingTimer); }
  const CONC = 3;
  const queues = Array.from({length: Math.min(CONC, uuids.length)}, (_,i) => uuids.filter((_,j) => j%CONC === i));
  const rtt = await clientRtt().catch(()=>null);
  async function worker(list){
    for(const uuid of list){
      try{
        const r = await authF(`/api/links/${uuid}/ping`, {method:'POST'});
        const d = await r.json();
        // فقط اگر کاربر روی همان لینک در حال کلیک نیست، آپدیت کن
        const el = document.getElementById('pb-'+uuid);
        if(el && !el.dataset.userActive){
          renderPingBadge(uuid, d, rtt);
        }
      }catch(e){ /* ignore — silent background */ }
    }
  }
  await Promise.all(queues.map(q => worker(q)));
  // تکرار هر ۶۰ ثانیه — فقط اگر تب لینک‌ها هنوز فعال است
  window.__autoPingTimer = setTimeout(()=>{
    if(document.querySelector('.nav-it.on[data-pg="links"]')){
      autoPingAll(uuids);
    } else {
      window.__autoPingScheduled = false;
    }
  }, 60000);
}

/* ══════ انتخاب گروهی و حذف دسته‌جمعی کانفیگ‌ها ══════ */
let selectedLinkUuids=new Set();
function toggleLinkSelect(uuid,el){
  if(selectedLinkUuids.has(uuid)){selectedLinkUuids.delete(uuid);el.classList.remove('checked');el.closest('.cfg-card')?.classList.remove('selected')}
  else{selectedLinkUuids.add(uuid);el.classList.add('checked');el.closest('.cfg-card')?.classList.add('selected')}
  updateBulkBar();
}
function toggleSelectAllLinks(){
  const selectable=allLinksList.filter(l=>!l._nodeId);
  const allSelected=selectable.length>0&&selectedLinkUuids.size===selectable.length;
  if(allSelected){selectedLinkUuids.clear()}
  else{selectedLinkUuids=new Set(selectable.map(l=>l.uuid))}
  document.querySelectorAll('#links-grid .cfg-card').forEach(card=>{
    const on=selectedLinkUuids.has(card.dataset.uuid);
    card.classList.toggle('selected',on);
    card.querySelector('.cfg-check')?.classList.toggle('checked',on);
  });
  updateBulkBar();
}
function clearLinkSelection(){
  selectedLinkUuids.clear();
  document.querySelectorAll('#links-grid .cfg-card').forEach(card=>{
    card.classList.remove('selected');
    card.querySelector('.cfg-check')?.classList.remove('checked');
  });
  updateBulkBar();
}
function updateBulkBar(){
  const bar=document.getElementById('links-bulkbar');
  const n=selectedLinkUuids.size;
  bar.classList.toggle('show',n>0);
  document.getElementById('links-bulkbar-n').textContent=toFa(n);
  const allCheck=document.getElementById('links-selectall-check');
  const selectableN=allLinksList.filter(l=>!l._nodeId).length;
  if(allCheck)allCheck.classList.toggle('checked',selectableN>0&&n===selectableN);
}
async function bulkDeleteLinks(){
  const n=selectedLinkUuids.size;
  if(!n)return;
  if(!confirm(`${toFa(n)} کانفیگ انتخاب‌شده حذف شود؟ این عمل قابل بازگشت نیست.`))return;
  const uuids=[...selectedLinkUuids];
  try{
    const results=await Promise.all(uuids.map(u=>authF('/api/links/'+u,{method:'DELETE'}).then(r=>r.ok).catch(()=>false)));
    const okCount=results.filter(Boolean).length;
    selectedLinkUuids.clear();
    if(okCount===uuids.length)toast(`${toFa(okCount)} کانفیگ حذف شد ✓`,'ok');
    else toast(`${toFa(okCount)} از ${toFa(uuids.length)} کانفیگ حذف شد`,okCount>0?'ok':'err');
    loadLinks();
  }catch(e){toast('خطا در حذف گروهی','err')}
}

let protoBase = 'vless', protoTransport = 'ws';

function qcTab(name, el){
  document.querySelectorAll('.qc-tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  document.querySelectorAll('.qc-pane').forEach(p=>p.classList.remove('active'));
  document.getElementById('qc-pane-'+name).classList.add('active');
}

let cmBase = 'vless', cmTransport = 'ws';
// ── Phase 37.18: frontend consumes the BACKEND compatibility matrix ──────
// ONE source of truth: /api/config-matrix (compat.py TRANSPORT_MATRIX).
// The create modal gates every (protocol, transport) choice against it —
// impossible combinations are blocked BEFORE the request, with the reason.
let EMIX_COMPAT = null;
async function cmLoadMatrix(){
  // Audit fix: قبلاً اگر ماتریس گرفته نمی‌شد gating بی‌صدا به «همه‌چیز مجاز»
  // تنزل می‌کرد. حالا افت gating به کاربر اعلام می‌شود (سرور همچنان 400
  // می‌دهد؛ این فقط لایه‌ی UX است — رفتار امنیتی تغییر نکرده).
  try {
    const r = await fetch('/api/config-matrix', {credentials:'same-origin'});
    if (!r.ok) { netErr(r, 'ماتریس سازگاری'); return; }
    const j = await r.json();
    if (j && j.ok && Array.isArray(j.combinations)) EMIX_COMPAT = j.combinations;
    else netErr(new Error('bad matrix payload'), 'ماتریس سازگاری');
  } catch(e) { netErr(e, 'ماتریس سازگاری'); }
}
function cmMatrixState(proto, transport){
  if (!EMIX_COMPAT) return 'VALID'; // matrix unavailable → legacy behavior
  const key = (proto === 'vless' && transport !== 'ws') ? transport : `${proto}-${transport}`;
  const row = EMIX_COMPAT.find(c => c.fused === key || (c.protocol === proto && c.transport === transport));
  return row ? row.state : 'NOT_IMPLEMENTED';
}
function cmGateCombo(proto, transport){
  const state = cmMatrixState(proto, transport);
  if (state === 'VALID') return true;
  const label = state === 'EXPERIMENTAL' ? 'ترکیب آزمایشی' :
                state === 'NOT_IMPLEMENTED' ? 'پیاده‌سازی نشده' : 'ترکیب نامعتبر';
  toast(`این ترکیب پروتکل/ترابرد ${label} است — ماتریس سازگاری سرور`, 'err');
  return false;
}
cmLoadMatrix();

function cmToggleDD(id){
  const el = document.getElementById(id);
  const isOpen = el.classList.contains('open');
  document.querySelectorAll('.cm-dd').forEach(d => d.classList.remove('open'));
  if(!isOpen) el.classList.add('open');
}

const BASE_INFO = {
  vless:    { icon:'ti-bolt',           title:'VLESS',          desc:'سبک، سریع و پرکاربردترین گزینه' },
  trojan:   { icon:'ti-shield-lock',    title:'Trojan',         desc:'شبیه‌سازی ترافیک HTTPS معمولی' },
  shadowsocks: { icon:'ti-shield-lock-filled', title:'Shadowsocks', desc:'رمزنگاری AEAD مستقیم، بدون نیاز به TLS خارجی' },
  telproxy: { icon:'ti-brand-telegram', title:'Telegram Proxy', desc:'پروکسی MTProto مستقیم روی یک پورت TCP اختصاصی' },
};
const TRANSPORT_INFO = {
  'ws':               { icon:'ti-link',    title:'WebSocket',            desc:'پایدار و سازگار با همه شرایط شبکه' },
  'xhttp-packet-up':  { icon:'ti-package', title:'XHTTP · packet-up',    desc:'سازگاری بالا با CDN و پروکسی‌ها' },
  'xhttp-stream-up':  { icon:'ti-rocket',  title:'XHTTP · stream-up',    desc:'تاخیر پایین‌تر برای اتصال‌های پرسرعت' }
};

function cmSelectBase(val, el){
  cmBase = val;
  document.querySelectorAll('#dd-base .cm-opt').forEach(o => o.classList.remove('sel'));
  el.classList.add('sel');
  const info = BASE_INFO[val];
  document.getElementById('dd-base-icon').innerHTML = `<i class="ti ${info.icon}"></i>`;
  document.getElementById('dd-base-current').textContent = info.title;
  document.getElementById('dd-base-current-desc').textContent = info.desc;
  cmToggleDD('dd-base');

  // ریست ترابرد به WS هر بار که پروتکل پایه عوض می‌شه (جلوگیری از state قدیمی)
  cmTransport = 'ws';
  document.querySelectorAll('#dd-transport .cm-opt').forEach(o => o.classList.remove('sel'));
  document.querySelector('#dd-transport .cm-opt[data-t="ws"]')?.classList.add('sel');
  const wsInfo = TRANSPORT_INFO['ws'];
  document.getElementById('dd-transport-icon').innerHTML = `<i class="ti ${wsInfo.icon}"></i>`;
  document.getElementById('dd-transport-current').textContent = wsInfo.title;
  document.getElementById('dd-transport-current-desc').textContent = wsInfo.desc;


  const streamSection = document.getElementById('stream-section');
  const normalNote = document.getElementById('transport-note');
  const mtNote = document.getElementById('mtproto-note');
  const portField = document.getElementById('mtproto-port-field');
  const ssField = document.getElementById('ss-cipher-field');
  const sniSpoofField = document.getElementById('sni-spoof-field');

  if (sniSpoofField) sniSpoofField.style.display = 'block';  // Always visible — disabled for MTProto/SS with explanation
  if (val === 'telproxy') {
    streamSection.style.display = 'none';
    normalNote.style.display = 'none';
    mtNote.style.display = 'flex';
    portField.style.display = 'block';
    if (ssField) ssField.style.display = 'none';
    // SNI spoofing section stays visible but disabled for MTProto
    if (sniSpoofField) {
      sniSpoofField.style.display = 'block';
      sniSpoofField.style.opacity = '0.5';
      sniSpoofField.style.pointerEvents = 'none';
      const spoofToggle = document.getElementById('nl-spoof-toggle');
      if (spoofToggle) spoofToggle.classList.remove('on');
      const spoofNote = sniSpoofField.querySelector('.cm-note');
      if (spoofNote) spoofNote.innerHTML = '<i class="ti ti-info-circle"></i> <span>MTProto از FakeTLS خودش استفاده می‌کند — SNI spoofing قابل استفاده نیست.</span>';
    }
    document.getElementById('cm-head-title').textContent = 'ساخت پروکسی جدید';
    document.getElementById('cm-head-sub').textContent = 'ساخت پروکسی تلگرام (MTProto) با پورت TCP اختصاصی';
    document.getElementById('cm-submit-text').textContent = 'ساخت پروکسی';
    document.getElementById('cm-head-icon').innerHTML = '<i class="ti ti-brand-telegram"></i>';
  } else if (val === 'shadowsocks') {
    cmTransport = 'ws';
    streamSection.style.display = 'none';
    normalNote.style.display = 'flex';
    mtNote.style.display = 'none';
    portField.style.display = 'none';
    if (ssField) ssField.style.display = 'block';
    // SNI spoofing section stays visible but disabled for SS
    if (sniSpoofField) {
      sniSpoofField.style.display = 'block';
      sniSpoofField.style.opacity = '0.5';
      sniSpoofField.style.pointerEvents = 'none';
      const spoofToggle = document.getElementById('nl-spoof-toggle');
      if (spoofToggle) spoofToggle.classList.remove('on');
      const spoofNote = sniSpoofField.querySelector('.cm-note');
      if (spoofNote) spoofNote.innerHTML = '<i class="ti ti-info-circle"></i> <span>Shadowsocks از v2ray-plugin استفاده می‌کند که host= را برای WS Host و TLS SNI به‌طور مشترک استفاده می‌کند — SNI spoofing قابل استفاده نیست.</span>';
    }
    document.getElementById('cm-head-title').textContent = 'ساخت کانفیگ Shadowsocks';
    document.getElementById('cm-head-sub').textContent = 'رمزنگاری AEAD، پسورد به‌صورت خودکار ساخته می‌شود';
    document.getElementById('cm-submit-text').textContent = 'ساخت کانفیگ';
    document.getElementById('cm-head-icon').innerHTML = '<i class="ti ti-shield-lock-filled"></i>';
  } else {
    streamSection.style.display = '';
    normalNote.style.display = 'flex';
    mtNote.style.display = 'none';
    portField.style.display = 'none';
    if (ssField) ssField.style.display = 'none';
    // VLESS + Trojan (WS/XHTTP) — SNI spoofing fully enabled
    if (sniSpoofField) {
      sniSpoofField.style.display = 'block';
      sniSpoofField.style.opacity = '1';
      sniSpoofField.style.pointerEvents = 'auto';
      const spoofNote = sniSpoofField.querySelector('.cm-note');
      if (spoofNote) spoofNote.innerHTML = '<i class="ti ti-info-circle"></i> <span>SNI جعلی در هندشیک TLS ارسال می‌شود. دامنه باید واقعی و روی CDN قابل resolve باشد.</span>';
    }
    document.getElementById('cm-head-title').textContent = 'ساخت کانفیگ جدید';
    document.getElementById('cm-head-sub').textContent = 'تنظیمات کامل پروتکل، ترابرد و محدودیت‌ها در یک صفحه';
    document.getElementById('cm-submit-text').textContent = 'ساخت کانفیگ';
    document.getElementById('cm-head-icon').innerHTML = '<i class="ti ti-square-rounded-plus"></i>';
  }
  cmApplyProto();
}
function cmSelectTransport(val, el){
  // Phase 37.18: gate against the backend compatibility matrix FIRST —
  // an impossible combination never reaches the API.
  const gateProto = (cmBase === 'telproxy') ? 'mtproto'
    : (cmBase === 'shadowsocks') ? 'shadowsocks' : cmBase;
  if (!cmGateCombo(gateProto, val)) return;
  cmTransport = val;
  document.querySelectorAll('#dd-transport .cm-opt').forEach(o => o.classList.remove('sel'));
  el.classList.add('sel');
  const info = TRANSPORT_INFO[val];
  document.getElementById('dd-transport-icon').innerHTML = `<i class="ti ${info.icon}"></i>`;
  document.getElementById('dd-transport-current').textContent = info.title;
  document.getElementById('dd-transport-current-desc').textContent = info.desc;
  cmToggleDD('dd-transport');
  cmApplyProto();
}
function cmApplyProto(){
  if (cmBase === 'telproxy') {
    document.getElementById('nl-proto').value = 'mtproto';
    return;
  }
  if (cmBase === 'shadowsocks') {
    const val = cmTransport === 'ws' ? 'shadowsocks' : `shadowsocks-${cmTransport}`;
    document.getElementById('nl-proto').value = val;
    return;
  }
  const val = cmTransport === 'ws'
    ? (cmBase === 'trojan' ? 'trojan-ws' : 'vless-ws')
    : (cmBase === 'trojan' ? `trojan-${cmTransport}` : cmTransport);
  document.getElementById('nl-proto').value = val;
}

/* ── سهمیه ترافیک و انقضا: هم با پیل، هم با تایپ مستقیم قابل تنظیم‌اند ── */
function cmQuota(val, unit, el){
  document.getElementById('nl-val').value = val === 0 ? '' : val;
  document.getElementById('nl-unit').value = unit;
  el.parentElement.querySelectorAll('.cm-pill').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}
function cmExpiry(days, el){
  document.getElementById('nl-exp').value = days === 0 ? '' : days;
  el.parentElement.querySelectorAll('.cm-pill').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}

function cmSetSni(domain, el){
  document.getElementById('nl-mtproto-domain').value = domain;
  el.parentElement.querySelectorAll('.cm-pill').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}

// ── SNI Spoofing toggle/preset helpers (per-link, opt-in) ───────────────
function cmToggleSpoof(){
  const toggle = document.getElementById('nl-spoof-toggle');
  const controls = document.getElementById('nl-spoof-controls');
  const enabledInput = document.getElementById('nl-spoof-enabled');
  const sniInput = document.getElementById('nl-spoof-sni');
  if(!toggle || !controls || !enabledInput) return;
  const isOn = toggle.classList.toggle('on');
  controls.style.display = isOn ? 'block' : 'none';
  enabledInput.value = isOn ? '1' : '0';
  if(!isOn && sniInput) sniInput.value = '';
  // Show CDN warning if SNI spoof is ON but no CDN domain configured
  cmCheckSpoofCdnWarning(isOn);
}
function cmSpoofPreset(sel){
  const v = (sel && sel.value) || '';
  if(!v) return;
  const sniInput = document.getElementById('nl-spoof-sni');
  if(sniInput) sniInput.value = v;
  sel.value = '';  // reset dropdown so user can pick again
}
function cmCheckSpoofCdnWarning(isOn){
  // Check if the link list response had cdn_domain=null — if so, show warning
  // when SNI spoof is toggled ON. We read from the first link's cdn_domain field.
  // Audit fix: `window.allLinksList` همیشه undefined بود (let در scope اسکریپت
  // propertyی window نمی‌شود) → وارنینگ همیشه نمایش داده می‌شد. حالا مستقیم
  // از متغیر scope با typeof ایمن خوانده می‌شود.
  const warn = document.getElementById('nl-spoof-cdn-warn');
  if(!warn) return;
  if(!isOn){ warn.style.display = 'none'; return; }
  // Try to read CDN domain from the first link in allLinksList
  let hasCdn = false;
  try{
    const lst = (typeof allLinksList !== 'undefined') ? allLinksList : [];
    if(lst && lst.length > 0){ hasCdn = !!lst[0].cdn_domain; }
  }catch(_e){}
  warn.style.display = hasCdn ? 'none' : 'block';
}
// ── ALPN preset helper ─────────────────────────────────────────────────
function cmAlpnPreset(alpnList, el){
  // Clear all active chips first
  document.querySelectorAll('#alpn-pills .alpn-chip').forEach(c => c.classList.remove('active'));
  // Activate the chips in the preset list
  alpnList.forEach(alpn => {
    const chip = document.querySelector(`#alpn-pills .alpn-chip[data-alpn="${alpn}"]`);
    if(chip) chip.classList.add('active');
  });
  // Update the hidden input
  cmUpdateAlpn();
  // Update pill active states
  el.parentElement.querySelectorAll('.cm-pill').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
}

function cmClearSniPills(){
  const wrap = document.getElementById('nl-mtproto-domain').closest('.cm-section').querySelector('.cm-pills');
  wrap?.querySelectorAll('.cm-pill').forEach(c => c.classList.remove('active'));
}

/* ── ALPN: چندانتخابی ── */
let cmAlpn = ['h2', 'http/1.1'];
function cmToggleAlpn(val, el){
  const idx = cmAlpn.indexOf(val);
  if(idx > -1){
    if(cmAlpn.length === 1) return; // حداقل یک ALPN باید بمونه
    cmAlpn.splice(idx, 1);
    el.classList.remove('active');
  } else {
    cmAlpn.push(val);
    el.classList.add('active');
  }
  document.getElementById('nl-alpn').value = cmAlpn.join(',');
}


function cmSetSsCipher(val, el){
  document.getElementById('nl-ss-cipher').value = val;
  el.parentElement.querySelectorAll('.cm-pill').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}

function cmSetFp(val, el){
  document.getElementById('nl-fp').value = val;
  document.querySelectorAll('#fp-pills .fp-card').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}
document.getElementById('nl-val')?.addEventListener('input', () => {
  document.querySelectorAll('#nl-val').forEach(()=>{});
  const wrap = document.getElementById('nl-val').closest('.cm-field').querySelector('.cm-pills');
  wrap?.querySelectorAll('.cm-pill').forEach(c => c.classList.remove('active'));
});
document.getElementById('nl-exp')?.addEventListener('input', () => {
  const wrap = document.getElementById('nl-exp').closest('.cm-field').querySelector('.cm-pills');
  wrap?.querySelectorAll('.cm-pill').forEach(c => c.classList.remove('active'));
});

function onNlTargetChange(){
  const targetEl=document.getElementById('nl-target');
  const nodeId=targetEl?targetEl.value:'';
  const nlSub=document.getElementById('nl-sub');
  if(nodeId){
    const node=onlineNodesList.find(n=>n.node_id===nodeId);
    const subs=(node&&node.subs)||[];
    nlSub.innerHTML='<option value="">— بدون گروه —</option>'+subs.map(s=>`<option value="${esc(s.sub_id)}">${esc(s.name)}</option>`).join('');
  }else{
    nlSub.innerHTML='<option value="">— بدون گروه —</option>'+allSubsList.map(s=>`<option value="${esc(s.sub_id)}">${esc(s.name)}</option>`).join('');
  }
  document.getElementById('nl-sub-wrap').style.display='';
}
async function createLink(){
  const label=document.getElementById('nl-label').value.trim()||'کانفیگ جدید';
  const val=document.getElementById('nl-val').value;
  const unit=document.getElementById('nl-unit').value;
  const exp=document.getElementById('nl-exp').value;
  const note=document.getElementById('nl-note').value.trim();
  const targetEl=document.getElementById('nl-target');
  const nodeId=targetEl?targetEl.value:'';
  const sub_id=document.getElementById('nl-sub').value||null;
  const protocol=document.getElementById('nl-proto').value||'vless-ws';
  const isMt = protocol === 'mtproto';
  const isSs = protocol.startsWith('shadowsocks');
  const mtproto_port = isMt ? (document.getElementById('nl-mtproto-port').value || null) : null;
  const mtproto_domain = isMt ? (document.getElementById('nl-mtproto-domain').value.trim() || null) : null;
  const mtproto_public_host = isMt ? (document.getElementById('nl-mtproto-public-host').value.trim() || null) : null;
  const mtproto_public_port = isMt ? (document.getElementById('nl-mtproto-public-port').value || null) : null;
  const alpn = (isMt || isSs) ? null : (document.getElementById('nl-alpn').value || 'h2,http/1.1');
  const fingerprint = (isMt || isSs) ? null : (document.getElementById('nl-fp').value || 'chrome');
  const ss_cipher = isSs ? (document.getElementById('nl-ss-cipher').value || 'chacha20-ietf-poly1305') : null;
  // ── SNI Spoofing (per-link, opt-in) ──────────────────────────────────
  // Only sent for VLESS/Trojan (WS/XHTTP). The backend also validates +
  // rejects invalid values, so client-side is just UX.
  let spoof_sni = null, spoof_sni_enabled = false;
  if (!isMt && !isSs) {
    const spoofEnabledEl = document.getElementById('nl-spoof-enabled');
    const spoofSniEl = document.getElementById('nl-spoof-sni');
    if (spoofEnabledEl && spoofEnabledEl.value === '1' && spoofSniEl) {
      spoof_sni = spoofSniEl.value.trim();
      spoof_sni_enabled = !!spoof_sni;
      if (spoof_sni_enabled && !spoof_sni) {
        toast('یک دامنه‌ی SNI معتبر وارد کنید', 'err'); return;
      }
    }
  }
  try{
    const url = nodeId ? ('/api/nodes/'+nodeId+'/links') : '/api/links';
    const r=await authF(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({label,limit_value:val||0,limit_unit:unit,expires_days:exp||0,note,sub_id,protocol,mtproto_port,mtproto_domain,mtproto_public_host,mtproto_public_port,alpn,fingerprint,ss_cipher,spoof_sni,spoof_sni_enabled})});
    if(!r.ok){
      const d=await r.json().catch(()=>({}));
      throw new Error(d.detail||'failed');
    }
    ['nl-label','nl-val','nl-exp','nl-note','nl-mtproto-port','nl-mtproto-domain','nl-mtproto-public-host','nl-mtproto-public-port','nl-spoof-sni'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});
    // Reset SNI spoofing toggle to OFF after successful submit
    const spoofToggle=document.getElementById('nl-spoof-toggle');
    const spoofControls=document.getElementById('nl-spoof-controls');
    const spoofEnabledInput=document.getElementById('nl-spoof-enabled');
    if(spoofToggle){spoofToggle.classList.remove('on');}
    if(spoofControls){spoofControls.style.display='none';}
    if(spoofEnabledInput){spoofEnabledInput.value='0';}
    toast(isMt ? 'پروکسی ساخته شد ✓' : (nodeId?'کانفیگ روی نود ساخته شد ✓':'کانفیگ ساخته شد ✓'),'ok');
    loadLinks();
  }catch(e){toast('✗ '+(e.message||'خطا (شاید کلید این نود اجازه‌ی ساخت از راه دور ندارد)'),'err')}
}


function openEditLink(uuid,nodeId){
  const l=allLinksList.find(x=>x.uuid===uuid&&(nodeId?x._nodeId===nodeId:!x._nodeId));
  if(!l)return;
  document.getElementById('el-uuid').value=uuid;
  document.getElementById('el-node-id').value=nodeId||'';
  const notice=document.getElementById('el-node-notice');
  if(nodeId){ notice.style.display=''; notice.innerHTML=`<span class="node-origin"><i class="ti ti-topology-star-3"></i> ویرایش از راه دور روی نود: ${esc(l._nodeName)}</span>`; }
  else notice.style.display='none';
  document.getElementById('el-label').value=l.label;
  document.getElementById('el-note').value=l.note||'';
  if(l.limit_bytes===0){document.getElementById('el-val').value='';document.getElementById('el-unit').value='GB';}
  else{document.getElementById('el-val').value=(l.limit_bytes/1024/1024).toFixed(0);document.getElementById('el-unit').value='MB';}
  document.getElementById('el-exp').value='';
  openModal('modal-edit-link');
}
async function saveEditLink(){
  const uuid=document.getElementById('el-uuid').value;
  const nodeId=document.getElementById('el-node-id').value||null;
  const label=document.getElementById('el-label').value.trim();
  const note=document.getElementById('el-note').value.trim();
  const val=document.getElementById('el-val').value;
  const unit=document.getElementById('el-unit').value;
  const exp=document.getElementById('el-exp').value;
  const body={label,note,limit_value:val||0,limit_unit:unit};
  if(exp&&Number(exp)>0)body.expires_days=Number(exp);
  try{
    const r=await authF(linkApiBase(nodeId)+uuid,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||'');
    closeModal('modal-edit-link');
    toast('کانفیگ ویرایش شد ✓','ok');loadLinks();
  }catch(e){toast(e.message||'خطا در ویرایش (شاید کلید این نود اجازه‌ی ویرایش از راه دور ندارد)','err')}
}
function linkApiBase(nodeId){ return nodeId? ('/api/nodes/'+nodeId+'/links/') : '/api/links/'; }
async function toggleActive(uuid,newState,nodeId){
  try{const r=await authF(linkApiBase(nodeId)+uuid,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({active:newState})});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||'');toast(newState?'فعال شد ✓':'غیرفعال شد','ok');loadLinks();}catch(e){toast(e.message||'خطا (شاید کلید این نود اجازه‌ی ویرایش ندارد)','err')}
}
async function resetUsage(uuid,nodeId){
  try{const r=await authF(linkApiBase(nodeId)+uuid,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({reset_usage:true})});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||'');toast('مصرف ریست شد ✓','ok');loadLinks();}catch(e){toast(e.message||'خطا (شاید کلید این نود اجازه‌ی ویرایش از راه دور ندارد)','err')}
}
let atCurrentUuid = null;

function openAdTagModal(uuid, label, currentTag){
  atCurrentUuid = uuid;
  document.getElementById('at-cfg-name').textContent = label;
  document.getElementById('at-tag').value = currentTag || '';
  openModal('modal-ad-tag');
  setTimeout(()=>document.getElementById('at-tag').focus(), 150);
}

function mtPlainSecret(fullSecret){
  if (!fullSecret) return '';
  // فرمت mtg: "ee" + 32 کاراکتر هگز سکرت + دامنه‌ی fake-TLS به‌صورت هگز
  if (fullSecret.startsWith('ee') && fullSecret.length > 34) {
    return fullSecret.slice(2, 34);
  }
  return fullSecret;
}

function openMtInfoModal(label, secret, fullLink, hasPublicHost){
  document.getElementById('mti-cfg-name').textContent = label;
  document.getElementById('mti-secret').textContent = mtPlainSecret(secret) || '—';
  document.getElementById('mti-link').textContent = fullLink || '—';
  const warnEl = document.getElementById('mti-warn');
  if (warnEl) warnEl.style.display = hasPublicHost ? 'none' : 'flex';
  openModal('modal-mt-info');
}

function cpMtiField(id, msg){
  const el = document.getElementById(id);
  navigator.clipboard.writeText(el.textContent).then(()=>toast(msg,'ok'));
}

async function submitAdTag(){
  if(!atCurrentUuid) return;
  const tag = document.getElementById('at-tag').value.trim();
  if(!tag){ toast('ad_tag نمی‌تواند خالی باشد','err'); return; }

  const btn = document.getElementById('at-submit-btn');
  btn.disabled = true;
  btn.innerHTML = '<i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال اعمال...';

  try{
    const r = await authF('/api/links/'+atCurrentUuid+'/ad-tag', {
      method:'PATCH', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ad_tag: tag})
    });
    if(!r.ok){ const d = await r.json().catch(()=>({})); throw new Error(d.detail || 'خطا'); }
    closeModal('modal-ad-tag');
    toast('تبلیغ ثبت شد، پروکسی در حال ری‌استارت است...','ok');
    setTimeout(loadLinks, 2000);
  }catch(e){
    toast('✗ '+e.message,'err');
  }
  btn.disabled = false;
  btn.innerHTML = '<i class="ti ti-check"></i> ذخیره و اعمال';
}
async function deleteLink(uuid,nodeId){
  if(!confirm('حذف این کانفیگ؟'))return;
  try{const r=await authF(linkApiBase(nodeId)+uuid,{method:'DELETE'});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||'');toast('حذف شد ✓','ok');loadLinks();}catch(e){toast(e.message||'خطا (شاید کلید این نود اجازه‌ی حذف ندارد)','err')}
}
function showQR(link){window.open('/api/qr?data='+encodeURIComponent(link),'_blank')}
let allSubsRaw=[];
async function loadSubs(){
  try{
    const [sr,nr]=await Promise.all([authF('/api/subs'),authF('/api/nodes/aggregate').catch(()=>null)]);
    const d=await sr.json();
    const subs=d.subs||[];
    let nodeSubs=[];
    if(nr && nr.ok){
      try{
        const nd=await nr.json();
        (nd.nodes||[]).forEach(n=>{
          if(n.disabled||!n.online) return;
          (n.subs||[]).forEach(s=>nodeSubs.push({...s,_nodeId:n.node_id,_nodeName:n.label||'نود'}));
        });
      }catch(e){}
    }
    const all=[...subs,...nodeSubs];
    allSubsRaw=all;
    document.getElementById('subs-nb').textContent=all.length;
    document.getElementById('subs-pg-cnt').textContent=toFa(all.length)+' گروه';
    renderSubsGrid(all);
  }catch(e){console.error(e)}
}
function renderSubsGrid(subs){
  const grid=document.getElementById('subs-grid');
  if(!subs.length){
    grid.innerHTML='<div class="subs-empty-v2"><div class="subs-empty-v2-icon"><i class="ti ti-folders"></i></div><div class="subs-empty-v2-title">هنوز گروهی وجود ندارد</div><div class="subs-empty-v2-sub">یک گروه جدید بسازید تا کانفیگ‌ها را دسته‌بندی کنید</div></div>';
    return;
  }
  grid.innerHTML=subs.map(s=>{
    const isNode=!!s._nodeId;
    const nodeBadge=isNode?`<span class="sub-card-lock-badge open" style="background:var(--purple-bg,rgba(168,85,247,.14));color:var(--purple,#FACC15)" title="نود: ${esc(s._nodeName)}"><i class="ti ti-topology-star-3"></i></span>`:'';
    return `
    <div class="sub-card">
      <div class="sub-card-top">
        <div class="sub-card-head-v2">
          <div class="sub-card-icon"><i class="ti ti-folder"></i></div>
          <div class="sub-card-titles">
            <div class="sub-card-name-v2">${esc(s.name)}</div>
            ${isNode?`<div class="sub-card-desc-v2" style="color:var(--purple-t,#A5F3FC)"><i class="ti ti-topology-star-3" style="font-size:10px"></i> نود: ${esc(s._nodeName)}</div>`:(s.desc?`<div class="sub-card-desc-v2">${esc(s.desc)}</div>`:'<div class="sub-card-desc-v2" style="opacity:.5">بدون توضیحات</div>')}
          </div>
          ${isNode?nodeBadge:`<div class="sub-card-lock-badge ${s.has_password?'locked':'open'}" title="${s.has_password?'رمزدار':'پابلیک'}">
            <i class="ti ${s.has_password?'ti-lock':'ti-lock-open'}"></i>
          </div>`}
        </div>
        <div class="sub-card-stats">
          <div class="sub-card-stat"><div class="sub-card-stat-val">${toFa(s.links_count)}</div><div class="sub-card-stat-label">کانفیگ</div></div>
          <div class="sub-card-stat"><div class="sub-card-stat-val" style="color:var(--green-t)">${toFa(s.active_count)}</div><div class="sub-card-stat-label">فعال</div></div>
          <div class="sub-card-stat"><div class="sub-card-stat-val" style="font-size:12px">${esc(s.total_used_fmt)}</div><div class="sub-card-stat-label">مصرف</div></div>
        </div>
      </div>
      <div class="sub-card-url-row">
        <span class="sub-card-url-text">${esc(s.public_url)}</span>
        <button class="sub-card-url-copy" onclick="navigator.clipboard.writeText('${esc(s.public_url)}').then(()=>toast('لینک پابلیک کپی شد','ok'))" title="کپی"><i class="ti ti-copy"></i></button>
        <button class="sub-card-url-copy" onclick="window.open('${esc(s.public_url)}','_blank')" title="باز کردن"><i class="ti ti-external-link"></i></button>
      </div>
      <div class="sub-card-bottom">
        <button class="btn btn-sm btn-g" onclick="openSubLinks('${esc(s.sub_id)}','${esc(s.name)}','${esc(s._nodeId||'')}')"><i class="ti ti-link-plus"></i> کانفیگ‌ها</button>
        ${isNode?`<button class="btn btn-sm btn-g btn-icon" onclick="openEditSubModal('${esc(s.sub_id)}','${esc(s._nodeId)}')" title="ویرایش"><i class="ti ti-edit"></i></button>`:''}
        <button class="btn btn-sm btn-o" onclick="navigator.clipboard.writeText('${esc(s.sub_url)}').then(()=>toast('لینک ساب کپی شد','ok'))"><i class="ti ti-rss"></i> ساب</button>
        <button class="btn btn-sm btn-g btn-icon" onclick="showQR('${esc(s.sub_url)}')" title="QR"><i class="ti ti-qrcode"></i></button>
        <button class="btn btn-sm btn-d btn-icon" onclick="deleteSub('${esc(s.sub_id)}','${esc(s._nodeId||'')}')" title="حذف"><i class="ti ti-trash"></i></button>
      </div>
    </div>
  `;}).join('');
}
function filterSubs(q){
  q=q.trim().toLowerCase();
  if(!q){renderSubsGrid(allSubsRaw);return}
  renderSubsGrid(allSubsRaw.filter(s=>s.name.toLowerCase().includes(q)||(s.desc||'').toLowerCase().includes(q)));
}
function openCreateSubModal(){
  const targetEl=document.getElementById('ns-target'), wrap=document.getElementById('ns-target-wrap');
  if(targetEl){
    targetEl.innerHTML='<option value="">این پنل</option>'+onlineNodesList.map(n=>`<option value="${esc(n.node_id)}">${esc(n.label||'نود')}</option>`).join('');
    if(wrap) wrap.style.display = onlineNodesList.length ? '' : 'none';
  }
  openModal('modal-create-sub');
}
async function createSub(){
  const name=document.getElementById('ns-name').value.trim()||'گروه جدید';
  const desc=document.getElementById('ns-desc').value.trim();
  const pw=document.getElementById('ns-pw').value;
  const targetEl=document.getElementById('ns-target');
  const nodeId=targetEl?targetEl.value:'';
  try{
    const url = nodeId ? ('/api/nodes/'+nodeId+'/subs') : '/api/subs';
    const r=await authF(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,desc,password:pw})});
    if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(d.detail||'failed')}
    ['ns-name','ns-desc','ns-pw'].forEach(id=>document.getElementById(id).value='');
    closeModal('modal-create-sub');
    toast(nodeId?'گروه روی نود ساخته شد ✓':'گروه ساخته شد ✓','ok');
    loadSubs();
  }catch(e){toast('خطا در ساخت گروه: '+(e.message||''),'err')}
}
async function deleteSub(sub_id,nodeId){
  if(!confirm('حذف این گروه؟ کانفیگ‌ها حذف نمی‌شوند.'))return;
  try{
    const url = nodeId ? ('/api/nodes/'+nodeId+'/subs/'+sub_id) : ('/api/subs/'+sub_id);
    const r=await authF(url,{method:'DELETE'});
    if(!r.ok)throw new Error();
    toast('گروه حذف شد ✓','ok');loadSubs();loadLinks();
    if(document.getElementById('pg-subscriptions')?.classList.contains('on'))loadSubsPage();
  }catch(e){toast('خطا','err')}
}
function openEditSubModal(sub_id,nodeId){
  const s=allSubsRaw.find(x=>x.sub_id===sub_id&&(x._nodeId||'')===(nodeId||''));
  if(!s)return;
  const name=prompt('نام جدید گروه:',s.name);
  if(name===null)return;
  const desc=prompt('توضیحات (اختیاری):',s.desc||'')||'';
  editSubMeta(sub_id,nodeId,name.trim()||s.name,desc.trim());
}
async function editSubMeta(sub_id,nodeId,name,desc){
  try{
    const url = nodeId ? ('/api/nodes/'+nodeId+'/subs/'+sub_id) : ('/api/subs/'+sub_id);
    const r=await authF(url,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,desc})});
    if(!r.ok)throw new Error();
    toast('گروه بروزرسانی شد ✓','ok');loadSubs();
  }catch(e){toast('خطا در ویرایش گروه','err')}
}
let lmodalLinks=[],lmodalNodeLinks=[],lmodalInSub=new Set(),currentSubNodeId='';
async function openSubLinks(sub_id,name,nodeId){
  currentSubId=sub_id;
  currentSubNodeId=nodeId||'';
  document.getElementById('modal-sub-name').textContent=name+(currentSubNodeId?' (نود)':'');
  document.getElementById('modal-links-body').innerHTML='<div style="color:var(--t3);font-size:12px;padding:20px;text-align:center"><i class="ti ti-loader-2" style="animation:spin 1s linear infinite;font-size:20px"></i></div>';
  document.getElementById('lmodal-search-inp').value='';
  openModal('modal-links');
  if(currentSubNodeId){
    // گروهِ متعلق به یک نود: کانفیگ‌های خودِ آن نود + همه‌ی کانفیگ‌های پنل مرکزی و سایر نودها هم قابل افزودن‌اند
    try{
      const [lr,nr]=await Promise.all([authF('/api/links'),authF('/api/nodes/aggregate')]);
      const {links: centralLinks=[]}=await lr.json();
      const nd=await nr.json();
      const targetNode=(nd.nodes||[]).find(n=>n.node_id===currentSubNodeId);
      const thisSub=(targetNode&&targetNode.subs||[]).find(s=>s.sub_id===sub_id);
      const ownKeys=(thisSub?.link_ids||[]).map(u=>currentSubNodeId+'::'+u);
      const foreignKeys=(thisSub?.foreign_links||[]).map(fl=>fl.key).filter(Boolean);
      lmodalInSub=new Set([...ownKeys,...foreignKeys]);
      lmodalLinks=[];
      lmodalNodeLinks=[
        ...centralLinks.map(l=>({...l,node_id:'local',node_label:'این پنل'})),
        ...(nd.nodes||[]).filter(n=>!n.disabled&&n.online).flatMap(n=>(n.links||[]).map(l=>({...l,node_id:n.node_id,node_label:(n.node_id===currentSubNodeId?'این نود · ':'')+(n.label||'نود')})))
      ];
      renderLmodalList();
    }catch(e){toast('خطا در بارگذاری','err')}
    return;
  }
  try{
    const [lr,sr,nr]=await Promise.all([authF('/api/links'),authF('/api/subs'),authF('/api/nodes/aggregate').catch(()=>null)]);
    const {links=[]}=await lr.json();
    const {subs=[]}=await sr.json();
    const thisSub=subs.find(s=>s.sub_id===sub_id);
    lmodalInSub=new Set([...(thisSub?.link_ids||[]),...(thisSub?.node_link_ids||[])]);
    lmodalLinks=links;
    lmodalNodeLinks=[];
    if(nr){
      const nd=await nr.json().catch(()=>null);
      (nd?.nodes||[]).forEach(n=>{
        if(!n.online||!(n.links||[]).length)return;
        n.links.forEach(l=>lmodalNodeLinks.push({...l,node_id:n.node_id,node_label:n.label}));
      });
    }
    renderLmodalList();
  }catch(e){toast('خطا در بارگذاری','err')}
}
function renderLmodalList(){
  const body=document.getElementById('modal-links-body');
  const localItems=lmodalLinks.map(l=>({key:l.uuid,label:l.label,protocol:l.protocol,used_bytes:l.used_bytes,active:l.active,expired:l.expired,nodeLabel:null}));
  const nodeItems=lmodalNodeLinks.map(l=>({key:l.node_id+'::'+l.uuid,label:l.label,protocol:l.protocol,used_bytes:l.used_bytes,active:l.active,expired:l.expired,nodeLabel:l.node_label}));
  const all=[...localItems,...nodeItems];
  if(!all.length){body.innerHTML='<div class="empty" style="padding:30px"><i class="ti ti-link-off"></i><p>هنوز کانفیگی وجود ندارد</p></div>';updateLmodalCount();return}
  const protoIcon=p=>p==='mtproto'?'ti-brand-telegram':p&&p.startsWith('shadowsocks')?'ti-shield-lock-filled':p&&p.startsWith('trojan')?'ti-shield-lock':p&&p.includes('xhttp')?'ti-bolt':'ti-link';
  body.innerHTML=all.map(l=>{
    const checked=lmodalInSub.has(l.key);
    const on=l.active&&!l.expired;
    const nodeBadge=l.nodeLabel?`<span class="lrow-v2-status" style="background:var(--purple-bg,rgba(168,85,247,.14));color:var(--purple,#FACC15);margin-left:4px"><i class="ti ti-topology-star-3" style="font-size:9px"></i> ${esc(l.nodeLabel)}</span>`:'';
    return `<div class="lrow-v2 ${checked?'checked':''}" data-key="${esc(l.key)}" data-name="${esc(l.label).toLowerCase()}" onclick="toggleLrow('${esc(l.key)}',this)">
      <div class="lrow-v2-check"><i class="ti ti-check"></i></div>
      <div class="lrow-v2-avatar"><i class="ti ${protoIcon(l.protocol)}"></i></div>
      <div class="lrow-v2-info">
        <div class="lrow-v2-name">${esc(l.label)}</div>
        <div class="lrow-v2-meta"><i class="ti ti-database" style="font-size:10px"></i> ${fmtB(l.used_bytes)}</div>
      </div>
      ${nodeBadge}
      <span class="lrow-v2-status ${on?'on':'off'}">${on?'فعال':'غیرفعال'}</span>
    </div>`;
  }).join('');
  updateLmodalCount();
}
function toggleLrow(key,el){
  if(lmodalInSub.has(key)){lmodalInSub.delete(key);el.classList.remove('checked')}
  else{lmodalInSub.add(key);el.classList.add('checked')}
  updateLmodalCount();
}
function lmodalSelectAll(state){
  lmodalLinks.forEach(l=>{if(state)lmodalInSub.add(l.uuid);else lmodalInSub.delete(l.uuid)});
  lmodalNodeLinks.forEach(l=>{const k=l.node_id+'::'+l.uuid;if(state)lmodalInSub.add(k);else lmodalInSub.delete(k)});
  renderLmodalList();
}
function updateLmodalCount(){
  const el=document.getElementById('lmodal-count');
  if(el)el.textContent=toFa(lmodalInSub.size)+' انتخاب شده';
}
function filterLmodal(q){
  q=q.trim().toLowerCase();
  document.querySelectorAll('#modal-links-body .lrow-v2').forEach(row=>{
    row.style.display = !q || row.dataset.name.includes(q) ? '' : 'none';
  });
}
async function saveSubLinks(){
  if(!currentSubId)return;
  if(currentSubNodeId){
    const selected=[...lmodalInSub];
    const own=[], foreign=[];
    selected.forEach(key=>{
      const idx=key.indexOf('::');
      if(idx<0)return;
      const nid=key.slice(0,idx), uid=key.slice(idx+2);
      if(nid===currentSubNodeId){ own.push(uid); return; }
      const item=lmodalNodeLinks.find(l=>l.node_id===nid&&l.uuid===uid);
      if(!item||!item.vless_link)return;
      foreign.push({key,label:item.label,vless_link:item.vless_link,used_bytes:item.used_bytes||0,source:item.node_label||''});
    });
    try{
      const r=await authF('/api/nodes/'+currentSubNodeId+'/subs/'+currentSubId,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({link_ids:own,foreign_links:foreign})});
      if(!r.ok)throw new Error();
      closeModal('modal-links');
      toast('کانفیگ‌های گروه ذخیره شدند ✓','ok');
      loadSubs();loadLinks();
    }catch(e){toast('خطا در ذخیره','err')}
    return;
  }
  const allKeys=[...lmodalInSub];
  const link_ids=allKeys.filter(k=>!k.includes('::'));
  const node_link_ids=allKeys.filter(k=>k.includes('::'));
  try{
    const r=await authF('/api/subs/'+currentSubId,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({link_ids,node_link_ids})});
    if(!r.ok)throw new Error();
    await Promise.all(lmodalLinks.map(l=>
      authF('/api/links/'+l.uuid,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({sub_id:lmodalInSub.has(l.uuid)?currentSubId:null})})
    ));
    closeModal('modal-links');
    toast('کانفیگ‌های گروه ذخیره شدند ✓','ok');
    loadSubs();loadLinks();
  }catch(e){toast('خطا در ذخیره','err')}
}
async function loadSubsPage(){
  document.getElementById('sub-all-url').textContent=location.protocol+'//'+location.host+'/sub-all';
  try{
    const [sr,nr]=await Promise.all([authF('/api/subs'),authF('/api/nodes/aggregate').catch(()=>null)]);
    const d=await sr.json();
    const subs=d.subs||[];
    let nodeSubs=[];
    if(nr && nr.ok){
      try{
        const nd=await nr.json();
        (nd.nodes||[]).forEach(n=>{
          if(n.disabled||!n.online) return;
          (n.subs||[]).forEach(s=>nodeSubs.push({...s,_nodeId:n.node_id,_nodeName:n.label||'نود'}));
        });
      }catch(e){}
    }
    const all=[...subs,...nodeSubs];
    const el=document.getElementById('sub-groups-list');
    if(!all.length){el.innerHTML='<div class="empty"><i class="ti ti-rss-off"></i><p>هنوز گروهی ندارید</p></div>';return}
    el.innerHTML=all.map(s=>{
      const isNode=!!s._nodeId;
      const nodeTag=isNode?` <span style="color:var(--purple-t,#A5F3FC)"><i class="ti ti-topology-star-3" style="font-size:10px"></i> نود: ${esc(s._nodeName)}</span>`:'';
      return `
      <div style="padding:13px 15px;background:var(--accent-d);border:1px solid var(--card-b);border-radius:10px;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap">
        <div>
          <div style="font-weight:700;font-size:13px;margin-bottom:3px">${esc(s.name)}${nodeTag}</div>
          <div style="font-family:ui-monospace,monospace;font-size:10px;color:#FFB199">${esc(s.sub_url)}</div>
          <div style="font-size:10px;color:var(--t3);margin-top:3px">${toFa(s.links_count)} کانفیگ · ${esc(s.total_used_fmt)} مصرف ${s.has_password?'· 🔒 رمزدار':''}</div>
        </div>
        <div style="display:flex;gap:5px;flex-wrap:wrap">
          <button class="btn btn-sm btn-pur" onclick="navigator.clipboard.writeText('${esc(s.sub_url)}').then(()=>toast('کپی شد','ok'))"><i class="ti ti-copy"></i> ساب</button>
          <button class="btn btn-sm btn-pur" onclick="navigator.clipboard.writeText('${esc(s.public_url)}').then(()=>toast('کپی شد','ok'))"><i class="ti ti-globe"></i> پابلیک</button>
          <button class="btn btn-sm btn-g" onclick="showQR('${esc(s.sub_url)}')"><i class="ti ti-qrcode"></i></button>
          <button class="btn btn-sm btn-d btn-icon" onclick="deleteSub('${esc(s.sub_id)}','${esc(s._nodeId||'')}')" title="حذف"><i class="ti ti-trash"></i></button>
        </div>
      </div>
    `;}).join('');
  }catch(e){netErr(e,'سابسکریپشن‌ها')}
}
function cpSubAll(){navigator.clipboard.writeText(location.protocol+'//'+location.host+'/sub-all').then(()=>toast('کپی شد ✓','ok'))}
function parseBytesFmt(s){
  if(!s)return 0;
  const m=String(s).match(/([\d.]+)\s*([A-Za-z]+)/);
  if(!m)return 0;
  const n=parseFloat(m[1]),u=m[2].toUpperCase();
  const mult={B:1,KB:1024,MB:1024**2,GB:1024**3,TB:1024**4};
  return n*(mult[u]||1);
}
async function loadConns(){
  try{
    const r=await authF('/api/connections'),d=await r.json();
    const grid=document.getElementById('conns-grid'),ce=document.getElementById('conns-empty');
    document.getElementById('conns-live').innerHTML='<span class="dot dg pulse"></span> '+d.count+' اتصال';
    document.getElementById('ch-count').textContent=toFa(d.count);
    const conns=d.connections||[];
    if(!d.count){
      grid.innerHTML='';ce.style.display='block';
      document.getElementById('ch-traffic').textContent='—';
      document.getElementById('ch-avgdur').textContent='—';
      document.getElementById('ch-uniq').textContent='—';
      return;
    }
    ce.style.display='none';
    const totalBytes=conns.reduce((s,c)=>s+parseBytesFmt(c.bytes_fmt),0);
    document.getElementById('ch-traffic').textContent=fmtB(totalBytes);
    const uniqIps=new Set(conns.map(c=>c.ip)).size;
    document.getElementById('ch-uniq').textContent=toFa(uniqIps);
    const durs=conns.map(c=>c.connected_at?Math.max(0,Math.floor((Date.now()-new Date(c.connected_at).getTime())/1000)):0);
    const avgSec=durs.length?Math.floor(durs.reduce((a,b)=>a+b,0)/durs.length):0;
    document.getElementById('ch-avgdur').textContent=avgSec<60?avgSec+' ث':avgSec<3600?Math.floor(avgSec/60)+' د':Math.floor(avgSec/3600)+' س';
    const maxDur=Math.max(...durs,1);
    grid.innerHTML=conns.map(c=>{
      const secs=c.connected_at?Math.max(0,Math.floor((Date.now()-new Date(c.connected_at).getTime())/1000)):0;
      const dur=secs<60?secs+' ثانیه':secs<3600?Math.floor(secs/60)+' دقیقه':Math.floor(secs/3600)+' ساعت';
      const durPct=Math.min(100,Math.round((secs/maxDur)*100));
      const protoVal=c.transport==='vless-ws'?'vless-ws':(c.transport||'').replace('xhttp-','xhttp-');
      return `<div class="conn-card-v2">
        <div class="conn-card-v2-glow"></div>
        <div class="conn-card-v2-top">
          <div class="conn-avatar"><i class="ti ti-device-desktop"></i></div>
          <div class="conn-card-v2-id">
            <div class="conn-ip-v2">${esc(c.ip)}
              <button class="conn-ip-copy" onclick="navigator.clipboard.writeText('${esc(c.ip)}').then(()=>toast('IP کپی شد','ok'))" title="کپی IP"><i class="ti ti-copy"></i></button>
            </div>
            <div class="conn-label-v2">${esc(c.label)}</div>
          </div>
          <span class="conn-status-pill"><span class="dot dg pulse"></span> زنده</span>
        </div>
        <div class="conn-card-v2-divider"></div>
        <div class="conn-card-v2-body">
          <div class="conn-proto-row">${protoBadge(protoVal)}</div>
          <div class="conn-stat-row">
            <div class="conn-stat-box">
              <div class="conn-stat-icon"><i class="ti ti-transfer"></i></div>
              <div>
                <div class="conn-stat-text-label">ترافیک</div>
                <div class="conn-stat-text-val">${esc(c.bytes_fmt)}</div>
              </div>
            </div>
            <div class="conn-stat-box">
              <div class="conn-stat-icon time"><i class="ti ti-clock"></i></div>
              <div>
                <div class="conn-stat-text-label">مدت اتصال</div>
                <div class="conn-stat-text-val">${dur}</div>
              </div>
            </div>
          </div>
          <div class="conn-duration-track"><div class="conn-duration-fill" style="width:${durPct}%"></div></div>
        </div>
      </div>`;
    }).join('');
  }catch(e){console.error(e)}
}
async function loadErrs(){try{const r=await authF('/stats'),d=await r.json();renderErrs(d.recent_errors||[]);}catch(e){netErr(e,'آخرین خطاها')}}
async function fetchDefaultVless(){
  try{const r=await authF('/api/links'),d=await r.json();const links=d.links||[];const def=links.find(l=>l.limit_bytes===0&&l.active&&!l.expired)||links.find(l=>l.active&&!l.expired)||links[0];document.getElementById('vless-main').textContent=def?def.vless_link:'هنوز کانفیگی وجود ندارد';}catch(e){netErr(e,'کانفیگ پیش‌فرض')}
}
function cpText(id){navigator.clipboard.writeText(document.getElementById(id).textContent).then(()=>toast('کپی شد ✓','ok'))}
function qrFor(id){showQR(document.getElementById(id).textContent)}
function refreshAll(){fetchStats();fetchDefaultVless();loadLinks();checkVolumeBanner();if(document.getElementById('pg-subgroups').classList.contains('on'))loadSubs();if(document.getElementById('pg-subscriptions').classList.contains('on'))loadSubsPage();if(document.getElementById('pg-connections').classList.contains('on'))loadConns();if(document.getElementById('pg-logs').classList.contains('on'))loadActivity();toast('رفرش شد','ok')}
async function changePw(){
  const cur=document.getElementById('cp-cur').value,nw=document.getElementById('cp-new').value,cf=document.getElementById('cp-cf').value;
  if(!cur||!nw||!cf){toast('همه فیلدها را پر کنید','err');return}
  if(nw.length<4){toast('حداقل ۴ کاراکتر','err');return}
  if(nw!==cf){toast('تکرار رمز اشتباه','err');return}
  try{
    const r=await authF('/api/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:cur,new_password:nw})});
    const d=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(d.detail||'خطا');
    toast('رمز تغییر کرد ✓','ok');
    ['cp-cur','cp-new','cp-cf'].forEach(id=>document.getElementById(id).value='');
  }catch(e){toast('✗ '+e.message,'err')}
}
function togglePwField(id,btn){
  const inp=document.getElementById(id);
  const icon=btn.querySelector('i');
  const toText=inp.type==='password';
  inp.type=toText?'text':'password';
  icon.className='ti '+(toText?'ti-eye-off':'ti-eye');
}
function checkPwStrength(val){
  const segs=document.querySelectorAll('#pw-strength-bar .pw-strength-seg');
  const label=document.getElementById('pw-strength-label');
  const reqLen=document.getElementById('req-len'),reqNum=document.getElementById('req-num'),reqCase=document.getElementById('req-case');
  const hasLen=val.length>=4,hasNum=/\d/.test(val),hasCase=/[a-z]/.test(val)&&/[A-Z]/.test(val),hasLong=val.length>=8;
  reqLen.classList.toggle('met',hasLen);
  reqNum.classList.toggle('met',hasNum);
  reqCase.classList.toggle('met',hasCase);
  let score=0;if(hasLen)score++;if(hasNum)score++;if(hasCase)score++;if(hasLong)score++;
  const colors=['#EF4444','#F59E0B','#8B5CF6','#10B981'],labels=['خیلی ضعیف','ضعیف','متوسط','قوی'];
  segs.forEach((s,i)=>{s.style.background=i<score?colors[Math.max(0,score-1)]:'rgba(100,116,139,.2)'});
  if(val.length===0){label.innerHTML='<i class="ti ti-shield"></i> قدرت رمز';return}
  label.innerHTML=`<i class="ti ti-shield-check" style="color:${colors[Math.max(0,score-1)]}"></i> ${labels[Math.max(0,score-1)]}`;
}
function makeGradient(ctx,color1,color2){
  const g=ctx.createLinearGradient(0,0,0,260);
  g.addColorStop(0,color1);g.addColorStop(1,color2);
  return g;
}
function initCharts(){
  const c1=document.getElementById('ch1').getContext('2d');
  const grad1=makeGradient(c1,'rgba(139,92,246,.38)','rgba(139,92,246,0)');
  const opts={
    responsive:true,maintainAspectRatio:false,
    interaction:{mode:'index',intersect:false},
    plugins:{
      legend:{display:false},
      tooltip:{
        backgroundColor:'rgba(13,27,46,.96)',borderColor:'rgba(139,92,246,.3)',borderWidth:1,
        titleColor:'#E6FAF7',bodyColor:'#7CC7C4',padding:11,cornerRadius:10,displayColors:false,
        titleFont:{family:'Vazirmatn',size:11,weight:'700'},bodyFont:{family:'Vazirmatn',size:11},
        callbacks:{label:v=>`${v.parsed.y.toFixed(2)} مگابایت`}
      }
    },
    scales:{
      x:{grid:{display:false},border:{display:false},ticks:{color:'#4A8F8B',font:{size:9,family:'Vazirmatn'}}},
      y:{grid:{color:'rgba(139,92,246,.06)'},border:{display:false},ticks:{color:'#4A8F8B',font:{size:9,family:'Vazirmatn'},callback:v=>v+' MB'}}
    },
    elements:{line:{capBezierPoints:true}}
  };
  const ds1={label:'MB',data:[],borderColor:'#8B5CF6',backgroundColor:grad1,fill:true,tension:.42,pointRadius:0,pointHoverRadius:6,pointHoverBackgroundColor:'#8B5CF6',pointHoverBorderColor:'#fff',pointHoverBorderWidth:2,borderWidth:2.5};
  ch1=new Chart(document.getElementById('ch1'),{type:'line',data:{labels:[],datasets:[ds1]},options:opts});

  function makeGradientV2(ctx,c1,c2,c3){
    const g=ctx.createLinearGradient(0,0,0,320);
    g.addColorStop(0,c1);g.addColorStop(.6,c2);g.addColorStop(1,c3);
    return g;
  }
  const c3ctx=document.getElementById('ch3').getContext('2d');
  const gradFill3=makeGradientV2(c3ctx,'rgba(139,92,246,.45)','rgba(139,92,246,.08)','rgba(139,92,246,0)');
  ch3=new Chart(document.getElementById('ch3'),{
    type:'line',
    data:{labels:[],datasets:[
      {label:'مصرف',data:[],borderColor:'#8B5CF6',backgroundColor:gradFill3,fill:true,tension:.45,pointRadius:0,pointHoverRadius:7,pointHoverBackgroundColor:'#fff',pointHoverBorderColor:'#8B5CF6',pointHoverBorderWidth:3,borderWidth:3,order:2},
      {label:'میانگین',data:[],borderColor:'#F59E0B',borderDash:[6,5],borderWidth:1.6,pointRadius:0,fill:false,tension:0,order:1}
    ]},
    options:{
      responsive:true,maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{
        legend:{display:false},
        tooltip:{
          backgroundColor:'rgba(13,27,46,.97)',borderColor:'rgba(139,92,246,.35)',borderWidth:1,
          titleColor:'#E6FAF7',bodyColor:'#8FD6D3',padding:13,cornerRadius:12,displayColors:true,boxPadding:4,
          titleFont:{family:'Vazirmatn',size:11.5,weight:'700'},bodyFont:{family:'Vazirmatn',size:11},
          callbacks:{label:v=>` ${v.dataset.label}: ${v.parsed.y.toFixed(2)} MB`}
        }
      },
      scales:{
        x:{grid:{display:false},border:{display:false},ticks:{color:'#4A8F8B',font:{size:9.5,family:'Vazirmatn'},maxRotation:0}},
        y:{grid:{color:'rgba(139,92,246,.05)'},border:{display:false},ticks:{color:'#4A8F8B',font:{size:9.5,family:'Vazirmatn'},callback:v=>v+' MB'}}
      }
    }
  });

  ch2=new Chart(document.getElementById('ch2'),{
    type:'doughnut',
    data:{labels:['VLESS/WS','XHTTP Ultra','HTTP Proxy'],datasets:[{
      data:[55,35,10],
      backgroundColor:['#8B5CF6','#10B981','#FACC15'],
      borderColor:getComputedStyle(document.documentElement).getPropertyValue('--card')||'#0d1b2e',
      borderWidth:4,hoverOffset:10,borderRadius:6,spacing:3
    }]},
    options:{
      responsive:true,maintainAspectRatio:false,cutout:'72%',
      plugins:{
        legend:{position:'bottom',labels:{color:'var(--t2)',font:{size:10,family:'Vazirmatn'},padding:12,usePointStyle:true,pointStyle:'circle'}},
        tooltip:{backgroundColor:'rgba(13,27,46,.96)',borderColor:'rgba(139,92,246,.3)',borderWidth:1,padding:10,cornerRadius:10,bodyFont:{family:'Vazirmatn'},titleFont:{family:'Vazirmatn'}}
      }
    }
  });
}
let ws;
function wsLog(c,m){const l=document.getElementById('ws-log'),p=document.createElement('p');const colors={ok:'#34D399',err:'#F87171',info:'#7CC7C4',sent:'#FCD34D'};p.style.color=colors[c]||'#fff';p.textContent='['+new Date().toLocaleTimeString('fa-IR')+'] '+m;l.appendChild(p);l.scrollTop=l.scrollHeight}
function wsConn(){const u=document.getElementById('ws-uuid').value.trim();if(!u){toast('UUID را وارد کنید','err');return}const url=(location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/ws/'+u;wsLog('info','اتصال: '+url);ws=new WebSocket(url);ws.onopen=()=>wsLog('ok','✓ متصل - UUID معتبر');ws.onerror=()=>wsLog('err','✗ خطا - UUID نامعتبر یا غیرفعال');ws.onmessage=m=>wsLog('info','دریافت '+(m.data.size||m.data.length)+' byte');ws.onclose=e=>wsLog('err','قطع ('+e.code+')'+(e.code===1008?' - دسترسی رد شد':''))}
function wsSend(){const m=document.getElementById('ws-msg').value;if(!m||!ws||ws.readyState!==1)return;ws.send(m);wsLog('sent','ارسال: '+m);document.getElementById('ws-msg').value=''}
function wsDisc(){if(ws)ws.close()}
const ICON_MAP={ad:'ti-speakerphone',news:'ti-news',warning:'ti-alert-triangle',urgent:'ti-alert-octagon'};
const LABEL_MAP={ad:'تبلیغ',news:'خبر',warning:'هشدار',urgent:'فوری'};
async function loadAnnouncements(){
  try{
    const r=await authF('/api/announcements'),d=await r.json();
    const seen=JSON.parse(localStorage.getItem('rvg-seen-ann')||'[]');
    const list=(d.announcements||[]).filter(a=>!seen.includes(a.id));
    document.getElementById('ann-banner-wrap').innerHTML=list.map(a=>`
      <div class="ann-card ${a.type}" id="ann-${a.id}">
        <button class="ann-close" onclick="dismissAnn('${a.id}')"><i class="ti ti-x"></i></button>
        <div class="ann-icon"><i class="ti ${ICON_MAP[a.type]||'ti-bell'}"></i></div>
        <div class="ann-body">
          <div class="ann-title">${esc(a.title)} <span style="font-size:9px;color:var(--t3)">· ${LABEL_MAP[a.type]||''}</span></div>
          <div class="ann-text">${esc(a.body)}</div>
          ${a.image_url?`<img class="ann-img" src="${esc(a.image_url)}">`:''}
        </div>
      </div>`).join('');
      if (list.length) {
      authF('/api/announcements/view', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: list.map(a => a.id) })
      }).catch(() => {});
    }
  }catch(e){netErr(e,'اطلاعیه‌ها')}
}
function dismissAnn(id){
  const seen=JSON.parse(localStorage.getItem('rvg-seen-ann')||'[]');
  seen.push(id);localStorage.setItem('rvg-seen-ann',JSON.stringify(seen));
  document.getElementById('ann-'+id)?.remove();
}
let lastSupportMsgId = null;
 
function fmtSupTime(ts){
  const d = new Date(ts);
  return d.toLocaleTimeString('fa-IR',{hour:'2-digit',minute:'2-digit'});
}
function fmtSupDate(ts){
  const d = new Date(ts);
  const today = new Date();
  const isToday = d.toDateString() === today.toDateString();
  if (isToday) return 'امروز';
  const y = new Date(today); y.setDate(y.getDate()-1);
  if (d.toDateString() === y.toDateString()) return 'دیروز';
  return d.toLocaleDateString('fa-IR');
}
 
async function loadSupportMsgs() {
  try {
    const r = await authF('/api/support/messages'),
      d = await r.json();
    const msgs = d.messages || [];
    const blocked = !!d.blocked;
    const el = document.getElementById('support-msgs');

    if (el) {
      if (!msgs.length) {
        el.innerHTML =
          '<div class="sup-empty"><i class="ti ti-message-circle-2"></i><b>هنوز گفتگویی نیست</b><span>اولین پیام را شما بفرستید، تیم پشتیبانی به زودی پاسخ می‌دهد</span></div>';
      } else {
        let html = '',
          lastDate = '';
        msgs.forEach((m, idx) => {
          const dateLabel = fmtSupDate(m.created_at);
          if (dateLabel !== lastDate) {
            html +=
              '<div class="sup-date-sep"><span>' + dateLabel + '</span></div>';
            lastDate = dateLabel;
          }
          const isLastClientMsg =
            m.sender === 'client' && idx === msgs.length - 1; // not used, but kept
          const seenTick =
            m.sender === 'client'
              ? m.read_by_admin
                ? '<i class="ti ti-checks seen"></i>'
                : '<i class="ti ti-check"></i>'
              : '';
          // ✅ Fixed: removed backslashes before backticks
          html += `
            <div class="sup-msg-row ${m.sender}">
              <div class="sup-msg ${m.sender}">
                ${esc(m.body)}
                <span class="sup-time">${fmtSupTime(m.created_at)} ${seenTick}</span>
              </div>
              <div class="sup-avatar ${m.sender}"><i class="ti ${m.sender === 'admin' ? 'ti-headset' : 'ti-user'}"></i></div>
            </div>`;
        });
        el.innerHTML = html;
      }
      const shouldScroll =
        !lastSupportMsgId ||
        (msgs.length && msgs[msgs.length - 1].id !== lastSupportMsgId);
      if (shouldScroll) el.scrollTop = el.scrollHeight;
      if (msgs.length) lastSupportMsgId = msgs[msgs.length - 1].id;
    }

    const banner = document.getElementById('sup-blocked-banner');
    const inputRow = document.getElementById('sup-input-row');
    if (banner) banner.style.display = blocked ? 'flex' : 'none';
    if (inputRow) inputRow.classList.toggle('disabled', blocked);

    const nb = document.getElementById('support-nb');
    if (nb) {
      const lastAdmin = [...msgs].reverse().find((m) => m.sender === 'admin');
      const seenId = localStorage.getItem('rvg-last-seen-support-msg');
      const onSupportPage = document
        .getElementById('pg-support')
        .classList.contains('on');
      const hasNew = lastAdmin && lastAdmin.id !== seenId && !onSupportPage;
      nb.style.display = hasNew ? 'inline-flex' : 'none';
      if (lastAdmin && onSupportPage)
        localStorage.setItem('rvg-last-seen-support-msg', lastAdmin.id);
    }
  } catch (e) {
    netErr(e, 'پیام‌های پشتیبانی');
  }
}
 
async function loadLoggingSetting(){
  try{
    const r=await authF('/api/settings/logging');
    if(!r.ok)return;
    const d=await r.json();
    document.getElementById('disable-logging-tog')?.classList.toggle('on', !!d.disabled);
  }catch(e){netErr(e,'تنظیم لاگ')}
}
async function toggleLoggingSetting(){
  const btn=document.getElementById('disable-logging-tog');
  const next = !btn.classList.contains('on');
  btn.classList.toggle('on', next);
  try{
    const r=await authF('/api/settings/logging',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({disabled:next})});
    if(!r.ok)throw new Error();
    toast(next?'لاگ‌گیری کامل متوقف شد':'لاگ‌گیری دوباره فعال شد','ok');
  }catch(e){
    btn.classList.toggle('on', !next);
    toast('خطا در ذخیره‌ی تنظیمات','err');
  }
}
async function sendSupportMsg(){
  const inp=document.getElementById('support-inp');const msg=inp.value.trim();if(!msg)return;
  inp.disabled = true;
  try{
    const r=await authF('/api/support/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
    if(r.status===403){toast('شما توسط پشتیبانی بلاک شده‌اید','err');loadSupportMsgs();inp.disabled=false;return}
    if(!r.ok)throw new Error();
    inp.value='';loadSupportMsgs();
  }catch(e){toast('خطا در ارسال پیام','err')}
  inp.disabled = false;
  inp.focus();
}
document.addEventListener('DOMContentLoaded', async () => {
  await checkAuth();
  initCharts();
  document.getElementById('set-host').textContent = location.host;
  loadLoggingSetting();
  checkVolumeBanner();
  document.getElementById('sub-all-url') && 
    (document.getElementById('sub-all-url').textContent = 
      location.protocol + '//' + location.host + '/sub-all');
  
  try {
    await loadVersion();
  } catch(e) {
    console.error('loadVersion failed:', e);
  }
  
  try {
    const updateDismissed = sessionStorage.getItem('rvg-update-dismissed') === 'true';
    if (updateAvailable && !updateDismissed) {
      document.getElementById('update-modal-version').textContent = updateVersion;
      document.getElementById('update-modal-desc').textContent = updateDescription;
      openModal('modal-update');
    }
  } catch(e) {
    console.error('modal error:', e);
  }

  try {
    if (localStorage.getItem('rvg-support-dev-seen') !== 'true') {
      openModal('modal-support-dev');
    }
  } catch(e) {
    console.error('support modal error:', e);
  }

  fetchStats();
  fetchDefaultVless();
  loadLinks();
  loadSubs();
  loadAnnouncements();
  loadSupportMsgs();

  setInterval(fetchStats, 2000);
  // Audit fix: وضعیت سرویس + توزیع پروتکل از داده‌ی واقعی (هر ۳۰s + بلافاصله)
  loadOverviewReal();
  setInterval(loadOverviewReal, 30000);
  setInterval(() => {
    if (document.getElementById('pg-links').classList.contains('on')) loadLinks();
    if (document.getElementById('pg-subgroups').classList.contains('on')) loadSubs();
    if (document.getElementById('pg-subscriptions').classList.contains('on')) loadSubsPage();
    if (document.getElementById('pg-connections').classList.contains('on')) loadConns();
    if (document.getElementById('pg-logs').classList.contains('on')) loadActivity();
    if (document.getElementById('pg-support').classList.contains('on')) loadSupportMsgs();
    loadVersion();
  }, 5000);
  setInterval(loadAnnouncements, 3000);
});

function timeAgoFa(ts){
  const diff = Math.max(0, (Date.now()/1000) - ts);
  if(diff < 60) return 'همین الان';
  if(diff < 3600) return toFa(Math.floor(diff/60))+' دقیقه پیش';
  if(diff < 86400) return toFa(Math.floor(diff/3600))+' ساعت پیش';
  if(diff < 2592000) return toFa(Math.floor(diff/86400))+' روز پیش';
  return new Date(ts*1000).toLocaleDateString('fa-IR');
}

async function loadVersion(){
  // نسخه‌ی واقعی دیپلوی‌شده — از /api/deployment-version (بدون احراز هویت)
  try{
    const dr=await fetch('/api/deployment-version',{cache:'no-store'});
    if(dr.ok){
      const dv=await dr.json();
      const el=document.getElementById('srv-version-val');
      if(el&&dv.version)el.textContent='v'+dv.version;
      // Audit fix: چیپ‌های نسخه‌ی hardcoded (sidebar/footer) حالا واقعی‌اند
      const fv=document.getElementById('footer-ver');if(fv&&dv.version)fv.textContent='v'+dv.version;
      const lv=document.getElementById('logo-ver-chip');if(lv&&dv.version)lv.textContent='Gateway · v'+dv.version;
    }
  }catch(e){}
  try{
    const r=await authF('/api/version'), d=await r.json();
    const cur=d.current||{}, lat=d.latest||{};

    document.getElementById('ver-current').textContent=cur.version||'—';
    document.getElementById('ver-current-desc').textContent=cur.description||'بدون توضیحات ثبت‌شده برای این نسخه';
    document.getElementById('ver-repo').textContent=d.repo||'تنظیم نشده';
    document.getElementById('ver-branch').textContent=d.branch||'—';

    const badge=document.getElementById('ver-status-badge'), nb=document.getElementById('update-nb');
    const latestCard=document.getElementById('upd-latest-card');

    if(lat.error){
      badge.innerHTML='<span class="upd-pill upd-pill-amber"><i class="ti ti-alert-triangle"></i> '+esc(lat.error)+'</span>';
      latestCard.style.display='none';
      nb.style.display='none';
      updateAvailable = false;
    } else if(d.update_available){
      badge.innerHTML='<span class="upd-pill upd-pill-amber"><span class="upd-dot"></span> بروزرسانی جدید موجود است</span>';
      document.getElementById('ver-latest-num').textContent=lat.version||'—';
      document.getElementById('ver-latest-desc').textContent=lat.description||'بدون توضیحات';
      latestCard.style.display='flex';
      nb.style.display='inline-flex';
      nb.textContent='1';
      // تنظیم متغیرهای سراسری برای مودال
      updateAvailable = true;
      updateVersion = lat.version || '—';
      updateDescription = lat.description || 'بدون توضیحات';
    } else {
      badge.innerHTML='<span class="upd-pill upd-pill-green"><i class="ti ti-circle-check"></i> پنل بروز است</span>';
      latestCard.style.display='none';
      nb.style.display='none';
      updateAvailable = false;
    }
  } catch(e) {
    console.error(e);
    updateAvailable = false;
  }
  loadUpdateHistory();
}

let updatePolling=null, pollTicks=0;
async function startUpdate(){
  if(!confirm('نصب بروزرسانی سرور را چند ثانیه ری‌استارت می‌کند. ادامه می‌دهید؟'))return;
  const btn=document.getElementById('update-btn');
  btn.disabled=true;btn.innerHTML='<i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال نصب...';
  document.getElementById('update-progress-wrap').style.display='block';
  pollTicks=0;
  try{
    await authF('/api/update',{method:'POST'});
    toast('بروزرسانی شروع شد','ok');
    updatePolling=setInterval(pollUpdate,900);
  }catch(e){
    toast('خطا در شروع بروزرسانی','err');
    btn.disabled=false;btn.innerHTML='<i class="ti ti-download"></i> نصب بروزرسانی';
  }
}
let btpPolling = null;
let btpHasToken = false;

function btpShowStep(step){
  ['input','vpn','ping','search','done'].forEach(s=>{
    document.getElementById('btp-step-'+s).style.display = (s===step) ? '' : 'none';
  });
  document.getElementById('btp-start-btn').style.display = (step==='input') ? 'flex' : 'none';
  document.getElementById('btp-continue-btn').style.display = (step==='vpn') ? 'flex' : 'none';
  document.getElementById('btp-stop-btn').style.display = (step==='search') ? 'flex' : 'none';
  document.getElementById('btp-cancel-btn').style.display = (step==='input'||step==='vpn'||step==='ping') ? 'flex' : 'none';
  document.getElementById('btp-close-done-btn').style.display = (step==='done') ? 'flex' : 'none';
}

function btpSetStatus(icon, cls, text, spin){
  const ic = document.getElementById('btp-status-icon');
  const note = document.getElementById('btp-status-note');
  ic.className = 'ti ' + icon;
  ic.style.animation = spin ? 'spin 1s linear infinite' : '';
  note.classList.remove('st-run','st-ok','st-err','st-warn');
  if(cls) note.classList.add(cls);
  document.getElementById('btp-status-text').textContent = text;
}

function btpSetPingStatus(icon, cls, text, spin){
  const ic = document.getElementById('btp-ping-status-icon');
  const note = document.getElementById('btp-ping-status-note');
  ic.className = 'ti ' + icon;
  ic.style.animation = spin ? 'spin 1s linear infinite' : '';
  note.classList.remove('st-run','st-ok','st-err','st-warn');
  if(cls) note.classList.add(cls);
  document.getElementById('btp-ping-status-text').textContent = text;
}

function btpRenderPingList(results){
  const el = document.getElementById('btp-ping-list');
  if(!results || !results.length){
    el.innerHTML = '<span style="font-size:11px;color:var(--t3)">در حال تست...</span>';
    return;
  }
  const sorted = [...results].sort((a,b)=> (b.ok - a.ok));
  el.innerHTML = sorted.map(r => `
    <div style="display:flex;align-items:center;gap:8px;background:${r.ok?'rgba(34,197,94,.08)':'rgba(239,68,68,.06)'};border:1px solid ${r.ok?'rgba(34,197,94,.25)':'rgba(239,68,68,.18)'};border-radius:10px;padding:7px 11px">
      <i class="ti ${r.ok?'ti-circle-check':'ti-clock-x'}" style="color:${r.ok?'var(--green-t)':'var(--red-t)'}"></i>
      <span style="flex:1;font-family:ui-monospace,monospace;font-size:11px;color:var(--t1)">${esc(r.domain)}</span>
      <span style="font-size:10px;color:${r.ok?'var(--green-t)':'var(--red-t)'}">${r.ok?'در دسترس':'Timeout'}</span>
    </div>
  `).join('');
}

function btpRenderFound(result){
  const el = document.getElementById('btp-found-list');
  if(!result){
    el.innerHTML = '<span style="font-size:11px;color:var(--t3)">هنوز چیزی پیدا نشده...</span>';
    return;
  }
  el.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.25);border-radius:10px;padding:8px 11px">
      <i class="ti ti-circle-check" style="color:var(--green-t)"></i>
      <span style="flex:1;font-family:ui-monospace,monospace;font-size:11px;color:var(--t1)">${esc(result.domain)}:${result.port}</span>
    </div>
  `;
}

function btpChangeToken(){
  document.getElementById('btp-token').style.display = '';
  document.getElementById('btp-token-saved-note').style.display = 'none';
  btpHasToken = false;
}

let btpReachableDomains = [];
let btpPingAborted = false;

async function btpCheckTokenState(){
  btpShowStep('input');
  document.getElementById('btp-token').value = '';
  document.getElementById('btp-port').value = '';
  btpReachableDomains = [];
  try{
    const r = await authF('/api/bot-tcp-proxy/status'), d = await r.json();
    btpHasToken = !!d.has_token;
    document.getElementById('btp-token').style.display = btpHasToken ? 'none' : '';
    document.getElementById('btp-token-saved-note').style.display = btpHasToken ? '' : 'none';

    if(d.running){
      btpShowStep('search');
      btpSetStatus('ti-loader-2', 'st-run', `در حال جست‌وجو... (${d.attempts} تلاش)`, true);
      btpRenderFound(null);
      btpPolling = setInterval(pollBotTcpProxy, 1200);
    } else if(d.phase === 'done' && d.result){
      btpFinishAttach(d.result);
    }
  }catch(e){}
}

function btpCloseModal(){
  clearInterval(btpPolling);
  btpPingAborted = true;
  closeModal('modal-bot-tcp-proxy');
}

// مرحله ۱ → مرحله ۲ (هشدار VPN)
function startBotTcpProxy(){
  const token = btpHasToken ? '' : document.getElementById('btp-token').value.trim();
  const portVal = document.getElementById('btp-port').value.trim();
  if(!btpHasToken && !token){ toast('توکن Railway را وارد کن','err'); return; }
  if(!portVal){ toast('پورت را وارد کن','err'); return; }
  btpShowStep('vpn');
  document.getElementById('btp-continue-btn').onclick = btpStartPing;
}

// مرحله ۲ → مرحله ۳: پینگ واقعی از خودِ مرورگر کاربر (نه از سرور پنل)، یکی‌یکی
const BTP_PING_TIMEOUT_MS = 6000;

async function btpPingOneDomain(domain){
  // fetch با mode:'no-cors' یعنی دقیقاً مثل باز کردن https://domain/ توی تب جدید مرورگر.
  // نکته‌ی مهم: بعضی از این دامنه‌ها گواهیِ TLS نامعتبر/نامنطبق دارن (صفحه‌ی "این اتصال
  // خصوصی نیست" توی کروم) — یعنی خودِ دامنه در دسترسه و اصلاً فیلتر نیست، فقط fetch به
  // خاطر گواهی خیلی سریع (کمتر از چند صد میلی‌ثانیه) reject می‌شه. این را نباید Timeout
  // حساب کرد. فقط وقتی واقعاً تا آخرِ مهلت (نزدیک ۶ ثانیه) صبر کردیم و جوابی نیومد،
  // یعنی واقعاً فیلتر/غیرقابل‌دسترسه.
  const ctrl = new AbortController();
  const timer = setTimeout(()=>ctrl.abort(), BTP_PING_TIMEOUT_MS);
  const started = performance.now();
  try{
    await fetch('https://' + domain + '/', { mode:'no-cors', cache:'no-store', signal: ctrl.signal });
    clearTimeout(timer);
    return true;
  }catch(e){
    clearTimeout(timer);
    const elapsed = performance.now() - started;
    // اگر خیلی زود شکست خورد (نه به خاطر Timeout واقعی ما)، یعنی دامنه در دسترس بوده
    // ولی به دلیلی دیگه (مثل گواهی نامعتبر) fetch رد شده — پس این را «سالم» حساب می‌کنیم.
    return elapsed < (BTP_PING_TIMEOUT_MS * 0.85);
  }
}

async function btpStartPing(){
  btpShowStep('ping');
  btpPingAborted = false;
  btpSetPingStatus('ti-loader-2', 'st-run', 'در حال تست دامنه‌ها از اینترنت خودت...', true);
  btpRenderPingList([]);

  let domains = [];
  try{
    const r = await authF('/api/bot-tcp-proxy/domains'), d = await r.json();
    domains = d.domains || [];
  }catch(e){
    toast('✗ خطا در گرفتن لیست دامنه‌ها','err');
    btpShowStep('input');
    return;
  }

  const results = [];
  for(const domain of domains){
    if(btpPingAborted) return;
    btpSetPingStatus('ti-loader-2', 'st-run', `در حال تست... (${results.length+1}/${domains.length}) ${domain}`, true);
    const ok = await btpPingOneDomain(domain);
    results.push({domain, ok});
    btpRenderPingList(results);
  }
  if(btpPingAborted) return;

  btpReachableDomains = results.filter(r=>r.ok).map(r=>r.domain);
  if(btpReachableDomains.length > 0){
    btpSetPingStatus('ti-circle-check', 'st-ok', `${btpReachableDomains.length} دامنه با اینترنت تو کار می‌کنه`, false);
    document.getElementById('btp-continue-btn').style.display = 'flex';
    document.getElementById('btp-continue-btn').onclick = btpStartSearch;
    document.getElementById('btp-cancel-btn').style.display = 'flex';
  } else {
    btpSetPingStatus('ti-alert-circle', 'st-err', 'هیچ دامنه‌ای با اینترنت تو کار نکرد', false);
    toast('✗ هیچ‌کدام از دامنه‌ها با اینترنت تو باز نشدن','err');
  }
}


// مرحله ۳ → مرحله ۴ (ساخت مکرر پروکسی تا رسیدن به یک دامنه‌ی سالم)
async function btpStartSearch(){
  const token = btpHasToken ? '' : document.getElementById('btp-token').value.trim();
  const port = document.getElementById('btp-port').value.trim();

  btpShowStep('search');
  btpSetStatus('ti-loader-2', 'st-run', 'در حال اتصال به Railway...', true);
  btpRenderFound(null);

  try{
    const r = await authF('/api/bot-tcp-proxy/start', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ token, port, reachable_domains: btpReachableDomains })
    });
    if(!r.ok){ const d = await r.json().catch(()=>({})); throw new Error(d.detail || 'خطا'); }
    btpPolling = setInterval(pollBotTcpProxy, 1200);
  }catch(e){
    toast('✗ '+e.message,'err');
    btpSetStatus('ti-alert-circle', 'st-err', e.message, false);
    btpShowStep('input');
  }
}

async function stopBotTcpProxy(){
  const btn = document.getElementById('btp-stop-btn');
  btn.disabled = true;
  try{
    await authF('/api/bot-tcp-proxy/stop', {method:'POST'});
    toast('درخواست توقف ارسال شد','ok');
  }catch(e){
    toast('خطا در توقف','err');
  }
  btn.disabled = false;
}

async function pollBotTcpProxy(){
  try{
    const r = await authF('/api/bot-tcp-proxy/status'), d = await r.json();
    if(d.running){
      btpSetStatus('ti-loader-2', 'st-run', `در حال تلاش... (${d.attempts} تلاش)`, true);
    }else{
      clearInterval(btpPolling);
      if(d.phase === 'done' && d.result){
        btpSetStatus('ti-circle-check', 'st-ok', 'دامنه‌ی سالم پیدا شد ✓', false);
        btpRenderFound(d.result);
        await btpFinishAttach(d.result);
      } else if(d.stopped_by_user){
        btpSetStatus('ti-player-stop', 'st-warn', 'فرآیند متوقف شد', false);
        btpShowStep('input');
      } else if(d.error){
        btpSetStatus('ti-alert-circle', 'st-err', d.error, false);
        toast('✗ '+d.error,'err');
        btpShowStep('input');
      }
    }
  }catch(e){}
}

// مرحله ۴ → مرحله ۵ (اتصال خودکار به پروکسی تلگرام)
async function btpFinishAttach(result){
  try{
    const r = await authF('/api/bot-tcp-proxy/attach', {method:'POST'});
    if(!r.ok){ const d = await r.json().catch(()=>({})); throw new Error(d.detail || 'خطا'); }
    const d = await r.json();
    document.getElementById('btp-done-domain').textContent = `${d.result.domain}:${d.result.port}`;
    if(d.share_link){
      document.getElementById('btp-done-link-wrap').style.display = '';
      document.getElementById('btp-done-link').value = d.share_link;
      toast('پروکسی تلگرام «'+ (d.attached_link ? d.attached_link.label : '') +'» ساخته شد ✓','ok');
    } else {
      toast('دامنه نهایی شد، اما لینک تلگرامی برای اتصال پیدا نشد','warn');
    }
    btpShowStep('done');
  }catch(e){
    toast('✗ '+e.message,'err');
  }
}

function btpCopyLink(){
  const inp = document.getElementById('btp-done-link');
  inp.select();
  navigator.clipboard.writeText(inp.value).then(()=>toast('کپی شد ✓','ok')).catch(()=>{});
}

// ══════════════════ Zeus Proxy — کارت داخل لیست کانفیگ‌ها + مدیریت + آی‌پی‌های متصل ══════════════════
let zpHasToken = false;
let zpStatusInterval = null;
let zeusStatus = null; // آخرین وضعیت دریافت‌شده از /api/zeus-proxy/status (توسط loadLinks پر می‌شود)

// ── کارت پروکسی Zeus با همون دیزاین بقیه‌ی کانفیگ‌ها ──
function zpExpChip(remH){
  if(remH === null || remH === undefined) return '<span class="exp-chip ec-inf"><i class="ti ti-infinity"></i> نامحدود</span>';
  if(remH <= 0) return '<span class="exp-chip ec-exp"><i class="ti ti-calendar-x"></i> منقضی</span>';
  const days = Math.floor(remH/24);
  if(days <= 0) return `<span class="exp-chip ec-warn"><i class="ti ti-alert-triangle"></i> ${toFa(Math.ceil(remH))} ساعت مانده</span>`;
  if(days <= 3) return `<span class="exp-chip ec-warn"><i class="ti ti-alert-triangle"></i> ${toFa(days)} روز مانده</span>`;
  return `<span class="exp-chip ec-ok"><i class="ti ti-calendar-check"></i> ${toFa(days)} روز مانده</span>`;
}
function zeusUniqueIpCount(d){
  // هر آی‌پی، صرف‌نظر از تعداد اتصال‌های بازی که دارد، فقط یک بار شمرده می‌شود
  const byIp = (d && d.connections_by_ip) || {};
  return Object.keys(byIp).length;
}
function zeusCardHtml(d){
  const r = d.result || {};
  const limitGb = r.traffic_limit_gb ?? d.config?.traffic_limit_gb ?? 0;
  const usedGb  = d.bytes_used_gb ?? 0;
  const pct     = limitGb ? Math.min(100, usedGb/limitGb*100) : 0;
  const bc      = pct>90?'var(--red)':pct>70?'var(--amber)':'var(--accent)';
  const remH    = d.expires_remaining_hours;
  const expired = (remH !== null && remH !== undefined && remH <= 0);
  const ipCount = zeusUniqueIpCount(d);
  const cfgStr  = esc(r.config || '');
  return `<div class="cfg-card ${expired?'is-exp':''}" data-uuid="zeus-proxy">
    <div class="cfg-row">
      <span style="width:18px;flex-shrink:0"></span>
      <span class="cfg-status-dot ${!expired?'pulse':''}"></span>
      <div class="cfg-identity">
        <div class="cfg-label">پروکسی Zeus</div>
        <div class="cfg-sub-meta">
          <span class="cfg-uuid-mini" onclick="zpCopyConfigStr('${cfgStr}')" title="کپی کانفیگ"><i class="ti ti-key"></i> SOCKS5</span>
        </div>
      </div>
      <div class="cfg-divider-v"></div>
      <div class="cfg-usage-col">
        <div class="ubar"><div class="ubar-f" style="width:${pct}%;background:${bc}"></div></div>
        <div class="utxt"><span>${usedGb.toFixed(2)} GB</span><span>از ${limitGb?limitGb+' GB':'∞'}</span></div>
      </div>
      <div class="cfg-divider-v"></div>
      <div class="cfg-exp-col">${zpExpChip(remH)}</div>
      <div class="cfg-divider-v"></div>
      <div class="cfg-badges-col">
        <span class="proto-chip pc-ss">SOCKS5 · Zeus</span>
        <span class="cfg-sub-tag"><i class="ti ti-router"></i> ${toFa(ipCount)} آی‌پی متصل</span>
      </div>
      <div class="cfg-divider-v"></div>
      <div class="cfg-actions">
        <button class="btn btn-sm btn-g btn-icon" onclick="zpOpenIps()" title="آی‌پی‌های متصل"><i class="ti ti-network"></i></button>
        <button class="btn btn-sm btn-g btn-icon" onclick="zpCopyConfigStr('${cfgStr}')" title="کپی کانفیگ"><i class="ti ti-copy"></i></button>
        <button class="btn btn-sm btn-amber btn-icon" onclick="zpOpenManage()" title="مدیریت / ویرایش"><i class="ti ti-settings"></i></button>
        <button class="btn btn-sm btn-d btn-icon" onclick="zpDelete()" title="حذف"><i class="ti ti-trash"></i></button>
      </div>
    </div>
  </div>`;
}
function zpCopyConfigStr(str){
  navigator.clipboard.writeText(str).then(()=>toast('کانفیگ کپی شد ✓','ok')).catch(()=>{});
}
function refreshZeusCardOnly(d){
  const grid = document.getElementById('links-grid');
  const old = grid.querySelector('.cfg-card[data-uuid="zeus-proxy"]');
  if(old) old.outerHTML = zeusCardHtml(d);
}

// ── مودال ساخت (فقط ساخت — بعد از ساخت، مدیریت از روی کارت لیست انجام می‌شود) ──
function zpChangeToken(){
  document.getElementById('zp-token').style.display = '';
  document.getElementById('zp-token-saved-note').style.display = 'none';
  zpHasToken = false;
}

function zpShowCreateStep(step){
  ['input','building','error'].forEach(s=>{
    document.getElementById('zp-step-'+s).style.display = (s===step ? '' : 'none');
  });
  document.getElementById('zp-start-btn').style.display = (step==='input') ? '' : 'none';
}

async function zpCheckTokenState(){
  zpShowCreateStep('input');
  document.getElementById('zp-token').value = '';
  try{
    const r = await authF('/api/zeus-proxy/status'), d = await r.json();
    zeusStatus = d;
    zpHasToken = !!d.has_token;
    document.getElementById('zp-token').style.display = zpHasToken ? 'none' : '';
    document.getElementById('zp-token-saved-note').style.display = zpHasToken ? '' : 'none';
    const cfg = d.config || {};
    document.getElementById('zp-cfg-traffic').value = cfg.traffic_limit_gb ?? 10;
    document.getElementById('zp-cfg-days').value    = cfg.expires_days ?? 30;
    document.getElementById('zp-cfg-maxip').value   = cfg.max_connections_per_ip ?? 3;
  }catch(e){}
}

function zpCloseModal(){
  closeModal('modal-zeus-proxy');
}

async function zpStart(){
  const token = zpHasToken ? '' : document.getElementById('zp-token').value.trim();
  if(!zpHasToken && !token){ toast('توکن Railway را وارد کن','err'); return; }

  const traffic_limit_gb       = parseFloat(document.getElementById('zp-cfg-traffic').value) || 0;
  const expires_days           = parseInt(document.getElementById('zp-cfg-days').value)    || 0;
  const max_connections_per_ip = parseInt(document.getElementById('zp-cfg-maxip').value)   || 0;

  zpShowCreateStep('building');
  try{
    const r = await authF('/api/zeus-proxy/create', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({token, traffic_limit_gb, expires_days, max_connections_per_ip})
    });
    const d = await r.json();
    if(!r.ok){ throw new Error(d.detail || 'ساخت پروکسی ناموفق بود'); }
    toast('پروکسی Zeus ساخته شد ✓','ok');
    zpCloseModal();
    await loadLinks(); // پروکسی حالا مثل بقیه‌ی کانفیگ‌ها توی لیست نمایش داده می‌شود
  }catch(e){
    document.getElementById('zp-error-text').textContent = e.message;
    zpShowCreateStep('error');
    document.getElementById('zp-start-btn').style.display = '';
  }
}

// ── مودال مدیریت (آمار + ویرایش کانفیگ) — از روی کارت لیست باز می‌شود ──
function zpRenderDone(d){
  const result = d.result || d;
  document.getElementById('zp-done-config').value = result.config || '';
  document.getElementById('zp-edit-traffic').value = result.traffic_limit_gb ?? d.config?.traffic_limit_gb ?? 10;
  document.getElementById('zp-edit-days').value    = result.expires_days    ?? d.config?.expires_days    ?? 30;
  document.getElementById('zp-edit-maxip').value   = result.max_connections_per_ip ?? d.config?.max_connections_per_ip ?? 3;
  zpUpdateStats(d);
}

function zpUpdateStats(d){
  const usedGb   = (d.bytes_used_gb ?? 0).toFixed(3);
  const limitGb  = d.result?.traffic_limit_gb ?? 0;
  const pct      = d.traffic_percent;
  document.getElementById('zp-stat-traffic').textContent =
    limitGb ? `${usedGb} / ${limitGb} GB` : `${usedGb} GB`;
  const barWrap = document.getElementById('zp-traffic-bar-wrap');
  if(limitGb && pct !== null && pct !== undefined){
    barWrap.style.display = '';
    const bar = document.getElementById('zp-traffic-bar');
    bar.style.width = Math.min(100, pct) + '%';
    bar.style.background = pct >= 90 ? 'var(--red-t)' : pct >= 70 ? '#FACC15' : 'var(--accent)';
    document.getElementById('zp-traffic-bar-label').textContent = pct.toFixed(1) + '% مصرف‌شده';
  } else { barWrap.style.display = 'none'; }

  const remH = d.expires_remaining_hours;
  if(remH === null || remH === undefined){
    document.getElementById('zp-stat-expiry').textContent = 'بی‌انقضا';
  } else {
    const days = Math.floor(remH / 24), hrs = Math.floor(remH % 24);
    document.getElementById('zp-stat-expiry').textContent =
      days > 0 ? `${days}روز ${hrs}ساعت` : `${hrs}ساعت`;
  }

  // اتصال‌ها: هر آی‌پی صرف‌نظر از تعداد اتصال‌هایش یک بار شمرده می‌شود
  const ipCount = zeusUniqueIpCount(d);
  document.getElementById('zp-stat-conns').textContent = `${toFa(ipCount)} IP`;
}

function zpOpenManage(){
  if(!zeusStatus || zeusStatus.phase !== 'done') return;
  zpRenderDone(zeusStatus);
  openModal('modal-zeus-manage');
  zpStartPolling();
}
function zpCloseManage(){
  closeModal('modal-zeus-manage');
  zpMaybeStopPolling();
}
function zpCloseIps(){
  closeModal('modal-zeus-ips');
  zpMaybeStopPolling();
}

// ── مودال آی‌پی‌های متصل (شمارش یکتا: هر آی‌پی فقط یک بار) ──
function zpRenderIps(d){
  const byIp = (d && d.connections_by_ip) || {};
  const ips  = Object.keys(byIp);
  document.getElementById('zp-ips-sub').textContent = `${toFa(ips.length)} آی‌پی متصل (هر آی‌پی یک بار شمرده می‌شود)`;
  const list = document.getElementById('zp-ips-list'), empty = document.getElementById('zp-ips-empty');
  if(!ips.length){ list.innerHTML=''; empty.style.display='block'; return; }
  empty.style.display='none';
  list.innerHTML = ips.map(ip=>`
    <div style="display:flex;align-items:center;justify-content:space-between;background:var(--card2,var(--card));border-radius:8px;padding:8px 12px">
      <span style="font-family:ui-monospace,monospace;font-size:12.5px;direction:ltr;text-align:left">${esc(ip)}</span>
      <span class="cfg-sub-tag" title="تعداد اتصال باز این آی‌پی — در شمارش کلی فقط ۱ حساب می‌شود">${toFa(byIp[ip])} اتصال</span>
    </div>
  `).join('');
}
function zpOpenIps(){
  if(!zeusStatus || zeusStatus.phase !== 'done') return;
  zpRenderIps(zeusStatus);
  openModal('modal-zeus-ips');
  zpStartPolling();
}

// ── پولینگ مشترک وقتی مودال مدیریت یا آی‌پی‌ها باز است ──
function zpStartPolling(){
  if(zpStatusInterval) return;
  zpStatusInterval = setInterval(async ()=>{
    try{
      const r = await authF('/api/zeus-proxy/status'), d = await r.json();
      zeusStatus = d;
      if(d.phase !== 'done'){
        zpMaybeStopPolling(true);
        closeModal('modal-zeus-manage'); closeModal('modal-zeus-ips');
        loadLinks();
        return;
      }
      if(document.getElementById('modal-zeus-manage').classList.contains('open')) zpUpdateStats(d);
      if(document.getElementById('modal-zeus-ips').classList.contains('open')) zpRenderIps(d);
      refreshZeusCardOnly(d);
    }catch(e){}
  }, 5000);
}
function zpMaybeStopPolling(force){
  const manageOpen = document.getElementById('modal-zeus-manage').classList.contains('open');
  const ipsOpen = document.getElementById('modal-zeus-ips').classList.contains('open');
  if(force || (!manageOpen && !ipsOpen)){ clearInterval(zpStatusInterval); zpStatusInterval = null; }
}

async function zpDelete(){
  if(!confirm('پروکسی Zeus حذف شود؟ TCP Proxy روی Railway هم پاک می‌شود.')) return;
  try{
    const r = await authF('/api/zeus-proxy/delete',{method:'POST'});
    if(!r.ok) throw new Error('حذف ناموفق');
    toast('پروکسی Zeus حذف شد','ok');
    zeusStatus = null;
    clearInterval(zpStatusInterval); zpStatusInterval = null;
    closeModal('modal-zeus-manage');
    closeModal('modal-zeus-ips');
    await loadLinks();
  }catch(e){ toast('خطا: '+e.message,'err'); }
}

async function zpSaveConfig(){
  const traffic_limit_gb       = parseFloat(document.getElementById('zp-edit-traffic').value) || 0;
  const expires_days           = parseInt(document.getElementById('zp-edit-days').value)       || 0;
  const max_connections_per_ip = parseInt(document.getElementById('zp-edit-maxip').value)      || 0;
  try{
    const r = await authF('/api/zeus-proxy/config',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({traffic_limit_gb, expires_days, max_connections_per_ip})
    });
    if(!r.ok) throw new Error('ذخیره ناموفق');
    toast('کانفیگ ذخیره شد ✓','ok');
    const rr = await authF('/api/zeus-proxy/status');
    zeusStatus = await rr.json();
    zpUpdateStats(zeusStatus);
    refreshZeusCardOnly(zeusStatus);
  }catch(e){ toast('خطا: '+e.message,'err'); }
}

function zpCopyConfig(){
  const inp = document.getElementById('zp-done-config');
  inp.select();
  navigator.clipboard.writeText(inp.value).then(()=>toast('کپی شد ✓','ok')).catch(()=>{});
}
async function pollUpdate(){
  pollTicks++;
  try{
    const r=await fetch('/api/update-log',{credentials:'include'});
    if(r.status===401){clearInterval(updatePolling);location.reload();return}
    const d=await r.json();
    document.getElementById('update-progress-bar').style.width=d.progress+'%';
    document.getElementById('update-progress-pct').textContent=d.progress+'%';
    renderUpdateLog(d.logs);
    if(d.logs && d.logs.length) document.getElementById('update-progress-txt').textContent=d.logs[d.logs.length-1].msg;

    if(!d.running && d.progress>=100){
      document.getElementById('update-progress-txt').textContent='بروزرسانی کامل شد؛ در حال اتصال مجدد...';
      clearInterval(updatePolling);
      let tries=0;
      const reconnect=setInterval(async()=>{
        tries++;
        try{const rr=await fetch('/api/me',{credentials:'include'});if(rr.ok){clearInterval(reconnect);location.reload();}}catch(e){}
        if(tries>40)clearInterval(reconnect);
      },2000);
    }else if(!d.running && pollTicks>3){
      document.getElementById('update-progress-txt').textContent='بروزرسانی متوقف شد (خطا) — لاگ را ببینید';
      document.getElementById('update-btn').disabled=false;
      document.getElementById('update-btn').innerHTML='<i class="ti ti-download"></i> نصب بروزرسانی';
      clearInterval(updatePolling);
    }
  }catch(e){}
}
async function loadUpdateLog(){
  try{const r=await authF('/api/update-log'),d=await r.json();renderUpdateLog(d.logs);}catch(e){}
}

let dgPolling = null;

function dgSetStatus(icon, color, text, spin){
  const ic = document.getElementById('dg-status-icon');
  ic.className = 'ti ' + icon;
  ic.style.color = color;
  ic.style.animation = spin ? 'spin 1s linear infinite' : '';
  document.getElementById('dg-status-text').textContent = text;
}
function dgToggleButtons(running){
  document.getElementById('dg-start-btn').style.display = running ? 'none' : 'flex';
  document.getElementById('dg-stop-btn').style.display = running ? 'flex' : 'none';
}
function dgChangeToken(){
  document.getElementById('dg-token-section').style.display = '';
  document.getElementById('dg-token-saved-section').style.display = 'none';
}
function dgRenderResults(results){
  const el = document.getElementById('dg-results');
  if(!results || !results.length){ el.innerHTML=''; return; }
  el.innerHTML = results.map(r=>`
    <div style="display:flex;align-items:center;gap:8px;background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);border-radius:10px;padding:8px 11px">
      <i class="ti ti-circle-check" style="color:var(--green-t)"></i>
      <span style="flex:1;font-family:ui-monospace,monospace;font-size:11px;color:var(--t1)">${esc(r.domain)}:${r.port}</span>
      <button class="btn btn-sm btn-g" onclick="navigator.clipboard.writeText('${esc(r.domain)}:${r.port}').then(()=>toast('کپی شد ✓','ok'))"><i class="ti ti-copy"></i></button>
    </div>
  `).join('');
}
async function dgCheckTokenState(){
  try{
    const r = await authF('/api/domain-gen/status'), d = await r.json();
    document.getElementById('dg-token-section').style.display = d.has_token ? 'none' : '';
    document.getElementById('dg-token-saved-section').style.display = d.has_token ? '' : 'none';
    dgToggleButtons(d.running);
    dgRenderResults(d.results || []);
    if(d.running){
      dgPolling = setInterval(pollDomainGen, 1500);
      dgSetStatus('ti-loader-2','var(--accent)', `در حال ساخت... (${d.attempts} تلاش، ${(d.results||[]).length}/${d.target_count} دامنه)`, true);
    }
  }catch(e){}
}
async function startDomainGen(){
  const tokenField = document.getElementById('dg-token');
  const token = tokenField.style.display !== 'none' ? tokenField.value.trim() : '';
  const port = document.getElementById('dg-port').value.trim();
  const count = parseInt(document.getElementById('dg-count').value || '10');

  const btn = document.getElementById('dg-start-btn');
  btn.disabled = true;
  btn.innerHTML = '<i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال اجرا...';
  dgSetStatus('ti-loader-2','var(--accent)','در حال اتصال به Railway...', true);
  document.getElementById('dg-log-box').style.display = 'block';

  try{
    const r = await authF('/api/domain-gen/start', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ token, port: port || undefined, count })
    });
    if(!r.ok){ const d = await r.json().catch(()=>({})); throw new Error(d.detail || 'خطا'); }
    document.getElementById('dg-token-section').style.display = 'none';
    document.getElementById('dg-token-saved-section').style.display = '';
    dgToggleButtons(true);
    dgPolling = setInterval(pollDomainGen, 1500);
  }catch(e){
    toast('✗ '+e.message,'err');
    dgSetStatus('ti-alert-circle','var(--red-t)', e.message, false);
    btn.disabled = false; btn.innerHTML = '<i class="ti ti-player-play"></i> شروع ساخت';
  }
}
async function stopDomainGen(){
  const btn = document.getElementById('dg-stop-btn');
  btn.disabled = true;
  try{ await authF('/api/domain-gen/stop', {method:'POST'}); toast('درخواست توقف ارسال شد','ok'); }
  catch(e){ toast('خطا در توقف','err'); }
  btn.disabled = false;
}
async function pollDomainGen(){
  try{
    const r = await authF('/api/domain-gen/status'), d = await r.json();
    const box = document.getElementById('dg-log-box');
    box.innerHTML = (d.logs||[]).map(l=>`<p class="upd-log-line">[${new Date(l.time*1000).toLocaleTimeString('fa-IR')}] ${esc(l.msg)}</p>`).join('') || '<p class="upd-log-empty">لاگی موجود نیست</p>';
    box.scrollTop = box.scrollHeight;
    dgRenderResults(d.results || []);

    if(d.running){
      dgToggleButtons(true);
      dgSetStatus('ti-loader-2','var(--accent)', `در حال ساخت... (${d.attempts} تلاش، ${(d.results||[]).length}/${d.target_count} دامنه)`, true);
    }else{
      clearInterval(dgPolling);
      dgToggleButtons(false);
      const btn = document.getElementById('dg-start-btn');
      btn.disabled = false; btn.innerHTML = '<i class="ti ti-player-play"></i> شروع ساخت';
      if(d.results && d.results.length >= d.target_count){
        dgSetStatus('ti-circle-check','var(--green-t)', `${d.target_count} دامنه با موفقیت ساخته شد ✓`, false);
        toast(d.target_count+' دامنه ساخته شد ✓','ok');
      } else if(d.stopped_by_user){
        dgSetStatus('ti-player-stop','var(--amber-t)', 'فرآیند متوقف شد', false);
      } else if(d.error){
        dgSetStatus('ti-alert-circle','var(--red-t)', d.error, false);
      }
    }
  }catch(e){}
}

function renderUpdateLog(logs){
  const box=document.getElementById('update-log-box');
  if(!logs||!logs.length){box.innerHTML='<p class="upd-log-empty">لاگی موجود نیست</p>';return}
  box.innerHTML=logs.map(l=>{
    const cls = l.msg.includes('❌') ? 'err' : (l.msg.includes('✅') ? 'ok' : '');
    return `<p class="upd-log-line ${cls}">[${new Date(l.time*1000).toLocaleTimeString('fa-IR')}] ${esc(l.msg)}</p>`;
  }).join('');
  box.scrollTop=box.scrollHeight;
}
async function loadUpdateHistory(){
  try{
    const r=await authF('/api/update-history'),d=await r.json();
    const hist=d.history||[];
    document.getElementById('upd-history-count').textContent=toFa(hist.length)+' مورد';
    const el=document.getElementById('upd-history-list');
    if(!hist.length){
      el.innerHTML='<div class="upd-history-empty"><i class="ti ti-history-toggle"></i><p>هنوز هیچ بروزرسانی‌ای ثبت نشده</p></div>';
      return;
    }
    el.innerHTML=hist.map(h=>{
      const isErr = h.status==='err';
      return `
      <div class="upd-item ${isErr?'err':''}">
        <div class="upd-item-dot-wrap"><div class="upd-item-dot"><i class="ti ${isErr?'ti-x':'ti-check'}"></i></div></div>
        <div class="upd-item-card">
          <div class="upd-item-head">
            <div class="upd-item-versions">
              <span>${esc(h.from_version||'—')}</span>
              <i class="ti ti-arrow-left arrow"></i>
              <span class="to">${esc(h.to_version||'—')}</span>
            </div>
            <span class="upd-item-badge ${isErr?'err':'ok'}">${isErr?'ناموفق':'موفق'}</span>
          </div>
          <div class="upd-item-time"><i class="ti ti-clock"></i> ${new Date(h.time*1000).toLocaleString('fa-IR')} · ${timeAgoFa(h.time)}</div>
          ${h.description?`<div class="upd-item-desc">${esc(h.description)}</div>`:''}
          ${isErr && h.error?`<div class="upd-item-err-box"><i class="ti ti-alert-circle"></i> ${esc(h.error)}</div>`:''}
        </div>
      </div>`;
    }).join('');
  }catch(e){console.error(e)}
}
// Audit fix: auto-domain widget JS حذف شد — عناصر HTML آن وجود نداشتند (موتور TCP-Proxy واقعی از /api/bot-tcp-proxy قابل استفاده است)
function openDomainScanModal(){
  dsDomains = [];
  dsRenderChips();
  document.getElementById('ds-token-section').style.display = '';
  openModal('modal-domain-scan');
  authF('/api/bot-tcp-proxy/status').then(r=>r.json()).then(d=>{
    if(d.has_token) document.getElementById('ds-token-section').style.display = 'none';
  }).catch(()=>{});
}


function dsAddDomain(){
  const inp = document.getElementById('ds-domain-inp');
  const v = inp.value.trim().toLowerCase().replace(/\.$/, '');
  if(v && !dsDomains.includes(v)) dsDomains.push(v);
  inp.value = '';
  document.querySelectorAll('#modal-domain-scan .cm-opt').forEach(o=>o.classList.remove('sel')); // جدید
  dsRenderChips();
}
function dsRemoveDomain(d){
  dsDomains = dsDomains.filter(x=>x!==d);
  dsRenderChips();
}
function dsRenderChips(){
  document.getElementById('ds-domain-chips').innerHTML = dsDomains.map(d=>
    `<span class="cm-pill active" style="cursor:pointer" onclick="dsRemoveDomain('${d}')">${d} <i class="ti ti-x" style="font-size:10px"></i></span>`
  ).join('') || '<span style="font-size:10.5px;color:var(--t3)">هنوز دامنه‌ای اضافه نشده</span>';
}
async function startDomainScan(){
  if(!dsDomains.length){ toast('حداقل یک دامنه اضافه کن','err'); return; }
  const tokenField = document.getElementById('ds-token');
  const token = tokenField.style.display !== 'none' ? tokenField.value.trim() : '';
  const btn = document.getElementById('ds-start-btn');
  btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال اجرا...';
  document.getElementById('ds-log-box').style.display = 'block';
  try{
    const r = await authF('/api/bot-tcp-proxy/start', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ token, mode:'whitelist', target_domains: dsDomains })
    });
    if(!r.ok){ const d = await r.json().catch(()=>({})); throw new Error(d.detail || 'خطا'); }
    document.getElementById('ds-stop-btn').style.display = 'flex';
    dsPolling = setInterval(pollDomainScan, 1500);
  }catch(e){
    toast('✗ '+e.message,'err');
    btn.disabled = false; btn.innerHTML = '<i class="ti ti-player-play"></i> شروع اسکن';
  }
}
async function stopDomainScan(){
  await authF('/api/bot-tcp-proxy/stop', {method:'POST'});
  toast('درخواست توقف ارسال شد','ok');
}
async function pollDomainScan(){
  try{
    const r = await authF('/api/bot-tcp-proxy/status'), d = await r.json();
    const box = document.getElementById('ds-log-box');
    box.innerHTML = (d.logs||[]).map(l=>`<p class="upd-log-line">[${new Date(l.time*1000).toLocaleTimeString('fa-IR')}] ${esc(l.msg)}</p>`).join('') || '<p class="upd-log-empty">لاگی موجود نیست</p>';
    box.scrollTop = box.scrollHeight;
    const txt = document.getElementById('ds-status-text');
    if(d.running){
      txt.textContent = `در حال جستجو... (${d.attempts} تلاش)`;
    } else {
      clearInterval(dsPolling);
      document.getElementById('ds-stop-btn').style.display = 'none';
      const btn = document.getElementById('ds-start-btn');
      btn.disabled = false; btn.innerHTML = '<i class="ti ti-player-play"></i> شروع اسکن';
      if(d.result){
        txt.textContent = `پیدا شد: ${d.result.domain}:${d.result.port}`;
        toast('دامنه پیدا شد: '+d.result.domain+':'+d.result.port,'ok');
      } else if(d.error){
        txt.textContent = d.error;
      }
    }
  }catch(e){}
}
// آدرس Worker رو بعد از دیپلوی اینجا بذار (بخش ۳)
const SUGGEST_WORKER_URL = 'https://railway-tcp.arvin341az.workers.dev/suggest';

function openSuggestModal(prefill){
  document.getElementById('sg-domain').value = prefill || '';
  document.getElementById('sg-note').value = '';
  document.getElementById('sg-status-text').textContent = 'هنوز ارسال نشده';
  openModal('modal-suggest-domain');
}

async function submitDomainSuggestion(){
  const domain = document.getElementById('sg-domain').value.trim().toLowerCase();
  const note = document.getElementById('sg-note').value.trim();
  if(!domain){ toast('دامنه را وارد کن','err'); return; }
  const btn = document.getElementById('sg-submit-btn');
  btn.disabled = true;
  btn.innerHTML = '<i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال ارسال...';
  try{
    const r = await fetch(SUGGEST_WORKER_URL, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        domain, note,
        panel_host: location.host,
        sent_at: new Date().toISOString(),
      })
    });
    if(!r.ok) throw new Error('ارسال ناموفق بود');
    document.getElementById('sg-status-text').textContent = 'با موفقیت ارسال شد ✓';
    toast('پیشنهاد شما ارسال شد ✓','ok');
    setTimeout(()=>closeModal('modal-suggest-domain'), 900);
  }catch(e){
    toast('✗ '+e.message,'err');
  }
  btn.disabled = false;
  btn.innerHTML = '<i class="ti ti-send"></i> ارسال پیشنهاد';
}
async function downloadBackup(){
  try{
    const r = await authF('/api/backup/export');
    if(!r.ok) throw new Error('خطا در دریافت بکاپ');
    const blob = await r.blob();
    const cd = r.headers.get('Content-Disposition') || '';
    const m = cd.match(/filename="?([^"]+)"?/);
    const filename = m ? m[1] : 'rvg-backup.json';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast('فایل بکاپ دانلود شد ✓','ok');
  }catch(e){ toast('✗ '+e.message,'err'); }
}

async function restoreBackup(){
  const inp = document.getElementById('restore-file');
  const file = inp.files[0];
  if(!file){ toast('فایل بکاپ را انتخاب کنید','err'); return; }
  if(!confirm('تمام اطلاعات فعلی پنل با فایل بکاپ جایگزین می‌شود. ادامه می‌دهید؟')) return;

  const btn = document.getElementById('restore-btn');
  btn.disabled = true;
  btn.innerHTML = '<i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i> در حال بازیابی...';

  try{
    const text = await file.text();
    let data;
    try{ data = JSON.parse(text); }catch(e){ throw new Error('فایل JSON معتبر نیست'); }
    const keepPw = !document.getElementById('restore-pw-tog').classList.contains('on');
    const r = await authF('/api/backup/import', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ data, keep_current_password: keepPw })
    });
    if(!r.ok){ const d = await r.json().catch(()=>({})); throw new Error(d.detail || 'خطا در بازیابی'); }
    const d = await r.json();
    toast('بازیابی موفق ✓ ('+toFa(d.links_count)+' کانفیگ، '+toFa(d.subs_count)+' گروه)','ok');
    inp.value = '';
    loadLinks(); loadSubs(); fetchStats();
  }catch(e){
    toast('✗ '+e.message,'err');
  }
  btn.disabled = false;
  btn.innerHTML = '<i class="ti ti-database-import"></i> شروع بازیابی';
}

// ══════════════════════════ نود ══════════════════════════
const NK_PERM_LABELS = {usage:'مصرف',links:'کانفیگ‌ها',subs:'ساب‌ها',requests:'درخواست‌ها',logs:'لاگ‌ها'};

function toggleNkPerm(el){
  el.classList.toggle('on');
}

function openNodeKeyModal(){
  document.getElementById('nk-label').value='';
  document.getElementById('nk-password').value='';
  document.getElementById('nk-result').style.display='none';
  document.getElementById('nk-key').textContent='—';
  document.querySelectorAll('#nk-perms .nk-perm-tile').forEach(el=>{
    const on = el.dataset.perm!=='logs' && el.dataset.perm!=='manage';
    el.classList.toggle('on', on);
  });
  const btn=document.getElementById('nk-gen-btn');
  btn.style.display='';btn.disabled=false;
  openModal('modal-node-key');
}

async function genNodeKey(){
  const label=document.getElementById('nk-label').value.trim();
  const share={};
  document.querySelectorAll('#nk-perms .nk-perm-tile').forEach(el=>{
    share[el.dataset.perm]=el.classList.contains('on');
  });
  const can_manage=!!share.manage; delete share.manage;
  const password=document.getElementById('nk-password').value;
  const btn=document.getElementById('nk-gen-btn');
  btn.disabled=true;
  try{
    const r=await authF('/api/nodes/keys',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({label,share,can_manage,password})});
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'خطا در ساخت کلید');
    document.getElementById('nk-key').textContent=d.key;
    document.getElementById('nk-result').style.display='';
    btn.style.display='none';
    toast('کلید ساخته شد ✓','ok');
    loadNodeKeys();
  }catch(e){ toast(e.message||'خطا در ساخت کلید','err'); }
  finally{ btn.disabled=false; }
}

function renderNodeKeys(keys){
  document.getElementById('nk-cnt').textContent=toFa(keys.length);
  const list=document.getElementById('nk-list');
  if(!keys.length){ list.innerHTML='<div class="empty" style="padding:16px 0"><i class="ti ti-key-off"></i><p>هنوز کلیدی نساخته‌اید</p></div>'; return; }
  list.innerHTML = keys.map(k=>{
    const share = k.share||{};
    const chips = Object.keys(NK_PERM_LABELS).filter(p=>share[p]).map(p=>NK_PERM_LABELS[p]).join('، ') || 'هیچ‌کدام';
    const manageChip = k.can_manage ? ' <span class="exp-chip ec-warn"><i class="ti ti-edit"></i> ویرایش/حذف از راه دور</span>' : '';
    const stateChip = k.revoked ? '<span class="exp-chip ec-exp">غیرفعال</span>' : '<span class="exp-chip ec-ok">فعال</span>';
    const pwChip = k.has_password ? ' <span class="exp-chip ec-warn" title="برای اتصال به این کلید، رمز لازم است"><i class="ti ti-lock"></i> رمزدار</span>' : '';
    const meta = [
      k.use_count ? (toFa(k.use_count)+' بار استفاده') : null,
      k.peer_host ? ('آخرین اتصال از '+esc(k.peer_host)) : null,
    ].filter(Boolean).join(' · ');
    return `
    <div class="node-key-row ${k.revoked?'off':''}">
      <span class="node-key-dot"></span>
      <div class="node-key-body">
        <div class="node-key-label">${esc(k.label)} ${stateChip}${pwChip}</div>
        <div class="node-key-val" onclick="navigator.clipboard.writeText('${esc(k.key)}').then(()=>toast('کپی شد ✓','ok'))" title="برای کپی کلیک کنید"><i class="ti ti-copy"></i>${esc(k.key)}</div>
        <div class="node-key-state" title="دسترسی: ${esc(chips)}${meta?(' · '+esc(meta)):''}">${esc(chips)}${manageChip}${meta?(' · '+esc(meta)):''}</div>
      </div>
      <div class="node-key-actions">
        <button class="btn btn-o btn-sm btn-icon" onclick="setNodeKeyPassword('${k.key_id}',${k.has_password})" title="${k.has_password?'تغییر/حذف رمز':'قرار دادن رمز'}"><i class="ti ti-${k.has_password?'lock':'lock-open'}"></i></button>
        <button class="btn btn-o btn-sm btn-icon" onclick="toggleNodeKeyState('${k.key_id}',${k.revoked})" title="${k.revoked?'فعال‌سازی':'غیرفعال کردن'}"><i class="ti ti-${k.revoked?'player-play':'player-pause'}"></i></button>
        <button class="btn btn-d btn-sm btn-icon" onclick="deleteNodeKey('${k.key_id}')" title="حذف کامل"><i class="ti ti-trash"></i></button>
      </div>
    </div>`;
  }).join('');
}

async function loadNodeKeys(){
  try{
    const r=await authF('/api/nodes/keys');
    const d=await r.json();
    renderNodeKeys(d.keys||[]);
  }catch(e){}
}

async function toggleNodeKeyState(keyId,isRevoked){
  try{
    const r=await authF('/api/nodes/keys/'+keyId,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:isRevoked})});
    if(!r.ok) throw new Error();
    toast(isRevoked?'کلید فعال شد ✓':'کلید غیرفعال شد','ok');
    loadNodeKeys();
  }catch(e){ toast('خطا در تغییر وضعیت','err'); }
}

async function setNodeKeyPassword(keyId,hasPassword){
  const pw=prompt(hasPassword?'رمز جدید را وارد کنید (برای حذف رمز، خالی بگذارید و تایید کنید):':'رمز موردنظر را برای این کلید وارد کنید:','');
  if(pw===null) return;
  try{
    const r=await authF('/api/nodes/keys/'+keyId,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
    if(!r.ok) throw new Error();
    toast(pw.trim()?'رمز تنظیم شد ✓':'رمز حذف شد ✓','ok');
    loadNodeKeys();
  }catch(e){ toast('خطا در تغییر رمز','err'); }
}

async function deleteNodeKey(keyId){
  if(!confirm('این کلید برای همیشه حذف شود؟ پنل متصل با این کلید دیگر دسترسی نخواهد داشت.')) return;
  try{
    const r=await authF('/api/nodes/keys/'+keyId,{method:'DELETE'});
    if(!r.ok) throw new Error();
    toast('کلید حذف شد ✓','ok');
    loadNodeKeys();
  }catch(e){ toast('خطا در حذف کلید','err'); }
}

function openNodeConnectModal(){
  document.getElementById('nc-key').value='';
  document.getElementById('nc-label').value='';
  document.getElementById('nc-password').value='';
  document.getElementById('nc-host-preview').textContent='—';
  ncSetError(null);
  openModal('modal-node-connect');
}

function previewNodeKey(){
  const raw=document.getElementById('nc-key').value.trim();
  const el=document.getElementById('nc-host-preview');
  if(!raw.startsWith('rvg-')||!raw.slice(4).includes('.')){ el.textContent='—'; return; }
  try{
    const hostPart=raw.slice(4).split('.')[0];
    let b64=hostPart.replace(/-/g,'+').replace(/_/g,'/');
    while(b64.length%4) b64+='=';
    const host=decodeURIComponent(escape(atob(b64)));
    el.textContent=host||'—';
  }catch(e){ el.textContent='—'; }
}

function ncSetError(msg){
  const el=document.getElementById('nc-error');
  if(!el) return;
  const span=el.querySelector('span');
  if(!msg){ el.style.display='none'; if(span)span.textContent=''; return; }
  if(span)span.textContent=msg;
  el.style.display='flex';
}
async function connectNode(){
  const key=document.getElementById('nc-key').value.trim();
  const label=document.getElementById('nc-label').value.trim();
  const password=document.getElementById('nc-password').value;
  ncSetError(null);
  if(!key){ toast('کلید را وارد کنید','err'); return; }
  const btn=document.getElementById('nc-btn');
  btn.disabled=true;
  try{
    const r=await authF('/api/nodes/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,label,password})},true);
    const d=await r.json().catch(()=>({}));
    if(!r.ok){
      let msg = d.detail||'اتصال برقرار نشد';
      if(d.detail==='PASSWORD_REQUIRED') msg='این نود دارای رمز عبور است؛ لطفاً رمز را وارد کنید';
      else if(d.detail==='PASSWORD_INVALID') msg='رمز عبور وارد شده اشتباه است';
      else if(r.status===401) msg='کلید یا رمز عبور معتبر نیست';
      ncSetError(msg);
      document.getElementById('nc-password').focus();
      return;
    }
    toast('به نود متصل شد ✓','ok');
    closeModal('modal-node-connect');
    document.getElementById('nc-key').value='';
    document.getElementById('nc-label').value='';
    document.getElementById('nc-password').value='';
    loadNodes();
  }catch(e){ ncSetError(e.message||'اتصال برقرار نشد'); }
  finally{ btn.disabled=false; }
}

function nodePermPill(node,part){
  const on = !!(node.share||{})[part];
  return `<div class="node-perm ${on?'on':''}" onclick='toggleNodeShare("${node.node_id}","${part}",this)'><div class="cfg-check ${on?'checked':''}"><i class="ti ti-check"></i></div> ${NK_PERM_LABELS[part]}</div>`;
}

function renderNodes(data){
  const nodes=data.nodes||[], totals=data.totals||{};
  document.getElementById('nodes-pg-cnt').textContent=toFa(nodes.length)+' نود';
  document.getElementById('nodes-online-txt').textContent=toFa(totals.nodes_online||0)+' از '+toFa(totals.nodes_total||0)+' آنلاین';
  document.getElementById('na-used').textContent=fmtB(totals.used_bytes||0);
  document.getElementById('na-used-sub').textContent='این پنل '+fmtB(totals.local_used_bytes||0)+' + نودها '+fmtB(totals.node_used_bytes||0);
  document.getElementById('na-links').textContent=toFa(totals.links||0);
  document.getElementById('na-links-sub').textContent='از '+toFa(totals.active_links||0)+' فعال';
  document.getElementById('na-subs').textContent=toFa(totals.subs||0);
  document.getElementById('na-reqs').textContent=toFa(totals.requests||0);

  const grid=document.getElementById('nodes-grid'), empty=document.getElementById('nodes-empty');
  if(!nodes.length){ grid.innerHTML=''; empty.style.display=''; return; }
  empty.style.display='none';
  grid.innerHTML = nodes.map(n=>{
    const off = n.disabled || !n.enabled;
    const err = !off && !n.online;
    const stat = n.stats||{};
    const statusChip = n.online?'<span class="exp-chip ec-ok"><i class="ti ti-circle-check" style="font-size:9px"></i> آنلاین</span>':(off?'<span class="exp-chip ec-exp">غیرفعال</span>':'<span class="exp-chip ec-warn">آفلاین</span>');
    return `
    <div class="node-card ${off?'is-off':''} ${err?'is-err':''}">
      <div class="node-card-bar"></div>
      <div class="node-card-body">
        <div class="node-head">
          <div class="node-avatar ${n.online?'online':''}"><i class="ti ti-topology-star-3"></i><span class="node-avatar-dot"></span></div>
          <div class="node-titles">
            <div class="node-name">${esc(n.label)} ${statusChip}</div>
            <div class="node-host" onclick="navigator.clipboard.writeText('${esc(n.host)}').then(()=>toast('کپی شد ✓','ok'))" title="برای کپی کلیک کنید"><i class="ti ti-server-2"></i>${esc(n.host)}</div>
            <div class="node-meta"><i class="ti ti-refresh"></i>${n.last_sync_at?('همگام‌سازی: '+esc(n.last_sync_at.slice(0,19).replace('T',' '))):'هنوز همگام نشده'}</div>
          </div>
        </div>
        ${n.error?`<div class="node-err"><i class="ti ti-alert-triangle"></i><span>${esc(n.error)}</span></div>`:''}
        <div class="node-stats">
          <div class="node-stat"><i class="ti ti-transfer"></i><div class="node-stat-val">${fmtB((stat.total_bytes)||0)}</div><div class="node-stat-label">مصرف</div></div>
          <div class="node-stat"><i class="ti ti-arrows-exchange"></i><div class="node-stat-val">${toFa(stat.active_connections||0)}</div><div class="node-stat-label">اتصال فعال</div></div>
          <div class="node-stat"><i class="ti ti-link"></i><div class="node-stat-val">${toFa(stat.links_count||0)}</div><div class="node-stat-label">کانفیگ</div></div>
        </div>
        <div class="node-perms">
          ${['usage','links','subs','requests','logs'].map(p=>nodePermPill(n,p)).join('')}
        </div>
      </div>
      <div class="node-foot">
        <button class="btn btn-o btn-sm" onclick="toggleNodeEnabled('${n.node_id}',${n.enabled===false})"><i class="ti ti-${n.enabled===false?'player-play':'player-pause'}"></i> ${n.enabled===false?'فعال‌سازی':'غیرفعال'}</button>
        <button class="btn btn-d btn-sm" onclick="disconnectNode('${n.node_id}')"><i class="ti ti-plug-connected-x"></i> قطع اتصال</button>
      </div>
    </div>`;
  }).join('');
}

async function toggleNodeShare(nodeId,part,el){
  const willOn = !el.querySelector('.cfg-check').classList.contains('checked');
  el.querySelector('.cfg-check').classList.toggle('checked',willOn);
  el.classList.toggle('on',willOn);
  try{
    const r=await authF('/api/nodes/'+nodeId,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({share:{[part]:willOn}})});
    if(!r.ok) throw new Error();
  }catch(e){ toast('خطا در ذخیره تنظیمات','err'); loadNodes(); }
}

async function toggleNodeEnabled(nodeId,enable){
  try{
    const r=await authF('/api/nodes/'+nodeId,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:enable})});
    if(!r.ok) throw new Error();
    toast(enable?'نود فعال شد ✓':'نود غیرفعال شد','ok');
    loadNodes();
  }catch(e){ toast('خطا در تغییر وضعیت','err'); }
}

async function disconnectNode(nodeId){
  if(!confirm('اتصال به این نود قطع شود؟')) return;
  try{
    const r=await authF('/api/nodes/'+nodeId,{method:'DELETE'});
    if(!r.ok) throw new Error();
    toast('اتصال قطع شد ✓','ok');
    loadNodes();
  }catch(e){ toast('خطا در قطع اتصال','err'); }
}

async function loadNodes(fresh){
  try{
    const r=await authF('/api/nodes/aggregate'+(fresh?'?fresh=1':''));
    const d=await r.json();
    renderNodes(d);
  }catch(e){netErr(e,'نودها')}
}

function loadNodesPage(){ loadNodeKeys(); loadNodes(); }

// ═════════════════════════════════════════════════════════════════════════════
// JavaScript برای بخش آزمایشی (Experimental Section)
// حالت: AUTO-ENABLED — بعد از deploy خودکار فعال است (مگر EMIX_EXPERIMENTAL=0)
// ═════════════════════════════════════════════════════════════════════════════
async function loadExperimentalPage(){
  try{
    const r = await authF('/api/exp/status');
    if(!r.ok){
      document.getElementById('exp-status-badge').textContent = '⚠ بخش غیرفعال';
      document.getElementById('exp-status-badge').style.color = '#EF4444';
      document.getElementById('exp-features-grid').innerHTML = `
        <div style="grid-column:1/-1;text-align:center;padding:40px">
          <i class="ti ti-lock-off" style="font-size:48px;color:#EF4444;opacity:.6"></i>
          <h3 style="margin-top:14px;color:#EF4444">بخش آزمایشی غیرفعال شده</h3>
          <p style="color:var(--t3);font-size:12px;margin-top:8px;line-height:1.6">
            ادمین با <code style="background:rgba(0,0,0,.3);padding:2px 6px;border-radius:4px;color:#EF4444">EMIX_EXPERIMENTAL=0</code>
            آن را غیرفعال کرده است. برای فعال‌سازی، این متغیر را حذف یا به <code style="background:rgba(0,0,0,.3);padding:2px 6px;border-radius:4px;color:#10B981">1</code> تنظیم کنید و Deploy Latest Commit را بزنید.
          </p>
        </div>`;
      return;
    }
    const d = await r.json();
    document.getElementById('exp-status-badge').innerHTML = d.experimental_enabled ?
      '✓ فعال — ' + d.features.filter(f=>f.enabled).length + ' فیچر' :
      '⚠ غیرفعال (EMIX_EXPERIMENTAL=0)';
    document.getElementById('exp-status-badge').style.color = d.experimental_enabled ? '#10B981' : '#FACC15';
    // Render feature cards
    const grid = document.getElementById('exp-features-grid');
    grid.innerHTML = d.features.map(f => `
      <div class="exp-feature-card" style="padding:14px;border-radius:14px;background:rgba(139,92,246,${f.enabled ? '.08' : '.03'});border:1px solid rgba(139,92,246,${f.enabled ? '.4' : '.15'});">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;gap:8px;flex-wrap:wrap">
          <div style="font-weight:700;font-size:13px;flex:1;min-width:0;word-break:break-word">${f.key}</div>
          <span style="font-size:10px;padding:2px 8px;border-radius:6px;background:${f.enabled ? 'rgba(16,185,129,.2)' : 'rgba(0,0,0,.3)'};color:${f.enabled ? '#10B981' : 'var(--t3)'};font-weight:600;flex-shrink:0">
            ${f.enabled ? '✓ ON' : '✗ OFF'}
          </span>
        </div>
        <div style="font-size:11px;color:var(--t3);line-height:1.5;margin-bottom:8px">${f.description}</div>
        <div style="font-size:10px;color:var(--t4);font-family:monospace;word-break:break-all">${f.env_var}=1</div>
        ${f.requires_experimental ? '<div style="font-size:10px;color:#FACC15;margin-top:4px">⚠ نیاز به EMIX_EXPERIMENTAL=1</div>' : ''}
      </div>
    `).join('');
    // Render stealth grid
    const stealthR = await authF('/api/exp/stealth/registry');
    if(stealthR.ok){
      const sd = await stealthR.json();
      document.getElementById('exp-stealth-grid').innerHTML = sd.stealth_methods.map(m => `
        <div class="exp-stealth-card" style="padding:12px;border-radius:12px;background:rgba(0,0,0,.3);border:1px solid rgba(139,92,246,${m.enabled ? '.4' : '.15'});">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:6px;flex-wrap:wrap">
            <div style="font-weight:700;font-size:12px;flex:1;min-width:0;word-break:break-word">${m.name}</div>
            <span style="font-size:9px;padding:1px 6px;border-radius:4px;background:${m.enabled ? 'rgba(16,185,129,.2)' : 'rgba(0,0,0,.3)'};color:${m.enabled ? '#10B981' : 'var(--t3)'};flex-shrink:0">${m.enabled ? 'ON' : 'OFF'}</span>
          </div>
          <div style="font-size:10px;color:var(--t3);line-height:1.4">${m.description}</div>
          <div style="font-size:9px;color:var(--t4);margin-top:4px">پلتفرم: ${m.platform}</div>
        </div>
      `).join('');
    }else{
      document.getElementById('exp-stealth-grid').innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:14px;color:var(--t3);font-size:11px">بخش استتار فعال نیست</div>';
    }
  }catch(e){
    document.getElementById('exp-status-badge').textContent = '⚠ بخش غیرفعال';
    document.getElementById('exp-features-grid').innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--t3);font-size:12px">${e.message}</div>`;
  }
}

// ── Emit link functions ──────────────────────────────────────────────
// One-click generation — auto-fills UUID, address, port from the panel's own host.
// No manual input required.
function _autoUuid() {
  // Generate a UUID v4 client-side (crypto.randomUUID or fallback)
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random()*16|0, v = c==='x'?r:(r&0x3|0x8);
    return v.toString(16);
  });
}
function _autoHost() {
  // Use the panel's own host from the URL
  return window.location.hostname;
}
async function expEmitLink(type){
  // Auto-fill all fields — one-click generation
  const host = _autoHost();
  const uuid = _autoUuid();
  const port = 443;
  let body = {};
  if (type === 'vmess') {
    body = {address: host, port, uuid, name: `EMIX-VMess-${uuid.slice(0,8)}`, net: 'ws', host, path: '/ws/' + uuid, sni: host, fp: 'chrome'};
  } else if (type === 'vless-reality') {
    // Reality needs a public key — we can't auto-generate it (needs xray-core)
    // Fall back to a known public test key (won't actually connect but the link format is valid)
    body = {address: host, port, uuid, pbk: 'N'+uuid.slice(0,32), sni: 'www.cloudflare.com', fp: 'chrome', name: `EMIX-Reality-${uuid.slice(0,8)}`};
  } else if (type === 'trojan-reality') {
    body = {address: host, port, password: uuid, pbk: 'N'+uuid.slice(0,32), sni: 'www.cloudflare.com', fp: 'chrome', name: `EMIX-TrojanReality-${uuid.slice(0,8)}`};
  } else if (type === 'ss2022') {
    // Generate a random 32-byte base64url password
    const pw = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))));
    body = {method: '2022-blake3-aes-256-gcm', password: pw, address: host, port, name: `EMIX-SS2022-${uuid.slice(0,8)}`};
  } else if (type === 'spiderx') {
    body = {uuid, sub_id: ''};
  } else if (type === 'finalmask') {
    body = {base_link: `vless://${uuid}@${host}:${port}?encryption=none&security=tls&type=ws&host=${host}&path=/ws/${uuid}&sni=${host}&fp=chrome`, fm_config: {tls_fragment: true, salamander: false, bbr: false, noise: 0}};
  } else if (type === 'utls') {
    body = {link: `vless://${uuid}@${host}:${port}?encryption=none&security=tls&type=ws&host=${host}&path=/ws/${uuid}&sni=${host}&fp=chrome`, fp: 'chrome'};
  }
  try{
    const r = await authF('/api/exp/link/' + type.replace('_','-'), { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
    const d = await r.json();
    if(d.ok){
      navigator.clipboard.writeText(d.link).then(()=>toast('✓ لینک تولید شد و کپی شد:\n\n' + d.link));
    }else{
      alert('⚠ ' + (d.detail || 'خطا در تولید لینک'));
    }
  }catch(e){ alert('⚠ خطا: ' + e.message); }
}

async function expSub(format){
  // get all links first
  try{
    const lr = await authF('/api/links');
    const ld = await lr.json();
    const links = (ld.links || []).map(l => ({url: l.url || '', name: l.name || ''})).filter(l => l.url);
    if(!links.length){ alert('هیچ کانفیگی موجود نیست'); return; }
    const r = await authF('/api/exp/subscription', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ links: links.map(l=>l.url), remarks: links.map(l=>l.name), format }) });
    const d = await r.json();
    if(d.ok){
      const blob = new Blob([d.content], {type:'text/plain'});
      const u = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = u;
      a.download = 'subscription.' + format + (format==='clash' ? '.yaml' : format==='json' ? '.json' : '.txt');
      a.click();
      URL.revokeObjectURL(u);
    }else{
      alert('⚠ ' + (d.detail || 'خطا'));
    }
  }catch(e){ alert('⚠ خطا: ' + e.message); }
}

async function expRecheckAntiDPI(){
  document.getElementById('exp-antidpi-result').innerHTML = '<div style="padding:14px;text-align:center;color:var(--t3);font-size:12px"><i class="ti ti-loader-2 ti-spin"></i> در حال بررسی...</div>';
  try{
    const r = await authF('/api/exp/recheck-anti-dpi', { method:'POST' });
    const d = await r.json();
    if(!d.ok){ throw new Error(d.detail || 'error'); }
    let html = '<div style="font-size:12px;color:var(--t3);margin-bottom:8px">تعداد: ' + d.total + ' کانفیگ ضد-DPI</div>';
    if(d.anti_dpi_configs && d.anti_dpi_configs.length){
      html += d.anti_dpi_configs.map(c => `
        <div style="padding:10px 12px;background:rgba(0,0,0,.3);border-radius:10px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">
          <div>
            <div style="font-weight:700;font-size:12px">${c.name || c.uuid.slice(0,8)}</div>
            <div style="font-size:10px;color:var(--t3);">${c.type_label}</div>
          </div>
          <div>
            <button class="btn btn-o" style="font-size:10px;padding:4px 8px" onclick="pingLink('${c.uuid}')"><i class="ti ti-activity-heartbeat"></i> پینگ</button>
          </div>
        </div>`).join('');
    }else{
      html += '<div style="text-align:center;padding:14px;color:var(--t3);font-size:12px">هیچ کانفیگ ضد-DPI یافت نشد</div>';
    }
    document.getElementById('exp-antidpi-result').innerHTML = html;
  }catch(e){
    document.getElementById('exp-antidpi-result').innerHTML = '<div style="padding:14px;color:#EF4444;font-size:12px">⚠ ' + e.message + '</div>';
  }
}

// ── Unified Configs View (Phase 8) ────────────────────────────────────
let _unifiedConfigsCurrent = [];
let _unifiedConfigsFilter = 'all';

async function loadUnifiedConfigsPage(){
  try{
    const r = await authF('/api/exp/unified-configs');
    if(!r.ok){
      document.getElementById('unified-configs-grid').innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--t3);font-size:12px">⚠ بخش آزمایشی فعال نیست (EMIX_EXPERIMENTAL=1)</div>';
      return;
    }
    const d = await r.json();
    _unifiedConfigsCurrent = d.configs || [];
    renderUnifiedConfigs();
  }catch(e){
    document.getElementById('unified-configs-grid').innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:30px;color:#EF4444;font-size:12px">' + e.message + '</div>';
  }
}

function filterUnifiedConfigs(section){
  _unifiedConfigsFilter = section;
  renderUnifiedConfigs();
}

function renderUnifiedConfigs(){
  const grid = document.getElementById('unified-configs-grid');
  let configs = _unifiedConfigsCurrent;
  if(_unifiedConfigsFilter !== 'all'){
    configs = configs.filter(c => c.section === _unifiedConfigsFilter);
  }
  if(!configs.length){
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--t3);font-size:12px">هیچ کانفیگی یافت نشد</div>';
    return;
  }
  const sectionColors = {
    'links': '#8B5CF6',
    'subscriptions': '#FACC15',
    'nodes': '#4ADE80',
    'vpn-pro': '#3B82F6',
    'experimental': '#EC4899',
  };
  const protoIcon = (proto) => {
    if(!proto) return 'ti ti-link';
    if(proto.includes('vless')) return 'ti ti-bolt';
    if(proto.includes('trojan')) return 'ti ti-shield-lock';
    if(proto.includes('shadowsocks') || proto.includes('ss')) return 'ti ti-key';
    if(proto.includes('mtproto')) return 'ti ti-brand-telegram';
    if(proto.includes('vmess')) return 'ti ti-atom';
    if(proto.includes('wireguard')) return 'ti ti-shield-lock-filled';
    if(proto.includes('openvpn')) return 'ti ti-lock';
    return 'ti ti-link';
  };
  grid.innerHTML = configs.map(c => {
    const color = sectionColors[c.section] || '#888';
    const colorRgb = color === '#8B5CF6' ? '139,92,246' : color === '#FACC15' ? '250,204,21' : color === '#4ADE80' ? '74,222,128' : color === '#3B82F6' ? '59,130,246' : '236,72,153';
    const url = c.url || c.vless_link || '';
    const canCopy = url && url.startsWith(('vless://','trojan://','ss://','vmess://','tg://','socks5://'));
    return `
      <div class="cfg-card" style="padding:14px;border-radius:14px;background:var(--card);border:1px solid rgba(${colorRgb},.25);">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;gap:8px;flex-wrap:wrap">
          <div style="flex:1;min-width:0;display:flex;align-items:center;gap:8px">
            <i class="${protoIcon(c.type)}" style="color:${color};font-size:16px"></i>
            <div style="min-width:0">
              <div style="font-weight:700;font-size:13px;color:var(--t1);margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(c.name || c.uuid.slice(0,8))}</div>
              <div style="font-size:10px;color:var(--t3)">${esc(c.type_label || c.type || 'unknown')}</div>
            </div>
          </div>
          <span style="font-size:9px;padding:2px 6px;border-radius:4px;background:rgba(${colorRgb},.15);color:${color};font-weight:600;text-transform:uppercase;flex-shrink:0">${c.section}</span>
        </div>
        ${url ? `<div style="font-size:9.5px;color:var(--t4);font-family:monospace;word-break:break-all;background:rgba(0,0,0,.4);padding:6px 8px;border-radius:6px;margin-top:6px;max-height:60px;overflow-y:auto;line-height:1.4">${esc(url)}</div>` : ''}
        ${c.endpoint ? '<div style="font-size:10px;color:var(--t3);margin-top:4px"><i class="ti ti-server" style="font-size:9px"></i> ' + esc(c.endpoint) + '</div>' : ''}
        ${canCopy ? `
        <div style="display:flex;gap:6px;margin-top:8px">
          <button class="btn btn-sm btn-g btn-icon" onclick="navigator.clipboard.writeText('${esc(url)}').then(()=>toast('لینک کپی شد ✓','ok'))" title="کپی لینک"><i class="ti ti-copy"></i></button>
          <button class="btn btn-sm btn-g btn-icon" onclick="showQR('${esc(url)}')" title="QR Code"><i class="ti ti-qrcode"></i></button>
          ${c.sub_url || c.section === 'links' ? `<button class="btn btn-sm btn-g btn-icon" onclick="navigator.clipboard.writeText('${esc(window.location.origin + (c.sub_url || '/sub/' + c.uuid))}').then(()=>toast('Sub URL کپی شد','ok'))" title="Sub URL"><i class="ti ti-rss"></i></button>` : ''}
        </div>` : ''}
      </div>`;
  }).join('');
}
</script>
</body></html>"""


def get_public_page_html(uuid_key: str) -> str:
    """صفحه پابلیک ساب v3 — طراحی حرفه‌ای‌تر با هدرهای مناسب برای برنامه‌های خارجی + نوار مصرف کل"""
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>EMIX Sub</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.19.0/dist/tabler-icons.min.css">
<style>
*{{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}}
:root{{
  --bg:#0A0A0F;--bg2:#14141C;--bg3:#1E1E28;
  --card:rgba(20,20,28,0.72);--card-b:rgba(139,92,246,0.16);--card-bh:rgba(139,92,246,0.32);
  --accent:#8B5CF6;--accent2:#FACC15;--accent-d:rgba(139,92,246,0.12);
  --green:#22C55E;--green-bg:rgba(34,197,94,0.12);--green-t:#4ADE80;
  --red:#EF4444;--red-bg:rgba(239,68,68,0.12);--red-t:#F87171;
  --amber:#FACC15;--amber-bg:rgba(250,204,21,0.12);--amber-t:#FDE047;
  --purple:#A855F7;--purple-bg:rgba(168,85,247,0.14);--purple-t:#C4B5FD;
  --t1:#FFFFFF;--t2:#9CA3AF;--t3:#6B7280;
  --radius:18px;--shadow:0 12px 40px rgba(0,0,0,0.55);
  --serif:'Vazirmatn',sans-serif;
}}
[data-theme="light"]{{
  --bg:#F5F5F7;--bg2:#FFFFFF;--bg3:#E8EAF0;
  --card:#FFFFFF;--card-b:rgba(124,58,237,0.15);--card-bh:rgba(124,58,237,0.32);
  --accent:#7C3AED;--accent2:#CA8A04;--accent-d:rgba(124,58,237,0.08);
  --green:#16A34A;--green-bg:rgba(22,163,74,0.08);--green-t:#15803D;
  --red:#DC2626;--red-bg:rgba(220,38,38,0.08);--red-t:#B91C1C;
  --amber:#CA8A04;--amber-bg:rgba(202,138,4,0.08);--amber-t:#A16207;
  --purple:#8B5CF6;--purple-bg:rgba(139,92,246,0.08);--purple-t:#6D28D9;
  --t1:#0A0A0F;--t2:#4B5563;--t3:#9CA3AF;
  --shadow:0 12px 36px rgba(0,0,0,0.12);
}}
html,body{{min-height:100%;background:var(--bg);font-family:var(--serif);color:var(--t1);font-size:14px;transition:background .35s,color .35s}}
.bg-fx{{position:fixed;inset:0;background:radial-gradient(ellipse 70% 45% at 50% -8%,rgba(139,92,246,0.16),transparent 62%),var(--bg);z-index:0;pointer-events:none;transition:background .35s}}
.grid-fx{{position:fixed;inset:0;background-image:linear-gradient(rgba(139,92,246,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(139,92,246,0.03) 1px,transparent 1px);background-size:46px 46px;z-index:0;pointer-events:none}}
.wrap{{position:relative;z-index:10;max-width:800px;margin:0 auto;padding:24px 16px 64px}}
.top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:26px;gap:10px}}
.brand{{display:flex;align-items:center;gap:11px;min-width:0}}
.brand-img{{width:40px;height:40px;border-radius:12px;overflow:hidden;border:1px solid var(--card-b);box-shadow:0 0 0 1px rgba(255,255,255,.02);flex-shrink:0}}
.brand-img img{{width:100%;height:100%;object-fit:cover}}
.brand-name{{font-size:14.5px;font-weight:800;color:var(--t1);letter-spacing:-.01em}}
.brand-sub{{font-size:9.5px;color:var(--t3);font-weight:500}}
.top-actions{{display:flex;align-items:center;gap:6px;flex-shrink:0}}
.icon-btn{{width:36px;height:36px;border-radius:11px;background:var(--card);border:1px solid var(--card-b);color:var(--t2);display:flex;align-items:center;justify-content:center;font-size:16px;cursor:pointer;transition:.18s}}
.icon-btn:hover{{background:var(--accent-d);color:var(--accent2);border-color:var(--card-bh)}}

.sub-info{{background:var(--card);border:1px solid var(--card-b);border-radius:22px;padding:24px 24px 22px;margin-bottom:16px;box-shadow:var(--shadow);position:relative;overflow:hidden}}
.sub-info::before{{content:'';position:absolute;top:0;right:0;width:160px;height:160px;background:radial-gradient(circle at top right,rgba(139,92,246,.14),transparent 70%);pointer-events:none}}
.sub-eyebrow{{font-size:10px;font-weight:700;color:var(--accent2);text-transform:uppercase;letter-spacing:.12em;margin-bottom:8px;display:flex;align-items:center;gap:6px}}
.sub-eyebrow i{{font-size:13px}}
.sub-name{{font-size:23px;font-weight:800;color:var(--t1);margin-bottom:6px;letter-spacing:-.02em}}
.sub-desc{{font-size:12.5px;color:var(--t2);line-height:1.8;margin-bottom:14px}}
.sub-meta-row{{font-size:10.5px;color:var(--t3);margin-bottom:14px;display:flex;align-items:center;gap:6px}}
.sub-sub-box{{background:var(--accent-d);border:1px solid var(--card-b);border-radius:13px;padding:12px 14px;display:flex;align-items:center;gap:9px;flex-wrap:wrap}}
.sub-sub-url{{font-family:ui-monospace,monospace;font-size:10px;color:var(--accent2);word-break:break-all;flex:1;min-width:140px}}

/* ══════ نوار مصرف کل — بخش جدید ══════ */
.total-usage-box{{background:rgba(0,0,0,.14);border:1px solid var(--card-b);border-radius:13px;padding:14px 16px;margin-top:12px}}
[data-theme="light"] .total-usage-box{{background:rgba(124,58,237,.04)}}
.tu-head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:9px;gap:8px;flex-wrap:wrap}}
.tu-label{{font-size:10.5px;color:var(--t2);font-weight:700;display:flex;align-items:center;gap:6px}}
.tu-label i{{color:var(--accent2);font-size:14px}}
.tu-val{{font-size:11.5px;font-weight:800;color:var(--t1);font-family:ui-monospace,monospace}}
.tu-bar{{height:9px;border-radius:6px;background:rgba(139,92,246,0.14);overflow:hidden;position:relative}}
.tu-bar-f{{height:100%;border-radius:6px;transition:width .6s ease;position:relative;overflow:hidden}}
.tu-bar-f::after{{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent);width:40%;animation:tuShimmer 1.8s linear infinite}}
@keyframes tuShimmer{{0%{{transform:translateX(-120%)}}100%{{transform:translateX(280%)}}}}
.tu-foot{{display:flex;justify-content:space-between;margin-top:7px;font-size:9.5px;color:var(--t3)}}
.tu-pct{{font-weight:800}}

.stats-bar{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px}}
.stat-card{{background:var(--card);border:1px solid var(--card-b);border-radius:16px;padding:16px 17px;transition:.2s}}
.stat-card:hover{{border-color:var(--card-bh);transform:translateY(-1px)}}
.stat-label{{font-size:9px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.07em;margin-bottom:7px}}
.stat-val{{font-size:22px;font-weight:800;color:var(--t1);line-height:1;letter-spacing:-.01em}}
.stat-sub{{font-size:9.5px;color:var(--t3);margin-top:6px}}

.copy-all-bar{{display:flex;align-items:center;gap:12px;background:linear-gradient(120deg,#8B5CF6 0%,#E8590C 100%);border-radius:18px;padding:16px 19px;margin-bottom:18px;box-shadow:0 10px 30px rgba(139,92,246,.3);flex-wrap:wrap}}
.copy-all-text{{flex:1;min-width:160px}}
.copy-all-title{{font-size:13.5px;font-weight:800;color:#fff;display:flex;align-items:center;gap:6px}}
.copy-all-sub{{font-size:10px;color:rgba(255,255,255,.78);margin-top:3px}}
.copy-all-btn{{background:#fff;color:#E23E1E;border:none;border-radius:12px;padding:10px 19px;font-family:inherit;font-size:12.5px;font-weight:800;cursor:pointer;display:flex;align-items:center;gap:6px;transition:.18s;white-space:nowrap}}
.copy-all-btn:hover{{transform:translateY(-1px);box-shadow:0 6px 16px rgba(0,0,0,.22)}}
.copy-all-btn:active{{transform:translateY(0) scale(.98)}}

.cfg-title{{font-size:12px;font-weight:800;color:var(--t2);margin-bottom:13px;display:flex;align-items:center;gap:6px;text-transform:uppercase;letter-spacing:.07em}}
.cfg-title i{{color:var(--accent);font-size:15px}}
.cfg-grid{{display:grid;gap:13px}}

.cfg-card{{background:var(--card);border:1px solid var(--card-b);border-radius:18px;transition:all .2s;position:relative;overflow:hidden}}
.cfg-card:hover{{border-color:var(--card-bh);box-shadow:var(--shadow)}}
.cfg-top{{padding:17px 19px 15px;position:relative}}
.cfg-top::after{{content:'';position:absolute;top:0;right:0;width:3px;height:100%;background:var(--green)}}
.cfg-card.inactive .cfg-top::after{{background:var(--red)}}
.cfg-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:12px;flex-wrap:wrap}}
.cfg-label{{font-size:14.5px;font-weight:700;color:var(--t1)}}
.cfg-badges{{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}}
.proto-chip{{font-size:9px;padding:3px 8px;border-radius:7px;font-weight:800;letter-spacing:.02em}}
.pc-ws{{background:var(--accent-d);color:var(--accent2)}}
.pc-trojan{{background:var(--purple-bg);color:#FFB199}}
.pc-xhttp{{background:var(--purple-bg);color:var(--purple-t)}}
.pc-ultra{{background:var(--green-bg);color:var(--green-t)}}
.pc-ss{{background:var(--purple-bg);color:#FFB199}}
.cfg-status{{display:flex;align-items:center;gap:5px;font-size:10px;font-weight:700;padding:4px 10px;border-radius:20px;white-space:nowrap}}
.cfg-status.ok{{background:var(--green-bg);color:var(--green-t)}}
.cfg-status.no{{background:var(--red-bg);color:var(--red-t)}}
.cfg-usage{{margin-bottom:4px}}
.ubar{{height:6px;border-radius:4px;background:rgba(139,92,246,0.14);overflow:hidden;margin-bottom:5px;min-width:100%}}
.ubar-f{{height:100%;border-radius:4px;transition:width .5s ease;min-width:2px}}
.utxt{{font-size:10px;color:var(--t3);display:flex;justify-content:space-between;gap:8px}}

.cfg-tear{{position:relative;height:0;border-top:1.5px dashed var(--card-b);margin:0 19px}}
.cfg-tear::before,.cfg-tear::after{{content:'';position:absolute;top:50%;width:18px;height:18px;border-radius:50%;background:var(--bg);transform:translateY(-50%);border:1px solid var(--card-b)}}
.cfg-tear::before{{right:-28px}}
.cfg-tear::after{{left:-28px}}

.cfg-bottom{{padding:15px 19px 18px}}
.cfg-link-toggle{{width:100%;display:flex;align-items:center;justify-content:space-between;gap:10px;background:transparent;border:1px dashed var(--card-b);border-radius:11px;padding:10px 13px;cursor:pointer;font-family:inherit;color:var(--t2);font-size:11.5px;font-weight:600;transition:.15s}}
.cfg-link-toggle:hover{{background:var(--accent-d);border-color:var(--card-bh);color:var(--accent2)}}
.cfg-link-toggle .ltl{{display:flex;align-items:center;gap:7px}}
.cfg-link-toggle i.ti-chevron-down{{transition:transform .2s}}
.cfg-link-toggle.open i.ti-chevron-down{{transform:rotate(180deg)}}
.cfg-vless-wrap{{display:grid;grid-template-rows:0fr;transition:grid-template-rows .25s ease}}
.cfg-vless-wrap.open{{grid-template-rows:1fr}}
.cfg-vless-inner{{overflow:hidden}}
.cfg-vless{{background:rgba(0,0,0,.22);border:1px solid var(--card-b);border-radius:10px;padding:11px 13px;font-size:9.8px;font-family:ui-monospace,monospace;color:var(--accent2);word-break:break-all;line-height:1.7;margin-top:9px;max-height:90px;overflow-y:auto}}
[data-theme="light"] .cfg-vless{{background:rgba(124,58,237,.05)}}
.cfg-actions{{display:flex;gap:7px;flex-wrap:wrap;margin-top:11px}}
.btn{{font-family:inherit;font-size:11.5px;font-weight:700;border-radius:10px;padding:8px 15px;cursor:pointer;display:inline-flex;align-items:center;gap:5px;border:none;transition:all .15s;white-space:nowrap}}
.btn i{{font-size:13px}}
.btn-p{{background:linear-gradient(135deg,#8B5CF6,#FACC15);color:#fff;border-radius:999px;box-shadow:0 3px 14px -2px rgba(139,92,246,.5)}}
.btn-p:hover{{background:linear-gradient(135deg,#FF5C3F,#FF9A55)}}
.btn-g{{background:rgba(139,92,246,.12);color:#FFB199;border:1px solid rgba(139,92,246,.25);border-radius:999px}}
.btn-g:hover{{background:rgba(139,92,246,.22)}}
.btn-pur{{background:rgba(168,85,247,.12);color:#FFB199;border:1px solid rgba(168,85,247,.28);border-radius:999px}}
.btn-pur:hover{{background:rgba(168,85,247,.22)}}
.conn-chip{{display:inline-flex;align-items:center;gap:4px;font-size:9.5px;padding:3px 8px;border-radius:20px;background:var(--green-bg);color:var(--green-t);font-weight:700}}
.dot{{width:5px;height:5px;border-radius:50%;background:var(--green);display:inline-block;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}

.lock-stage{{display:flex;align-items:center;justify-content:center;min-height:78vh;padding:20px 0}}
.lock-card{{background:var(--card);border:1px solid var(--card-b);border-radius:26px;padding:0;text-align:center;max-width:380px;width:100%;box-shadow:var(--shadow);overflow:hidden;position:relative}}
.lock-banner{{background:linear-gradient(150deg,rgba(139,92,246,.18),rgba(139,92,246,.02) 70%);padding:38px 30px 26px;position:relative}}
.lock-shield{{width:64px;height:64px;border-radius:18px;background:var(--accent-d);border:1px solid var(--card-bh);display:flex;align-items:center;justify-content:center;margin:0 auto 18px;position:relative}}
.lock-shield::after{{content:'';position:absolute;inset:-7px;border-radius:22px;border:1px solid var(--card-b);animation:breathe 2.6s ease-in-out infinite}}
@keyframes breathe{{0%,100%{{transform:scale(1);opacity:.5}}50%{{transform:scale(1.08);opacity:0}}}}
.lock-shield i{{font-size:28px;color:var(--accent2)}}
.lock-title{{font-size:18px;font-weight:800;margin-bottom:6px;color:var(--t1);letter-spacing:-.01em}}
.lock-sub{{font-size:12px;color:var(--t3);line-height:1.7}}
.lock-form{{padding:24px 30px 30px}}
.lock-field{{position:relative;margin-bottom:13px}}
.lock-inp{{width:100%;padding:13px 44px 13px 44px;border-radius:13px;border:1px solid var(--card-b);background:rgba(0,0,0,.2);color:var(--t1);font-family:inherit;font-size:14px;outline:none;text-align:center;letter-spacing:.14em;transition:.18s}}
[data-theme="light"] .lock-inp{{background:rgba(124,58,237,.05)}}
.lock-inp:focus{{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-d)}}
.lock-eye{{position:absolute;left:13px;top:50%;transform:translateY(-50%);background:none;border:none;color:var(--t3);cursor:pointer;font-size:16px;padding:4px;display:flex}}
.lock-eye:hover{{color:var(--accent2)}}
.lock-lockicon{{position:absolute;right:14px;top:50%;transform:translateY(-50%);color:var(--t3);font-size:15px;pointer-events:none}}
.lock-err{{color:var(--red-t);font-size:11.5px;margin-bottom:10px;min-height:16px;display:flex;align-items:center;justify-content:center;gap:5px}}
.lock-btn{{width:100%;justify-content:center;padding:13px;font-size:13px;border-radius:13px}}
.lock-footer{{padding:14px 30px;border-top:1px solid var(--card-b);font-size:10px;color:var(--t3);display:flex;align-items:center;justify-content:center;gap:6px}}

.empty-state{{text-align:center;padding:80px 20px;color:var(--t3)}}
.empty-state i{{font-size:38px;display:block;margin-bottom:14px}}

.toast{{position:fixed;bottom:22px;left:50%;transform:translateX(-50%) translateY(40px);background:var(--card);border:1px solid var(--card-b);color:var(--t1);border-radius:12px;padding:10px 20px;font-size:12.5px;font-weight:600;opacity:0;transition:all .25s;z-index:999;pointer-events:none;display:flex;align-items:center;gap:7px;box-shadow:var(--shadow);white-space:nowrap}}
.toast.show{{opacity:1;transform:translateX(-50%) translateY(0)}}
.toast.ok{{border-color:rgba(31,184,126,.35);background:var(--green-bg);color:var(--green-t)}}

.qr-modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:600;align-items:center;justify-content:center;backdrop-filter:blur(6px);padding:20px}}
.qr-modal.open{{display:flex}}
.qr-box{{background:var(--card);border:1px solid var(--card-b);border-radius:22px;padding:26px;text-align:center;max-width:340px;width:100%;box-shadow:var(--shadow)}}
.qr-title{{font-size:13.5px;font-weight:800;margin-bottom:16px;color:var(--t1)}}
.qr-img{{border-radius:14px;overflow:hidden;margin-bottom:15px}}
.qr-img img{{width:100%;display:block;background:#fff;padding:10px;border-radius:14px}}

.footer{{text-align:center;padding-top:28px;font-size:10.5px;color:var(--t3)}}
.footer a{{color:var(--accent2);font-weight:700}}

@media(max-width:520px){{
  .stats-bar{{grid-template-columns:1fr 1fr}}
  .stats-bar .stat-card:nth-child(3){{grid-column:1/-1}}
  .sub-name{{font-size:19px}}
  .copy-all-bar{{flex-direction:column;align-items:stretch}}
  .copy-all-btn{{justify-content:center}}
  .wrap{{padding:16px 12px 50px}}
  .lock-banner{{padding:32px 22px 22px}}
  .lock-form{{padding:20px 22px 26px}}
}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style>
<style>
/* EMIX — glass overrides (neon red/orange) */
.sub-info,.stat-card,.cfg-card,.lock-card,.qr-box,.icon-btn{{
  background:rgba(22,18,28,0.55);
  backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);
  border:1px solid rgba(255,255,255,0.07);
  box-shadow:0 18px 50px -24px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.05);
}}
[data-theme="light"] .sub-info,[data-theme="light"] .stat-card,[data-theme="light"] .cfg-card,[data-theme="light"] .lock-card,[data-theme="light"] .qr-box{{background:rgba(255,255,255,0.78)}}
.cfg-card:hover,.stat-card:hover{{border-color:rgba(139,92,246,.35);box-shadow:0 0 30px -12px rgba(139,92,246,.35),inset 0 1px 0 rgba(255,255,255,.05)}}
.brand-img{{border-color:rgba(139,92,246,.35);box-shadow:0 0 18px -2px rgba(139,92,246,.5)}}
.icon-btn:hover{{background:rgba(139,92,246,.12);color:#FFB199;border-color:rgba(139,92,246,.3)}}
.sub-eyebrow i{{color:#FF6A45}}
.sub-sub-box{{background:rgba(139,92,246,.08);border-color:rgba(139,92,246,.22)}}
.sub-sub-url{{color:#FFB199}}
.tu-label i{{color:#FF6A45}}
.tu-bar-f,.ubar-f{{background:linear-gradient(90deg,#FACC15,#8B5CF6)}}
.cfg-vless{{color:#FFB199;border-color:rgba(139,92,246,.18)}}
.cfg-link-toggle:hover{{background:rgba(139,92,246,.1);border-color:rgba(139,92,246,.28);color:#FFB199}}
.pc-ws{{background:rgba(139,92,246,.12);color:#FFB199}}
.pc-ultra{{background:rgba(16,185,129,.12)}}
.cfg-status.ok{{background:rgba(16,185,129,.12)}}
.lock-shield{{background:rgba(139,92,246,.12);border-color:rgba(139,92,246,.3)}}
.lock-shield i{{color:#FACC15}}
.lock-inp:focus{{border-color:#8B5CF6;box-shadow:0 0 0 3px rgba(139,92,246,.14)}}
.qr-img img{{border-radius:12px}}
.cfg-top::after{{background:linear-gradient(180deg,#8B5CF6,#E8590C)}}
.cfg-card.inactive .cfg-top::after{{background:var(--red)}}


/* NixHD premium touches for sub page */
.sub-info{{box-shadow:0 16px 50px rgba(0,0,0,0.55),0 0 0 1px rgba(139,92,246,0.10) inset}}
.sub-info::before{{background:radial-gradient(circle at top right,rgba(139,92,246,0.18),transparent 70%)}}
.sub-eyebrow{{color:var(--accent2)}}
.sub-sub-box{{background:rgba(139,92,246,0.08);border-color:rgba(139,92,246,0.20)}}
.sub-sub-url{{color:var(--accent2)}}
.tu-bar{{background:rgba(139,92,246,0.14)}}
.tu-bar-f{{background:linear-gradient(90deg,var(--accent),var(--accent2))}}

</style>
</head>
<body>
<div class="bg-fx"></div><div class="grid-fx"></div>
<div class="toast" id="toast"></div>
<div class="qr-modal" id="qr-modal" onclick="this.classList.remove('open')">
  <div class="qr-box" onclick="event.stopPropagation()">
    <div class="qr-title" id="qr-label">QR Code</div>
    <div class="qr-img"><img id="qr-img" src="" alt="QR"></div>
    <button class="btn btn-g" style="width:100%;justify-content:center" onclick="document.getElementById('qr-modal').classList.remove('open')"><i class="ti ti-x"></i> بستن</button>
  </div>
</div>
<div class="wrap">
  <div class="top">
    <div class="brand">
      <div class="brand-img"><svg viewBox="0 0 100 100" width="100%" height="100%" role="img" aria-label="EMIX logo"><rect width="100" height="100" fill="#030303"/><circle cx="50" cy="48" r="45" fill="#0B0B0B" stroke="#5A160E" stroke-width="2"/><circle cx="50" cy="48" r="42" fill="none" stroke="#FF3B24" stroke-width="1" opacity=".7"/><path d="M72 24H39C29 24 23 30 23 40V61C23 71 29 77 39 77H73M39 50H64C72 50 76 46 80 39" fill="none" stroke="#7A170F" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" opacity=".6"/><path d="M72 24H39C29 24 23 30 23 40V61C23 71 29 77 39 77H73M39 50H64C72 50 76 46 80 39" fill="none" stroke="#FF4028" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/><text x="50" y="91" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" font-weight="800" letter-spacing="3" fill="#FF3B24">EMIX</text></svg></div>
      <div><div class="brand-name">EMIX</div><div class="brand-sub">Gateway · v9.5</div></div>
    </div>
    <div class="top-actions">
      <button class="icon-btn" id="theme-toggle" onclick="toggleTheme()" title="تغییر تم"><i class="ti ti-sun" id="theme-icon"></i></button>
      <a class="icon-btn" href="https://t.me/emixpi" target="_blank" title="کانال تلگرام"><i class="ti ti-brand-telegram"></i></a>
    </div>
  </div>
  <div id="root">
    <div class="empty-state"><i class="ti ti-loader-2" style="animation:spin 1s linear infinite"></i>در حال بارگذاری...</div>
  </div>
  <div class="footer">کانال رسمی: <a href="https://t.me/emixpi" target="_blank">@emixpi</a> · EMIX v9.5</div>
</div>
<script>
const UUID_KEY='{uuid_key}';
let savedPw='';

let SUB_DATA = {{
  total_used: 0,
  total_limit: 0,
  expiry_date: null,
  links: []
}};

let isDark=localStorage.getItem('rvg-pub-theme')!=='light';
function applyTheme(dark){{
  document.documentElement.setAttribute('data-theme',dark?'dark':'light');
  document.getElementById('theme-icon').className='ti '+(dark?'ti-sun':'ti-moon');
}}
function toggleTheme(){{isDark=!isDark;localStorage.setItem('rvg-pub-theme',isDark?'dark':'light');applyTheme(isDark)}}
applyTheme(isDark);

function toast(msg,type=''){{
  const t=document.getElementById('toast');
  t.textContent=msg;t.className='toast show'+(type?' '+type:'');
  setTimeout(()=>t.classList.remove('show'),2400);
}}
function esc(s){{return String(s||'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
function fmtB(b){{if(!b||b===0)return '0 B';if(b<1024)return b+' B';if(b<1024**2)return (b/1024).toFixed(1)+' KB';if(b<1024**3)return (b/1024**2).toFixed(2)+' MB';return (b/1024**3).toFixed(2)+' GB'}}
function toFa(n){{return String(n).replace(/\\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d])}}
function protoChip(p){{
  p = p || 'vless-ws';
  if(p==='mtproto')return '<span class="proto-chip pc-trojan"><i class="ti ti-brand-telegram"></i> Telegram Proxy</span>';
  if(p.startsWith('shadowsocks')){{
    const isWsVariant = p !== 'shadowsocks';
    return '<span class="proto-chip pc-ss"><i class="ti ti-shield-lock-filled"></i> Shadowsocks'+(isWsVariant?' · '+esc(p.replace('shadowsocks-','')):'')+'</span>';
  }}
  if(p.startsWith('trojan'))return '<span class="proto-chip pc-trojan"><i class="ti ti-shield-lock"></i> '+esc(p)+'</span>';
  if(p.startsWith('xhttp'))return '<span class="proto-chip pc-xhttp">'+esc(p)+'</span>';
  return '<span class="proto-chip pc-ws">VLESS · WS</span>';
}}

function showQR(label,link){{
  document.getElementById('qr-label').textContent=label;
  document.getElementById('qr-img').src='/api/qr?data='+encodeURIComponent(link);
  document.getElementById('qr-modal').classList.add('open');
}}

function toggleLink(i){{
  const wrap=document.getElementById('vw-'+i);
  const btn=document.getElementById('vt-'+i);
  const open=wrap.classList.toggle('open');
  btn.classList.toggle('open',open);
  btn.querySelector('.ltl span').textContent = open ? 'پنهان کردن لینک' : 'نمایش لینک کانفیگ';
}}

async function loadData(pw=''){{
  const url='/api/public/sub/'+UUID_KEY+(pw?'?pw='+encodeURIComponent(pw):'');
  const r=await fetch(url);
  const data = await r.json();

  if (data.total_used !== undefined) {{
    SUB_DATA.total_used = data.total_used;
  }}
  if (data.total_limit !== undefined) {{
    SUB_DATA.total_limit = data.total_limit;
  }}
  if (data.expiry_date !== undefined) {{
    SUB_DATA.expiry_date = data.expiry_date;
  }}
  if (data.links) {{
    SUB_DATA.links = data.links;
  }}

  return data;
}}

function renderLock(name,errMsg=''){{
  document.getElementById('root').innerHTML=`
    <div class="lock-stage">
      <div class="lock-card">
        <div class="lock-banner">
          <div class="lock-shield"><i class="ti ti-shield-lock"></i></div>
          <div class="lock-title">${{esc(name)}}</div>
          <div class="lock-sub">این گروه با رمز محافظت شده. برای دیدن کانفیگ‌ها رمز رو وارد کنید.</div>
        </div>
        <div class="lock-form">
          <div class="lock-err" id="lock-err">${{errMsg ? '<i class="ti ti-alert-circle"></i> '+esc(errMsg) : ''}}</div>
          <div class="lock-field">
            <i class="ti ti-lock lock-lockicon"></i>
            <input class="lock-inp" type="password" id="lock-pw" placeholder="••••••••" autofocus>
            <button class="lock-eye" type="button" onclick="togglePwVis()"><i class="ti ti-eye" id="lock-eye-icon"></i></button>
          </div>
          <button class="btn btn-p lock-btn" onclick="submitLock()"><i class="ti ti-lock-open"></i> ورود به گروه</button>
        </div>
        <div class="lock-footer"><i class="ti ti-shield-check"></i> اتصال شما رمزنگاری‌شده است</div>
      </div>
    </div>
  `;
  const inp=document.getElementById('lock-pw');
  inp.addEventListener('keydown',e=>{{if(e.key==='Enter')submitLock()}});
}}
 
function togglePwVis(){{
  const inp=document.getElementById('lock-pw');
  const icon=document.getElementById('lock-eye-icon');
  const toText = inp.type==='password';
  inp.type = toText ? 'text' : 'password';
  icon.className = 'ti '+(toText ? 'ti-eye-off' : 'ti-eye');
}}

async function submitLock(){{
  const pw=document.getElementById('lock-pw').value;
  const data=await loadData(pw);
  if(data.locked){{renderLock(data.name,'رمز اشتباه است');return}}
  savedPw=pw;
  renderContent(data);
}}

function renderContent(d){{
  const activeCount=d.links.filter(l=>l.active).length;
  const baseSubUrl = d.sub_url || (window.location.protocol + '//' + window.location.host + '/sub-group/' + UUID_KEY);
  const subUrl = baseSubUrl + (savedPw ? '?pw=' + encodeURIComponent(savedPw) : '');

  // محاسبه کل مصرف و تاریخ انقضا
  // نکته: totalLimit فقط روی کانفیگ‌هایی جمع می‌شود که سهمیه محدود دارند (limit_bytes > 0)
  // در غیر این‌صورت یک کانفیگ نامحدود، سقف کل گروه را کاذب بی‌نهایت/گمراه‌کننده می‌کرد.
  let totalUsed = 0;
  let totalLimit = 0;
  let hasUnlimited = false;
  let expiryDate = null;

  d.links.forEach(l => {{
    totalUsed += (l.used_bytes || 0);
    if (l.limit_bytes && l.limit_bytes > 0) {{
      totalLimit += l.limit_bytes;
    }} else {{
      hasUnlimited = true;
    }}
    if (l.expiry_date && (!expiryDate || new Date(l.expiry_date) < new Date(expiryDate))) {{
      expiryDate = l.expiry_date;
    }}
  }});

  SUB_DATA.total_used = totalUsed;
  SUB_DATA.total_limit = totalLimit;
  SUB_DATA.expiry_date = expiryDate;

  window._rvgSubUrl  = subUrl;
  window._rvgSubName = d.name;
  window._rvgLinks   = d.links.map(l => ({{
    vless : l.vless_link,
    sub   : l.sub_url + (savedPw ? '?pw=' + encodeURIComponent(savedPw) : ''),
    label : l.label,
    used_bytes: l.used_bytes || 0,
    limit_bytes: l.limit_bytes || 0,
    expiry_date: l.expiry_date || null
  }}));

  // ── نوار مصرف کل ──
  // اگر حداقل یک کانفیگ نامحدود در گروه باشد، درصد را بر اساس همان سقف محدودها نشان می‌دهیم
  // ولی برچسب "+ شامل کانفیگ نامحدود" اضافه می‌کنیم تا گمراه‌کننده نباشد.
  const tuPct = totalLimit > 0 ? Math.min(100, (totalUsed / totalLimit) * 100) : 0;
  const tuColor = tuPct > 90 ? 'var(--red)' : tuPct > 70 ? 'var(--amber)' : 'var(--green)';
  const tuLimitTxt = totalLimit > 0 ? fmtB(totalLimit) + (hasUnlimited ? ' + نامحدود' : '') : 'نامحدود';
  const totalUsageHtml = `
    <div class="total-usage-box">
      <div class="tu-head">
        <span class="tu-label"><i class="ti ti-chart-donut-2"></i> مصرف کل گروه</span>
        <span class="tu-val">${{fmtB(totalUsed)}} <span style="color:var(--t3);font-weight:600"> / ${{tuLimitTxt}}</span></span>
      </div>
      <div class="tu-bar"><div class="tu-bar-f" style="width:${{totalLimit>0?tuPct:100}}%;background:${{totalLimit>0?tuColor:'var(--accent)'}}"></div></div>
      <div class="tu-foot">
        <span>${{totalLimit>0?('<span class=\\'tu-pct\\'>'+tuPct.toFixed(1)+'%</span> مصرف‌شده'):'بدون سقف کل (شامل کانفیگ نامحدود)'}}</span>
        <span>${{toFa(d.links.length)}} کانفیگ</span>
      </div>
    </div>`;

  document.getElementById('root').innerHTML=`
    <div class="sub-info">
      <div class="sub-eyebrow"><i class="ti ti-folders"></i> گروه دسترسی</div>
      <div class="sub-name">${{esc(d.name)}}</div>
      ${{d.desc ? `<div class="sub-desc">${{esc(d.desc)}}</div>` : ''}}
      <div class="sub-meta-row"><i class="ti ti-clock"></i> آخرین بروزرسانی: ${{new Date().toLocaleTimeString('fa-IR')}}</div>
      <div class="sub-sub-box">
        <span class="sub-sub-url">${{esc(subUrl)}}</span>
        <button class="btn btn-pur" style="padding:7px 12px;font-size:10.5px"
          onclick="navigator.clipboard.writeText(window._rvgSubUrl).then(()=>toast('لینک ساب کپی شد ✓','ok'))">
          <i class="ti ti-copy"></i> کپی لینک ساب
        </button>
        <button class="btn btn-g" style="padding:7px 12px;font-size:10.5px"
          onclick="showQR(window._rvgSubName + ' — کل گروه', window._rvgSubUrl)">
          <i class="ti ti-qrcode"></i> QR کل
        </button>
      </div>
      ${{totalUsageHtml}}
    </div>

    <div class="copy-all-bar">
      <div class="copy-all-text">
        <div class="copy-all-title"><i class="ti ti-copy"></i> کپی همه‌ی کانفیگ‌ها</div>
        <div class="copy-all-sub">تمام لینک‌های فعال این گروه را یک‌جا کپی کن</div>
      </div>
      <button class="copy-all-btn" onclick="copyAllConfigs()"><i class="ti ti-clipboard-copy"></i> کپی همه (${{toFa(activeCount)}})</button>
    </div>

    <div class="stats-bar">
      <div class="stat-card">
        <div class="stat-label">کانفیگ‌های فعال</div>
        <div class="stat-val">${{toFa(activeCount)}}</div>
        <div class="stat-sub">از ${{toFa(d.links.length)}} کانفیگ</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">اتصالات زنده</div>
        <div class="stat-val">${{toFa(d.active_connections)}}</div>
        <div class="stat-sub" style="color:var(--green-t);display:flex;align-items:center;gap:4px"><span class="dot"></span> آنلاین</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">کل مصرف</div>
        <div class="stat-val" style="font-size:17px;margin-top:3px">${{totalLimit > 0 ? fmtB(totalUsed) + ' / ' + fmtB(totalLimit) : fmtB(totalUsed)}}</div>
        <div class="stat-sub">${{expiryDate ? 'انقضا: ' + new Date(expiryDate).toLocaleDateString('fa-IR') : 'نامحدود'}}</div>
      </div>
    </div>

    <div class="cfg-title"><i class="ti ti-link"></i> کانفیگ‌ها (${{toFa(d.links.length)}} عدد)</div>
    <div class="cfg-grid">
      ${{d.links.map((l, i) => {{
        const usedBytes = Number(l.used_bytes) || 0;
        const limitBytes = Number(l.limit_bytes) || 0;
        const pct = limitBytes === 0 ? 0 : Math.min(100, usedBytes / limitBytes * 100);
        const bc  = pct > 90 ? 'var(--red)' : pct > 70 ? 'var(--amber)' : 'var(--green)';
        const lim = limitBytes === 0 ? '∞' : fmtB(limitBytes);
        // اگر used_fmt از بک‌اند خالی/نامعتبر بیاد (مثلاً برای بعضی پروتکل‌ها مثل Shadowsocks)،
        // مقدار را مستقیماً از used_bytes می‌سازیم تا همیشه عدد درست نمایش داده شود.
        const usedFmt = (l.used_fmt && String(l.used_fmt).trim()) ? l.used_fmt : fmtB(usedBytes);
        const barWidth = limitBytes === 0 ? (usedBytes > 0 ? 100 : 0) : pct;
        const barColor = limitBytes === 0 ? 'var(--accent)' : bc;
        const exp = l.expiry_date ? new Date(l.expiry_date).toLocaleDateString('fa-IR') : 'نامحدود';
        return `
          <div class="cfg-card${{l.active ? '' : ' inactive'}}">
            <div class="cfg-top">
              <div class="cfg-head">
                <div>
                  <div class="cfg-label">${{esc(l.label)}}</div>
                  <div class="cfg-badges">
                    ${{protoChip(l.protocol)}}
                    ${{l.connections > 0 ? `<span class="conn-chip"><span class="dot"></span> ${{toFa(l.connections)}} اتصال</span>` : ''}}
                    ${{l.expiry_date ? `<span class="conn-chip" style="background:var(--amber-bg);color:var(--amber-t)"><i class="ti ti-calendar"></i> ${{exp}}</span>` : ''}}
                  </div>
                </div>
                <span class="cfg-status ${{l.active ? 'ok' : 'no'}}">${{l.active ? '<i class="ti ti-circle-check"></i> فعال' : '<i class="ti ti-circle-x"></i> غیرفعال'}}</span>
              </div>
              <div class="cfg-usage">
                <div class="ubar"><div class="ubar-f" style="width:${{barWidth}}%;background:${{barColor}}"></div></div>
                <div class="utxt"><span>${{esc(usedFmt)}} مصرف شده</span><span>سهمیه: ${{lim}} · انقضا: ${{exp}}</span></div>
              </div>
            </div>
            <div class="cfg-tear"></div>
            <div class="cfg-bottom">
              <button class="cfg-link-toggle" id="vt-${{i}}" onclick="toggleLink(${{i}})">
                <span class="ltl"><i class="ti ti-eye"></i> <span>نمایش لینک کانفیگ</span></span>
                <i class="ti ti-chevron-down"></i>
              </button>
              <div class="cfg-vless-wrap" id="vw-${{i}}">
                <div class="cfg-vless-inner">
                  <div class="cfg-vless">${{esc(l.vless_link)}}</div>
                </div>
              </div>
              <div class="cfg-actions">
                <button class="btn btn-p"
                  onclick="navigator.clipboard.writeText(window._rvgLinks[${{i}}].vless).then(()=>toast('لینک کپی شد ✓','ok'))">
                  <i class="ti ti-copy"></i> کپی لینک
                </button>
                <button class="btn btn-g"
                  onclick="showQR(window._rvgLinks[${{i}}].label, window._rvgLinks[${{i}}].vless)">
                  <i class="ti ti-qrcode"></i> QR
                </button>
              </div>
            </div>
          </div>
        `;
      }}).join('')}}
    </div>
  `;

  updateSubscriptionHeaders(totalUsed, totalLimit, expiryDate);

  setTimeout(() => autoRefresh(), 30000);
}}

function updateSubscriptionHeaders(used, limit, expiry) {{
  try {{
    localStorage.setItem('rvg_sub_used', String(used));
    localStorage.setItem('rvg_sub_limit', String(limit));
    if (expiry) {{
      localStorage.setItem('rvg_sub_expiry', expiry);
    }}
  }} catch(e) {{}}
}}

function copyAllConfigs(){{
  const links=window._rvgLinks||[];
  if(!links.length){{toast('کانفیگی برای کپی نیست','');return}}
  const text=links.map(l=>l.vless).join('\\n');
  navigator.clipboard.writeText(text).then(()=>toast('همه‌ی '+toFa(links.length)+' کانفیگ کپی شد ✓','ok'));
}}

async function autoRefresh(){{
  try{{
    const data = await loadData(savedPw);
    if (!data.locked) renderContent(data);
  }} catch(e) {{}}
}}

function getSubscriptionInfo() {{
  return {{
    used: parseInt(localStorage.getItem('rvg_sub_used') || '0'),
    limit: parseInt(localStorage.getItem('rvg_sub_limit') || '0'),
    expiry: localStorage.getItem('rvg_sub_expiry') || null
  }};
}}

async function init(){{
  try{{
    const data = await loadData();
    if (data.locked) {{ renderLock(data.name); return; }}
    renderContent(data);
  }} catch(e) {{
    document.getElementById('root').innerHTML =
      '<div class="empty-state" style="color:var(--red-t)"><i class="ti ti-alert-circle"></i>خطا در بارگذاری</div>';
  }}
}}

window.getSubData = function() {{
  return SUB_DATA;
}};

init();
</script>
</body></html>"""

// ═══════════════════════════════════════════════════════════════════
// EMIX Exit Node — سرور خروج رایگان VLESS-over-WebSocket
// ═══════════════════════════════════════════════════════════════════
// این سرور کوچک روی هر پلتفرم رایگان (Railway / Koyeb / Render / Fly)
// deploy می‌شود و دامنه‌اش در پنل EMIX به‌عنوان «لوکیشن خروج» ثبت می‌شود:
//
//   کاربر ──► Cloudflare Worker (گیت‌وی) ──► این سرور ──► اینترنت
//
// تنظیم: متغیر محیطی UUID را با UUID یکی از کانفیگ‌های پنل ست کنید
// (پنل EMIX → تب گیمینگ → «بسته‌ی سرور خروج رایگان» دقیقاً همین فایل را
//  با UUID شما پخت می‌دهد — این نسخه‌ی عمومی مخزن است)
//
// راهنمای کامل: README.md همین پوشه
// ═══════════════════════════════════════════════════════════════════
const http = require('http');
const net = require('net');
const { WebSocketServer } = require('ws');

// UUID از متغیر محیطی — حتماً ست شود
const UUID = (process.env.UUID || '').toLowerCase();
const UUID_HEX = UUID.replace(/-/g, '');
const PORT = parseInt(process.env.PORT || '8080', 10);
const IDLE_MS = parseInt(process.env.IDLE_TIMEOUT_MS || '300000', 10);

if (!/^[0-9a-f]{32}$/.test(UUID_HEX)) {
  console.error('[emix-exit] خطا: متغیر محیطی UUID ست نشده یا نامعتبر است.');
  console.error('[emix-exit] آن را با UUID کانفیگ پنل EMIX ست کنید (Settings → Variables → UUID)');
  process.exit(1);
}

let active = 0;
const server = http.createServer((req, res) => {
  // سلامت‌سنجی: وورکر و پنل این مسیرها را صدا می‌زنند
  if (req.url === '/api/ping' || req.url === '/health' || req.url === '/') {
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ ok: true, node: 'emix-exit', proto: 'vless-ws', active, ts: Date.now() }));
    return;
  }
  res.writeHead(404, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ ok: false }));
});

// پذیرش WS روی هر مسیری — احراز هویت داخل هدر VLESS انجام می‌شود
const wss = new WebSocketServer({ server, maxPayload: 8 * 1024 * 1024 });

wss.on('connection', (ws) => {
  ws.once('message', (first) => {
    try {
      const buf = Buffer.isBuffer(first) ? first : Buffer.from(first);
      if (buf.length < 24 || buf[0] !== 0x00) return ws.close();
      const uuidHex = buf.subarray(1, 17).toString('hex');
      if (uuidHex !== UUID_HEX) return ws.close();   // UUID غلط → قطع فوری
      let pos = 17;
      pos += 1 + buf[pos];                            // addons
      const cmd = buf[pos]; pos += 1;
      if (cmd !== 0x01) return ws.close();            // فقط TCP (مثل بک‌اند اصلی EMIX)
      const port = buf.readUInt16BE(pos); pos += 2;
      const atyp = buf[pos]; pos += 1;
      let addr = '';
      if (atyp === 1) {
        addr = `${buf[pos]}.${buf[pos + 1]}.${buf[pos + 2]}.${buf[pos + 3]}`; pos += 4;
      } else if (atyp === 2) {
        const dl = buf[pos]; pos += 1;
        addr = buf.subarray(pos, pos + dl).toString('utf-8'); pos += dl;
      } else if (atyp === 3) {
        const parts = [];
        for (let i = 0; i < 16; i += 2) parts.push(buf.subarray(pos + i, pos + i + 2).toString('hex'));
        addr = parts.join(':'); pos += 16;
      } else {
        return ws.close();
      }
      const payload = buf.subarray(pos);

      active++;
      const remote = net.connect({ host: addr, port }, () => {
        try { ws.send(Buffer.from([0x00, 0x00])); } catch (e) { /* بسته شد */ }
        if (payload.length) remote.write(payload);
      });
      let closed = false;
      const finish = () => { if (!closed) { closed = true; active--; try { remote.destroy(); } catch (e) {} try { ws.close(); } catch (e) {} } };
      ws.on('message', (m) => {
        const d = Buffer.isBuffer(m) ? m : Buffer.from(m);
        if (d.length && !remote.destroyed) remote.write(d);
      });
      remote.on('data', (d) => { try { ws.send(d); } catch (e) { finish(); } });
      remote.on('error', finish);
      remote.on('close', finish);
      ws.on('close', finish);
      ws.on('error', finish);
      remote.setTimeout(IDLE_MS, () => { remote.destroy(); });
    } catch (e) {
      try { ws.close(); } catch (e2) { /* noop */ }
    }
  });
});

server.listen(PORT, () => console.log('[emix-exit] listening on :' + PORT + ' — UUID: ' + UUID.slice(0, 8) + '...'));

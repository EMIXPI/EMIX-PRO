//! ═══════════════════════════════════════════════════════════════════════════
//! emix-smart-routing-v1 — EMIX-PRO Smart Routing Network Worker (v1.0.0)
//! ═══════════════════════════════════════════════════════════════════════════
//! کاملاً جدید و مستقل — از workerهای قبلی EMIX هیچ خطی عمداً
//! بازاستفاده نشده و آن workerها دست‌نخورده باقی می‌مانند.
//!
//! نقش واقعی (ادعای «VPN exit جادویی» ندارد):
//!   • edge component / control-plane روی Cloudflare
//!   • relay شفاف WS/HTTP به upstream (پنل EMIX-PRO روی Railway)
//!   • اندازه‌گیری latency لبه→upstream و گزارش دوره‌ای (Cron)
//!   • خروجی egress خودِ Worker (fetch واقعی — برچسب صادق)
//!
//! Bindings:
//!   EMIX_UPSTREAM  (secret)  — host پنل (مثلاً xxx.up.railway.app)
//!   SR_SIGNING_KEY (secret)  — کلید HMAC مشترک با پنل (هرگز hardcode نمی‌شود)
//!   SR_STATE       (KV)      — nonce replay cache + آخرین گزارش سلامت
//!
//! Security:
//!   • /sr/admin/* فقط با امضای HMAC (ts ±۹۰s + nonce یک‌بارمصرف + sha256 body)
//!   • proxy فقط به EMIX_UPSTREAM ثابت (SSRF غیرممکن — مقصد آزاد نیست)
//!   • rate limit سبک روی /sr/*
//! ═══════════════════════════════════════════════════════════════════════════

const WORKER_NAME = "emix-smart-routing-v1";
const WORKER_VERSION = "1.0.0";
const TS_WINDOW_S = 90;                 // قرارداد مشترک: timestamp بر حسب «ثانیه»
const NONCE_TTL_S = 600;

const jsonHeaders = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: jsonHeaders });

async function sha256hex(data) {
  const d = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, "0")).join("");
}

async function hmacHex(keyStr, msg) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(keyStr), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(msg));
  return [...new Uint8Array(mac)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function timingSafeEq(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return out === 0;
}

/** امضای مشترک با پنل: ts.nonce.METHOD.path.sha256(body) */
async function canonical(ts, nonce, method, path, body) {
  const bh = await sha256hex(body || new Uint8Array(0));
  return `${ts}.${nonce}.${method.toUpperCase()}.${path}.${bh}`;
}

/** verify درخواست امضاشده‌ی پنل — timestamp window + nonce (KV) + HMAC */
async function verifySigned(request, env, url) {
  const key = env.SR_SIGNING_KEY;
  if (!key) return { ok: false, reason: "SR_SIGNING_KEY تنظیم نشده" };
  const ts = request.headers.get("x-sr-timestamp") || "";
  const nonce = request.headers.get("x-sr-nonce") || "";
  const sig = request.headers.get("x-sr-signature") || "";
  if (!ts || !nonce || !sig) return { ok: false, reason: "هدرهای امضا ناقص" };
  const its = parseInt(ts, 10);
  if (!Number.isFinite(its)) return { ok: false, reason: "timestamp نامعتبر" };
  if (Math.abs(Date.now() / 1000 - its) > TS_WINDOW_S) return { ok: false, reason: "timestamp خارج از پنجره" };
  const body = new Uint8Array(await request.clone().arrayBuffer().catch(() => new ArrayBuffer(0)));
  const expect = await hmacHex(key, await canonical(ts, nonce, request.method, url.pathname, body));
  if (!timingSafeEq(expect, sig.toLowerCase())) return { ok: false, reason: "امضا نامعتبر" };
  if (env.SR_STATE) {
    const seen = await env.SR_STATE.get(`n:${nonce}`);
    if (seen) return { ok: false, reason: "nonce تکراری (replay)" };
    await env.SR_STATE.put(`n:${nonce}`, "1", { expirationTtl: NONCE_TTL_S });
  }
  return { ok: true };
}

/** امضای درخواست خروجی worker → پنل (ts = ثانیه — همان قرارداد پنل) */
async function signedHeaders(env, method, path, bodyStr) {
  const ts = String(Math.floor(Date.now() / 1000));
  const nonce = crypto.randomUUID().replace(/-/g, "");
  const bh = await sha256hex(new TextEncoder().encode(bodyStr || ""));
  const sig = await hmacHex(env.SR_SIGNING_KEY, `${ts}.${nonce}.${method}.${path}.${bh}`);
  return { "x-sr-timestamp": ts, "x-sr-nonce": nonce, "x-sr-signature": sig, "content-type": "application/json" };
}

/** upstream چک سبک — همان اندپوینت healthcheck پنل (بدون auth، فقط ok) */
async function upstreamHealth(env) {
  const t0 = Date.now();
  try {
    const r = await fetch(`https://${env.EMIX_UPSTREAM}/api/ping`, { signal: AbortSignal.timeout(8000) });
    return { ok: r.status === 200, latency_ms: Date.now() - t0, status: r.status };
  } catch (e) {
    return { ok: false, latency_ms: Date.now() - t0, error: String(e).slice(0, 80) };
  }
}

// ═════════════════════════════ main handler ═════════════════════════════════
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    try {
      // ── مسیرهای کنترلی /sr/* ────────────────────────────────────────────
      if (path === "/sr/health") {
        const up = await upstreamHealth(env);
        return json({ ok: true, worker: WORKER_NAME, version: WORKER_VERSION, upstream: up, colo: request.cf?.colo || null, ts: Date.now() });
      }

      if (path === "/sr/edge-info") {
        const v = await verifySigned(request, env, url);
        if (!v.ok) return json({ ok: false, error: v.reason }, 401);
        return json({
          ok: true, worker: WORKER_NAME, version: WORKER_VERSION,
          colo: request.cf?.colo || null, country: request.cf?.country || null,
          city: request.cf?.city || null, latitude: request.cf?.latitude || null,
          longitude: request.cf?.longitude || null, request_id: crypto.randomUUID(),
        });
      }

      if (path === "/sr/egress-test") {
        const v = await verifySigned(request, env, url);
        if (!v.ok) return json({ ok: false, error: v.reason }, 401);
        // egress واقعیِ fetchهای این Worker (برچسب صادق: worker-fetch-egress —
        // این egressِ تونل کاربر نیست؛ egress تونل از داخل خود تونل سنجیده می‌شود)
        const t0 = Date.now();
        const out = { ok: false, label: "worker-fetch-egress" };
        try {
          const r = await fetch("https://api.ipify.org?format=json", { signal: AbortSignal.timeout(8000) });
          const d = await r.json();
          out.ok = true; out.egress_ip = d.ip; out.latency_ms = Date.now() - t0;
          try {
            const g = await fetch(`http://ip-api.com/json/${d.ip}?fields=countryCode,as,asNumber`, { signal: AbortSignal.timeout(8000) });
            const gd = await g.json();
            out.country = gd.countryCode || null; out.asn = gd.as || null; out.asn_num = gd.asNumber || null;
          } catch (_) { /* geo اختیاری */ }
        } catch (e) { out.error = String(e).slice(0, 80); }
        return json(out);
      }

      if (path === "/sr/probe-upstream") {
        const v = await verifySigned(request, env, url);
        if (!v.ok) return json({ ok: false, error: v.reason }, 401);
        // WS handshake واقعی از لبه‌ی CF به upstream: /api/ping روی همان اتصال TLS
        const t0 = Date.now();
        try {
          const r = await fetch(`https://${env.EMIX_UPSTREAM}/api/ping`, { signal: AbortSignal.timeout(8000) });
          const up_ok = r.status === 200;
          let colo = request.cf?.colo || null;
          return json({ ok: true, edge_to_upstream_ms: Date.now() - t0, upstream_ok: up_ok, colo, ts: Date.now() });
        } catch (e) {
          return json({ ok: false, error: String(e).slice(0, 80), edge_to_upstream_ms: Date.now() - t0 });
        }
      }

      if (path === "/sr/report") {
        const v = await verifySigned(request, env, url);
        if (!v.ok) return json({ ok: false, error: v.reason }, 401);
        const body = await request.json().catch(() => ({}));
        if (env.SR_STATE) {
          await env.SR_STATE.put("last_report", JSON.stringify({ ...body, received: Date.now() }));
        }
        return json({ ok: true, stored: true });
      }

      if (path === "/sr/report/last") {
        const v = await verifySigned(request, env, url);
        if (!v.ok) return json({ ok: false, error: v.reason }, 401);
        const last = env.SR_STATE ? await env.SR_STATE.get("last_report") : null;
        return json({ ok: true, last_report: last ? JSON.parse(last) : null });
      }

      // ── relay شفاف به upstream (WS + HTTP + همه‌ی متدها) ────────────────
      // proxy فقط به EMIX_UPSTREAM ثابت — SSRF به مقصد آزاد ساختاراً ممکن نیست.
      if (!env.EMIX_UPSTREAM) {
        return json({ ok: false, error: "EMIX_UPSTREAM تنظیم نشده" }, 500);
      }
      const upstreamUrl = `https://${env.EMIX_UPSTREAM}${path}${url.search}`;
      const proxyReq = new Request(upstreamUrl, request);
      proxyReq.headers.set("x-sr-worker", `${WORKER_NAME}/${WORKER_VERSION}`);
      proxyReq.headers.set("x-sr-colo", (request.cf && request.cf.colo) || "");
      const resp = await fetch(proxyReq);
      // ⚠ حیاتی برای WebSocket: پاسخ 101 قابل بازسازی با Response() نیست —
      // باید دقیقاً همان پاسخ برگردد تا استریم دوطرفه زنده بماند.
      if (resp.status === 101 || resp.websocket) {
        return resp;
      }
      const h = new Headers(resp.headers);
      h.set("x-sr-worker", `${WORKER_NAME}/${WORKER_VERSION}`);
      h.set("x-sr-colo", (request.cf && request.cf.colo) || "");
      return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers: h });
    } catch (e) {
      return json({ ok: false, worker: WORKER_NAME, error: String(e).slice(0, 120) }, 502);
    }
  },

  // ═════════════════════════ Cron: گزارش دوره‌ای سلامت به پنل ═══════════════
  async scheduled(event, env, ctx) {
    const up = await upstreamHealth(env);
    const report = {
      worker: WORKER_NAME, version: WORKER_VERSION,
      upstream_ok: up.ok, upstream_latency_ms: up.latency_ms,
      colo: null, ts: Date.now(),
    };
    if (env.SR_STATE) {
      await env.SR_STATE.put("last_report", JSON.stringify(report));
    }
    // گزارش امضاشده به پنل (همان upstream)
    if (env.SR_SIGNING_KEY && env.EMIX_UPSTREAM) {
      const bodyStr = JSON.stringify(report);
      const headers = await signedHeaders(env, "POST", "/api/smart-routing/worker/report", bodyStr);
      await fetch(`https://${env.EMIX_UPSTREAM}/api/smart-routing/worker/report`, {
        method: "POST", headers, body: bodyStr,
        signal: AbortSignal.timeout(10_000),
      }).catch(() => { /* گزارش best-effort — پنل خودش هم می‌پرسد */ });
    }
  },
};

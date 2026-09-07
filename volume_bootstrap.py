# volume_bootstrap.py — Volume ریلوی: تشخیص خودکار + پیوست خودکار (v13.6.0)
# ══════════════════════════════════════════════════════════════════════════════
# ریشه‌ی شکایت مالک: «Volume بعد از دیپلوی اتومات attach نمی‌شود و نیاز به
# کار دستی دارد». این ماژول همان کار دستی را در boot انجام می‌دهد:
#
#   ۱) تشخیص صادق: آیا DATA_DIR روی mount پایدار است؟ (/proc/self/mountinfo)
#   ۲) اگر روی Railway هستیم و Volume متصل نیست و توکن موجود است:
#        - اگر پروژه هیچ Volumeی ندارد → volumeCreate (GraphQL رسمی ریلوی،
#          همان مسیر اثبات‌شده‌ی فاز ۴۴) با mountPath=DATA_DIR → سپس با تغییر
#          یک متغیر کوچک redeploy خودکار ریلوی را نudge می‌کنیم → بوت بعدی
#          با Volume پایدار بالا می‌آید (خودکار، بدون قدم دستی).
#        - اگر پروژه Volume دارد ولی روی این سرویس mount نیست → هیچ action
#          مخربی نمی‌کنیم؛ فقط راهنمای صادق (ضد ایجاد Volume تکراری و ضد
#          حلقه‌ی بی‌نهایت redeploy).
#   ۳) نتیجه در smart_settings (volume_bootstrap) + route_events ثبت می‌شود
#      تا UI/Health بتوانند وضعیت پایداری را صادقانه نشان دهند.
#
# 🔒 ایمنی حلقه (loop-safety — عمدی و مستند):
#   - mount موجود → هیچ کاری نکن (deployهای عادی پروداکشن همین‌اند).
#   - خارج از Railway → هیچ کاری نکن (توسعه‌ی لوکال).
#   - Volume موجود در پروژه → create/redeploy ممنوع (فقط راهنما).
#   - create ناموفق → redeploy نکن (یعنی تا وقتی create موفق نشده redeploy
#     بی‌نهایت رخ نمی‌دهد).
#   - opt-out اپراتور: AUTO_VOLUME_ATTACH=false
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import logging
import os
import time
from pathlib import Path

import httpx

logger = logging.getLogger("EMIX")

GRAPHQL_URL = "https://backboard.railway.app/graphql/v2"
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
REDEPLOY_NUDGE_VAR = "EMIX_VOLUME_BOOTSTRAP"      # متغیری که فقط برای nudge عوض می‌شود

# شکل‌های رسمی GraphQL (docs.railway.com/integrations/api/manage-volumes —
# همانهایی که در مستندات عمومی ریلوی مستند شده‌اند):
_Q_PROJECT_VOLUMES = """
query project($id: String!) {
  project(id: $id) {
    volumes {
      edges { node { id name createdAt } }
    }
  }
}
"""
_M_VOLUME_CREATE = """
mutation volumeCreate($input: VolumeCreateInput!) {
  volumeCreate(input: $input) { id name }
}
"""
_M_VARIABLE_UPSERT = """
mutation VariableUpsert($input: VariableUpsertInput!) {
  variableUpsert(input: $input)
}
"""


# ── تشخیص mount (/proc/self/mountinfo) ───────────────────────────────────────
def _unescape_mount(s: str) -> str:
    """octal escapes مثل \\040 (space) در mountinfo."""
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\":
            chunk = s[i + 1:i + 4]
            if len(chunk) == 3 and all(c in "01234567" for c in chunk):
                try:
                    out.append(chr(int(chunk, 8)))
                    i += 4
                    continue
                except ValueError:
                    pass
        out.append(s[i])
        i += 1
    return "".join(out)


def _mount_entries() -> list[dict]:
    try:
        with open("/proc/self/mountinfo", encoding="utf-8", errors="ignore") as f:
            entries = []
            for line in f:
                parts = line.split()
                if len(parts) < 7:
                    continue
                try:
                    sep = parts.index("-")
                except ValueError:
                    continue
                if len(parts) < sep + 3:
                    continue
                entries.append({
                    "mount_point": _unescape_mount(parts[4]),
                    "fstype": parts[sep + 1],
                    "source": parts[sep + 2],
                })
            return entries
    except Exception:
        return []


def mount_entry(path) -> dict | None:
    """اگر «دقیقاً همین مسیر» یک mount باشد، ورودی‌اش را برگردان (نه ancestor)."""
    p = str(Path(path).absolute()).rstrip("/")
    for e in _mount_entries():
        if e["mount_point"].rstrip("/") == p:
            return e
    return None


def is_mount(path) -> bool:
    """آیا مسیر داده روی یک mount واقعی (Volume) نشسته؟

    ریشه‌ی filesystem کانتینر («/» با fstype=overlay) عمداً mount حساب
    نمی‌شود — فقط mount دقیقِ خودِ مسیر (مثل /data با ext4) معتبر است."""
    return mount_entry(path) is not None


def on_railway() -> bool:
    return bool(os.environ.get("RAILWAY_SERVICE_ID", "").strip())


def auto_attach_enabled() -> bool:
    return os.environ.get("AUTO_VOLUME_ATTACH", "true").strip().lower() not in (
        "0", "false", "no", "off")


def _ids() -> dict:
    return {
        "service_id": os.environ.get("RAILWAY_SERVICE_ID", "").strip(),
        "environment_id": os.environ.get("RAILWAY_ENVIRONMENT_ID", "").strip(),
        "project_id": os.environ.get("RAILWAY_PROJECT_ID", "").strip(),
    }


def _token() -> str:
    """توکن Railway — env RAILWAY_TOKEN مقدم است؛ بعد فایل ذخیره‌شده‌ی پنل."""
    t = (os.environ.get("RAILWAY_TOKEN") or "").strip()
    if t:
        return t
    try:
        import bottokentcpproxy
        return bottokentcpproxy.load_token() or ""
    except Exception:
        return ""


def _record(payload: dict) -> None:
    """ثبت نتیجه در smart_settings + event (برای UI/Health) — fail-safe."""
    try:
        from smart_routing import db as sr_db
        sr_db.set_setting("volume_bootstrap", payload)
        if payload.get("action"):
            sr_db.add_event("engine", "Volume bootstrap: " + str(payload.get("action"))[:160])
    except Exception:
        pass


def status() -> dict:
    """snapshot صادقِ وضعیت پایداری — بدون هیچ side-effect."""
    me = mount_entry(DATA_DIR)
    ids = _ids()
    return {
        "ok": True,
        "data_dir": str(DATA_DIR),
        "mounted": me is not None,
        "persistent": me is not None,
        "mount": {"fstype": me["fstype"], "source": me["source"]} if me else None,
        "on_railway": on_railway(),
        "auto_attach_enabled": auto_attach_enabled(),
        "has_token": bool(_token()),
        "ids_present": all(ids.values()),
        "at_risk": on_railway() and me is None,
        "ts": time.time(),
    }


# ── GraphQL helpers (honest — خطاها سبز جعلی نمی‌شوند) ───────────────────────
async def _gql(token: str, query: str, variables: dict) -> tuple[bool, dict | list | None, str]:
    try:
        async with httpx.AsyncClient(timeout=25.0) as cli:
            r = await cli.post(GRAPHQL_URL, json={"query": query, "variables": variables},
                               headers={"Authorization": f"Bearer {token}",
                                        "Content-Type": "application/json"})
        if r.status_code == 401:
            return False, None, "توکن Railway نامعتبر است (401)"
        data = r.json()
        if data.get("errors"):
            msgs = "; ".join(e.get("message", "") for e in data["errors"])
            return False, None, f"GraphQL: {msgs[:180]}"
        return True, data.get("data"), ""
    except Exception as e:
        return False, None, f"{type(e).__name__}: {str(e)[:120]}"


async def _project_volume_count(token: str, project_id: str) -> tuple[int | None, str]:
    ok, data, err = await _gql(token, _Q_PROJECT_VOLUMES, {"id": project_id})
    if not ok:
        return None, err
    try:
        edges = (((data or {}).get("project") or {}).get("volumes") or {}).get("edges") or []
        return len(edges), ""
    except Exception as e:
        return None, f"parse: {e}"


async def _create_volume(token: str, ids: dict) -> tuple[bool, dict, str]:
    variables = {"input": {
        "projectId": ids["project_id"],
        "serviceId": ids["service_id"],
        "mountPath": str(DATA_DIR),
    }}
    if ids.get("environment_id"):
        variables["input"]["environmentId"] = ids["environment_id"]
    ok, data, err = await _gql(token, _M_VOLUME_CREATE, variables)
    if not ok:
        return False, {}, err
    return True, (data or {}).get("volumeCreate") or {}, ""


async def _nudge_redeploy(token: str, ids: dict) -> tuple[bool, str]:
    """تغییر مقدار یک متغیر بی‌اثر → Railway خودش redeploy می‌کند (مسیر فاز ۴۴)."""
    variables = {"input": {
        "environmentId": ids["environment_id"],
        "projectId": ids["project_id"],
        "serviceId": ids["service_id"],
        "name": REDEPLOY_NUDGE_VAR,
        "value": f"boot-{int(time.time())}",
    }}
    ok, data, err = await _gql(token, _M_VARIABLE_UPSERT, variables)
    if not ok:
        return False, err
    return bool(data), ""


# ── ارکستراتور boot ──────────────────────────────────────────────────────────
async def ensure_volume() -> dict:
    """در هر boot صدا زده می‌شود — فقط در صورت لزوم Volume می‌سازد/وصل می‌کند.

    هیچ‌وقت crash نمی‌کند و هیچ‌وقت boot را بلاک نمی‌کند (فراخوانی به‌صورت
    background task از startup main.py)."""
    me = mount_entry(DATA_DIR)
    if me is not None:
        _record({**status(), "action": "mount موجود — هیچ کاری لازم نیست"})
        return {"ok": True, "action": "already-mounted"}

    if not on_railway():
        _record({**status(), "action": "خارج از Railway — storage لوکال"})
        return {"ok": True, "action": "not-railway"}

    if not auto_attach_enabled():
        _record({**status(), "action": "AUTO_VOLUME_ATTACH خاموش — skip شد (اپراتور)"})
        return {"ok": True, "action": "disabled-by-env"}

    ids = _ids()
    token = _token()
    base = status()
    if not token or not all(ids.values()):
        # راهنمای صادق — نه خطا، نه عمل
        _record({**base, "action": "توکن/شناسه‌های Railway موجود نیست — Volume دستی "
                                   "attach کنید یا RAILWAY_TOKEN را به‌عنوان متغیر ست کنید "
                                   "(با هر دیپلوی/ری‌دیپلوی خودکار اعمال می‌شود)"})
        logger.warning(
            "⚠ Volume پایدار نیست و bootstrap خودکار ممکن نیست (توکن/شناسه‌ها "
            "نبودند). داده‌ها بین دیپلوی‌ها می‌مانند فقط اگر Volume روی %s "
            "attach شود. راه سریع: متغیر RAILWAY_TOKEN را در سرویس ست کنید.",
            str(DATA_DIR),
        )
        return {"ok": False, "action": "missing-token-or-ids"}

    count, err = await _project_volume_count(token, ids["project_id"])
    if count is None:
        _record({**base, "action": f"بررسی Volumeهای پروژه ناموفق: {err}"})
        return {"ok": False, "action": "query-failed", "error": err}
    if count and count > 0:
        # ⛔ عمداً create نمی‌کنیم: Volume در پروژه هست ولی روی این سرویس mount
        # نیست — احتمالاً به سرویس دیگری وصل است؛ create تکراری/خطرناک است.
        _record({**base, "action": f"پروژه {count} Volume دارد اما DATA_DIR mount نیست — "
                                   "در dashboard همین Volume را به این سرویس "
                                   f"(mountPath={DATA_DIR}) attach و redeploy کنید"})
        return {"ok": False, "action": "volume-exists-not-mounted", "volumes": count}

    ok, created, err = await _create_volume(token, ids)
    if not ok:
        _record({**base, "action": f"ساخت Volume ناموفق: {err}"})
        return {"ok": False, "action": "create-failed", "error": err}

    # create موفق → nudge یک redeploy تا Volume mount شود (فقط همین‌جا؛
    # بوت بعدی mount را می‌بیند و دیگر هیچ redeployای رخ نمی‌دهد).
    nudge_ok, nudge_err = await _nudge_redeploy(token, ids)
    action = (f"Volume «{(created or {}).get('name') or 'data'}» ساخته و به سرویس وصل شد "
              f"(mountPath={DATA_DIR})" + (" — redeploy خودکار در راه است (~۱-۲ دقیقه)"
                                           if nudge_ok else
                                           f" — redeploy نudge ناموفق: {nudge_err} (دستی redeploy کنید)"))
    _record({**base, "action": action, "created": created})
    logger.info("✅ %s", action)
    return {"ok": True, "action": "created", "created": created,
            "redeploy_nudged": nudge_ok}


def register_routes(app) -> None:
    """GET /api/persistence/status — وضعیت پایداری داده (احراز هویت پنل)."""
    from fastapi import Depends
    from fastapi.responses import JSONResponse
    from main import require_auth

    @app.get("/api/persistence/status")
    async def persistence_status(_=Depends(require_auth)):
        out = status()
        try:
            from smart_routing import db as sr_db
            out["bootstrap"] = sr_db.get_setting("volume_bootstrap") or None
        except Exception:
            out["bootstrap"] = None
        return JSONResponse(out, headers={"Cache-Control": "no-store"})


async def _selftest() -> None:
    print(json_pretty(status()))


def json_pretty(d: dict) -> str:
    import json
    return json.dumps(d, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(_selftest())

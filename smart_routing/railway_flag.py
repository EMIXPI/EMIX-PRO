# smart_routing/railway_flag.py — فعال‌سازی feature flag روی Railway (اپراتور، یک‌بار)
# ══════════════════════════════════════════════════════════════════════════════
# سند: «بعد از تست: true فعال شود». این ماژول فقط برای همین یک کار است:
#   SMART_ROUTING_ENABLED=true را به‌عنوان متغیر سرویس Railway ست می‌کند
#   (با توکن ذخیره‌شده‌ی اپراتور — همان مسیر اثبات‌شده‌ی فاز ۴۴؛ هیچ
#   secretی hardcode نمی‌شود). Railway بعد از تغییر متغیر خودش redeploy می‌کند.
# rollback = مقدار false (همان endpoint با enable=false).
# ══════════════════════════════════════════════════════════════════════════════

import os

import httpx

GRAPHQL_URL = "https://backboard.railway.app/graphql/v2"

# شکل ۱ — همان که Phase 44 با introspection واقعی ریلوی تأیید و در پروداکشن
# اجرا کرد: variableUpsert(input: VariableUpsertInput!): Boolean
#   VariableUpsertInput: environmentId!, name!, projectId!, serviceId?, value!
_MUTATION = """
mutation VariableUpsert($input: VariableUpsertInput!) {
  variableUpsert(input: $input)
}
"""


def _ids() -> dict:
    return {
        "service_id": os.environ.get("RAILWAY_SERVICE_ID", ""),
        "environment_id": os.environ.get("RAILWAY_ENVIRONMENT_ID", ""),
        "project_id": os.environ.get("RAILWAY_PROJECT_ID", ""),
    }


def _token() -> str:
    try:
        import bottokentcpproxy
        t = bottokentcpproxy.load_token()
        return t or ""
    except Exception:
        return ""


async def set_env_flag(enable: bool) -> dict:
    """SMART_ROUTING_ENABLED را روی Railway ست می‌کند (redeploy خودکار).

    خروجی صادق است: اگر توکن/شناسه‌ها نبودند یا GraphQL خطا داد، دستور
    دقیقِ دستی اپراتور برگردانده می‌شود — نه سبز جعلی."""
    token = _token()
    ids = _ids()
    missing = [k for k, v in ids.items() if not v]
    if not token:
        return {"ok": False,
                "manual": "در Railway dashboard متغیر SMART_ROUTING_ENABLED=true را ست کنید (توکن ذخیره‌شده پیدا نشد)"}
    if missing:
        return {"ok": False,
                "manual": f"متغیرهای {missing} در runtime نیستند — دستی در dashboard ست کنید"}
    value = "true" if enable else "false"
    variables = {"input": {
        "environmentId": ids["environment_id"],
        "projectId": ids["project_id"],
        "serviceId": ids["service_id"],
        "name": "SMART_ROUTING_ENABLED",
        "value": value,
    }}
    try:
        async with httpx.AsyncClient(timeout=25.0) as cli:
            r = await cli.post(GRAPHQL_URL, json={"query": _MUTATION, "variables": variables},
                               headers={"Authorization": f"Bearer {token}",
                                        "Content-Type": "application/json"})
        if r.status_code == 401:
            return {"ok": False, "manual": "توکن Railway نامعتبر است — دستی در dashboard ست کنید"}
        data = r.json()
        if data.get("errors"):
            msgs = "; ".join(e.get("message", "") for e in data["errors"])
            return {"ok": False, "error": f"GraphQL: {msgs}",
                    "manual": "در Railway dashboard متغیر SMART_ROUTING_ENABLED=" + value + " را ست کنید"}
        ok = bool(data.get("data", {}).get("variableUpsert"))
        return {"ok": ok, "value": value,
                "note": "Railway بعد از تغییر متغیر خودش redeploy می‌کند (~۱-۲ دقیقه)" if ok else ""}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}",
                "manual": "در Railway dashboard متغیر SMART_ROUTING_ENABLED=" + value + " را ست کنید"}


def has_railway_token() -> bool:
    return bool(_token())

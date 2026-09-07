# smart_routing/scoring.py — Route Scoring Engine (امتیاز ترکیبی + penalties)
# ══════════════════════════════════════════════════════════════════════════════
# امتیاز فقط بر اساس ping نیست (سند §SMART ROUTE SCORING):
#   score = 100 × Σ (وزن × زیر-امتیاز)
#   LATENCY 30% · JITTER 15% · PACKET LOSS 20% · UPTIME 15% ·
#   AVAILABILITY 10% · EGRESS 10%      (وزن‌ها configurable)
#   penalties: jitter بالا، loss، instability (واریانس)، verify ناموفق
#   → verify ناموفق = score صفر + INVALID (هرگز active نمی‌شود)
# ══════════════════════════════════════════════════════════════════════════════

from . import db

DEFAULT_WEIGHTS = {"latency": 0.30, "jitter": 0.15, "packet_loss": 0.20,
                   "uptime": 0.15, "availability": 0.10, "egress": 0.10}

# حالت‌های انتخاب (سند §CONFIG BUILDER INTEGRATION)
MODES = ("OFF", "AUTO", "LOW_LATENCY", "STABLE", "IRAN_OPTIMIZED")

MODE_WEIGHTS = {
    "AUTO": DEFAULT_WEIGHTS,
    "LOW_LATENCY": {"latency": 0.55, "jitter": 0.15, "packet_loss": 0.20,
                    "uptime": 0.05, "availability": 0.05, "egress": 0.00},
    "STABLE": {"latency": 0.10, "jitter": 0.15, "packet_loss": 0.35,
               "uptime": 0.25, "availability": 0.10, "egress": 0.05},
    "IRAN_OPTIMIZED": DEFAULT_WEIGHTS,   # + اولویت قابلیت IRAN_EGRESS در selector
}


def _clamp01(x) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


def _latency_score(ms) -> float:
    """۱ در ≤۵۰ms، ۰ در ≥۸۰۰ms — خطی بین (کم = بهتر)."""
    if ms is None:
        return 0.0
    if ms <= 50:
        return 1.0
    if ms >= 800:
        return 0.0
    return 1.0 - (ms - 50) / 750.0


def _jitter_score(ms) -> float:
    """۱ در ≤۱۰ms، ۰ در ≥۱۵۰ms."""
    if ms is None:
        return 0.0
    if ms <= 10:
        return 1.0
    if ms >= 150:
        return 0.0
    return 1.0 - (ms - 10) / 140.0


def _loss_score(loss) -> float:
    """۱ در ۰٪، ۰ در ≥۲۰٪."""
    if loss is None:
        return 0.0
    if loss <= 0:
        return 1.0
    if loss >= 0.20:
        return 0.0
    return 1.0 - loss / 0.20


def _uptime_score(pct) -> float:
    """۹۹٪↑ → ۱؛ ۸۰٪↓ → ۰."""
    if pct is None:
        return 0.0
    if pct >= 99:
        return 1.0
    if pct <= 80:
        return 0.0
    return (pct - 80) / 19.0


def _availability_score(ep: dict) -> float:
    """نسبت ok در تاریخچه‌ی اخیر (پایداری، نه آخرین چک)."""
    history = ep.get("history") or []
    if not history:
        return 0.0
    ok_n = sum(1 for h in history if h.get("ok"))
    return ok_n / len(history)


def _egress_score(ep: dict) -> float:
    ver = ep.get("verification") or {}
    if ver.get("egress", {}).get("status") == "VERIFIED":
        return 1.0
    if ver.get("egress", {}).get("status") == "INVALID":
        return 0.0
    return 0.0     # UNVERIFIED → صفر (نه سبز جعلی)


def score_endpoint(ep: dict, mode: str = "AUTO") -> dict:
    """امتیاز کامل + زیر-امتیازها + penalties (شفاف — قابل نمایش در UI)."""
    weights = MODE_WEIGHTS.get(mode, db.get_setting("score_weights", DEFAULT_WEIGHTS))
    if mode == "AUTO":
        weights = db.get_setting("score_weights", DEFAULT_WEIGHTS)
    sub = {
        "latency": _latency_score(ep.get("latency_ms")),
        "jitter": _jitter_score(ep.get("jitter_ms")),
        "packet_loss": _loss_score(ep.get("packet_loss")),
        "uptime": _uptime_score(ep.get("uptime_pct")),
        "availability": _availability_score(ep),
        "egress": _egress_score(ep),
    }
    base = 100.0 * sum(weights.get(k, 0.0) * v for k, v in sub.items())

    # ── penalties (سند: high latency / jitter / loss / unstable / failed verify) ─
    penalties = {}
    lat = ep.get("latency_ms")
    if lat is not None and lat > 500:
        penalties["high_latency"] = -10.0
    jit = ep.get("jitter_ms")
    if jit is not None and jit > 80:
        penalties["high_jitter"] = -10.0
    loss = ep.get("packet_loss") or 0.0
    if loss >= 0.10:
        penalties["packet_loss"] = -15.0
    samples = (ep.get("verification") or {}).get("metrics", {}).get("samples") or []
    if len(samples) >= 3:
        mean = sum(samples) / len(samples)
        var = sum((x - mean) ** 2 for x in samples) / len(samples)
        if (var ** 0.5) > 60:
            penalties["unstable"] = -8.0

    ver = ep.get("verification") or {}
    eg_status = (ver.get("egress") or {}).get("status")
    if eg_status == "INVALID":
        return {"score": 0.0, "sub": sub, "penalties": {"failed_verification": -100.0},
                "weights": weights, "note": "egress verify ناموفق — INVALID"}
    if eg_status == "UNVERIFIED":
        penalties["unverified_egress"] = -20.0     # هرگز active بدون verify کامل

    total = max(0.0, min(100.0, base + sum(penalties.values())))
    return {"score": round(total, 1), "sub": sub,
            "penalties": penalties or {}, "weights": weights}

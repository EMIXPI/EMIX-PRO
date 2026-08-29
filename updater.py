# updater.py — بروزرسانی پنل بر اساس مانیفست JSON که یک Cloudflare Worker
# تولید می‌کند (به‌جای فایل PHP روی InfinityFree که به‌خاطر anti-bot/محدودیت
# منابع کنار گذاشته شد). مانیفست شامل نسخه، توضیحات و لیست فایل‌های
# قابل‌دانلود (هر کدام با URL و sha1) است.
# + نگهداری تاریخچه‌ی کامل بروزرسانی‌ها (زمان، نسخه، توضیحات) روی دیسک دائمی
# + کش سراسری برای مانیفست تا صرف‌نظر از تعداد کاربران پنل، فشار درخواست به
#   سرور Worker ثابت و کم بماند (Cloudflare Workers هم سقف رایگان دارن،
#   پس این کش هنوز لازمه)
import asyncio, os, time, traceback, re, json, hashlib
from pathlib import Path
from collections import deque
import httpx

# آدرس Worker مانیفست. مقدار پیش‌فرض روی ساب‌دامین workers.dev شماست؛ در صورت
# نیاز (مثلاً بعد از ست‌کردن دامنه‌ی اختصاصی روی Worker) می‌توانید با متغیر
# محیطی UPDATE_MANIFEST_URL آن را override کنید.
UPDATE_MANIFEST_URL = os.environ.get(
    "UPDATE_MANIFEST_URL", "https://rvg-update.arvin341az.workers.dev/version.json"
)

APP_DIR = Path(os.environ.get("APP_DIR", os.getcwd()))
LOCAL_VERSION_FILE = APP_DIR / "version.txt"

# سازگاری با main.py که هنوز REPO/BRANCH رو از updater import می‌کنه
# (مربوط به نسخه‌ی قدیمی گیت‌هابی). این‌جا دیگه معنای واقعی «ریپو/برنچ»
# ندارن، فقط برای جلوگیری از ImportError نگه داشته شدن. در پنل به‌جاشون
# آدرس مانیفست Worker نمایش داده می‌شه.
REPO = UPDATE_MANIFEST_URL
BRANCH = "cf-worker-manifest"

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
HISTORY_FILE = DATA_DIR / "update_history.json"

update_log: deque = deque(maxlen=300)
update_state = {"running": False, "progress": 0}

# ── کش سراسری مانیفست ─────────────────────────────────────────────────────────
# درخواست از سمت سرور پنل به Worker زده می‌شود، نه از مرورگر هر کاربر. بدون این
# کش، اگر پنل هزاران کاربر هم‌زمان داشته باشد که هر کدام مرتب /api/version را
# صدا می‌زنند، فشار زیادی روی Worker (که با وجود اسکیل بالا، سقف رایگان
# 100k req/day داره) وارد می‌شود. با این کش، صرف‌نظر از تعداد کاربران،
# فقط هر MANIFEST_CACHE_TTL ثانیه یک‌بار درخواست واقعی زده می‌شود.
_manifest_cache: dict = {"data": None, "ts": 0.0}
MANIFEST_CACHE_LOCK = asyncio.Lock()
MANIFEST_CACHE_TTL = float(os.environ.get("MANIFEST_CACHE_TTL", "120"))  # ثانیه

# ── قفل بروزرسانی خودکار (EMIX) ────────────────────────────────────────────────
# نسخه‌ی فعلی پنل (EMIX با رابط کاربری بازطراحی‌شده) نباید توسط مانیفست Worker
# بازنویسی شود؛ در غیر این صورت طراحی و برندینگ به نسخه‌ی اصلی برمی‌گردد.
# پیش‌فرض: بروزرسانی کاملاً غیرفعال است. برای فعال‌کردن دوباره، متغیر محیطی
# DISABLE_UPDATES را روی "0" تنظیم کنید.
UPDATES_DISABLED = os.environ.get("DISABLE_UPDATES", "1") != "0"


def _log(msg: str):
    update_log.append({"time": time.time(), "msg": msg})
    print(f"[UPDATER] {msg}", flush=True)


def _parse_kv_text(text: str) -> dict:
    """پارس فایل محلی version.txt (فرمت key=value) که بعد از هر آپدیت نوشته می‌شود."""
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().lower()
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        result[k] = v
    return result


def _parse_version_tuple(v: str):
    """'9.4' -> (9, 4) — برای مقایسه‌ی عددی صحیح بین نسخه‌ها."""
    if not v:
        return None
    parts = re.findall(r"\d+", v)
    if not parts:
        return None
    return tuple(int(p) for p in parts)


def is_newer_version(latest: str, current: str) -> bool:
    """True فقط وقتی latest واقعاً از current بزرگ‌تر باشد (مقایسه‌ی عددی)."""
    if not latest:
        return False
    if not current or current == "نامشخص":
        return True
    lv, cv = _parse_version_tuple(latest), _parse_version_tuple(current)
    if lv is not None and cv is not None:
        return lv > cv
    return latest != current


def get_current_version_info() -> dict:
    """نسخه و توضیحات فعلی نصب‌شده روی سرور، از فایل محلی version.txt."""
    try:
        if LOCAL_VERSION_FILE.exists():
            kv = _parse_kv_text(LOCAL_VERSION_FILE.read_text(encoding="utf-8"))
            return {
                "version": kv.get("version", "نامشخص"),
                "description": kv.get("description", ""),
            }
    except Exception:
        pass
    return {"version": "نامشخص", "description": ""}


def get_current_version() -> str:
    return get_current_version_info()["version"]


def _write_local_version_file(version: str, description: str):
    """بعد از هر آپدیت موفق، version.txt محلی رو با نسخه‌ی جدید بازنویسی می‌کنه
    تا get_current_version_info() نسخه‌ی درست رو نشون بده."""
    try:
        content = f"version={version}\ndescription={description}\n"
        tmp = LOCAL_VERSION_FILE.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, LOCAL_VERSION_FILE)
    except Exception as e:
        _log(f"⚠️ خطا در نوشتن version.txt محلی: {e}")


async def _fetch_manifest_from_worker() -> dict:
    """درخواست واقعی (بدون کش) به Cloudflare Worker مانیفست."""
    if not UPDATE_MANIFEST_URL:
        return {"error": "UPDATE_MANIFEST_URL تنظیم نشده"}
    url = f"{UPDATE_MANIFEST_URL}?_={int(time.time())}"
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        # روی Worker معمولاً لازم نیست، ولی نگه داشته شده تا اگر جلوی Worker
        # یک پراکسی/CDN دیگه هم قرار گرفت، رفتار یکسان بمونه.
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 404:
                return {"error": "مانیفست version.json پیدا نشد (404) — آدرس UPDATE_MANIFEST_URL یا روت Worker رو چک کنید"}
            r.raise_for_status()

            raw_text = r.text
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError as je:
                # به‌جای پیام مبهم "Expecting value..."، کل محتوای واقعی برگشتی
                # رو (تا سقف مشخص) لاگ می‌کنیم تا خودتون دقیقاً ببینید Worker
                # چی برگردونده (خطای اسکریپت؟ صفحه‌ی Cloudflare error؟ خالی؟).
                ctype = r.headers.get("content-type", "?")
                full = raw_text.strip()
                _log(f"⚠️ پاسخ Worker معتبر (JSON) نبود | content-type={ctype} | status={r.status_code} | طول={len(full)} کاراکتر")
                if not full:
                    return {"error": "پاسخ Worker کاملاً خالی بود (بررسی کنید route درست تنظیم شده)"}
                # چون هر خط لاگ جدا نمایش داده می‌شه، متن رو تکه‌تکه (هر تکه ۵۰۰ کاراکتر) چاپ می‌کنیم
                # تا کل HTML/متن برگشتی رو بدون افتادگی، در باکس لاگ پنل ببینید.
                CHUNK = 500
                total_chunks = (len(full) + CHUNK - 1) // CHUNK
                MAX_CHUNKS = 20  # سقف ~10000 کاراکتر، برای جلوگیری از سنگین شدن لاگ
                for idx in range(min(total_chunks, MAX_CHUNKS)):
                    piece = full[idx * CHUNK: (idx + 1) * CHUNK]
                    _log(f"📄 RAW[{idx+1}/{total_chunks}]: {piece}")
                if total_chunks > MAX_CHUNKS:
                    _log(f"📄 RAW: ... ({total_chunks - MAX_CHUNKS} تکه‌ی دیگه بریده شد ...)")
                if full.lstrip().startswith("<"):
                    return {"error": "Worker به‌جای JSON یک صفحه‌ی HTML برگردوند (احتمالاً خطای Cloudflare) — متن کامل رو در لاگ بالا ببینید"}
                return {"error": f"پاسخ Worker قابل‌پارس نبود: {je} — متن کامل رو در لاگ بالا ببینید"}

            if "version" not in data:
                return {"error": "فرمت مانیفست نامعتبر است (کلید version یافت نشد)"}
            if "files" not in data or not isinstance(data["files"], list):
                return {"error": "فرمت مانیفست نامعتبر است (کلید files یافت نشد)"}
            return {
                "version": data.get("version", ""),
                "description": data.get("description", ""),
                "files": data.get("files", []),
            }
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code} از Worker"}
    except Exception as e:
        return {"error": str(e)}


async def get_latest_version_info() -> dict:
    """
    نسخه و توضیحات مانیفست Worker، با کش سراسری. بین بازه‌های کش، همه‌ی
    کاربران پنل از یک نتیجه‌ی مشترک سرو می‌شوند (مستقل از تعدادشان).
    خروجی این تابع فقط شامل version/description است (برای نمایش در پنل)؛
    لیست files برای دانلود واقعی در perform_update جداگانه گرفته می‌شود.
    """
    if UPDATES_DISABLED:
        # قفل EMIX: هیچ درخواستی به Worker زده نمی‌شود تا نسخه‌ی جدید پیشنهاد نشود.
        return {}
    now = time.time()
    async with MANIFEST_CACHE_LOCK:
        cached = _manifest_cache["data"]
        age = now - _manifest_cache["ts"]
        if cached is not None and age < MANIFEST_CACHE_TTL:
            if cached.get("error"):
                return cached
            return {"version": cached.get("version", ""), "description": cached.get("description", "")}

        result = await _fetch_manifest_from_worker()

        if result.get("error") and cached and not cached.get("error"):
            _log(f"⚠️ خطا در گرفتن مانیفست از Worker ({result['error']}) — استفاده از کش قبلی")
            _manifest_cache["ts"] = now - (MANIFEST_CACHE_TTL * 0.5)
            return {"version": cached.get("version", ""), "description": cached.get("description", "")}

        _manifest_cache["data"] = result
        _manifest_cache["ts"] = now
        if result.get("error"):
            return result
        return {"version": result.get("version", ""), "description": result.get("description", "")}


# سازگاری با کد قدیمی که فقط dict شامل version می‌خواست
async def get_latest_version() -> dict:
    return await get_latest_version_info()


def _check_writable() -> str | None:
    try:
        probe = APP_DIR / ".rvg_write_test"
        probe.write_text("ok")
        probe.unlink()
        return None
    except Exception as e:
        return str(e)


# ── تاریخچه‌ی بروزرسانی‌ها (پایدار روی دیسک، مستقل از کد پروژه) ───────────────
def load_update_history() -> list:
    try:
        if HISTORY_FILE.exists():
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save_update_history_entry(entry: dict):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        hist = load_update_history()
        hist.insert(0, entry)   # جدیدترین بالا
        hist = hist[:200]
        HISTORY_FILE.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        _log(f"⚠️ خطا در ذخیره‌ی تاریخچه‌ی بروزرسانی: {e}")


async def _download_one_file(client: httpx.AsyncClient, entry: dict) -> tuple[bool, str]:
    """یک فایل از مانیفست رو دانلود و روی دیسک (APP_DIR/path) می‌نویسه.
    خروجی: (موفق؟, پیام خطا در صورت شکست)"""
    rel = entry.get("path", "").lstrip("/")
    url = entry.get("url", "")
    expected_sha1 = entry.get("sha1")
    if not rel or not url:
        return False, "ورودی مانیفست ناقص است (path/url خالی)"
    # جلوگیری از path traversal (../ در مسیر فایل)
    target = (APP_DIR / rel).resolve()
    if not str(target).startswith(str(APP_DIR.resolve())):
        return False, f"مسیر غیرمجاز رد شد: {rel}"
    try:
        r = await client.get(url, timeout=30)
        r.raise_for_status()
        content = r.content
        if expected_sha1:
            actual = hashlib.sha1(content).hexdigest()
            if actual != expected_sha1:
                return False, f"عدم تطابق sha1 برای {rel} (دانلود ناقص/خراب)"
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_name(target.name + ".rvgtmp")
        tmp_target.write_bytes(content)
        os.replace(tmp_target, target)
        return True, ""
    except Exception as e:
        return False, str(e)


async def perform_update() -> bool:
    """مانیفست Worker رو می‌گیره، فایل‌های لیست‌شده رو دانلود و جایگزین می‌کنه،
    و در پایان version.txt محلی رو با نسخه‌ی جدید بروزرسانی می‌کنه."""
    if UPDATES_DISABLED:
        _log("⛔ بروزرسانی غیرفعال است — نسخه‌ی EMIX قفل شده تا طراحی سفارشی حفظ شود.")
        update_state["running"] = False
        return False
    update_state["running"] = True
    update_state["progress"] = 1
    _log(f"شروع بروزرسانی | MANIFEST={UPDATE_MANIFEST_URL or 'خالی!'} | APP_DIR={APP_DIR}")

    write_err = _check_writable()
    if write_err:
        _log(f"❌ عدم دسترسی نوشتن روی {APP_DIR}: {write_err}")
        _log("فایل‌سیستم این کانتینر احتمالاً read-only است.")
        update_state["running"] = False
        return False

    if not UPDATE_MANIFEST_URL:
        _log("❌ UPDATE_MANIFEST_URL تنظیم نشده.")
        update_state["running"] = False
        return False

    old_version = get_current_version()

    _log("در حال دریافت مانیفست از Cloudflare Worker...")
    update_state["progress"] = 5
    manifest = await _fetch_manifest_from_worker()
    if manifest.get("error"):
        _log(f"❌ خطا در دریافت مانیفست: {manifest['error']}")
        update_state["running"] = False
        _save_update_history_entry({
            "time": time.time(),
            "from_version": old_version,
            "to_version": "نامشخص",
            "description": "",
            "status": "err",
            "error": manifest["error"],
        })
        return False

    new_version = manifest.get("version", "")
    new_description = manifest.get("description", "")
    files = manifest.get("files", [])
    _log(f"مانیفست دریافت شد. نسخه‌ی مقصد: {new_version} | تعداد فایل‌ها: {len(files)}")
    update_state["progress"] = 15

    if not files:
        _log("❌ لیست فایل‌ها در مانیفست خالی است؛ بروزرسانی لغو شد.")
        update_state["running"] = False
        return False

    try:
        written, failed = 0, 0
        fail_msgs = []
        async with httpx.AsyncClient(follow_redirects=True) as client:
            total = len(files)
            for i, entry in enumerate(files, start=1):
                ok, err = await _download_one_file(client, entry)
                if ok:
                    written += 1
                else:
                    failed += 1
                    fail_msgs.append(f"{entry.get('path','?')}: {err}")
                    _log(f"⚠️ خطا در دانلود {entry.get('path','?')}: {err}")
                # پیشرفت بین 15 تا 90 درصد رو متناسب با تعداد فایل‌ها آپدیت کن
                update_state["progress"] = 15 + int((i / total) * 75)

        _log(f"دانلود تمام شد. نوشته‌شده: {written} | خطادار: {failed}")
        update_state["progress"] = 92

        if written == 0:
            _log("❌ هیچ فایلی با موفقیت دانلود نشد؛ بروزرسانی لغو شد.")
            update_state["running"] = False
            _save_update_history_entry({
                "time": time.time(),
                "from_version": old_version,
                "to_version": new_version,
                "description": new_description,
                "status": "err",
                "error": "; ".join(fail_msgs[:5]) or "دانلود هیچ فایلی موفق نبود",
            })
            return False

        # نسخه‌ی محلی رو با مقدار جدید بروزرسانی کن (این جایگزین «فایل version.txt
        # داخل ریپو» در روش قبلی گیت‌هابیه، چون اینجا خبری از تارگز کل ریپو نیست)
        _write_local_version_file(new_version, new_description)

        _log(f"✅ بروزرسانی با موفقیت اعمال شد. نسخه‌ی جدید: {new_version}")
        _log("سرور در حال راه‌اندازی مجدد...")
        update_state["progress"] = 100

        # کش مانیفست رو باطل می‌کنیم تا بلافاصله بعد از ری‌استارت، نسخه‌ی
        # واقعی و تازه نمایش داده بشه.
        _manifest_cache["data"] = None
        _manifest_cache["ts"] = 0.0

        _save_update_history_entry({
            "time": time.time(),
            "from_version": old_version,
            "to_version": new_version,
            "description": new_description,
            "status": "ok",
            "note": (f"{failed} فایل با خطا رد شد" if failed else None),
        })
        return True

    except Exception as exc:
        _log(f"❌ خطای غیرمنتظره: {exc}")
        _log(traceback.format_exc()[-800:])
        _save_update_history_entry({
            "time": time.time(),
            "from_version": old_version,
            "to_version": new_version,
            "description": new_description,
            "status": "err",
            "error": str(exc),
        })
        return False
    finally:
        update_state["running"] = False

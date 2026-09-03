# tests/conftest.py — shared fixtures for the EMIX-PRO test suite.
# Adds the project root to sys.path so `import main` / `import config_layer`
# works without installation.

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Pre-set test env vars before any EMIX module imports.
os.environ.setdefault("PORT", "8765")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("RAILWAY_PUBLIC_DOMAIN", "test.example.com")
os.environ.setdefault("DATA_DIR", "/tmp/emix-test-data")
# v12: تست‌سایت با پروفایل full اجرا می‌شود تا «همه‌ی» موتورها پوشش داده
# شوند (رفتار v11). پروفایل core (پیش‌فرض production) با بوت‌های subprocess
# در tests/integration/test_core_revival.py آزمایش می‌شود.
os.environ.setdefault("EMIX_PROFILE", "full")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

# v12: هر session با state تازه شروع می‌شود — totals ترافیک ذاتاً «تجمعی»
# هستند و فایل state پابرجاست؛ بدون این پاک‌سازی، تست‌های مرزی مثل
# totals-roundtrip به آلودگی ران‌های قبلی حساس می‌شوند (سرویس‌محور:
# هر deploy تازه = state تازه).
_state_file = Path(os.environ["DATA_DIR"]) / "rvg_state.json"
try:
    _state_file.unlink()
except FileNotFoundError:
    pass
except Exception:
    pass

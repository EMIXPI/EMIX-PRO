# link_emit.py — صدور share-link های پروتکل‌های جدید (آزاد، بدون runtime تغییر)
#
# این module فقط لینک تولید می‌کند. هیچ inbound جدیدی اضافه نمی‌کند.
# پس پایداری اصلی پروژه حفظ می‌شود.
#
# منبع: 3X-ui.3.7.0 audit report recommendation #1-7, 13
# فعال‌سازی: experimental.py is_enabled("reality_link_emit") و ...

import base64
import hashlib
import json
import secrets
import time
import urllib.parse

# ─── VMESS base64-JSON share-link ──────────────────────────────────────────
# فرمت: vmess://<base64-JSON>
# JSON: {v,ps,add,port,id,aid,net,type,host,path,tls,sni,alpn,fp,scv}
def gen_vmess_link(
    address: str,
    port: int,
    uuid: str,
    name: str = "",
    aid: int = 0,
    net: str = "ws",
    host: str = "",
    path: str = "/",
    tls: str = "",
    sni: str = "",
    alpn: str = "",
    fp: str = "chrome",
) -> str:
    obj = {
        "v": "2",
        "ps": name,
        "add": address,
        "port": str(port),
        "id": uuid,
        "aid": str(aid),
        "net": net,
        "type": "none",
        "host": host,
        "path": path,
        "tls": tls,
        "sni": sni,
        "alpn": alpn,
        "fp": fp,
        "scy": "auto",
    }
    raw = json.dumps(obj, separators=(",", ":"))
    b64 = base64.b64encode(raw.encode()).decode()
    return f"vmess://{b64}"


# ─── VLESS-Reality share-link ──────────────────────────────────────────────
# فرمت: vless://<uuid>@<host>:<port>?...&pbk=<pubkey>&sid=<shortid>&sni=<sni>&fp=<fp>&spx=<spx>&type=<type>
def gen_vless_reality_link(
    address: str,
    port: int,
    uuid: str,
    pbk: str,  # x25519 public key (用户提供)
    sid: str = "",  # short id (用户提供或随机)
    sni: str = "www.cloudflare.com",
    fp: str = "chrome",
    spx: str = "/",
    flow: str = "xtls-rprx-vision",
    name: str = "",
) -> str:
    if not sid:
        sid = secrets.token_hex(8)
    params = {
        "encryption": "none",
        "flow": flow,
        "security": "reality",
        "sni": sni,
        "fp": fp,
        "pbk": pbk,
        "sid": sid,
        "spx": spx,
        "type": "tcp",
    }
    q = urllib.parse.urlencode(params, doseq=True)
    frag = urllib.parse.quote(name) if name else ""
    return f"vless://{uuid}@{address}:{port}?{q}#{frag}"


# ─── Trojan-Reality share-link ─────────────────────────────────────────────
def gen_trojan_reality_link(
    address: str,
    port: int,
    password: str,
    pbk: str,
    sid: str = "",
    sni: str = "www.cloudflare.com",
    fp: str = "chrome",
    spx: str = "/",
    name: str = "",
) -> str:
    if not sid:
        sid = secrets.token_hex(8)
    params = {
        "security": "reality",
        "sni": sni,
        "fp": fp,
        "pbk": pbk,
        "sid": sid,
        "spx": spx,
        "type": "tcp",
    }
    q = urllib.parse.urlencode(params, doseq=True)
    frag = urllib.parse.quote(name) if name else ""
    return f"trojan://{urllib.parse.quote(password)}@{address}:{port}?{q}#{frag}"


# ─── Shadowsocks-2022 (SIP022) link ───────────────────────────────────────
# فرمت: ss://method:2022-blake3-aes-256-gcm@host:port#name
# یا با encryption: ss://base64(method:pass@host:port)#name (legacy)
def gen_ss2022_link(
    method: str,
    password: str,
    address: str,
    port: int,
    name: str = "",
) -> str:
    """صدور SS-2022 link با cipher مدرن (2022-blake3-aes-256-gcm و امثال)."""
    user_part = f"{method}:{password}"
    user_b64 = base64.urlsafe_b64encode(user_part.encode()).decode().rstrip("=")
    frag = urllib.parse.quote(name) if name else ""
    return f"ss://{user_b64}@{address}:{port}#{frag}"


# ─── FinalMask share-link emission (recommendation #7) ────────────────────
# این فقط لینک emits می‌کند با param های finalmask. client-side (xray-core 26+)
# خودش TLS fragmentation/obfs را انجام می‌دهد.
def gen_finalmask_link(
    base_link: str,
    fm_config: dict = None,
) -> str:
    """اضافه‌کردن param های FinalMask به یک base link.
    fm_config شامل: tls_fragment (bool), salamander_obfs (bool),
    bbr (bool), port_hopping (str range), noise (int bytes),
    xmc (str), sudoku (bool)."""
    if not fm_config:
        fm_config = {}
    # اگر base_link قبلاً query string دارد، با & اضافه می‌کنیم
    sep = "&" if "?" in base_link else "?"
    parts = []
    for k, v in fm_config.items():
        if isinstance(v, bool):
            parts.append(f"fm_{k}={'1' if v else '0'}")
        else:
            parts.append(f"fm_{k}={urllib.parse.quote(str(v))}")
    if not parts:
        return base_link
    return f"{base_link}{sep}{'&'.join(parts)}"


# ─── Pinned Cert SHA-256 (recommendation #3) ──────────────────────────────
def add_pinned_cert_to_link(link: str, pcs: str, vcn: str = "") -> str:
    """اضافه‌کردن pcs (Pinned Cert SHA-256) و vcn (Verify Cert Name) به link."""
    sep = "&" if "?" in link else "?"
    parts = [f"pcs={urllib.parse.quote(pcs)}"]
    if vcn:
        parts.append(f"vcn={urllib.parse.quote(vcn)}")
    return f"{link}{sep}{'&'.join(parts)}"


# ─── Per-client Reality spiderX path (recommendation #4) ─────────────────
def gen_spiderx_path(client_uuid: str, sub_id: str = "") -> str:
    """مسیر منحصر بفرد spiderX به ازای کلاینت.
    فرمول: sha256(seed | subId)[:15]
    جلوگیری از DPI correlation بین کلاینت‌ها."""
    seed = client_uuid + "|" + (sub_id or client_uuid)
    h = hashlib.sha256(seed.encode()).hexdigest()[:15]
    return f"/{h}"


# ─── uTLS fingerprint emission (recommendation #2) ───────────────────────
UTLS_FINGERPRINTS = [
    "chrome", "firefox", "safari", "edge", "ios", "android",
    "random", "randomized", "chrome_psk", "chrome_password",
]


def add_utls_fingerprint(link: str, fp: str = "chrome") -> str:
    """اضافه‌کردن fp=chrome (یا firefox/safari/etc) به link."""
    if fp not in UTLS_FINGERPRINTS:
        fp = "chrome"
    sep = "&" if "?" in link else "?"
    return f"{link}{sep}fp={fp}"


# ─── Subscription formats (recommendation #9) ────────────────────────────
def gen_subscription_raw(links: list[str]) -> str:
    """فرمت raw: هر link در یک خط."""
    return "\n".join(links)


def gen_subscription_json(links: list[str], remarks: list[str] = None) -> str:
    """فرمت JSON: v2rayN/sing-box compatible."""
    out = []
    for i, lnk in enumerate(links):
        remark = remarks[i] if remarks and i < len(remarks) else f"config-{i+1}"
        out.append({"remark": remark, "url": lnk})
    return json.dumps({"version": "1", "configs": out}, ensure_ascii=False, indent=2)


def gen_subscription_clash(links: list[str], remarks: list[str] = None) -> str:
    """فرمت Clash.Meta YAML (ساده — فقط proxies)."""
    out = ["proxies:"]
    for i, lnk in enumerate(links):
        remark = remarks[i] if remarks and i < len(remarks) else f"config-{i+1}"
        # crude parsing — فقط vless/trojan/ss
        if lnk.startswith("vless://"):
            out.append(f"  - name: \"{remark}\"")
            out.append(f"    type: vless")
            out.append(f"    url: \"{lnk}\"")
        elif lnk.startswith("trojan://"):
            out.append(f"  - name: \"{remark}\"")
            out.append(f"    type: trojan")
            out.append(f"    url: \"{lnk}\"")
        elif lnk.startswith("ss://"):
            out.append(f"  - name: \"{remark}\"")
            out.append(f"    type: ss")
            out.append(f"    url: \"{lnk}\"")
        elif lnk.startswith("vmess://"):
            out.append(f"  - name: \"{remark}\"")
            out.append(f"    type: vmess")
            out.append(f"    url: \"{lnk}\"")
    return "\n".join(out)


def gen_subscription_encrypted(links: list[str], key: str) -> str:
    """فرمت base64-encrypted (برای defeat naive DPI)."""
    raw = gen_subscription_raw(links).encode()
    # XOR simple cipher — فقط برای obfuscation naive
    key_bytes = key.encode()
    out = bytearray(len(raw))
    for i, b in enumerate(raw):
        out[i] = b ^ key_bytes[i % len(key_bytes)]
    return base64.b64encode(bytes(out)).decode()

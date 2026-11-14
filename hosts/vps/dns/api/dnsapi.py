#!/usr/bin/env python3
"""HTTP API over knotc for the doesnmlab.xyz zone, with a small web UI.

Auth has two legs:
  * scripts send `Authorization: Bearer <token>` from /etc/dnsapi/token;
  * the browser logs in through Dex (OIDC authorization-code flow run server-side,
    because Dex sets no CORS headers) and gets a signed session cookie. The access
    token never reaches the browser.

Writes are Knot transactions: begin -> zone-set -> zone-diff -> commit, so a change
is all-or-nothing and the UI can show a diff before applying.
"""
import base64
import hmac
import os
import json
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ZONE = os.environ.get("ZONE", "doesnmlab.xyz")
BIND = (os.environ.get("BIND", "0.0.0.0"), int(os.environ.get("PORT", "8088")))
KNOT_SOCKET = os.environ.get("KNOT_SOCKET", "/rundir/knot.sock")
BASE_URL = "https://dns.doesnmlab.xyz"
DEX_ISSUER = "https://nexus.doesnmlab.xyz/dex"
CLIENT_ID = "dns-api"

TOKEN_FILE = Path(os.environ.get("TOKEN_FILE", "/secrets/token"))
OIDC_SECRET_FILE = Path(os.environ.get("OIDC_SECRET_FILE", "/secrets/oidc-secret"))
SESSION_SECRET_FILE = Path(os.environ.get("SESSION_SECRET_FILE", "/secrets/session.key"))
STATIC = Path(os.environ.get("STATIC_DIR", "/opt/dnsapi/static"))

SAFE_TYPES = {"TXT", "SRV", "TLSA"}
REDIRECT_TYPES = {"A", "AAAA", "CNAME", "MX"}
CRITICAL_TYPES = {"NS", "DS", "CAA"}
OWNER_RE = re.compile(r"^(@|\*|[a-zA-Z0-9_][a-zA-Z0-9_.*-]{0,252})$")
TYPE_RE = re.compile(r"^[A-Z][A-Z0-9]{0,9}$")
SESSION_TTL = 12 * 3600


class ApiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def secret(path: Path, create=False) -> str:
    if create and not path.exists():
        path.write_text(secrets.token_hex(32))
        path.chmod(0o600)
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def knotc(*args):
    proc = subprocess.run(["knotc", "-s", KNOT_SOCKET, *args], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise ApiError(502, (proc.stderr or proc.stdout).strip() or "knotc failed")
    return proc.stdout


def list_records():
    """Read the zone as served.

    Knot 3.5 prints each line as "[zone.] owner ttl TYPE rdata", 3.6 (and the
    socket path generally) prints "owner ttl TYPE rdata". Both are handled, and
    DNSSEC housekeeping types are dropped: they are regenerated, not managed.
    """
    rows = []
    for raw in knotc("zone-read", ZONE).splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("["):
            line = line.split("]", 1)[1].strip()
        parts = line.split(None, 3)
        if len(parts) < 4 or not parts[1].isdigit():
            continue
        owner, ttl, rtype, rdata = parts
        if rtype in ("RRSIG", "NSEC", "NSEC3", "DNSKEY", "CDS", "CDNSKEY", "SOA"):
            continue
        rows.append({"owner": owner.rstrip("."), "ttl": int(ttl), "type": rtype, "rdata": rdata})
    return rows


def check_record(rec: dict) -> dict:
    owner = (rec.get("owner") or "").strip()
    rtype = (rec.get("type") or "").strip().upper()
    rdata = rec.get("rdata") if isinstance(rec.get("rdata"), str) else ""
    rdata = rdata.strip()
    ttl = rec.get("ttl", 3600)
    if not OWNER_RE.match(owner):
        raise ApiError(400, f"bad owner: {owner!r}")
    if not TYPE_RE.match(rtype):
        raise ApiError(400, f"bad type: {rtype!r}")
    if "\n" in rdata or "\r" in rdata:
        raise ApiError(400, "rdata must be a single line")
    if rtype in ("A", "AAAA", "CNAME", "MX", "NS") and not rdata:
        raise ApiError(400, f"{rtype} needs a value")
    if not isinstance(ttl, int) or not (60 <= ttl <= 86400):
        raise ApiError(400, "ttl must be an integer between 60 and 86400")
    return {"owner": owner, "type": rtype, "rdata": rdata, "ttl": ttl}


def require_confirmation(records, body):
    for rec in records:
        if rec["type"] in CRITICAL_TYPES and body.get("confirm_zone") != ZONE:
            raise ApiError(428, f'{rec["type"]} hands over the domain: send confirm_zone="{ZONE}"')
        if rec["type"] in REDIRECT_TYPES and body.get("confirm") is not True:
            raise ApiError(428, f'{rec["type"]} redirects traffic: send "confirm": true')


# --- OIDC ------------------------------------------------------------------
_discovery = {}


def discovery():
    if not _discovery:
        url = f"{DEX_ISSUER}/.well-known/openid-configuration"
        with urllib.request.urlopen(url, timeout=10) as r:
            _discovery.update(json.load(r))
    return _discovery


def sign_session(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    mac = hmac.new(secret(SESSION_SECRET_FILE, create=True).encode(), raw.encode(), "sha256").hexdigest()
    return f"{raw}.{mac}"


def verify_session(value: str):
    try:
        raw, mac = value.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret(SESSION_SECRET_FILE, create=True).encode(), raw.encode(), "sha256").hexdigest()
    if not hmac.compare_digest(mac, expected):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw))
    except Exception:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "dnsapi/2"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # --- helpers
    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, url, extra_headers=None):
        self.send_response(302)
        self.send_header("Location", url)
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _session(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == "dnsapi_session":
                return verify_session(value)
        return None

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        token = secret(TOKEN_FILE)
        if token and hmac.compare_digest(header, f"Bearer {token}"):
            return True
        return self._session() is not None

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > 64 * 1024:
            raise ApiError(413, "body too large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw or b"{}")
        except ValueError:
            raise ApiError(400, "invalid JSON")

    # --- routes
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/login":
                state = secrets.token_urlsafe(16)
                url = discovery()["authorization_endpoint"] + "?" + urllib.parse.urlencode({
                    "client_id": CLIENT_ID,
                    "response_type": "code",
                    "scope": "openid profile email",
                    "redirect_uri": f"{BASE_URL}/callback",
                    "state": state,
                })
                return self._redirect(url, {"Set-Cookie": f"dnsapi_state={state}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=600"})

            if path == "/callback":
                code = (query.get("code") or [""])[0]
                state = (query.get("state") or [""])[0]
                cookie_state = self.headers.get("Cookie", "")
                if not code or f"dnsapi_state={state}" not in cookie_state:
                    raise ApiError(400, "bad state")
                data = urllib.parse.urlencode({
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": CLIENT_ID,
                    "client_secret": secret(OIDC_SECRET_FILE),
                    "redirect_uri": f"{BASE_URL}/callback",
                }).encode()
                req = urllib.request.Request(discovery()["token_endpoint"], data=data,
                                             headers={"Content-Type": "application/x-www-form-urlencoded"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    tokens = json.load(r)
                info_req = urllib.request.Request(discovery()["userinfo_endpoint"],
                                                  headers={"Authorization": f"Bearer {tokens['access_token']}"})
                with urllib.request.urlopen(info_req, timeout=10) as r:
                    user = json.load(r)
                cookie = sign_session({"user": user.get("email") or user.get("name", "?"), "exp": int(time.time()) + SESSION_TTL})
                return self._redirect("/", {"Set-Cookie": f"dnsapi_session={cookie}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={SESSION_TTL}"})

            if path in ("/", "/index.html"):
                if self._session() is None:
                    return self._redirect("/login")
                body = (STATIC / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if not self._authorized():
                raise ApiError(401, "unauthorized")
            if path == "/health":
                return self._json(200, {"ok": True, "zone": ZONE, "user": (self._session() or {}).get("user")})
            if path == "/records":
                status = knotc("zone-status", ZONE)
                m = re.search(r"serial: (\d+)", status)
                return self._json(200, {"zone": ZONE, "serial": m.group(1) if m else None,
                                        "records": list_records()})
            raise ApiError(404, "not found")
        except ApiError as e:
            self._json(e.code, {"error": e.message})
        except urllib.error.HTTPError as e:
            self._json(401, {"error": f"oidc: {e.code}"})
        except Exception as e:  # noqa: BLE001 - the UI must show something useful
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        try:
            if not self._authorized():
                raise ApiError(401, "unauthorized")
            body = self._body()
            records = [check_record(r) for r in body.get("records", [])]
            if not records:
                raise ApiError(400, "no records in request")
            require_confirmation(records, body)

            if path == "/preview":
                knotc("zone-begin", ZONE)
                try:
                    for r in records:
                        knotc("zone-set", ZONE, r["owner"], str(r["ttl"]), r["type"], r["rdata"])
                    diff = knotc("zone-diff", ZONE)
                finally:
                    knotc("zone-abort", ZONE)
                return self._json(200, {"preview": diff.strip(), "records": records})

            if path == "/apply":
                knotc("zone-begin", ZONE)
                for r in records:
                    knotc("zone-set", ZONE, r["owner"], str(r["ttl"]), r["type"], r["rdata"])
                knotc("zone-commit", ZONE)
                return self._json(200, {"applied": records, "status": knotc("zone-status", ZONE).strip()})

            raise ApiError(404, "not found")
        except ApiError as e:
            self._json(e.code, {"error": e.message})


def main():
    secret(SESSION_SECRET_FILE, create=True)
    server = ThreadingHTTPServer(BIND, Handler)
    print(f"listening on {BIND[0]}:{BIND[1]} for {ZONE}", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()

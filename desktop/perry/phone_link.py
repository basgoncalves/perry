"""
Phone link — lets Perry on your Android phone talk to Perry on this PC.

A tiny HTTP server on the local network (stdlib only). Every request must
carry the pairing token in an ``X-Perry-Token`` header; anything else gets
401. Endpoints:

    GET  /ping      -> {"ok": true, "name": "Perry", "host": ...}
    POST /wake      -> runs the "Daddy's home" restore on this PC
    POST /command   -> body {"text": "..."}; routed like a spoken phrase,
                       returns {"reply": "..."} for the phone to speak

Pair the phone with:  python . --phone   (prints address + token)
"""

from __future__ import annotations

import hmac
import json
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 47812


def ensure_token(cfg: dict, save_fn=None) -> str:
    """Return the pairing token, creating and saving one on first use."""
    tok = cfg.get("phone_link_token") or ""
    if not tok:
        tok = secrets.token_urlsafe(18)
        cfg["phone_link_token"] = tok
        if save_fn:
            try:
                save_fn(cfg)
            except OSError:
                pass
    return tok


def lan_ip() -> str:
    """Best guess at this PC's address on the Wi-Fi/LAN (no packets sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class PhoneLink:
    def __init__(self, perry, token: str, port: int = DEFAULT_PORT,
                 host: str = "0.0.0.0"):
        self.perry = perry
        self.token = token
        self.port = port
        self.host = host
        self.server: ThreadingHTTPServer | None = None
        self.error: str | None = None

    # -- request handling (kept off the handler so tests can call it) -------
    def authorized(self, header: str | None) -> bool:
        return bool(header) and hmac.compare_digest(header, self.token)

    def handle(self, method: str, path: str, body: dict) -> tuple[int, dict]:
        p = self.perry
        if method == "GET" and path == "/ping":
            return 200, {"ok": True, "name": getattr(p, "name", "Perry"),
                         "host": socket.gethostname()}
        if method == "POST" and path == "/wake":
            p.hud.set_heard("phone: Daddy's home")
            p.wake()
            return 200, {"reply": "Welcome home. Restoring your session."}
        if method == "POST" and path == "/command":
            text = str(body.get("text", "")).strip()
            if not text:
                return 400, {"error": "empty text"}
            return 200, {"reply": p.phone_command(text)}
        return 404, {"error": "unknown endpoint"}

    # -- server ---------------------------------------------------------------
    def start(self) -> bool:
        link = self

        class Handler(BaseHTTPRequestHandler):
            def _go(self, method):
                if not link.authorized(self.headers.get("X-Perry-Token")):
                    return self._send(401, {"error": "bad token"})
                body = {}
                n = int(self.headers.get("Content-Length") or 0)
                if n:
                    try:
                        body = json.loads(self.rfile.read(min(n, 8192)) or b"{}")
                    except ValueError:
                        return self._send(400, {"error": "bad json"})
                try:
                    code, out = link.handle(method, self.path.split("?")[0], body)
                except Exception as e:
                    code, out = 500, {"error": str(e)}
                self._send(code, out)

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self): self._go("GET")
            def do_POST(self): self._go("POST")
            def log_message(self, *_a): pass

        try:
            self.server = ThreadingHTTPServer((self.host, self.port), Handler)
        except OSError as e:
            self.error = f"phone link port {self.port} busy: {e}"
            return False
        threading.Thread(target=self.server.serve_forever, daemon=True,
                         name="perry-phone-link").start()
        return True

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None


def print_pairing(cfg: dict, save_fn=None) -> int:
    tok = ensure_token(cfg, save_fn)
    port = int(cfg.get("phone_link_port", DEFAULT_PORT))
    print("Perry phone link — enter these in the phone app's settings:\n")
    print(f"  PC address : {lan_ip()}")
    print(f"  Port       : {port}")
    print(f"  Token      : {tok}\n")
    print("Phone and PC must be on the same Wi-Fi. If the phone can't connect,")
    print("run 'Allow Perry Phone Link.bat' once (as administrator) to open the firewall.")
    return 0

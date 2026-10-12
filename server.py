"""Local web server: python3 server.py  ->  http://localhost:8000"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from answer import handle, to_json
from session import Sessions, reply
from recommender import load_data

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = load_data()
SESSIONS = Sessions()


def recommend_text(q: str) -> dict:
    return to_json(handle(q, DATA))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/recommend":
            q = (parse_qs(url.query).get("q") or [""])[0][:300]
            self._send(200, json.dumps(recommend_text(q)).encode(), "application/json")
        elif url.path == "/chat":
            qs = parse_qs(url.query)
            q = (qs.get("q") or [""])[0][:300]
            sid = (qs.get("sid") or ["default"])[0][:64]
            self._send(200, json.dumps({"reply": reply(SESSIONS.get(sid), q, DATA)}).encode(), "application/json")
        elif url.path in ("/", "/index.html"):
            with open(os.path.join(ROOT, "web", "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"Serving on http://localhost:{port}")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
